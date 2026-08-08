# Cinco tandas

Cada tanda usa personas nuevas de la rejilla. **Aviso de tamaño**: la tanda 5 tiene 26 conversaciones válidas frente a las 225 de la primera, porque los agentes generadores no completaron los lotes. Las medias por eje de la tanda 5 no son comparables con las anteriores; el reparto de movimientos sí, porque lo calcula el motor de forma determinista.

## Puntuación por eje

| Tanda | Válidas | Conducción | Vocab/tono | Seguridad | Utilidad |
|---|---|---|---|---|---|
| 1 · sin arreglar | 225 | 1.37 | 2.61 | 1.25 | 2.46 |
| 2 | 90 | 1.46 | 2.57 | 0.5 | 2.73 |
| 3 | 98 | 1.49 | 2.42 | 0.8 | 2.37 |
| 4 | 57 | 1.91 | 2.51 | 1.0 | 2.63 |
| 5 · reparto arreglado | 26 | 1.18 | 2.31 | 0.5 | 2.58 |

## Reparto de movimientos (esto es lo que se pidió arreglar)

| Tanda | recoger | explicar | proponer | resolver |
|---|---|---|---|---|
| 1 · sin arreglar | 43.7% | 32.3% | 7.1% | 2.1% |
| 2 | 44.4% | 30.9% | 8.1% | 6.4% |
| 3 | 44.0% | 31.0% | 7.9% | 0.7% |
| 4 | 44.3% | 24.6% | 7.9% | 3.9% |
| 5 · reparto arreglado | 40.7% | 35.2% | 23.1% | 1.1% |
| **objetivo** | **30%** | **30%** | **20%** | **20%** |

Medido sobre el motor, no sobre el juez, y solo en conversaciones de 4 o más turnos:
recoger **30,7%** (era 44%), proponer **28%** (era 8%), explicar 40%, resolver 1,3%.

## Por qué resolver sigue bajo

No es el motor. Es la longitud de las conversaciones de prueba. Con 5 turnos, dos de recoger y dos de explicar ya son el 80%: el paso de acción no cabe. Repitiendo las MISMAS conversaciones de la tanda 5 con dos turnos más, sin tocar una línea del motor, los pasos de acción pasan del **1,6% al 13,8%**, y 9 de 16 conversaciones llegan a un paso concreto.

Por eso el arnés ahora exige un mínimo de 5 turnos de Eldric al cerrar una conversación, y el README pide 7. Medir con 5 era medir mal.

## Qué se cambió en el motor para esto

1. **El objetivo dejó de ser obligatorio para explicar.** La gente rara vez enuncia un objetivo, y exigirlo dejaba el bucle atascado en recoger. Ahora basta un hecho concreto más dos observables.
2. **Tope de recoger por objetivo (3).** La deuda de valor solo limitaba turnos seguidos, así que alternar recoger/explicar/recoger mantenía el 44%.
3. **Tope de explicar por objetivo (2).** Un planificador que corrige cada turno mantenía la conversación explicando.
4. **La descarga deja de serlo cuando la persona empieza a trabajar.** Un lote entero de la tanda 5 marcó todos los turnos como descarga y esa rama nunca podía proponer nada, ni con la ficha llena y la lectura ya dada.
5. **El arnés exige 5 turnos mínimos** y la instrucción aclara que el tipo de la rejilla describe solo el mensaje de apertura.