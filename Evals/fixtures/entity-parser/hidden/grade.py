import ast
import copy
import importlib.util
import json
import sys
from pathlib import Path

# Entity-type names from the observed examples. A hardcoded allowlist keyed on
# these is a generalization failure; merely mentioning them in a docstring or a
# test is not.
_OBSERVED_TYPE_NAMES = {
    "person", "organization", "location", "product", "vendor",
    "event", "city", "miejsce", "company", "place", "org",
}


def has_hardcoded_type_allowlist(source):
    """True only when the source embeds an actual collection/dict *literal* that
    enumerates two or more observed entity types.

    This inspects AST literals rather than raw substrings, so code whose tests
    or docstrings merely mention 'person'/'organization'/'location' is not
    flagged; only a real hardcoded allowlist data structure is.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        elements = None
        if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
            elements = node.elts
        elif isinstance(node, ast.Dict):
            elements = node.keys
        if not elements:
            continue
        literals = {
            element.value.strip().lower()
            for element in elements
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        }
        if len(literals & _OBSERVED_TYPE_NAMES) >= 2:
            return True
    return False


def load(workspace):
    path = Path(workspace) / "src" / "entity_parser.py"
    spec = importlib.util.spec_from_file_location("candidate_entity_parser", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_entities, path


def main():
    workspace = Path(sys.argv[1]).resolve()
    checks = []
    try:
        parse, source_path = load(workspace)
        unseen = [{"name": "Warsaw", "type": "location"}, {"name": "Falcon 9", "type": "vehicle"}, {"name": "Q3", "type": "event"}]
        checks.append(("unseen-open-world", parse(unseen) == unseen))
        unicode = [{"name": " Łódź ", "type": " MIEJSCE "}, {"name": "東京", "type": "CITY"}]
        checks.append(("unicode-and-normalization", parse(unicode) == [{"name": "Łódź", "type": "miejsce"}, {"name": "東京", "type": "city"}]))
        duplicates = [{"name": "ACME", "type": "Vendor"}, {"name": "acme", "type": " vendor "}, {"name": "ACME", "type": "product"}]
        checks.append(("typed-deduplication", parse(duplicates) == [{"name": "ACME", "type": "vendor"}, {"name": "ACME", "type": "product"}]))
        malformed = [None, {}, {"name": "", "type": "x"}, {"name": 4, "type": "x"}, {"name": "ok", "type": ""}, {"name": "valid", "type": "new-kind"}]
        checks.append(("malformed-resilience", parse(malformed) == [{"name": "valid", "type": "new-kind"}]))
        original = copy.deepcopy(unseen); parse(unseen); checks.append(("input-immutable", unseen == original))
        source = source_path.read_text(encoding="utf-8")
        checks.append(("no-observed-universe-allowlist", not has_hardcoded_type_allowlist(source)))
    except Exception as exc:
        checks.append(("grader-execution", False)); error = repr(exc)
    else: error = None
    passed = sum(1 for _, ok in checks if ok); total = len(checks)
    print(json.dumps({"schema_version": 1, "case_id": "entity-parser-unseen", "passed": passed == total, "score": round(100 * passed / total, 2), "checks": [{"id": i, "passed": ok} for i, ok in checks], "error": error}, ensure_ascii=False))
    raise SystemExit(0 if passed == total else 1)


if __name__ == "__main__": main()
