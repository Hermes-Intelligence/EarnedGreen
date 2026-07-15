"""Render one benchmark result Markdown file to a polished local PDF."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

module_path = Path(__file__).with_name("build-pdfs.py")
spec = importlib.util.spec_from_file_location("benchmark_pdf_renderer", module_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load PDF renderer: {module_path}")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
NumberedDoc = renderer.NumberedDoc
markdown_story = renderer.markdown_story


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", default="Benchmark Result")
    args = parser.parse_args()
    doc = NumberedDoc(args.output.resolve(), args.title)
    doc.build(markdown_story(args.source.resolve()))
    print(args.output.resolve())


if __name__ == "__main__":
    main()
