# GLOSSARY

| Term | Meaning in this project |
| --- | --- |
| Advection | Transport of a field by the wind. Our network does it semi-Lagrangian style: sample the field where the air came from |
| Anomaly | Value minus the climatology for that calendar day and cell |
| Anti-blur | Judge check: day-8 spatial variance between 40% and 250% of the real field's |
| Blend | Per-lead, per-channel weighted mix of network and ridge forecasts |
| Box | Rectangle of cells where a shock is applied (judge boxes: Bay of Bengal lat 8-20 lon 82-94; Arabian Sea lat 8-20 lon 65-75) |
| Causality checks | Judge's tests on shock responses: non-zero, localized, propagates, stable (plus null) |
| Clamp | Final step bounding outputs (tp ≥ 0, tcwv ≥ 0, t2m in range, finite) |
| Climatology | 366-slot mean seasonal cycle per cell with 15-day smoothing (kit method) |
| Control | The unshocked forecast in a fork |
| CSI | Critical success index for heavy rain at 10 mm/day: hits / (hits + misses + false alarms) |
| Delta (D) | Shocked network rollout minus base network rollout |
| doy_sincos | `[sin(2π d/365), cos(2π d/365)]` of the last input day |
| Dynamics head | The network alone, used for shock responses |
| Fork | Branching a forecast into an alternate universe by applying a shock |
| Fuzz test | Our battery of ~60 random shocks checking validity and causality |
| Gate | A pass/fail checkpoint in the build (Gate 1, v0.1, Gate 2, v0.2, freeze, Gate 4) |
| Lab server | Our second process (port 8001) for dashboard science features |
| Lead (k) | Days after the last input day; lead 1 is `rollout[0]` |
| Light cone | Set of cells that can be influenced after k steps; ours has radius 8k |
| Near mask | Judge's box dilated by 3 four-neighbour steps |
| Null shock | All-zero perturbation; must change nothing |
| OOD meter | How far a shocked state is from the training range, in local standard deviations |
| Persistence | Reference forecast repeating the last input day |
| Post-processor (PP) | Damping toward climatology and rain calibration applied to the blended forecast |
| Quantile mapping | Calibration matching the distribution of forecast rain to observed rain |
| Reach | Maximum distance, in cells, that information can travel in one step |
| Ridge head | Per-cell, per-lead linear regression model |
| Self-grade | Our reproduction of the judge's score on held-out data with the kit's code |
| sigma_err | Per-cell forecast RMSE by lead (2021), used for stippling and probabilities |
| Skill head | Blend + post-processor; produces the scored forecast |
| Skill score (SS) | `1 - RMSE_model / min(RMSE_persistence, RMSE_climatology)` |
| Speed limit | Our design bound, checked by unit tests: the network's daily update moves information at most 8 cells along either axis (~900 km; up to 9.7 cells diagonally) |
| Stippling | Dots on cells where the delta exceeds typical forecast error |
| Timeline Prime | The unshocked forecast (track terminology) |
| Universe | One branch in the fork tree |
| Validity gate | Judge's hard gate: finite, rain ≥ 0, t2m within -40 to +60 °C, correct shape |
