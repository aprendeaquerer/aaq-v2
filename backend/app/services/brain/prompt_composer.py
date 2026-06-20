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
            memory_lines.append(f"{index}. ({memory['type']}) {memory['summary']}")
        memory_lines.append("Use these memories only if they are directly relevant. Do not invent memories.")
        sections.append("\n".join(memory_lines))

    if sections:
        sections.append(
            "\n\nRESPONSE STRATEGY:\n"
            "Use the knowledge naturally, not as a citation dump. "
            "Prefer one clear insight and one grounded next step. "
            "If memory is present, refer to it gently and only when useful."
        )

    return base_prompt + "".join(sections)
