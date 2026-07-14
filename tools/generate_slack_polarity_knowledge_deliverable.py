#!/usr/bin/env python3
import re
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "brain" / "knowledge" / "polarity" / "articles"
OUT_DIR = ROOT / "output" / "slack_codex_inbox" / "1783473037_022699"


def split_front_matter(text):
    if text.startswith("---\n"):
        _, fm, body = text.split("---\n", 2)
        return fm, body
    return "", text


def parse_meta(front_matter):
    meta = {}
    current = None
    for raw in front_matter.splitlines():
        line = raw.rstrip()
        if line.startswith("  - ") and current:
            meta.setdefault(current, []).append(line[4:].strip())
        elif ":" in line:
            key, value = line.split(":", 1)
            current = key.strip()
            value = value.strip().strip('"')
            meta[current] = value if value else []
    return meta


def title_from_body(body):
    match = re.search(r"^# (.+)$", body, flags=re.M)
    return match.group(1).strip() if match else "Sin titulo"


def clean_body(body):
    return body.strip()


def load_articles():
    articles = []
    for path in sorted(SOURCE_DIR.glob("*.md")):
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        fm, body = split_front_matter(text)
        meta = parse_meta(fm)
        articles.append(
            {
                "id": meta.get("id", path.stem),
                "title": title_from_body(body),
                "lane": meta.get("polarity_lane", "shared_principle"),
                "topics": meta.get("topics", []),
                "audience": meta.get("audience", []),
                "path": path.relative_to(ROOT).as_posix(),
                "body": clean_body(body),
            }
        )
    return articles


def lane_label(lane):
    return {
        "feminine_advice": "Knowledge femenino / usuaria",
        "masculine_advice": "Knowledge masculino / usuario hombre",
        "shared_principle": "Principios compartidos",
    }.get(lane or "shared_principle", lane or "Principios compartidos")


def write_markdown(articles):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md_path = OUT_DIR / "knowledge_polaridad_bot.md"
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    lanes = ["shared_principle", "feminine_advice", "masculine_advice"]
    lines = [
        "# Knowledge para bot - polaridad, apego ansioso y dinamicas masculino/femenino",
        "",
        f"Generado: {generated}",
        "",
        "Este archivo agrupa el knowledge curado en bloques autocontenidos para recuperacion por IA. No sustituye los articulos fuente: los une en una copia de trabajo pensada para busqueda, lectura y uso del bot.",
        "",
        "## Como debe usarlo el bot",
        "",
        "- Priorizar seguridad emocional, consentimiento, reciprocidad, agencia y limites.",
        "- Elegir el bloque por situacion del usuario, no por titulo literal del documento original.",
        "- Usar el campo de audiencia como pista, pero no convertirlo en dogma de genero.",
        "- No prometer curacion definitiva ni recomendar permanecer en relaciones con abuso, desprecio o manipulacion.",
        "- Cuando una idea sea de polaridad, traducirla a conducta concreta y observable.",
        "",
        "## Mapa de recuperacion",
        "",
    ]
    for lane in lanes:
        selected = [a for a in articles if (a["lane"] or "shared_principle") == lane]
        if not selected:
            continue
        lines.append(f"### {lane_label(lane)}")
        lines.append("")
        for article in selected:
            topics = ", ".join(article["topics"] if isinstance(article["topics"], list) else [])
            audience = ", ".join(article["audience"] if isinstance(article["audience"], list) else [])
            lines.append(f"- `{article['id']}`: {article['title']}. Audiencia: {audience or 'general'}. Temas: {topics or 'sin etiquetar'}.")
        lines.append("")
    lines.extend(["---", ""])
    for lane in lanes:
        selected = [a for a in articles if (a["lane"] or "shared_principle") == lane]
        if not selected:
            continue
        lines.append(f"# {lane_label(lane)}")
        lines.append("")
        for article in selected:
            lines.extend(
                [
                    f"<!-- source: {article['path']} -->",
                    f"<!-- retrieval_id: {article['id']} -->",
                    "",
                    article["body"],
                    "",
                    "---",
                    "",
                ]
            )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def html_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def markdown_to_flowables(markdown, styles):
    flowables = []
    in_list = False
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line or line.startswith("<!--"):
            in_list = False
            if not line:
                flowables.append(Spacer(1, 4))
            continue
        if line == "---":
            flowables.append(Spacer(1, 8))
            in_list = False
            continue
        if line.startswith("# "):
            if flowables:
                flowables.append(PageBreak())
            flowables.append(Paragraph(html_escape(line[2:]), styles["Title"]))
        elif line.startswith("## "):
            flowables.append(Paragraph(html_escape(line[3:]), styles["H2"]))
        elif line.startswith("### "):
            flowables.append(Paragraph(html_escape(line[4:]), styles["H3"]))
        elif line.startswith("- "):
            flowables.append(Paragraph("- " + html_escape(line[2:]), styles["Bullet"]))
            in_list = True
        else:
            if in_list:
                flowables.append(Spacer(1, 3))
                in_list = False
            flowables.append(Paragraph(html_escape(line), styles["Body"]))
    return flowables


def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Arial", 8)
    canvas.setFillColor(colors.HexColor("#52606D"))
    canvas.drawString(2 * cm, 1.1 * cm, "Knowledge polaridad bot")
    canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, str(doc.page))
    canvas.restoreState()


def write_pdf(markdown):
    pdf_path = OUT_DIR / "knowledge_polaridad_bot.pdf"
    pdfmetrics.registerFont(TTFont("Arial", "/System/Library/Fonts/Supplemental/Arial.ttf"))
    pdfmetrics.registerFont(TTFont("Arial-Bold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"))
    base = getSampleStyleSheet()
    styles = {
        "Title": ParagraphStyle("Title", parent=base["Title"], fontName="Arial-Bold", fontSize=20, leading=25, alignment=TA_LEFT, spaceAfter=12, textColor=colors.HexColor("#102A43")),
        "H2": ParagraphStyle("H2", parent=base["Heading2"], fontName="Arial-Bold", fontSize=14, leading=18, spaceBefore=8, spaceAfter=6, textColor=colors.HexColor("#243B53")),
        "H3": ParagraphStyle("H3", parent=base["Heading3"], fontName="Arial-Bold", fontSize=11.5, leading=15, spaceBefore=7, spaceAfter=4, textColor=colors.HexColor("#334E68")),
        "Body": ParagraphStyle("Body", parent=base["BodyText"], fontName="Arial", fontSize=9, leading=12.8, alignment=TA_JUSTIFY, spaceAfter=4),
        "Bullet": ParagraphStyle("Bullet", parent=base["BodyText"], fontName="Arial", fontSize=8.7, leading=12.4, leftIndent=10, firstLineIndent=-7, spaceAfter=2),
    }
    doc = BaseDocTemplate(str(pdf_path), pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=1.8 * cm)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="body", frames=[frame], onPage=add_page_number)])
    doc.build(markdown_to_flowables(markdown, styles))
    return pdf_path


def main():
    articles = load_articles()
    md_path = write_markdown(articles)
    pdf_path = write_pdf(md_path.read_text(encoding="utf-8"))
    print(md_path)
    print(pdf_path)
    print(f"articles={len(articles)}")


if __name__ == "__main__":
    main()
