#!/usr/bin/env bash
# Starts the forecast server, the lab server and the built dashboard, waits until each is ready, runs the live checks and
# opens the browser.   bash scripts/demo.sh          start everything
#                      bash scripts/demo.sh stop     stop what this script started
# Needs: artifacts/ (committed), data/india_climate_train.nc (NOT committed), Node 20+ for the dashboard build.
set -u
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=${PY:-python}
[ -x "$ROOT/.venv/bin/python" ] && PY="$ROOT/.venv/bin/python"
JUDGE_PORT=${JUDGE_PORT:-8000}; LAB_PORT=${LAB_PORT:-8001}; DASH_PORT=${DASH_PORT:-4173}
RUN="$ROOT/runs/demo"; mkdir -p "$RUN"

stop_all() {
  for f in "$RUN"/*.pid; do
    [ -f "$f" ] || continue
    pid=$(cat "$f"); kill "$pid" 2>/dev/null && echo "stopped $(basename "$f" .pid) ($pid)"; rm -f "$f"
  done
}
if [ "${1:-}" = "stop" ]; then stop_all; exit 0; fi

die() { echo "ERROR: $*" >&2; stop_all; exit 1; }
wait_for() {  # url, seconds, label
  local i=0
  until curl -fsS -o /dev/null "$1" 2>/dev/null; do
    i=$((i + 1)); [ "$i" -ge "$2" ] && die "$3 did not come up within $2 s (see $RUN/*.log)"; sleep 1
  done
}
busy() { (exec 3<>/dev/tcp/127.0.0.1/"$1") 2>/dev/null; }

echo "== 1/5 preflight =="
if [ ! -f dashboard/dist/index.html ]; then
  echo "dashboard not built yet: building"
  command -v npm >/dev/null || die "npm not found (install Node 20+)"
  (cd dashboard && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && npm run build) >"$RUN/build.log" 2>&1 || die "dashboard build failed (see $RUN/build.log)"
fi
"$PY" scripts/preflight.py --ports "$JUDGE_PORT,$LAB_PORT,$DASH_PORT" || die "preflight failed: fix the FAIL lines above, then run again"

echo "== 2/5 forecast server =="
if busy "$JUDGE_PORT"; then echo "port $JUDGE_PORT already serving: reusing it"; else
  nohup "$PY" serve.py --port "$JUDGE_PORT" >"$RUN/serve.log" 2>&1 & echo $! >"$RUN/serve.pid"
fi
i=0; until curl -fsS -X POST "http://127.0.0.1:$JUDGE_PORT/health" 2>/dev/null | grep -q '"ready"'; do i=$((i + 1)); [ "$i" -ge 120 ] && die "forecast server not ready after 120 s"; sleep 1; done
echo "ready"

echo "== 3/5 lab server =="
if busy "$LAB_PORT"; then echo "port $LAB_PORT already serving: reusing it"; else
  nohup "$PY" -m lab.lab_server --port "$LAB_PORT" >"$RUN/lab.log" 2>&1 & echo $! >"$RUN/lab.pid"
fi
wait_for "http://127.0.0.1:$LAB_PORT/status" 90 "lab server"
echo "ready"

echo "== 4/5 dashboard =="
if busy "$DASH_PORT"; then echo "port $DASH_PORT already serving: reusing it"; else
  (cd dashboard && nohup npx vite preview --host 0.0.0.0 --port "$DASH_PORT" >"$RUN/dashboard.log" 2>&1 & echo $! >"$RUN/dashboard.pid")
fi
wait_for "http://127.0.0.1:$DASH_PORT" 30 "dashboard"
echo "ready"

echo "== 5/5 live checks (also warms the model) =="
"$PY" scripts/preflight.py --live --ports "$JUDGE_PORT,$LAB_PORT,$DASH_PORT" || die "live checks failed (see above)"

URL="http://localhost:$DASH_PORT"
echo; echo "Dashboard: $URL      (stop with: bash scripts/demo.sh stop)"
if [ -z "${NO_OPEN:-}" ]; then
  (command -v xdg-open >/dev/null && xdg-open "$URL" >/dev/null 2>&1) || (command -v open >/dev/null && open "$URL") || true
fi
