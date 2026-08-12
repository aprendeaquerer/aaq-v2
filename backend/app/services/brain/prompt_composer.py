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
        memory_lines.append(
            "Use these memories only if they are directly relevant. Active high-confidence memories are direct "
            "user-given data. Candidate memories are saved and useful, but treat them gently and do not overstate "
            "them. Do not invent memories."
        )
        sections.append("\n".join(memory_lines))

    if sections:
        sections.append(
            "\n\nRESPONSE STRATEGY:\n"
            "Use the knowledge naturally, not as a citation dump. It is the source material "
            "for the teaching part of every reply: pick the ONE idea that best fits what she "
            "just said and land it on her concrete case — never a general lecture. The "
            "CONDUCCION DE LA CONVERSACION block (further below, if present) decides what "
            "kind of teaching this turn carries. Use the user context and memories to make "
            "both the teaching and the final question more specific to HER; the more you "
            "know about this user, the more personal the reply must get. Do not invent "
            "memories."
        )

    return base_prompt + "".join(sections)
