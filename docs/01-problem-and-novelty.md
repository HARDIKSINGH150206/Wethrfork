# 01. Problem and novelty

## 1. The official problem (Track 2, "Multiverse of Monsoon")

**Domain**: Earth-system modelling, spatiotemporal deep learning, climate simulation.
**Environment**: the provided Indian climate dataset (`india_climate_train.nc`, 2005-2021 daily, 32 x 36 grid) and an
offline inference server (`serve.py`).
**Team kit**: `yug-monsoon-kit` (data, API contract, validator and starter server on its Releases page, tag v1.0.0).
**Inspired by**: ISRO's Bharatiya Antariksh Hackathon PS-5, "AI-Powered Digital Twin of India's Climate".

### Mission brief (paraphrased from the track)
Weather apps answer "Will it rain tomorrow?". A Climate Digital Twin answers "How does India's atmosphere evolve,
and what happens in an alternate universe if we change the starting conditions?" Build a fast, physics-aware twin that:
1. **Simulates (Timeline Prime)**: from the last 3 days of India's state, roll forward day by day without exploding or
   blurring into a flat average.
2. **Branches (Multiverse)**: accept a localized shock (a hotter Bay of Bengal, a weaker monsoon wind) and show how it
   ripples across India.

No starter model or baseline weights are provided. The starter `serve.py` only handles the API; its placeholder repeats
the last day and scores zero by design. Passing the automated benchmark only gets a team to the desk review. There,
teams demo the full system: the engine, an interactive map dashboard, and a scientific or social-impact extension
(for example crop stress under a stalled monsoon, solar or wind generation, heatwave or flood risk, ensemble
uncertainty, or a policy co-pilot).

### What the organizers say they look for
- **Stable rollouts**: 10 steps or more with no NaN or Inf, rain never negative, no collapse into blurry averages.
- **Real weather skill**: beat "repeat yesterday" and climatology, including heavy rain.
- **Causal shocks**: a shock stays near where it was applied at first, then spreads outward. A zero shock changes nothing.
- **Real impact**: a dashboard and impact module driven live by the team's own simulation.

### Submission
- Public GitHub repo: training code and `serve.py` at the root; model weights inside the repo (Git LFS fine, under
  2 GB; nothing is downloaded at evaluation, so a Hugging Face link alone is not enough); dashboard code separate from
  the server code; a README on how to train and run.
- 2-page brief (PDF): page 1 model design, how drift and blur are prevented, failure modes; page 2 visualization and
  the impact use case.

### Offline run
Organizers run `python serve.py --port 8000` in a sandbox: no internet, 6 GB RAM, 4 CPU cores, no GPU, read-only repo
(write only to `/tmp`). Available libraries: torch (CPU), numpy, scipy, pandas, xarray, scikit-learn, lightgbm,
onnxruntime, fastapi, flask, uvicorn (and gunicorn per the contract). Anything else must be inside the repo.

### Ground rules
- Offline only; no external weather APIs or internet at inference.
- No lookup tricks: hardcoded dates, lookup tables or shipped archives of past weather fail the shock tests and the repo
  scan, and lead to disqualification.
- Real coupling: the dashboard must run on live output from our own `/simulate`, not pre-rendered results.
- Frozen at the deadline.
- Original work: repo, training, weights and dashboard are built during the hackathon. Open-source libraries are fine.

### Universal hackathon structure
All tracks submit a public repo and a 2-page brief. Stage 1 is an automated test suite plus code and artifact checks
(top 10 per track advance). Stage 2 is a desk review with a live demo and technical questions (top 2 advance). Round 3
is final judging before the official panel.

## 2. Why this problem is hard

| Difficulty | Why | What most teams will do | What we do |
| --- | --- | --- | --- |
| Error accumulation | Autoregressive models feed on their own errors; small biases compound into drift or NaNs | Train single-step MSE and hope | Residual on the last day, unrolled training (4 then 8 steps), noise injection, clamps |
| Blur | MSE-optimal forecasts converge to the conditional mean, which is smooth | Ignore, or add noise (punished above 2.5x variance) | Damp only where RMSE gains; rain quantile mapping restores intensity; variance floor 0.5 |
| Heavy rain | Rare, intense, spatially patchy; MSE under-predicts it | Report RMSE only | CSI-targeted rain calibration per lead |
| Causal shocks | Global layers spread a shock everywhere instantly; damping kills it | U-Nets, transformers, global normalization | A provably local architecture with a speed limit |
| Zero shock | Any randomness in the server breaks equality | Ensembles inside the server | Deterministic server; zero shock skips the shocked run |
| CPU, 5 s | Big models are slow on 4 cores | Large networks that time out | About 1 million parameters, under 1 s for 10 steps |
| Repo scan traps | The scanner seeds on any Python file containing the route string | Tests and clients with dates | Route only in `serve.py`, dates only in YAML, CI scan |
| Distribution shift | Judge windows are 2023-2024, warmer than training | Train and test on random splits | Year-based splits, out-of-sample 2021 grade, mean-anomaly input |

## 3. Our novelty

### 3.1 The headline: "a weather model with a speed limit"
Most data-driven weather models can move information anywhere in one step. Ours cannot. Each simulated day, a change
can travel at most 8 grid cells (about 900 km): 4 cells of bounded advection along the learned flow, plus 4 cells of
local mixing (bilinear sampling and three 3x3 convolutions). We check it with a light-cone unit test that perturbs a
single cell and measures, with the judge's own distance metric, where the gradient becomes nonzero.

Why it matters:
- **For scoring**: the automated causality checks (localized on day 1, outward spread by days 4-8, nothing beyond
  `3 + 8(k+1)` cells) are designed to pass, and we check that on every held-out window rather than assuming it.
- **For trust**: a planner using the twin needs to know a forecast change in Delhi was not caused by a numerical
  artefact in the Bay of Bengal. Our model can say "this could only have come from within 900 km per day of here".
- **For the story**: one sentence that a judge remembers.

### 3.2 A twin that audits itself, live
When a judge composes any shock, the dashboard calls the lab server, which runs the official kit `causality_checks`
on that exact shock and shows four ticks (non-zero, localized, propagates, stable), the day-1 near fraction, the far
fraction, an out-of-distribution meter, and the pass rate of similar shocks in our fuzz test. Judges see the answer to
"how do you know it's right?" before they ask.

### 3.3 Validation against natural experiments
A shock has no ground truth: nobody can warm the Bay of Bengal by 3 K and watch. But nature runs similar experiments.
We find days in 2005-2021 when the Bay of Bengal was anomalously warm, average what actually happened in the following
days (a composite), and compare it with our model's warm_ocean response. Pattern correlation turns "trust us" into
evidence.

### 3.4 Measured limits, not hidden ones
A shock fuzz test runs about 60 random shocks (boxes anywhere, every channel, extreme amplitudes, every season)
through validity and causality checks. The pass-rate heatmap is page 1's failure-modes panel and the limits panel's
data. Example of an honest limit: "the Arabian Sea low-level jet is faster than our speed limit, so jet transport is
under-represented".

### 3.5 A twin for people
The impact card turns a shock into what a state disaster officer needs: the change in the probability of heavy rain
(above 64.5 mm/day, the IMD "heavy" threshold) and of heatwave temperatures, by region and lead day, using our own
measured forecast error to express uncertainty. A second card reports kharif crop stress (rain deficit plus heat over
cropland cells) for monsoon-stall scenarios.

### 3.6 The multiverse, literally
"Wethr-fork": any day can be forked into named universes (control, warm ocean, monsoon stall, planted cyclone, a
judge's custom shock), shown as a branching tree with synchronized side-by-side maps and the speed-limit ring drawn
around each shock.

## 4. What we will not claim
- Not a replacement for IMD or ECMWF forecasts; 1-degree daily fields cannot resolve cyclones' cores or convective cells.
- Not a climate projection tool; it is a weather-scale twin (days to two weeks).
- The shock response is the network's response, not ground truth; the natural experiment is supporting evidence, not proof.
- Skill beyond about day 8 is mostly climatology, and we say so.

## 5. Related work (for the brief and Q&A)
| Work | Relevance | Our use |
| --- | --- | --- |
| Learning to Advect: a neural semi-Lagrangian architecture for weather forecasting (arXiv 2601.21151) | Separates learned transport from local changes | Inspiration for our bounded advection step |
| Controlling transient amplification improves long-horizon rollouts (arXiv 2605.08856) | Rollout stability | We get most of the benefit from unrolled training; cited as future work |
| Latent-space multivariate constraints for ML weather forecasting (arXiv 2510.04006) | Consistent relationships between variables | Idea borrowed for physically consistent shocks; not reproduced |
| ClimODE (ICLR 2024) | Physics-informed neural ODE with advection | Related advection-based design |
| Aurora 1.5 (Microsoft), WeatherNext 3 (Google DeepMind), Earth2Studio (NVIDIA) | Large foundation models and toolchains | Context only; unusable here (must train during the event, CPU-only judging) |
