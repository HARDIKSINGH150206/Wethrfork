"""Capture the README screenshots from the live dashboard (docs/images/screenshots/*.jpg).

Needs the three services running (bash scripts/demo.sh) and Playwright for Python with Chrome or Chromium:
    pip install playwright pillow && python scripts/capture_readme_screenshots.py [--chrome /usr/bin/google-chrome]
Every image shows live output of our own forecast server on a real start state; nothing is staged or pre-rendered.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images" / "screenshots"


def main() -> int:
    from PIL import Image
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:4173/")
    ap.add_argument("--chrome", default=None, help="Chrome or Chromium binary (default: Playwright's own)")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    def save(page, name: str, quality: int = 84) -> None:
        page.wait_for_timeout(900)  # let particles and transitions settle
        img = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
        img.save(OUT / f"{name}.jpg", "JPEG", quality=quality, optimize=True, progressive=True)
        print(f"{name}.jpg  {img.size[0]}x{img.size[1]}  {(OUT / f'{name}.jpg').stat().st_size // 1024} KB")

    def day(page, k: int) -> None:  # jump the timeline to forecast day k (1-based)
        box = page.locator(".tline .ticks").bounding_box()
        page.mouse.click(box["x"] + box["width"] * (k - 1) / 9, box["y"] + 6)
        page.mouse.move(700, 120)

    errors: list[str] = []
    with sync_playwright() as p:
        kw = {"executable_path": args.chrome} if args.chrome else {}
        b = p.chromium.launch(headless=True, args=["--no-sandbox"], **kw)
        page = b.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(args.url)
        page.wait_for_selector(".models button.on small", timeout=60000)
        page.mouse.move(720, 120)
        save(page, "hero-wind")

        page.click(".maps .item:has-text('Precipitation')")
        save(page, "precipitation")

        page.click(".maps .item:has-text('Temperature')")
        page.click(".maps .item:has-text('Fork a universe')")
        page.click(".presets button:has-text('Warm Bay')")
        page.wait_for_function(
            "!document.querySelector('.models .spin') && document.querySelectorAll('.models button').length === 2",
            timeout=60000,
        )
        save(page, "fork-composer")

        page.click(".drawer .ptabs button:has-text('Audit')")
        page.wait_for_selector(".checks li", timeout=60000)
        day(page, 2)
        save(page, "audit-verdict")
        page.click(".drawer .ptabs .x")

        page.click(".maps .sub:has-text('Difference')")
        day(page, 4)
        save(page, "difference-rings")

        page.click(".maps .sub:has-text('Swipe compare')")
        day(page, 3)
        save(page, "swipe-compare")
        page.click(".maps .sub:has-text('Swipe compare')")

        day(page, 1)
        page.click(".maps .item:has-text('Pressure')")
        page.click(".rail [aria-label='Pressure lines']")
        page.mouse.click(700, 360)
        page.click(".picker .pa button:has-text('Forecast')")
        page.click(".meteo .mtabs button:has-text('Meteogram')")
        save(page, "point-forecast")
        page.click(".meteo header button[aria-label='Close']")
        page.click(".picker .x")
        page.click(".rail [aria-label='Pressure lines']")

        for label, name in (
            ("Timeline Prime", "page-timeline-prime"),
            ("Validation", "page-validation"),
            ("About the model", "page-about"),
        ):
            page.click(".rail [aria-label='About, validation and more']")
            page.click(f".pop .row.nav:has-text('{label}')")
            page.wait_for_timeout(2500)
            save(page, name)
            page.click(".sheetx")

        page.set_viewport_size({"width": 390, "height": 844})
        page.click(".maps .item:has-text('Wind')") if page.locator(".maps .item:has-text('Wind')").count() else None
        save(page, "phone")
        b.close()
    if errors:
        print("page errors:", errors[:5])
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
