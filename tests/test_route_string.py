"""The route string may appear in serve.py only."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORD = "sim" + "ulate"  # built from pieces so this file never contains the route string itself
ROUTE_RE = re.compile("[/'\"]" + WORD + "['\"]|/" + WORD + r"\b")
SKIP = {".git", ".venv", "node_modules", "__pycache__", "data", "runs", "dist", "build"}


def test_route_only_in_serve():
    hits = [
        str(p.relative_to(ROOT))
        for p in ROOT.rglob("*.py")
        if not (set(p.relative_to(ROOT).parts) & SKIP) and ROUTE_RE.search(p.read_text(errors="ignore"))
    ]
    assert hits == ["serve.py"], hits
