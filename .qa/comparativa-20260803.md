# Antes y después de los arreglos

Tanda 1 (sistema sin arreglar): 225 conversaciones válidas de 300 generadas.
Tanda 2 (todo corregido): 90 conversaciones válidas de 100 generadas.

Los recuentos de fallos van **por cada 100 conversaciones**: las dos tandas tienen tamaños distintos y los números brutos no se pueden comparar.

## Puntuación por eje

| Eje | Media antes | Media después | Graves antes | Graves después |
|---|---|---|---|---|
| Conducción | 1.37 | 1.46 | 33.7% | 34.3% |
| Vocabulario y tono | 2.61 | 2.57 | 5.3% | 3.3% |
| Seguridad | 1.25 | 0.5 | 35.0% | 50.0% |
| Utilidad y knowledge | 2.46 | 2.73 | 9.3% | 5.6% |

El eje de seguridad tiene 20 casos evaluados antes y solo 4 después: con esa muestra la media no significa nada. Lo que sí se puede afirmar del rail está más abajo.

## Otros indicadores

| Indicador | Antes | Después |
|---|---|---|
| Fallos de recuperación de knowledge | 14.2% | 6.7% |
| Tres turnos seguidos sin entregar nada | 2 | 0 |
| Transcripciones rotas por el propio arnés | 25% (75 de 300) | 10% (10 de 100) |

## Reparto de movimientos

| Movimiento | Antes | Después | Objetivo |
|---|---|---|---|
| recoger | 43.7% | 44.4% | 30% |
| explicar | 32.3% | 30.9% | 30% |
| proponer | 7.1% | 8.1% | 20% |
| resolver | 2.1% | 6.4% | 20% |

## Fallos de conducción

| Familia | Antes (por 100 conv.) | Después (por 100 conv.) |
|---|---|---|
| Otros | 40.4 | 11.1 |
| Abre resumiendo al usuario | 31.1 | 47.8 |
| Mezcla varios movimientos | 10.2 | 1.1 |
| Dos o más preguntas en un turno | 6.2 | 7.8 |
| Pregunta en un turno que no la admite | 6.2 | 12.2 |
| Pregunta por causas o por la otra persona | 4.9 | 1.1 |
| Plan o consejo cuando tocaba recoger | 4.0 | 1.1 |
| Paso sin concretar | 2.2 | 0.0 |
| Explicar sin nombrar patrón | 2.2 | 7.8 |
| Le pide al usuario que identifique su patrón | 0.4 | 0.0 |
| Pide permiso para continuar | 0.4 | 0.0 |

## Vocabulario y tono

| Familia | Antes (por 100 conv.) | Después (por 100 conv.) |
|---|---|---|
| Palabra vetada | 23.6 | 15.6 |
| Prosa poética o metáfora | 2.7 | 0.0 |
| Cierre de aliento no pedido | 0.4 | 0.0 |
| Estructura 'no es X, es Y' | 0.4 | 0.0 |
| Tono de terapeuta | 0.0 | 2.2 |
| Validación no pedida | 0.0 | 2.2 |
| Otros | 0.0 | 2.2 |
| Pregunta retórica final | 0.0 | 1.1 |

## Lo que queda abierto

1. **Abrir resumiendo al usuario** es el fallo que no baja. Casi siempre empieza literal por "Entendido:". Después de medir esto he añadido una lista de aperturas prohibidas al bloque de conducción; esa corrección todavía no está medida.
2. **El reparto sigue escorado.** `resolver` ha pasado del 2,1% al 6,4%, pero el objetivo es 20%. La causa es que el planificador simulado rara vez marca `intentos` como contestado.
3. **Seguridad**: el rail ahora detecta violencia sin sujeto, control coercitivo e ideación pasiva, y el arnés lo ejecuta igual que producción. Los dos fallos que quedan (qa-050, qa-075) son de conversaciones que los agentes escribieron sin pasar por el arnés, así que el rail no llegó a correr.