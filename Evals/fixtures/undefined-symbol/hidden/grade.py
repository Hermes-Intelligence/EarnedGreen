import ast
import builtins
import importlib.util
import json
import sys
from pathlib import Path

p = Path(sys.argv[1]) / "src/service.py"
s = importlib.util.spec_from_file_location('m', p)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
c = []


class Cache:
    def __init__(self):
        self.d = {}
        self.calls = []

    def get(self, k):
        self.calls.append(('get', k))
        return self.d.get(k)

    def set(self, k, v):
        self.calls.append(('set', k))
        self.d[k] = v


def ck(i, v):
    c.append((i, bool(v)))


def undefined_globals(source):
    """Names read at load-time that are never bound anywhere and are not builtins.

    This replaces a brittle substring ban (which rejected any code merely
    mentioning `logger`, e.g. `logger = logging.getLogger(__name__)`) with a
    real check for genuinely undefined names such as an invented `cache_client`.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Unparseable source cannot be reasoned about statically; the runtime
        # checks below still exercise the module, so do not fail here.
        return set()
    bound = set(dir(builtins)) | {"__name__", "__file__", "__doc__", "__builtins__", "__spec__", "__loader__", "__package__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound.add((alias.asname or alias.name).split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound.add(alias.asname or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
    used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
    return used - bound


try:
    try:
        m.process_order({})
        valid = False
    except ValueError:
        valid = True
    ck('invalid-path', valid)
    cache = Cache()
    a = m.process_order({'id': 'x'}, cache)
    b = m.process_order({'id': 'x'}, cache)
    ck('cache-contract', a == b and cache.calls == [('get', 'x'), ('set', 'x'), ('get', 'x')])
    ck('no-invented-globals', undefined_globals(p.read_text(encoding="utf-8")) == set())
except Exception:
    ck('execution', False)
n = sum(v for _, v in c)
print(json.dumps({'passed': n == len(c), 'score': 100 * n / len(c), 'checks': [{'id': i, 'passed': v} for i, v in c]}))
sys.exit(0 if n == len(c) else 1)
