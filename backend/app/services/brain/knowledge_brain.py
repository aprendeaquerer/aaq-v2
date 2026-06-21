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
    scored = []

    for chunk in chunks:
        if chunk.language not in (language, "multi", ""):
            continue
        score = _score_chunk(chunk, query_terms, routed_domains)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    results = []
    for score, chunk in scored[:limit]:
        results.append(
            KnowledgeChunk(
                id=chunk.id,
                article_id=chunk.article_id,
                title=chunk.title,
                section=chunk.section,
                content=chunk.content,
                domain=chunk.domain,
                language=chunk.language,
                topics=chunk.topics,
                source_notes=chunk.source_notes,
                score=score,
            )
        )
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
        ),
        "relationships": (
            "relacion", "relationship", "pareja", "partner", "conflicto", "conflict",
            "comunicacion", "communication", "limite", "boundary", "cita", "dating",
            "inner work of relationships", "conscious relationship", "relacion consciente",
            "herida relacional", "heridas", "rechazo", "juicio", "desbordamiento",
            "desconfianza", "insuficiencia", "inseguridad", "reaseguro", "ruptura",
            "reparacion", "inner child", "niño interior",
        ),
        "polarity": (
            "masculino", "masculine", "femenino", "feminine", "polaridad", "polarity",
            "deseo", "desire", "liderar", "lead", "presencia", "presence",
        ),
        "somatics": (
            "cuerpo", "body", "somatico", "somatic", "nervioso", "nervous", "vagal",
            "meditar", "meditation", "respirar", "breath", "ansiedad", "anxiety",
        ),
        "self_improvement": (
            "conciencia", "consciousness", "mejorar", "improve", "crecimiento", "growth",
            "habito", "habit", "disciplina", "discipline", "proposito", "purpose",
            "valores", "values", "mindset", "sombra", "shadow", "madurez", "maturity",
            "responsabilidad", "responsibility", "presencia", "awareness", "self-awareness",
            "inner work", "ego", "self", "creencia-raiz", "creencia raiz", "root belief",
            "root program", "trigger", "triggers", "autoindagacion", "niño interior",
            "inner child", "self-worth", "valor propio",
        ),
    }
    for domain, words in keyword_map.items():
        if any(word in text for word in words):
            domains.append(domain)
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
    chunks = []
    for section, content in sections:
        if len(content.strip()) < 80:
            continue
        section_id = _slug(section)
        chunks.append(
            KnowledgeChunk(
                id=f"{article['id']}/{section_id}",
                article_id=article["id"],
                title=article["title"],
                section=section,
                content=content.strip(),
                domain=article["domain"],
                language=article["language"],
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


def _score_chunk(chunk: KnowledgeChunk, query_terms: Iterable[str], routed_domains: List[str]) -> float:
    terms = set(query_terms)
    haystack = " ".join([chunk.title, chunk.section, chunk.content, " ".join(chunk.topics)]).lower()
    score = sum(1 for term in terms if term in haystack)
    if chunk.domain in routed_domains:
        score += 3
    score += len(terms.intersection(set(chunk.topics))) * 2
    return float(score)


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
