"""Is "apply the perturbation through the API" the same as "add it to the last input day and forecast normally"?

By design it is NOT: the served formula is  clamp(PP(Blend(skill(base))) + limiter[D(shocked) - D(base)]),  so the forecast of the
unshocked state is kept and only the dynamics network's response is added. This script measures the gap on every systematic
window for both official shocks, so the claim in the brief and the Q&A is a number, not an adjective."""

from __future__ import annotations

import argparse
import json

import numpy as np

from evaluation import windows as W
from training.data import ROOT, load_archive, load_config
from wethrfork.engine import Engine
from wethrfork.physics import CHANNELS


def main() -> int:
    from monsoon_r1 import scoring as S

    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/eval.yaml")
    ap.add_argument("--data-config", default="configs/data.yaml")
    args = ap.parse_args()
    cfg = load_config(ROOT / args.config)
    arc = load_archive(load_config(ROOT / args.data_config))
    eng = Engine.load()
    assert eng.ready, eng.error
    std = np.array(json.loads((ROOT / "artifacts" / "stats.json").read_text())["std"], dtype=np.float32)
    rows = {name: [] for name in ("warm_ocean", "monsoon_stall")}
    worst = (0.0, "", None)
    for w in W.systematic(arc, cfg):
        for name in rows:
            pert = S.make_shock(name, w["init"][-1], std)
            api = eng.simulate(w["init"], w["doy_sincos"], 10, pert)
            direct_init = w["init"].copy()
            direct_init[-1] = direct_init[-1] + pert
            direct = eng.simulate(direct_init, w["doy_sincos"], 10, None)
            d = np.abs(api - direct)
            z = (d / std[None, :, None, None]).max(axis=(0, 2, 3))  # per channel, in std units
            rows[name].append({"max_abs": d.max(axis=(0, 2, 3)), "z": z})
            if d[:, 1].max() > worst[0]:
                worst = (float(d[:, 1].max()), name, w["id"])
    print("API perturbation  vs  same perturbation added to the last input day (forecast normally)")
    print(f"windows: {len(rows['warm_ocean'])}; difference in physical units, max over days and cells")
    for name, r in rows.items():
        m = np.array([x["max_abs"] for x in r])
        zz = np.array([x["z"] for x in r])
        print(f"  {name}:")
        for c, ch in enumerate(CHANNELS):
            print(
                f"    {ch:5s} median {np.median(m[:, c]):9.3f}   p95 {np.percentile(m[:, c], 95):9.3f}   max {m[:, c].max():9.3f}   (max {zz[:, c].max():.2f} std)"
            )
    print(f"largest rainfall difference anywhere: {worst[0]:.1f} mm/day ({worst[1]}, window {worst[2]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
