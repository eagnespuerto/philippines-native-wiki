"""Entry point for the Philippines Native Wiki desktop app.

Run:
    python app/main.py
    python -m app.main
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python app/main.py` in addition to `python -m app.main`
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.ui import run
else:
    from .ui import run


if __name__ == "__main__":
    run()
