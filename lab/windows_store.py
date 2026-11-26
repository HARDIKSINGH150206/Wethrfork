"""Read demo start windows from the gitignored archive per configs/demo.yaml. Never ships data."""

from __future__ import annotations

import numpy as np

from evaluation.windows import index_of
from training.data import ROOT, Archive, load_archive, load_config
from wethrfork.climatology import sincos_of_slot

SEASONS = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJAS", 7: "JJAS", 8: "JJAS", 9: "JJAS"}


class WindowsStore:
    def __init__(self) -> None:
        self.cfg = load_config(ROOT / "configs" / "demo.yaml")
        self.arc: Archive | None = None
        self.clim: np.ndarray | None = None

    def _archive(self) -> Archive:
        if self.arc is None:
            self.arc = load_archive(load_config(ROOT / "configs" / "data.yaml"))
        return self.arc

    def listing(self) -> list[dict]:
        arc = self._archive()
        out = []
        for w in self.cfg["windows"]:
            i = index_of(arc, w["last_input_day"])
            slot = int(arc.slots()[i])
            month = int(arc.dates[i].month)
            out.append({"id": w["id"], "label": w["label"], "season": SEASONS.get(month, "ON"), "doy": slot})
        return out

    def get(self, wid: str, steps: int = 10) -> dict | None:
        arc = self._archive()
        for w in self.cfg["windows"]:
            if w["id"] != wid:
                continue
            i = index_of(arc, w["last_input_day"])
            slot = int(arc.slots()[i])
            d = {
                "id": wid,
                "init_states": arc.data[i - 2 : i + 1].tolist(),
                "doy_sincos": sincos_of_slot(slot),
                "weekday": int(arc.dates[i].weekday()),  # 0 = Monday, of the last input day (timeline labels)
            }
            if self.clim is None:
                self.clim = np.load(ROOT / "artifacts" / "climatology.npy")
            d["clim"] = self.clim[[(slot + k) % 366 for k in range(1, steps + 1)]].tolist()
            if w.get("truth"):
                d["truth"] = arc.data[i + 1 : i + 1 + steps].astype(np.float32).tolist()
            return d
        return None
