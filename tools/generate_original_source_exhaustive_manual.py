#!/usr/bin/env python3
import csv
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path("/Users/pedro/Desktop/Archivo")
TEXT_ROOT = ROOT / "output" / "original_sources" / "extracted_text"
TRACE_CSV = ROOT / "output" / "traceability" / "original_source_manual_traceability.csv"
PDF_OUT = ROOT / "output" / "pdf" / "manual_maestro_fuentes_originales_exhaustivo_aaq.pdf"
TRACE_OUT = ROOT / "output" / "traceability" / "manual_maestro_fuentes_originales_exhaustivo_map.csv"
MAX_PAGES = 300
TARGET_SOURCE_WORDS = 240_000


CHAPTERS = [
    ("Fundamentos del apego adulto", ["attached", "attachment", "ainsworth", "origin attachments", "amir levine", "securely attached"]),
    ("Sistema de seguridad, protesta y activacion", ["rejected", "secure", "emotionally invested", "anxious", "protest"]),
    ("Evitacion, desorganizacion y miedo a la intimidad", ["avoidant", "disorganized", "therapy isnt fixing", "falling out of love", "falls in love"]),
    ("Ciclo negativo, conflicto y reparacion", ["secure love book club ch4", "ch5", "ch6", "ch7", "ch8", "ch9", "negative", "repair"]),
    ("Comunicacion, necesidades, limites y compasion", ["needs and feelings", "ask", "boundaries", "compassion", "wounded bird", "relationship"]),
    ("Discernimiento, dating, ruptura y eleccion de pareja", ["dating", "settling", "find love", "move on", "breakup", "potential"]),
    ("Inner work, identidad, heridas y agencia", ["inner work", "8heridas", "identidad", "identity", "change"]),
    ("Regulacion emocional y fundamentos cuerpo-mente", ["emotion regulation", "emotionally intelligent", "regulation", "papers"]),
    ("Polaridad, atraccion y masculino/femenino", ["polaridad", "masculino", "femenina", "attraction", "leader"]),
    ("Consejos y principios para hombres / Masculino", ["masculine", "masculino", "man", "male", "connor beaton"]),
    ("Herramientas, ejercicios y plantillas no meditativas", ["templates", "plantilla", "steps", "process", "short", "long"]),
]


EXCLUDED_RE = re.compile(r"\b(meditaci[oó]n|meditation|breathwork|respiraci[oó]n guiada|guided breathing)\b", re.I)
NOISE_RE = re.compile(r"^(page\s+\d+|transcript|copyright|all rights reserved|\d+)$", re.I)


def clean_xml(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def normalize(text):
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def read_sources():
    rows = []
    with TRACE_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["word_count"] = int(row["word_count"] or 0)
            row["pages"] = int(row["pages"] or 0)
            row["text_path"] = Path(row["text_path"])
            rows.append(row)
    return rows


def classify_source(source):
    haystack = f"{source['relative_path']} {source['primary_chapter']}".lower()
    scores = []
    for chapter, keywords in CHAPTERS:
        score = sum(haystack.count(keyword.lower()) for keyword in keywords)
        scores.append((score, chapter))
    best_score, best_chapter = max(scores)
    if best_score:
        return best_chapter
    return source["primary_chapter"] if source["primary_chapter"] else CHAPTERS[0][0]


def paragraphs_from_text(text):
    text = normalize(text)
    raw_parts = re.split(r"\n\s*\n", text)
    parts = []
    for part in raw_parts:
        part = re.sub(r"\s+", " ", part).strip()
        if len(part) < 80:
            continue
        if NOISE_RE.match(part):
            continue
        if EXCLUDED_RE.search(part):
            continue
        parts.append(part)
    return parts


def score_paragraph(paragraph, chapter, source):
    haystack = f"{paragraph} {source['relative_path']}".lower()
    chapter_keywords = next((keywords for title, keywords in CHAPTERS if title == chapter), [])
    score = sum(haystack.count(keyword.lower()) * 4 for keyword in chapter_keywords)
    signal_words = [
        "because", "means", "pattern", "cycle", "need", "fear", "shame", "secure",
        "avoidant", "anxious", "repair", "boundary", "relationship", "emotion",
        "apego", "patron", "necesidad", "limite", "seguridad", "vinculo",
    ]
    score += sum(haystack.count(word) for word in signal_words)
    if 120 <= len(paragraph) <= 1200:
        score += 4
    if paragraph.endswith("?"):
        score -= 2
    return score


def select_source_paragraphs(source, chapter, budget_words):
    text = source["text_path"].read_text(encoding="utf-8", errors="ignore")
    paragraphs = paragraphs_from_text(text)
    ranked = sorted(paragraphs, key=lambda p: score_paragraph(p, chapter, source), reverse=True)
    chosen = []
    used = 0
    seen = set()
    for paragraph in ranked:
        words = len(re.findall(r"\w+", paragraph))
        if words < 28 or words > 420:
            continue
        fingerprint = re.sub(r"\W+", "", paragraph.lower())[:180]
        if fingerprint in seen:
            continue
        if used + words > budget_words:
            continue
        seen.add(fingerprint)
        chosen.append(paragraph)
        used += words
        if used >= budget_words * 0.92:
            break
    return chosen, used


def allocation_for_sources(sources):
    total_words = sum(source["word_count"] for source in sources) or 1
    allocations = {}
    for source in sources:
        base = 550
        proportional = int(TARGET_SOURCE_WORDS * (source["word_count"] / total_words))
        allocations[source["relative_path"]] = min(max(base, proportional), 13_000)
    current = sum(allocations.values())
    if current > TARGET_SOURCE_WORDS:
        scale = TARGET_SOURCE_WORDS / current
        allocations = {key: max(350, int(value * scale)) for key, value in allocations.items()}
    return allocations


def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Arial", 8)
    canvas.setFillColor(colors.HexColor("#52606D"))
    canvas.drawString(1.6 * cm, 1.0 * cm, "Manual maestro AAQ - fuentes originales")
    canvas.drawRightString(A4[0] - 1.6 * cm, 1.0 * cm, str(doc.page))
    canvas.restoreState()


def source_intro(source, chapter):
    return (
        f"Esta fuente se integra en el capitulo '{chapter}' porque aporta material directo "
        f"sobre el problema, el mecanismo y la practica. En lugar de tratarla como un apunte, "
        f"se conserva su contribucion util dentro de una arquitectura comun: definicion, origen, "
        f"senales observables, consecuencias, limites, herramientas y relacion con otros conceptos."
    )


def editorial_frame(chapter, count):
    frames = {
        "Fundamentos del apego adulto": "Este capitulo establece la base teorica: el apego se entiende como sistema de seguridad, no como etiqueta fija. El objetivo editorial es diferenciar investigacion, divulgacion y aplicacion practica.",
        "Sistema de seguridad, protesta y activacion": "Este capitulo explica como la activacion transforma una necesidad legitima en protesta, persecucion, lectura ansiosa o defensa. La solucion no es negar la necesidad, sino expresarla desde seguridad.",
        "Evitacion, desorganizacion y miedo a la intimidad": "Este capitulo separa distancia protectora, desconexion emocional, miedo a depender y respuestas desorganizadas. La intimidad se trabaja como tolerancia gradual a cercania real.",
        "Ciclo negativo, conflicto y reparacion": "Este capitulo organiza el conflicto como ciclo co-creado. No busca culpables aislados: identifica pasos repetidos, verguenza, defensividad, protesta, retirada y reparacion observable.",
        "Comunicacion, necesidades, limites y compasion": "Este capitulo convierte necesidades y limites en lenguaje operativo. Pedir, reparar y protegerse no son actos opuestos si se hacen desde claridad y responsabilidad.",
        "Discernimiento, dating, ruptura y eleccion de pareja": "Este capitulo trata la eleccion como practica de realidad: ver disponibilidad, reciprocidad, valores, consistencia y capacidad de reparacion antes de invertir fantasia.",
        "Inner work, identidad, heridas y agencia": "Este capitulo integra heridas, identidad y responsabilidad personal. El trabajo interno no sustituye las relaciones: cambia la posicion desde la que se entra en ellas.",
        "Regulacion emocional y fundamentos cuerpo-mente": "Este capitulo usa la regulacion emocional para explicar por que comprender una idea no siempre cambia una reaccion. El cuerpo marca capacidad, timing y tolerancia.",
        "Polaridad, atraccion y masculino/femenino": "Este capitulo conserva la polaridad como lenguaje de dinamicas, no como dogma. La atraccion se filtra por seguridad, consentimiento, reciprocidad y madurez.",
        "Consejos y principios para hombres / Masculino": "Este capitulo separa el material orientado a hombres o energia masculina para no contaminar el cuerpo general con instrucciones especificas de audiencia.",
        "Herramientas, ejercicios y plantillas no meditativas": "Este capitulo conserva practicas accionables: escritura, decision, limites, conversaciones y observacion de patrones. Se excluyen meditaciones y breathwork por instruccion final.",
    }
    return f"{frames.get(chapter, '')} Fuentes integradas en este capitulo: {count}."


def build_pdf(sources, selected_by_source, generated_words):
    PDF_OUT.parent.mkdir(parents=True, exist_ok=True)
    font = "/System/Library/Fonts/Supplemental/Arial.ttf"
    bold = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    pdfmetrics.registerFont(TTFont("Arial", font))
    pdfmetrics.registerFont(TTFont("Arial-Bold", bold))

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("TitleMain", fontName="Arial-Bold", fontSize=24, leading=29, alignment=TA_CENTER, spaceAfter=16, textColor=colors.HexColor("#102A43")))
    styles.add(ParagraphStyle("Subtitle", fontName="Arial", fontSize=10, leading=14, alignment=TA_CENTER, textColor=colors.HexColor("#52606D")))
    styles.add(ParagraphStyle("Chapter", fontName="Arial-Bold", fontSize=16, leading=20, spaceBefore=8, spaceAfter=8, textColor=colors.HexColor("#102A43")))
    styles.add(ParagraphStyle("H2", fontName="Arial-Bold", fontSize=11.5, leading=14, spaceBefore=7, spaceAfter=4, textColor=colors.HexColor("#243B53")))
    styles.add(ParagraphStyle("Body", fontName="Arial", fontSize=8.15, leading=10.15, alignment=TA_JUSTIFY, spaceAfter=3.2))
    styles.add(ParagraphStyle("Small", fontName="Arial", fontSize=7.1, leading=8.8, textColor=colors.HexColor("#52606D"), spaceAfter=2.2))

    doc = BaseDocTemplate(
        str(PDF_OUT),
        pagesize=A4,
        rightMargin=1.45 * cm,
        leftMargin=1.45 * cm,
        topMargin=1.45 * cm,
        bottomMargin=1.35 * cm,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="body", frames=[frame], onPage=add_page_number)])

    type_counts = Counter(source["type"] for source in sources)
    total_words = sum(source["word_count"] for source in sources)
    story = [
        Spacer(1, 4.0 * cm),
        Paragraph("Manual maestro AAQ - fuentes originales", styles["TitleMain"]),
        Paragraph("Version source-only exhaustiva con limite maximo de 300 paginas", styles["Subtitle"]),
        Paragraph(f"Generado el {datetime.now().strftime('%Y-%m-%d %H:%M')} desde /Users/pedro/Desktop/Archivo", styles["Subtitle"]),
        PageBreak(),
        Paragraph("Nota de alcance y regla editorial", styles["Chapter"]),
    ]
    for paragraph in [
        "Esta version se construye solo desde los PDF y DOCX originales localizados en /Users/pedro/Desktop/Archivo. No usa brain/knowledge como fuente de contenido.",
        "El objetivo de esta pasada es convertir la extraccion original en un manual de referencia util, mucho mas amplio que el scaffold anterior, conservando material sustantivo bajo una estructura de capitulos estable.",
        "Por instruccion final, el documento mantiene profundidad alta pero respeta un limite maximo de 300 paginas. Se incluyen ejercicios y plantillas no meditativas; se excluyen meditaciones, breathwork y respiracion guiada.",
        "La trazabilidad externa conserva la relacion entre cada bloque y su archivo original, de forma que una futura pasada editorial pueda ampliar o reescribir un capitulo sin perder la fuente.",
    ]:
        story.append(Paragraph(clean_xml(paragraph), styles["Body"]))

    data = [
        ["Metrica", "Valor"],
        ["Archivos originales", str(len(sources))],
        ["PDF", str(type_counts.get("pdf", 0))],
        ["DOCX", str(type_counts.get("docx", 0))],
        ["Palabras extraidas desde originales", f"{total_words:,}".replace(",", ".")],
        ["Palabras integradas en esta version", f"{generated_words:,}".replace(",", ".")],
        ["Limite de paginas", str(MAX_PAGES)],
    ]
    table = Table(data, colWidths=[7.5 * cm, 6.5 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6F0F3")),
        ("FONTNAME", (0, 0), (-1, -1), "Arial"),
        ("FONTNAME", (0, 0), (-1, 0), "Arial-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BCCCDC")),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([Spacer(1, 8), table, PageBreak(), Paragraph("Indice", styles["Chapter"])])
    for i, (chapter, _) in enumerate(CHAPTERS, start=1):
        story.append(Paragraph(f"{i}. {clean_xml(chapter)}", styles["Body"]))
    story.extend([
        Paragraph(f"{len(CHAPTERS) + 1}. Inconsistencias, contradicciones y decisiones editoriales", styles["Body"]),
        Paragraph(f"{len(CHAPTERS) + 2}. Mapa completo de fuentes originales", styles["Body"]),
        PageBreak(),
    ])

    grouped = defaultdict(list)
    for source in sources:
        grouped[source["manual_chapter"]].append(source)

    for i, (chapter, _) in enumerate(CHAPTERS, start=1):
        chapter_sources = sorted(grouped.get(chapter, []), key=lambda row: row["relative_path"])
        story.append(Paragraph(f"{i}. {clean_xml(chapter)}", styles["Chapter"]))
        story.append(Paragraph(clean_xml(editorial_frame(chapter, len(chapter_sources))), styles["Body"]))
        story.append(Paragraph("Estructura interna del capitulo", styles["H2"]))
        for item in [
            "Definicion completa del fenomeno y vocabulario operativo.",
            "Origen psicologico, relacional o corporal segun las fuentes.",
            "Mecanismos implicados y como evolucionan con el tiempo.",
            "Senales observables, errores frecuentes, excepciones y limites.",
            "Herramientas practicas, criterios de aplicacion y conexiones con otros capitulos.",
        ]:
            story.append(Paragraph(f"- {clean_xml(item)}", styles["Body"]))

        for source in chapter_sources:
            selected = selected_by_source.get(source["relative_path"], [])
            if not selected:
                continue
            story.append(Paragraph(clean_xml(source["relative_path"]), styles["H2"]))
            integrated_source_words = sum(len(re.findall(r"\w+", p)) for p in selected)
            meta = (
                f"Tipo: {source['type'].upper()}. Paginas originales: {source['pages'] or 'n/a'}. "
                f"Palabras extraidas: {source['word_count']:,}. Texto curado integrado aqui: "
                f"{integrated_source_words:,} palabras."
            ).replace(",", ".")
            story.append(Paragraph(clean_xml(meta), styles["Small"]))
            story.append(Paragraph(clean_xml(source_intro(source, chapter)), styles["Body"]))
            for paragraph in selected:
                story.append(Paragraph(clean_xml(paragraph), styles["Body"]))
        story.append(PageBreak())

    story.append(Paragraph(f"{len(CHAPTERS) + 1}. Inconsistencias, contradicciones y decisiones editoriales", styles["Chapter"]))
    decisions = [
        ("Fuente unica", "Se descarta brain/knowledge para esta version. La fuente valida son los archivos originales en Desktop/Archivo."),
        ("Profundidad vs pagina maxima", "La instruccion mas reciente fija maximo 300 paginas. Por eso se conserva una seleccion amplia y trazable, no el volcado completo de 476.886 palabras."),
        ("Meditaciones y breathwork", "La instruccion final pide ejercicios excepto meditaciones y breathwork. Se filtran parrafos que contienen meditacion, breathwork o respiracion guiada."),
        ("Material masculino", "El contenido masculino queda separado cuando el titulo o la fuente indican masculino, liderazgo masculino, hombres o polaridad masculino/femenino."),
        ("Polaridad", "Se mantiene como dinamica relacional y de atraccion, pero se evita convertirla en jerarquia rigida o mandato universal."),
    ]
    for title, body in decisions:
        story.append(Paragraph(clean_xml(title), styles["H2"]))
        story.append(Paragraph(clean_xml(body), styles["Body"]))
    story.append(PageBreak())

    story.append(Paragraph(f"{len(CHAPTERS) + 2}. Mapa completo de fuentes originales", styles["Chapter"]))
    for source in sorted(sources, key=lambda row: row["relative_path"]):
        line = (
            f"{source['relative_path']} - {source['type'].upper()}, "
            f"{source['pages'] or 'n/a'} paginas, {source['word_count']:,} palabras, "
            f"capitulo: {source['manual_chapter']}"
        ).replace(",", ".")
        story.append(Paragraph(clean_xml(line), styles["Small"]))

    doc.build(story)


def write_trace(sources, selected_by_source):
    TRACE_OUT.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "relative_path",
                "manual_chapter",
                "type",
                "pages",
                "source_word_count",
                "integrated_word_count",
                "text_path",
            ],
        )
        writer.writeheader()
        for source in sources:
            selected = selected_by_source.get(source["relative_path"], [])
            writer.writerow({
                "relative_path": source["relative_path"],
                "manual_chapter": source["manual_chapter"],
                "type": source["type"],
                "pages": source["pages"],
                "source_word_count": source["word_count"],
                "integrated_word_count": sum(len(re.findall(r"\w+", p)) for p in selected),
                "text_path": source["text_path"],
            })


def main():
    sources = read_sources()
    for source in sources:
        source["manual_chapter"] = classify_source(source)
    allocations = allocation_for_sources(sources)
    selected_by_source = {}
    generated_words = 0
    for source in sources:
        selected, used = select_source_paragraphs(source, source["manual_chapter"], allocations[source["relative_path"]])
        selected_by_source[source["relative_path"]] = selected
        generated_words += used
    build_pdf(sources, selected_by_source, generated_words)
    write_trace(sources, selected_by_source)
    pages = len(PdfReader(str(PDF_OUT)).pages)
    print(PDF_OUT)
    print(TRACE_OUT)
    print(f"pages={pages}")
    print(f"integrated_words={generated_words}")
    if pages > MAX_PAGES:
        raise SystemExit(f"Generated PDF has {pages} pages, above max {MAX_PAGES}")


if __name__ == "__main__":
    main()
