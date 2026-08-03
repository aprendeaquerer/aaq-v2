# Conducción de la conversación

Esquema con el que Eldric decide qué hace en cada turno. La lógica vive en
`backend/app/services/brain/conversation_flow.py` y se inyecta en el prompt desde
`coaching_planner.compose_session_prompt`.

El reparto entre escuchar, explicar, proponer y resolver no se deja al criterio del modelo.
El planificador (LLM) informa de **qué ve**; el motor decide en Python **qué movimiento toca**.

---

## Capa A — Tipo de turno

El planificador clasifica cada mensaje en uno de cinco tipos:

| Tipo | Señal | Qué activa |
|---|---|---|
| `crisis` | Riesgo para la persona o para otro | Rail fijo. Corta todo lo demás. |
| `duda` | Pregunta concreta e informativa | Respuesta directa. Sin bucle. |
| `descarga` | Relato emocional sin petición | Recoger. Sin plan. |
| `situacion` | Problema concreto con hechos | Bucle completo. |
| `seguimiento` | Vuelve tras un paso acordado | Empieza por el resultado del paso. |

---

## Capa B — La ficha de seis huecos

El motor de curiosidad. El planificador mantiene seis huecos con estado
`pending` / `filled` / `skipped`. Los vacíos son lo único por lo que Eldric puede preguntar.

| Clave | Qué es | Pregunta de referencia |
|---|---|---|
| `hecho` | Secuencia observable | ¿Qué pasó exactamente? |
| `frecuencia` | Cuántas veces, desde cuándo | ¿Cuánto lleva pasando? |
| `conducta_propia` | Qué hace el usuario cuando pasa | ¿Qué haces tú entonces? |
| `intentos` | Qué ha probado y con qué resultado | ¿Qué has probado ya? |
| `objetivo` | Qué quiere que sea distinto | ¿Qué quieres conseguir? |
| `supuesto` | Lo que da por hecho sin verificar | ¿En qué lo notas? |

Reglas:

- Orden de pregunta: `hecho`, `objetivo`, `supuesto`, `intentos`, `conducta_propia`, `frecuencia`.
- `frecuencia`, `conducta_propia` e `intentos` no se preguntan hasta que hay un `hecho` concreto.
- Una pregunta por turno. Siempre.
- `supuesto` se activa cuando la persona afirma algo sobre otro como si fuera un hecho.
  La pregunta va al indicio observable, nunca a la causa.

**Umbrales:**

- Explicar: `hecho` + `objetivo` + uno cualquiera más.
- Proponer y resolver: además, `intentos` en `filled` o `skipped`.

---

## Capa C — Los cuatro movimientos

`recoger` → `explicar` → `proponer` → `resolver`.

Un movimiento dominante por respuesta, uno secundario como máximo, nunca tres.
La dosis de cada uno (longitud, prohibiciones, si lleva pregunta) está en
`conversation_flow._INSTRUCCIONES` y en `response-composition.md`.

---

## Capa D — Las dos deudas

Lo que mantiene el equilibrio sin secuencia rígida:

- **Deuda de valor**: nunca un tercer turno seguido de `recoger`. Al llegar a dos, el motor
  fuerza `explicar`, con lectura parcial si hace falta.
- **Deuda de contexto**: no se llega a `resolver` con `intentos` en `pending`. El motor
  retiene el movimiento en `proponer`.

Reparto de referencia sobre diez turnos: 30% recoger, 30% explicar, 20% proponer, 20% resolver.
El estado guarda un contador `reparto` para revisarlo desde el panel de debug.

---

## Capa E — Tránsito y vuelta atrás

- `drift = "objetivo_nuevo"` reinicia el bucle entero.
- `drift = "corrige"` o `hecho_nuevo = true` invalidan la lectura y la propuesta ya dadas.
- `resistencia = true` dos turnos seguidos: el motor avanza de movimiento en lugar de repetir.
  Eldric no reformula ni insiste.
- Después del paso, `drift = "profundiza"` devuelve a `recoger` para el siguiente paso.

---

## Estado persistido

Vive dentro de `coaching_plans.plan_json`, bajo la clave `conversacion`. No hay migración de BD.

```json
{
  "tipo_turno": "situacion",
  "movimiento": "explicar",
  "movimiento_anterior": "recoger",
  "turnos_recoger_seguidos": 0,
  "lectura_dada": true,
  "propuesta_dada": false,
  "paso_dado": false,
  "rechazos": 0,
  "hueco_pendiente": "intentos",
  "reparto": {"recoger": 2, "explicar": 1, "proponer": 0, "resolver": 0}
}
```

Si el planificador falla, `conversacion` no existe, no se inyecta bloque de movimiento y
Eldric sigue con las reglas base del prompt. Degrada sin romper.

---

## Origen de las reglas de pregunta

Las reglas de forma vienen del Tema 2 del máster de coaching (preguntas poderosas):
breves, abiertas, un solo tema, en segunda persona, sobre la experiencia propia.
Añadidas al prompt: el inicio de la pregunta marca el nivel de la respuesta
(*qué* → conducta, *cómo* → capacidad y acción, *cuándo/dónde* → contexto), y la técnica de
repetir la palabra clave en interrogativo.

Los manuales del máster no están cargados como knowledge recuperable, y no hace falta que lo
estén: aquí funcionan como reglas de método, no como contenido que Eldric deba citar.
