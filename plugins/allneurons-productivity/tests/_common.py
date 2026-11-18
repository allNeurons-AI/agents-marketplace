"""Shared helpers for the regression tests: paths and a scratch directory."""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
FIX = os.path.join(ROOT, "tests", "fixtures")
for p in (ASSETS, os.path.join(ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


def tmpdir():
    return tempfile.mkdtemp(prefix="hp-test-")


def run(script, *args, **kw):
    """Run an assets/ script as a subprocess; returns CompletedProcess (text)."""
    return subprocess.run([sys.executable, os.path.join(ASSETS, script)] + [str(a) for a in args],
                          capture_output=True, text=True, **kw)
