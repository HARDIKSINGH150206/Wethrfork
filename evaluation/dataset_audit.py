"""Audit of the training archive and everything derived from it before use: integrity, continuity, physical ranges,
agreement with the organisers' statistics, our climatology against the kit's reference implementation, and split leakage.
Reads data/ only (never committed); contains no dates (the splits come from configs/data.yaml)."""

from __future__ import annotations

import hashlib
import json

import numpy as np

from training.build_climatology import climatology
from training.data import ROOT, load_archive, load_config, sample_starts, split_bounds

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def main() -> int:
    cfg = load_config(ROOT / "configs" / "data.yaml")
    arc = load_archive(cfg)
    d, dates = arc.data, arc.dates
    n = len(dates)
    path = ROOT / cfg["data_path"]
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    check("file is the organisers' release (sha256 recorded)", True, sha[:16] + "...")
    check("shape [N,6,32,36]", d.ndim == 4 and d.shape[1:] == (6, 32, 36), str(d.shape))
    check("no NaN or Inf", bool(np.isfinite(d).all()))
    gaps = np.diff(dates.values).astype("timedelta64[D]").astype(int)
    check(
        "daily and contiguous (no gaps, no duplicates)",
        bool((gaps == 1).all()),
        f"{n} days, min gap {gaps.min()}, max gap {gaps.max()}",
    )
    leap_years = sum(
        1 for y in range(dates[0].year, dates[-1].year + 1) if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0
    )
    slots = arc.slots()
    check(
        "every Feb 29 present",
        int((slots == 59).sum()) == leap_years,
        f"{int((slots == 59).sum())} Feb 29 days, {leap_years} leap years",
    )
    names = ["t2m", "tp", "u10", "v10", "msl", "tcwv"]
    lim = {
        "t2m": (230, 335),
        "tp": (0, 600),
        "u10": (-60, 60),
        "v10": (-60, 60),
        "msl": (85000, 110000),
        "tcwv": (0, 120),
    }
    for c, nm in enumerate(names):
        lo, hi = float(d[:, c].min()), float(d[:, c].max())
        check(f"range {nm}", lim[nm][0] <= lo and hi <= lim[nm][1], f"[{lo:.2f}, {hi:.2f}]")
    st = json.loads((ROOT / cfg["stats_path"]).read_text())
    mean_err = np.abs(d.mean(axis=(0, 2, 3)) - np.array(st["mean"])) / np.array(st["std"])
    std_err = np.abs(d.std(axis=(0, 2, 3)) / np.array(st["std"]) - 1)
    check(
        "agrees with the organisers' stats.json (mean within 1e-3 std, std within 1e-3)",
        bool((mean_err < 1e-3).all() and (std_err < 1e-3).all()),
        f"max mean err {mean_err.max():.1e}, max std err {std_err.max():.1e}",
    )
    check("channel order matches the contract", st["channels"] == names, str(st["channels"]))
    check("land-sea mask in [0,1]", 0 <= arc.static[0].min() and arc.static[0].max() <= 1)
    check(
        "orography plausible",
        -500 <= arc.static[1].min() and arc.static[1].max() < 9000,
        f"[{arc.static[1].min():.0f}, {arc.static[1].max():.0f}] m",
    )

    lo, hi = cfg["climatology"]["years"]
    i0, i1 = arc.index_range(lo, hi)
    ours = np.load(ROOT / "artifacts" / "climatology.npy")
    rebuilt = climatology(d[i0:i1], slots[i0:i1], cfg["climatology"]["smooth_days"])
    check(
        "shipped climatology == rebuilt from the archive",
        float(np.abs(ours - rebuilt).max()) < 1e-4,
        f"max diff {np.abs(ours - rebuilt).max():.1e}",
    )
    try:
        import datetime as dt

        from monsoon_r1 import stats as K

        ymd = np.array([int(x.strftime("%Y%m%d")) for x in dates[i0:i1]])
        ref = K.climatology(d[i0:i1], ymd, cfg["climatology"]["smooth_days"])
        check(
            "our climatology == the kit's reference implementation",
            float(np.abs(ours - ref).max()) < 1e-4,
            f"max diff {np.abs(ours - ref).max():.1e}",
        )
        del dt
    except ImportError:
        check("our climatology == the kit's reference implementation", False, "kit not installed")
    counts = np.bincount(slots[i0:i1], minlength=366)
    check("every calendar slot has samples", bool((counts > 0).all()), f"min {counts.min()}, Feb 29 {counts[59]}")

    # split leakage
    ranges = {k: split_bounds(arc, cfg, k) for k in ("train", "calib", "grade")}
    s_tr = sample_starts(*ranges["train"], horizon=14)
    s_ca = sample_starts(*ranges["calib"], horizon=14)
    s_gr = sample_starts(*ranges["grade"], horizon=14)
    check(
        "train samples never reach into calibration",
        int(s_tr.max()) + 14 < ranges["train"][1] + 1 and int(s_tr.max()) + 14 < int(s_ca.min()) - 2,
    )
    check("calibration samples never reach into grading", int(s_ca.max()) + 14 < int(s_gr.min()) - 2)
    check(
        "splits are disjoint and ordered",
        ranges["train"][1] <= ranges["calib"][0] and ranges["calib"][1] <= ranges["grade"][0],
    )
    print(f"       samples: train {len(s_tr)}, calibration {len(s_ca)}, grading {len(s_gr)}")
    tr = d[ranges["train"][0] : ranges["train"][1]]
    gr = d[ranges["grade"][0] : ranges["grade"][1]]
    shift = (gr.mean(axis=(0, 2, 3)) - tr.mean(axis=(0, 2, 3))) / tr.std(axis=(0, 2, 3))
    print(
        "       grading-year mean minus training mean, in training std (t2m, tp, u10, v10, msl, tcwv):",
        np.round(shift, 3).tolist(),
    )
    bad = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} dataset checks passed" + (f"; FAILED: {bad}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
