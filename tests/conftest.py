"""Pytest path wiring: the container package is the import root."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTAINER = ROOT / "container"

if str(CONTAINER) not in sys.path:
    sys.path.insert(0, str(CONTAINER))
