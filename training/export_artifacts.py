"""Copy the trained checkpoints into artifacts/ and write manifest.json (sha256 hashes plus the training lineage).

Two stages, because calibration needs the weights in place before it can run:
  --stage weights   copy nn.pt / nn_dyn.pt (and their configs) from the run directories; FAILS if a checkpoint is missing
  --stage manifest  hash every shipped file and record where it came from
  --stage all       both (default)
Nothing is ever kept silently: a missing checkpoint is an error unless --keep-existing is given explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "artifacts"
REQUIRED = [
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
]
OPTIONAL = ["sigma_err.npy", "sigma_err_logtp.npy"]
FILES = REQUIRED + OPTIONAL
POSTPROC_KEYS = ["blend_w", "damp", "rain_shrink", "rain_floor", "rain_scale", "rain_scale_above"]
LINEAGE_CONFIGS = ["data.yaml", "ridge.yaml", "train_skill.yaml", "train.yaml", "train_dyn_ft.yaml", "calib.yaml"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def status() -> None:
    for f in FILES + ["manifest.json"]:
        p = ART / f
        print(f"{'ok ' if p.exists() else '-- '} {f} {p.stat().st_size if p.exists() else ''}")
    gate = ROOT / "runs" / "gate" / "latest.json"
    print("gate:", ("PASS" if json.loads(gate.read_text()).get("all_pass") else "FAIL") if gate.exists() else "not run")


def copy_weights(skill_dir: Path, dyn_dir: Path, keep_existing: bool) -> None:
    for label, run_dir, dst in (("skill", skill_dir, "nn"), ("dynamics", dyn_dir, "nn_dyn")):
        best, cfg = run_dir / "best.pt", run_dir / "nn_config.json"
        if best.exists() and cfg.exists():
            shutil.copy2(best, ART / f"{dst}.pt")
            shutil.copy2(cfg, ART / f"{dst}_config.json")
            print(
                f"copied {label} network from {run_dir.relative_to(ROOT) if run_dir.is_relative_to(ROOT) else run_dir}"
            )
        elif keep_existing and (ART / f"{dst}.pt").exists():
            print(f"WARNING: no checkpoint in {run_dir}; keeping the existing artifacts/{dst}.pt (--keep-existing)")
        else:
            sys.exit(
                f"ERROR: {label} checkpoint missing ({best} or {cfg}). Train it first (make train) or pass --keep-existing."
            )


def check_complete() -> None:
    missing = [f for f in REQUIRED if not (ART / f).exists()]
    if missing:
        sys.exit(f"ERROR: required artifacts missing: {missing}")
    pp = json.loads((ART / "postproc.json").read_text())
    lost = [k for k in POSTPROC_KEYS if k not in pp]
    if lost:
        sys.exit(
            f"ERROR: postproc.json is missing {lost}: the calibration was not saved completely. Re-run the calibration fit."
        )


def git_head() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return None


def write_manifest(model_name: str, selfgrade: dict | None, skill_dir: Path, dyn_dir: Path) -> None:
    check_complete()
    files = {f: {"sha256": sha(ART / f), "bytes": (ART / f).stat().st_size} for f in FILES if (ART / f).exists()}
    lineage = {
        "skill_checkpoint_sha256": sha(skill_dir / "best.pt") if (skill_dir / "best.pt").exists() else None,
        "dynamics_checkpoint_sha256": sha(dyn_dir / "best.pt") if (dyn_dir / "best.pt").exists() else None,
        "configs": {c: sha(ROOT / "configs" / c) for c in LINEAGE_CONFIGS if (ROOT / "configs" / c).exists()},
        "git_commit": git_head(),
    }
    manifest = {
        "model_name": model_name,
        "files": files,
        "trained_on": "train split from configs/data.yaml",
        "lineage": lineage,
        "selfgrade": selfgrade or {"mean_ss_grade": None, "csi_skill_grade": None},
    }
    (ART / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print("manifest written:", ", ".join(files))


def main() -> None:
    sys.path.insert(0, str(ROOT))
    from wethrfork import MODEL_NAME

    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--stage", choices=["weights", "manifest", "all"], default="all")
    ap.add_argument("--skill-dir", default="runs/nn_skill")
    ap.add_argument("--dyn-dir", default="runs/nn_dyn_ft")
    ap.add_argument("--model-name", default=MODEL_NAME)
    ap.add_argument("--selfgrade-json", default=None)
    ap.add_argument(
        "--keep-existing", action="store_true", help="allow keeping existing weights when a checkpoint is absent"
    )
    args = ap.parse_args()
    if args.status:
        status()
        return
    skill_dir, dyn_dir = ROOT / args.skill_dir, ROOT / args.dyn_dir
    if args.stage in ("weights", "all"):
        copy_weights(skill_dir, dyn_dir, args.keep_existing)
    if args.stage in ("manifest", "all"):
        sg = json.loads(Path(args.selfgrade_json).read_text()) if args.selfgrade_json else None
        write_manifest(args.model_name, sg, skill_dir, dyn_dir)


if __name__ == "__main__":
    main()
