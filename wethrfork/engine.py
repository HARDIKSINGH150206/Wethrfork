"""Engine: loads artifacts, runs the served formula  out = clamp( PP(Blend(base)) + [NN(shocked) - NN(base)] ).

A null perturbation skips the shocked run, so the delta is exactly zero and the output equals the plain call.
The engine is deterministic: no dropout, no sampling, no noise.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import torch

from . import MODEL_NAME
from .blend import PostProc, clamp, limit_delta
from .climatology import slot_of_last_day
from .model import NetConfig, SpeedLimitNet, rollout
from .normalize import from_z, to_z
from .physics import MAX_STEPS, NC, NLAT, NLON, T_IN
from .ridge import RidgeHead

log = logging.getLogger(__name__)
ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Engine:
    def __init__(self) -> None:
        self.ready = False
        self.error: str | None = None
        self.model_name = MODEL_NAME
        self.clim: np.ndarray | None = None
        self.clim_t: torch.Tensor | None = None
        self.s: torch.Tensor | None = None
        self.static_t: torch.Tensor | None = None
        self.ridge: RidgeHead | None = None
        self.net: SpeedLimitNet | None = None
        self.dyn: SpeedLimitNet | None = None  # optional separate network for the shock response
        self.pp = PostProc()
        self.clim_std: np.ndarray | None = None
        self.kit_std: np.ndarray | None = None

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, artifacts_dir: Path | str | None = None, warmup: bool = True, verify: bool = True) -> Engine:
        eng = cls()
        d = Path(artifacts_dir) if artifacts_dir else ARTIFACTS
        try:
            eng._load(d, verify)
            if warmup:
                eng._warmup()
            eng.ready = True
        except Exception as e:  # health must report the failure, not hide it
            log.exception("engine failed to load")
            eng.error = f"{type(e).__name__}: {e}"
        return eng

    def _load(self, d: Path, verify: bool) -> None:
        manifest = {}
        mp = d / "manifest.json"
        if mp.exists():
            manifest = json.loads(mp.read_text())
            self.model_name = manifest.get("model_name", MODEL_NAME)
            if verify:
                for name, meta in manifest.get("files", {}).items():
                    want = meta.get("sha256")
                    if want and _sha256(d / name) != want:
                        raise RuntimeError(f"hash mismatch for {name}")
        self.clim = np.load(d / "climatology.npy").astype(np.float32)
        self.clim_t = torch.from_numpy(self.clim)
        norm = json.loads((d / "norm.json").read_text())
        self.s = torch.tensor(norm["anom_std"], dtype=torch.float32)
        self.static_t = torch.from_numpy(np.load(d / "static.npy").astype(np.float32)).clone()
        self.static_t[1] = self.static_t[1] / 1000.0  # orography in km
        sp = d / "stats.json"
        self.kit_std = np.array(json.loads(sp.read_text())["std"], dtype=np.float32) if sp.exists() else None
        cs = d / "clim_std.npy"
        self.clim_std = np.load(cs).astype(np.float32) if cs.exists() else None
        rp = d / "ridge.pt"
        if rp.exists():
            self.ridge = RidgeHead(torch.load(rp, map_location="cpu", weights_only=True))
        nn_p = d / "nn.pt"
        if nn_p.exists():
            cfg = NetConfig(**json.loads((d / "nn_config.json").read_text()))
            net = SpeedLimitNet(cfg)
            net.load_state_dict(torch.load(nn_p, map_location="cpu", weights_only=True))
            self.net = net.eval()
            for p in self.net.parameters():
                p.requires_grad_(False)
        dyn_p = d / "nn_dyn.pt"
        if dyn_p.exists():
            dcfg = NetConfig(**json.loads((d / "nn_dyn_config.json").read_text()))
            dyn = SpeedLimitNet(dcfg)
            dyn.load_state_dict(torch.load(dyn_p, map_location="cpu", weights_only=True))
            self.dyn = dyn.eval()
            for p in self.dyn.parameters():
                p.requires_grad_(False)
        if self.ridge is None and self.net is None:
            raise RuntimeError("no ridge.pt or nn.pt found in artifacts")
        pp = d / "postproc.json"
        self.pp = PostProc(json.loads(pp.read_text())) if pp.exists() else PostProc()

    def _warmup(self) -> None:
        base = self.clim[100][None].repeat(T_IN, axis=0)
        pert = np.zeros((NC, NLAT, NLON), np.float32)
        pert[0, 10:14, 10:14] = 1.0
        from .climatology import sincos_of_slot

        self.simulate(base, sincos_of_slot(100), 10, pert)

    # ------------------------------------------------------------------ helpers
    def _clean_inputs(self, init_states: np.ndarray, slot0: int) -> np.ndarray:
        x = np.asarray(init_states, dtype=np.float32)
        if x.shape != (T_IN, NC, NLAT, NLON):
            raise ValueError(f"init_states shape {x.shape}")
        bad = ~np.isfinite(x)
        if bad.any():
            fill = self.clim[[(slot0 - 2) % 366, (slot0 - 1) % 366, slot0 % 366]]
            x = np.where(bad, fill, x)
        return x

    @staticmethod
    def _is_null(pert: np.ndarray | None) -> bool:
        return pert is None or not np.any(np.nan_to_num(pert))

    def _slots(self, slot0: int, steps: int) -> np.ndarray:
        return np.array([(slot0 + k) % 366 for k in range(steps + 1)], dtype=np.int64)

    # ------------------------------------------------------------------ core
    @torch.no_grad()
    def simulate_parts(
        self,
        init_states: np.ndarray,
        doy_sincos: Sequence[float],
        steps: int,
        perturbation: np.ndarray | None,
    ) -> dict:
        steps = int(min(max(int(steps), 1), MAX_STEPS))
        slot0 = slot_of_last_day(doy_sincos)
        x = self._clean_inputs(init_states, slot0)
        shocked = not self._is_null(perturbation)
        slots = self._slots(slot0, steps)
        slots_t = torch.from_numpy(slots).unsqueeze(0)
        prev = torch.tensor([(slot0 - 2) % 366, (slot0 - 1) % 366, slot0 % 366])
        clim_in = self.clim_t[prev]  # [3,6,H,W]
        clim_tgt = self.clim_t[slots_t[0, 1:]]  # [K,6,H,W]

        xs = [x]
        if shocked:
            p = np.nan_to_num(np.asarray(perturbation, dtype=np.float32))
            x2 = x.copy()
            x2[-1] = x2[-1] + p  # exactly as given, physical units, nothing else
            xs.append(x2)
        xt = torch.from_numpy(np.stack(xs))  # [B,3,6,H,W]
        z0 = to_z(xt, clim_in.unsqueeze(0), self.s)

        z_ridge = None
        if self.ridge is not None:
            z_ridge = self.ridge.predict(z0[0], slots_t[0, 1:]).numpy()
        z_nn = nn_phys = None
        if self.net is not None:
            zr = rollout(self.net, z0, slots_t.expand(len(xs), -1), self.clim_t, self.s, self.static_t, steps)
            nn_phys = from_z(zr, clim_tgt.unsqueeze(0), self.s).numpy()
            z_nn = zr[0].numpy()
        if z_ridge is None:
            z_ridge = z_nn

        zf = self.pp.damp_z(self.pp.blend(z_nn, z_ridge))
        skill = from_z(torch.from_numpy(zf), clim_tgt, self.s).numpy()
        skill[:, 1] = self.pp.map_rain(skill[:, 1])

        dyn_phys = None
        if shocked and self.dyn is not None:  # dynamics head: a second local network, batch of 2
            zd = rollout(self.dyn, z0, slots_t.expand(len(xs), -1), self.clim_t, self.s, self.static_t, steps)
            dyn_phys = from_z(zd, clim_tgt.unsqueeze(0), self.s).numpy()
        resp = dyn_phys if dyn_phys is not None else nn_phys
        if shocked and resp is not None:
            delta = np.nan_to_num(resp[1] - resp[0]).astype(np.float32)
            if self.kit_std is not None:
                delta = limit_delta(delta, self.kit_std)
        elif shocked:  # ridge-only fallback: response lives inside the shock box only
            z_r2 = self.ridge.predict(z0[1], slots_t[0, 1:]).numpy()
            delta = (
                from_z(torch.from_numpy(z_r2), clim_tgt, self.s) - from_z(torch.from_numpy(z_ridge), clim_tgt, self.s)
            ).numpy()
        else:
            delta = np.zeros_like(skill)
        out = clamp(skill + delta, self.clim[slots[1:]])
        return {
            "skill": skill,
            "nn_base": None if nn_phys is None else nn_phys[0],
            "nn_shocked": None if nn_phys is None or not shocked else nn_phys[1],
            "delta": delta,
            "out": out,
        }

    def simulate(
        self,
        init_states: np.ndarray,
        doy_sincos: Sequence[float],
        steps: int,
        perturbation: np.ndarray | None,
    ) -> np.ndarray:
        """[3,6,32,36] physical -> [steps,6,32,36] physical, clamped. Never raises: falls back to the ridge head."""
        try:
            return self.simulate_parts(init_states, doy_sincos, steps, perturbation)["out"]
        except Exception:
            log.exception("simulate failed; using ridge-only fallback")
            return self._fallback(init_states, doy_sincos, steps, perturbation)

    @torch.no_grad()
    def _fallback(self, init_states, doy_sincos, steps, perturbation) -> np.ndarray:
        steps = int(min(max(int(steps), 1), MAX_STEPS))
        slot0 = slot_of_last_day(doy_sincos)
        slots = self._slots(slot0, steps)[1:]
        x = np.nan_to_num(np.asarray(init_states, dtype=np.float32), nan=0.0)
        if perturbation is not None:
            x = x.copy()
            x[-1] = x[-1] + np.nan_to_num(np.asarray(perturbation, dtype=np.float32))
        clim_tgt = self.clim_t[torch.from_numpy(slots)]
        if self.ridge is not None:
            prev = torch.tensor([(slot0 - 2) % 366, (slot0 - 1) % 366, slot0 % 366])
            z0 = to_z(torch.from_numpy(x), self.clim_t[prev], self.s)
            out = from_z(self.ridge.predict(z0, torch.from_numpy(slots)), clim_tgt, self.s).numpy()
        else:
            out = np.repeat(x[-1][None], steps, axis=0)
        return clamp(out, self.clim[slots])

    def nn_rollout_torch(self, init_states_t: torch.Tensor, doy_sincos: Sequence[float], steps: int) -> torch.Tensor:
        """Differentiable network rollout, physical in and out. init_states_t [B,3,6,H,W] -> [B,steps,6,H,W]."""
        assert self.net is not None
        slot0 = slot_of_last_day(doy_sincos)
        slots = torch.from_numpy(self._slots(slot0, steps)).unsqueeze(0).expand(init_states_t.shape[0], -1)
        prev = torch.tensor([(slot0 - 2) % 366, (slot0 - 1) % 366, slot0 % 366])
        z0 = to_z(init_states_t, self.clim_t[prev].unsqueeze(0), self.s)
        z = rollout(self.net, z0, slots, self.clim_t, self.s, self.static_t, steps)
        return from_z(z, self.clim_t[slots[0, 1:]].unsqueeze(0), self.s)
