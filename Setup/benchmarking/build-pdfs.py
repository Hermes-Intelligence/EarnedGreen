"""Build the human benchmarking PDFs from canonical Markdown.

Markdown remains the source of truth. This renderer is intentionally local,
deterministic, and network-free so a fresh clone can reproduce the PDFs.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    PageBreak,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent
INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#5C667A")
ACCENT = colors.HexColor("#3167E3")
ACCENT_DARK = colors.HexColor("#214DB0")
PALE = colors.HexColor("#EEF3FF")
LINE = colors.HexColor("#DCE3F0")
CODE_BG = colors.HexColor("#121827")


def register_fonts() -> tuple[str, str, str]:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    bold_candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    mono_candidates = [
        Path("C:/Windows/Fonts/consola.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    ]
    try:
        regular = next(path for path in candidates if path.exists())
        bold = next(path for path in bold_candidates if path.exists())
        mono = next(path for path in mono_candidates if path.exists())
        pdfmetrics.registerFont(TTFont("AgenticSans", str(regular)))
        pdfmetrics.registerFont(TTFont("AgenticSansBold", str(bold)))
        pdfmetrics.registerFont(TTFont("AgenticMono", str(mono)))
        pdfmetrics.registerFontFamily("AgenticSans", normal="AgenticSans", bold="AgenticSansBold")
        return "AgenticSans", "AgenticSansBold", "AgenticMono"
    except (StopIteration, OSError):
        return "Helvetica", "Helvetica-Bold", "Courier"


FONT, FONT_BOLD, FONT_MONO = register_fonts()


def inline_markup(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        lambda m: f'<a href="{m.group(2)}" color="{ACCENT.hexval()}"><u>{m.group(1)}</u></a>',
        escaped,
    )
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"`([^`]+)`", lambda m: f'<font name="{FONT_MONO}" color="#263B68">{m.group(1)}</font>', escaped)
    return escaped


def styles(compact: bool = False):
    base = getSampleStyleSheet()
    body_size = 8.7 if compact else 9.2
    leading = 11.2 if compact else 12.2
    return {
        "title": ParagraphStyle("Title", parent=base["Title"], fontName=FONT_BOLD, fontSize=25 if not compact else 20, leading=28, textColor=INK, alignment=TA_LEFT, spaceAfter=7 * mm),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], fontName=FONT_BOLD, fontSize=15 if not compact else 12, leading=18, textColor=ACCENT_DARK, spaceBefore=4 * mm, spaceAfter=2.2 * mm, keepWithNext=True),
        "h3": ParagraphStyle("H3", parent=base["Heading3"], fontName=FONT_BOLD, fontSize=11.2, leading=14, textColor=INK, spaceBefore=3 * mm, spaceAfter=1.5 * mm, keepWithNext=True),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontName=FONT, fontSize=body_size, leading=leading, textColor=INK, spaceAfter=2.1 * mm),
        "bullet": ParagraphStyle("Bullet", parent=base["BodyText"], fontName=FONT, fontSize=body_size, leading=leading, textColor=INK, leftIndent=5 * mm, firstLineIndent=-3.5 * mm, bulletIndent=1 * mm, spaceAfter=1.2 * mm),
        "code": ParagraphStyle("Code", parent=base["Code"], fontName=FONT_MONO, fontSize=7.5, leading=10, textColor=colors.white, backColor=CODE_BG, borderPadding=7, spaceBefore=1 * mm, spaceAfter=3 * mm),
        "small": ParagraphStyle("Small", parent=base["BodyText"], fontName=FONT, fontSize=7.5, leading=9.5, textColor=MUTED),
        "table": ParagraphStyle("Table", parent=base["BodyText"], fontName=FONT, fontSize=7.2 if not compact else 6.8, leading=9, textColor=INK),
    }


class NumberedDoc(BaseDocTemplate):
    def __init__(self, filename: Path, title: str, compact: bool = False):
        super().__init__(str(filename), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=19 * mm, bottomMargin=17 * mm, title=title, author="Agentic Work Best Practices")
        self.report_title = title
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="main")
        self.addPageTemplates(PageTemplate(id="standard", frames=frame, onPage=self.decorate))

    def decorate(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.line(self.leftMargin, A4[1] - 12 * mm, A4[0] - self.rightMargin, A4[1] - 12 * mm)
        canvas.setFont(FONT_BOLD, 7.5)
        canvas.setFillColor(ACCENT_DARK)
        canvas.drawString(self.leftMargin, A4[1] - 9.2 * mm, "AGENTIC WORK BEST PRACTICES")
        canvas.setFont(FONT, 7.2)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(A4[0] - self.rightMargin, 9 * mm, f"{self.report_title}  |  {doc.page}")
        canvas.restoreState()


def parse_table(lines: list[str], sty: dict) -> Table:
    rows = []
    for index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if index == 1 and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append([Paragraph(inline_markup(cell), sty["table"]) for cell in cells])
    widths = [174 * mm / len(rows[0])] * len(rows[0])
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def markdown_story(source: Path, compact: bool = False):
    sty = styles(compact)
    lines = source.read_text(encoding="utf-8-sig").splitlines()
    story = []
    paragraph = []
    in_code = False
    code = []

    def flush_paragraph():
        if paragraph:
            story.append(Paragraph(inline_markup(" ".join(part.strip() for part in paragraph)), sty["body"]))
            paragraph.clear()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("```"):
            flush_paragraph()
            if in_code:
                story.append(Paragraph("<br/>".join(html.escape(item) or " " for item in code), sty["code"]))
                code.clear()
            in_code = not in_code
            i += 1
            continue
        if in_code:
            code.append(line)
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and lines[i + 1].startswith("|"):
            flush_paragraph()
            table_lines = []
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            story.extend([parse_table(table_lines, sty), Spacer(1, 2.5 * mm)])
            continue
        if not line.strip():
            flush_paragraph()
        elif line.startswith("# "):
            flush_paragraph(); story.append(Paragraph(inline_markup(line[2:]), sty["title"]))
        elif line.startswith("## "):
            flush_paragraph(); story.append(Paragraph(inline_markup(line[3:]), sty["h2"]))
        elif line.startswith("### "):
            flush_paragraph(); story.append(Paragraph(inline_markup(line[4:]), sty["h3"]))
        elif re.match(r"^[-*] ", line):
            flush_paragraph(); story.append(Paragraph(inline_markup(line[2:]), sty["bullet"], bulletText="-"))
        elif re.match(r"^\d+\. ", line):
            flush_paragraph(); number, text = line.split(". ", 1); story.append(Paragraph(inline_markup(text), sty["bullet"], bulletText=f"{number}."))
        else:
            paragraph.append(line)
        i += 1
    flush_paragraph()
    return story


def build(source_name: str, output_name: str, title: str, compact: bool = False):
    source = ROOT / source_name
    output = ROOT / output_name
    doc = NumberedDoc(output, title, compact=compact)
    doc.build(markdown_story(source, compact=compact))


if __name__ == "__main__":
    build("benchmarking-handbook.md", "benchmarking-handbook.pdf", "Benchmarking Handbook")
    build("quick-reference.md", "quick-reference.pdf", "Benchmarking Quick Reference", compact=True)
    print("Built benchmarking-handbook.pdf and quick-reference.pdf")
