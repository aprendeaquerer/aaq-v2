from app.services.brain.types import BrainContext


def compose_brain_prompt(base_prompt: str, context: BrainContext) -> str:
    sections = []

    if context.knowledge_chunks:
        knowledge_lines = [
            "\n\nMATERIAL DEL LIBRO PARA ESTE TURNO",
            "Estos fragmentos son del metodo Aprende a Querer y se han seleccionado "
            "por su cercania con lo que la usuaria acaba de escribir.",
        ]
        for index, chunk in enumerate(context.knowledge_chunks, start=1):
            topics = ", ".join(chunk.topics) if chunk.topics else "general"
            knowledge_lines.append(
                f"{index}. [{chunk.section}]\n{chunk.content}\n"
                f"   (Topics: {topics}.)"
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

    # Primera regla despues del reset a cero (17-08-2026), elegida por la
    # propietaria: "el libro primero, luego criterio". Hasta ahora los fragmentos
    # se volcaban bajo un titulo y nada mas, sin decirle al modelo que hacer con
    # ellos, asi que los leia como ruido de fondo y contestaba con lo que el sabia.
    # Solo se anade cuando hay material: sin fragmentos, esta instruccion no aplica.
    if context.knowledge_chunks:
        sections.append(
            "\n\nCOMO USAR EL MATERIAL DEL LIBRO\n"
            "El libro es tu fuente. Si alguno de los fragmentos de arriba sirve para "
            "lo que te acaba de contar, apoya tu respuesta en el: usa su explicacion, "
            "sus distinciones y su criterio, aterrizados en el caso concreto de ella. "
            "No lo cites, no lo copies entero y no lo menciones como fuente: hablas tu.\n"
            "Si ninguno encaja, responde con criterio propio sin avisar de que el libro "
            "no lo cubre. Nunca fuerces un fragmento que no viene a cuento; es peor "
            "meter teoria que no aplica que no usar el libro en ese turno."
        )

    return base_prompt + "".join(sections)
