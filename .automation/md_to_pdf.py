#!/usr/bin/env python3
"""md_to_pdf.py -- Render Markdown to a beautiful, print-ready PDF via headless Chrome.

Zero third-party dependencies: a self-contained GitHub-flavored-Markdown (subset)
to HTML converter + a styled template + Chrome/Edge --print-to-pdf. This keeps the
weekly unattended research run from ever breaking on a missing pip package.

Usage:
  python md_to_pdf.py --in report.md --out report.pdf \
      --title "Agentic Best Practices -- Research Report" \
      --subtitle "Weekly deep-research pass" --date 2026-07-12

If --title is omitted, the first H1 in the Markdown (or the filename) is used, and
that leading H1 is removed from the body so the cover page does not duplicate it.
Set CHROME_PATH to override browser discovery.
"""
from __future__ import annotations
import argparse
import html
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

# --------------------------------------------------------------------------- #
#  Markdown -> HTML  (controlled GFM subset: headings, lists, tables, code,
#  blockquotes, hr, and inline bold/italic/code/links/images/strikethrough)
# --------------------------------------------------------------------------- #

_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)+\|?\s*$")
_LIST_ITEM = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
_HR = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")


def _inline(text: str) -> str:
    """Inline formatting with code/link/image protected as tokens before escaping."""
    tokens: list[str] = []

    def stash(fragment: str) -> str:
        tokens.append(fragment)
        return f"\x00T{len(tokens) - 1}\x00"

    # code spans first (their contents are literal)
    text = re.sub(r"`([^`]+)`",
                  lambda m: stash("<code>" + html.escape(m.group(1), quote=False) + "</code>"),
                  text)
    # images  ![alt](url)
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)",
                  lambda m: stash(f'<img alt="{html.escape(m.group(1), quote=True)}" '
                                  f'src="{html.escape(m.group(2), quote=True)}">'),
                  text)
    # links  [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)",
                  lambda m: stash(f'<a href="{html.escape(m.group(2), quote=True)}">'
                                  f'{html.escape(m.group(1), quote=False)}</a>'),
                  text)
    # escape everything else
    text = html.escape(text, quote=False)
    # emphasis (operates on escaped text; tokens contain no * or _)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", text)
    text = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"(?<![A-Za-z0-9_])_([^_\n]+)_(?![A-Za-z0-9_])", r"<em>\1</em>", text)
    # restore tokens (loop to resolve nesting, e.g. code inside a link)
    while re.search(r"\x00T\d+\x00", text):
        text = re.sub(r"\x00T(\d+)\x00", lambda m: tokens[int(m.group(1))], text)
    return text


def _split_row(row: str) -> list[str]:
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    cells = re.split(r"(?<!\\)\|", row)
    return [c.strip().replace("\\|", "|") for c in cells]


def _aligns(sep: str) -> list[str]:
    out = []
    for c in _split_row(sep):
        c = c.strip()
        left, right = c.startswith(":"), c.endswith(":")
        out.append("center" if left and right else "right" if right else "left" if left else "")
    return out


def _render_table(header: str, sep: str, rows: list[str]) -> str:
    heads = _split_row(header)
    aligns = _aligns(sep)

    def sty(i: int) -> str:
        a = aligns[i] if i < len(aligns) else ""
        return f' style="text-align:{a}"' if a else ""

    th = "".join(f"<th{sty(i)}>{_inline(h)}</th>" for i, h in enumerate(heads))
    body = []
    for r in rows:
        cells = _split_row(r)
        tds = "".join(f"<td{sty(i)}>{_inline(c)}</td>" for i, c in enumerate(cells))
        body.append(f"<tr>{tds}</tr>")
    return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _indent(s: str) -> int:
    return len(s) - len(s.lstrip(" "))


def _dedent(lines: list[str]) -> list[str]:
    non = [l for l in lines if l.strip()]
    if not non:
        return lines
    m = min(_indent(l) for l in non)
    return [l[m:] if len(l) >= m else l for l in lines]


def _render_list(lines: list[str]) -> str:
    base = min(_indent(l) for l in lines if l.strip())
    ordered = bool(re.match(r"^\s*\d+[.)]\s+", lines[0]))
    items: list[tuple[str, list[str]]] = []
    i = 0
    while i < len(lines):
        l = lines[i]
        m = re.match(r"^\s*([-*+]|\d+[.)])\s+(.*)$", l)
        if m and _indent(l) == base:
            text = m.group(2)
            children: list[str] = []
            i += 1
            while i < len(lines) and (_indent(lines[i]) > base or lines[i].strip() == ""):
                children.append(lines[i])
                i += 1
            items.append((text, children))
        else:  # lazy continuation of the current item
            if items:
                t, ch = items[-1]
                items[-1] = (t + " " + l.strip(), ch)
            i += 1
    tag = "ol" if ordered else "ul"
    out = []
    for text, children in items:
        inner = _inline(text)
        if any(c.strip() for c in children):
            out.append(f"<li>{inner}{md_to_html(chr(10).join(_dedent(children)))}</li>")
        else:
            out.append(f"<li>{inner}</li>")
    return f"<{tag}>{''.join(out)}</{tag}>"


def _is_block_start(line: str, nxt: str) -> bool:
    return bool(
        re.match(r"^(```|~~~)", line)
        or re.match(r"^#{1,6}\s+", line)
        or _HR.match(line)
        or re.match(r"^\s*>", line)
        or _LIST_ITEM.match(line)
        or ("|" in line and _TABLE_SEP.match(nxt))
    )


def md_to_html(md: str) -> str:
    lines = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        fence = re.match(r"^(```|~~~)(.*)$", line)
        if fence:
            marker, lang = fence.group(1), fence.group(2).strip()
            i += 1
            buf = []
            while i < n and not lines[i].startswith(marker):
                buf.append(lines[i])
                i += 1
            i += 1  # closing fence
            cls = f' class="lang-{html.escape(lang, quote=True)}"' if lang else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(buf), quote=False)}</code></pre>")
            continue
        if line.strip() == "":
            i += 1
            continue
        h = re.match(r"^(#{1,6})\s+(.*)$", line)
        if h:
            lvl = len(h.group(1))
            out.append(f"<h{lvl}>{_inline(h.group(2).strip().rstrip('#').strip())}</h{lvl}>")
            i += 1
            continue
        if _HR.match(line):
            out.append("<hr>")
            i += 1
            continue
        if re.match(r"^\s*>", line):
            buf = []
            while i < n and re.match(r"^\s*>", lines[i]):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append(f"<blockquote>{md_to_html(chr(10).join(buf))}</blockquote>")
            continue
        if "|" in line and i + 1 < n and _TABLE_SEP.match(lines[i + 1]):
            header, sep = line, lines[i + 1]
            i += 2
            rows = []
            while i < n and "|" in lines[i] and lines[i].strip() != "":
                rows.append(lines[i])
                i += 1
            out.append(_render_table(header, sep, rows))
            continue
        if _LIST_ITEM.match(line):
            block = []
            while i < n and (_LIST_ITEM.match(lines[i]) or (lines[i].strip() != "" and lines[i].startswith(" "))):
                block.append(lines[i])
                i += 1
            out.append(_render_list(block))
            continue
        # paragraph
        buf = []
        while i < n and lines[i].strip() != "" and not _is_block_start(lines[i], lines[i + 1] if i + 1 < n else ""):
            buf.append(lines[i].strip())
            i += 1
        out.append(f"<p>{_inline(' '.join(buf))}</p>")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
#  Template
# --------------------------------------------------------------------------- #

CSS = r"""
:root{
  --ink:#1f2937; --muted:#6b7280; --hair:#e5e7eb;
  --accent:#4f46e5; --accent-2:#7c3aed; --accent-tint:#eef2ff;
  --code-bg:#f6f8fa; --code-ink:#24292f;
}
*{box-sizing:border-box}
@page{ size:A4; margin:16mm 18mm 18mm; }
html{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }
body{ font-family:"Segoe UI",-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif;
  color:var(--ink); font-size:10.8pt; line-height:1.62; margin:0; }
a{ color:var(--accent); text-decoration:none; }
code,pre{ font-family:"Cascadia Code",Consolas,"SFMono-Regular",Menlo,monospace; }

.cover{ min-height:84vh; display:flex; flex-direction:column; justify-content:center;
  break-after:page; page-break-after:always; }
.cover .kicker{ font-size:10.5pt; letter-spacing:.18em; text-transform:uppercase;
  color:var(--accent); font-weight:700; }
.cover .accent-bar{ height:6px; width:120px; margin:14px 0 26px;
  background:linear-gradient(90deg,var(--accent),var(--accent-2)); border-radius:3px; }
.cover-title{ font-size:31pt; line-height:1.15; font-weight:800; margin:0 0 14px;
  letter-spacing:-.01em; border:0; padding:0; }
.cover-sub{ font-size:14pt; color:var(--muted); margin:0; max-width:32em; }
.cover-meta{ margin-top:auto; padding-top:26px; display:flex; justify-content:space-between;
  font-size:9.5pt; color:var(--muted); border-top:1px solid var(--hair); }

.doc h1,.doc h2,.doc h3,.doc h4{ line-height:1.25; font-weight:700; margin:1.5em 0 .5em; }
.doc h1{ font-size:19pt; padding-bottom:.24em; border-bottom:2px solid var(--accent); }
.doc h2{ font-size:15pt; margin-top:1.7em; padding-left:.5em; border-left:4px solid var(--accent); }
.doc h3{ font-size:12.5pt; color:#111827; }
.doc h4{ font-size:10.5pt; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
.doc p{ margin:.55em 0; }
.doc ul,.doc ol{ margin:.5em 0; padding-left:1.5em; }
.doc li{ margin:.24em 0; }
.doc li>ul,.doc li>ol{ margin:.2em 0; }
.doc blockquote{ margin:1em 0; padding:.55em 1em; background:var(--accent-tint);
  border-left:4px solid var(--accent); border-radius:0 6px 6px 0; color:#3730a3; }
.doc blockquote p{ margin:.3em 0; }
.doc hr{ border:0; border-top:1px solid var(--hair); margin:1.6em 0; }
.doc code{ background:var(--code-bg); color:var(--code-ink); padding:.12em .38em;
  border-radius:4px; font-size:.86em; border:1px solid var(--hair); }
.doc pre{ background:var(--code-bg); border:1px solid var(--hair); border-radius:8px;
  padding:.9em 1em; overflow:auto; font-size:8.9pt; line-height:1.5; }
.doc pre code{ background:none; border:0; padding:0; font-size:inherit; }
.doc table{ border-collapse:collapse; width:100%; margin:1em 0; font-size:9.6pt; }
.doc th,.doc td{ border:1px solid var(--hair); padding:.5em .7em; text-align:left; vertical-align:top; }
.doc thead th{ background:var(--accent-tint); color:#3730a3; font-weight:700; }
.doc tbody tr:nth-child(even){ background:#fafafa; }
.doc img{ max-width:100%; }
.doc h2,.doc h3{ break-after:avoid; }
.doc pre,.doc table,.doc blockquote{ break-inside:avoid; }
"""


def build_html(body: str, title: str, subtitle: str, date: str, cover: bool = True) -> str:
    sub = f'<p class="cover-sub">{html.escape(subtitle)}</p>' if subtitle else ""
    cover_html = f"""<section class="cover">
  <div class="kicker">Agentic Work Best Practices</div>
  <div class="accent-bar"></div>
  <h1 class="cover-title">{html.escape(title)}</h1>
  {sub}
  <div class="cover-meta"><span>{html.escape(date)}</span><span>Source of truth &middot; SebsKk/AgenticWorkBestPractices</span></div>
</section>""" if cover else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>{CSS}</style></head>
<body>
{cover_html}
<main class="doc">
{body}
</main>
</body></html>"""


# --------------------------------------------------------------------------- #
#  Chrome / Edge rendering
# --------------------------------------------------------------------------- #

def find_browser(explicit: str | None = None) -> str | None:
    cands = [explicit, os.environ.get("CHROME_PATH"),
             r"C:\Program Files\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
             os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
             r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    for name in ("chrome", "google-chrome", "chromium", "msedge"):
        p = shutil.which(name)
        if p:
            return p
    return None


def render_pdf(html_path: str, pdf_path: str, browser: str | None = None) -> None:
    exe = find_browser(browser)
    if not exe:
        raise SystemExit("No Chrome/Edge found. Install Chrome or set CHROME_PATH.")
    profile = tempfile.mkdtemp(prefix="cpdf-")
    uri = Path(html_path).resolve().as_uri()
    try:
        for headless in ("--headless=new", "--headless"):
            cmd = [exe, headless, "--disable-gpu", "--no-first-run",
                   "--no-default-browser-check", f"--user-data-dir={profile}",
                   "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}", uri]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if os.path.isfile(pdf_path) and os.path.getsize(pdf_path) > 0:
                return
        raise SystemExit(f"PDF not produced.\nSTDERR:\n{res.stderr}")
    finally:
        shutil.rmtree(profile, ignore_errors=True)


# --------------------------------------------------------------------------- #

def _first_h1(md: str) -> str | None:
    m = re.search(r"^\s*#\s+(.*)$", md, re.MULTILINE)
    return m.group(1).strip() if m else None


def _strip_leading_h1(md: str) -> str:
    return re.sub(r"^\s*#\s+.*(?:\r?\n)+", "", md, count=1) if re.match(r"^\s*#\s+", md.lstrip("\n")) else md


def main() -> None:
    ap = argparse.ArgumentParser(description="Render Markdown to a styled PDF via headless Chrome.")
    ap.add_argument("--in", dest="inp", required=True, help="input .md path")
    ap.add_argument("--out", dest="out", required=True, help="output .pdf path")
    ap.add_argument("--title", default=None)
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--date", default="")
    ap.add_argument("--chrome", default=None, help="explicit browser exe path")
    ap.add_argument("--keep-html", action="store_true", help="keep the intermediate .html next to the PDF")
    ap.add_argument("--no-cover", action="store_true", help="omit the full-page cover (for compact one-page artifacts)")
    a = ap.parse_args()

    md = Path(a.inp).read_text(encoding="utf-8")
    title = a.title or _first_h1(md) or Path(a.inp).stem
    body = md_to_html(_strip_leading_h1(md))
    doc = build_html(body, title, a.subtitle, a.date, cover=not a.no_cover)

    out_path = Path(a.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if a.keep_html:
        html_path = out_path.with_suffix(".html")
        html_path.write_text(doc, encoding="utf-8")
    else:
        fd, tmp = tempfile.mkstemp(prefix="cpdf-", suffix=".html")
        os.close(fd)
        html_path = Path(tmp)
        html_path.write_text(doc, encoding="utf-8")

    try:
        render_pdf(str(html_path), str(out_path), a.chrome)
    finally:
        if not a.keep_html:
            try:
                html_path.unlink()
            except OSError:
                pass
    print(f"OK: {out_path}  ({out_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
