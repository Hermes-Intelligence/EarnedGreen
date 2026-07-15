import ast
import importlib.util
import json
import sys
import time
from pathlib import Path

p = Path(sys.argv[1]) / "src/extractor.py"
s = importlib.util.spec_from_file_location("x", p)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
c = []


def check(i, v):
    c.append((i, bool(v)))


def uses_known_allowlist(source):
    """True when the code defines/uses an identifier for a hardcoded ``known_*``
    allowlist (e.g. ``known_fields``), inspected via the AST.

    Restricting the scan to real identifiers (names, attributes, args,
    def/class names) means a comment, docstring, or test that merely mentions a
    'known' format no longer trips the check, while an actual hardcoded
    allowlist variable still does.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Conservative fallback if the module cannot be parsed.
        return 'known_' in source.lower()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id.lower().startswith('known_'):
            return True
        if isinstance(node, ast.arg) and node.arg.lower().startswith('known_'):
            return True
        if isinstance(node, ast.Attribute) and node.attr.lower().startswith('known_'):
            return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name.lower().startswith('known_'):
            return True
    return False


try:
    check('unicode-colons', m.extract_records("# x\r\n użytkownik : Łukasz:admin \r\nurl: https://x:y\ninvalid") == [{"name": "użytkownik", "value": "Łukasz:admin"}, {"name": "url", "value": "https://x:y"}])
    t = time.perf_counter()
    m.extract_records('a' * 200000)
    check('bounded', time.perf_counter() - t < 1.0)
    check('no-observed-list', not uses_known_allowlist(p.read_text(encoding="utf-8")))
except Exception as e:
    check('execution', False)
n = sum(v for _, v in c)
print(json.dumps({'passed': n == len(c), 'score': 100 * n / len(c), 'checks': [{'id': i, 'passed': v} for i, v in c]}))
sys.exit(0 if n == len(c) else 1)
