"""PDF report generation for attachment style results."""

import io
from typing import Dict, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from app.data.test_questions import get_style_description, get_relationship_description


def generate_attachment_report(
    nombre: Optional[str],
    attachment_style: str,
    scores: Dict[str, float],
    partner_style: Optional[str] = None,
    relationship_status: Optional[str] = None,
    language: str = "es",
) -> bytes:
    """Generate a PDF report with attachment style results."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=inch, bottomMargin=inch)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=24, spaceAfter=20)
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontSize=16, spaceAfter=12)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=12, spaceAfter=8, leading=16)

    elements = []

    # Title
    elements.append(Paragraph("Aprende a Querer", title_style))
    elements.append(Paragraph("Reporte de Estilo de Apego", heading_style))
    elements.append(Spacer(1, 20))

    if nombre:
        elements.append(Paragraph(f"Nombre: {nombre}", body_style))
        elements.append(Spacer(1, 10))

    # Main result
    description = get_style_description(attachment_style, language)
    elements.append(Paragraph(f"Tu estilo de apego: {attachment_style.upper()}", heading_style))
    elements.append(Paragraph(description, body_style))
    elements.append(Spacer(1, 15))

    # Scores
    elements.append(Paragraph("Puntuaciones:", heading_style))
    for style, score in scores.items():
        elements.append(Paragraph(f"  {style.capitalize()}: {score}/10", body_style))
    elements.append(Spacer(1, 15))

    # Partner results if available
    if partner_style and relationship_status:
        elements.append(Paragraph(f"Estilo de apego de tu pareja: {partner_style.upper()}", heading_style))
        rel_desc = get_relationship_description(relationship_status, language)
        elements.append(Paragraph(rel_desc, body_style))

    doc.build(elements)
    return buffer.getvalue()
