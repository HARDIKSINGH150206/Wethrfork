#!/usr/bin/env bash
# Starts the judge server, the lab server and the built dashboard, waits until ready, warms up, opens the browser.
# STUB: implement in Phase 6 (docs/PHASES.md). Steps:
#   1. python serve.py --port 8000 &        wait for health = ready
#   2. python -m lab.lab_server --port 8001 &   wait for /meta
#   3. (cd dashboard && npm run build && npm run preview -- --port 5173) &
#   4. one warm-up fork via the lab or a small Python call using Engine
#   5. open http://localhost:5173
