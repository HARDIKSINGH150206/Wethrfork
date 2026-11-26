"""Train SpeedLimitNet with the unroll curriculum on GPU. Real optimizer loop: loss.backward() + optimizer.step()."""

from __future__ import annotations

import argparse
import json
import logging
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from training.data import ROOT, load_archive, load_config, sample_starts, split_bounds
from training.fit_ridge import build_z, load_norm_inputs
from wethrfork.model import NetConfig, SpeedLimitNet, rollout
from wethrfork.normalize import from_z
from wethrfork.physics import CHANNELS, NC, lat_weights

log = logging.getLogger(__name__)


class Ctx:
    """Everything the loops need, already on the device."""

    def __init__(self, cfg: dict, dcfg: dict, device: torch.device) -> None:
        self.arc = load_archive(dcfg)
        art = ROOT / "artifacts"
        clim, s = load_norm_inputs(art)
        self.dev = device
        self.clim = clim.to(device)
        self.s = s.to(device)
        st = torch.from_numpy(np.load(art / "static.npy")).clone()
        st[1] = st[1] / 1000.0
        self.static = st.to(device)
        self.z = build_z(self.arc, clim, s).to(device)
        self.slots = torch.from_numpy(self.arc.slots()).to(device)
        self.tp = torch.from_numpy(self.arc.data[:, 1]).to(device)
        self.phys = torch.from_numpy(self.arc.data).to(device)
        w = torch.from_numpy(lat_weights()).to(device).view(1, 1, 1, -1, 1)
        cw = cfg["loss"]["channel_weights"]
        self.w_lat = w
        self.w_ch = torch.tensor([cw[c] for c in CHANNELS], device=device).view(1, 1, NC, 1, 1)
        self.heavy_mm = cfg["loss"]["heavy_rain_mm"]
        self.heavy_w = cfg["loss"]["heavy_rain_weight"]

    def batch(self, t: torch.Tensor, k: int):
        ar = torch.arange(1, k + 1, device=t.device)
        z0 = self.z[torch.stack([t - 2, t - 1, t], dim=1)]
        tgt = self.z[t[:, None] + ar]
        slots = self.slots[t[:, None] + torch.arange(0, k + 1, device=t.device)]
        heavy = self.tp[t[:, None] + ar] > self.heavy_mm
        return z0, tgt, slots, heavy

    def loss(self, pred: torch.Tensor, tgt: torch.Tensor, heavy: torch.Tensor) -> torch.Tensor:
        wt = self.w_lat * self.w_ch
        wt = wt.expand_as(pred).clone()
        wt[:, :, 1] = wt[:, :, 1] * (1.0 + (self.heavy_w - 1.0) * heavy.float())
        return (wt * (pred - tgt) ** 2).mean()


def _idx(arc, day: str) -> int:
    return int(arc.dates.get_loc(pd.Timestamp(day)))


@torch.no_grad()
def predict_phys(model, ctx: Ctx, init: torch.Tensor, slots: torch.Tensor, steps: int) -> torch.Tensor:
    """init [B,3,6,H,W] physical; slots [B,steps+1] -> [B,steps,6,H,W] physical (no clamps)."""
    prev = torch.stack([(slots[:, 0] - 2) % 366, (slots[:, 0] - 1) % 366, slots[:, 0]], dim=1)
    from wethrfork.normalize import to_z

    z0 = to_z(init, ctx.clim[prev], ctx.s)
    z = rollout(model, z0, slots, ctx.clim, ctx.s, ctx.static, steps)
    return from_z(z, ctx.clim[slots[:, 1:]], ctx.s)


@torch.no_grad()
def evaluate(model, ctx: Ctx, cfg: dict, kit_std: np.ndarray) -> dict:
    """Quick self-grade on the calibration year plus the causality gate on the network alone."""
    from monsoon_r1 import contract as C
    from monsoon_r1 import scoring as S

    model.eval()
    sel = cfg["select_windows"]
    sy = sel["systematic"]
    lo, hi = _idx(ctx.arc, sy["start"]), _idx(ctx.arc, sy["end"])
    ts = torch.arange(lo, hi + 1, int(sy["every_days"]), device=ctx.dev)
    ts = ts[ts + 10 < len(ctx.arc.dates)]
    init = ctx.phys[torch.stack([ts - 2, ts - 1, ts], dim=1)]
    slots = ctx.slots[ts[:, None] + torch.arange(0, 11, device=ctx.dev)]
    pred = predict_phys(model, ctx, init, slots, 10).cpu().numpy()
    truth = ctx.phys[ts[:, None] + torch.arange(1, 11, device=ctx.dev)].cpu().numpy()
    clim_t = ctx.clim[slots[:, 1:]].cpu().numpy()
    last = init[:, -1].cpu().numpy()
    ss = []
    idx = [0, 3, 7]
    for i in range(len(ts)):
        persist = np.repeat(last[i][None], 10, axis=0)
        sk = S.skill_vs_best_ref(pred[i][idx], truth[i][idx], persist[idx], clim_t[i][idx])
        ss.append(float(np.nanmean(sk["ss"])))
    day4 = S.skill_vs_best_ref(pred[:, 3], truth[:, 3], np.repeat(last[:, None], 1, axis=1)[:, 0], clim_t[:, 3])
    # gate on the network alone, per season, both official shocks
    gate = cfg.get("gate", {"near_frac_min": 0.75, "growth_min": 3.0, "far_frac_max": 0.01, "max_z": 4.0})
    passes, total, detail = 0, 0, []
    for season, day in sel["shock"].items():
        t = _idx(ctx.arc, day)
        x = ctx.phys[t - 2 : t + 1][None]
        sl = ctx.slots[t + torch.arange(0, 11, device=ctx.dev)][None]
        for name, box in (("warm_ocean", C.BOX_BAY_OF_BENGAL), ("monsoon_stall", C.BOX_ARABIAN_SEA)):
            pert = torch.from_numpy(S.make_shock(name, x[0, -1].cpu().numpy(), kit_std)).to(ctx.dev)
            x2 = x.clone()
            x2[0, -1] = x2[0, -1] + pert
            out = predict_phys(model, ctx, torch.cat([x, x2]), sl.expand(2, -1), 10).cpu().numpy()
            res = S.causality_checks(out[0], out[1], box, kit_std)
            d = out[1] - out[0]
            e = S._energy(d, kit_std)
            near = S.near_mask(box)
            out_e = np.array([e[k][~near].sum() for k in range(10)])
            growth = float(out_e[3:8].mean() / max(out_e[0], 1e-12))
            zmax = float(np.abs(d / kit_std[None, :, None, None]).max())
            ok = (
                res["finite"]
                and res["nonzero"]
                and res.get("near_frac_day1", 0) >= gate["near_frac_min"]
                and growth >= gate["growth_min"]
                and res["far_frac_max"] <= gate["far_frac_max"]
                and zmax <= gate["max_z"]
            )
            passes += int(ok)
            total += 1
            detail.append(
                (season, name, round(res.get("near_frac_day1", 0), 2), round(growth, 1), round(zmax, 2), bool(ok))
            )
    model.train()
    return {
        "mean_ss": float(np.mean(ss)),
        "gate_pass": passes,
        "gate_total": total,
        "detail": detail,
        "day4_ss_persist": float(np.nanmean(day4["ss_persist"])),
    }


def train(cfg: dict, dcfg: dict, quick: bool = False) -> Path:
    torch.manual_seed(int(cfg["seed"]))
    np.random.seed(int(cfg["seed"]))
    dev = torch.device(cfg["device"] if torch.cuda.is_available() else "cpu")
    ctx = Ctx(cfg, dcfg, dev)
    kit_std = np.array(json.loads((ROOT / dcfg["stats_path"]).read_text())["std"], dtype=np.float32)
    mcfg = cfg["model"]
    net_cfg = NetConfig(
        hidden=mcfg["hidden"],
        conv_blocks=mcfg["conv_blocks"],
        displacement_cap=mcfg["displacement_cap"],
        alpha_init=mcfg["alpha_init"],
    )
    model = SpeedLimitNet(net_cfg).to(dev)
    log.info("parameters: %d on %s", sum(p.numel() for p in model.parameters()), dev)
    out_dir = ROOT / cfg["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    tr = split_bounds(ctx.arc, dcfg, "train")
    o = cfg["optim"]
    best_key = (-1, -1e9)
    history = []
    for si, stage in enumerate(cfg["curriculum"]):
        k = int(stage["unroll"])
        starts = torch.from_numpy(sample_starts(*tr, horizon=k)).to(dev)
        epochs = 1 if quick else int(stage["epochs"])
        base_lr = float(o["lr"]) * cfg.get("lr_scale_by_stage", [1.0] * 9)[si]
        opt = torch.optim.AdamW(model.parameters(), lr=base_lr, weight_decay=float(o["weight_decay"]))
        steps_total = epochs * math.ceil(len(starts) / int(o["batch_size"]))
        step = 0
        for ep in range(epochs):
            perm = starts[torch.randperm(len(starts), device=dev)]
            t0, tot, nb = time.time(), 0.0, 0
            for b0 in range(0, len(perm), int(o["batch_size"])):
                t = perm[b0 : b0 + int(o["batch_size"])]
                z0, tgt, slots, heavy = ctx.batch(t, k)
                if stage.get("input_noise", 0) > 0:
                    z0 = z0 + float(stage["input_noise"]) * torch.randn_like(z0)
                lr = float(o["lr_min"]) + 0.5 * (base_lr - float(o["lr_min"])) * (
                    1 + math.cos(math.pi * step / max(steps_total, 1))
                )
                for g in opt.param_groups:
                    g["lr"] = lr
                pred = rollout(model, z0, slots, ctx.clim, ctx.s, ctx.static, k)
                loss = ctx.loss(pred, tgt, heavy)
                opt.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), float(o["grad_clip"]))
                opt.step()
                tot += loss.item()
                nb += 1
                step += 1
            ev = evaluate(model, ctx, cfg, kit_std)
            key = (ev["gate_pass"], ev["mean_ss"]) if cfg["select"]["require_gate"] else (0, ev["mean_ss"])
            tag = ""
            if k > 1 and key > best_key:
                best_key = key
                torch.save(model.state_dict(), out_dir / "best.pt")
                (out_dir / "best.json").write_text(
                    json.dumps({"stage": si, "epoch": ep, **ev}, indent=1, default=float)
                )
                tag = " *best*"
            log.info(
                "stage %d (K=%d) epoch %d/%d loss %.4f | calib ss %.4f gate %d/%d day4-vs-persist %.3f | %.1fs%s",
                si,
                k,
                ep + 1,
                epochs,
                tot / nb,
                ev["mean_ss"],
                ev["gate_pass"],
                ev["gate_total"],
                ev["day4_ss_persist"],
                time.time() - t0,
                tag,
            )
            history.append({"stage": si, "epoch": ep, "loss": tot / nb, **ev})
            torch.save(model.state_dict(), out_dir / f"stage{si}_last.pt")
    (out_dir / "history.json").write_text(json.dumps(history, indent=1, default=float))
    if not (out_dir / "best.pt").exists():
        torch.save(model.state_dict(), out_dir / "best.pt")
    (out_dir / "nn_config.json").write_text(json.dumps(net_cfg.to_dict()))
    return out_dir / "best.pt"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/train.yaml")
    ap.add_argument("--data-config", default="configs/data.yaml")
    ap.add_argument("--quick", action="store_true", help="one epoch per stage (smoke test)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    cfg = load_config(ROOT / args.config)
    cfg["gate"] = load_config(ROOT / "configs/eval.yaml")["gate"]
    train(cfg, load_config(ROOT / args.data_config), quick=args.quick)


if __name__ == "__main__":
    main()
