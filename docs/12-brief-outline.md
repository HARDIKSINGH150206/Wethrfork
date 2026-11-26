# 12. The 2-page brief

15 points, read by a person, and the first thing desk reviewers and finalists' judges see. Exactly two pages, A4 or
Letter, PDF. Required structure from the track: **page 1** model design, how we prevent drift and blur, failure modes;
**page 2** visualization and the impact use case. The universal requirements also ask for USP, system architecture and
technical approach. Sources: `brief/brief.md` (or `brief/brief.typ`), figures in `brief/figures/`.

---

## Page 1: "A weather model with a speed limit"

**Title block** (2 lines): Wethrfork, the monsoon toolkit · team name · repo URL.

**USP (2 sentences)**: Wethrfork is a Climate Digital Twin of India whose shock responses are locally bounded by design:
the network cannot move a change more than 8 grid cells along either axis (about 900 km) per simulated day. It forecasts beyond both persistence and
climatology on held-out data and audits every shock live with the organizers' own causality checks.

**Panel A: architecture (small diagram, about 1/4 page)**
```
3 days (6 ch) ─► anomalies vs climatology ─┬─► Network: bounded advection (≤4 cells/day) + local CNN (≤4) ─┐
                                           │                                                               ├─► Blend ─► Post-processor ─► + shock delta (network only) ─► clamp
                                           └─► Ridge (per cell, per lead) ─────────────────────────────────┘
```
One line under it: "Skill head for the forecast, dynamics head for the counterfactual: a control forecast plus a
perturbation model."

**Panel B: the contract table (the heart of page 1)**
| Judge criterion | Architectural guarantee | Measured evidence (2021, out-of-sample) |
| --- | --- | --- |
| Shocks local, then spreading, never teleporting | Reach ≤ 8 cells/step (advection cap 4 + bilinear 1 + three 3x3 convs) | Light-cone test; near fraction day 1 = X; growth ratio = Y, all seasons |
| Zero shock changes nothing | Deterministic server; zero shock skips the shocked run | Max difference 0.0 |
| No NaN, rain ≥ 0, bounded t2m | Final clamp after the delta | 100% validity over N fuzz shocks |
| Beat persistence and climatology | Ridge + network blend, calibrated per lead | Mean skill X (days 1/4/8) |
| Heavy rain | Log-space rain, wet-cell weighting, per-lead quantile map | CSI skill Y at 10 mm/day |
| No blur | Residual dynamics; damping floor keeps day-8 variance ≥ 50% | Variance ratio by channel at day 8 |
| Fast, offline | ~1M parameters, CPU, 4 threads | 10 steps in Z ms |

**Panel C: drift and blur (figure, about 1/5 page)**: variance ratio and RMSE versus lead day for t2m and tp, model
against persistence and climatology.

**Panel D: failure modes (4 bullets + fuzz heatmap thumbnail)**
- Jet transport: the Arabian Sea low-level jet (12-15 m/s) exceeds our 4 cells/day advection cap.
- Cyclones: 1° daily fields cannot hold a cyclone core; planted vortices fill in about 3 days.
- Domain edges: energy that leaves the grid is lost; shocks on the edge propagate less.
- Extremes: shocks above 5σ of local variability pass causality in only X% of fuzz cases; validity always holds.
- Long leads: beyond day 8 the skill head is close to climatology (by design).

## Page 2: "A multiverse you can trust, for people who need it"

**Panel E: dashboard screenshot (about 1/3 page)**: Fork view with control, shocked and delta maps, ring, stippling,
limits verdict panel visible. Callouts: (1) shock composer, (2) speed-limit ring, (3) stippling = beyond forecast
error, (4) live verdict with the official checks.

**Panel F: natural-experiment validation (figure)**: observed composite after naturally warm Bay of Bengal days versus
our warm_ocean response (tp and msl at day 2), pattern correlation, number of events.

**Panel G: impact use case (text + small table)**: a state disaster officer's view of a warm Bay shock: change in the
probability of heavy rain (≥ 35 and ≥ 64.5 mm/day) and of heat by region and day, using our measured forecast error.
Example table with 4 regions. Second use case in 2 lines: kharif crop stress under monsoon stall.

**Panel H: engineering (5 bullets)**: offline, CPU, deterministic; repo scan 15/15 verified in CI; calibrations fitted on
2020 and graded on 2021; data never shipped; everything reproducible with `make artifacts`.

**Footer**: data credit (ERA5 via WeatherBench 2, CC BY 4.0), related work (Learning to Advect), honest limitations
line.

## Writing rules
- Numbers, not adjectives. Every claim on page 1 has a number from `docs/STATUS.md`.
- Figures at least 8 pt text; consistent colours with the dashboard.
- No calendar dates of test windows in the brief beyond "2021 (held out)".
- Final check: open the PDF, confirm exactly 2 pages, fonts embedded, links work.

## Figure production
| Figure | Script | Output |
| --- | --- | --- |
| Light cone | `evaluation/report.py --fig lightcone` | `brief/figures/lightcone.png` |
| Variance and RMSE by lead | `evaluation/report.py --fig leads` | `brief/figures/leads.png` |
| Fuzz heatmap | `evaluation/report.py --fig fuzz` | `brief/figures/fuzz.png` |
| Natural experiment | `evaluation/report.py --fig natural` | `brief/figures/natural.png` |
| Dashboard screenshot | manual (P3) | `brief/figures/dashboard.png` |
