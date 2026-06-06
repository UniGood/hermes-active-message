#!/usr/bin/env python3

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


SOURCE = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser() / "active-message" / "build_context.py"
sys.path.insert(0, str(SOURCE.parent))
runpy.run_path(str(SOURCE), run_name="__main__")
