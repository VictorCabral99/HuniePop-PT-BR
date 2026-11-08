"""Open the PT-BR curation desk.

    python scripts/curate.py
    python scripts/curate.py --port 8765
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    server = Path(__file__).resolve().parents[1] / "curation" / "server.py"
    sys.argv[0] = str(server)
    runpy.run_path(str(server), run_name="__main__")
