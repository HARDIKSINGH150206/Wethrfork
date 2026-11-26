"""Run the official repo scan on the committed files only; fail below 15 points or on any flag."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    from monsoon_r1.repo_scan import scan

    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    with tempfile.TemporaryDirectory() as tmp:
        for f in tracked:
            src = ROOT / f
            if src.is_file():
                dst = Path(tmp) / f
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        res = scan(Path(tmp))
    print(json.dumps(res, indent=1))
    ok = res["points"] >= 15 and not res["flags"]
    print("SCAN", "PASS" if ok else "FAIL", res["points"], "/ 15")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
