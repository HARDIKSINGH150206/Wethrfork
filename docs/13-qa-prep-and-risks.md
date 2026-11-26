# 13. Q&A preparation and risk register

## 1. Judge questions and model answers (each person owns the marked ones)

| # | Question | Answer (under 30 seconds) | Owner |
| --- | --- | --- | --- |
| 1 | Why not a U-Net or transformer? | Those see the whole map in one step, so a shock leaks everywhere on day 1. The judge's checks require 60% of the day-1 response near the shock and no energy beyond 3+8(k+1) cells. Our reach is at most 8 cells a day by construction, and a unit test proves it. | P1 |
| 2 | What exactly is the speed limit? | Advection displacement is capped at 4 cells/day (vector length, smooth tanh cap), bilinear sampling adds 1, three 3x3 convolutions add 3: 8 cells, about 900 km, per day. | P1 |
| 3 | Isn't that too slow for the monsoon jet? | Yes for the core of the low-level jet (12-15 m/s). It is a stated limitation. Most synoptic features move slower, and RMSE skill comes mostly from the blended skill head. | P1 |
| 4 | Your forecast and your counterfactual come from different models? | It's a control forecast plus a perturbation model, as in tangent-linear and ensemble forecasting. The network's own response is added to the best control forecast. They agree closely at short leads; we report the gap. | P2 |
| 5 | How do you know the ripple is right? | Nature runs the experiment: we composite what happened after naturally warm Bay days and compare with our response. Pattern correlation X for rain, Y for pressure. | P1 |
| 6 | How do you prevent drift? | Residual on the last day, unrolled training to 8 steps, input noise, anomalies relative to climatology, damping toward climatology at long leads in the skill head, clamps. | P1 |
| 7 | How do you prevent blur? | The skill head is not smoothed by averaging; damping toward climatology is fitted per lead with a floor on spatial variance. Measured on held-out 2021, day-8 variance ratio per channel (t2m, tp, u10, v10, msl, tcwv): 1.01, 0.68, 0.71, 0.78, 0.85, 0.91; the judge floor is 0.4. | P2 |
| 8 | Heavy rain? | Rain is modelled in log space with triple weight on cells above 10 mm. After the blend we shrink, floor and scale rain per lead, tuned on a per-window points proxy so that false drizzle in dry seasons is not rewarded. CSI skill at 10 mm/day on held-out 2021: 0.075 (day 1: 0.09, day 4: 0.02). | P2 |
| 9 | Is the rain calibration a lookup table? | No: it is 14 triples (shrink, floor, scale), one per lead, fitted once on 2020 with no dates and no per-day entries. We tried a 41-point quantile map per lead and dropped it: it matched rain amounts but inflated variance and lowered RMSE skill. | P2 |
| 10 | Is your evaluation in-sample? | No: network and ridge trained on 2005-2019, calibrations fitted on 2020, graded on 2021. The judge's windows are 2023-2024. | P2 |
| 11 | What happens with my extreme shock? | The OOD meter shows how far outside the training range it is. Validity always holds (clamps). Causality for shocks above 5σ passed X% in our fuzz test. | P2 |
| 12 | Why is a zero shock exact? | The server is deterministic and skips the shocked run when the perturbation is zero, so the difference is exactly 0. | P2 |
| 13 | What's the impact use case? | A state disaster officer forks a shock (for example a warm Bay) and sees how mean rain and temperature change by region and day. We measured forecast error maps on 2021 but do not yet turn them into exceedance probabilities or crop-stress indices; that is the next step. | P3 |
| 14 | Why should a planner trust it? | Every change has a bounded cause region; every shock is audited live; limits are measured, not hidden. | P3 |
| 15 | Does the dashboard use pre-computed results? | No. Every map comes from a live call to our server; turn off Wi-Fi and it still works. | P3 |
| 16 | How long does inference take? | About 0.18 s wall time for 10 days with a shock, including JSON, on 4 CPU threads; the shocked run is batched with the control. | P2 |
| 17 | What would you do with more time? | Higher-resolution grid, learned sub-stepping to model faster jets within the speed limit, transient-amplification regularization, ensemble perturbation model, data assimilation. | P1 |
| 18 | Why 1-degree cells and not districts? | The data is 1 degree (about 110 km). District-level output would be false precision, so impact is by region. | P3 |
| 20 | Your monsoon-stall shock makes it rain MORE on the west coast. Why? | Look at the timing: for the first two days the west coast gets drier (about -0.4 mm/day), then wetter from day 4 (dynamics network: +3.5 mm/day by day 8, 11 of 12 monsoon windows). The data shows the same sequence after naturally weak Arabian Sea flow: rain anomaly -1.4 on day 1, +1.0 on day 5, +1.8 on day 10 (311 cases). That is the break-then-revival cycle of the monsoon, which the model learned. Honest limit: it is a learned correlation, not a proven intervention effect, because a statistical model cannot tell an imposed stall from a natural weak spell. The late response is about twice the observed composite (+3.5 against +1.6 mm/day at day 8): the price of the regulariser that makes every official shock propagate. | P1 |
| 19 | What did each team member build? | P1 model and training, P2 server, calibration and validation, P3 dashboard and brief. | All |
| 20 | Where does the data come from? | ERA5 reanalysis via WeatherBench 2, regridded by the organizers; CC BY 4.0. Never shipped in the repo. | P2 |

## 2. Risk register

| # | Risk | Likelihood | Impact | Early signal | Mitigation | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | Repo-scan flag (date or route string in the wrong file) | Medium | High (up to 8 points) | `make scan` < 15 | CI scan, route and date tests | P2 |
| R2 | Validity failure on a shock call (negative rain, NaN) | Low | Fatal (gate) | fuzz validity < 100% | Clamp last; nan_to_num; fallback to ridge on exception | P2 |
| R3 | Shock fades before day 4 (fails "propagates") | Medium | High (up to 7.5 points) | growth ratio < 3 in gate | Residual-on-last-day, shock augmentation, network-only delta | P1 |
| R4 | Shock leaks on day 1 (fails "localized") | Low | High | near fraction < 0.75 | Architecture limits; light-cone test | P1 |
| R5 | Skill below 12% on 2023-2024 | Medium | Medium (up to 30 points scaled) | 2021 self-grade < 0.12 | Ridge blend, mean-anomaly input, damping, honest grade | P1/P2 |
| R6 | CSI negative at day 4-8 | Medium | Medium | CSI skill < 0 on 2021 | Quantile map with bias taper; fall back to bias 1.0 | P2 |
| R7 | Timeout on judge CPU | Low | Fatal | latency test > 1.5 s | Small model, batch of 2, 4 threads, `torch.inference_mode()` | P2 |
| R8 | Judge machine torch version cannot load weights | Low | Fatal | — | `state_dict` only; avoid new ops; test with an older torch in `make judge` if possible | P2 |
| R9 | Scope overrun | High | Medium | missed gates | Cut order, freeze at T+10 | All |
| R10 | Demo failure (processes, data file) | Medium | High (Stage 2) | rehearsal issues | `make demo`, lab-offline fallback, backup video | P3 |
| R11 | GPU problems on the training laptop | Low | High | CUDA errors in Phase 0 | Model sized to train on CPU in about 1 to 2 hours as fallback | P1 |
| R12 | Arabian Sea box on the west edge reduces outward growth | Medium | Medium | monsoon_stall growth lower in gate | Border padding; check all seasons; tune damping of the delta (none) | P1 |
| R13 | doy convention mismatch | Low | Low | off-by-one in tests | 15-day smoothing makes it negligible; tests pin it | P1 |
| R14 | Repo created before the event | Medium | Disqualification risk | — | Create the GitHub repo (or make the first commit) after the clock starts; confirm with organizers if it already exists | Hardik |
| R15 | Human reviewer reads calibration files as lookup tables | Low | High | — | No dates or per-day entries; one-line explanation in brief and README | P2 |
