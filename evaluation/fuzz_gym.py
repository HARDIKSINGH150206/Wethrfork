"""Fuzz test: random shocks through the served formula; validity and causality pass rates by channel, amplitude, season."""

from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path

import numpy as np

from evaluation import windows as W
from training.data import ROOT, load_archive, load_config
from wethrfork.engine import Engine
from wethrfork.physics import CHANNELS

log = logging.getLogger(__name__)


def make_case(rng: np.random.Generator, cfg: dict, std: np.ndarray, last: np.ndarray) -> tuple[np.ndarray, tuple, dict]:
    ch = int(rng.integers(0, 6))
    shape = str(rng.choice(cfg["shapes"]))
    size_lo, size_hi = cfg["box_size_cells"]
    h, w = int(rng.integers(size_lo, size_hi + 1)), int(rng.integers(size_lo, size_hi + 1))
    if cfg.get("include_edge_boxes", True) and rng.random() < 0.25:
        i0 = int(rng.choice([0, 32 - h]))
        j0 = int(rng.choice([0, 36 - w]))
    else:
        i0, j0 = int(rng.integers(0, 32 - h + 1)), int(rng.integers(0, 36 - w + 1))
    relative = ch in (1, 2, 3, 5) and rng.random() < 0.5
    if relative:
        frac = float(rng.choice(cfg["relative_options"])) * float(rng.choice([-1, 1]))
        amp_label = f"rel{abs(frac)}"
    else:
        k = float(rng.choice(cfg["amplitude_std"]))
        frac = k * float(rng.choice([-1, 1])) * std[ch]
        amp_label = f"{k}std"
    mask = np.zeros((32, 36), dtype=np.float32)
    if shape == "box":
        mask[i0 : i0 + h, j0 : j0 + w] = 1.0
    else:
        ii, jj = np.indices((32, 36))
        ci, cj = i0 + h / 2, j0 + w / 2
        mask = np.exp(-(((ii - ci) / (h / 2 + 0.5)) ** 2 + ((jj - cj) / (w / 2 + 0.5)) ** 2)).astype(np.float32)
    pert = np.zeros((6, 32, 36), dtype=np.float32)
    pert[ch] = mask * (frac * last[ch] if relative else frac)
    box = (6.5 + i0, 6.5 + i0 + h - 1, 65.5 + j0, 65.5 + j0 + w - 1)
    return pert, box, {"channel": CHANNELS[ch], "shape": shape, "amp": amp_label, "size": f"{h}x{w}"}


def run(engine: Engine, arc, cfg: dict, ecfg: dict, std: np.ndarray, n: int | None = None) -> dict:
    from monsoon_r1 import scoring as S

    rng = np.random.default_rng(int(cfg["seed"]))
    wins = W.shock_windows(arc, ecfg)
    seasons = list(wins)
    cases = []
    for k in range(n or int(cfg["n_shocks"])):
        season = seasons[k % len(seasons)]
        w = wins[season]
        pert, box, meta = make_case(rng, cfg, std, w["init"][-1])
        base = engine.simulate(w["init"], w["doy_sincos"], 10, None)
        shock = engine.simulate(w["init"], w["doy_sincos"], 10, pert)
        valid = not S.validity(shock, 10)
        r = S.causality_checks(base, shock, box, std)
        cases.append(
            {
                **meta,
                "season": season,
                "valid": bool(valid),
                "nonzero": bool(r["nonzero"]),
                "localized": bool(r["localized"]),
                "propagates": bool(r["propagates"]),
                "stable": bool(r["stable"]),
                "pass": bool(valid and r["nonzero"] and r["localized"] and r["propagates"] and r["stable"]),
                "near1": float(r.get("near_frac_day1", 0.0)),
            }
        )
    out = {
        "n": len(cases),
        "validity": float(np.mean([c["valid"] for c in cases])),
        "pass_rate": float(np.mean([c["pass"] for c in cases])),
    }
    for key in ("channel", "amp", "season", "shape"):
        g = defaultdict(list)
        for c in cases:
            g[c[key]].append(c["pass"])
        out["by_" + key] = {k: {"n": len(v), "pass_rate": float(np.mean(v))} for k, v in g.items()}
    out["cases"] = cases
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/fuzz.yaml")
    ap.add_argument("--eval-config", default="configs/eval.yaml")
    ap.add_argument("--data-config", default="configs/data.yaml")
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--artifacts", default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    cfg = load_config(ROOT / args.config)
    ecfg = load_config(ROOT / args.eval_config)
    arc = load_archive(load_config(ROOT / args.data_config))
    eng = Engine.load(Path(args.artifacts) if args.artifacts else None)
    assert eng.ready, eng.error
    std = np.array(json.loads((ROOT / "artifacts" / "stats.json").read_text())["std"], dtype=np.float32)
    res = run(eng, arc, cfg, ecfg, std, args.n)
    out = ROOT / cfg["out_dir"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(res, indent=1))
    print(f"fuzz n={res['n']} validity={res['validity']:.3f} pass_rate={res['pass_rate']:.3f}")
    for key in ("by_channel", "by_amp", "by_season"):
        print(key, {k: round(v["pass_rate"], 2) for k, v in res[key].items()})


if __name__ == "__main__":
    main()
