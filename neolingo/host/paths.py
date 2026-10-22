"""Where things are.  NEOLINGO_VAR overrides var/ (the tests use it to keep their own database); NEOLINGO_PAGE overrides
page/ (a scratch host can serve a newer page than the one in the folder, which a running host serves)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAR = Path(os.environ.get("NEOLINGO_VAR") or ROOT / "var").resolve()
PAGE = Path(os.environ.get("NEOLINGO_PAGE") or ROOT / "page").resolve()
DATA = ROOT / "data"
TAKES = VAR / "takes"
SPEECH = VAR / "speech"
ARCHIVE = VAR / "archive"                 # kept for good: every take, and one line a Record and a Check
ARCHIVE_TAKES = ARCHIVE / "takes"
GUEST_LIST = VAR / "guest_takes.txt"       # tokens of takes a guest may have made, until deleted
DB = VAR / "neolingo.sqlite"
LOG = VAR / "host.log"
_BIN = "/Users/matthew/Lean/locus/.lake/build/bin"
# The production engine is `neolingo-serve` (locus stage 0, 22 October: the same protocol and answers, 4.6 MB
# instead of 102 MB); `neolingo` (the tools, the gate's commands) answers `neohost` identically and is the fallback.
ENGINE = os.environ.get("NEOLINGO_ENGINE") or (f"{_BIN}/neolingo-serve" if os.path.exists(f"{_BIN}/neolingo-serve")
                                               else f"{_BIN}/neolingo")
UID = "me"


def make_dirs():
    for d in (VAR, TAKES, SPEECH, ARCHIVE, ARCHIVE_TAKES):
        d.mkdir(parents=True, exist_ok=True)
