"""Componentes editoriais do PDF, com tabelas legíveis e navegação interna."""
from __future__ import annotations

import html
from pathlib import Path

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, LongTable, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

INK = colors.HexColor("#183447")
TEAL = colors.HexColor("#12677A")
MUTED = colors.HexColor("#536777")
PALE = colors.HexColor("#EDF4F7")
WIDTH = A4[0] - 88


def pdf_styles():
    fonts = Path(matplotlib.get_data_path()) / "fonts/ttf"
    for name, file in (("DejaVu", "DejaVuSans.ttf"), ("DejaVu-Bold", "DejaVuSans-Bold.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(fonts / file)))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu", boldItalic="DejaVu-Bold")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Text", fontName="DejaVu", fontSize=10, leading=15, textColor=INK,
                              spaceAfter=8, splitLongWords=True, allowWidows=0, allowOrphans=0))
    for name, size, leading, color in (("Chapter", 20, 25, TEAL), ("Subhead", 12, 17, INK),
                                       ("Cover", 30, 36, INK), ("Deck", 13, 20, MUTED)):
        styles.add(ParagraphStyle(name, parent=styles["Text"], fontName="DejaVu-Bold", fontSize=size,
                                  leading=leading, textColor=color, spaceBefore=12, spaceAfter=10,
                                  keepWithNext=name in ("Chapter", "Subhead")))
    for name, size, leading in (("Small", 8, 11), ("Cell", 8.8, 12), ("CellHead", 8.5, 11), ("Case", 9, 12)):
        styles.add(ParagraphStyle(name, parent=styles["Text"], fontSize=size, leading=leading,
                                  spaceAfter=0, textColor=MUTED if name == "Small" else INK))
    styles["CellHead"].fontName = "DejaVu-Bold"
    return styles


def p(text, styles, style="Text", *, markup=False):
    return Paragraph(str(text) if markup else html.escape(str(text)), styles[style])


def heading(text, key, styles, *, level=0):
    result = p(text, styles, "Chapter" if level == 0 else "Subhead")
    result.section_key = key
    result.outline_level = level
    result.section_title = text
    return result


def table(headers, rows, widths, styles, *, small=False, compact=False):
    style = "Small" if small else "Cell"
    cells = [[p(v, styles, "CellHead") for v in headers]]
    cells += [[p("—" if v is None else v, styles, style) for v in row] for row in rows]
    result = LongTable(cells, colWidths=widths, repeatRows=1, hAlign="LEFT", spaceAfter=10)
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCEBF0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7F9")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 3 if compact else 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 3 if compact else 6),
        ("LINEBELOW", (0, 0), (-1, 0), .6, TEAL),
    ]))
    return result


def callout(title, text, styles):
    box = Table([[p(title, styles, "Subhead")], [p(text, styles)]], colWidths=[WIDTH], hAlign="LEFT", spaceAfter=12)
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), .4, colors.HexColor("#C1D6DF")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 4), ("BOTTOMPADDING", (0, -1), (-1, -1), 9)]))
    return box


def picture(path, *, max_height=280):
    image = Image(str(path))
    scale = min(WIDTH / image.imageWidth, max_height / image.imageHeight)
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    image.hAlign = "CENTER"
    return image


class AnalysisPDF(BaseDocTemplate):
    def __init__(self, path, *, title, styles):
        super().__init__(str(path), pagesize=A4, leftMargin=44, rightMargin=44, topMargin=58,
                         bottomMargin=44, title=title, author="PauloHFA — fontes TSE e IBGE")
        self.styles = styles
        self.section_pages = {}
        self.current_section = "Análise presidencial"
        frame = Frame(44, 44, WIDTH, A4[1] - 102, id="body", leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0)
        self.addPageTemplates(PageTemplate(id="report", frames=[frame], onPageEnd=self.decorate))

    def beforeDocument(self):
        self.section_pages = {}
        self.current_section = "Análise presidencial"

    def afterFlowable(self, flowable):
        if not hasattr(flowable, "section_key"):
            return
        key, title, level = flowable.section_key, flowable.section_title, flowable.outline_level
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(title, key, level=level, closed=False)
        self.section_pages[key] = self.page
        self.notify("TOCEntry", (level, title, self.page, key))
        if level == 0:
            self.current_section = title

    def decorate(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D3E0E7"))
        canvas.line(44, A4[1] - 34, A4[0] - 44, A4[1] - 34)
        canvas.setFont("DejaVu", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(44, A4[1] - 26, "ELEIÇÕES PRESIDENCIAIS  •  ANÁLISE DE DADOS AGREGADOS")
        footer = self.current_section
        while pdfmetrics.stringWidth(footer, "DejaVu", 7.5) > WIDTH - 80:
            footer = footer[:-4] + "…"
        canvas.setFont("DejaVu", 7.5)
        canvas.drawString(44, 25, footer)
        canvas.drawRightString(A4[0] - 44, 25, f"Página {doc.page}")
        canvas.restoreState()


def contents(styles):
    result = TableOfContents()
    result.levelStyles = [ParagraphStyle("TOC0", parent=styles["Text"], fontSize=10.5, leading=17,
                                         spaceBefore=7, leftIndent=0, firstLineIndent=0, alignment=TA_LEFT),
                          ParagraphStyle("TOC1", parent=styles["Small"], leftIndent=12, spaceBefore=3)]
    result.dotsMinLevel = 0
    return result
