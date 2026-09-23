# Eval suite (Fase 3 del plan de mejora)

`scripts/eval_suite.py` corre escenarios multi-turno contra el pipeline real
(`PipelineRunner`, el mismo que usan `POST /conversation/message` y voz) y
califica cada turno de dos formas:

1. **Checks determinísticos** definidos en el YAML del escenario
   (`expect.intent`, `expect.strategy_type`, `expect.must_mention`,
   `expect.must_not_mention`).
2. **LLM-as-judge**: relevancia, adherencia a la táctica, no-invención de
   datos, idioma correcto. Atrapa regresiones de calidad que los checks
   determinísticos no ven (una respuesta con el intent correcto pero grosera,
   o que inventa un descuento que nunca se ofreció).

Un escenario "pasa" solo si TODOS los checks determinísticos pasan Y el score
del judge supera `--threshold` (default 0.7). El exit code es no-cero si
algún escenario falla — pensado como gate de CI / pre-publish, no solo reporte.

## Uso

```bash
# necesita la DB con al menos un agent_version publicado, y OPENAI_API_KEY/
# ANTHROPIC_API_KEY según settings.primary_llm_provider
python -m scripts.eval_suite --agent <agent_version_id>

# JSON a stdout (para inspección rápida)
python -m scripts.eval_suite --agent <id> --json

# JSON directo a archivo — usar esto para baselines/CI. El echo de SQLAlchemy
# en dev (connection.py) ensucia stdout de forma que ni --json ni redirección
# de logging alcanzan a limpiar del todo; --output evita el problema del todo
# escribiendo directo al archivo, sin pasar por stdout.
python -m scripts.eval_suite --agent <id> --output tests/evals/baseline.json

# vía Makefile
make eval AGENT=<agent_version_id>
```

## Escribir un escenario nuevo

`tests/evals/scenarios/*.yaml`:

```yaml
name: nombre_del_escenario
description: qué está probando y por qué
turns:
  - client: "mensaje del cliente"
    expect:
      intent: objection          # opcional — valor exacto de core.enums.Intent
      strategy_type: price_defense  # opcional — valor exacto de core.enums.StrategyType;
                                     # usar con cuidado, la selección de estrategia es
                                     # scored/no-determinística, varias pueden ser válidas
      must_mention: ["financiamiento"]      # opcional, substrings (case-insensitive)
      must_not_mention: ["50% de descuento"] # opcional, substrings que NO deben aparecer
```

Cada escenario abre su propia conversación (cliente/organización efímeros,
igual que `eval_conversation.py`) y corre sus turnos en secuencia sobre esa
misma conversación, así el segundo turno ve el historial del primero.

## `baseline.json`

Snapshot de una corrida real contra el agente de dev local
(`Audi Miami South Agent`, `agent_version_id=f1312657-afb4-4089-a43b-548e39176fac`
al momento de generarlo, 2026-09-23). **No es un diff automático de CI** — el
judge usa un LLM con algo de variabilidad turno a turno, así que compararlo
byte a byte contra una corrida nueva va a dar falsos positivos. Es un punto de
referencia para revisión humana: si una corrida nueva tiene `judge_score`
notablemente más bajo en el mismo escenario, o un check determinístico que
antes pasaba ahora falla, ahí sí hay una regresión real que investigar.

Al agregar/cambiar escenarios, o al re-publicar el agente contra el que se
generó, regenerar con `--output tests/evals/baseline.json` y commitear.
