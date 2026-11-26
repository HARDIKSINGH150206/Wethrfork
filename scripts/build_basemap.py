"""Build the dashboard's offline base map from two public-domain sources (DECISIONS.md D42).

    dashboard/public/basemap.jpg   NASA Blue Marble "land and oceans" (public domain), cropped to the map extent
    dashboard/public/borders.json  Natural Earth 1:10m countries, India's point of view (public domain): coastlines and
                                   land borders clipped to the map extent, de-duplicated and simplified, plus label points

One-off build step; the outputs are committed so the dashboard needs no network. Needs Pillow (not a serve dependency).

    python scripts/build_basemap.py --image Whole_world_-_land_and_oceans_12000.jpg \
                                    --countries ne_10m_admin_0_countries_ind.geojson

Sources:
    https://commons.wikimedia.org/wiki/File:Whole_world_-_land_and_oceans_12000.jpg  (24000 x 12000, NASA)
    https://github.com/nvkelso/natural-earth-vector  geojson/ne_10m_admin_0_countries_ind.geojson
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard" / "public"

# Map extent: wider than the model domain (65-101 E, 6-38 N) so the map never ends at the screen edge.
LON0, LON1, LAT0, LAT1 = 40.0, 126.0, -6.0, 52.0
PPD = 24  # basemap pixels per degree
SIMPLIFY_DEG = 0.012  # Douglas-Peucker tolerance (about 1.3 km)
LABEL_BOX = (62.0, 104.0, 4.0, 40.0)  # country labels are kept when their label point falls in here

Pt = tuple[float, float]


def build_image(src: Path) -> None:
    from PIL import Image, ImageEnhance

    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(src).convert("RGB")
    w, h = im.size
    box = (
        round((LON0 + 180) / 360 * w),
        round((90 - LAT1) / 180 * h),
        round((LON1 + 180) / 360 * w),
        round((90 - LAT0) / 180 * h),
    )
    crop = im.crop(box).resize((round((LON1 - LON0) * PPD), round((LAT1 - LAT0) * PPD)), Image.Resampling.LANCZOS)
    crop = ImageEnhance.Brightness(crop).enhance(0.9)  # a touch darker so forecast colours and labels read on top
    crop.save(OUT / "basemap.jpg", "JPEG", quality=80, optimize=True, progressive=True)


def clip_ring(ring: list[Pt]) -> list[Pt]:
    """Sutherland-Hodgman clip of a closed ring against the map extent."""
    edges = (
        (lambda p: p[0] >= LON0, lambda a, b: _ix(a, b, 0, LON0)),
        (lambda p: p[0] <= LON1, lambda a, b: _ix(a, b, 0, LON1)),
        (lambda p: p[1] >= LAT0, lambda a, b: _ix(a, b, 1, LAT0)),
        (lambda p: p[1] <= LAT1, lambda a, b: _ix(a, b, 1, LAT1)),
    )
    pts = ring[:-1] if ring and ring[0] == ring[-1] else ring
    for inside, cut in edges:
        if not pts:
            break
        out: list[Pt] = []
        prev = pts[-1]
        for cur in pts:
            if inside(cur):
                if not inside(prev):
                    out.append(cut(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cut(prev, cur))
            prev = cur
        pts = out
    return pts + pts[:1] if pts else []


def _ix(a: Pt, b: Pt, axis: int, v: float) -> Pt:
    t = (v - a[axis]) / (b[axis] - a[axis])
    p = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
    p[axis] = v
    return (p[0], p[1])


def on_frame(a: Pt, b: Pt) -> bool:
    """True for a segment that lies along the clip frame (an artefact of clipping, never drawn)."""
    return any(a[k] == v and b[k] == v for k, v in ((0, LON0), (0, LON1), (1, LAT0), (1, LAT1)))


def simplify(pts: list[Pt], tol: float) -> list[Pt]:
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        (x0, y0), (x1, y1) = pts[i], pts[j]
        dx, dy = x1 - x0, y1 - y0
        n = (dx * dx + dy * dy) ** 0.5 or 1e-12
        best, k = -1.0, -1
        for m in range(i + 1, j):
            d = abs(dy * (pts[m][0] - x0) - dx * (pts[m][1] - y0)) / n
            if d > best:
                best, k = d, m
        if best > tol:
            keep[k] = True
            stack += [(i, k), (k, j)]
    return [p for p, f in zip(pts, keep, strict=True) if f]


def build_borders(src: Path) -> None:
    feats = json.loads(src.read_text())["features"]
    rings: list[list[Pt]] = []
    labels = []
    for f in feats:
        g, p = f["geometry"], f["properties"]
        if g is None:
            continue
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            for ring in poly[:1]:  # outer rings only: holes are lakes or enclaves, too small at this scale
                r = clip_ring([(float(x), float(y)) for x, y in ring])
                if len(r) > 3:
                    rings.append(r)
        lx, ly = p.get("LABEL_X"), p.get("LABEL_Y")
        if lx is not None and LABEL_BOX[0] <= lx <= LABEL_BOX[1] and LABEL_BOX[2] <= ly <= LABEL_BOX[3]:
            labels.append(
                {
                    "name": str(p.get("NAME_EN") or p["NAME"]).upper(),
                    "lon": round(lx, 2),
                    "lat": round(ly, 2),
                    "rank": int(p.get("LABELRANK", 5)),
                }
            )

    # A segment used by two countries is a land border, by one a coastline. Shared borders are identical in Natural
    # Earth, so counting undirected segments separates the two and lets each border be drawn once.
    key = lambda a, b: (a, b) if a <= b else (b, a)  # noqa: E731
    count: dict[tuple[Pt, Pt], int] = {}
    for r in rings:
        for a, b in zip(r, r[1:], strict=False):
            if a != b and not on_frame(a, b):
                count[key(a, b)] = count.get(key(a, b), 0) + 1
    seen: set[tuple[Pt, Pt]] = set()
    lines: dict[str, list[list[Pt]]] = {"coast": [], "border": []}
    for r in rings:
        run: list[Pt] = []
        kind = ""
        for a, b in zip(r, r[1:], strict=False):
            k = key(a, b)
            ok = a != b and k in count and k not in seen
            t = "border" if count.get(k, 0) > 1 else "coast"
            if ok and run and t == kind and run[-1] == a:
                run.append(b)
            else:
                if len(run) > 1:
                    lines[kind].append(run)
                run, kind = ([a, b], t) if ok else ([], "")
            if ok:
                seen.add(k)
        if len(run) > 1:
            lines[kind].append(run)

    def pack(ls: list[list[Pt]]) -> list[list[list[float]]]:
        out = []
        for ln in ls:
            s = simplify(ln, SIMPLIFY_DEG)
            if len(s) > 1:
                out.append([[round(x, 3), round(y, 3)] for x, y in s])
        return out

    doc = {
        "source": "Natural Earth 1:10m admin 0 countries, India point of view (public domain)",
        "extent": [LON0, LON1, LAT0, LAT1],
        "coast": pack(lines["coast"]),
        "border": pack(lines["border"]),
        "labels": sorted(labels, key=lambda d: d["rank"]),
    }
    (OUT / "borders.json").write_text(json.dumps(doc, separators=(",", ":")))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", type=Path, help="Blue Marble land-and-oceans JPEG (equirectangular, whole world)")
    ap.add_argument("--countries", type=Path, help="Natural Earth admin 0 countries GeoJSON (India point of view)")
    a = ap.parse_args()
    if not a.image and not a.countries:
        ap.error("give --image and/or --countries")
    if a.image:
        build_image(a.image)
    if a.countries:
        build_borders(a.countries)
    for name in ("basemap.jpg", "borders.json"):
        f = OUT / name
        if f.exists():
            print(f"{f.relative_to(ROOT)}  {f.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
