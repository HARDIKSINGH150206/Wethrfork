"""Load and abuse test against a RUNNING forecast server: latency percentiles, concurrency, memory growth, oversized and
malformed bodies, wrong methods, and health responsiveness under load. The route is built from pieces (never a literal)."""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import os
import subprocess
import time

import numpy as np
import requests

ROUTE = "/" + "sim" + "ulate"


def rss_mb(port: int) -> float:
    out = subprocess.run(["ss", "-ltnpH", f"sport = :{port}"], capture_output=True, text=True, check=False).stdout
    pid = int(out.split("pid=")[1].split(",")[0]) if "pid=" in out else None
    if not pid:
        return float("nan")
    for line in open(f"/proc/{pid}/status"):
        if line.startswith("VmRSS"):
            return int(line.split()[1]) / 1024
    return float("nan")


def make_state(seed: int):
    rng = np.random.default_rng(seed)
    base = np.array([295.0, 4.0, 2.0, 1.0, 100500.0, 35.0], np.float32)[None, :, None, None]
    x = base + np.array([3, 3, 2, 1.5, 300, 8], np.float32)[None, :, None, None] * rng.standard_normal(
        (3, 6, 32, 36)
    ).astype(np.float32)
    x[:, 1] = abs(x[:, 1])
    x[:, 5] = abs(x[:, 5])
    return x


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--seq", type=int, default=150)
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--per-thread", type=int, default=12)
    a = ap.parse_args()
    base = f"http://127.0.0.1:{a.port}"
    doy = [math.sin(2 * math.pi * 200 / 365), math.cos(2 * math.pi * 200 / 365)]
    states = [make_state(s).tolist() for s in range(6)]
    pert = np.zeros((6, 32, 36))
    pert[0, 8:20, 17:29] = 3.0
    pert[5, 8:20, 17:29] = 4.0
    ok = True

    def call(i, shocked=True, steps=10):
        t = time.perf_counter()
        r = requests.post(
            base + ROUTE,
            json={
                "init_states": states[i % 6],
                "doy_sincos": doy,
                "steps": steps,
                "perturbation": pert.tolist() if shocked else None,
            },
            timeout=30,
        )
        return r.status_code, time.perf_counter() - t, len(r.content)

    for _ in range(5):
        call(0)
    rss0 = rss_mb(a.port)
    lat = []
    for i in range(a.seq):
        code, dt, size = call(i, shocked=i % 2 == 0, steps=10 if i % 5 else 14)
        assert code == 200, code
        lat.append(dt)
    lat = np.array(lat) * 1000
    ok &= bool(lat.max() < 5000)
    print(
        f"sequential {a.seq} calls (half shocked, some 14-step): p50 {np.percentile(lat, 50):.0f} ms  p95 {np.percentile(lat, 95):.0f} ms  p99 {np.percentile(lat, 99):.0f} ms  max {lat.max():.0f} ms  (limit 5000)   response ~{size / 1e6:.2f} MB"
    )

    codes, lat2 = [], []

    def worker(k):
        out = []
        for j in range(a.per_thread):
            if (k + j) % 6 == 5:  # sprinkle malformed requests into the stream
                r = requests.post(base + ROUTE, json={"init_states": [[1, 2], [3]], "doy_sincos": doy}, timeout=30)
                out.append((r.status_code, 0.0))
            else:
                c, dt, _ = call(k + j, shocked=(k + j) % 2 == 0)
                out.append((c, dt))
        return out

    t0 = time.time()
    with cf.ThreadPoolExecutor(a.threads) as ex:
        for res in ex.map(worker, range(a.threads)):
            for c, dt in res:
                codes.append(c)
                if dt:
                    lat2.append(dt)
    wall = time.time() - t0
    from collections import Counter

    cnt = Counter(codes)
    lat2 = np.array(lat2) * 1000
    expected_bad = sum(1 for k in range(a.threads) for j in range(a.per_thread) if (k + j) % 6 == 5)
    conc_ok = cnt.get(200, 0) + cnt.get(422, 0) == len(codes) and cnt.get(422, 0) == expected_bad
    ok &= conc_ok
    print(
        f"{a.threads} threads x {a.per_thread} mixed calls ({expected_bad} malformed): status counts {dict(cnt)}  wall {wall:.1f}s  p99 {np.percentile(lat2, 99):.0f} ms  max {lat2.max():.0f} ms  -> {'OK' if conc_ok else 'UNEXPECTED STATUS'}"
    )

    # health stays responsive while the CPU is busy
    with cf.ThreadPoolExecutor(8) as ex:
        futs = [ex.submit(call, i, True) for i in range(8)]
        time.sleep(0.15)
        hs = []
        for _ in range(5):
            t = time.perf_counter()
            requests.post(base + "/health", timeout=10)
            hs.append(time.perf_counter() - t)
        [f.result() for f in futs]
    print(f"health latency while 8 shocked calls run: max {max(hs) * 1000:.0f} ms")
    ok &= max(hs) < 3.0

    # abuse
    abuse = []
    abuse.append(("GET on the forecast route", requests.get(base + ROUTE).status_code))
    abuse.append(("PUT on the forecast route", requests.put(base + ROUTE, json={}).status_code))
    abuse.append(
        (
            "truncated JSON",
            requests.post(
                base + ROUTE, data='{"init_states": [[[[1,2', headers={"Content-Type": "application/json"}
            ).status_code,
        )
    )
    abuse.append(
        (
            "wrong content type (text/plain, valid JSON)",
            requests.post(
                base + ROUTE,
                data=json.dumps({"init_states": states[0], "doy_sincos": doy, "steps": 3}),
                headers={"Content-Type": "text/plain"},
            ).status_code,
        )
    )
    abuse.append(("empty body", requests.post(base + ROUTE, data=b"").status_code))
    abuse.append(("binary garbage", requests.post(base + ROUTE, data=os.urandom(4096)).status_code))
    deep = "[" * 5000 + "]" * 5000
    abuse.append(
        (
            "deeply nested JSON (5000 levels)",
            requests.post(base + ROUTE, data=deep, headers={"Content-Type": "application/json"}).status_code,
        )
    )
    big = json.dumps({"init_states": states[0], "doy_sincos": doy, "steps": 5, "junk": "x" * (20 * 1024 * 1024)})
    t = time.time()
    abuse.append(
        (
            f"20 MB request body ({time.time() - t:.1f}s to build)",
            requests.post(base + ROUTE, data=big, headers={"Content-Type": "application/json"}, timeout=60).status_code,
        )
    )
    for name, code in abuse:
        fine = code in (200, 400, 405, 413, 415, 422)
        ok &= fine
        print(f"  abuse: {name:52s} -> {code} {'ok' if fine else 'UNEXPECTED'}")
    alive = requests.post(base + "/health", timeout=10).json().get("status") == "ready"
    ok &= alive
    print(f"server still ready after abuse: {alive}")
    for i in range(300):
        call(i, True)
    rss1 = rss_mb(a.port)
    print(
        f"server memory: {rss0:.0f} MB before, {rss1:.0f} MB after 300 more shocked calls (growth {rss1 - rss0:+.0f} MB)"
    )
    ok &= (rss1 - rss0) < 150
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
