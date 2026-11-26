from __future__ import annotations

from wethrfork.climatology import doy_from_sincos, sincos_of_slot, slot_of_doy, slots_for_steps


def test_roundtrip_all_slots():
    for slot in range(365):
        assert doy_from_sincos(sincos_of_slot(slot)) == slot


def test_dec31_wraps_into_january():
    # last input day at slot 364 (Dec 31 in non-leap indexing): next target is slot 365 then wraps to 0
    slots = slots_for_steps(sincos_of_slot(364), 3)
    assert slots.tolist() == [365, 0, 1]


def test_jan1_and_feb29():
    assert slots_for_steps(sincos_of_slot(0), 1).tolist() == [1]
    assert slots_for_steps(sincos_of_slot(58), 2).tolist() == [59, 60]  # Feb 28 -> Feb 29 slot -> Mar 1


def test_non_finite_is_safe():
    assert doy_from_sincos([float("nan"), 0.0]) == 0
    assert slot_of_doy(999) == 365 and slot_of_doy(-3) == 0
