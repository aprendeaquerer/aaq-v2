"""File-backed knowledge brain.

Markdown articles under /brain/knowledge are the source of truth. This first
retriever is intentionally simple so article structure can stabilize before an
embedding index is introduced.
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from app.services.brain.types import KnowledgeChunk

SUPPORTED_DOMAINS = ("attachment", "relationships", "polarity", "somatics", "self_improvement")
NON_CONTENT_SECTIONS = {"source notes", "related concepts"}
AUXILIARY_CONTENT_SECTIONS = {"example eldric language"}
BREAKUP_ARTICLE_IDS = {"jay-shetty-move-on-from-ex", "old-templates-breakup-no-contact-grief"}
BREAKUP_TOPICS = {"breakup_recovery", "breakup-grief", "closure"}
EARLY_INVESTMENT_ARTICLE_IDS = {"nathalie-emotionally-invested-too-quickly"}
EARLY_INVESTMENT_CUES = (
    "me apego rapido", "me apego rápido", "apego rapido", "apego rápido",
    "me engancho", "me engancho rapido", "me engancho rápido",
    "invierto emocionalmente", "invertido emocionalmente",
    "me ilusiono rapido", "me ilusiono rápido", "too quickly",
    "fast attachment", "emotionally invested",
)
ACTIVE_CONFLICT_ARTICLE_IDS = {
    "secure-love-ch01-problem-beneath-problem",
    "secure-love-ch04-negative-cycle",
    "secure-love-ch05-part1-interrupting-negative-cycle",
    "secure-love-ch05-part2-interrupting-negative-cycle-qa",
    "secure-love-ch07-reaching-and-responding",
    "secure-love-ch08-repair-after-conflict",
    "secure-love-ch09-attachment-injuries-and-repair",
    "adam-lane-smith-avoidant-falling-in-love-20-steps",
    "inner-work-relationships-system",
    "inner-work-relationships-eight-wounds",
    "mind-reading-needs-ask-to-be-known",
    "old-templates-couple-dynamics-difference",
    "old-templates-stay-or-go-decision",
    "old-templates-lost-identity-in-relationship",
}
ATTACHMENT_STYLE_ARTICLE_IDS = {
    "anxious": {
        "old-templates-anxious-unavailable-reconditioning",
        "nathalie-emotionally-invested-too-quickly",
        "amir-levine-rejection-secure-mode-carp",
        "secure-love-ch03-whats-your-attachment-style",
        "secure-love-ch05-part1-interrupting-negative-cycle",
        "secure-love-ch05-part2-interrupting-negative-cycle-qa",
    },
    "avoidant": {
        "adam-lane-smith-avoidant-falling-in-love-20-steps",
        "adam-lane-smith-falling-out-of-love-bonding-system",
        "secure-love-ch03-whats-your-attachment-style",
        "secure-love-ch05-part2-interrupting-negative-cycle-qa",
        "secure-love-ch07-reaching-and-responding",
    },
    "disorganized": {
        "adam-lane-smith-disorganized-attachment-truths",
        "secure-love-ch03-whats-your-attachment-style",
        "secure-love-ch02-understanding-attachment-theory",
        "adam-lane-smith-therapy-attachment-skills",
    },
    "secure": {
        "adam-lane-smith-secure-attachment-12-steps",
        "amir-levine-how-attachment-works",
        "ainsworth-strange-situation-secure-base",
        "secure-love-ch03-whats-your-attachment-style",
    },
}
DATING_ARTICLE_IDS = {
    "old-templates-dating-clarity-signals",
    "nathalie-emotionally-invested-too-quickly",
    "old-templates-anxious-unavailable-reconditioning",
    "stop-settling-for-potential",
}
BREAKUP_CUES = (
    "mi ex", "my ex", "ex pareja", "expareja", "ruptura amorosa", "breakup",
    "move on", "superar a", "superar mi ex", "soltar a mi ex", "volver con mi ex",
    "terminamos", "rompimos", "lo dejamos", "duelo amoroso",
)
ACTIVE_PARTNER_CUES = (
    "mi pareja", "mi novia", "mi novio", "mi esposa", "mi esposo", "mi mujer",
    "mi marido", "pareja", "novia", "novio", "ella", "el", "él", "olga",
    "conflicto", "defensiva", "defensivo", "se defiende", "distancia",
    "se aleja", "evita", "evita el conflicto", "hablar con ella", "hablar con el",
    "hablar con él", "relacion", "relación",
)
STOPWORDS = {
    "a", "al", "and", "are", "as", "at", "be", "but", "como", "con", "cuando", "de",
    "del", "el", "en", "for", "i", "in", "is", "it", "la", "las", "lo", "los", "mas",
    "me", "mi", "my", "no", "of", "on", "or", "para", "por", "que", "se", "si", "the",
    "to", "un", "una", "y", "yo",
}


def retrieve_knowledge(message: str, language: str = "es", limit: int = 6) -> List[KnowledgeChunk]:
    chunks = _load_chunks()
    if not chunks:
        return []

    query_terms = _terms(message)
    routed_domains = route_domains(message)
    active_partner_context = _looks_like_active_partner_context(message)
    breakup_context = _looks_like_breakup_context(message)
    dating_context = _looks_like_dating_context(message)
    polarity_lane_context = _polarity_lane_context(message)
    attachment_style_context = _attachment_style_context(message)
    scored = []

    for chunk in chunks:
        if chunk.language not in (language, "multi", ""):
            continue
        score = _score_chunk(
            chunk,
            query_terms,
            routed_domains,
            polarity_lane_context,
            attachment_style_context,
        )
        if breakup_context and _is_breakup_recovery_chunk(chunk):
            score += 5
        if active_partner_context:
            if _is_active_conflict_chunk(chunk):
                score += 4
            if _is_breakup_recovery_chunk(chunk):
                score -= 8
            if _is_early_investment_chunk(chunk) and not _looks_like_early_investment_context(message):
                score -= 6
        if attachment_style_context and _is_attachment_style_chunk(chunk, attachment_style_context):
            score += 7
        elif attachment_style_context and _is_other_attachment_style_chunk(chunk, attachment_style_context):
            score -= 5
        if dating_context and _is_dating_chunk(chunk):
            score += 6
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    results = []
    article_counts: Dict[str, int] = {}
    for score, chunk in scored:
        article_count = article_counts.get(chunk.article_id, 0)
        if article_count >= 2:
            continue
        results.append(
            KnowledgeChunk(
                id=chunk.id,
                article_id=chunk.article_id,
                title=chunk.title,
                section=chunk.section,
                content=chunk.content,
                domain=chunk.domain,
                language=chunk.language,
                polarity_lane=chunk.polarity_lane,
                topics=chunk.topics,
                source_notes=chunk.source_notes,
                score=score,
            )
        )
        article_counts[chunk.article_id] = article_count + 1
        if len(results) >= limit:
            break
    return results


def list_knowledge_chunks(language: str = "", domain: str = "") -> List[KnowledgeChunk]:
    chunks = _load_chunks()
    if not chunks:
        return []

    filtered = []
    for chunk in chunks:
        if language and chunk.language not in (language, "multi", ""):
            continue
        if domain and chunk.domain != domain:
            continue
        filtered.append(chunk)

    return sorted(filtered, key=lambda item: (item.domain, item.title, item.section))


def route_domains(message: str) -> List[str]:
    text = message.lower()
    domains = []
    keyword_map = {
        "attachment": (
            "apego", "attachment", "ansioso", "anxious", "evitativo", "avoidant",
            "abandono", "abandonment", "rechazo", "seguro", "secure", "ciclo",
            "cycle", "ruptura", "repair", "reparar", "reparacion", "traicion",
            "betrayal", "infidelidad", "confianza", "trust", "lesion", "injury",
            "desorganizado", "disorganized", "desamor", "desenamor", "falling out",
            "dopamina", "dopamine", "oxitocina", "oxytocin", "vasopresina",
            "vasopressin", "cortisol", "coregulacion", "coregulation", "terapia",
            "therapy", "reality testing", "prueba de realidad", "fear testing",
            "earned secure", "apego ganado", "contrato secreto", "secret contract",
            "carp", "cyberball", "secure mode", "modo seguro", "secure priming",
            "rejection sensitivity", "sensibilidad al rechazo", "ainsworth",
            "strange situation", "situacion extraña", "base segura", "secure base",
            "inversion rapida", "invierto emocionalmente", "emotionally invested",
            "fast attachment", "apego rapido", "defensiva", "defensive",
            "defensivo", "distancia", "distance", "se aleja", "cerrarse",
            "se cierra", "evita", "avoidance", "shutdown",
            "persona no disponible", "personas no disponibles", "unavailable",
            "familiaridad con seguridad", "self sourcing", "autocubrir",
            "recondicionamiento", "herida nuclear", "migajas",
        ),
        "relationships": (
            "relacion", "relationship", "pareja", "partner", "conflicto", "conflict",
            "comunicacion", "communication", "limite", "boundary", "cita", "dating",
            "inner work of relationships", "conscious relationship", "relacion consciente",
            "herida relacional", "heridas", "rechazo", "juicio", "desbordamiento",
            "desconfianza", "insuficiencia", "inseguridad", "reaseguro", "ruptura",
            "reparacion", "inner child", "niño interior",
            "my ex", "mi ex", "breakup", "ruptura amorosa", "closure", "cierre", "move on",
            "soltar", "duelo", "grief", "potential", "potencial", "settling",
            "conformarse", "mind reading", "leer la mente", "pedir", "asking",
            "needs", "necesidades", "resentimiento", "attunement", "sintonia",
            "valores", "values", "self compassion", "autocompasion",
            "defensiva", "defensive", "defensivo", "distancia", "distance",
            "se aleja", "se cierra", "evita", "avoidance", "hablar con",
            "no contacto", "no contact", "me quedo", "me voy", "stay or go",
            "diferencia", "otredad", "lealtades", "dinamicas de pareja",
            "señales confusas", "senales confusas", "claridad dating",
            "texting", "perder identidad", "perdida de identidad",
            "intensidad intimidad", "identidad en la relacion", "dating claridad",
        ),
        "polarity": (
            "masculino", "masculine", "femenino", "feminine", "polaridad", "polarity",
            "deseo", "desire", "liderar", "lead", "presencia", "presence",
            "atraccion", "attraction", "despolarizacion", "depolarization",
            "energia masculina", "energia femenina", "nice guy", "complacencia",
            "holding frame", "sostener el marco", "tension emocional",
            "liderazgo masculino", "masculine leadership", "grounded",
            "energía masculina", "energía femenina", "dark feminine", "light feminine",
            "receptividad", "receptiva", "desapego", "detachment", "black cat", "white cat",
        ),
        "somatics": (
            "cuerpo", "body", "somatico", "somatic", "nervioso", "nervous", "vagal",
            "meditar", "meditation", "respirar", "breath", "ansiedad", "anxiety",
            "meditacion", "meditación", "visualizacion", "visualización", "gratitud",
            "gratitude", "abundancia", "abundance", "confianza", "surrender",
            "soltar", "breathwork", "trauma somatico", "trauma somático",
            "sistema nervioso", "reset nervioso", "tension", "tensión",
        ),
        "self_improvement": (
            "conciencia", "consciousness", "mejorar", "improve", "crecimiento", "growth",
            "habito", "habit", "disciplina", "discipline", "proposito", "purpose",
            "valores", "values", "mindset", "sombra", "shadow", "madurez", "maturity",
            "responsabilidad", "responsibility", "presencia", "awareness", "self-awareness",
            "inner work", "ego", "self", "creencia-raiz", "creencia raiz", "root belief",
            "root program", "trigger", "triggers", "autoindagacion", "niño interior",
            "inner child", "self-worth", "valor propio",
            "identidad", "identity", "reinvencion", "reinvention", "cambio",
            "change", "limites", "boundaries", "paz interna", "inner peace",
            "energia", "energy", "autoimagen", "self image", "duda", "self doubt",
            "confianza", "confidence", "workflow growth", "reprogramacion",
            "possible selves", "posibles yos", "agencia", "agency",
        ),
    }
    for domain, words in keyword_map.items():
        if any(word in text for word in words):
            domains.append(domain)
    if _attachment_style_context(message) and "attachment" not in domains:
        domains.append("attachment")
    return domains or ["relationships"]


def brain_root() -> Path:
    return Path(__file__).resolve().parents[4] / "brain" / "knowledge"


def packaged_brain_root() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "brain" / "knowledge"


@lru_cache(maxsize=1)
def _load_chunks() -> Tuple[KnowledgeChunk, ...]:
    root = brain_root() if brain_root().exists() else packaged_brain_root()
    if not root.exists():
        return ()

    chunks: List[KnowledgeChunk] = []
    for path in root.rglob("*.md"):
        if "templates" in path.parts or path.name == "README.md":
            continue
        article = _parse_article(path)
        if article:
            chunks.extend(_article_to_chunks(article))
    return tuple(chunks)


def _parse_article(path: Path) -> Dict:
    raw = path.read_text(encoding="utf-8")
    metadata, body = _parse_frontmatter(raw)
    domain = metadata.get("domain") or _domain_from_path(path)
    article_id = metadata.get("id") or path.stem
    language = metadata.get("language", "es")
    polarity_lane = metadata.get("polarity_lane", "")
    if domain == "polarity" and not polarity_lane:
        polarity_lane = "shared_principle"
    topics = metadata.get("topics", [])
    if isinstance(topics, str):
        topics = [topics]

    title_match = re.search(r"^#\s+(.+)$", body, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem.replace("-", " ").title()

    return {
        "id": article_id,
        "path": path,
        "title": title,
        "domain": domain,
        "language": language,
        "polarity_lane": polarity_lane,
        "topics": topics,
        "body": body,
        "source_notes": _extract_section(body, "Source Notes"),
    }


def _parse_frontmatter(raw: str) -> Tuple[Dict, str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    metadata = _parse_simple_yaml(parts[1])
    return metadata, parts[2].strip()


def _parse_simple_yaml(text: str) -> Dict:
    metadata: Dict[str, object] = {}
    current_key = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") and current_key:
            metadata.setdefault(current_key, [])
            if isinstance(metadata[current_key], list):
                metadata[current_key].append(stripped[2:].strip())
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            current_key = key.strip()
            value = value.strip()
            metadata[current_key] = _parse_yaml_value(value)
    return metadata


def _parse_yaml_value(value: str):
    if not value:
        return []
    if value.startswith("[") and value.endswith("]"):
        return [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]
    return value.strip("'\"")


def _article_to_chunks(article: Dict) -> List[KnowledgeChunk]:
    sections = _split_sections(article["body"])
    example_language = _section_content(sections, "Example Eldric Language")
    chunks = []
    for section, content in sections:
        section_key = section.strip().lower()
        if section_key in NON_CONTENT_SECTIONS or section_key in AUXILIARY_CONTENT_SECTIONS:
            continue
        chunk_content = content.strip()
        if section_key == "coaching moves" and example_language:
            chunk_content = f"{chunk_content}\n\nExample Eldric language:\n{example_language}"
        if len(chunk_content.strip()) < 80:
            continue
        section_id = _slug(section)
        chunks.append(
            KnowledgeChunk(
                id=f"{article['id']}/{section_id}",
                article_id=article["id"],
                title=article["title"],
                section=section,
                content=chunk_content.strip(),
                domain=article["domain"],
                language=article["language"],
                polarity_lane=article["polarity_lane"],
                topics=article["topics"],
                source_notes=article["source_notes"],
            )
        )
    return chunks


def _split_sections(body: str) -> List[Tuple[str, str]]:
    matches = list(re.finditer(r"^##\s+(.+)$", body, flags=re.MULTILINE))
    if not matches:
        return [("Article", body)]
    sections = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections.append((match.group(1).strip(), body[start:end].strip()))
    return sections


def _extract_section(body: str, section_name: str) -> str:
    for section, content in _split_sections(body):
        if section.lower() == section_name.lower():
            return content.strip()
    return ""


def _section_content(sections: List[Tuple[str, str]], section_name: str) -> str:
    for section, content in sections:
        if section.lower() == section_name.lower():
            return content.strip()
    return ""


def _score_chunk(
    chunk: KnowledgeChunk,
    query_terms: Iterable[str],
    routed_domains: List[str],
    polarity_lane_context: str,
    attachment_style_context: str,
) -> float:
    terms = set(query_terms)
    haystack = " ".join([chunk.title, chunk.section, chunk.content, " ".join(chunk.topics)]).lower()
    term_score = sum(1 for term in terms if term in haystack)
    topic_score = len(terms.intersection(set(chunk.topics))) * 2
    score = term_score + topic_score
    has_specific_match = score > 0 or bool(polarity_lane_context) or bool(attachment_style_context)
    if chunk.domain in routed_domains and has_specific_match:
        score += 3
    if polarity_lane_context and chunk.polarity_lane == polarity_lane_context:
        score += 5
    if attachment_style_context and chunk.domain == "attachment":
        score += 2
    return float(score)


def _attachment_style_context(message: str) -> str:
    text = message.lower()
    disorganized_cues = (
        "un dia quiero", "un día quiero", "al siguiente paso", "desaparezco y vuelvo",
        "me acerco y luego", "me alejo y luego", "no se si quiero estar",
        "no sé si quiero estar", "quiero verla y al siguiente", "quiero verlo y al siguiente",
    )
    anxious_cues = (
        "miro el movil", "miro el móvil", "si no escribe", "si no contesta",
        "si tarda en contestar", "no le importo", "lo pierdo", "la pierdo",
        "me olvida", "miedo no gustar", "se va a cansar de mi", "se va a cansar de mí",
        "necesitaba mas contacto", "necesitaba más contacto", "necesito mas contacto",
        "necesito más contacto", "asegurarme enseguida", "se me escapa",
        "pánico", "panico", "temblando", "hice algo mal",
    )
    avoidant_cues = (
        "prefiero callarme", "me bloqueo", "me cierro", "me voy al garaje",
        "pongo la tele", "desaparecer", "desaparezco", "me agobio", "me agobia",
        "siento presión", "siento presion", "interrogatorio", "reportando todo el dia",
        "reportando todo el día", "disponible siempre", "dejarlo morir",
        "conversación incómoda", "conversacion incomoda", "obligación", "obligacion",
        "quiero que se calme el tema", "me dan ganas de cortar todo",
    )
    secure_cues = (
        "puedo aceptar", "no me hundiria", "no me hundiría", "sin presión", "sin presion",
        "hablar claro", "quiero hacerlo honesto", "no es una crisis", "hablamos bien",
        "puedo esperar", "marco realista", "no necesito que me prometa nada",
    )

    anxious_score = _phrase_score(text, anxious_cues)
    avoidant_score = _phrase_score(text, avoidant_cues)
    if _phrase_score(text, disorganized_cues) >= 1 or (anxious_score >= 1 and avoidant_score >= 1):
        return "disorganized"
    if anxious_score >= 1:
        return "anxious"
    if avoidant_score >= 1:
        return "avoidant"
    if _phrase_score(text, secure_cues) >= 1:
        return "secure"
    return ""


def _phrase_score(text: str, phrases: Tuple[str, ...]) -> int:
    return sum(1 for phrase in phrases if phrase in text)


def _is_attachment_style_chunk(chunk: KnowledgeChunk, style: str) -> bool:
    topics = set(chunk.topics)
    if f"{style}_attachment" in topics:
        return True
    return chunk.article_id in ATTACHMENT_STYLE_ARTICLE_IDS.get(style, set())


def _is_other_attachment_style_chunk(chunk: KnowledgeChunk, style: str) -> bool:
    return any(
        other_style != style and _is_attachment_style_chunk(chunk, other_style)
        for other_style in ATTACHMENT_STYLE_ARTICLE_IDS
    )


def _polarity_lane_context(message: str) -> str:
    text = message.lower()
    feminine_cues = (
        "energia femenina", "energía femenina", "feminine energy", "feminine",
        "femenina", "mujer", "mujeres", "dark feminine", "light feminine",
        "black cat", "white cat", "receptiva", "receptividad",
    )
    masculine_cues = (
        "energia masculina", "energía masculina", "masculine energy", "masculine",
        "masculino", "hombre masculino", "liderazgo masculino",
    )
    if any(cue in text for cue in feminine_cues):
        return "feminine_advice"
    if any(cue in text for cue in masculine_cues):
        return "masculine_advice"
    return ""


def _looks_like_active_partner_context(message: str) -> bool:
    text = message.lower()
    if _looks_like_breakup_context(message):
        return False
    return any(cue in text for cue in ACTIVE_PARTNER_CUES)


def _looks_like_breakup_context(message: str) -> bool:
    text = message.lower()
    return any(cue in text for cue in BREAKUP_CUES)


def _is_breakup_recovery_chunk(chunk: KnowledgeChunk) -> bool:
    topics = set(chunk.topics)
    return chunk.article_id in BREAKUP_ARTICLE_IDS or bool(topics.intersection(BREAKUP_TOPICS))


def _is_early_investment_chunk(chunk: KnowledgeChunk) -> bool:
    return chunk.article_id in EARLY_INVESTMENT_ARTICLE_IDS


def _is_active_conflict_chunk(chunk: KnowledgeChunk) -> bool:
    return chunk.article_id in ACTIVE_CONFLICT_ARTICLE_IDS


def _looks_like_early_investment_context(message: str) -> bool:
    text = message.lower()
    return any(cue in text for cue in EARLY_INVESTMENT_CUES)


def _looks_like_dating_context(message: str) -> bool:
    text = message.lower()
    cues = (
        "cita", "citas", "dating", "apps", "qué somos", "que somos",
        "exclusividad", "conociéndola", "conociendola", "conociéndolo",
        "conociendolo", "seguir conociendo", "señales confusas",
        "senales confusas", "interes real", "interés real",
    )
    return any(cue in text for cue in cues)


def _is_dating_chunk(chunk: KnowledgeChunk) -> bool:
    if chunk.domain not in {"relationships", "attachment"}:
        return False
    return chunk.article_id in DATING_ARTICLE_IDS or "dating" in set(chunk.topics)


def _terms(text: str) -> List[str]:
    words = re.findall(r"[\wáéíóúñü]+", text.lower())
    return [word for word in words if len(word) > 2 and word not in STOPWORDS]


def _domain_from_path(path: Path) -> str:
    for part in path.parts:
        if part in SUPPORTED_DOMAINS:
            return part
    return "relationships"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or "section"
