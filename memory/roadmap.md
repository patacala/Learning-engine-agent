# ProSales — Roadmap de Desarrollo

## Visión

ProSales es un **sistema cognitivo especializado en interacción humana** que:
- Piensa antes de hablar (12+ pasos de cognición antes del LLM)
- Aprende de expertos reales (training module → patrones estructurados)
- Mejora con cada conversación (episodic memory + feedback loop)
- Tiene identidad profunda (no un prompt, sino un modelo mental completo)
- Es independiente y desacoplado (API que cualquier sistema puede consumir)

---

## Completado

### Sprint 1 — Observabilidad Cognitiva ✅
- PipelineExecution model, _timed wrapper, 6 atomic events
- Decision Timeline con RuleEvaluation (qué regla matcheó y por qué)
- Strategy Timeline con StrategyTrace (candidatos, scores, switched)
- Timeline API: GET /conversation/{id}/timeline con filtro por event_type
- Structured logging: structlog (JSON prod / ConsoleRenderer dev)
- Decision Trace embebido: cada decisión guarda el "por qué"
- 50 unit tests

### Sprint 2 → Sprint 3 — Agent Architecture ✅
- Refactoring completo: Workspace → Agent-centric
- **AgentContext**: organization_id, agent_id, agent_version_id, capabilities
- **11 tablas**: organizations, agents, agent_versions, agent_identity, agent_personality, agent_rules, agent_strategies, agent_tactics, agent_prompt_templates, agent_voice, organization_agents
- **AgentContextResolver**: API key → org → agent_version → AgentContext
- **6 Providers**: Identity, Personality, Rule, Strategy, Prompt, Voice (cache TTL 300s)
- **Capability split**: org (knowledge, inventory) vs agent (voice, negotiation)
- **Templates**: ORG_TEMPLATES (industry) + AGENT_TEMPLATES (sales, support, receptionist)
- Workspace code eliminado completamente
- 76 unit tests

### Sprint 4 — Identity Engine ✅
- **AgentIdentity** DTO: name, description, communication_style, compliance_notes + principles, beliefs, values, words_never_use, words_prefer
- **`@property prompt_context`**: formatea principles/values/beliefs/compliance para prompts
- **`@property language_context`**: formatea restricciones de lenguaje para prompts
- **IdentityEngine**: route → identify → (fast: personify | full: retrieve)
- **PersonalityProfile** ahora tiene 5 capas: brand, conversation, voice, emotion, identity
- **PersonalityEngine** lee `state["identity"]` para communication_style + identity layer
- **PromptBuilder** lee identity desde state (ya no toma identity_provider en constructor)
- **words_to_avoid** removido de AgentPersonalityConfig/Model/Provider (vive en Identity)
- DB column: `values_list` (evita conflicto con SQLAlchemy `.values()`)
- Templates enriquecidos con principles, beliefs, values, words por tipo de agente
- 98 unit tests (22 nuevos)

### Sprint 5 — Episodic Memory ✅
- **Regla**: Episodic Memory registra hechos. Learning interpreta. No inferencia en episodios.
- **Episode** DTO: dominant_intent, dominant_sentiment, sentiment_shifts, final_stage, objections_detected, strategies_used, urgency/risk_signals, outcome
- **EpisodeExtractor**: agregación determinista de eventos (sin LLM)
- **EpisodicMemoryEngine**: servicio llamado desde API (no pipeline). Extrae + persiste + embedding opcional
- **API**: `POST /conversation/{id}/close` → extraer Episode, `PATCH /conversation/{id}/episode` → feedback CRM
- **MemoryEngine** mejorado: `episodic_repo` param, carga `client_episodes` como `EpisodeSummary` list
- **ContextBuilder** mejorado: agrega contexto histórico factual de episodios
- DB: tabla `episodic_memories` (migration 005), unique on conversation_id
- 116 unit tests (18 nuevos)

### Sprint 6 — Training Module ✅
- **TrainingExtractor**: usa `complete_json(temperature=0.2)` para extracción estructurada de 10 tipos de patrón
- **Tipos de patrón**: technique, objection_handling, needs_discovery, closing, signal, identity:principle/belief/value/words_never_use/words_prefer
- **Proposals con supervisión**: patrones guardados como pending, revisión via PATCH approve/reject
- **AudioTranscriber**: OpenAI Whisper API ($0.006/min), soporta mp3/mp4/m4a/wav/webm, 25MB límite
- **TrainingApprover**: identity:* → append a AgentIdentity JSONB arrays; otros → `index_document()` a knowledge_documents
- **API**: `POST /training/ingest`, `GET /sessions`, `GET /sessions/{id}/proposals`, `PATCH /proposals/{id}`
- DB: tablas `training_sessions` + `training_proposals` (migration 006)
- 130 unit tests (14 nuevos)

### Sprint 7 — Training UI + v2 Redesign ✅
- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS v4 en `frontend/`
- **Diseño ChatGPT Light Mode**: monocromático (#f9f9f9 sidebar, #0d0d0d texto, #6e6e80 secundario, #e3e3e3 bordes)
- **SSE streaming**: POST /ingest → StreamingResponse con stages
- **Source label auto-inferido**: LLM genera título corto, fallback a transcript[:50]
- **Session continuity**: ingest acepta `session_id` opcional para agregar a sesión existente
- **Batch approve**: `PATCH /proposals/batch` para aprobar/rechazar en lote
- **Edit flow**: PatternCard con edit inline → textarea + "Save & Approve"
- **Agent Brain Dashboard**: SVG cerebro con 6 regiones que se llenan + cards expandibles por categoría
- **Brain endpoint**: `GET /agents/{id}/brain` → identity, knowledge counts, training stats, learned items
- **Sidebar**: tabs Sessions/Brain, delete session, new session button
- **PatternCard**: iconos por tipo, approve/edit/reject inline, expandible
- 136 unit tests (6 nuevos)

### Sprint 8 — Strategy Library ✅
- **StrategyType enum**: 8 → 30 tipos organizados en 8 categorías (discovery, presentation, objection_handling, closing, negotiation, rapport, retention, specialized)
- **Taxonomía**: `StrategyCategory`, `ClientProfile` (6 perfiles: rational, emotional, distrustful, rushed, silent, analytical), `StrategyMeta` con `stage_fit` y `client_profiles` por estrategia
- **Catálogo expandido**: 5 → 30 estrategias, cada una con 2-3 tactics accionables para el LLM
- **Signal Scorers** (arquitectura desacoplada):
  - `BaseScorer` ABC con 4 implementaciones pluggables: `IntentScorer`, `SentimentScorer`, `StageScorer`, `EpisodicScorer`
  - Agregar nuevo factor = nueva clase en `DEFAULT_SCORERS`, sin tocar el selector
  - `IntentScorer`: mapping 1:N (Intent → list[StrategyType]), ponderado por posición + confianza
  - `SentimentScorer`: boost empáticas (+0.1), penaliza urgencia (-0.1) en sentimiento negativo
  - `StageScorer`: +0.15 si `stage_fit` de taxonomía incluye etapa actual
  - `EpisodicScorer`: +0.2 por conversión, -0.15 por pérdida, cap ±0.3
- **Selector refactorizado**: combina señales de todos los scorers, backward compatible (params opcionales)
- **Multi-tactic**: `tactic_position`/`tactic_total` en StrategySelection; engine avanza posición con misma estrategia, resetea al cambiar, clamp al máximo
- **LearningEngine activado**: evalúa efectividad por shift de sentimiento, emite evento `strategy.evaluated`
- **Pipeline**: nodo `learn` después de `store` antes de `END`; `initial_sentiment` capturado en nodo analyze
- **Episodic → Strategy wiring**: episodios del memory pasados al selector para scoring
- **Templates**: sales agent 2 → 8 estrategias default (consultive, price_defense, needs_diagnosis, value_first, social_proof, feel_felt_found, assumptive_close, rapport_building)
- **Seed script**: `scripts/seed_strategies.py` — idempotente, puebla DB para versiones publicadas
- 160 unit tests (28 nuevos)

---

## Pendiente

### Sprint 9 — Integración con Retell (Voice)
Conectar el flujo real de voz:

```
Llamada telefónica → Retell → Webhook → ProSales → Respuesta → Retell → Voz
```

- Webhook endpoint para recibir llamadas
- Mapeo de eventos Retell → pipeline input
- Respuesta: texto + SSML para Retell
- Manejo de estado de llamada (inicio, en curso, fin)
- Persistencia entre turnos
- **Objetivo**: conversaciones telefónicas reales con el cognitive engine

---

### Sprint 10 — Feedback Loop + Optimización
Con datos reales de Sprint 9:

- Sales Evaluation Engine: scoring por conversación (qué se hizo bien/mal)
- Probabilidad de conversión post-conversación
- Feedback automático a episodic memory
- Strategy Engine deja de ser reglas → optimiza con datos reales
- "¿SPIN funciona mejor que Challenger con este tipo de cliente?"
- Las estrategias que no funcionan bajan de ranking automáticamente

---

### Sprint 11 — Voice Layer Avanzado
Cuando el sistema ya vende bien, mejorar naturalidad:

- Pausas inteligentes basadas en contexto (no solo reglas)
- Manejo de interrupciones
- Fillers naturales contextuales
- Prosodia adaptativa (emoción → ritmo)
- Detección de silencio del cliente → acción
- Turn-taking avanzado

---

### Tool / Action Layer (Modelo A) — que el agente ACTÚE, no solo hable

**Problema**: hoy el agente solo produce texto. Cuando dice "te agendo el sábado", no agenda nada — es ficción hasta que un humano/CRM actúe. Falta una capa de acciones/herramientas (agendar, consultar inventario, crear/actualizar contacto CRM, transferir a humano, etc.).

**Principio de diseño (preserva la separación de Cognition)**:
- Se separa **schema/intención** (Cognition sí lo conoce: existe `schedule_appointment(cuándo)`, es dominio) de **binding/ejecución** (URL, credenciales, qué app — Cognition NUNCA lo conoce).
- **Modelo A (elegido)**: Cognition es un **servidor** que solo responde. Emite las tool-calls como **datos en su respuesta** (`{response, tool_calls: [...]}`); **no hace ninguna llamada saliente**. El **CRM** (que llamó a Cognition y ya es tenant de esa org) **ejecuta** la acción con SU config de calendario/integraciones. Cognition solo lleva `org_id` (del api_key) + intención abstracta; el binding `org_id→URL` vive en el CRM.
- **Diferenciación por org**: solo por `api_key → org_id` (como ya funciona). Cognition NO guarda URLs por org; hoy ni siquiera existe config per-org (el `crm_webhook_url` es global — a migrar si algún día se necesita Modelo B).
- **Tool-loop**: si el agente necesita el resultado para seguir (verificar disponibilidad → confirmar), el CRM maneja el ida-y-vuelta (ejecuta y devuelve el resultado en el siguiente turno). Cognition solo va contestando.
- **Modelo B** (adaptador de tools en el borde de ProSales que ejecuta inline, leyendo `organization_integrations[org_id, tool]`) queda **solo** para tools que requieran ejecución en tiempo real dentro de una llamada de voz (sin poder pagar el round-trip). El motor cognitivo sigue sin ver la URL.

**Sinergia con el aprendizaje**: una acción real exitosa (agendamiento confirmado por la tool) es **señal de outcome ground-truth** — mucho mejor que inferir `scheduled` del texto. Las tools no solo hacen al agente más capaz; mejoran la calidad de la calificación/scoring.

**Alcance sugerido (por fases)**:
1. Framework de tool-calls: extender `LLMProvider` con function-calling; nodo de pipeline decide tool-calls; `PipelineResult`/`MessageResponse` exponen `tool_calls` (abstractos). Capability abstracta por agente (`can_schedule`, etc.) + schema; sin URLs ni secretos.
2. Primeras 1-2 tools de alto valor: **agendar cita** y **transferir a humano**. El CRM ejecuta.
3. Tool-loop (resultado → siguiente turno) + feed del resultado real a la calificación/outcome.
4. (Opcional/después) Modelo B: `organization_integrations` en el borde + ToolAdapter provider-agnóstico para ejecución inline en voz.

---

### Futuro — Fine-tuning
Solo cuando tengamos miles de conversaciones exitosas del training:
- Fine-tune un modelo base con conversaciones del experto
- No antes de tener Identity Engine + Episodic Memory + Strategy Library funcionando
- El fine-tuning es el último paso, no el primero

---

## Concepto Transversal: Decision Trace

Desde Sprint 1 está embebido. Cada decisión guarda el "por qué":

```json
{
  "decision": "offer_financing",
  "reason": ["budget_detected", "price_objection", "credit_score_unknown"],
  "confidence": 0.93,
  "identity_influence": "principle: nunca presionar, ofrecer alternativa",
  "episodic_match": "cliente similar en conv_xyz aceptó financiamiento"
}
```

Esto convierte a ProSales en un sistema **explicable**:
- Depurar comportamiento
- Mejorar estrategias con datos
- Ganarse confianza de clientes empresariales

---

## Nota sobre Organizations

El CRM es dueño de las organizaciones/tenants. ProSales usa `organization_id` solo para:
- Aislar knowledge store por tenant
- Asignar el agent correcto (API key → org → agent)
- Scoping de episodic memory

No duplica información del negocio (industry, business_type, etc.) — eso viene del CRM como contexto en el request si es necesario.
