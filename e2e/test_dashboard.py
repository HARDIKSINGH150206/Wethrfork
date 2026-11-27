"""The dashboard, driven like a judge would on demo day (see e2e/conftest.py for the set-up).

Each test starts from a fresh page with the control run loaded; the `app` fixture then checks that the page logged no
error and sent nothing to any host but our own local servers.
"""

from __future__ import annotations

import pytest

MAPS = ["Precipitation", "Wind", "Temperature", "Moisture", "Pressure"]


def fork_preset(page, name: str = "Warm Bay") -> None:
    page.click(".maps .item:has-text('Fork a universe')")
    page.click(f".presets button:has-text('{name}')")
    page.wait_for_function(
        "document.querySelectorAll('.models button').length === 2 && !document.querySelector('.models .spin')",
        timeout=30000,
    )


def canvas_variance(page) -> float:
    """Spread of pixel values on the map canvas: 0 for a blank or single-colour map."""
    return page.evaluate(
        """() => {
        const c = document.querySelector('.stage canvas'); const g = c.getContext('2d');
        const d = g.getImageData(0, 0, c.width, c.height).data; let s = 0, s2 = 0, n = 0;
        for (let i = 0; i < d.length; i += 4 * 97) { const v = d[i] + d[i + 1] + d[i + 2]; s += v; s2 += v * v; n++ }
        return s2 / n - (s / n) ** 2 }"""
    )


# ------------------------------------------------------------------------------------------------ the map
def test_map_loads_with_every_control_offline(app):
    """Logo, map menu, right rail, timeline, legend, coordinates, scale and the control run; a non-blank map."""
    for sel in (".logo", ".maps", ".rail.top", ".rail.bottom", ".tline", ".legend", ".coords", ".scale", ".attrib"):
        assert app.locator(sel).is_visible(), sel
    assert [t.strip() for t in app.locator(".maps .item").all_inner_texts()][:5] == MAPS
    assert app.locator(".models button.on").inner_text().startswith("Control")
    assert app.locator(".tline .now em").inner_text() == "Day +1"
    assert canvas_variance(app) > 50, "the map canvas looks blank"


def test_every_map_layer_switches_and_relabels_the_legend(app):
    units = set()
    for name in MAPS:
        app.click(f".maps .item:has-text('{name}')")
        assert "on" in app.locator(f".maps .item:has-text('{name}')").get_attribute("class")
        units.add(app.locator(".legend .u").inner_text())
        assert canvas_variance(app) > 50, f"{name}: blank map"
    assert len(units) == 5, f"each layer needs its own unit, got {units}"


def test_timeline_seek_play_and_reset(app):
    box = app.locator(".tline .ticks").bounding_box()
    app.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + 6)
    assert app.locator(".tline .now em").inner_text() == "Day +5.5"
    app.click(".tline .play")
    app.wait_for_timeout(1500)
    assert app.locator(".tline .now em").inner_text() != "Day +5.5", "playback did not advance"
    app.click(".tline .play")
    app.click(".tline .skip")
    assert app.locator(".tline .now em").inner_text() == "Day +1"


def test_menu_collapses_to_the_active_map(app):
    app.click(".maps .head")
    assert app.locator(".maps .item").count() == 1
    app.click(".maps .head")
    assert app.locator(".maps .item").count() >= 7


# ------------------------------------------------------------------------------------------------ forks
def test_preset_fork_runs_live_with_the_official_verdict(app, stack):
    fork_preset(app)
    pill = app.locator(".models button.on").inner_text()
    assert "Warm Bay" in pill and "ms" in pill
    app.click(".drawer .ptabs button:has-text('Audit')")
    app.wait_for_selector(".checks li", timeout=30000)
    checks = {
        li.inner_text().split()[1]: "ok" in (li.get_attribute("class") or "") for li in app.locator(".checks li").all()
    }
    assert set(checks) == {"non-zero", "localized", "propagates", "stable"}, checks
    assert checks["non-zero"] and checks["localized"] and checks["stable"], checks
    if not stack["stub"]:  # outward growth needs real weather; the gate and the rehearsal check it on every window
        assert checks["propagates"], checks
    assert app.locator(".impact.expo tbody tr").count() >= 5, "rainfall exposure table is empty"


def test_difference_swipe_and_speed_limit_rings(app):
    fork_preset(app)
    app.click(".drawer .ptabs .x")
    app.click(".maps .sub:has-text('Difference')")
    assert app.locator(".legend .u").inner_text().startswith("Δ")
    app.click(".maps .sub:has-text('Swipe compare')")
    handle = app.locator(".divider i")
    assert handle.is_visible()
    x0 = app.locator(".divider").bounding_box()["x"]
    hb = handle.bounding_box()
    app.mouse.move(hb["x"] + hb["width"] / 2, hb["y"] + hb["height"] / 2)
    app.mouse.down()
    app.mouse.move(hb["x"] + 200, hb["y"] + hb["height"] / 2, steps=6)
    app.mouse.up()
    assert app.locator(".divider").bounding_box()["x"] > x0 + 100, "the swipe divider did not move"
    rings = app.locator(".rail [aria-label='Speed-limit rings']")
    before = rings.get_attribute("aria-pressed")
    rings.click()
    assert rings.get_attribute("aria-pressed") != before


def test_draw_a_box_and_fork_a_custom_shock(app):
    app.click(".rail [aria-label='Draw a shock']")
    app.mouse.move(900, 420)
    app.mouse.down()
    app.mouse.move(1060, 560, steps=8)
    app.mouse.up()
    assert "cells" in app.locator(".boxinfo").inner_text()
    app.fill(".form input[type=number]", "4")
    app.click(".panel .primary")
    app.wait_for_function(
        "document.querySelectorAll('.models button').length === 2 && !document.querySelector('.models .spin')",
        timeout=30000,
    )
    assert "t2m +4" in app.locator(".models button.on").inner_text()


def test_shock_form_refuses_bad_input_with_a_reason(app):
    app.click(".maps .item:has-text('Fork a universe')")
    assert "Draw a box" in app.locator(".panel .hint").first.inner_text()
    assert app.locator(".panel .primary").is_disabled()


# ------------------------------------------------------------------------------------------------ panels and pages
def test_point_readout_and_ten_day_forecast(app):
    app.mouse.click(860, 420)
    assert app.locator(".picker .pv b").is_visible()
    app.click(".picker .pa button:has-text('Forecast')")
    assert app.locator(".meteo tr.days td").count() == 10
    app.click(".meteo .mtabs button:has-text('Meteogram')")
    assert app.locator(".meteo svg.mchart").is_visible()
    app.click(".meteo header button[aria-label='Close']")
    assert app.locator(".meteo").count() == 0


def test_search_jumps_to_a_place(app):
    app.click(".rail [aria-label='Search']")
    app.keyboard.type("Kolkata")
    app.keyboard.press("Enter")
    assert app.locator(".pop").count() == 0
    assert "Kolkata" in app.locator(".picker .pa span").inner_text()


def test_settings_change_units_and_list_start_states(app):
    app.click(".rail [aria-label='Settings']")
    row = app.locator(".pop .row:has-text('Temperature') b")
    before = row.inner_text()
    row.click()
    assert row.inner_text() != before
    assert app.locator(".pop .list").first.locator(".row").count() >= 1
    assert "ready" in app.locator(".pop .status").inner_text()


@pytest.mark.parametrize(
    "label,heading", [("Timeline Prime", "Timeline Prime"), ("Validation", "Validation"), ("About the model", "About")]
)
def test_secondary_pages_open_and_return_to_the_map(app, label, heading):
    app.click(".rail [aria-label='About, validation and more']")
    app.click(f".pop .row.nav:has-text('{label}')")
    app.wait_for_selector(".sheet h2", timeout=15000)
    assert heading in app.locator(".sheet h2").first.inner_text()
    app.click(".sheetx")
    assert app.locator(".sheet").count() == 0
    assert app.locator(".tline").is_visible()


# ------------------------------------------------------------------------------------------------ layouts
@pytest.mark.parametrize("w,h", [(1280, 720), (390, 844)])
def test_layout_fits_laptop_and_phone(app, w, h):
    app.set_viewport_size({"width": w, "height": h})
    app.wait_for_timeout(400)
    for sel in (".logo", ".rail.top", ".rail.bottom", ".tline", ".legend"):
        b = app.locator(sel).bounding_box()
        assert b and b["x"] >= 0 and b["y"] >= 0 and b["x"] + b["width"] <= w + 1 and b["y"] + b["height"] <= h + 1, (
            f"{sel} off screen: {b}"
        )
    assert app.evaluate("document.scrollingElement.scrollWidth") <= w, "horizontal scrolling"
