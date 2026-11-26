"""Write the small aggregate JSON files the dashboard's Validation and About tabs read (no weather fields, no dates)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dashboard" / "public"


def main() -> None:
    sg = json.loads((ROOT / "runs" / "selfgrade" / "v02_fit2020.json").read_text())
    slim = {
        k: {
            key: sg[k][key]
            for key in (
                "n_windows",
                "mean_ss",
                "mean_csi_skill",
                "rmse_pts",
                "csi_pts",
                "blur_pts",
                "var_ratio_day8_mean",
                "ss_by_lead_channel",
                "csi_skill_by_lead",
            )
        }
        for k in ("systematic", "typed")
    }
    gate = json.loads((ROOT / "runs" / "gate" / "latest.json").read_text())
    g = {}
    for season, v in gate.items():
        if season == "all_pass":
            continue
        g[season] = {
            name: {
                "near": v["checks"][name].get("near_frac_day1"),
                "growth": v["checks"][name]["growth_ratio"],
                "far": v["checks"][name]["far_frac_max"],
                "max_z": v["checks"][name]["max_z"],
                "pass": v["pass"][name],
            }
            for name in ("warm_ocean", "monsoon_stall")
        }
        g[season]["null_max_diff"] = v["checks"]["null_max_diff"]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "selfgrade.json").write_text(json.dumps(slim))
    (OUT / "gate.json").write_text(json.dumps(g))
    print("wrote", OUT / "selfgrade.json", OUT / "gate.json")


if __name__ == "__main__":
    main()
