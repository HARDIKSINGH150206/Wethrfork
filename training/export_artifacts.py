"""Copy the chosen checkpoint into artifacts/ and write manifest.json with sha256 hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "artifacts"
FILES = [
    "nn.pt",
    "nn_config.json",
    "nn_dyn.pt",
    "nn_dyn_config.json",
    "ridge.pt",
    "climatology.npy",
    "clim_std.npy",
    "static.npy",
    "stats.json",
    "norm.json",
    "postproc.json",
    "sigma_err.npy",
    "sigma_err_logtp.npy",
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def status() -> None:
    for f in FILES + ["manifest.json"]:
        p = ART / f
        print(f"{'ok ' if p.exists() else '-- '} {f} {p.stat().st_size if p.exists() else ''}")
    gate = ROOT / "runs" / "gate" / "latest.json"
    print("gate:", ("PASS" if json.loads(gate.read_text()).get("all_pass") else "FAIL") if gate.exists() else "not run")


def export(run_dir: Path, model_name: str, selfgrade: dict | None, dyn_dir: Path | None = None) -> None:
    if dyn_dir is not None and (dyn_dir / "best.pt").exists():
        shutil.copy2(dyn_dir / "best.pt", ART / "nn_dyn.pt")
        shutil.copy2(dyn_dir / "nn_config.json", ART / "nn_dyn_config.json")
    best = run_dir / "best.pt"
    if best.exists():
        shutil.copy2(best, ART / "nn.pt")
        shutil.copy2(run_dir / "nn_config.json", ART / "nn_config.json")
    files = {f: {"sha256": sha(ART / f), "bytes": (ART / f).stat().st_size} for f in FILES if (ART / f).exists()}
    manifest = {
        "model_name": model_name,
        "files": files,
        "trained_on": "train split from configs/data.yaml",
        "selfgrade": selfgrade or {"mean_ss_grade": None, "csi_skill_grade": None},
    }
    (ART / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print("manifest written:", ", ".join(files))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--run-dir", default="runs/nn")
    ap.add_argument("--model-name", default="wethrfork-v0.2-speedlimit")
    ap.add_argument("--selfgrade-json", default=None)
    ap.add_argument("--dyn-dir", default=None, help="run dir of the separate shock-dynamics network")
    args = ap.parse_args()
    if args.status:
        status()
        return
    sg = json.loads(Path(args.selfgrade_json).read_text()) if args.selfgrade_json else None
    export(ROOT / args.run_dir, args.model_name, sg, ROOT / args.dyn_dir if args.dyn_dir else None)


if __name__ == "__main__":
    main()
