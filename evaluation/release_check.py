"""One command before every push and tag: every gate we have, strict pass/fail, one summary.

    python -m evaluation.release_check            # everything (about 10 minutes; needs data/ and Docker)
    python -m evaluation.release_check --quick    # no dataset steps: lint, tests, scan, dashboard

Steps (thresholds: configs/rehearsal.yaml, configs/eval.yaml gate):
  lint         ruff check
  tests        pytest: unit tests plus the strict judge-contract tests (read-only copy, kit blocked, kit validator)
  scan         the kit's repo scan on a clean copy: 15 / 15, no flags
  preflight    static checks: artifacts and hashes, calibration, dashboard bundle offline (no external hosts)
  gate         causality gate, both official shocks, every season, our stricter thresholds
  sweep        both official shocks on every held-out window
  fuzz         random shocks: validity 100 %, causality pass rate at least the release floor
  selfgrade    held-out 2021 through the engine: valid, full RMSE points, CSI floor, day-8 variance band
  rehearsal    the judge's procedure in a judge-like container (evaluation/judge_rehearsal.py)
  dashboard    vitest and the production build (type-check)
Exit 0 only when every step passes. A skipped step is not a pass (exit 2). Report: runs/release_check/report.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
DATA = ROOT / "data" / "india_climate_train.nc"


def run(cmd: list[str], timeout: int, cwd: Path = ROOT) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr)
    except subprocess.TimeoutExpired as e:
        return 124, f"timeout after {timeout} s\n{e.stdout or ''}"
    except FileNotFoundError as e:
        return 127, str(e)


def last(text: str, n: int = 1) -> str:
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return " | ".join(lines[-n:])[:300]


def check_fuzz(cfg: dict) -> tuple[bool, str]:
    s = json.loads((ROOT / "runs/fuzz/summary.json").read_text())
    rel = cfg["release"]
    ok = s["validity"] >= rel["fuzz_validity"] and s["pass_rate"] >= rel["fuzz_pass_rate"]
    return (
        ok,
        f"n={s['n']} validity={s['validity']:.3f} (need {rel['fuzz_validity']}) pass_rate={s['pass_rate']:.3f} (need {rel['fuzz_pass_rate']})",
    )


def check_selfgrade(cfg: dict) -> tuple[bool, str]:
    r = json.loads((ROOT / "runs/selfgrade/latest.json").read_text())["systematic"]
    t = cfg["strict"]
    lo, hi = t["blur_ratio"]
    br = r["var_ratio_day8_mean"]
    fails = []
    if not r["valid"]:
        fails.append("invalid output")
    if r["mean_ss"] < t["mean_ss_min"]:
        fails.append(f"mean_ss {r['mean_ss']:.4f} < {t['mean_ss_min']}")
    if r["mean_csi_skill"] < t["csi_skill_min"]:
        fails.append(f"csi {r['mean_csi_skill']:.4f} < {t['csi_skill_min']}")
    if not all(lo <= x <= hi for x in br):
        fails.append(f"day-8 variance ratio {[round(x, 2) for x in br]} outside [{lo}, {hi}]")
    msg = (
        f"n={r['n_windows']} mean_ss={r['mean_ss']:.4f} ({r['rmse_pts']:.1f}/30) csi={r['mean_csi_skill']:.4f} "
        f"({r['csi_pts']:.1f}/15) blur {r['blur_pts']:.1f}/10"
    )
    return not fails, msg + ("" if not fails else "  FAIL: " + "; ".join(fails))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true", help="skip the dataset and Docker steps")
    ap.add_argument("--skip", nargs="*", default=[], help="step names to skip (reported as SKIPPED, exit 2)")
    ap.add_argument("--worktree", action="store_true", help="rehearse the working tree instead of git HEAD")
    args = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "configs/rehearsal.yaml").read_text())
    skip = set(args.skip) | ({"gate", "sweep", "fuzz", "selfgrade", "rehearsal"} if args.quick else set())

    steps: list[tuple[str, list[str], int, Path, object]] = [
        ("lint", [PY, "-m", "ruff", "check", "."], 120, ROOT, None),
        ("tests", [PY, "-m", "pytest", "-q", "tests/"], 900, ROOT, None),
        ("scan", [PY, "-m", "evaluation.scan_repo"], 300, ROOT, None),
        ("preflight", [PY, "scripts/preflight.py"], 300, ROOT, None),
        ("gate", [PY, "-m", "evaluation.causality_gate", "--config", "configs/eval.yaml"], 1200, ROOT, None),
        ("sweep", [PY, "-m", "evaluation.shock_sweep"], 1800, ROOT, None),
        ("fuzz", [PY, "-m", "evaluation.fuzz_gym", "--config", "configs/fuzz.yaml"], 1800, ROOT, check_fuzz),
        ("selfgrade", [PY, "-m", "evaluation.selfgrade", "--config", "configs/eval.yaml", "--tag", "release"], 1800, ROOT, check_selfgrade),
        ("rehearsal", [PY, "-m", "evaluation.judge_rehearsal", *(["--worktree"] if args.worktree else [])], 1800, ROOT, None),
        ("dashboard-tests", ["npm", "test", "--silent"], 300, ROOT / "dashboard", None),
        ("dashboard-build", ["npm", "run", "build", "--silent"], 300, ROOT / "dashboard", None),
    ]  # fmt: skip
    data_steps = {"preflight", "gate", "sweep", "fuzz", "selfgrade", "rehearsal"}
    rows = []
    t_all = time.time()
    for name, cmd, timeout, cwd, post in steps:
        if name in skip:
            rows.append({"step": name, "status": "SKIPPED", "s": 0, "detail": "skipped on request"})
            print(f"[SKIPPED] {name}", flush=True)
            continue
        if name in data_steps and name != "preflight" and not DATA.exists():
            rows.append({"step": name, "status": "FAIL", "s": 0, "detail": f"needs {DATA.relative_to(ROOT)}"})
            print(f"[FAIL] {name}: needs {DATA.relative_to(ROOT)}", flush=True)
            continue
        if name == "rehearsal" and not shutil.which("docker"):
            rows.append({"step": name, "status": "FAIL", "s": 0, "detail": "needs Docker (or --skip rehearsal)"})
            print(f"[FAIL] {name}: needs Docker", flush=True)
            continue
        if name.startswith("dashboard") and not shutil.which("npm"):
            rows.append({"step": name, "status": "FAIL", "s": 0, "detail": "needs Node 20+ and npm"})
            continue
        if name.startswith("dashboard") and not (ROOT / "dashboard/node_modules").exists():
            run(["npm", "ci", "--no-audit", "--no-fund"], 600, ROOT / "dashboard")
        print(f"[....] {name}", end="", flush=True)
        t0 = time.time()
        rc, out = run(cmd, timeout, cwd)
        ok, detail = rc == 0, last(out, 2)
        if ok and post is not None:
            try:
                ok, detail = post(cfg)
            except Exception as e:  # missing or malformed report counts as a failure
                ok, detail = False, f"cannot read the report: {type(e).__name__}: {e}"
        if name == "rehearsal":
            fails = [ln.strip() for ln in out.splitlines() if "[FAIL]" in ln]
            detail = (last(out) + ("  " + " ; ".join(fails[:4]) if fails else ""))[:600]
        rows.append(
            {
                "step": name,
                "status": "PASS" if ok else "FAIL",
                "s": round(time.time() - t0, 1),
                "detail": detail,
                "rc": rc,
            }
        )
        print(f"\r[{'PASS' if ok else 'FAIL'}] {name} ({time.time() - t0:.0f} s): {detail}", flush=True)

    out_dir = ROOT / "runs/release_check"
    out_dir.mkdir(parents=True, exist_ok=True)
    failed = [r["step"] for r in rows if r["status"] == "FAIL"]
    skipped = [r["step"] for r in rows if r["status"] == "SKIPPED"]
    verdict = "FAIL" if failed else ("INCOMPLETE" if skipped else "PASS")
    (out_dir / "report.json").write_text(
        json.dumps({"verdict": verdict, "steps": rows, "seconds": time.time() - t_all}, indent=1)
    )
    print(f"\nRELEASE CHECK: {verdict} in {time.time() - t_all:.0f} s", end="")
    print(f"  failed: {failed}" if failed else "", end="")
    print(f"  skipped: {skipped}" if skipped else "")
    print("report: runs/release_check/report.json")
    return 1 if failed else (2 if skipped else 0)


if __name__ == "__main__":
    sys.exit(main())
