# 05. Demo golden path

The live demo is where Stage 2 is won. This script is rehearsed twice before submission (hour 11) and once more before
the desk review. Target length: 5 minutes, then questions. One person drives (P3), one narrates (P1), one handles
questions on scoring and engineering (P2).

---

## 0. Setup checklist (10 minutes before)

- [ ] Laptop on power, display mirrored, browser zoom 100%, dark room check of colours.
- [ ] `make demo` running: judge server `:8000` ready, lab `:8001` ready, dashboard `:5173` open, one warm-up fork done.
- [ ] Data file present at `data/india_climate_train.nc` (lab windows load).
- [ ] Wi-Fi on until the demo starts (we turn it off on stage).
- [ ] Backup video open in a second tab (`brief/demo.mp4`), muted.
- [ ] Brief PDF open in a third tab.
- [ ] Terminal with `python -m monsoon_r1.schema_validator http://localhost:8000` output from today, in case asked.
- [ ] `docs/STATUS.md` numbers memorized: mean skill, CSI skill, fuzz pass rate, latency.

## 1. Script

| Time | Screen | Words (narrator) | Fallback |
| --- | --- | --- | --- |
| 0:00 | Dashboard home | "This is Wethrfork, a monsoon digital twin of India. Before anything, I'm turning off Wi-Fi." (turn it off; 10 seconds max) | If Wi-Fi toggle is awkward, skip and say "everything runs locally; happy to prove it later" |
| 0:15 | Home | "Our one idea: a weather model with a speed limit. No change in our simulation can travel more than about 900 km a day, and we can prove it. That is what makes our alternate universes trustworthy." | |
| 0:40 | Timeline Prime: a held-out window, model next to reality, scrub day 1 to 10 | "Here's a 10-day forecast from a window the model never saw, next to what really happened. Notice day 8 is still sharp, not a grey average. On held-out data we beat both 'repeat yesterday' and climatology by X%." | If truth is missing (data file absent), show the forecast only |
| 1:30 | Shock composer | "Now the multiverse. Would you like to pick the shock?" Hand the mouse to the judge. If they hesitate, offer the warm Bay of Bengal preset. | Preset button "Warm Bay +3 K" |
| 1:50 | Fork view: base, shocked, delta; speed-limit ring | "The universe forks. Left is the control, middle is the shocked world, right is the difference. The ring is our speed limit: the ripple cannot leave it. Dotted cells are where the change is bigger than our own measured forecast error." | If the fork is slow (> 3 s), narrate the ring while it loads |
| 2:20 | Limits verdict panel lights up | "And this panel just ran the organizers' own causality checks on your shock: non-zero, localized, propagating, stable. 86% of the day-1 response is next to the shock, and shocks like yours passed 9 of 10 times in our fuzz test." | If lab is offline: "the same checks run in our CI; here are the results" and open the fuzz heatmap image |
| 2:50 | Plant a cyclone preset; track drawn | "Let's plant a cyclone in the Bay: a balanced low with winds and moisture. Here is its track day by day." Honest if it fills: "At 1 degree the model fills it in about 3 days; that's one of our stated limits." | Skip if the cut was made |
| 3:30 | Natural-experiment plot | "How do we know the warm-Bay response is right when nobody can warm the Bay? Nature did it for us: here's what actually happened after naturally warm Bay days, next to our model's response. Pattern correlation 0.X." | Show the brief figure |
| 4:05 | Impact card | "For a state disaster officer: this shock raises the chance of heavy rain in coastal Odisha by X points on day 3, and lowers it in ... For agriculture, a stalled monsoon shows kharif stress in ..." | |
| 4:40 | Close | "So: skill beyond both baselines on held-out data, causality you can check live, limits we measured instead of hiding. That's Wethrfork." | |

## 2. Judge interaction rules
- Always offer the mouse. Judges remember what they did, not what we showed.
- Never argue with a judge's shock. If it breaks the model, read the OOD meter aloud: "This is 6 sigma outside anything
  in the training data; our fuzz test shows shocks this large pass 40% of the time. Here's what goes wrong: ...".
- Keep every answer under 30 seconds, then offer detail.

## 3. Likely judge shocks and what we expect
| Shock | Expected behaviour | Talking point |
| --- | --- | --- |
| Warm Arabian Sea +2.5 K | Local warming, moisture and rain increase downwind along the monsoon flow in JJAS | Downwind propagation within the ring |
| msl -2000 Pa low over the Bay | Cyclonic winds develop, moisture convergence, rain | Gradient-wind balance, filling at 1 degree |
| Heat dome over Rajasthan +5 K | Persistent warm anomaly, weak spread, lower msl | Land shocks spread slowly; dry air |
| Remove moisture over Kerala (tcwv -30%) | Rain suppressed locally, recovers as moist air advects in | Advection refills |
| Huge shock (+15 K) | OOD meter red; clamps hold; may fail stable | Honest limits; validity still holds |
| Shock on the grid edge | Energy can leave the domain | Border padding; edge limitation stated |

## 4. If everything fails
- Play the backup video (2 minutes) and walk through the brief.
- Run `python serve.py` + the validator in a terminal to show the engine works.

## 5. Finals version (Round 3, panel)
Same flow, tighter (4 minutes), plus one slide-like full-screen view of the speed-limit contract table from the brief,
and the out-of-sample numbers. Opening line:
"Every AI weather model can tell you tomorrow's rain. Ours can prove its answer obeys the speed of weather: a shock in
the Bay of Bengal cannot reach Delhi faster than the atmosphere can carry it."
