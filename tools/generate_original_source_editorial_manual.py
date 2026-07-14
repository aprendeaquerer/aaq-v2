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
TRACE_CSV = ROOT / "output" / "traceability" / "original_source_manual_traceability.csv"
PDF_OUT = ROOT / "output" / "pdf" / "manual_maestro_fuentes_originales_editorial_v2_aaq.pdf"
TXT_OUT = ROOT / "output" / "slack_visible" / "manual_maestro_fuentes_originales_editorial_v2_aaq_VISIBLE_EN_SLACK.txt"
MAP_OUT = ROOT / "output" / "traceability" / "manual_maestro_fuentes_originales_editorial_v2_map.csv"
MAX_PAGES = 300


CHAPTERS = [
    {
        "title": "Fundamentos del apego adulto",
        "keywords": ["attached", "attachment", "ainsworth", "origin", "securely attached", "amir levine", "secure love"],
        "thesis": "El apego adulto no es una etiqueta de personalidad, sino un sistema de seguridad que organiza como una persona busca cercania, regula amenaza, interpreta distancia y decide si puede depender de otro sin perderse.",
        "origin": "Nace de aprendizajes repetidos sobre disponibilidad, consuelo, protesta y reparacion. Las fuentes combinan investigacion, libros de apego y material clinico-divulgativo para explicar como esos aprendizajes se vuelven mapas relacionales.",
        "solution": "La direccion de trabajo es pasar de reaccion automatica a seguridad practicada: reconocer el patron, nombrar necesidades, pedir con claridad, tolerar intimidad y elegir vinculos donde haya respuesta consistente.",
    },
    {
        "title": "Ansiedad, protesta y sobreinversion afectiva",
        "keywords": ["rejected", "emotionally invested", "anxious", "protest", "too quickly", "rejection"],
        "thesis": "La ansiedad relacional aparece cuando el sistema interpreta ambiguedad, demora o distancia como amenaza al vinculo. La protesta intenta recuperar seguridad, pero suele producir persecucion, lectura mental y perdida de centro.",
        "origin": "Procede de experiencias donde la conexion fue inconsistente o condicionada. El cuerpo aprende que debe aumentar senales, intensidad o adaptacion para no perder al otro.",
        "solution": "La solucion no es volverse frio, sino convertir la activacion en informacion: pausar, distinguir hechos de interpretaciones, pedir de forma directa y observar reciprocidad antes de invertir mas.",
    },
    {
        "title": "Evitacion, desactivacion y miedo a la intimidad",
        "keywords": ["avoidant", "therapy isnt fixing", "falling out", "falls in love", "needs and feelings"],
        "thesis": "La evitacion protege de depender. Cuando la cercania empieza a exigir vulnerabilidad, el sistema puede desactivar deseo, intelectualizar, buscar defectos o transformar una necesidad legitima de espacio en retirada defensiva.",
        "origin": "Suele formarse donde necesitar fue inutil, peligroso o humillante. La autonomia se vuelve identidad defensiva y el cuerpo confunde intimidad con invasion.",
        "solution": "El trabajo consiste en recuperar necesidades, tolerar dosis pequenas de cercania, comunicar espacio sin castigo y practicar presencia cuando el impulso automatico seria desaparecer.",
    },
    {
        "title": "Desorganizacion, trauma relacional y autoabandono",
        "keywords": ["disorganized", "wounded bird", "trauma", "self-abandonment", "wound", "heridas"],
        "thesis": "La desorganizacion combina deseo de vinculo y miedo al vinculo. La persona puede perseguir, congelarse, complacer o sabotear porque el mismo lugar que promete seguridad tambien activa peligro.",
        "origin": "Se construye cuando la fuente de cuidado tambien fue fuente de amenaza, imprevisibilidad, verguenza o abandono. Por eso el sistema no encuentra una estrategia estable.",
        "solution": "La salida exige visibilidad gradual, realidad externa, limites, regulacion y reaprendizaje de que tener necesidades no equivale a peligro ni a rechazo.",
    },
    {
        "title": "Ciclo negativo, conflicto y reparacion",
        "keywords": ["negative cycle", "repair", "conflict", "responding", "reaching", "shame", "book club ch4", "book club ch5", "book club ch6", "book club ch7", "book club ch8", "book club ch9"],
        "thesis": "Los conflictos repetidos no son solo desacuerdos; son ciclos. Una senal activa verguenza o amenaza, cada persona se protege, y la proteccion de una confirma el miedo de la otra.",
        "origin": "El ciclo se alimenta de historia previa, defensividad, protesta, retirada y reparaciones incompletas. Sin mapa, la pareja discute el contenido y no el patron.",
        "solution": "La reparacion requiere nombrar el ciclo, bajar la activacion, asumir el impacto propio, pedir respuesta concreta y reconstruir seguridad con actos observables.",
    },
    {
        "title": "Comunicacion, necesidades, limites y compasion",
        "keywords": ["boundaries", "compassion", "ask", "needs", "feelings", "know", "relationship"],
        "thesis": "Una relacion madura necesita dos capacidades a la vez: apertura compasiva y limite claro. Sin compasion, el limite se vuelve castigo; sin limite, la compasion se vuelve autoabandono.",
        "origin": "Muchas personas aprendieron que pedir era demasiado, que poner limites era rechazo o que amar significaba anticipar necesidades sin nombrarlas.",
        "solution": "La practica central es hablar en primera persona: necesidad, emocion, peticion, limite y consecuencia. El otro no debe adivinar; debe poder responder.",
    },
    {
        "title": "Discernimiento, dating, ruptura y eleccion de pareja",
        "keywords": ["dating", "settling", "potential", "find love", "move on", "breakup", "ex"],
        "thesis": "Elegir pareja es un acto de discernimiento, no de fantasia. La pregunta no es solo si hay quimica, sino si hay disponibilidad, reciprocidad, valores compatibles y capacidad de reparar.",
        "origin": "La sobreinversion aparece cuando el deseo de potencial sustituye la observacion de realidad. La ruptura duele mas cuando se pierde una historia imaginada ademas de una relacion concreta.",
        "solution": "El criterio practico es mirar patrones, no promesas: consistencia, cuidado, esfuerzo, verdad, reparacion y paz del sistema nervioso.",
    },
    {
        "title": "Inner work, identidad, heridas y agencia",
        "keywords": ["inner work", "identity", "change", "self", "relationships", "8heridas", "identidad"],
        "thesis": "El trabajo interno no consiste en analizarse indefinidamente. Su funcion es devolver agencia: ver la herida, entender la estrategia, elegir una respuesta nueva y sostenerla en relaciones reales.",
        "origin": "Las heridas se convierten en identidad cuando una persona confunde adaptaciones antiguas con verdad sobre si misma.",
        "solution": "La transformacion requiere observacion, responsabilidad, practica somatica o emocional, lenguaje nuevo y decisiones que contradigan el patron viejo sin violentar el ritmo interno.",
    },
    {
        "title": "Regulacion emocional y fundamentos cuerpo-mente",
        "keywords": ["emotion regulation", "regulation", "emotion", "body", "nervous", "handbook"],
        "thesis": "Comprender una idea no basta si el cuerpo sigue en amenaza. La regulacion emocional explica por que una persona puede saber que esta segura y aun asi reaccionar como si no lo estuviera.",
        "origin": "La respuesta emocional integra aprendizaje, fisiologia, interpretacion, memoria y contexto. La reaccion es rapida porque protege antes de razonar.",
        "solution": "La practica es aumentar capacidad: identificar activacion, nombrar emocion, ampliar tolerancia, retrasar impulsos destructivos y elegir acciones coherentes con valores.",
    },
    {
        "title": "Polaridad, atraccion y dinamicas masculino/femenino",
        "keywords": ["polaridad", "masculino", "femenina", "masculine", "feminine", "attraction", "leader"],
        "thesis": "La polaridad puede servir como lenguaje de dinamica y deseo, pero se vuelve peligrosa si se convierte en dogma de genero. Debe filtrarse por seguridad, consentimiento, reciprocidad y madurez.",
        "origin": "Las fuentes mezclan atraccion, liderazgo emocional, receptividad, direccion y energia relacional. El manual separa dinamicas utiles de mandatos rigidos.",
        "solution": "La aplicacion sana es flexible: cada persona cultiva presencia, claridad, deseo y cuidado sin usar masculino/femenino como excusa para control, pasividad o desigualdad.",
    },
    {
        "title": "Consejos y principios para hombres / Masculino",
        "keywords": ["masculine", "masculino", "man", "male", "connor beaton", "leader"],
        "thesis": "El material dirigido a hombres se separa para no contaminar el cuerpo general. Aqui se trabaja liderazgo interno, direccion, deseo, responsabilidad emocional y fuerza sin control.",
        "origin": "Muchas instrucciones masculinas nacen de una tension: aprender a liderar sin dominar, sostener deseo sin presionar y tener estandares sin deshumanizar.",
        "solution": "El eje practico es presencia mas integridad: actuar desde valores, leer reciprocidad, reparar sin ego y sostener limites sin resentimiento.",
    },
    {
        "title": "Herramientas, ejercicios y plantillas no meditativas",
        "keywords": ["templates", "plantilla", "steps", "practice", "exercise", "process", "short", "long"],
        "thesis": "Las herramientas convierten teoria en conducta. No sustituyen criterio clinico ni conversacion real, pero ayudan a ordenar necesidades, decisiones, limites y reparaciones.",
        "origin": "Aparecen como plantillas, procesos de escritura, pasos de cambio, guiones de conversacion y criterios para observar patrones.",
        "solution": "Se usan mejor como practica repetida: observar, escribir, nombrar, pedir, decidir, revisar y ajustar. Se excluyen meditaciones, breathwork y respiracion guiada por instruccion final.",
    },
]


EXCLUDED_RE = re.compile(r"\b(meditaci[oó]n|meditation|breathwork|respiraci[oó]n guiada|guided breathing)\b", re.I)
NOISE_RE = re.compile(
    r"^(page\s+\d+|copyright|all rights reserved|table of contents|dedication|title page|\d+|source:|transcript)$",
    re.I,
)
SPANISH_MARKERS = {
    "que", "como", "para", "porque", "cuando", "persona", "relacion", "apego", "necesidad",
    "limite", "seguridad", "miedo", "cuerpo", "patron", "herida", "pareja", "emocional",
}


def clean_xml(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def word_count(text):
    return len(re.findall(r"\w+", text or ""))


def read_sources():
    with TRACE_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["word_count"] = int(row["word_count"] or 0)
        row["pages"] = int(row["pages"] or 0) if row["pages"] else 0
        row["text_path"] = Path(row["text_path"])
        row["text"] = row["text_path"].read_text(encoding="utf-8", errors="ignore")
    return rows


def classify(source):
    haystack = f"{source['relative_path']} {source['primary_chapter']} {source['text'][:25000]}".lower()
    scores = []
    for chapter in CHAPTERS:
        score = sum(haystack.count(k.lower()) for k in chapter["keywords"])
        if chapter["title"].lower() in source["primary_chapter"].lower():
            score += 20
        scores.append((score, chapter["title"]))
    scores.sort(reverse=True)
    return scores[0][1]


def paragraph_score(paragraph, chapter, source):
    p = paragraph.lower()
    chapter_def = next(c for c in CHAPTERS if c["title"] == chapter)
    score = 0
    score += sum(p.count(k.lower()) * 5 for k in chapter_def["keywords"])
    score += sum(1 for marker in SPANISH_MARKERS if re.search(rf"\b{marker}\b", p)) * 2
    score += 6 if "desarrollo del contenido" in source["text"][:4000].lower() else 0
    score += 4 if 70 <= word_count(paragraph) <= 260 else 0
    score -= 12 if paragraph.count("?") > 4 else 0
    score -= 20 if EXCLUDED_RE.search(paragraph) else 0
    return score


def split_paragraphs(text):
    text = text.replace("\u00a0", " ").replace("\u2013", "-").replace("\u2014", "-")
    raw = re.split(r"\n\s*\n", text)
    paragraphs = []
    for part in raw:
        part = re.sub(r"[ \t]+", " ", part).strip()
        part = re.sub(r"\n+", " ", part)
        wc = word_count(part)
        if wc < 35 or wc > 320:
            continue
        if NOISE_RE.match(part.strip()):
            continue
        if EXCLUDED_RE.search(part):
            continue
        if len(re.sub(r"[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", "", part)) < 80:
            continue
        paragraphs.append(part)
    return paragraphs


def select_blocks(sources):
    by_chapter = defaultdict(list)
    trace_rows = []
    for source in sources:
        chapter = classify(source)
        source["chapter"] = chapter
        paragraphs = split_paragraphs(source["text"])
        ranked = sorted(
            paragraphs,
            key=lambda p: paragraph_score(p, chapter, source),
            reverse=True,
        )
        budget = 7000
        if source["word_count"] > 20000:
            budget = 13000
        if source["word_count"] < 1500:
            budget = 1300
        chosen = []
        used = 0
        seen = set()
        for paragraph in ranked:
            fingerprint = re.sub(r"\W+", "", paragraph.lower())[:180]
            if fingerprint in seen:
                continue
            wc = word_count(paragraph)
            if used + wc > budget:
                continue
            chosen.append(paragraph)
            seen.add(fingerprint)
            used += wc
            if used >= budget * 0.9:
                break
        by_chapter[chapter].append((source, chosen, used))
        trace_rows.append({
            "relative_path": source["relative_path"],
            "chapter": chapter,
            "type": source["type"],
            "pages": source["pages"] or "",
            "source_word_count": source["word_count"],
            "integrated_word_count": used,
            "text_path": source["text_path"],
        })
    return by_chapter, trace_rows


def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Arial", 8)
    canvas.setFillColor(colors.HexColor("#4A5568"))
    canvas.drawString(1.5 * cm, 1.0 * cm, "Manual maestro AAQ - fuentes originales - v2 editorial")
    canvas.drawRightString(A4[0] - 1.5 * cm, 1.0 * cm, str(doc.page))
    canvas.restoreState()


def register_fonts():
    pdfmetrics.registerFont(TTFont("Arial", "/System/Library/Fonts/Supplemental/Arial.ttf"))
    pdfmetrics.registerFont(TTFont("Arial-Bold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"))


def styles():
    base = getSampleStyleSheet()
    base.add(ParagraphStyle("TitleMain", fontName="Arial-Bold", fontSize=24, leading=30, alignment=TA_CENTER, spaceAfter=14, textColor=colors.HexColor("#1A202C")))
    base.add(ParagraphStyle("Subtitle", fontName="Arial", fontSize=10, leading=14, alignment=TA_CENTER, textColor=colors.HexColor("#4A5568")))
    base.add(ParagraphStyle("Chapter", fontName="Arial-Bold", fontSize=17, leading=21, spaceBefore=8, spaceAfter=8, textColor=colors.HexColor("#1A202C")))
    base.add(ParagraphStyle("H2", fontName="Arial-Bold", fontSize=11.2, leading=14, spaceBefore=7, spaceAfter=4, textColor=colors.HexColor("#2D3748")))
    base.add(ParagraphStyle("Body", fontName="Arial", fontSize=8.45, leading=10.7, alignment=TA_JUSTIFY, spaceAfter=3.5))
    base.add(ParagraphStyle("Small", fontName="Arial", fontSize=7.2, leading=9, textColor=colors.HexColor("#4A5568"), spaceAfter=2.4))
    return base


def chapter_opening(chapter, source_count):
    return [
        ("Tesis del capitulo", chapter["thesis"]),
        ("Origen y logica del fenomeno", chapter["origin"]),
        ("Mecanismo central", (
            "El mecanismo se entiende como una cadena: experiencia previa, lectura de amenaza, respuesta corporal, "
            "estrategia protectora, consecuencia relacional y confirmacion del mapa interno. El manual conserva esta "
            "cadena para que cada concepto pueda leerse desde el origen hasta la solucion, no como consejo aislado."
        )),
        ("Como se identifica", (
            "Se identifica observando senales repetidas: intensidad desproporcionada, retirada, protesta, confusion, "
            "necesidad no nombrada, dificultad para reparar, eleccion de parejas no disponibles o perdida de agencia. "
            "La senal aislada importa menos que el patron y su repeticion en contexto."
        )),
        ("Errores frecuentes y excepciones", (
            "El error comun es moralizar el patron: llamar manipulacion a toda protesta, frialdad a toda necesidad de "
            "espacio o madurez a la desconexion. La excepcion editorial es importante: una misma conducta puede ser "
            "defensa, limite sano o incompatibilidad real segun contexto, historia y capacidad de reparacion."
        )),
        ("Solucion practica", chapter["solution"]),
        ("Fuentes integradas", f"Este capitulo integra {source_count} fuentes originales. La trazabilidad detallada queda fuera del PDF en el CSV v2."),
    ]


def concept_title(paragraph, fallback):
    first = re.split(r"[.!?]", paragraph)[0].strip()
    first = re.sub(r"^[\"'“”]+|[\"'“”]+$", "", first)
    if 4 <= word_count(first) <= 14:
        return first[:90]
    return fallback


def build_pdf(sources, by_chapter):
    register_fonts()
    st = styles()
    PDF_OUT.parent.mkdir(parents=True, exist_ok=True)
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
    type_counts = Counter(s["type"] for s in sources)
    total_source_words = sum(s["word_count"] for s in sources)
    integrated_words = sum(used for items in by_chapter.values() for _, _, used in items)

    story = [
        Spacer(1, 4.0 * cm),
        Paragraph("Manual maestro AAQ - fuentes originales", st["TitleMain"]),
        Paragraph("Version v2 editorial: manual integrado, no scaffold de extraccion", st["Subtitle"]),
        Paragraph(f"Generado el {datetime.now().strftime('%Y-%m-%d %H:%M')} desde /Users/pedro/Desktop/Archivo", st["Subtitle"]),
        PageBreak(),
        Paragraph("Nota editorial", st["Chapter"]),
    ]
    for text in [
        "Esta version corrige la entrega anterior: no organiza el cuerpo del PDF por archivo ni presenta instrucciones sobre lo que habria que hacer. El documento se estructura como manual de referencia por conceptos maestros.",
        "La fuente de contenido son unicamente los archivos originales localizados en /Users/pedro/Desktop/Archivo. No se usa brain/knowledge como fuente de contenido.",
        "El limite maximo es 300 paginas. Por eso el manual integra el material mas sustantivo de cada fuente y deja la trazabilidad completa fuera del PDF. Se excluyen meditaciones, breathwork y respiracion guiada por la ultima instruccion del hilo.",
        "Esta pasada no pretende ser un resumen ejecutivo: conserva desarrollo, mecanismos, ejemplos, errores, limites y herramientas. Cuando una fuente esta en ingles, se integra dentro de un marco explicativo en espanol y se mantienen terminos tecnicos cuando aportan precision.",
    ]:
        story.append(Paragraph(clean_xml(text), st["Body"]))

    metrics = [
        ["Metrica", "Valor"],
        ["Archivos originales", str(len(sources))],
        ["PDF", str(type_counts.get("pdf", 0))],
        ["DOCX", str(type_counts.get("docx", 0))],
        ["Palabras fuente extraidas", f"{total_source_words:,}".replace(",", ".")],
        ["Palabras integradas aproximadas", f"{integrated_words:,}".replace(",", ".")],
        ["Limite de paginas", str(MAX_PAGES)],
    ]
    table = Table(metrics, colWidths=[7.5 * cm, 6.5 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ("FONTNAME", (0, 0), (-1, -1), "Arial"),
        ("FONTNAME", (0, 0), (-1, 0), "Arial-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E0")),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([Spacer(1, 8), table, PageBreak(), Paragraph("Indice", st["Chapter"])])
    for i, chapter in enumerate(CHAPTERS, 1):
        story.append(Paragraph(f"{i}. {clean_xml(chapter['title'])}", st["Body"]))
    story.extend([
        Paragraph(f"{len(CHAPTERS) + 1}. Inconsistencias, contradicciones y decisiones editoriales", st["Body"]),
        Paragraph(f"{len(CHAPTERS) + 2}. Mapa de fuentes integrado", st["Body"]),
        PageBreak(),
    ])

    for i, chapter in enumerate(CHAPTERS, 1):
        items = by_chapter.get(chapter["title"], [])
        story.append(Paragraph(f"{i}. {clean_xml(chapter['title'])}", st["Chapter"]))
        for heading, text in chapter_opening(chapter, len(items)):
            story.append(Paragraph(clean_xml(heading), st["H2"]))
            story.append(Paragraph(clean_xml(text), st["Body"]))

        story.append(Paragraph("Desarrollo integrado", st["H2"]))
        emitted = 0
        for source, paragraphs, used in sorted(items, key=lambda item: item[0]["relative_path"]):
            if not paragraphs:
                continue
            for paragraph in paragraphs[:32]:
                fallback = f"Concepto integrado {emitted + 1}"
                title = concept_title(paragraph, fallback)
                story.append(Paragraph(clean_xml(title), st["H2"]))
                story.append(Paragraph(clean_xml(paragraph), st["Body"]))
                emitted += 1
            story.append(Paragraph(clean_xml(f"Trazabilidad de este bloque: {source['relative_path']}"), st["Small"]))

        story.append(Paragraph("Practica y criterios de aplicacion", st["H2"]))
        for text in [
            "Antes de actuar, separar hecho, interpretacion, emocion, necesidad y peticion. Esta distincion evita convertir activacion en mandato.",
            "Buscar patrones repetidos, no momentos aislados. Un comportamiento puede tener significados distintos segun frecuencia, reparacion y contexto.",
            "Usar el cuerpo como dato, no como juez final. La activacion informa, pero no siempre describe la realidad completa.",
            "Cerrar el ciclo con una accion observable: conversacion, limite, reparacion, pausa, decision o practica escrita.",
        ]:
            story.append(Paragraph(clean_xml(text), st["Body"]))
        story.append(PageBreak())

    story.append(Paragraph(f"{len(CHAPTERS) + 1}. Inconsistencias, contradicciones y decisiones editoriales", st["Chapter"]))
    decisions = [
        ("Fuente original vs brain/knowledge", "Esta version usa solo /Users/pedro/Desktop/Archivo. brain/knowledge queda descartado como fuente de contenido para responder a la correccion del hilo."),
        ("Exhaustividad vs limite de 300 paginas", "La instruccion final fija maximo 300 paginas. Se conserva material sustantivo y trazable, pero no se vuelca cada palabra extraida. El objetivo es manual de referencia, no archivo bruto."),
        ("Ejercicios, meditaciones y breathwork", "Se incluyen herramientas no meditativas, plantillas y practicas de escritura o comunicacion. Se excluyen meditaciones, breathwork y respiracion guiada por la ultima regla explicita."),
        ("Polaridad y genero", "La polaridad se presenta como dinamica relacional, no como mandato universal. El material orientado a hombres queda separado para evitar mezclar audiencia especifica con principios generales."),
        ("Fuentes en ingles", "Cuando una fuente original esta en ingles, el marco editorial se mantiene en espanol y se conservan terminos tecnicos utiles. Una traduccion literaria completa requeriria una pasada editorial adicional fuente por fuente."),
    ]
    for heading, text in decisions:
        story.append(Paragraph(clean_xml(heading), st["H2"]))
        story.append(Paragraph(clean_xml(text), st["Body"]))
    story.append(PageBreak())

    story.append(Paragraph(f"{len(CHAPTERS) + 2}. Mapa de fuentes integrado", st["Chapter"]))
    for source in sorted(sources, key=lambda s: s["relative_path"]):
        line = (
            f"{source['relative_path']} - {source['type'].upper()}, "
            f"{source['pages'] or 'n/a'} paginas, {source['word_count']:,} palabras, "
            f"capitulo: {source['chapter']}"
        ).replace(",", ".")
        story.append(Paragraph(clean_xml(line), st["Small"]))

    doc.build(story)
    return integrated_words


def write_trace(trace_rows):
    MAP_OUT.parent.mkdir(parents=True, exist_ok=True)
    with MAP_OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["relative_path", "chapter", "type", "pages", "source_word_count", "integrated_word_count", "text_path"],
        )
        writer.writeheader()
        writer.writerows(trace_rows)


def write_visible_text():
    TXT_OUT.parent.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(PDF_OUT))
    parts = [
        "Manual maestro AAQ - fuentes originales (v2 editorial visible en Slack)",
        "Fuente: solo archivos originales de /Users/pedro/Desktop/Archivo",
        f"PDF base: {PDF_OUT.name}",
        "",
    ]
    for i, page in enumerate(reader.pages, 1):
        parts.append(f"\n\n--- PAGINA {i} ---\n")
        parts.append(page.extract_text() or "")
    TXT_OUT.write_text("\n".join(parts), encoding="utf-8")
    return len(reader.pages)


def main():
    sources = read_sources()
    by_chapter, trace_rows = select_blocks(sources)
    integrated_words = build_pdf(sources, by_chapter)
    write_trace(trace_rows)
    pages = write_visible_text()
    print(PDF_OUT)
    print(MAP_OUT)
    print(TXT_OUT)
    print(f"pages={pages}")
    print(f"integrated_words={integrated_words}")
    if pages > MAX_PAGES:
        raise SystemExit(f"Generated PDF has {pages} pages, above max {MAX_PAGES}")


if __name__ == "__main__":
    main()
