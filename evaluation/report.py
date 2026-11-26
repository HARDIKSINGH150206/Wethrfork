"""Brief figures (matplotlib allowed here, never in the serve graph)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "brief" / "figures"


def fig_leads() -> None:
    sg = json.loads((ROOT / "runs" / "selfgrade" / "latest.json").read_text())["systematic"]
    leads = sorted(int(k) for k in sg["ss_by_lead_channel"])
    ss = np.array([sg["ss_by_lead_channel"][str(k)] for k in leads])
    names = ["t2m", "tp", "u10", "v10", "msl", "tcwv"]
    fig, ax = plt.subplots(1, 2, figsize=(8, 3))
    for c, n in enumerate(names):
        ax[0].plot(leads, ss[:, c], marker="o", label=n)
    ax[0].axhline(0, color="k", lw=0.6)
    ax[0].set_xlabel("lead day")
    ax[0].set_ylabel("RMSE skill vs best reference")
    ax[0].legend(fontsize=6)
    ax[1].bar(names, sg["var_ratio_day8_mean"])
    ax[1].axhline(0.4, color="r", ls="--", lw=0.8)
    ax[1].set_ylabel("day-8 variance ratio")
    fig.tight_layout()
    fig.savefig(OUT / "leads.png", dpi=200)


def fig_fuzz() -> None:
    fz = json.loads((ROOT / "runs" / "fuzz" / "summary.json").read_text())
    chans = list(fz["by_channel"])
    amps = sorted(fz["by_amp"])
    grid = np.full((len(chans), len(amps)), np.nan)
    for ci, ch in enumerate(chans):
        for ai, am in enumerate(amps):
            v = [c["pass"] for c in fz["cases"] if c["channel"] == ch and c["amp"] == am]
            if v:
                grid[ci, ai] = np.mean(v)
    fig, ax = plt.subplots(figsize=(5, 3))
    im = ax.imshow(grid, vmin=0, vmax=1, cmap="RdYlGn")
    ax.set_xticks(range(len(amps)), amps, fontsize=6, rotation=30)
    ax.set_yticks(range(len(chans)), chans, fontsize=7)
    fig.colorbar(im, ax=ax, label="causality pass rate")
    fig.tight_layout()
    fig.savefig(OUT / "fuzz.png", dpi=200)


def fig_natural() -> None:
    ne = json.loads((ROOT / "runs" / "natural" / "summary.json").read_text())
    k = ne["lead"] - 1
    fig, ax = plt.subplots(2, 2, figsize=(7, 5))
    for r, (key, name) in enumerate((("d_tp", "rain"), ("d_msl", "pressure"))):
        obs = np.array(ne["observed_composite"][key])[k]
        mod = np.array(ne["model_response"][key])[k]
        ax[r, 0].imshow(obs, origin="lower", cmap="RdBu_r")
        ax[r, 0].set_title(f"observed {name} anomaly", fontsize=8)
        ax[r, 1].imshow(mod, origin="lower", cmap="RdBu_r")
        ax[r, 1].set_title(f"model response (r={ne['pattern_corr']['tp' if r == 0 else 'msl']:.2f})", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "natural.png", dpi=200)


def fig_lightcone() -> None:
    import torch

    from wethrfork.model import NetConfig, SpeedLimitNet, rollout

    torch.manual_seed(3)
    net = SpeedLimitNet(NetConfig(hidden=16)).eval()
    with torch.no_grad():
        for m in (net.head, net.disp_corr):
            torch.nn.init.normal_(m.weight, std=0.3)
    clim = torch.zeros(366, 6, 32, 36)
    s = torch.ones(6)
    static = torch.zeros(2, 32, 36)
    ks = (1, 2, 3, 4)
    reach = []
    for k in ks:
        z = 0.2 * torch.randn(1, 3, 6, 32, 36)
        z[:, :, 2] += 12.0
        z2 = z.clone()
        z2[0, -1, 0, 16, 18] += 3.0
        sl = torch.arange(k + 1).unsqueeze(0) + 100
        with torch.no_grad():
            d = (rollout(net, z2, sl, clim, s, static, k) - rollout(net, z, sl, clim, s, static, k)).abs().amax(
                dim=(0, 1, 2)
            ) > 1e-6
        ii, jj = np.indices((32, 36))
        reach.append(float(np.maximum(abs(ii - 16), abs(jj - 18))[d.numpy()].max()))
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot(ks, reach, "o-", label="measured reach")
    ax.plot(ks, [8 * k for k in ks], "r--", label="speed limit 8 cells/day")
    ax.set_xlabel("step")
    ax.set_ylabel("cells (Chebyshev)")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "lightcone.png", dpi=200)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fig", default=None, choices=["leads", "fuzz", "natural", "lightcone"])
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    todo = {"leads": fig_leads, "fuzz": fig_fuzz, "natural": fig_natural, "lightcone": fig_lightcone}
    for name, fn in todo.items():
        if a.all or a.fig == name:
            try:
                fn()
                print("wrote", name)
            except FileNotFoundError as e:
                print("skipped", name, "missing", e.filename)


if __name__ == "__main__":
    main()
