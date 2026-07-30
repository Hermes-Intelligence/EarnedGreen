#!/usr/bin/env python3
"""One entry point: `python -m awbp`.

The modules in this package import each other flat (`import oracle_plan`), which
is what lets any one of them be run on its own with no package machinery. That
also means the package directory has to be on the path before the dispatch
happens, so it is put there here rather than assumed.

The CLI is loaded by FILE PATH, not by name. `import awbp` from inside the package
`awbp` returns the package itself, which is already in sys.modules by the time
`-m` runs this, so the plain import silently binds the wrong object and fails on
the first attribute access.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

_spec = importlib.util.spec_from_file_location("awbp_cli", HERE / "awbp.py")
_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cli)

if __name__ == "__main__":
    _cli.main()
