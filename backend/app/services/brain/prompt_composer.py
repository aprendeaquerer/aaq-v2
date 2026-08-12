from app.services.brain.types import BrainContext


def compose_brain_prompt(base_prompt: str, context: BrainContext) -> str:
    sections = []

    if context.knowledge_chunks:
        knowledge_lines = ["\n\nRELEVANT ELDRIC KNOWLEDGE BRAIN:"]
        for index, chunk in enumerate(context.knowledge_chunks, start=1):
            topics = ", ".join(chunk.topics) if chunk.topics else "general"
            knowledge_lines.append(
                f"{index}. [{chunk.domain}/{chunk.section}] {chunk.content}\n"
                f"   Article: {chunk.title}. Topics: {topics}."
            )
        sections.append("\n".join(knowledge_lines))

    if context.user_memories:
        memory_lines = ["\n\nRELEVANT USER MEMORY BRAIN:"]
        for index, memory in enumerate(context.user_memories, start=1):
            confidence = memory.get("confidence")
            confidence_text = f", confidence {confidence:.2f}" if isinstance(confidence, (int, float)) else ""
            memory_lines.append(
                f"{index}. ({memory['type']}, {memory.get('status', 'memory')}{confidence_text}) "
                f"{memory.get('curated_summary') or memory['summary']}"
            )
        sections.append("\n".join(memory_lines))

    # 2026-08-12, reset a cero por decision de la propietaria: la seccion RESPONSE
    # STRATEGY y las instrucciones de uso de memoria desaparecen con el resto de
    # reglas. Solo se pasan los datos: fragmentos del libro y memorias del usuario.
    return base_prompt + "".join(sections)
