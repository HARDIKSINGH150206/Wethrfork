"""The demo launcher is real (not a commented stub) and its pieces are consistent with the Makefile."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_demo_script_is_executable_shell_and_not_a_stub():
    sh = ROOT / "scripts" / "demo.sh"
    txt = sh.read_text()
    assert "STUB" not in txt
    for needle in ("serve.py", "lab.lab_server", "vite preview", "preflight.py --live", "xdg-open", "setsid", "wait_for_ok", "cd dashboard"):
        assert needle in txt, needle
    assert subprocess.run(["bash", "-n", str(sh)], check=False).returncode == 0


def test_makefile_wires_demo_and_preflight():
    mk = (ROOT / "Makefile").read_text()
    assert "bash scripts/demo.sh" in mk and "scripts/preflight.sh" not in mk
    assert "preflight" in mk


def test_preflight_helpers():
    import importlib.util

    spec = importlib.util.spec_from_file_location("preflight", ROOT / "scripts" / "preflight.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.port_free(1) in (True, False)
    assert m.check("x", True) is True and m.check("y", False, "why") is False
