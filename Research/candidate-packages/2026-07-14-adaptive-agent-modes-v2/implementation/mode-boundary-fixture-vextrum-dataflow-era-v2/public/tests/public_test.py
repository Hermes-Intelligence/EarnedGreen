"""Public smoke tests: the pipeline core imports and the documented no-op
paths stay no-ops. Uses an inline database fake (offline; no psycopg2 needed).
Run from the workspace root: python tests/public_test.py"""
import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "test://local")
os.environ.setdefault("UDS_DATABASE_URL", "test://uds")


class _Cursor:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, sql, params=None):
        pass

    def fetchall(self):
        return []

    def fetchone(self):
        return None


class _Conn:
    autocommit = False
    closed = 0

    def cursor(self, cursor_factory=None):
        return _Cursor()


fake = types.ModuleType("psycopg2")
fake_extras = types.ModuleType("psycopg2.extras")
fake_extras.RealDictCursor = object()
fake.connect = lambda dsn: _Conn()
fake.extras = fake_extras
sys.modules.setdefault("psycopg2", fake)
sys.modules.setdefault("psycopg2.extras", fake_extras)

import pipeline.executor  # noqa: E402,F401  (imports must succeed)
import pipeline.materializer  # noqa: E402
import pipeline.planner  # noqa: E402

assert pipeline.materializer.materialize_workspace("ws-x") == 0, \
    "a workspace with no active criteria must materialize nothing"
assert pipeline.planner.plan_workspace("ws-x") is None, \
    "a workspace with no active configuration must plan nothing"
print("public smoke: OK (imports + documented no-op paths)")
