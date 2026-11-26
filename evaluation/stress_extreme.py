"""Randomised extreme-input fuzz for Engine.simulate: hostile states, NaN/Inf sprinkles, absurd shocks, odd dates and steps.
Every output must be finite, within the judge's validity limits, deterministic, and a zero shock must equal no shock."""

from __future__ import annotations

import argparse

import numpy as np

from wethrfork.engine import Engine

LO = np.array([200.0, 0.0, -80.0, -80.0, 80000.0, 0.0], np.float32)
HI = np.array([350.0, 800.0, 80.0, 80.0, 115000.0, 120.0], np.float32)
NORMAL = np.array([295.0, 4.0, 2.0, 1.0, 100500.0, 35.0], np.float32)


def hostile_state(rng) -> np.ndarray:
    x = np.empty((3, 6, 32, 36), np.float32)
    for c in range(6):
        mode = rng.choice(["lo", "hi", "zero", "normal", "wide", "checker", "spike", "huge", "neg"])
        if mode == "lo":
            x[:, c] = LO[c]
        elif mode == "hi":
            x[:, c] = HI[c]
        elif mode == "zero":
            x[:, c] = 0.0
        elif mode == "normal":
            x[:, c] = NORMAL[c] + rng.standard_normal((3, 32, 36)) * (HI[c] - LO[c]) * 0.02
        elif mode == "wide":
            x[:, c] = rng.uniform(LO[c], HI[c], (3, 32, 36))
        elif mode == "checker":
            ii, jj = np.indices((32, 36))
            x[:, c] = np.where((ii + jj) % 2 == 0, LO[c], HI[c])
        elif mode == "spike":
            x[:, c] = NORMAL[c]
            x[:, c, rng.integers(0, 32), rng.integers(0, 36)] = HI[c] * 100
        elif mode == "huge":
            x[:, c] = rng.choice([1e20, -1e20, 3e38])
        else:
            x[:, c] = -abs(NORMAL[c]) * 50
    if rng.random() < 0.3:
        for _ in range(int(rng.integers(1, 40))):
            x[rng.integers(0, 3), rng.integers(0, 6), rng.integers(0, 32), rng.integers(0, 36)] = rng.choice(
                [np.nan, np.inf, -np.inf]
            )
    return x


def hostile_shock(rng) -> np.ndarray | None:
    r = rng.random()
    if r < 0.15:
        return None
    if r < 0.25:
        return np.zeros((6, 32, 36), np.float32)
    p = np.zeros((6, 32, 36), np.float32)
    for c in rng.choice(6, size=int(rng.integers(1, 7)), replace=False):
        scale = float(rng.choice([1e-3, 1, 50, 1e3, 1e6, 1e20]))
        i0, j0 = int(rng.integers(0, 32)), int(rng.integers(0, 36))
        h, w = int(rng.integers(1, 33)), int(rng.integers(1, 37))
        p[c, i0 : i0 + h, j0 : j0 + w] = rng.choice([-1, 1]) * scale * rng.random()
    if rng.random() < 0.1:
        p[rng.integers(0, 6), rng.integers(0, 32), rng.integers(0, 36)] = rng.choice([np.nan, np.inf, -np.inf])
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=2)
    a = ap.parse_args()
    eng = Engine.load()
    assert eng.ready, eng.error
    rng = np.random.default_rng(a.seed)
    fails = []
    for k in range(a.n):
        x = hostile_state(rng)
        p = hostile_shock(rng)
        steps = int(rng.choice([1, 2, 5, 10, 14, 20, 0, -2]))
        doy = (
            [float(rng.uniform(-3, 3)), float(rng.uniform(-3, 3))]
            if rng.random() < 0.3
            else [float(np.sin(rng.uniform(0, 6.28))), float(np.cos(rng.uniform(0, 6.28)))]
        )
        want = min(max(steps, 1), 14)
        try:
            out = eng.simulate(x, doy, steps, p)
            again = eng.simulate(x, doy, steps, p)
            why = []
            if out.shape != (want, 6, 32, 36):
                why.append(f"shape {out.shape}")
            if not np.isfinite(out).all():
                why.append("non-finite")
            else:
                if out[:, 1].min() < 0:
                    why.append("negative rain")
                if out[:, 5].min() < 0:
                    why.append("negative tcwv")
                if out[:, 0].min() < 233.15 or out[:, 0].max() > 333.15:
                    why.append("t2m outside judge range")
            if not np.array_equal(out, again):
                why.append("non-deterministic")
            if p is not None and not np.any(np.nan_to_num(p)):
                if np.abs(out - eng.simulate(x, doy, steps, None)).max() != 0.0:
                    why.append("zero shock != no shock")
        except Exception as e:  # any exception is a failure: simulate must not raise for well-shaped input
            why = [f"EXCEPTION {type(e).__name__}: {e}"]
        if why:
            fails.append((k, why))
    print(f"extreme-input fuzz: {a.n} cases, {len(fails)} failures")
    for k, why in fails[:10]:
        print("  case", k, why)
    print("RESULT:", "PASS" if not fails else "FAIL")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
