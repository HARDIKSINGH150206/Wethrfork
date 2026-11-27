"""README charts, light and dark, drawn only from measured reports in runs/ (nothing typed in by hand).

    python -m evaluation.readme_figures          # writes docs/images/charts/<name>-light.png and <name>-dark.png

Sources (create them first): runs/selfgrade/latest.json (make selfgrade), runs/rehearsal/report.json (make rehearsal),
runs/locality/summary.json (python -m evaluation.stress_locality), runs/sweep/summary.json (make sweep),
runs/release_check/report.json (make release-check). Palette: categorical slots validated for colour-vision
deficiency and contrast on GitHub's light (#ffffff) and dark (#0d1117) backgrounds.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images" / "charts"
CH = ["t2m", "tp", "u10", "v10", "msl", "tcwv"]
CH_NAME = ["Temperature", "Rain", "Wind u", "Wind v", "Pressure", "Moisture"]

THEMES = {
    "light": {
        "bg": "#ffffff", "text": "#191919", "muted": "#666666", "grid": "#e8e8e8", "axis": "#bdbdbd",
        "series": ["#257de0", "#f47230", "#00b894", "#f2a600", "#ee7fac", "#008a17"],
        "ref": "#8a8a8a", "strict": "#dc3c3d", "track": "#eef2f7",
    },
    "dark": {
        "bg": "#0d1117", "text": "#e6edf3", "muted": "#9198a1", "grid": "#21262d", "axis": "#3d444d",
        "series": ["#338ced", "#e76624", "#00a888", "#d28e05", "#e24d8b", "#0aac23"],
        "ref": "#8b949e", "strict": "#eb6263", "track": "#161b22",
    },
}  # fmt: skip


def load(rel: str) -> dict:
    p = ROOT / rel
    if not p.exists():
        raise SystemExit(f"missing {rel}: run the command named in this module's docstring first")
    return json.loads(p.read_text())


def frame(t: dict, title: str, subtitle: str, size=(8.0, 4.2)):
    fig, ax = plt.subplots(figsize=size, dpi=170)
    fig.patch.set_facecolor(t["bg"])
    ax.set_facecolor(t["bg"])
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(t["axis"])
    ax.tick_params(colors=t["muted"], labelsize=9, length=0, pad=6)
    ax.grid(axis="y", color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)
    fig.text(0.015, 0.965, title, ha="left", va="top", fontsize=13, fontweight="bold", color=t["text"])
    fig.text(0.015, 0.895, subtitle, ha="left", va="top", fontsize=9.2, color=t["muted"])
    fig.subplots_adjust(left=0.08, right=0.97, top=0.78, bottom=0.14)
    return fig, ax


def ref_line(ax, t: dict, y: float, label: str, strict: bool = False, outside: bool = False) -> None:
    c = t["strict"] if strict else t["ref"]
    ax.axhline(y, color=c, linewidth=1.2, linestyle=(0, (4, 3)), zorder=1)
    if outside:  # to the right of the plot, clear of the bars
        ax.annotate(label, (1.0, y), xycoords=("axes fraction", "data"), xytext=(6, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=8.5, color=c, annotation_clip=False)  # fmt: skip
    else:
        ax.annotate(label, (1.0, y), xycoords=("axes fraction", "data"), xytext=(-4, 4), textcoords="offset points",
                    ha="right", va="bottom", fontsize=8.5, color=c)  # fmt: skip


def save(fig, name: str, theme: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}-{theme}.png", facecolor=fig.get_facecolor())
    plt.close(fig)


# ------------------------------------------------------------------------------------------------------- charts
def skill_by_lead(t: dict, sg: dict) -> plt.Figure:
    s = sg["systematic"]["ss_by_lead_channel"]
    leads = [1, 4, 8]
    fig, ax = frame(
        t,
        "Forecast skill by lead day",
        "1 − RMSE ÷ best of persistence and climatology, 71 windows of 2021, shipped model. Above 0 beats both.",
    )
    for c in range(6):
        ys = [s[str(k)][c] for k in leads]
        ax.plot(
            leads,
            ys,
            color=t["series"][c],
            linewidth=2,
            marker="o",
            markersize=6.5,
            markeredgecolor=t["bg"],
            markeredgewidth=1.5,
            label=CH_NAME[c],
            zorder=3,
        )
    ax.axhline(0, color=t["axis"], linewidth=1)
    ax.set_xticks(leads, [f"Day {k}" for k in leads])
    ax.set_xlim(0.6, 8.4)
    ax.legend(
        ncol=6,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        frameon=False,
        fontsize=8.6,
        labelcolor=t["text"],
        handlelength=1.6,
        columnspacing=1.2,
    )
    ax.set_ylabel("skill", color=t["muted"], fontsize=9)
    return fig


def bars(t: dict, values, labels, title, subtitle, fmt="{:.2f}", ylim=None, refs=(), color=None) -> plt.Figure:
    fig, ax = frame(t, title, subtitle)
    x = np.arange(len(values))
    ax.bar(x, values, width=0.58, color=color or t["series"][0], zorder=2)
    for xi, v in zip(x, values, strict=True):
        ax.annotate(
            fmt.format(v),
            (xi, v),
            xytext=(0, 4 if v >= 0 else -12),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color=t["text"],
        )
    for y, lab, strict in refs:
        ref_line(ax, t, y, lab, strict, outside=True)
    if refs:
        fig.subplots_adjust(right=0.84)
    ax.axhline(0, color=t["axis"], linewidth=1)
    ax.set_xticks(x, labels)
    ax.tick_params(axis="x", colors=t["text"])
    if ylim:
        ax.set_ylim(*ylim)
    return fig


def causality(t: dict, rep: dict, key: str, title: str, subtitle: str, refs, log=False, ylim=None) -> plt.Figure:
    c = rep["causality"]
    wins = list(c)
    fig, ax = frame(t, title, subtitle, size=(8.0, 4.0))
    x = np.arange(len(wins))
    for k, (shock, lab) in enumerate(
        (("warm_ocean", "Warm ocean (Bay of Bengal)"), ("monsoon_stall", "Monsoon stall (Arabian Sea)"))
    ):
        ys = [c[w][shock][key] for w in wins]
        ax.plot(
            x + (k - 0.5) * 0.18,
            ys,
            linestyle="none",
            marker="o",
            markersize=8,
            color=t["series"][k],
            markeredgecolor=t["bg"],
            markeredgewidth=1.5,
            label=lab,
            zorder=3,
        )
    for y, lab, strict in refs:
        ref_line(ax, t, y, lab, strict)
    if log:
        ax.set_yscale("log")
    if ylim:
        ax.set_ylim(*ylim)
    pretty = {"monsoon_onset": "monsoon\nonset", "heavy_rain": "heavy\nrain", "heatwave": "heat-\nwave", "cyclone": "cyclone\n(Arabian)",
              "cyclone_alt": "cyclone\n(Bay)", "winter_disturbance": "winter\ndisturb."}  # fmt: skip
    names = [pretty.get(w, f"{w}\nseason") for w in wins]
    ax.set_xticks(x, names, rotation=0, fontsize=8)
    ax.tick_params(axis="x", colors=t["text"])
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False, fontsize=8.6, labelcolor=t["text"], ncol=2)
    fig.subplots_adjust(top=0.74, bottom=0.17)
    return fig


def headroom(t: dict, rep: dict) -> plt.Figure:
    rows = [
        ("Ready after cold start", rep["ready_s"], 120.0, "s"),
        ("Slowest forecast call", rep["latency_s"]["max"], 5.0, "s"),
        (
            "Peak memory",
            next(r["value"] for r in rep["checks"] if r["check"].startswith("server memory peak")),
            6.0,
            "GB",
        ),
    ]
    fig, ax = frame(
        t,
        "Headroom against the judge's limits",
        "Measured in the judge-like container (no network, read-only, 4 CPUs, 6 GB, Python 3.11). Bar = share of the limit used.",
        size=(8.0, 3.2),
    )
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=t["grid"], linewidth=0.8)
    y = np.arange(len(rows))[::-1]
    for yi, (_lab, v, lim, unit) in zip(y, rows, strict=True):
        ax.barh(yi, 100, height=0.5, color=t["track"], zorder=1)
        ax.barh(yi, max(v / lim * 100, 0.6), height=0.5, color=t["series"][0], zorder=2)
        ax.annotate(
            f"{v:.2f} {unit} of {lim:g} {unit}  ({v / lim * 100:.1f} %)",
            (v / lim * 100, yi),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
            color=t["text"],
        )
    ax.set_yticks(y, [r[0] for r in rows])
    ax.tick_params(axis="y", colors=t["text"])
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100], ["0 %", "25 %", "50 %", "75 %", "100 %"])
    fig.subplots_adjust(left=0.24, top=0.72, bottom=0.17)
    return fig


def score(t: dict, rep: dict, sweep_pts: float, scan_pts: float) -> plt.Figure:
    f = rep["forecast_systematic"]
    rows = [
        ("Forecast RMSE skill", f["rmse_pts"], 30), ("Heavy-rain CSI skill", f["csi_pts"], 15),
        ("Anti-blur", f["blur_pts"], 10), ("Perturbation causality", sweep_pts, 15), ("Repo scan", scan_pts, 15),
    ]  # fmt: skip
    got = sum(r[1] for r in rows)
    fig, ax = frame(
        t,
        f"Estimated automated score: {got:.1f} of 85",
        "Kit scoring, shipped model on 2021 (causality: all 71 windows). The brief (15 points) is read by a person.",
        size=(8.0, 3.6),
    )
    ax.grid(axis="y", visible=False)
    y = np.arange(len(rows))[::-1]
    for yi, (_lab, v, mx) in zip(y, rows, strict=True):
        ax.barh(yi, mx, height=0.52, color=t["track"], zorder=1)
        ax.barh(yi, v, height=0.52, color=t["series"][0] if v >= mx - 1e-6 else t["series"][1], zorder=2)
        ax.annotate(
            f"{v:.1f} / {mx}",
            (mx, yi),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
            color=t["text"],
        )
    ax.set_yticks(y, [r[0] for r in rows])
    ax.tick_params(axis="y", colors=t["text"])
    ax.set_xlim(0, 36)
    ax.set_xticks([0, 10, 20, 30], ["0", "10", "20", "30 points"])
    ax.grid(axis="x", color=t["grid"], linewidth=0.8)
    fig.subplots_adjust(left=0.24, top=0.74, bottom=0.14)
    return fig


def light_cone(t: dict, loc: dict) -> plt.Figure:
    days = np.arange(1, len(loc["max_reach"]) + 1)
    fig, ax = frame(
        t,
        "The speed limit, measured",
        f"Farthest cell changed by {loc['n']} random shocks (full served formula). Change beyond the limit: {loc['worst_outside_std']:.1f} std.",
    )
    ax.plot(
        days,
        loc["limit"],
        color=t["strict"],
        linewidth=2,
        linestyle=(0, (4, 3)),
        label="Limit: 8 cells (≈ 900 km) per day",
    )
    ax.plot(
        days,
        loc["max_reach"],
        color=t["series"][0],
        linewidth=2,
        marker="o",
        markersize=6.5,
        markeredgecolor=t["bg"],
        markeredgewidth=1.5,
        label="Measured farthest change",
    )
    ax.axhline(35, color=t["ref"], linewidth=1, linestyle=":")
    ax.annotate(
        "grid edge (36 cells wide)",
        (1.0, 35),
        xycoords=("axes fraction", "data"),
        xytext=(-4, -12),
        textcoords="offset points",
        ha="right",
        fontsize=8.5,
        color=t["ref"],
    )
    ax.set_xticks(days, [f"{d}" for d in days])
    ax.set_xlabel("forecast day", color=t["muted"], fontsize=9)
    ax.set_ylabel("cells from the shock", color=t["muted"], fontsize=9)
    ax.set_ylim(0, 84)
    ax.legend(loc="upper left", frameon=False, fontsize=8.8, labelcolor=t["text"])
    return fig


def main() -> int:
    sg = load("runs/selfgrade/latest.json")
    rep = load("runs/rehearsal/report.json")
    loc = load("runs/locality/summary.json")
    sweep = load("runs/sweep/summary.json")
    rc = load("runs/release_check/report.json")
    if rep["source"] not in ("git HEAD", "working tree") or not all(r["ok"] for r in rep["checks"]):
        raise SystemExit("runs/rehearsal/report.json is not a passing run on this repo: re-run make rehearsal")
    scan = next(s for s in rc["steps"] if s["step"] == "scan")
    if scan["status"] != "PASS":
        raise SystemExit("the last release check did not pass the repo scan: re-run make release-check")
    scan_pts = 15.0  # the scan step passes only at 15 / 15 with no flags (evaluation/scan_repo.py)
    f = rep["forecast_systematic"]
    for theme, t in THEMES.items():
        plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": t["text"]})
        save(skill_by_lead(t, sg), "skill-by-lead", theme)
        save(bars(t, f["day4_ss_persist"], CH_NAME, "Day-4 skill against persistence (the judge's hard gate)",
                  "1 − RMSE ÷ RMSE of repeating the last day, 2021, shipped model. Every channel must stay above 0.",
                  ylim=(0, max(f["day4_ss_persist"]) * 1.25)), "day4-vs-persistence", theme)  # fmt: skip
        save(bars(t, f["blur_ratio"], CH_NAME, "Day-8 variance ratio (anti-blur)",
                  "Spatial variance of the day-8 forecast ÷ that of reality. Full points from 0.4 to 2.5; our gate is 0.5 to 2.0.",
                  ylim=(0, 1.3), refs=((0.4, "judge minimum 0.4", False), (0.5, "our minimum 0.5", True))), "variance-ratio", theme)  # fmt: skip
        save(causality(t, rep, "near_frac_day1", "Day 1: the response stays near the shock",
                       "Share of day-1 response energy within 3 cells of the box, both official shocks, 10 windows.",
                       refs=((0.60, "judge 0.60", False), (0.75, "our gate 0.75", True)), ylim=(0.5, 1.03)), "causality-near", theme)  # fmt: skip
        save(causality(t, rep, "growth_ratio", "Days 4 to 8: the response spreads outward",
                       "Energy outside the neighbourhood on days 4-8 ÷ day 1 (log scale), both official shocks, 10 windows.",
                       refs=((1.5, "judge 1.5", False), (3.0, "our gate 3", True)), log=True, ylim=(1, 1e4)), "causality-growth", theme)  # fmt: skip
        save(headroom(t, rep), "headroom", theme)
        save(score(t, rep, sweep["points_min"], scan_pts), "score", theme)
        save(light_cone(t, loc), "light-cone", theme)
    for p in sorted(OUT.glob("*.png")):
        print(p.relative_to(ROOT), f"{p.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
