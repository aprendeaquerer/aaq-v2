# Pruebas de conversación de Eldric

Dos tandas, con propósitos distintos.

## Tanda sintética (cientos de conversaciones, sin coste de API)

Corre contra el prompt real, la recuperación real y el motor de movimientos real, sin backend ni
base de datos. Sirve para medir conducción, vocabulario, tono y utilidad a escala.

**No mide** el rail de seguridad de código (`safety.py`), la memoria de usuario ni el planificador
de producción.

```
# 1. rejilla de cobertura equilibrada
python3 tools/qa/coverage_grid.py --count 300 --out tools/qa/grid.json

# 2. las conversaciones las genera un modelo llamando a este helper turno a turno
#    (instrucciones completas en el arnés de la sesión de trabajo)
python3 tools/qa/turn_context.py --base-prompt
python3 tools/qa/turn_context.py --conv <fichero> --init '<persona>'
python3 tools/qa/turn_context.py --conv <fichero> --user '...' --planner '...' --prev-eldric '...'
python3 tools/qa/turn_context.py --conv <fichero> --prev-eldric '...' --close

# 3. el juez aplica tools/qa/judge_prompt.md a cada transcripción y escribe un JSON por conversación

# 4. informe
python3 tools/qa/aggregate_report.py \
    --verdicts <dir> --convs <dir> --grid tools/qa/grid.json \
    --validez <validez.json> --out-md informe.md --out-json informe.json
```

`--validez` excluye las transcripciones que rompió el propio arnés. Sin ese filtro las cifras
mienten: en la primera tanda, 75 de 300 conversaciones estaban corruptas.

## Tanda en vivo (30 conversaciones contra la app real)

Cuesta dinero y crea usuarios en la base de datos. A cambio prueba lo que la sintética no puede:
recuperación, planificador, memoria y rails de seguridad.

```
python3 tools/qa/build_live_scenarios.py --convs <dir> --grid tools/qa/grid.json --count 30
python3 tools/run_personality_simulations.py --api-url <url>
```

Los escenarios salen de las mismas personas de la tanda sintética, así que los resultados son
comparables.

## Ficheros

| Fichero | Qué hace |
|---|---|
| `coverage_grid.py` | Rejilla equilibrada por estilo, tipo de turno, relación, núcleo, género y edad. Inyecta casos de crisis. |
| `turn_context.py` | Compone el prompt real de cada turno: prompt base, knowledge recuperado y bloque de movimiento. |
| `judge_prompt.md` | Rúbrica del juez. Cuatro ejes, cita textual obligatoria. |
| `aggregate_report.py` | Agrega los veredictos en un informe con familias de fallo, cortes y las peores conversaciones. |
| `build_live_scenarios.py` | Convierte personas sintéticas en escenarios para la tanda en vivo. |
