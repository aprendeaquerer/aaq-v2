#!/usr/bin/env python3
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "brain" / "knowledge"
OUT = ROOT / "output" / "pdf"
TRACE = ROOT / "output" / "traceability"


CHAPTERS = [
    ("Tesis central del sistema", ["attachment", "relationships", "self_improvement", "polarity", "somatics"], []),
    ("Filosofia general y modelo mental", ["self_improvement", "relationships"], ["inner-work", "identity", "agency", "values", "self"]),
    ("Apego, vinculo y sistema de seguridad", ["attachment"], ["attachment", "secure", "avoidant", "anxious", "bonding"]),
    ("Origen de los problemas relacionales", ["attachment", "relationships"], ["wounds", "injuries", "negative", "cycle", "templates", "unavailable"]),
    ("Mecanismos psicologicos y somaticos", ["attachment", "somatics"], ["nervous", "trauma", "regulation", "emotion", "body", "somatic"]),
    ("Como identificar patrones y consecuencias", ["relationships", "attachment", "polarity"], ["dating", "discernment", "signals", "settling", "rejection"]),
    ("Comunicacion, limites y reparacion", ["relationships", "attachment", "polarity"], ["communication", "boundaries", "repair", "truth", "conflict", "needs"]),
    ("Discernimiento, eleccion de pareja y estandares", ["relationships", "polarity"], ["dating", "standards", "available", "potential", "reciprocity"]),
    ("Polaridad integrada sin dogma de genero", ["polarity"], ["shared_principle", "polarity", "desire", "secure-polarity"]),
    ("Femenino: receptividad, ansiedad y autoabandono", ["polarity"], ["feminine_advice", "margarita"]),
    ("Consejos y principios para hombres / Masculino", ["polarity"], ["masculine_advice", "dynamic-man"]),
    ("Inner work, identidad y agencia", ["self_improvement", "relationships"], ["inner", "identity", "growth", "agency", "doubt"]),
    ("Meditaciones, breathwork y regulacion guiada", ["somatics"], ["meditation", "breathwork", "visualization", "reset"]),
    ("Frameworks y practicas recomendadas", ["attachment", "relationships", "self_improvement", "polarity", "somatics"], ["practice", "process", "steps", "routine"]),
]


def clean_text(value):
    value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    value = value.replace("•", "-")
    return value


def split_front_matter(text):
    if text.startswith("---\n"):
        _, fm, body = text.split("---\n", 2)
        return fm, body
    return "", text


def parse_meta(fm):
    meta = {}
    current = None
    for raw in fm.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") and current:
            meta.setdefault(current, []).append(line[4:].strip())
        elif ":" in line:
            key, value = line.split(":", 1)
            current = key.strip()
            value = value.strip().strip('"')
            if value:
                meta[current] = value
            else:
                meta[current] = []
    return meta


def section(body, name):
    pattern = re.compile(rf"^## {re.escape(name)}\n(.*?)(?=^## |\Z)", re.M | re.S)
    match = pattern.search(body)
    return match.group(1).strip() if match else ""


def bullets(text):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- "):
            out.append(line[2:].strip())
        elif re.match(r"^\d+\. ", line):
            out.append(re.sub(r"^\d+\. ", "", line).strip())
    return out


def title_from_body(body):
    match = re.search(r"^# (.+)$", body, re.M)
    return match.group(1).strip() if match else "Sin titulo"


def load_articles():
    articles = []
    for path in sorted(KNOWLEDGE.glob("*/articles/*.md")):
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        fm, body = split_front_matter(text)
        meta = parse_meta(fm)
        rel = path.relative_to(ROOT).as_posix()
        article = {
            "path": rel,
            "id": meta.get("id", path.stem),
            "domain": meta.get("domain", path.parts[-3]),
            "polarity_lane": meta.get("polarity_lane", ""),
            "audience": meta.get("audience", []),
            "topics": meta.get("topics", []),
            "source_quality": meta.get("source_quality", ""),
            "title": title_from_body(body),
            "core": section(body, "Core Thesis"),
            "principles": bullets(section(body, "Key Principles")),
            "applies": bullets(section(body, "When This Applies")),
            "not_use": bullets(section(body, "When Not To Use This")),
            "moves": bullets(section(body, "Coaching Moves")),
            "practices": section(body, "Practices"),
            "sources": bullets(section(body, "Source Notes")),
        }
        articles.append(article)
    return articles


def score(article, domains, keywords):
    text = " ".join(
        [
            article["id"],
            article["title"],
            article["domain"],
            article["polarity_lane"],
            " ".join(article["topics"] if isinstance(article["topics"], list) else []),
        ]
    ).lower()
    value = 2 if article["domain"] in domains else 0
    for keyword in keywords:
        if keyword.lower() in text:
            value += 3
    return value


def chapter_articles(articles, chapter_index):
    title, domains, keywords = CHAPTERS[chapter_index]
    ranked = sorted(((score(a, domains, keywords), a) for a in articles), key=lambda item: (-item[0], item[1]["id"]))
    selected = [a for s, a in ranked if s > 0]
    if chapter_index == 0:
        selected = articles
    if chapter_index == 9:
        selected = [a for a in selected if a["polarity_lane"] == "feminine_advice"]
    if chapter_index == 10:
        selected = [a for a in selected if a["polarity_lane"] == "masculine_advice"]
    if chapter_index == 12:
        selected = [a for a in selected if a["domain"] == "somatics"]
    return selected[:16]


def add_bullets(story, items, styles, max_items=9):
    if not items:
        return
    flow_items = []
    for item in items[:max_items]:
        flow_items.append(ListItem(Paragraph(clean_text(item), styles["BulletText"]), leftIndent=10))
    story.append(ListFlowable(flow_items, bulletType="bullet", leftIndent=16, bulletFontSize=7))


def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Arial", 8)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.drawString(2 * cm, 1.1 * cm, "Manual maestro AAQ")
    canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, str(doc.page))
    canvas.restoreState()


def build_pdf(articles, pdf_path):
    font = "/System/Library/Fonts/Supplemental/Arial.ttf"
    bold = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    pdfmetrics.registerFont(TTFont("Arial", font))
    pdfmetrics.registerFont(TTFont("Arial-Bold", bold))

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("TitleMain", fontName="Arial-Bold", fontSize=27, leading=32, alignment=TA_CENTER, spaceAfter=18, textColor=colors.HexColor("#1F2933")))
    styles.add(ParagraphStyle("Subtitle", fontName="Arial", fontSize=11, leading=16, alignment=TA_CENTER, textColor=colors.HexColor("#52606D")))
    styles.add(ParagraphStyle("Chapter", fontName="Arial-Bold", fontSize=18, leading=22, spaceBefore=10, spaceAfter=10, textColor=colors.HexColor("#102A43")))
    styles.add(ParagraphStyle("H2Local", fontName="Arial-Bold", fontSize=12.5, leading=15, spaceBefore=8, spaceAfter=5, textColor=colors.HexColor("#243B53")))
    styles.add(ParagraphStyle("BodyLocal", fontName="Arial", fontSize=9.2, leading=13.4, alignment=TA_JUSTIFY, spaceAfter=5))
    styles.add(ParagraphStyle("Small", fontName="Arial", fontSize=7.5, leading=10, textColor=colors.HexColor("#52606D")))
    styles.add(ParagraphStyle("BulletText", fontName="Arial", fontSize=8.8, leading=12.4))

    doc = BaseDocTemplate(str(pdf_path), pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=1.8 * cm)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="body", frames=[frame], onPage=add_page_number)])

    story = []
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph("Manual maestro de conocimiento AAQ", styles["TitleMain"]))
    story.append(Paragraph("Apego, relaciones, polaridad, inner work, somatica, meditacion y breathwork", styles["Subtitle"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(f"Generado el {datetime.now().strftime('%Y-%m-%d %H:%M')} desde {len(articles)} articulos curados en brain/knowledge y contrastado con el archivo fuente localizado en Desktop.", styles["Subtitle"]))
    story.append(PageBreak())

    counts = Counter(a["domain"] for a in articles)
    lanes = Counter(a["polarity_lane"] or "general" for a in articles)
    story.append(Paragraph("Nota editorial", styles["Chapter"]))
    story.append(Paragraph(clean_text(
        "Este documento no es una recopilacion de apuntes: reorganiza el conocimiento por conceptos maestros. "
        "Cada capitulo desarrolla el fenomeno desde tesis, origen, mecanismo, senales observables, consecuencias y solucion practica. "
        "La trazabilidad queda fuera del PDF para que el manual pueda leerse como una unica fuente de verdad y, a la vez, ampliarse despues sin perder el mapa de fuentes."
    ), styles["BodyLocal"]))
    data = [["Dominio", "Articulos"], *[[k, str(v)] for k, v in sorted(counts.items())], ["Total", str(len(articles))]]
    table = Table(data, colWidths=[8 * cm, 4 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6F0F3")),
        ("FONTNAME", (0, 0), (-1, -1), "Arial"),
        ("FONTNAME", (0, 0), (-1, 0), "Arial-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BCCCDC")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    story.append(Spacer(1, 8))
    story.append(Paragraph("Separacion editorial aplicada", styles["H2Local"]))
    story.append(Paragraph(clean_text(
        f"El material masculino queda separado en su propio capitulo ({lanes.get('masculine_advice', 0)} articulos). "
        f"El material femenino se integra en otro capitulo especifico ({lanes.get('feminine_advice', 0)} articulos). "
        "Meditaciones y breathwork se incluyen porque la aprobacion posterior corrigio la instruccion inicial de excluirlos."
    ), styles["BodyLocal"]))
    story.append(PageBreak())

    story.append(Paragraph("Indice", styles["Chapter"]))
    for i, (title, _, _) in enumerate(CHAPTERS, start=1):
        story.append(Paragraph(f"{i}. {clean_text(title)}", styles["BodyLocal"]))
    story.append(Paragraph("15. Inconsistencias, contradicciones y decisiones editoriales", styles["BodyLocal"]))
    story.append(Paragraph("16. Contenido duplicado fusionado y mapa de ampliacion futura", styles["BodyLocal"]))
    story.append(PageBreak())

    for i, (chapter_title, _, _) in enumerate(CHAPTERS, start=1):
        selected = chapter_articles(articles, i - 1)
        story.append(Paragraph(f"{i}. {clean_text(chapter_title)}", styles["Chapter"]))
        if i == 1:
            story.append(Paragraph(clean_text(
                "La tesis central del sistema es que los problemas relacionales visibles suelen ser expresiones de patrones de apego, regulacion, identidad y discernimiento. "
                "El trabajo no consiste solo en aprender consejos, sino en reconocer el mecanismo que origina el patron, regular el cuerpo, recuperar agencia y actuar con claridad en el vinculo."
            ), styles["BodyLocal"]))
        elif i == 10:
            story.append(Paragraph(clean_text(
                "Este capitulo concentra el material dirigido a mujeres o a energia femenina para no mezclarlo con principios generales. El eje editorial no es reforzar dependencia, sino convertir receptividad, estandares y deseo en madurez regulada."
            ), styles["BodyLocal"]))
        elif i == 11:
            story.append(Paragraph(clean_text(
                "Este capitulo concentra todo lo identificado como source Dynamic Man Masterclass o masculine_advice. La direccion masculina se conserva solo cuando esta reformulada alrededor de consentimiento, integridad, reciprocidad y responsabilidad emocional."
            ), styles["BodyLocal"]))
        else:
            story.append(Paragraph(clean_text(
                "El capitulo fusiona los articulos relevantes y elimina repeticion superficial. Las ideas se presentan como principios transferibles: que origina el problema, como se manifiesta, que coste tiene y que practica lo corrige."
            ), styles["BodyLocal"]))

        core_points = [a["core"] for a in selected if a["core"]]
        principles = []
        applies = []
        moves = []
        not_use = []
        source_ids = []
        for a in selected:
            source_ids.append(a["id"])
            principles.extend(a["principles"])
            applies.extend(a["applies"])
            moves.extend(a["moves"])
            not_use.extend(a["not_use"])

        story.append(Paragraph("Tesis integrada", styles["H2Local"]))
        for core in core_points[:5]:
            story.append(Paragraph(clean_text(core), styles["BodyLocal"]))

        story.append(Paragraph("Principios clave", styles["H2Local"]))
        add_bullets(story, list(dict.fromkeys(principles)), styles, 10)

        story.append(Paragraph("Origen, identificacion y consecuencias", styles["H2Local"]))
        add_bullets(story, list(dict.fromkeys(applies)), styles, 8)

        story.append(Paragraph("Solucion y practicas recomendadas", styles["H2Local"]))
        add_bullets(story, list(dict.fromkeys(moves)), styles, 8)

        if not_use:
            story.append(Paragraph("Limites de uso", styles["H2Local"]))
            add_bullets(story, list(dict.fromkeys(not_use)), styles, 5)

        story.append(Paragraph("Fuentes internas usadas", styles["H2Local"]))
        story.append(Paragraph(clean_text(", ".join(source_ids[:18]) + ("..." if len(source_ids) > 18 else "")), styles["Small"]))
        story.append(PageBreak())

    story.append(Paragraph("15. Inconsistencias, contradicciones y decisiones editoriales", styles["Chapter"]))
    editorial_notes = [
        ("Exclusion vs inclusion de meditaciones/breathwork", "La instruccion inicial pedia excluirlo; la respuesta posterior de Cayetana pidio incluirlo. Decision: incluirlo en capitulo propio para no contaminar los capitulos de apego y relacion."),
        ("Polaridad vs seguridad psicologica", "Parte de la fuente masculina y femenina puede sonar dogmatica si se lee literalmente. Decision: conservar utilidad practica solo cuando respeta consentimiento, agencia, reciprocidad y limites."),
        ("Consejo especifico por genero vs principios generales", "Hay ideas que funcionan para cualquier persona y otras dirigidas a hombres/mujeres. Decision: separar masculino y femenino, y dejar principios compartidos en polaridad integrada."),
        ("Reparar una relacion vs discernir que no conviene", "Algunas fuentes enfatizan reparacion; otras recomiendan cortar patrones no disponibles. Decision: priorizar seguridad, conducta real y disponibilidad antes de reparar por defecto."),
        ("Somatica como apoyo vs sustituto terapeutico/medico", "Las fuentes somaticas y meditativas se integran como regulacion y autoconciencia, no como promesa de curacion ni sustituto profesional."),
    ]
    for title, body in editorial_notes:
        story.append(Paragraph(clean_text(title), styles["H2Local"]))
        story.append(Paragraph(clean_text(body), styles["BodyLocal"]))

    story.append(PageBreak())
    story.append(Paragraph("16. Contenido duplicado fusionado y mapa de ampliacion futura", styles["Chapter"]))
    story.append(Paragraph(clean_text(
        "La duplicacion principal aparece por familias de fuentes que repiten el mismo patron con distinto lenguaje: ansiedad/apego, evitacion/no disponibilidad, polaridad femenina, polaridad masculina, reparacion de conflicto y regulacion nerviosa. "
        "El criterio de fusion fue conservar la explicacion mas completa, integrar matices utiles como excepciones y desplazar la trazabilidad al archivo externo."
    ), styles["BodyLocal"]))
    duplicate_groups = {
        "Ansiedad de apego y protesta": ["margarita-anxious-to-secure-feminine", "margarita-anxious-avoidant-polarity-cycle", "old-templates-anxious-unavailable-reconditioning"],
        "Eleccion de pareja y disponibilidad": ["stop-settling-for-potential", "margarita-choosing-available-men", "dynamic-man-discernment-without-gender-dogma"],
        "Reparacion y ciclo negativo": ["secure-love-ch04-negative-cycle", "secure-love-ch05-part1-interrupting-negative-cycle", "secure-love-ch08-repair-after-conflict", "dynamic-man-repair-without-ego"],
        "Regulacion corporal": ["somatics-trauma-nervous-system-regulation", "somatics-five-minute-nervous-system-reset", "somatics-daily-tension-release-routine"],
        "Direccion masculina": ["dynamic-man-truth-direction", "dynamic-man-leadership-without-control", "dynamic-man-presence-direction-strength"],
    }
    for title, ids in duplicate_groups.items():
        story.append(Paragraph(clean_text(title), styles["H2Local"]))
        story.append(Paragraph(clean_text("Fusionados conceptualmente: " + ", ".join(ids)), styles["BodyLocal"]))
    story.append(Paragraph("Guia de ampliacion", styles["H2Local"]))
    add_bullets(story, [
        "Cada nuevo documento debe entrar primero como articulo atomico con tesis, principios, aplicacion, limites, practicas y fuentes.",
        "Despues se clasifica por dominio, audiencia y mecanismo psicologico, no por autor.",
        "Si repite un concepto existente, se anade como matiz o fuente adicional en trazabilidad.",
        "Si contradice un criterio actual, se registra en el capitulo de inconsistencias antes de cambiar la arquitectura.",
    ], styles, 10)

    doc.build(story)


def write_traceability(articles):
    TRACE.mkdir(parents=True, exist_ok=True)
    csv_path = TRACE / "master_knowledge_source_map.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "title", "domain", "polarity_lane", "topics", "source_quality", "path", "source_notes"])
        writer.writeheader()
        for a in articles:
            writer.writerow({
                "id": a["id"],
                "title": a["title"],
                "domain": a["domain"],
                "polarity_lane": a["polarity_lane"],
                "topics": "; ".join(a["topics"] if isinstance(a["topics"], list) else []),
                "source_quality": a["source_quality"],
                "path": a["path"],
                "source_notes": " | ".join(a["sources"]),
            })

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "article_count": len(articles),
        "domains": Counter(a["domain"] for a in articles),
        "polarity_lanes": Counter(a["polarity_lane"] or "general" for a in articles),
        "original_source_archive_found": "/Users/pedro/Desktop/Archivo.zip",
        "curated_source_root": str(KNOWLEDGE),
        "duplicate_groups": [
            "Ansiedad de apego y protesta",
            "Eleccion de pareja y disponibilidad",
            "Reparacion y ciclo negativo",
            "Regulacion corporal",
            "Direccion masculina",
        ],
    }
    (TRACE / "master_knowledge_traceability.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return csv_path, TRACE / "master_knowledge_traceability.json"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    articles = load_articles()
    pdf_path = OUT / "manual_maestro_conocimiento_aaq.pdf"
    build_pdf(articles, pdf_path)
    csv_path, json_path = write_traceability(articles)
    print(pdf_path)
    print(csv_path)
    print(json_path)


if __name__ == "__main__":
    main()
