#!/usr/bin/env python3
"""Read the repo's conventions out of the repo — provenance `host`, rank 3.

Generalised out of a real client deliverable on 2026-07-21. Two arms of that
campaign produced the same document; the only mechanically-measurable difference
between them was that one arm EXTRACTED the house rules from the file the product
already renders from, and the other transcribed them by hand. Transcribing turns
rank 3 into rank 2, which is the rung measured to saturate, and it rots the moment
the host file changes.

The extractors are format-shaped, not repo-shaped, so they travel:

    js_exports        export const NAME = {...} / [...]   design tokens, brand books
    json_tokens       any nested JSON of key -> scalar     theme files, token sets
    css_variables     --name: value                        stylesheets, :root blocks
    directives        MUST / NEVER / ALWAYS lines          CONVENTIONS.md, CLAUDE.md

The one behaviour worth reading the source for is what happens on a file that
parses to nothing. It reports `usable: false` and says which file was silent.
An empty rule set is the most dangerous output an extractor has, because a
document checked against zero rules passes every one of them.

    python host_rules.py --file path/to/tokens.json
    python host_rules.py --repo . --discover
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Files that carry house rules, by convention rather than by guess. Kept in sync
# with the `host` detector in oracle_plan.py, which reports that they exist; this
# module is what turns them into predicates.
DISCOVERY = ("**/tokens*.json", "**/theme*.js", "**/theme*.json", "**/*brandBook*",
             "**/*brand-book*", "**/design-system*", "**/tailwind.config.*",
             "**/*.tokens.*", "**/CONVENTIONS.md", "**/STYLEGUIDE.md")

EXCLUDED_PARTS = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv",
                  "venv", "site-packages", ".next", "coverage", "vendor",
                  "runs", "artifacts", "returned-workspace", "rollback"}


@dataclass
class Rules:
    """Extracted house rules, with the file and extractor that produced them."""
    path: str
    extractor: str
    values: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return sum(len(v) if isinstance(v, (list, dict)) else 1 for v in self.values.values())

    @property
    def usable(self) -> bool:
        return self.count > 0

    def as_dict(self) -> dict:
        return {"schema_version": 1, "provenance": "host", "rank": 3,
                "path": self.path, "extractor": self.extractor,
                "values": self.values, "count": self.count, "usable": self.usable,
                "notes": self.notes,
                "rule": ("extracted, not transcribed: a hand-copied rule is provenance "
                         "'spec' and stops tracking the file it came from")}


# ── balanced-literal reader ───────────────────────────────────────────────────
def js_literal(source: str, name: str) -> str:
    """The source text of `export const NAME = {...}` or `= [...]`, brackets balanced.

    String-aware on purpose: a brace inside a quoted tagline used to end the block
    early and truncate the rule set to whatever came before it.
    """
    match = re.search(rf"(?:export\s+)?const\s+{re.escape(name)}\s*=\s*", source)
    if not match:
        raise ValueError(f"{name} not found in the source; the module changed shape")
    start = match.end()
    opener = source[start]
    closer = {"[": "]", "{": "}"}.get(opener)
    if not closer:
        raise ValueError(f"{name} is not an array or object literal")
    depth, i, in_string, quote = 0, start, False, ""
    while i < len(source):
        ch = source[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                in_string = False
        elif ch in "\"'`":
            in_string, quote = True, ch
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
        i += 1
    raise ValueError(f"unterminated literal for {name}")


def js_fields(block: str, key: str) -> list[str]:
    """Every `key: "value"` in a literal block, in source order."""
    return re.findall(rf"{re.escape(key)}\s*:\s*[\"'`]([^\"'`]*)[\"'`]", block)


# ── extractors ────────────────────────────────────────────────────────────────
def extract_js_exports(path: Path) -> Rules:
    source = path.read_text(encoding="utf-8", errors="replace")
    names = re.findall(r"export\s+const\s+([A-Z][A-Z0-9_]*)\s*=\s*[\[{]", source)
    values, notes = {}, []
    for name in names:
        try:
            block = js_literal(source, name)
        except ValueError as exc:
            notes.append(f"{name}: {exc}")
            continue
        # Every quoted scalar in the literal, deduplicated, order preserved.
        scalars, seen = [], set()
        for token in re.findall(r"[\"'`]([^\"'`\n]{1,120})[\"'`]", block):
            if token and token not in seen:
                seen.add(token)
                scalars.append(token)
        if scalars:
            values[name] = scalars
    hexes = sorted(set(re.findall(r"#[0-9a-fA-F]{6}\b", source)))
    if hexes:
        values["_palette"] = hexes
    return Rules(str(path), "js_exports", values, notes)


def extract_json_tokens(path: Path) -> Rules:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as exc:
        return Rules(str(path), "json_tokens", {}, [f"unparseable: {exc}"])
    flat: dict[str, object] = {}

    def walk(node, prefix=""):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{prefix}.{key}" if prefix else key)
        elif isinstance(node, list):
            flat[prefix] = node
        else:
            flat[prefix] = node

    walk(data)
    return Rules(str(path), "json_tokens", {"tokens": flat})


def extract_css_variables(path: Path) -> Rules:
    source = path.read_text(encoding="utf-8", errors="replace")
    pairs = re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", source)
    return Rules(str(path), "css_variables",
                 {"variables": {name: value.strip() for name, value in pairs}})


DIRECTIVE = re.compile(r"^.{0,120}?\b(MUST NOT|MUST|NEVER|ALWAYS|DO NOT|REQUIRED)\b.{0,200}$",
                       re.MULTILINE)


def extract_directives(path: Path) -> Rules:
    source = path.read_text(encoding="utf-8", errors="replace")
    lines = [m.group(0).strip(" -*#\t") for m in DIRECTIVE.finditer(source)]
    seen, ordered = set(), []
    for line in lines:
        if line and line not in seen:
            seen.add(line)
            ordered.append(line)
    return Rules(str(path), "directives", {"directives": ordered},
                 ["prose directives are weaker than a parsed token file: they say what "
                  "to do, not what the value is"])


EXTRACTORS = {
    ".js": extract_js_exports, ".jsx": extract_js_exports,
    ".ts": extract_js_exports, ".tsx": extract_js_exports, ".mjs": extract_js_exports,
    ".json": extract_json_tokens,
    ".css": extract_css_variables, ".scss": extract_css_variables,
    ".md": extract_directives,
}


def extract(path: Path) -> Rules:
    """Extract from one host file, choosing the extractor by format."""
    if not path.exists():
        return Rules(str(path), "none", {}, ["file does not exist"])
    extractor = EXTRACTORS.get(path.suffix.lower())
    if extractor is None:
        return Rules(str(path), "none", {}, [f"no extractor for {path.suffix!r}"])
    rules = extractor(path)
    if not rules.usable:
        rules.notes.append(
            "extracted ZERO rules from a file that exists. This is reported as unusable "
            "rather than as an empty rule set, because a document checked against no "
            "rules passes all of them.")
    return rules


def _own(repo: Path, path: Path) -> bool:
    try:
        parts = path.relative_to(repo).parts
    except ValueError:
        return False
    return not any(part in EXCLUDED_PARTS for part in parts)


def discover(repo: Path, limit: int = 12) -> list[Path]:
    """Host files this repo actually has, deduplicated, own source only."""
    found: list[Path] = []
    for pattern in DISCOVERY:
        for hit in repo.glob(pattern):
            if hit.is_file() and _own(repo, hit) and hit not in found:
                found.append(hit)
                if len(found) >= limit:
                    return found
    return found


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", type=Path, help="one host file to extract from")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--discover", action="store_true", help="list host files in the repo")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    if args.discover and not args.file:
        hits = discover(args.repo.resolve())
        if not hits:
            print("no host files found. This repo's strongest oracle is not 'host'.")
            raise SystemExit(1)
        print(f"HOST FILES ({len(hits)}) — extract, do not transcribe\n")
        for hit in hits:
            rules = extract(hit)
            mark = "ok " if rules.usable else "EMPTY"
            print(f"  {mark}  {rules.count:>4} rules  {rules.extractor:<14} "
                  f"{hit.relative_to(args.repo.resolve())}")
        raise SystemExit(0)

    if not args.file:
        print(__doc__)
        raise SystemExit(0)

    rules = extract(args.file)
    if args.out:
        args.out.write_text(json.dumps(rules.as_dict(), indent=2) + "\n", encoding="utf-8")
    print(f"{rules.extractor} <- {rules.path}")
    print(f"  {rules.count} rules, usable={rules.usable}")
    for key, value in list(rules.values.items())[:8]:
        shown = value if not isinstance(value, (list, dict)) else f"{len(value)} entries"
        print(f"    {key}: {shown}")
    for note in rules.notes:
        print(f"  note: {note}")
    raise SystemExit(0 if rules.usable else 1)


if __name__ == "__main__":
    main()
