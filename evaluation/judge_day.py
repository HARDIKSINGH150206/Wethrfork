"""Judge day: the organisers' Stage 1 scoring and a Stage 2 live session, on weather our model has never seen.

What the judge does, and what this does in the same way:
1. Gets the repo: a fresh `git clone` of our GitHub repo (default), or `--head` / `--worktree` for local code.
2. Runs `python serve.py --port 8000` in `wethrfork-judge:py311`: Python 3.11, allowed libraries only, no kit, no
   network, read-only repo and root filesystem, 4 CPUs, 6 GB (evaluation/judge_rehearsal.py has the details).
3. Sends 8 hidden calls through the kit's own client (5 s deadline, no retries): 5 real windows after 10 Jan 2023 of
   the judge's 5 types, then warm_ocean, monsoon_stall and null on one of them. Our windows are real 2023-24 events
   built with the kit's own hidden-test pipeline (ARCO-ERA5, `monsoon_r1.build_dataset.arco_daily`); the model was
   trained on 2005-2019 and calibrated on 2020-2021, so nothing here was seen in training.
4. Scores with `monsoon_r1.scoring` and `monsoon_r1.repo_scan`: the 100-point table (85 automated, brief 15 human).
   The judge picks one shock window; we score every choice and report the worst. Set B repeats the run on other
   events, to show how much the score moves with the draw.
5. Stage 2: shocks a judge might invent on the spot (land heatwave, cyclone vortex, drying, a downpour, a pressure
   low, a huge amplitude, a corner, one cell, a whisper), sent live to the same server and checked with the kit's
   causality rules on their own boxes.
Also measured: how far the hidden-test source (ARCO-ERA5) is from our training file on days both contain.

    python -m evaluation.judge_day            # fetches about 140 days of ERA5 once (cached in data/blind/)
    python -m evaluation.judge_day --head     # the committed HEAD instead of GitHub
Exit 0 only if every judge gate passes. Report: runs/judge_day/report.json and runs/judge_day/scorecard.md
Needs: docker, the kit, network for the clone and the first fetch (pip install zarr gcsfs).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import tempfile
import time
from pathlib import Path

import numpy as np

from evaluation.judge_rehearsal import ensure_images, export_repo, run_containers, sh
from training.data import ROOT, load_archive, load_config

log = logging.getLogger(__name__)
BLIND = ROOT / "data" / "blind"
OUT = ROOT / "runs" / "judge_day"
TYPES = ("monsoon_onset", "heavy_rain", "heatwave", "cyclone", "winter_disturbance")
LEADS = (0, 3, 7)  # days 1, 4, 8
CH = ("t2m", "tp", "u10", "v10", "msl", "tcwv")
OFFICIAL = {"warm_ocean": "BOX_BAY_OF_BENGAL", "monsoon_stall": "BOX_ARABIAN_SEA"}


def _day(s: str) -> dt.date:
    return dt.date.fromisoformat(str(s))


# ---------------------------------------------------------------------------------------------------------- data
def fetch_days(days: list[dt.date], cache: Path) -> np.ndarray:
    """[D,6,32,36] from ARCO-ERA5 with the kit's own hidden-test pipeline, cached as npz."""
    if cache.exists():
        z = np.load(cache)
        if [int(x) for x in z["dates"]] == [int(f"{d:%Y%m%d}") for d in days]:
            return z["data"]
    from monsoon_r1.build_dataset import arco_daily

    t0 = time.time()
    for attempt in range(3):
        try:
            data = arco_daily(days)
            break
        except Exception as e:  # transient cloud read errors
            log.warning("fetch attempt %d failed: %s", attempt + 1, e)
            time.sleep(5 * (attempt + 1))
    else:
        raise SystemExit(f"cannot fetch {cache.name} from ARCO-ERA5 (network?)")
    data[:, 1] = np.maximum(data[:, 1], 0.0)  # what the kit's merge step does to ERA5 rain
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, data=data, dates=np.array([int(f"{d:%Y%m%d}") for d in days]))
    log.info("fetched %s: %d days in %.0f s", cache.name, len(days), time.time() - t0)
    return data


def load_windows(cfg: dict) -> list[dict]:
    from monsoon_r1 import contract as C

    wins = []
    for set_name, types in cfg["blind_windows"].items():
        for t in TYPES:
            spec = types[t]
            last = _day(spec["last"])
            days = [last + dt.timedelta(days=k) for k in range(-2, 11)]
            x = fetch_days(days, BLIND / f"{set_name}_{t}.npz")
            wins.append({
                "id": f"{set_name}.{t}", "set": set_name, "type": t, "note": spec["note"], "last": last,
                "init": x[:3], "truth": x[3:], "doy": C.doy_sincos(last.timetuple().tm_yday),
            })  # fmt: skip
    return wins


def source_check(cfg: dict, std: np.ndarray) -> dict:
    """Mean |ARCO-ERA5 - training file| per channel on days in both, in channel stds."""
    days = [_day(s) for s in cfg["source_check_days"]]
    arco = fetch_days(days, BLIND / "source_check.npz")
    arc = load_archive(load_config(ROOT / "configs/data.yaml"))
    idx = [int(arc.dates.get_loc(str(d))) for d in days]
    diff = np.abs(arco - arc.data[idx]).mean(axis=(0, 2, 3)) / std
    return {
        "days": len(days),
        "mean_abs_std": dict(zip(CH, diff.round(6).tolist(), strict=True)),
        "max": float(diff.max()),
    }


# ---------------------------------------------------------------------------------------------------------- shocks
def live_shock(spec: dict, last: np.ndarray) -> tuple[np.ndarray, tuple]:
    from monsoon_r1 import contract as C

    box = tuple(float(v) for v in spec["box"])
    m = C.box_mask(box)
    if not m.any():
        raise ValueError(f"box {box} holds no cell centre")
    d = np.zeros((6, 32, 36), "f4")
    if spec["kind"] == "add":
        for ch, v in spec["values"].items():
            d[CH.index(ch)][m] = v
    elif spec["kind"] == "scale":
        for ch, v in spec["values"].items():
            d[CH.index(ch)][m] = v * last[CH.index(ch)][m]
    elif spec["kind"] == "vortex":  # counter-clockwise (northern hemisphere) wind and a pressure low, inside the box
        ii, jj = np.indices(m.shape)
        ci, cj = ii[m].mean(), jj[m].mean()
        rad = max(1.0, min(np.ptp(ii[m]), np.ptp(jj[m])) / 2)
        dy, dx = ii - ci, jj - cj
        r = np.hypot(dx, dy) + 1e-6
        vt = spec["vmax"] * (r / rad) * np.exp(1 - r / rad)
        d[2] = np.where(m, -vt * dy / r, 0)
        d[3] = np.where(m, vt * dx / r, 0)
        d[4] = np.where(m, spec["dp"] * np.exp(-((r / rad) ** 2)), 0)
    else:
        raise ValueError(spec["kind"])
    return d, box


# ---------------------------------------------------------------------------------------------------------- plan
def build_plan(wins: list[dict], cfg: dict, std: np.ndarray, ready_s: float) -> tuple[dict, dict]:
    """The official 8 calls first, in the judge's order, then everything else we score."""
    from monsoon_r1 import scoring as S

    perts: list[np.ndarray] = []
    calls: list[dict] = []
    by_win = {w["id"]: i for i, w in enumerate(wins)}

    def add(cid: str, wid: str, pert: np.ndarray | None) -> None:
        if pert is not None:
            perts.append(pert.astype("f4"))
        calls.append({"id": cid, "win": by_win[wid], "pert": len(perts) - 1 if pert is not None else -1,
                      "enc": "list", "doy": wins[by_win[wid]]["doy"]})  # fmt: skip

    set_a = [w for w in wins if w["set"] == "A"]
    for w in set_a:  # calls 1-5
        add(f"{w['id']}:base", w["id"], None)
    for w in set_a[:1]:  # calls 6-8, on the first window; every other choice follows below
        for name in (*OFFICIAL, "null"):
            add(f"{w['id']}:{name}", w["id"], S.make_shock(name, w["init"][-1], std))
    for w in wins[5:]:
        add(f"{w['id']}:base", w["id"], None)
    for w in wins[1:]:
        for name in (*OFFICIAL, "null"):
            add(f"{w['id']}:{name}", w["id"], S.make_shock(name, w["init"][-1], std))
    live = wins[by_win[cfg["live_window"]]]
    boxes = {}
    for name, spec in cfg["live_shocks"].items():
        d, boxes[name] = live_shock(spec, live["init"][-1])
        add(f"live:{name}", live["id"], d)
    plan = {"ready_limit_s": ready_s, "calls": calls}
    arrays = {"inits": np.stack([w["init"] for w in wins]).astype("f4"), "perts": np.stack(perts)}
    return plan, {"live_boxes": boxes, "live_window": live["id"], "arrays": arrays}


# ---------------------------------------------------------------------------------------------------------- score
def forecast(wins: list[dict], out: dict, clim: np.ndarray) -> dict:
    """The judge's forecast points (RMSE skill 30, CSI 15, anti-blur 10) with the kit, refs from the real dates."""
    from monsoon_r1 import scoring as S
    from monsoon_r1.stats import _doy_index

    ss_w, csi_w, ratios, d4 = [], [], [], []
    per = {}
    for w in wins:
        pred, truth = out[f"{w['id']}:base"], w["truth"]
        persist = np.repeat(w["init"][-1][None], 10, axis=0)
        climr = np.stack([clim[_doy_index(w["last"] + dt.timedelta(days=k))] for k in range(1, 11)])
        i = list(LEADS)
        sk = S.skill_vs_best_ref(pred[i], truth[i], persist[i], climr[i])
        ss = float(np.nanmean(sk["ss"]))
        cs = S.csi_skill(
            S.csi(pred[i, 1], truth[i, 1]), S.csi(persist[i, 1], truth[i, 1]), S.csi(climr[i, 1], truth[i, 1])
        )
        r = S.variance_ratio(pred[7], truth[7])
        p4 = S.skill_vs_best_ref(pred[3:4], truth[3:4], persist[3:4], climr[3:4])["ss_persist"]
        ss_w.append(ss)
        csi_w.append(cs)
        ratios.append(r)
        d4.append(p4)
        per[w["id"]] = {
            "note": w["note"], "mean_ss": ss, "csi_skill": cs, "day4_ss_persist": float(np.nanmean(p4)),
            "heavy_rain_cells": int((truth[i, 1] >= S.RAIN_THRESH).sum()), "max_t2m_C": float(truth[:, 0].max() - 273.15),
        }  # fmt: skip
    fp = S.forecast_points(ss_w, csi_w)
    ratios = np.array(ratios)
    return {
        "rmse_pts": fp["rmse_pts"], "mean_ss": fp["mean_ss"], "csi_pts": fp["csi_pts"], "mean_csi_skill": fp["mean_csi_skill"],
        "blur_pts": S.anti_blur_points(ratios), "blur_ratio": dict(zip(CH, np.nanmean(ratios, axis=0).round(3).tolist(), strict=True)),
        "day4_ss_persist": dict(zip(CH, np.nanmean(np.array(d4), axis=0).round(3).tolist(), strict=True)),
        "day4_beats_persistence": bool(np.nanmean(np.array(d4)) > 0), "windows": per,
    }  # fmt: skip


def causality(wid: str, out: dict, std: np.ndarray) -> dict:
    from monsoon_r1 import contract as C
    from monsoon_r1 import scoring as S

    base = out[f"{wid}:base"]
    r = {n: S.causality_checks(base, out[f"{wid}:{n}"], getattr(C, b), std) for n, b in OFFICIAL.items()}
    null_ok = S.null_consistent(out[f"{wid}:null"], base, std)
    pts = S.causality_points([r["warm_ocean"], r["monsoon_stall"]], null_ok)
    return {"points": pts, "null_ok": null_ok, "null_max_diff": float(np.abs(out[f"{wid}:null"] - base).max()),
            **{n: {k: v for k, v in c.items()} for n, c in r.items()}}  # fmt: skip


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--head", action="store_true", help="test the committed HEAD instead of a GitHub clone")
    src.add_argument("--worktree", action="store_true", help="test the working tree instead of a GitHub clone")
    ap.add_argument("--rebuild", action="store_true", help="rebuild the judge and grader images")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from monsoon_r1 import contract as C
    from monsoon_r1 import repo_scan
    from monsoon_r1 import scoring as S

    cfg = load_config(ROOT / "configs/judge_day.yaml")
    rcfg = load_config(ROOT / "configs/rehearsal.yaml")
    std = np.array(json.loads((ROOT / "artifacts/stats.json").read_text())["std"], dtype=np.float32)
    clim = np.load(ROOT / "artifacts/climatology.npy")
    wins = load_windows(cfg)
    src_gap = source_check(cfg, std)
    ensure_images(args.rebuild)

    with tempfile.TemporaryDirectory(prefix="wf-judgeday-") as tmp:
        tmp = Path(tmp)
        export, work = tmp / "repo", tmp / "work"
        work.mkdir()
        if args.head or args.worktree:
            export.mkdir()
            export_repo(export, args.worktree)
            label = "working tree" if args.worktree else "git HEAD"
        else:
            url = sh(["git", "remote", "get-url", "origin"], cwd=ROOT).stdout.strip()
            r = sh(["git", "clone", "--depth", "1", url, str(export)])
            if r.returncode:
                raise SystemExit(f"cannot clone {url}:\n{r.stderr}")
            commit = sh(["git", "rev-parse", "--short", "HEAD"], cwd=export).stdout.strip()
            label = f"fresh clone of GitHub main @ {commit}"
            sh(["rm", "-rf", str(export / ".git")])  # the scan and the server see files only
        scan = repo_scan.scan(export)
        pdf = export / "brief" / "wethrfork-brief.pdf"
        brief_pages = (
            pdf.read_bytes().count(b"/Type /Page") - pdf.read_bytes().count(b"/Type /Pages") if pdf.exists() else 0
        )

        plan, ctx = build_plan(wins, cfg, std, rcfg["judge"]["ready_s"])
        (work / "plan.json").write_text(json.dumps(plan))
        np.savez(work / "windows.npz", **ctx["arrays"])
        log.info("judge day: %s, %d windows, %d calls", label, len(wins), len(plan["calls"]))
        t0 = time.time()
        info = run_containers(export, work, plan, timeout_s=rcfg["judge"]["ready_s"] + 8 * len(plan["calls"]) + 300)
        if not (work / "results.json").exists():
            log.error(
                "no results (rc %s):\n%s\n%s", info.get("grader_rc"), info.get("grader_stderr"), info.get("server_log")
            )
            return 1
        res = json.loads((work / "results.json").read_text())
        if not res.get("ready"):
            log.error("server never became ready:\n%s", info.get("server_log", "")[-3000:])
            return 1
        rolls = np.load(work / "out.npz")["rollouts"]
        elapsed = time.time() - t0

    calls = res["calls"]
    out = {c["id"]: rolls[n] for n, c in enumerate(plan["calls"])}
    ok = {c["id"]: c["ok"] and not S.validity(out[c["id"]], C.SCORE_STEPS) for c in calls}
    walls = {c["id"]: c["wall_s"] for c in calls}
    official = [c["id"] for c in calls[:8]]
    ready_s = res["ready_epoch"] - info["server_start_epoch"]

    # ---- Stage 1
    fc = {s: forecast([w for w in wins if w["set"] == s], out, clim) for s in ("A", "B")}
    caus = {w["id"]: causality(w["id"], out, std) for w in wins}
    cA = [caus[w["id"]]["points"] for w in wins if w["set"] == "A"]
    cB = [caus[w["id"]]["points"] for w in wins if w["set"] == "B"]
    any_local = any(caus[w["id"]][n]["nonzero"] and caus[w["id"]][n]["localized"] for w in wins[:1] for n in OFFICIAL)

    def total(f: dict, c: float) -> float:
        return f["rmse_pts"] + f["csi_pts"] + f["blur_pts"] + c + scan["points"]

    gates = {
        f"health ready within {rcfg['judge']['ready_s']:.0f} s": (ready_s <= rcfg["judge"]["ready_s"], f"{ready_s:.1f} s"),
        "all 8 official calls: HTTP 200 within 5 s and valid": (all(ok[i] for i in official), f"max {max(walls[i] for i in official):.2f} s"),
        "every other call (all windows, all shocks) valid": (all(ok.values()), f"{sum(ok.values())}/{len(ok)}"),
        "beat persistence at day 4": (fc["A"]["day4_beats_persistence"], f"mean SS {np.mean(list(fc['A']['day4_ss_persist'].values())):.3f}"),
        "non-zero localized response to a shock": (any_local, "official shock window"),
        "server memory under 6 GB, not killed": ((info.get("memory_peak_gb") or 9) <= 6 and not info["oom"], f"{info.get('memory_peak_gb', 0):.2f} GB"),
        "no anti-cheat flag": (scan["anti_cheat_points"] == 8.0, [f["what"] for f in scan["flags"]] or "none"),
    }  # fmt: skip

    # ---- Stage 2
    live = {}
    for name, box in ctx["live_boxes"].items():
        c = S.causality_checks(out[f"{ctx['live_window']}:base"], out[f"live:{name}"], box, std)
        d = out[f"live:{name}"] - out[f"{ctx['live_window']}:base"]
        c["max_z"] = float(np.abs(d / std[None, :, None, None]).max())
        c["valid"], c["wall_s"] = ok[f"live:{name}"], walls[f"live:{name}"]
        c["ok"] = (
            c["valid"]
            and c["wall_s"] <= 5
            and c["finite"]
            and c["nonzero"]
            and c["localized"]
            and c["stable"]
            and c["no_teleport"]
        )
        live[name] = c

    report = {
        "source": label, "elapsed_s": elapsed, "ready_s": ready_s, "memory_peak_gb": info.get("memory_peak_gb"),
        "latency_s": {"official_max": max(walls[i] for i in official), "all_max": max(walls.values()),
                      "p50": float(np.median(list(walls.values())))},
        "gates": {k: {"ok": bool(v[0]), "value": v[1]} for k, v in gates.items()},
        "points": {s: {"rmse": fc[s]["rmse_pts"], "csi": fc[s]["csi_pts"], "blur": fc[s]["blur_pts"],
                       "causality_worst": min(cl), "causality_mean": float(np.mean(cl)),
                       "repo_scan": scan["points"], "automated_worst": total(fc[s], min(cl)), "brief": "human (15)"}
                   for s, cl in (("A", cA), ("B", cB))},
        "forecast": fc, "causality": caus, "live_shocks": live, "repo_scan": scan, "brief_pdf_pages": brief_pages,
        "source_gap": src_gap, "live_window": ctx["live_window"], "validator_rc": res.get("validator_rc"),
    }  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.json").write_text(json.dumps(report, indent=1, default=str))
    md = scorecard(report)
    (OUT / "scorecard.md").write_text(md)
    print(md)
    passed = all(g["ok"] for g in report["gates"].values())
    print("RESULT:", "PASS: every Stage 1 gate holds" if passed else "FAIL: a Stage 1 gate fails", "  runs/judge_day/")
    return 0 if passed else 1


def scorecard(r: dict) -> str:
    P = r["points"]
    L = [f"# Judge day: {r['source']}", "",
         f"Server ready in {r['ready_s']:.1f} s; slowest official call "
         f"{r['latency_s']['official_max']:.2f} s, slowest of all {r['latency_s']['all_max']:.2f} s (limit 5 s); "
         f"peak memory {r['memory_peak_gb']:.2f} GB (limit 6). Kit schema validator exit {r['validator_rc']}.", "",
         "## Stage 1 hard gates", "", "| Gate | Result | Value |", "| --- | --- | --- |"]  # fmt: skip
    L += [f"| {k} | {'PASS' if g['ok'] else '**FAIL**'} | {g['value']} |" for k, g in r["gates"].items()]
    L += ["", "## Points (blind 2023-24 windows)", "",
          "| Part | Max | Set A (official draw) | Set B (second draw) |", "| --- | --- | --- | --- |",
          f"| Forecast RMSE skill | 30 | {P['A']['rmse']:.1f} | {P['B']['rmse']:.1f} |",
          f"| Heavy-rain CSI | 15 | {P['A']['csi']:.1f} | {P['B']['csi']:.1f} |",
          f"| Anti-blur | 10 | {P['A']['blur']:.1f} | {P['B']['blur']:.1f} |",
          f"| Causality (worst shock window) | 15 | {P['A']['causality_worst']:.1f} | {P['B']['causality_worst']:.1f} |",
          f"| Repo scan | 15 | {P['A']['repo_scan']:.1f} | {P['B']['repo_scan']:.1f} |",
          f"| **Automated total** | **85** | **{P['A']['automated_worst']:.1f}** | **{P['B']['automated_worst']:.1f}** |",
          f"| Brief | 15 | human (PDF has {r['brief_pdf_pages']} pages) | |", ""]  # fmt: skip
    fa, fb = r["forecast"]["A"], r["forecast"]["B"]
    L += [f"Mean RMSE skill {fa['mean_ss']:.3f} / {fb['mean_ss']:.3f} (full marks at 0.12); "
          f"CSI skill {fa['mean_csi_skill']:.3f} / {fb['mean_csi_skill']:.3f} (full at 0.10).", "",
          "| Window | Event | RMSE skill | CSI skill | Day-4 vs persistence | Heavy-rain cells | Causality |",
          "| --- | --- | --- | --- | --- | --- | --- |"]  # fmt: skip
    for s in ("A", "B"):
        for wid, v in r["forecast"][s]["windows"].items():
            L.append(f"| {wid} | {v['note']} | {v['mean_ss']:.3f} | {v['csi_skill']:.3f} | {v['day4_ss_persist']:.3f} "
                     f"| {v['heavy_rain_cells']} | {r['causality'][wid]['points']:.1f} |")  # fmt: skip
    L += ["", "Day-8 variance ratio (set A): " + ", ".join(f"{k} {v:.2f}" for k, v in fa["blur_ratio"].items()),
          "", "## Stage 2: shocks invented on the spot", "",
          f"Applied to {r['live_window']}; the kit's causality rules on each shock's own box.", "",
          "| Shock | Valid, < 5 s | Non-zero | Localized (day-1 near) | Stable (max z) | No teleport | Grows | Time |",
          "| --- | --- | --- | --- | --- | --- | --- | --- |"]  # fmt: skip
    for n, c in r["live_shocks"].items():
        y = lambda b: "yes" if b else "**no**"  # noqa: E731
        L.append(f"| {n} | {y(c['valid'] and c['wall_s'] <= 5)} | {y(c['nonzero'])} | {y(c['localized'])} ({c.get('near_frac_day1', 0):.2f}) "
                 f"| {y(c['stable'])} ({c['max_z']:.2f}) | {y(c['no_teleport'])} | {'yes' if c['propagates'] else 'no'} | {c['wall_s']:.2f} s |")  # fmt: skip
    g = r["source_gap"]
    L += ["", "## Hidden-test data source versus our training file", "",
          f"Mean |ARCO-ERA5 - training| on {g['days']} shared days, in channel stds: "
          + ", ".join(f"{k} {v:.5f}" for k, v in g["mean_abs_std"].items()) + f" (max {g['max']:.3f}).", ""]  # fmt: skip
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
