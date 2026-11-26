"""Natural experiment: composite of observed weather after a warm Bay of Bengal versus the model's response to the shock."""

from __future__ import annotations

import argparse
import json
import logging

import numpy as np

from training.data import ROOT, load_archive, load_config
from wethrfork.climatology import sincos_of_slot
from wethrfork.engine import Engine

log = logging.getLogger(__name__)
BOX = (8.0, 20.0, 82.0, 94.0)


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a.ravel() - a.mean(), b.ravel() - b.mean()
    return float((a * b).sum() / max(np.sqrt((a * a).sum() * (b * b).sum()), 1e-12))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-config", default="configs/data.yaml")
    ap.add_argument("--max-events", type=int, default=60)
    ap.add_argument("--lead", type=int, default=2)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    arc = load_archive(load_config(ROOT / args.data_config))
    eng = Engine.load()
    assert eng.ready, eng.error
    from monsoon_r1 import scoring as S
    from monsoon_r1.contract import box_mask

    m = box_mask(BOX)
    slots = arc.slots()
    anom = arc.data - eng.clim[slots]
    box_t2m = anom[:, 0][:, m].mean(axis=1)
    thr = box_t2m.mean() + 1.0 * box_t2m.std()
    cand = [t for t in np.where(box_t2m > thr)[0] if 2 <= t < len(slots) - 6]
    events: list[int] = []
    for t in cand:  # keep events at least 5 days apart
        if not events or t - events[-1] >= 5:
            events.append(int(t))
    events = events[: args.max_events]
    std = np.array(json.loads((ROOT / "artifacts" / "stats.json").read_text())["std"], dtype=np.float32)
    obs = np.mean([anom[t + 1 : t + 5][:, [1, 4]] for t in events], axis=0)  # [4,2,H,W]: lead 1..4 anomalies of tp, msl
    resp = []
    for t in events:
        init = arc.data[t - 2 : t + 1]
        doy = sincos_of_slot(int(slots[t]))
        base = eng.simulate(init, doy, 4, None)
        shock = eng.simulate(init, doy, 4, S.make_shock("warm_ocean", init[-1], std))
        resp.append((shock - base)[:, [1, 4]])
    resp = np.mean(resp, axis=0)
    k = args.lead - 1
    out = {
        "n_events": len(events),
        "lead": args.lead,
        "pattern_corr": {"tp": _corr(obs[k, 0], resp[k, 0]), "msl": _corr(obs[k, 1], resp[k, 1])},
        "sign_in_bay": {
            "tp": [float(obs[k, 0][m].mean()), float(resp[k, 0][m].mean())],
            "msl": [float(obs[k, 1][m].mean()), float(resp[k, 1][m].mean())],
        },
        "observed_composite": {"d_tp": obs[:, 0].tolist(), "d_msl": obs[:, 1].tolist()},
        "model_response": {"d_tp": resp[:, 0].tolist(), "d_msl": resp[:, 1].tolist()},
    }
    d = ROOT / "runs" / "natural"
    d.mkdir(parents=True, exist_ok=True)
    (d / "summary.json").write_text(json.dumps(out))
    print(
        "events", out["n_events"], "pattern corr", out["pattern_corr"], "sign in Bay (obs, model)", out["sign_in_bay"]
    )


if __name__ == "__main__":
    main()
