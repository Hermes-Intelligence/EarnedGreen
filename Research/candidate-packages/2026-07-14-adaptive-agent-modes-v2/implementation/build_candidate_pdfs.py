#!/usr/bin/env python3
"""Generate the Candidate report and human mode guide from canonical Markdown."""
from __future__ import annotations

import html, re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

HERE=Path(__file__).resolve().parent; CANDIDATE=HERE.parent
NAVY=colors.HexColor("#132238"); BLUE=colors.HexColor("#2364AA"); CYAN=colors.HexColor("#27A7B8"); PALE=colors.HexColor("#EDF5F8"); INK=colors.HexColor("#243447"); MUTED=colors.HexColor("#66788A")


def inline(text):
    escaped=html.escape(text)
    escaped=re.sub(r"\[([^]]+)\]\((https?://[^)]+)\)",lambda m:f'<link href="{m.group(2)}" color="#2364AA"><u>{m.group(1)}</u></link>',escaped)
    # Relative links (sibling files) cannot be clickable in a standalone PDF:
    # render the label alone instead of leaking raw markdown brackets.
    escaped=re.sub(r"\[([^]]+)\]\((?!https?://)[^)]+\)",r"\1",escaped)
    # Code spans are extracted to placeholders BEFORE emphasis: a literal
    # asterisk inside `codex/*` must never open an <i> that then closes across
    # the </font> boundary (reportlab rejects crossed tags outright).
    spans=[]
    def _stash(m):
        spans.append(m.group(1)); return f"\x00{len(spans)-1}\x00"
    escaped=re.sub(r"`([^`]+)`",_stash,escaped)
    escaped=re.sub(r"\*\*([^*]+)\*\*",r'<b>\1</b>',escaped)
    # Single-asterisk emphasis runs AFTER bold so **x** is not eaten as *…*.
    escaped=re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)",r'<i>\1</i>',escaped)
    for index,span in enumerate(spans):
        escaped=escaped.replace(f"\x00{index}\x00",f'<font name="Courier" color="#173F5F">{span}</font>')
    return escaped


def styles():
    s=getSampleStyleSheet()
    return {
        "title":ParagraphStyle("Title",parent=s["Title"],fontName="Helvetica-Bold",fontSize=25,leading=29,textColor=NAVY,spaceAfter=8*mm),
        "h1":ParagraphStyle("H1",parent=s["Heading1"],fontName="Helvetica-Bold",fontSize=17,leading=21,textColor=NAVY,spaceBefore=5*mm,spaceAfter=2.5*mm),
        "h2":ParagraphStyle("H2",parent=s["Heading2"],fontName="Helvetica-Bold",fontSize=13,leading=16,textColor=BLUE,spaceBefore=4*mm,spaceAfter=2*mm),
        "h3":ParagraphStyle("H3",parent=s["Heading3"],fontName="Helvetica-Bold",fontSize=10.5,leading=13,textColor=CYAN,spaceBefore=3*mm,spaceAfter=1.5*mm),
        "body":ParagraphStyle("Body",parent=s["BodyText"],fontName="Helvetica",fontSize=8.7,leading=12.2,textColor=INK,spaceAfter=2.1*mm),
        "bullet":ParagraphStyle("Bullet",parent=s["BodyText"],fontName="Helvetica",fontSize=8.4,leading=11.6,leftIndent=5*mm,firstLineIndent=-3.5*mm,textColor=INK,spaceAfter=1.3*mm),
        "status":ParagraphStyle("Status",parent=s["BodyText"],fontName="Helvetica-Bold",fontSize=9.3,leading=13,textColor=BLUE,backColor=PALE,borderPadding=7,spaceAfter=5*mm),
        "cell":ParagraphStyle("Cell",parent=s["BodyText"],fontName="Helvetica",fontSize=7.1,leading=9,textColor=INK),
        "cellh":ParagraphStyle("CellH",parent=s["BodyText"],fontName="Helvetica-Bold",fontSize=7.2,leading=9,textColor=colors.white,alignment=TA_CENTER),
    }


CANDIDATE_FOOTER="Candidate evidence - not Stable guidance"


def header_footer(canvas,doc,footer=CANDIDATE_FOOTER):
    canvas.saveState(); w,h=A4
    canvas.setFillColor(NAVY); canvas.rect(0,h-13*mm,w,13*mm,fill=1,stroke=0)
    canvas.setFillColor(colors.white); canvas.setFont("Helvetica-Bold",8); canvas.drawString(18*mm,h-8.2*mm,"AGENTIC WORK BEST PRACTICES")
    canvas.setFillColor(MUTED); canvas.setFont("Helvetica",7.5); canvas.drawString(18*mm,9*mm,footer)
    canvas.drawRightString(w-18*mm,9*mm,f"{doc.page}"); canvas.restoreState()


def markdown_story(path):
    st=styles(); lines=path.read_text(encoding="utf-8-sig").splitlines(); story=[]; i=0; first=True
    while i<len(lines):
        line=lines[i].strip()
        if not line: i+=1; continue
        if line.startswith("|" ) and i+1<len(lines) and re.match(r"^\|?[ :|-]+\|",lines[i+1].strip()):
            raw=[]
            while i<len(lines) and lines[i].strip().startswith("|"):
                raw.append([cell.strip() for cell in lines[i].strip().strip("|").split("|")]); i+=1
            raw.pop(1); data=[]
            for ridx,row in enumerate(raw): data.append([Paragraph(inline(cell),st["cellh" if ridx==0 else "cell"]) for cell in row])
            width=174*mm/len(data[0]); table=Table(data,colWidths=[width]*len(data[0]),repeatRows=1,hAlign="LEFT")
            table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY),("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#C7D6E0")),("BACKGROUND",(0,1),(-1,-1),colors.white),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)])); story += [table,Spacer(1,3*mm)]; continue
        if line.startswith("# "):
            if not first: story.append(PageBreak())
            story.append(Paragraph(inline(line[2:]),st["title"])); first=False
        elif line.startswith("## "): story.append(Paragraph(inline(line[3:]),st["h1"]))
        elif line.startswith("### "): story.append(Paragraph(inline(line[4:]),st["h2"]))
        elif line.startswith("Status:"): story.append(Paragraph(inline(line),st["status"]))
        elif re.match(r"^[-*] ",line): story.append(Paragraph("&#8226; "+inline(line[2:]),st["bullet"]))
        elif re.match(r"^\d+\. ",line): story.append(Paragraph(inline(line),st["bullet"]))
        elif line.startswith("```"):
            block=[]; i+=1
            while i<len(lines) and not lines[i].strip().startswith("```"): block.append(lines[i]); i+=1
            story.append(Paragraph("<font name='Courier'>"+"<br/>".join(html.escape(x) for x in block)+"</font>",st["body"]))
        else:
            paragraph=[line]
            while i+1<len(lines) and lines[i+1].strip() and not re.match(r"^(#|[-*] |\d+\. |\||```)",lines[i+1].strip()): i+=1; paragraph.append(lines[i].strip())
            story.append(Paragraph(inline(" ".join(paragraph)),st["body"]))
        i+=1
    return story


def build(source,output,footer=CANDIDATE_FOOTER):
    output.parent.mkdir(parents=True,exist_ok=True)
    doc=BaseDocTemplate(str(output),pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=20*mm,bottomMargin=16*mm,title=source.stem,author="AgenticWorkBestPractices")
    doc.addPageTemplates(PageTemplate(id="main",frames=[Frame(doc.leftMargin,doc.bottomMargin,doc.width,doc.height,id="body")],onPage=lambda c,d:header_footer(c,d,footer)))
    doc.build(markdown_story(source))


def main():
    build(CANDIDATE/"report.md",CANDIDATE/"report.pdf")
    # Payload docs become Stable on promotion, so they must not carry the
    # candidate-evidence footer.
    payload=CANDIDATE/"promotion/payload/Setup"
    for stem in (payload/"adaptive-modes", payload/"benchmarking/verification-loop-results"):
        build(stem.with_suffix(".md"),stem.with_suffix(".pdf"),footer="Stable guidance - promoted release")


if __name__=="__main__": main()
