# PRD: Wethrfork, the monsoon toolkit

| Field | Value |
| --- | --- |
| Product | Wethrfork |
| Tagline | A weather model with a speed limit |
| Event | Yugaantar DevForge, Track 2 "Multiverse of Monsoon" (inspired by ISRO Bharatiya Antariksh Hackathon PS-5, "AI-Powered Digital Twin of India's Climate") |
| Team | 3 people (P1 Model, P2 Server + science, P3 Dashboard + story) |
| Build window | 12 hours |
| Hardware | One RTX 4050 laptop GPU (6 GB VRAM) for training; judging is CPU only |
| Goal | First prize |
| Status of this document | Final plan, frozen after three enhance-and-critique rounds |

---

## 1. Problem

Weather apps answer "will it rain tomorrow?". A Climate Digital Twin answers "how does India's atmosphere evolve,
and what happens in an alternate universe if we change the starting conditions?" The track asks for a fast,
physics-aware twin that:

1. **Simulates (Timeline Prime)**: from the last 3 days of India's state (temperature, rain, wind, pressure,
   moisture), rolls the weather forward day by day without exploding into NaNs or blurring into a flat average.
2. **Branches (Multiverse)**: accepts a localized shock (a hotter Bay of Bengal, a weaker monsoon wind) and shows how
   it ripples across India.
3. **Matters**: drives an interactive map dashboard and an impact extension (crop stress, solar and wind, heatwave or
   flood risk, ensemble uncertainty, or a policy co-pilot), live from the team's own simulation.

No starter model or weights are given. The kit's placeholder server repeats the last day and scores zero by design.

## 2. Users and jobs to be done

| User | Job | What Wethrfork gives them |
| --- | --- | --- |
| Automated judge (Stage 1) | Score skill, dynamics, repo integrity | A server designed to pass the judge's checks, verified by running the judge's own code on every held-out window |
| Desk-review judge (Stage 2) | Apply a new shock live, probe design and limits | A shock composer, a fork view, and a live limits verdict that runs the official causality checks on their shock |
| Finals panel (Round 3) | Decide which twin is most credible and useful | A clear identity (speed limit), scientific validation (natural experiment), honest limits (fuzz heatmap), an impact story |
| State disaster officer (impact persona) | "Which regions, what risk, by when?" | An impact card showing how a shock shifts the probability of heavy rain and heatwave temperatures by region and lead day |
| Agricultural planner (secondary persona) | "Will a stalled monsoon stress kharif crops?" | A crop-stress indicator from rain deficit and heat over cropland cells |

## 3. Goals and non-goals

### Goals
- G1. Pass the Round 2 hard gate with margin: valid output on all 8 calls, beat persistence at day 4, a localized
  response to both shocks.
- G2. Score as close to 85 of the 85 automated points as possible (45 skill, 25 dynamics, 15 repo), and earn a strong
  brief score (15).
- G3. Win the live desk review: any judge shock answered in under 3 seconds, with a self-audit on screen.
- G4. Present a finals story no other team can tell: a tested locality bound, natural-experiment validation, measured limits.

### Non-goals
- Global or high-resolution forecasting. The grid is fixed at 1 degree over India.
- Hourly output, data assimilation, or any live data feed.
- Large foundation models (Aurora, WeatherNext, Earth2Studio pipelines). Weights must be trained during the event and
  must run on 4 CPU cores in under 5 s.
- LLM features. The policy text, if any, is templated from model numbers.
- District-level products. One grid cell is about 110 km; district precision would be false precision.

## 4. Scope

### 4.1 MVP (must ship; together these pass Stage 1 and survive the demo)
1. `serve.py` serving the blended model (ridge + network) with the speed limit and output clamps, passing the kit
   validator and the repo scan at 15/15.
2. Causality, zero-shock and validity gates passing in every season on our self-grade.
3. Dashboard: map, shock composer, fork view (normal versus shocked, side by side), driven live by our `/simulate`.
4. One impact card.
5. The 2-page brief.

### 4.2 Differentiators (win first place; each can be cut without failing)
In cut order from last to first (cut 8 first):
1. **Speed-limit identity**: light-cone unit test and heatmap, ring drawn on every fork map.
2. **Fork view** with full delta, stippled where it exceeds typical forecast error.
3. **Shock composer** with presets: warm ocean, monsoon stall, plant a cyclone (with drawn track).
4. **Live limits verdict**: kit causality checks on the judge's shock, out-of-distribution meter, fuzz pass rate.
5. **Natural-experiment validation**: our warm-Bay response versus observed composites.
6. **Shock fuzz test**: about 60 random shocks, validity and causality, pass-rate heatmap.
7. **Impact card**: exceedance-probability shifts by region; kharif crop stress.
8. **Sensitivity click**: where a city's rain comes from 5 days out.

### 4.3 Explicitly cut (decided; do not re-add during the event)
Inverse twin (gradient search for the smallest shock causing an outcome), historical event replay (2018 Kerala floods),
365-day free run, monsoon onset and break-spell analytics, district rankings, action playbook, client-side ensembles,
variance-matching loss, final refit on all years, U-Net or attention architectures.

## 5. Functional requirements

| ID | Requirement | Acceptance |
| --- | --- | --- |
| F1 | `POST /health` returns ready only after artifacts load and a warm-up rollout runs | Validator health OK; ready within 30 s of start |
| F2 | `POST /simulate` accepts the contract input and returns `[steps,6,32,36]` | Validator passes in both wire formats |
| F3 | Shock added to the last input day exactly as given | Unit test compares to manual addition |
| F4 | Zero or null shock gives identical output | Max difference exactly 0.0 |
| F5 | Output validity | No NaN/Inf, tp and tcwv at least 0, t2m in range on 100% of fuzz shocks |
| F6 | Latency | 10 steps under 1.5 s on 4 threads, p95 over 20 calls |
| F7 | Causality | Per season: day-1 near fraction at least 0.75, outward growth at least 3x, max z at most 5 |
| F8 | Skill | Out-of-sample 2021 self-grade: mean RMSE skill at least 0.12 versus the better reference, CSI skill above 0 |
| F9 | Anti-blur | Day-8 variance ratio between 0.5 and 2.0 for every channel |
| F10 | Dashboard live coupling | Every map frame comes from a live `/simulate` call |
| F11 | Fork view | Two or more universes side by side, synced day scrubber, delta map |
| F12 | Shock composer | Box or Gaussian shocks on any channel; presets; physically consistent option |
| F13 | Limits verdict | Shows the four kit checks plus near fraction, far fraction, OOD meter, fuzz pass rate, within 3 s |
| F14 | Impact card | Regional exceedance-probability change for heavy rain and heat; crop stress |
| F15 | Offline demo | Works with Wi-Fi off: no CDN, no tiles, no fonts fetched |
| F16 | Brief | Two pages, PDF, page 1 model, drift and blur, failure modes; page 2 visualization and impact |

## 6. Non-functional requirements

- Determinism: identical inputs give identical outputs across calls and restarts.
- Memory: server resident set below 1.5 GB (judge limit 6 GB).
- Startup: ready within 30 s (judge waits 120 s).
- Repo size: under 200 MB including weights (limit 2 GB with LFS; we expect a few tens of MB).
- Reproducibility: `make artifacts` rebuilds every artifact from the netCDF with fixed seeds.
- Code health: training pipeline, separate server and UI, frontend, README, checkpoint all detectable by the scan.

## 7. Success metrics

| Metric | Target | Stretch |
| --- | --- | --- |
| Stage 1 automated points (out of 85) | 70 | 80+ |
| Mean RMSE skill vs better reference (2021, days 1/4/8) | 0.12 | 0.18 |
| Heavy-rain CSI skill | 0.05 | 0.10 |
| Anti-blur points | 10/10 | 10/10 |
| Causality points | 15/15 | 15/15 |
| Repo scan | 15/15 | 15/15 |
| Fuzz validity | 100% | 100% |
| Fuzz causality pass rate (localized + propagates) | 80% | 95% |
| Live shock round trip in dashboard | under 3 s | under 1.5 s |

## 8. Risks (top five; full list in `docs/13-qa-prep-and-risks.md`)

1. Forecast skill on 2023-2024 windows lower than on 2021 (distribution shift, warmer years). Mitigation: ridge
   baseline, 3-day mean anomaly input, out-of-sample self-grade, conservative long-lead damping.
2. A repo-scan flag from a stray date or route string. Mitigation: CI scan on every push.
3. The shock fades before day 4 and fails "propagates". Mitigation: residual-on-last-day design, per-season gate.
4. Scope overrun. Mitigation: fixed cut order, feature freeze at hour 10.
5. Demo failure (two processes, local data). Mitigation: `make demo`, offline assets, lab-offline fallback, recorded video.

## 9. Timeline

12 hours, 4 gates (hour 2 scan and validator, hour 3 v0.1, hour 5 full model passes gates, hour 10 freeze), submit by
hour 11:30. See `docs/PHASES.md` and `docs/07-build-plan-12h.md`.
