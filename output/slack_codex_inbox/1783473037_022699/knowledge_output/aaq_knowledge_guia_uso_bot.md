# Guia de uso del knowledge AAQ para el bot

Fuente valida: solo `Archivo.zip` del hilo Slack `1783473037.022699`.

## Entregables

- `aaq_knowledge_bot_estructurado.md`: texto completo extraido, organizado por fuente, pagina, outline y tags.
- `aaq_knowledge_chunks.jsonl`: version machine-readable para ingesta en una base vectorial o RAG.
- `aaq_knowledge_bot_estructurado.pdf`: copia legible del mismo contenido estructurado.

## Regla principal

No usar knowledge antiguo para responder sobre este material. Si falta informacion en estos chunks, el bot debe decir que no tiene fuente suficiente.

## Flujo de recuperacion recomendado

1. Clasificar la pregunta del usuario en tags de recuperacion.
2. Buscar chunks por tag + palabras clave + outline_context.
3. Traer chunks vecinos cuando el contenido parezca continuar en paginas siguientes.
4. Comprobar limites, advertencias y contradicciones antes de responder con seguridad.
5. Responder en lenguaje natural sin inventar contenido no presente en las fuentes.

## Tags disponibles

- `apego_ansioso`: Usar cuando el usuario muestra hiperactivacion, miedo al abandono, necesidad de confirmacion, protesta o inversion emocional rapida.
- `apego_evitativo`: Usar cuando el usuario describe distancia, cierre emocional, miedo a dependencia, desconexion o estrategias de desactivacion.
- `apego_seguro`: Usar para criterios de seguridad, base segura, comunicacion estable y pasos hacia seguridad ganada.
- `apego_desorganizado`: Usar cuando aparecen oscilaciones intensas, miedo al vinculo y al abandono, o respuestas contradictorias.
- `regulacion_emocional`: Usar para explicar sistema nervioso, autorregulacion, corregulacion, emociones y tolerancia corporal.
- `conflicto_reparacion`: Usar en discusiones, ciclos negativos, reparacion, lesiones de apego, confianza y comunicacion dificil.
- `dating_eleccion_pareja`: Usar para citas, filtros, compatibilidad, mentalidad de dating e inversion emocional inicial.
- `duelo_ruptura`: Usar para rupturas, contacto cero, cierre, recaidas, duelo y reconstruccion de identidad.
- `polaridad`: Usar para contenido de polaridad, registro femenino/masculino, liderazgo, deseo y atraccion.
- `pat_stedman_hombres`: Usar para material especifico de hombres, psicologia masculina, caracter, liderazgo y relacion desde masculino.
- `practicas_ejercicios`: Usar cuando el bot necesite proponer o explicar ejercicios, protocolos, meditaciones o practicas somaticas presentes en la fuente.
- `limites_advertencias`: Usar para cautelas, terapia, limites, seguridad emocional y senales que requieren cuidado.
- `codependencia`: Usar para dependencia emocional, autoabandono, dinamicas ansioso-evitativas y dificultad para soltar.
- `verguenza_sombra_nino_interior`: Usar para vergüenza, ego, sombra, niño interior, heridas nucleares y trabajo interior.
- `contradicciones`: Usar para revisar tensiones entre fuentes antes de dar una respuesta categorica.
