"""The internal causality gate must require the judge's own flags, not only our stricter numeric thresholds."""

from __future__ import annotations

from evaluation.causality_gate import passes

GATE = {"near_frac_min": 0.75, "growth_min": 3.0, "far_frac_max": 0.01, "max_z": 4.0}


def _ok():
    return {
        "finite": True,
        "nonzero": True,
        "localized": True,
        "propagates": True,
        "stable": True,
        "near_frac_day1": 0.9,
        "growth_ratio": 10.0,
        "far_frac_max": 0.0,
        "max_z": 2.0,
    }


def _res(**over):
    a, b = _ok(), _ok()
    a.update(over)
    return {"warm_ocean": a, "monsoon_stall": b, "null_max_diff": 0.0}


def test_all_good_passes():
    assert all(passes(_res(), GATE).values())


def test_official_propagates_false_fails_even_when_numbers_pass():
    r = passes(_res(propagates=False), GATE)  # growth 10x, far 0.0: the numeric rule alone would have passed
    assert r["warm_ocean"] is False and r["monsoon_stall"] is True


def test_official_localized_and_stable_flags_are_required():
    assert passes(_res(localized=False), GATE)["warm_ocean"] is False
    assert passes(_res(stable=False), GATE)["warm_ocean"] is False


def test_null_must_be_exactly_zero():
    r = _res()
    r["null_max_diff"] = 1e-9
    assert passes(r, GATE)["null"] is False
