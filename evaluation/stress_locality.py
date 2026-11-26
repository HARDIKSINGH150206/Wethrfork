"""Brutal locality test through the FULL served formula (skill + dynamics + limiter + clamp), not just the network.

Random single-cell and small-patch shocks on every channel, including corners and edges. Outside the architectural reach
(Chebyshev 8 per day, plus a small allowance for float noise between batch sizes) the served output must not change.
Also: determinism across fresh processes, continuity for tiny shocks, and edge wrap-around."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

import numpy as np

from training.data import ROOT, load_archive, load_config
from wethrfork.climatology import sincos_of_slot
from wethrfork.engine import Engine

STD = np.array(json.loads((ROOT / "artifacts" / "stats.json").read_text())["std"], dtype=np.float32)


def leak(eng, init, doy, steps, i0, j0, ch, amp, half=0):
    pert = np.zeros((6, 32, 36), np.float32)
    pert[ch, max(i0 - half, 0) : i0 + half + 1, max(j0 - half, 0) : j0 + half + 1] = amp * STD[ch]
    base = eng.simulate(init, doy, steps, None)
    out = eng.simulate(init, doy, steps, pert)
    z = np.abs(out - base) / STD[None, :, None, None]
    ii, jj = np.indices((32, 36))
    ci0, ci1, cj0, cj1 = max(i0 - half, 0), i0 + half, max(j0 - half, 0), j0 + half
    cheb = np.maximum(np.maximum(ci0 - ii, ii - ci1), np.maximum(cj0 - jj, jj - cj1)).clip(
        min=0
    )  # distance to the patch
    worst = 0.0
    reach = np.zeros(steps, int)
    for d in range(steps):
        zd = z[d].max(axis=0)
        outside = cheb > 8 * (d + 1)
        if outside.any():
            worst = max(worst, float(zd[outside].max()))
        inside = zd > 1e-4
        reach[d] = int(cheb[inside].max()) if inside.any() else 0
    return worst, reach


def child() -> None:
    arc = load_archive(load_config(ROOT / "configs" / "data.yaml"))
    eng = Engine.load()
    t = 3000
    out = eng.simulate(arc.data[t - 2 : t + 1], sincos_of_slot(int(arc.slots()[t])), 10, None)
    print(float(out.astype(np.float64).sum()), float(out[3, 1].sum()), float(out[9, 4, 7, 7]))


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child()
        return 0
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    a = ap.parse_args()
    arc = load_archive(load_config(ROOT / "configs" / "data.yaml"))
    eng = Engine.load()
    rng = np.random.default_rng(11)
    slots = arc.slots()
    worst_all, max_reach = 0.0, np.zeros(10, int)
    corners = [(0, 0), (0, 35), (31, 0), (31, 35), (0, 18), (31, 18), (16, 0), (16, 35)]
    cases = []
    for k in range(a.n):
        t = int(rng.integers(3, len(arc.dates) - 12))
        ch = int(rng.integers(0, 6))
        amp = float(rng.choice([0.5, 1, 2, 4, 8])) * float(rng.choice([-1, 1]))
        half = int(rng.choice([0, 0, 1, 3]))
        i0, j0 = corners[k % len(corners)] if k % 3 == 0 else (int(rng.integers(0, 32)), int(rng.integers(0, 36)))
        cases.append((t, ch, amp, half, i0, j0))
    for t, ch, amp, half, i0, j0 in cases:
        w, reach = leak(eng, arc.data[t - 2 : t + 1], sincos_of_slot(int(slots[t])), 10, i0, j0, ch, amp, half)
        worst_all = max(worst_all, w)
        max_reach = np.maximum(max_reach, reach)
    print(f"locality: {len(cases)} random shocks (channels, signs, 0.5 to 8 std, corners and edges included)")
    print(
        f"  largest change outside the reach 8 cells x days (in std units): {worst_all:.2e}   (must be ~0; float noise bound 1e-3)"
    )
    print(
        f"  farthest cell changed per day (max-axis, over all cases): {max_reach.tolist()}   limit: {[8 * (d + 1) for d in range(10)]}"
    )
    ok1 = worst_all < 1e-3 and bool((max_reach <= np.array([8 * (d + 1) for d in range(10)])).all())
    # continuity: shocks of shrinking size give shrinking changes (no cliff between zero and non-zero)
    t = 2500
    init, doy = arc.data[t - 2 : t + 1], sincos_of_slot(int(slots[t]))
    base = eng.simulate(init, doy, 10, None)
    cont = []
    for eps in (1e-1, 1e-3, 1e-6, 1e-9, 1e-30):
        p = np.zeros((6, 32, 36), np.float32)
        p[0, 10:14, 10:14] = eps
        cont.append((eps, float((np.abs(eng.simulate(init, doy, 10, p) - base) / STD[None, :, None, None]).max())))
    print("  continuity (t2m patch of size eps K -> max change in std):", ", ".join(f"{e:g}:{v:.1e}" for e, v in cont))
    ok2 = cont[-1][1] < 1e-3 and cont[2][1] < 1e-2
    # determinism across fresh processes
    sig = [
        subprocess.run(
            [sys.executable, "-m", "evaluation.stress_locality", "--child"], capture_output=True, text=True, cwd=ROOT
        ).stdout.strip()
        for _ in range(3)
    ]
    ok3 = len(set(sig)) == 1 and sig[0] != ""
    print(f"  determinism across 3 fresh processes (bitwise-equal checksums): {ok3}  {sig[0] if sig else ''}")
    print("RESULT:", "PASS" if ok1 and ok2 and ok3 else "FAIL")
    return 0 if ok1 and ok2 and ok3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
