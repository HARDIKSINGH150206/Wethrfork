"""Why does a monsoon-stall shock change west-coast rain? Compare the networks' response with what the data shows after
naturally weak Arabian Sea flow. Run: python -m evaluation.stall_diagnostic (needs data/)."""

from __future__ import annotations

import json

import numpy as np
import torch
from monsoon_r1 import contract as C
from monsoon_r1 import scoring as S

from training.data import ROOT, load_archive, load_config
from wethrfork.engine import Engine
from wethrfork.model import rollout
from wethrfork.normalize import from_z, to_z

dcfg = load_config(ROOT / "configs/data.yaml")
arc = load_archive(dcfg)
YEAR = int(dcfg["splits"]["grade"][0][:4])  # held-out year comes from the config
eng = Engine.load(warmup=False, verify=False)
std = np.array(json.load(open("data/stats.json"))["std"], dtype=np.float32)
land = np.load("artifacts/static.npy")[0] >= 0.5
lat = 6.5 + np.arange(32)[:, None]
lon = 65.5 + np.arange(36)[None, :]
wc = land & (lat >= 8) & (lat <= 20) & (lon >= 72) & (lon <= 78)  # west-coast land cells
box = C.box_mask(C.BOX_ARABIAN_SEA)
slots = arc.slots()
dates = arc.dates


def idx(y, m, d):
    return int(np.where((dates.year == y) & (dates.month == m) & (dates.day == d))[0][0])


wins = [idx(YEAR, m, d) for m in (6, 7, 8, 9) for d in (5, 15, 25)]


@torch.no_grad()
def nn_delta(net, t, pert):
    init = torch.from_numpy(np.stack([arc.data[t - 2 : t + 1], arc.data[t - 2 : t + 1]])).clone()
    init[1, -1] += torch.from_numpy(pert)
    sl = torch.from_numpy(np.array([(slots[t] + k) % 366 for k in range(11)])).unsqueeze(0).expand(2, -1)
    prev = torch.stack([(sl[:, 0] - 2) % 366, (sl[:, 0] - 1) % 366, sl[:, 0]], 1)
    z0 = to_z(init, eng.clim_t[prev], eng.s)
    z = rollout(net, z0, sl, eng.clim_t, eng.s, eng.static_t, 10)
    ph = from_z(z, eng.clim_t[sl[:, 1:]], eng.s).numpy()
    return ph[1] - ph[0]


rows = {"skill": [], "dyn": [], "ridge": []}
for t in wins:
    pert = S.make_shock("monsoon_stall", arc.data[t], std)
    for name, net in (("skill", eng.net), ("dyn", eng.dyn)):
        d = nn_delta(net, t, pert)
        rows[name].append(d[:, 1][:, wc].mean(axis=1))
    sl = torch.from_numpy(np.array([(slots[t] + k) % 366 for k in range(1, 11)]))
    prev = torch.tensor([(slots[t] - 2) % 366, (slots[t] - 1) % 366, slots[t]])
    init = torch.from_numpy(arc.data[t - 2 : t + 1]).clone()
    i2 = init.clone()
    i2[-1] += torch.from_numpy(pert)
    r1 = from_z(eng.ridge.predict(to_z(init, eng.clim_t[prev], eng.s), sl), eng.clim_t[sl], eng.s).numpy()
    r2 = from_z(eng.ridge.predict(to_z(i2, eng.clim_t[prev], eng.s), sl), eng.clim_t[sl], eng.s).numpy()
    rows["ridge"].append((r2 - r1)[:, 1][:, wc].mean(axis=1))
print("west-coast land cells:", int(wc.sum()), " windows:", len(wins))
for k, v in rows.items():
    a = np.array(v)
    print(
        f"{k:6s} mean tp delta (mm/day) days 1..10:",
        np.round(a.mean(axis=0), 2),
        " windows with day-4..8 mean > 0:",
        int((a[:, 3:8].mean(axis=1) > 0).sum()),
        "/",
        len(a),
    )
# what does the data say? composite after weak Arabian Sea westerlies in JJAS
u = arc.data[:, 2][:, box].mean(axis=1)
a_u = u - np.array([u[slots == s].mean() for s in range(366)])[slots]
jjas = np.isin(dates.month, [6, 7, 8, 9])
ok = np.where(jjas)[0]
ok = ok[(ok > 2) & (ok < len(dates) - 11)]
lo = ok[a_u[ok] < np.percentile(a_u[ok], 15)]
hi = ok[a_u[ok] > np.percentile(a_u[ok], 85)]
clim = eng.clim


def comp(sel):
    return np.array(
        [[arc.data[t + k, 1][wc].mean() - clim[slots[t + k], 1][wc].mean() for k in range(1, 11)] for t in sel]
    ).mean(axis=0)


print(
    "observed: west-coast rain anomaly days 1..10 after WEAK Arabian Sea u10 (bottom 15%):",
    np.round(comp(lo), 2),
    "n",
    len(lo),
)
print("observed: after STRONG u10 (top 15%):                                              ", np.round(comp(hi), 2))
print(
    "mean u10 anomaly in the composites (m/s): weak",
    round(float(a_u[lo].mean()), 2),
    "strong",
    round(float(a_u[hi].mean()), 2),
)
