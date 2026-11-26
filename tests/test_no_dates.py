"""No Python file in the repo may contain a date literal or a dated constructor call."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATE_RE = re.compile(r"\b(?:19|20)\d{2}[-/]?(?:0[1-9]|1[0-2])[-/]?(?:0[1-9]|[12]\d|3[01])\b")
DATETIME_CALL = re.compile(r"(?:date|datetime|Timestamp)\(\s*['\"]?(?:19|20)\d{2}")
SKIP = {".git", ".venv", "node_modules", "__pycache__", "data", "runs", "dist", "build"}


def _py_files():
    for p in ROOT.rglob("*.py"):
        if not (set(p.relative_to(ROOT).parts) & SKIP):
            yield p


def test_no_date_literals_in_python():
    offenders = []
    for p in _py_files():
        t = p.read_text(errors="ignore")
        if DATE_RE.search(t) or DATETIME_CALL.search(t):
            offenders.append(str(p.relative_to(ROOT)))
    assert not offenders, offenders
