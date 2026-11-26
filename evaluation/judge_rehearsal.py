"""Judge rehearsal: the organisers' Stage 1 procedure, as close as we can reproduce it, with strict pass/fail.

1. A clean copy of the repo (default: the committed tree, git HEAD, which is what the judge receives).
2. The server runs in `wethrfork-judge:py311` (docker/judge.Dockerfile: Python 3.11, only the allowed libraries, NO kit)
   with no network, a read-only repo AND a read-only root filesystem (only /tmp writable), 4 CPUs, 6 GB RAM.
3. A grader container shares its network namespace and makes every call with the kit's own client
   (evaluation/grader_client.py): health wait, then the forecast calls back to back, then contract probes for steps
   1..14, then the kit's schema validator.
4. The answers are scored here with `monsoon_r1.scoring` against the real archive: validity, RMSE skill, heavy-rain CSI,
   anti-blur, the four causality checks per official shock, the null shock. Thresholds: configs/rehearsal.yaml
   ("judge" = the organisers' limits, "strict" = ours) and the causality gate in configs/eval.yaml.

Calls: every held-out 2021 window (configs/eval.yaml systematic), the judge's window types (typed) and one window per
season; the three official shocks on every typed and season window (the judge uses one window, we use all); a repeated
call (determinism), the same call in base64 (both wire forms), and every typed window with the day of year counted from
0 instead of 1 (the contract does not say which; we must be fine with both).

    python -m evaluation.judge_rehearsal              # committed code
    python -m evaluation.judge_rehearsal --worktree   # include uncommitted and untracked (not ignored) files
Exit 0 only if every judge and strict check passes. Report: runs/rehearsal/report.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

import numpy as np

from evaluation import windows as W
from evaluation.causality_gate import growth_ratio, passes
from training.data import ROOT, load_archive, load_config

log = logging.getLogger(__name__)
JUDGE_IMAGE = "wethrfork-judge:py311"
GRADER_IMAGE = "wethrfork-grader:py311"
SHOCKS = {"warm_ocean": "BOX_BAY_OF_BENGAL", "monsoon_stall": "BOX_ARABIAN_SEA"}
LEADS = (0, 3, 7)  # days 1, 4, 8
CH = ("t2m", "tp", "u10", "v10", "msl", "tcwv")


# ---------------------------------------------------------------------------------------------------------- set-up
def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def ensure_images(rebuild: bool) -> None:
    have = lambda img: sh(["docker", "image", "inspect", img]).returncode == 0  # noqa: E731
    if rebuild or not have(JUDGE_IMAGE):
        log.info("building %s", JUDGE_IMAGE)
        r = sh(
            ["docker", "build", "-f", str(ROOT / "docker/judge.Dockerfile"), "-t", JUDGE_IMAGE, str(ROOT / "docker")]
        )
        if r.returncode:
            raise SystemExit(f"cannot build {JUDGE_IMAGE}:\n{r.stderr[-2000:]}")
    if rebuild or not have(GRADER_IMAGE):
        log.info("building %s", GRADER_IMAGE)
        r = sh(
            ["docker", "build", "-f", str(ROOT / "docker/grader.Dockerfile"), "-t", GRADER_IMAGE, str(ROOT / "vendor")]
        )
        if r.returncode:
            raise SystemExit(f"cannot build {GRADER_IMAGE}:\n{r.stderr[-2000:]}")


def export_repo(dest: Path, worktree: bool, source: Path | None = None) -> list[str]:
    """Copy the repo the way the judge gets it. Returns warnings (serve files that differ from what is exported).
    `source` copies an arbitrary directory instead (used to prove the rehearsal fails on deliberately broken copies)."""
    warn = []
    if source is not None:
        skip = shutil.ignore_patterns(".git", ".venv", "data", "runs", "node_modules", "dist", "__pycache__")
        shutil.copytree(source, dest, ignore=skip, dirs_exist_ok=True)
        warn.append(f"testing a copy of {source}, not this repo")
    elif worktree:
        files = sh(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT).stdout.split("\0")
        for f in filter(None, files):
            src = ROOT / f
            if src.is_file():
                (dest / f).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest / f)
    else:
        arch = dest.parent / "head.tar"
        r = sh(["git", "archive", "--format=tar", "-o", str(arch), "HEAD"], cwd=ROOT)
        if r.returncode:
            raise SystemExit(f"git archive failed: {r.stderr}")
        with tarfile.open(arch) as t:
            t.extractall(dest, filter="data")
        dirty = sh(
            ["git", "status", "--porcelain", "--", "serve.py", "wethrfork", "artifacts"], cwd=ROOT
        ).stdout.strip()
        if dirty:
            warn.append("uncommitted changes in serve files are NOT in this run (the judge gets HEAD):\n" + dirty)
    return warn


# ---------------------------------------------------------------------------------------------------------- plan
def build_plan(arc, ecfg: dict, std: np.ndarray, ready_limit: float) -> tuple[dict, dict]:
    """Windows and the ordered list of calls. Returns (plan for the grader, host-side context for scoring)."""
    from monsoon_r1 import contract as C
    from monsoon_r1 import scoring as S

    wins = []
    for kind, ws in (("systematic", W.systematic(arc, ecfg)), ("typed", W.typed(arc, ecfg))):
        wins += [dict(w, kind=kind) for w in ws]
    wins += [dict(w, kind="season") for w in W.shock_windows(arc, ecfg).values() if w]
    for w in wins:
        doy = int(arc.dates[w["last_idx"]].day_of_year)  # calendar day of year, counted from 1
        w["doy"] = C.doy_sincos(doy)
        w["doy0"] = C.doy_sincos(doy - 1)  # the same day counted from 0
    perts: list[np.ndarray] = []
    calls: list[dict] = []

    def add(cid: str, win: int, pert: np.ndarray | None, enc: str = "list", doy_key: str = "doy") -> None:
        p = -1
        if pert is not None:
            perts.append(pert.astype("f4"))
            p = len(perts) - 1
        calls.append({"id": cid, "win": win, "pert": p, "enc": enc, "doy": wins[win][doy_key]})

    for i, w in enumerate(wins):
        add(f"{w['id']}:base", i, None)
    shock_wins = [i for i, w in enumerate(wins) if w["kind"] in ("typed", "season")]
    for i in shock_wins:
        last = wins[i]["init"][-1]
        for name in SHOCKS:
            add(f"{wins[i]['id']}:{name}", i, S.make_shock(name, last, std))
        add(f"{wins[i]['id']}:null", i, S.make_shock("null", last, std))
    first = shock_wins[0]
    add(f"{wins[first]['id']}:repeat", first, None)
    add(f"{wins[first]['id']}:b64", first, None, enc="b64")
    add(
        f"{wins[first]['id']}:warm_ocean_b64",
        first,
        S.make_shock("warm_ocean", wins[first]["init"][-1], std),
        enc="b64",
    )
    for i in shock_wins:
        if wins[i]["kind"] == "typed":
            add(f"{wins[i]['id']}:doy0", i, None, doy_key="doy0")

    plan = {"ready_limit_s": ready_limit, "calls": calls}
    arrays = {
        "inits": np.stack([w["init"] for w in wins]).astype("f4"),
        "perts": np.stack(perts) if perts else np.zeros((0, 6, 32, 36), "f4"),
    }
    return plan, {"wins": wins, "arrays": arrays, "shock_wins": shock_wins}


# ---------------------------------------------------------------------------------------------------------- run
def run_containers(export: Path, work: Path, plan: dict, timeout_s: float) -> dict:
    name = f"wf-rehearsal-{int(time.time())}"
    run = [
        "docker", "run", "-d", "--name", name,
        "--network", "none", "--cpus", "4", "--memory", "6g", "--memory-swap", "6g",
        "--read-only", "--tmpfs", "/tmp:rw,size=1g",
        "-v", f"{export}:/sub:ro", "-w", "/sub",
        JUDGE_IMAGE, "python", "serve.py", "--port", "8000",
    ]  # fmt: skip
    info: dict = {"container": name}
    t_start = time.time()
    r = sh(run)
    if r.returncode:
        raise SystemExit(f"cannot start the server container: {r.stderr}")
    info["server_start_epoch"] = t_start
    try:
        g = sh(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                f"container:{name}",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "-v",
                f"{work}:/work",
                "-v",
                f"{ROOT / 'evaluation/grader_client.py'}:/grader_client.py:ro",
                GRADER_IMAGE,
                "python",
                "/grader_client.py",
                "/work",
            ],  # fmt: skip
            timeout=timeout_s,
        )
        info["grader_rc"], info["grader_stderr"] = g.returncode, g.stderr[-4000:]
        st = sh(
            ["docker", "inspect", "-f", "{{.State.Running}} {{.State.ExitCode}} {{.State.OOMKilled}}", name]
        ).stdout.split()
        info["server_running"], info["server_exit"], info["oom"] = st[0] == "true", int(st[1]), st[2] == "true"
        peak = sh(["docker", "exec", name, "cat", "/sys/fs/cgroup/memory.peak"]).stdout.strip()
        info["memory_peak_gb"] = int(peak) / 2**30 if peak.isdigit() else None
        logs = sh(["docker", "logs", name])
        info["server_log"] = (logs.stdout + logs.stderr)[-6000:]
    finally:
        sh(["docker", "rm", "-f", name])
    return info


# ---------------------------------------------------------------------------------------------------------- score
class Checks:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, level: str, name: str, ok: bool, value=None, limit=None) -> None:
        self.rows.append({"level": level, "check": name, "ok": bool(ok), "value": value, "limit": limit})

    @property
    def failed(self) -> list[dict]:
        return [r for r in self.rows if not r["ok"] and r["level"] in ("judge", "strict")]


def forecast_scores(wins: list[dict], outs: dict[int, np.ndarray], clim: np.ndarray, arc) -> dict:
    """The judge's forecast scoring with the kit: refs from the real dates (persistence, kit climatology by target day)."""
    from monsoon_r1 import scoring as S
    from monsoon_r1.stats import _doy_index

    ss_w, csi_w, ratios, p4, t4, pe4, cl4 = [], [], [], [], [], [], []
    for i, w in enumerate(wins):
        pred, truth = outs[i], w["truth"]
        steps = truth.shape[0]
        persist = np.repeat(w["init"][-1][None], steps, axis=0)
        climr = np.stack([clim[_doy_index(arc.dates[w["last_idx"] + k].date())] for k in range(1, steps + 1)])
        idx = list(LEADS)
        sk = S.skill_vs_best_ref(pred[idx], truth[idx], persist[idx], climr[idx])
        ss_w.append(float(np.nanmean(sk["ss"])))
        csi_w.append(
            S.csi_skill(
                S.csi(pred[idx, 1], truth[idx, 1]),
                S.csi(persist[idx, 1], truth[idx, 1]),
                S.csi(climr[idx, 1], truth[idx, 1]),
            )
        )
        ratios.append(S.variance_ratio(pred[7], truth[7]))
        for acc, x in ((p4, pred), (t4, truth), (pe4, persist), (cl4, climr)):
            acc.append(x[3])
    fp = S.forecast_points(ss_w, csi_w)
    ratios = np.array(ratios)
    d4 = S.skill_vs_best_ref(np.stack(p4), np.stack(t4), np.stack(pe4), np.stack(cl4))
    return {
        "n": len(wins),
        "mean_ss": fp["mean_ss"], "rmse_pts": fp["rmse_pts"],
        "mean_csi_skill": fp["mean_csi_skill"], "csi_pts": fp["csi_pts"],
        "blur_pts": S.anti_blur_points(ratios), "blur_ratio": np.nanmean(ratios, axis=0).tolist(),
        "day4_ss_persist": d4["ss_persist"].tolist(),
    }  # fmt: skip


def score(
    ctx: dict, plan: dict, res: dict, info: dict, cfg: dict, ecfg: dict, std: np.ndarray, arc, host_engine: bool
) -> tuple[Checks, dict]:
    from monsoon_r1 import contract as C
    from monsoon_r1 import scoring as S

    J, T = cfg["judge"], cfg["strict"]
    ck, rep = Checks(), {}
    wins = ctx["wins"]

    # --- start-up and environment
    ready_s = res.get("ready_epoch", 0) - info["server_start_epoch"] if res.get("ready") else None
    rep["ready_s"] = ready_s
    ck.add(
        "judge",
        "health ready (offline, read-only, 4 CPU, 6 GB, py3.11, no kit)",
        bool(res.get("ready")),
        ready_s,
        J["ready_s"],
    )
    if not res.get("ready"):
        return ck, rep
    ck.add("strict", "ready time", ready_s <= T["ready_s"], round(ready_s, 2), T["ready_s"])
    h = res["health"]
    hb = h["body"]
    ck.add(
        "judge",
        "health answers 200 {status: ready, model_name}",
        h["status_code"] == 200 and hb.get("status") == "ready",
        hb,
    )
    ck.add(
        "strict",
        "model_name is wethrfork-<version>",
        str(hb.get("model_name", "")).startswith("wethrfork-"),
        hb.get("model_name"),
    )
    mem = info.get("memory_peak_gb")
    ck.add("judge", "server memory", mem is not None and mem <= J["memory_gb"] and not info["oom"], mem, J["memory_gb"])
    ck.add(
        "strict",
        "server memory peak (GB)",
        mem is not None and mem <= T["memory_gb"],
        round(mem or -1, 2),
        T["memory_gb"],
    )
    ck.add("strict", "server still running after every call", info["server_running"], info["server_exit"])
    bad_log = [ln for ln in info["server_log"].splitlines() if "Traceback" in ln or " 500 " in ln or "ERROR" in ln]
    ck.add("strict", "server log has no traceback or error", not bad_log, bad_log[:3])

    # --- every scored call: kit client, 5 s, 200, valid
    calls = res["calls"]
    walls = np.array([c["wall_s"] for c in calls])
    failed = [c for c in calls if not c["ok"]]
    ck.add(
        "judge",
        f"all {len(calls)} calls answered (HTTP 200, < 5 s, decodable)",
        not failed,
        [f"{c['id']}: {c['error']}" for c in failed][:5],
    )
    rep["latency_s"] = {
        "first": float(walls[0]),
        "p50": float(np.median(walls)),
        "p95": float(np.percentile(walls, 95)),
        "max": float(walls.max()),
    }
    ck.add(
        "strict",
        "every call under the strict time",
        walls.max() <= T["call_s"],
        round(float(walls.max()), 3),
        T["call_s"],
    )
    ck.add(
        "strict",
        "first call after warm-up under the strict time",
        walls[0] <= T["call_s"],
        round(float(walls[0]), 3),
        T["call_s"],
    )
    outs_all = np.load(Path(res["_work"]) / "out.npz")["rollouts"]
    by_id = {c["id"]: outs_all[n] for n, c in enumerate(plan["calls"])}
    invalid = {cid: S.validity(o, C.SCORE_STEPS) for cid, o in by_id.items() if S.validity(o, C.SCORE_STEPS)}
    ck.add(
        "judge",
        "validity gate on every output (shape, finite, rain >= 0, t2m in range)",
        not invalid,
        list(invalid.items())[:5],
    )
    neg_q = [cid for cid, o in by_id.items() if o[:, 5].min() < 0]
    ck.add("strict", "moisture (tcwv) never negative", not neg_q, neg_q[:5])

    # --- wire contract
    pr = res["probes"]
    bad_pr = [p for p in pr if p.get("error") or p["status"] != 200 or p["shape"] != [p["steps"], 6, 32, 36] or p["validity"]
              or not p["rollout_is_list"] or not p["inference_ms_ok"] or "application/json" not in p["content_type"]
              or p["keys"] != ["inference_ms", "rollout"] or p["wall_s"] > J["call_s"]]  # fmt: skip
    ck.add(
        "judge",
        "steps 1..14: exact shape, nested lists, numeric inference_ms, JSON",
        not bad_pr,
        [p["steps"] for p in bad_pr],
    )
    ck.add(
        "judge",
        "kit schema validator (both wire forms, warm_ocean, zeros)",
        res["validator_rc"] == 0,
        res["validator_rc"],
    )
    w0 = wins[ctx["shock_wins"][0]]["id"]
    ck.add(
        "strict",
        "deterministic: repeated call identical bit for bit",
        np.array_equal(by_id[f"{w0}:base"], by_id[f"{w0}:repeat"]),
    )
    ck.add(
        "strict", "base64 input gives the same answer as lists", np.array_equal(by_id[f"{w0}:base"], by_id[f"{w0}:b64"])
    )
    ck.add(
        "strict",
        "base64 shock gives the same answer as lists",
        np.array_equal(by_id[f"{w0}:warm_ocean"], by_id[f"{w0}:warm_ocean_b64"]),
    )

    # --- causality on every shock window
    per_win, worst_null = {}, 0.0
    any_localized = False
    for i in ctx["shock_wins"]:
        wid = wins[i]["id"]
        base = by_id[f"{wid}:base"]
        r = {}
        for name, box_name in SHOCKS.items():
            box = getattr(C, box_name)
            sh_ = by_id[f"{wid}:{name}"]
            c = S.causality_checks(base, sh_, box, std)
            c["growth_ratio"] = growth_ratio(base, sh_, box, std)
            c["max_z"] = float(np.abs((sh_ - base) / std[None, :, None, None]).max())
            r[name] = c
            any_localized |= c["nonzero"] and c["localized"]
        null = by_id[f"{wid}:null"]
        r["null_max_diff"] = float(np.abs(null - base).max())
        worst_null = max(worst_null, r["null_max_diff"])
        null_ok = S.null_consistent(null, base, std)
        pts = S.causality_points([r["warm_ocean"], r["monsoon_stall"]], null_ok)
        gate = passes(r, ecfg["gate"])
        per_win[wid] = {
            "points": pts,
            "gate": gate,
            **{k: {kk: v for kk, v in r[k].items()} for k in SHOCKS},
            "null_max_diff": r["null_max_diff"],
        }
    rep["causality"] = per_win
    pts = {k: v["points"] for k, v in per_win.items()}
    ck.add("judge", "hard gate: a non-zero localized response to a shock", any_localized)
    null_bad = [w for w in per_win if not S.null_consistent(by_id[f"{w}:null"], by_id[f"{w}:base"], std)]
    ck.add("judge", "null shock within 1e-3 std of the unshocked call (kit null_consistent)", not null_bad, null_bad)
    ck.add("strict", "null shock identical bit for bit on every window", worst_null <= T["null_max_diff"], worst_null)
    ck.add(
        "judge",
        "causality points on the worst window >= half",
        min(pts.values()) >= J["causality_points"],
        min(pts.values()),
    )
    ck.add("strict", "causality 15 / 15 on every shock window", min(pts.values()) >= T["causality_points"], pts)
    gate_fail = {
        w: [k for k, ok in v["gate"].items() if not ok] for w, v in per_win.items() if not all(v["gate"].values())
    }
    ck.add(
        "strict",
        "our gate (near >= 0.75, growth >= 3, far <= 0.01, max z <= 4) on every window",
        not gate_fail,
        gate_fail,
    )

    # --- forecast skill on held-out 2021 (systematic) and on the judge's window types
    for kind in ("systematic", "typed"):
        sel = [w for w in wins if w["kind"] == kind]
        outs = {k: by_id[f"{w['id']}:base"] for k, w in enumerate(sel)}
        rep[f"forecast_{kind}"] = forecast_scores(sel, outs, ctx["clim"], arc)
    f = rep["forecast_systematic"]
    d4 = f["day4_ss_persist"]
    ck.add(
        "judge",
        "hard gate: beats persistence at day 4 (mean over channels, held-out 2021)",
        float(np.nanmean(d4)) > 0,
        round(float(np.nanmean(d4)), 3),
    )
    ck.add(
        "strict",
        "beats persistence at day 4 on every channel",
        min(d4) > 0,
        dict(zip(CH, np.round(d4, 3).tolist(), strict=True)),
    )
    ck.add(
        "strict",
        "mean RMSE skill (full 30 points)",
        f["mean_ss"] >= T["mean_ss_min"],
        round(f["mean_ss"], 4),
        T["mean_ss_min"],
    )
    ck.add(
        "strict",
        "heavy-rain CSI skill floor",
        f["mean_csi_skill"] >= T["csi_skill_min"],
        round(f["mean_csi_skill"], 4),
        T["csi_skill_min"],
    )
    lo, hi = T["blur_ratio"]
    br = f["blur_ratio"]
    ck.add(
        "strict",
        "day-8 variance ratio per channel within our band",
        all(lo <= x <= hi for x in br),
        dict(zip(CH, np.round(br, 2).tolist(), strict=True)),
        [lo, hi],
    )
    ck.add(
        "info",
        "points from held-out 2021 (RMSE / CSI / anti-blur)",
        True,
        f"{f['rmse_pts']:.1f}/30, {f['csi_pts']:.1f}/15, {f['blur_pts']:.1f}/10",
    )
    t = rep["forecast_typed"]
    ck.add(
        "info",
        "points on the judge's window types",
        True,
        f"{t['rmse_pts']:.1f}/30, {t['csi_pts']:.1f}/15, {t['blur_pts']:.1f}/10 (n={t['n']})",
    )

    # --- day-of-year convention: counting from 0 instead of 1 must not matter
    typed = [w for w in wins if w["kind"] == "typed"]
    shift = max(
        float(np.abs((by_id[f"{w['id']}:doy0"] - by_id[f"{w['id']}:base"]) / std[None, :, None, None]).max())
        for w in typed
    )
    alt = forecast_scores(typed, {k: by_id[f"{w['id']}:doy0"] for k, w in enumerate(typed)}, ctx["clim"], arc)
    dss = abs(alt["mean_ss"] - t["mean_ss"])
    rep["doy_shift"] = {"max_diff_std": shift, "skill_change": dss}
    ck.add(
        "strict",
        "day of year counted from 0 or 1: skill unchanged",
        dss <= T["doy_shift_skill_change"],
        round(dss, 4),
        T["doy_shift_skill_change"],
    )

    # --- the judge's environment gives the same numbers as ours
    if host_engine:
        from wethrfork.engine import Engine

        eng = Engine.load()
        drift = 0.0
        for w in typed:
            for cid, pert in (
                (f"{w['id']}:base", None),
                (f"{w['id']}:warm_ocean", S.make_shock("warm_ocean", w["init"][-1], std)),
            ):
                mine = eng.simulate(w["init"], w["doy"], 10, pert)
                drift = max(drift, float(np.abs((mine - by_id[cid]) / std[None, :, None, None]).max()))
        rep["engine_drift_std"] = drift
        ck.add(
            "strict",
            "judge container (py3.11) matches the dev engine",
            drift <= T["engine_drift_std"],
            drift,
            T["engine_drift_std"],
        )
    return ck, rep


# ---------------------------------------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--worktree", action="store_true", help="test the working tree instead of the committed HEAD")
    ap.add_argument("--rebuild", action="store_true", help="rebuild the judge and grader images")
    ap.add_argument("--no-host-engine", action="store_true", help="skip the container-versus-dev comparison")
    ap.add_argument(
        "--source", type=Path, default=None, help=argparse.SUPPRESS
    )  # rehearse another directory (self-test)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = load_config(ROOT / "configs/rehearsal.yaml")
    ecfg = load_config(ROOT / "configs/eval.yaml")
    stats = ROOT / "data/stats.json" if (ROOT / "data/stats.json").exists() else ROOT / "artifacts/stats.json"
    std = np.array(json.loads(stats.read_text())["std"], dtype=np.float32)
    arc = load_archive(load_config(ROOT / "configs/data.yaml"))
    ensure_images(args.rebuild)
    label = f"copy of {args.source}" if args.source else ("working tree" if args.worktree else "git HEAD")

    with tempfile.TemporaryDirectory(prefix="wf-rehearsal-") as tmp:
        tmp = Path(tmp)
        export, work = tmp / "repo", tmp / "work"
        export.mkdir()
        work.mkdir()
        warnings = export_repo(export, args.worktree, args.source)
        for wmsg in warnings:
            log.warning("WARNING: %s", wmsg)
        plan, ctx = build_plan(arc, ecfg, std, cfg["judge"]["ready_s"])
        ctx["clim"] = np.load(ROOT / "artifacts/climatology.npy")
        (work / "plan.json").write_text(json.dumps(plan))
        np.savez(work / "windows.npz", **ctx["arrays"])
        log.info(
            "rehearsal: %d windows, %d calls, %s",
            len(ctx["wins"]),
            len(plan["calls"]),
            label,
        )
        t0 = time.time()
        info = run_containers(export, work, plan, timeout_s=cfg["judge"]["ready_s"] + 8 * len(plan["calls"]) + 300)
        res_file = work / "results.json"
        if not res_file.exists():
            log.error(
                "the grader produced no results (rc %s):\n%s\n--- server log ---\n%s",
                info.get("grader_rc"),
                info.get("grader_stderr"),
                info.get("server_log"),
            )
            return 1
        res = json.loads(res_file.read_text())
        res["_work"] = str(work)
        ck, rep = score(ctx, plan, res, info, cfg, ecfg, std, arc, not args.no_host_engine)
        rep["elapsed_s"] = time.time() - t0

    out = ROOT / "runs/rehearsal"
    out.mkdir(parents=True, exist_ok=True)
    report = {"source": label, "warnings": warnings, "checks": ck.rows, **rep,
              "validator_log": res.get("validator_log", ""), "server_log_tail": info.get("server_log", "")[-2000:]}  # fmt: skip
    (out / "report.json").write_text(json.dumps(report, indent=1, default=str))

    print(f"\nJUDGE REHEARSAL ({report['source']}): {len(plan['calls'])} calls in {rep.get('elapsed_s', 0):.0f} s")
    if "latency_s" in rep:
        print("latency s: " + ", ".join(f"{k} {v:.3f}" for k, v in rep["latency_s"].items()))
    for r in ck.rows:
        mark = "PASS" if r["ok"] else ("FAIL" if r["level"] != "info" else "INFO")
        val = "" if r["value"] is None else f"  {r['value']}"
        lim = "" if r["limit"] is None else f"  (limit {r['limit']})"
        print(f"  [{mark}] {r['level']:6s} {r['check']}{val}{lim}"[:400])
    for wmsg in warnings:
        print("  [WARN] " + wmsg.splitlines()[0])
    if not res.get("ready"):
        print("  server log (last lines):")
        for ln in info.get("server_log", "").strip().splitlines()[-15:]:
            print("    | " + ln)
    print(
        "RESULT:",
        "PASS" if not ck.failed else f"FAIL ({len(ck.failed)} checks)",
        "  report: runs/rehearsal/report.json",
    )
    return 0 if not ck.failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
