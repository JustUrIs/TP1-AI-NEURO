"""
Renderiza un Markdown a PDF con reportlab.

No es un conversor general: cubre el subconjunto que usa el informe (titulos,
parrafos, listas, tablas, citas, bloques de codigo y enfasis en linea). Existe
porque el informe tiene un tope duro de 3 paginas y hace falta poder medirlo y
ajustarlo sin salir del repositorio.

    python build_pdf.py informe.md informe.pdf
"""

from __future__ import annotations

import html
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BODY = 8.65
LEAD = 10.9
INK = colors.HexColor("#16181d")
MUTED = colors.HexColor("#5b6270")
RULE = colors.HexColor("#c9cdd6")
BAND = colors.HexColor("#eef0f4")
ACCENT = colors.HexColor("#1b3a6b")


def styles():
    base = getSampleStyleSheet()
    s = {}
    s["title"] = ParagraphStyle(
        "title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=14.5,
        leading=16.5, spaceAfter=1, textColor=ACCENT, alignment=0,
    )
    s["subtitle"] = ParagraphStyle(
        "subtitle", parent=base["Normal"], fontName="Helvetica", fontSize=8.2,
        leading=10, textColor=MUTED, spaceAfter=7,
    )
    s["h2"] = ParagraphStyle(
        "h2", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10.0,
        leading=11.8, textColor=ACCENT, spaceBefore=6.5, spaceAfter=2.5,
    )
    s["h3"] = ParagraphStyle(
        "h3", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9.2,
        leading=11, textColor=INK, spaceBefore=5, spaceAfter=2,
    )
    s["body"] = ParagraphStyle(
        "body", parent=base["Normal"], fontName="Helvetica", fontSize=BODY,
        leading=LEAD, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=3.0,
    )
    s["quote"] = ParagraphStyle(
        "quote", parent=s["body"], leftIndent=8, rightIndent=6, spaceBefore=3,
        spaceAfter=4, textColor=ACCENT, fontName="Helvetica-Bold", borderPadding=3,
    )
    s["code"] = ParagraphStyle(
        "code", parent=base["Normal"], fontName="Courier", fontSize=7.6,
        leading=9.2, textColor=INK, leftIndent=6, spaceBefore=2, spaceAfter=4,
    )
    s["cell"] = ParagraphStyle(
        "cell", parent=base["Normal"], fontName="Helvetica", fontSize=7.5,
        leading=8.8, textColor=INK,
    )
    s["cellhead"] = ParagraphStyle(
        "cellhead", parent=s["cell"], fontName="Helvetica-Bold", textColor=ACCENT,
    )
    s["bullet"] = ParagraphStyle("bullet", parent=s["body"], spaceAfter=1.5)
    return s


def inline(text: str) -> str:
    """
    Markdown en linea -> marcado de reportlab.

    El orden importa y es la parte delicada. Los tramos de codigo se sacan
    primero y se reponen al final: si no, un asterisco adentro de `codigo` se
    interpreta como enfasis y las etiquetas quedan cruzadas (<font><i></font>),
    que es un error de parseo, no un problema estetico.
    """
    spans: list[str] = []

    def grab(m):
        spans.append(m.group(1))
        return "\x00%d\x00" % (len(spans) - 1)

    text = re.sub(r"`([^`]+)`", grab, text)
    text = text.replace("\\*", "\x01")          # asterisco escapado en el markdown
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)

    # Helvetica no trae superindices unicode: se mapean a <super>, que reportlab
    # si sabe dibujar. Sin esto salen cuadrados negros.
    sup = {"\u2070": "0", "\u00b9": "1", "\u00b2": "2", "\u00b3": "3", "\u2074": "4",
           "\u2075": "5", "\u2076": "6", "\u2077": "7", "\u2078": "8", "\u2079": "9",
           "\u207b": "-"}
    out, run = [], []
    for ch in text:
        if ch in sup:
            run.append(sup[ch])
            continue
        if run:
            out.append("<super>" + "".join(run) + "</super>")
            run = []
        out.append(ch)
    if run:
        out.append("<super>" + "".join(run) + "</super>")
    text = "".join(out)

    text = text.replace("\x01", "*")
    text = re.sub(
        "\x00(\\d+)\x00",
        lambda m: '<font face="Courier" size="7.6">'
        + html.escape(spans[int(m.group(1))], quote=False)
        + "</font>",
        text,
    )
    return text


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def build(md_path: str, pdf_path: str) -> int:
    s = styles()
    raw = open(md_path, encoding="utf-8").read().split("\n")
    flow: list = []
    i, n = 0, len(raw)
    first_heading = True

    while i < n:
        line = raw[i]

        if not line.strip():
            i += 1
            continue

        # --- regla horizontal
        if line.strip() == "---":
            flow.append(Spacer(1, 1.5))
            flow.append(HRFlowable(width="100%", thickness=0.5, color=RULE, spaceAfter=3))
            i += 1
            continue

        # --- bloque de codigo
        if line.startswith("```"):
            i += 1
            buf = []
            while i < n and not raw[i].startswith("```"):
                buf.append(raw[i])
                i += 1
            i += 1
            body = "<br/>".join(html.escape(x, quote=False).replace(" ", "&nbsp;") for x in buf)
            tbl = Table([[Paragraph(body, s["code"])]], colWidths=[176 * mm])
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), BAND),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            flow.append(tbl)
            flow.append(Spacer(1, 3))
            continue

        # --- tabla
        if line.strip().startswith("|") and i + 1 < n and set(raw[i + 1].replace("|", "").strip()) <= set("-: "):
            header = split_row(line)
            i += 2
            rows = []
            while i < n and raw[i].strip().startswith("|"):
                rows.append(split_row(raw[i]))
                i += 1
            data = [[Paragraph(inline(c), s["cellhead"]) for c in header]]
            data += [[Paragraph(inline(c), s["cell"]) for c in r] for r in rows]

            ncol = len(header)
            first = 0.40 if ncol >= 3 else 0.52
            widths = [176 * mm * first] + [176 * mm * (1 - first) / (ncol - 1)] * (ncol - 1) if ncol > 1 else [172 * mm]
            tbl = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), BAND),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, RULE),
                ("LINEBELOW", (0, 1), (-1, -2), 0.25, colors.HexColor("#e4e6ec")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2.2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
            ]))
            flow.append(Spacer(1, 1.5))
            flow.append(tbl)
            flow.append(Spacer(1, 4))
            continue

        # --- cita
        if line.startswith(">"):
            buf = []
            while i < n and raw[i].startswith(">"):
                buf.append(raw[i].lstrip("> ").rstrip())
                i += 1
            para = Paragraph(inline(" ".join(x for x in buf if x)), s["quote"])
            tbl = Table([[para]], colWidths=[176 * mm])
            tbl.setStyle(TableStyle([
                ("LINEBEFORE", (0, 0), (0, -1), 2, ACCENT),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            flow.append(tbl)
            flow.append(Spacer(1, 3))
            continue

        # --- lista
        if re.match(r"^[-*] ", line):
            items = []
            while i < n and re.match(r"^[-*] ", raw[i]):
                text = raw[i][2:].rstrip()
                i += 1
                while i < n and raw[i].startswith("  ") and raw[i].strip():
                    text += " " + raw[i].strip()
                    i += 1
                items.append(ListItem(Paragraph(inline(text), s["bullet"]), leftIndent=11))
            flow.append(ListFlowable(items, bulletType="bullet", start="•",
                                     bulletFontSize=6, leftIndent=11, bulletOffsetY=1))
            flow.append(Spacer(1, 2.5))
            continue

        # --- imagen
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", line.strip())
        if m:
            from reportlab.platypus import Image
            from PIL import Image as PILImage
            path = m.group(2)
            with PILImage.open(path) as im:
                w, h = im.size
            width = 152 * mm
            flow.append(Spacer(1, 2))
            flow.append(Image(path, width=width, height=width * h / w))
            if m.group(1):
                flow.append(Paragraph(inline(m.group(1)), s["subtitle"]))
            flow.append(Spacer(1, 3))
            i += 1
            continue

        # --- titulos
        if line.startswith("### "):
            flow.append(Paragraph(inline(line[4:]), s["h3"]))
            i += 1
            continue
        if line.startswith("## "):
            flow.append(Paragraph(inline(line[3:]), s["h2"]))
            i += 1
            continue
        if line.startswith("# "):
            flow.append(Paragraph(inline(line[2:]), s["title"]))
            i += 1
            first_heading = False
            continue

        # --- parrafo
        buf = [line.rstrip()]
        i += 1
        while i < n and raw[i].strip() and not re.match(r"^(#|\||>|```|!\[|[-*] |---$)", raw[i]):
            buf.append(raw[i].rstrip())
            i += 1
        text = " ".join(buf)
        style = s["subtitle"] if (not first_heading and text.startswith("**Trabajo")) else s["body"]
        flow.append(Paragraph(inline(text), style))
        if style is s["subtitle"]:
            first_heading = True

    doc = SimpleDocTemplate(
        pdf_path, pagesize=A4,
        leftMargin=17 * mm, rightMargin=17 * mm,
        topMargin=13 * mm, bottomMargin=12 * mm,
        title="Gold Dice RL - TP1", author="",
    )

    pages = {"n": 0}

    def footer(canvas, _doc):
        pages["n"] = max(pages["n"], canvas.getPageNumber())
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(A4[0] - 19 * mm, 9 * mm, str(canvas.getPageNumber()))
        canvas.restoreState()

    doc.build(flow, onFirstPage=footer, onLaterPages=footer)
    return pages["n"]


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "informe.md"
    dst = sys.argv[2] if len(sys.argv) > 2 else "informe.pdf"
    total = build(src, dst)
    print(f"{src} -> {dst}   {total} pagina(s)")
    if "informe.pdf" in dst and total > 3:
        print(f"  ATENCION: el enunciado permite hasta 3 paginas y salieron {total}.")
