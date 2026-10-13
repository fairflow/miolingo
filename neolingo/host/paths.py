"""Where things are.  NEOLINGO_VAR overrides var/ (the tests use it to keep their own database)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAR = Path(os.environ.get("NEOLINGO_VAR") or ROOT / "var").resolve()
PAGE = ROOT / "page"
DATA = ROOT / "data"
TAKES = VAR / "takes"
SPEECH = VAR / "speech"
DB = VAR / "neolingo.sqlite"
LOG = VAR / "host.log"
ENGINE = os.environ.get("NEOLINGO_ENGINE") or "/Users/matthew/Lean/locus/.lake/build/bin/neolingo"
UID = "me"


def make_dirs():
    for d in (VAR, TAKES, SPEECH):
        d.mkdir(parents=True, exist_ok=True)
