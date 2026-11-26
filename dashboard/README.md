# dashboard/

React + Vite + TypeScript dashboard. Feature specification: ../docs/06-frontend-plan.md; current layout: D42 in
../docs/DECISIONS.md. Calls the judge server on port 8000 and the lab server on port 8001. Must work offline.

```bash
npm ci && npm run build      # type-check and build into dist/
npm test                     # vitest unit tests
bash ../scripts/demo.sh      # forecast server + lab server + this dashboard, with checks
```

Layout (`src/components/map/`): `Sidebar` (logo, map menu), `Rail` (right-hand tools and their panels), `Timeline`,
`Legend` (legend, run picker, coordinates, scale, sources), `MapStage` (canvas: base map, forecast, labels, particles),
`Drawer` (shocks and audit), `Meteogram` (point forecast). The map camera lives in `src/state/mapctl.ts`.

Base map files in `public/` (public domain, built by `../scripts/build_basemap.py`, committed so nothing is fetched):
`basemap.jpg` (NASA Blue Marble) and `borders.json` (Natural Earth 1:10m, India's point of view).
`india_outline.geojson` is kept only as a fallback if `borders.json` is missing.
