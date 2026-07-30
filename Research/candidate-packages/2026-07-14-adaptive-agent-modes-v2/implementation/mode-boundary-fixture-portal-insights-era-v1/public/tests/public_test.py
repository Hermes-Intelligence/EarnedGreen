"""Public smoke: the module imports and its route surface exists.
Skips cleanly where fastapi is unavailable (offline sandboxes)."""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    import fastapi  # noqa: F401
    import pydantic  # noqa: F401
except ImportError:
    print("public smoke: SKIPPED (fastapi unavailable in this sandbox)")
    raise SystemExit(0)

for name in ("boto3", "httpx"):
    mod = types.ModuleType(name)
    mod.__getattr__ = lambda attr: (lambda *a, **k: None)
    sys.modules.setdefault(name, mod)
botocore = types.ModuleType("botocore")
config = types.ModuleType("botocore.config")
config.Config = lambda *a, **k: object()
botocore.config = config
sys.modules.setdefault("botocore", botocore)
sys.modules.setdefault("botocore.config", config)

import hermes_intelligence.routes.vextrum as vextrum  # noqa: E402

assert hasattr(vextrum, "get_run_sources"), "sources endpoint must exist"
assert hasattr(vextrum, "get_run_countries"), "countries endpoint must exist"
assert hasattr(vextrum, "router"), "the APIRouter must exist"
print("public smoke: OK (module imports; route surface present)")
