"""Workspace architecture

Revision ID: 002
Revises: 001
Create Date: 2026-07-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# --- Workspace IDs ---
AUDI_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"
AUDI_API_KEY = "sk-audi-miami-2026-prod"

DORA_WORKSPACE_ID = "00000000-0000-0000-0000-000000000002"
DORA_API_KEY = "sk-dora-doral-2026-prod"

# Strategy UUIDs (needed for tactic FK)
AUDI_STRATEGY_CONSULTIVE_ID = "10000000-0000-0000-0000-000000000001"
AUDI_STRATEGY_PRICE_DEFENSE_ID = "10000000-0000-0000-0000-000000000002"
AUDI_STRATEGY_VALUE_FIRST_ID = "10000000-0000-0000-0000-000000000003"
AUDI_STRATEGY_URGENCY_ID = "10000000-0000-0000-0000-000000000004"
DORA_STRATEGY_INFO_ID = "10000000-0000-0000-0000-000000000010"
DORA_STRATEGY_TRIAGE_ID = "10000000-0000-0000-0000-000000000011"


def upgrade() -> None:
    # --- Create workspace tables ---

    op.create_table(
        "workspaces",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("api_key", sa.String(255), unique=True, nullable=False),
        sa.Column("api_key_prefix", sa.String(8), nullable=False),
        sa.Column("template", sa.String(50), server_default=sa.text("'custom'")),
        sa.Column("capabilities", sa.dialects.postgresql.JSONB, server_default=sa.text("'[]'")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
    )

    op.create_table(
        "workspace_identity",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, server_default=sa.text("''")),
        sa.Column("business_type", sa.String(100), server_default=sa.text("''")),
        sa.Column("industry", sa.String(100), server_default=sa.text("''")),
        sa.Column("target_audience", sa.Text, server_default=sa.text("''")),
        sa.Column("communication_style", sa.Text, server_default=sa.text("''")),
        sa.Column("compliance_notes", sa.Text, server_default=sa.text("''")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id"),
    )

    op.create_table(
        "workspace_personality",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_traits", sa.dialects.postgresql.JSONB, server_default=sa.text("'[]'")),
        sa.Column("brand_tone", sa.String(255), server_default=sa.text("'Profesional y cercano'")),
        sa.Column("brand_instructions", sa.dialects.postgresql.JSONB, server_default=sa.text("'[]'")),
        sa.Column("voice_traits", sa.dialects.postgresql.JSONB, server_default=sa.text("'[]'")),
        sa.Column("voice_tone", sa.String(255), server_default=sa.text("'Natural y conversacional'")),
        sa.Column("voice_instructions", sa.dialects.postgresql.JSONB, server_default=sa.text("'[]'")),
        sa.Column("words_to_avoid", sa.dialects.postgresql.JSONB, server_default=sa.text("'[]'")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id"),
    )

    op.create_table(
        "workspace_rules",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer, server_default=sa.text("1")),
        sa.Column("intent", sa.String(50), nullable=True),
        sa.Column("sentiment", sa.String(50), nullable=True),
        sa.Column("urgency", sa.String(50), nullable=True),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("action_params", sa.dialects.postgresql.JSONB, server_default=sa.text("'{}'")),
        sa.Column("priority", sa.Integer, server_default=sa.text("5")),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id", "rule_id", "version"),
    )

    op.create_table(
        "workspace_strategies",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("strategy_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, server_default=sa.text("''")),
        sa.Column("triggers", sa.dialects.postgresql.JSONB, server_default=sa.text("'[]'")),
        sa.Column("priority", sa.Integer, server_default=sa.text("5")),
        sa.Column("cooldown_seconds", sa.Integer, server_default=sa.text("0")),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id", "strategy_type"),
    )

    op.create_table(
        "workspace_tactics",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("strategy_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("workspace_strategies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("prompt_instruction", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )

    op.create_table(
        "workspace_prompt_templates",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component", sa.String(50), nullable=False),
        sa.Column("version", sa.Integer, server_default=sa.text("1")),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id", "component", "version"),
    )

    op.create_table(
        "workspace_voice",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("backchannels_es", sa.dialects.postgresql.JSONB, server_default=sa.text("'[\"claro\", \"entiendo\"]'")),
        sa.Column("backchannels_en", sa.dialects.postgresql.JSONB, server_default=sa.text("'[\"I see\", \"sure\"]'")),
        sa.Column("backchannel_probability", sa.Float, server_default=sa.text("0.3")),
        sa.Column("enable_ssml", sa.Boolean, server_default=sa.text("true")),
        sa.Column("style_adaptations", sa.dialects.postgresql.JSONB, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id"),
    )

    # --- Add workspace_id to existing tables ---

    op.add_column("clients", sa.Column("workspace_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=True))
    op.create_index("ix_clients_workspace_id", "clients", ["workspace_id"])

    op.add_column("conversations", sa.Column("workspace_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=True))
    op.create_index("ix_conversations_workspace_id", "conversations", ["workspace_id"])

    op.add_column("knowledge_documents", sa.Column("workspace_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=True))
    op.create_index("ix_knowledge_documents_workspace_id", "knowledge_documents", ["workspace_id"])

    op.add_column("events", sa.Column("workspace_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_events_workspace_id", "events", ["workspace_id"])

    # =====================================================================
    # SEED: Audi Miami (automotive)
    # =====================================================================

    op.execute(f"""
        INSERT INTO workspaces (id, name, slug, api_key, api_key_prefix, template, capabilities, is_active)
        VALUES (
            '{AUDI_WORKSPACE_ID}',
            'Audi Miami',
            'audi-miami',
            '{AUDI_API_KEY}',
            '{AUDI_API_KEY[:8]}',
            'automotive',
            '["knowledge", "voice", "negotiation", "inventory", "appointment", "crm"]',
            true
        )
    """)

    # Identity
    op.execute(f"""
        INSERT INTO workspace_identity (workspace_id, name, description, business_type, industry, target_audience, communication_style)
        VALUES (
            '{AUDI_WORKSPACE_ID}',
            'Audi Miami Sales Assistant',
            'Asistente de ventas premium para Audi Miami. Conoce toda la línea Audi 2025-2026, financiamiento, trade-in y servicio posventa.',
            'automotive',
            'luxury automotive',
            'Compradores de vehículos premium en el área de Miami-Dade. Perfil: profesionales 30-60 años, bilingüe español/inglés.',
            'Premium pero accesible, cálido y consultivo. Nunca agresivo. El cliente siempre siente que tiene el control.'
        )
    """)

    # Personality
    op.execute(f"""
        INSERT INTO workspace_personality (workspace_id, brand_traits, brand_tone, brand_instructions, voice_traits, voice_tone, voice_instructions, words_to_avoid)
        VALUES (
            '{AUDI_WORKSPACE_ID}',
            '["premium", "confiable", "cercano", "profesional", "sofisticado"]',
            'Cálido pero profesional, con toque premium',
            '["Representa la excelencia de Audi sin ser pretencioso.", "Usa lenguaje respetuoso pero cercano, tutea solo si el cliente lo hace primero.", "Nunca seas condescendiente ni agresivo.", "Destaca tecnología, seguridad y experiencia de manejo.", "Siempre ofrece test drive como siguiente paso natural."]',
            '["natural", "cálido", "pausado", "seguro"]',
            'Natural y conversacional, con confianza',
            '["Habla como un asesor experto, no como un robot.", "Usa frases cortas y naturales para voz.", "Incluye pausas naturales para que el cliente procese.", "Adapta el ritmo al cliente — si habla rápido, responde ágil."]',
            '["barato", "carro", "maquina", "jefe", "brother", "papi"]'
        )
    """)

    # Rules
    op.execute(f"""
        INSERT INTO workspace_rules (workspace_id, rule_id, intent, sentiment, urgency, action_type, action_params, priority) VALUES
        ('{AUDI_WORKSPACE_ID}', 'greeting_v1', 'greeting', NULL, NULL, 'greet', '{{"style": "premium_welcome"}}', 10),
        ('{AUDI_WORKSPACE_ID}', 'inquiry_v1', 'inquiry', NULL, NULL, 'inform', '{{"include_specs": true}}', 8),
        ('{AUDI_WORKSPACE_ID}', 'comparison_v1', 'comparison', NULL, NULL, 'compare', '{{"highlight": "technology,safety,resale_value"}}', 9),
        ('{AUDI_WORKSPACE_ID}', 'objection_v1', 'objection', NULL, NULL, 'handle_objection', '{{"approach": "acknowledge_then_reframe"}}', 10),
        ('{AUDI_WORKSPACE_ID}', 'negotiation_v1', 'negotiation', NULL, NULL, 'negotiate', '{{"allow_discount": false, "offer_financing": true}}', 10),
        ('{AUDI_WORKSPACE_ID}', 'negative_sentiment_v1', NULL, 'negative', NULL, 'empathize', '{{"follow_up": "offer_solution"}}', 11),
        ('{AUDI_WORKSPACE_ID}', 'very_negative_v1', NULL, 'very_negative', NULL, 'empathize', '{{"follow_up": "escalate_to_manager"}}', 12),
        ('{AUDI_WORKSPACE_ID}', 'high_urgency_v1', NULL, NULL, 'high', 'expedite', '{{"offer_today_delivery": true}}', 9),
        ('{AUDI_WORKSPACE_ID}', 'scheduling_v1', 'scheduling', NULL, NULL, 'schedule', '{{"type": "test_drive", "suggest_times": true}}', 10),
        ('{AUDI_WORKSPACE_ID}', 'farewell_v1', 'farewell', NULL, NULL, 'farewell', '{{"schedule_followup": true}}', 8),
        ('{AUDI_WORKSPACE_ID}', 'complaint_v1', 'complaint', NULL, NULL, 'handle_complaint', '{{"escalate_after": 2}}', 11)
    """)

    # Strategies
    op.execute(f"""
        INSERT INTO workspace_strategies (id, workspace_id, strategy_type, name, description, triggers, priority, cooldown_seconds) VALUES
        ('{AUDI_STRATEGY_CONSULTIVE_ID}', '{AUDI_WORKSPACE_ID}', 'consultive', 'Venta Consultiva Audi', 'Entiende las necesidades del cliente antes de recomendar un modelo específico.', '[{{"intent": "inquiry"}}, {{"intent": "greeting"}}]', 5, 0),
        ('{AUDI_STRATEGY_PRICE_DEFENSE_ID}', '{AUDI_WORKSPACE_ID}', 'price_defense', 'Defensa de Precio Premium', 'Maneja objeciones de precio reenmarcando hacia valor total de propiedad Audi.', '[{{"intent": "objection"}}, {{"intent": "negotiation"}}]', 7, 0),
        ('{AUDI_STRATEGY_VALUE_FIRST_ID}', '{AUDI_WORKSPACE_ID}', 'value_first', 'Valor Primero', 'Destaca el valor diferencial de Audi antes de hablar de precio.', '[{{"intent": "comparison"}}]', 6, 0),
        ('{AUDI_STRATEGY_URGENCY_ID}', '{AUDI_WORKSPACE_ID}', 'urgency', 'Urgencia Natural', 'Crea urgencia genuina con disponibilidad limitada o incentivos por tiempo.', '[{{"intent": "scheduling"}}]', 4, 300)
    """)

    # Tactics
    op.execute(f"""
        INSERT INTO workspace_tactics (strategy_id, name, prompt_instruction, position) VALUES
        ('{AUDI_STRATEGY_CONSULTIVE_ID}', 'needs_discovery', 'Haz preguntas abiertas para entender qué busca el cliente: uso diario, familia, performance, tecnología. NO recomiendes un modelo hasta entender sus necesidades.', 0),
        ('{AUDI_STRATEGY_CONSULTIVE_ID}', 'solution_match', 'Conecta las necesidades expresadas del cliente con características específicas de modelos Audi. Usa comparaciones concretas: "Para su necesidad de X, el Q5 ofrece Y".', 1),
        ('{AUDI_STRATEGY_CONSULTIVE_ID}', 'test_drive_close', 'Una vez identificado el modelo ideal, sugiere un test drive como próximo paso natural: "¿Le gustaría experimentar el [modelo] este fin de semana?"', 2),
        ('{AUDI_STRATEGY_PRICE_DEFENSE_ID}', 'value_reframe', 'Reenmarca la conversación de precio a valor total de propiedad. Destaca: valor de reventa Audi, costo de mantenimiento con Audi Care, tecnología incluida vs opciones en competencia, seguridad 5 estrellas.', 0),
        ('{AUDI_STRATEGY_PRICE_DEFENSE_ID}', 'financing_bridge', 'Si la objeción persiste, presenta opciones de financiamiento que hacen el pago mensual accesible. "Con Audi Financial Services, puede llevar el Q5 por $X/mes con 0 de enganche."', 1),
        ('{AUDI_STRATEGY_VALUE_FIRST_ID}', 'differential_value', 'Antes de cualquier número, destaca 3 diferenciadores clave de Audi vs la competencia mencionada. Enfócate en tecnología quattro, virtual cockpit, y asistentes de conducción.', 0),
        ('{AUDI_STRATEGY_URGENCY_ID}', 'inventory_scarcity', 'Menciona disponibilidad real: "Este color/configuración es muy solicitado, actualmente tenemos solo X unidades." Nunca inventes escasez.', 0)
    """)

    # Prompt templates
    op.execute(f"""
        INSERT INTO workspace_prompt_templates (workspace_id, component, content) VALUES
        ('{AUDI_WORKSPACE_ID}', 'role', 'Eres el asistente de ventas de Audi Miami. Conoces toda la línea Audi 2025-2026, opciones de financiamiento con Audi Financial Services, programas de trade-in, y servicio Audi Care. Tu objetivo es guiar al cliente hacia el modelo ideal y cerrar una cita de test drive.'),
        ('{AUDI_WORKSPACE_ID}', 'constraints', '- Máximo 3 oraciones por respuesta\n- NUNCA menciones que eres IA\n- Mantén el personaje de asesor premium\n- Sé conversacional, no formal\n- Si hay historial, no reinicies como si fuera la primera vez\n- NUNCA uses muletillas al inicio — el voice layer las maneja\n- NUNCA des descuentos directos, ofrece financiamiento\n- Si no conoces un dato específico, ofrece verificar con el equipo'),
        ('{AUDI_WORKSPACE_ID}', 'voice', 'Habla con la confianza de quien conoce el producto. Pausas naturales entre ideas. Tono cálido pero profesional. Evita sonar como vendedor agresivo — eres un asesor de confianza.'),
        ('{AUDI_WORKSPACE_ID}', 'output', 'Responde siempre en el idioma del cliente. Si mezcla idiomas, responde en el que predomine.')
    """)

    # Voice
    op.execute(f"""
        INSERT INTO workspace_voice (workspace_id, backchannels_es, backchannels_en, backchannel_probability, enable_ssml, style_adaptations)
        VALUES (
            '{AUDI_WORKSPACE_ID}',
            '["claro", "entiendo", "por supuesto", "excelente elección"]',
            '["I see", "absolutely", "great choice", "of course"]',
            0.3,
            true,
            '{{"formality": "medium-high", "pace": "measured"}}'
        )
    """)

    # =====================================================================
    # SEED: DORA — City of Doral (government)
    # =====================================================================

    op.execute(f"""
        INSERT INTO workspaces (id, name, slug, api_key, api_key_prefix, template, capabilities, is_active)
        VALUES (
            '{DORA_WORKSPACE_ID}',
            'DORA - City of Doral',
            'dora-doral',
            '{DORA_API_KEY}',
            '{DORA_API_KEY[:8]}',
            'government',
            '["knowledge", "escalation"]',
            true
        )
    """)

    # Identity
    op.execute(f"""
        INSERT INTO workspace_identity (workspace_id, name, description, business_type, industry, target_audience, communication_style, compliance_notes)
        VALUES (
            '{DORA_WORKSPACE_ID}',
            'DORA',
            'Digital Online Resident Assistant — Conserje virtual de la Ciudad de Doral. Ayuda a residentes y visitantes con trámites, permisos, servicios municipales, eventos y preguntas sobre la ciudad.',
            'government',
            'municipal services',
            'Residentes de Doral, negocios locales, visitantes. Comunidad diversa: 80%% hispana, bilingüe español/inglés.',
            'Eficiente y servicial, directo pero amable. Nunca burocrático. El ciudadano siente que tiene un aliado en el gobierno.',
            'No dar asesoría legal. No prometer plazos de aprobación. Siempre referir a departamentos oficiales para trámites formales. Cumplir con ADA y requisitos de accesibilidad.'
        )
    """)

    # Personality
    op.execute(f"""
        INSERT INTO workspace_personality (workspace_id, brand_traits, brand_tone, brand_instructions, voice_traits, voice_tone, voice_instructions, words_to_avoid)
        VALUES (
            '{DORA_WORKSPACE_ID}',
            '["eficiente", "servicial", "directo", "confiable", "accesible"]',
            'Eficiente y servicial, como un vecino que sabe todo sobre la ciudad',
            '["Eres DORA, la asistente digital de la Ciudad de Doral.", "Proporciona información clara y directa sobre servicios municipales.", "Si no puedes resolver algo, dirige al departamento correcto con teléfono y horario.", "Nunca hagas suposiciones sobre trámites — verifica.", "Prioriza la resolución rápida del problema del ciudadano.", "Trata cada interacción como si el ciudadano estuviera frente a ti en City Hall."]',
            '["claro", "eficiente", "amable", "directo"]',
            'Claro y eficiente, con calidez humana',
            '["Sé concisa pero amable.", "Usa lenguaje simple, evita jerga burocrática.", "Si el tema es complejo, divide la información en pasos claros.", "Siempre confirma que el ciudadano entendió antes de seguir."]',
            '["tramitología", "burocracia", "demora", "no se puede", "imposible"]'
        )
    """)

    # Rules
    op.execute(f"""
        INSERT INTO workspace_rules (workspace_id, rule_id, intent, sentiment, urgency, action_type, action_params, priority) VALUES
        ('{DORA_WORKSPACE_ID}', 'greeting_v1', 'greeting', NULL, NULL, 'greet', '{{"style": "municipal_welcome", "mention": "City of Doral"}}', 10),
        ('{DORA_WORKSPACE_ID}', 'inquiry_v1', 'inquiry', NULL, NULL, 'inform', '{{"source": "knowledge_base", "include_contact": true}}', 8),
        ('{DORA_WORKSPACE_ID}', 'complaint_v1', 'complaint', NULL, NULL, 'handle_complaint', '{{"log_ticket": true, "department": "constituent_services"}}', 10),
        ('{DORA_WORKSPACE_ID}', 'complaint_urgent_v1', 'complaint', NULL, 'high', 'escalate_emergency', '{{"department": "emergency_services", "notify": true}}', 15),
        ('{DORA_WORKSPACE_ID}', 'negative_sentiment_v1', NULL, 'negative', NULL, 'empathize', '{{"follow_up": "offer_resolution"}}', 11),
        ('{DORA_WORKSPACE_ID}', 'very_negative_v1', NULL, 'very_negative', NULL, 'empathize', '{{"follow_up": "escalate_to_supervisor", "log": true}}', 12),
        ('{DORA_WORKSPACE_ID}', 'scheduling_v1', 'scheduling', NULL, NULL, 'schedule', '{{"type": "appointment", "department_lookup": true}}', 10),
        ('{DORA_WORKSPACE_ID}', 'farewell_v1', 'farewell', NULL, NULL, 'farewell', '{{"include_survey_link": true}}', 8),
        ('{DORA_WORKSPACE_ID}', 'follow_up_v1', 'follow_up', NULL, NULL, 'follow_up', '{{"check_ticket_status": true}}', 7),
        ('{DORA_WORKSPACE_ID}', 'escalation_fallback_v1', NULL, NULL, NULL, 'escalate', '{{"after_turns": 3, "message": "Let me connect you with the right department."}}', 3)
    """)

    # Strategies
    op.execute(f"""
        INSERT INTO workspace_strategies (id, workspace_id, strategy_type, name, description, triggers, priority, cooldown_seconds) VALUES
        ('{DORA_STRATEGY_INFO_ID}', '{DORA_WORKSPACE_ID}', 'informational', 'Entrega de Información Municipal', 'Proporciona información clara, directa y accionable sobre servicios de la ciudad.', '[{{"intent": "inquiry"}}, {{"intent": "follow_up"}}]', 5, 0),
        ('{DORA_STRATEGY_TRIAGE_ID}', '{DORA_WORKSPACE_ID}', 'triage', 'Triage y Derivación', 'Identifica el departamento correcto y deriva al ciudadano con toda la información de contacto.', '[{{"intent": "complaint"}}, {{"intent": "scheduling"}}]', 7, 0)
    """)

    # Tactics
    op.execute(f"""
        INSERT INTO workspace_tactics (strategy_id, name, prompt_instruction, position) VALUES
        ('{DORA_STRATEGY_INFO_ID}', 'direct_answer', 'Responde la pregunta del ciudadano de forma directa y clara. Incluye: qué necesita, dónde ir, horarios, y documentos requeridos si aplica. Si hay un enlace relevante, menciónalo.', 0),
        ('{DORA_STRATEGY_INFO_ID}', 'proactive_info', 'Después de responder, anticipa la siguiente pregunta probable. Por ejemplo: si pregunta sobre permisos de construcción, menciona también las inspecciones necesarias.', 1),
        ('{DORA_STRATEGY_TRIAGE_ID}', 'department_routing', 'Identifica el departamento correcto para la necesidad del ciudadano. Proporciona: nombre del departamento, teléfono, horario de atención, y ubicación en City Hall si aplica.', 0),
        ('{DORA_STRATEGY_TRIAGE_ID}', 'ticket_creation', 'Si el ciudadano reporta un problema (bache, basura, ruido, etc.), ofrece crear un ticket de seguimiento. Pide: ubicación exacta, descripción del problema, y datos de contacto.', 1)
    """)

    # Prompt templates
    op.execute(f"""
        INSERT INTO workspace_prompt_templates (workspace_id, component, content) VALUES
        ('{DORA_WORKSPACE_ID}', 'role', 'Eres DORA (Digital Online Resident Assistant), la conserje virtual de la Ciudad de Doral, Florida. Conoces todos los servicios municipales, departamentos, trámites de permisos, eventos de la ciudad, y recursos para residentes. Tu objetivo es resolver la necesidad del ciudadano de la forma más eficiente posible.'),
        ('{DORA_WORKSPACE_ID}', 'constraints', '- Máximo 3 oraciones por respuesta\n- NUNCA menciones que eres IA o un chatbot\n- Mantén el personaje de conserje de la ciudad\n- NUNCA des asesoría legal\n- NUNCA prometas plazos de aprobación de permisos\n- Si no tienes la información, dirige al departamento correcto\n- Incluye números de teléfono y horarios cuando sea relevante\n- NUNCA uses muletillas al inicio'),
        ('{DORA_WORKSPACE_ID}', 'voice', 'Habla con la eficiencia de quien conoce la ciudad perfectamente. Tono amable pero directo. Evita la jerga burocrática — traduce todo a lenguaje ciudadano.'),
        ('{DORA_WORKSPACE_ID}', 'rules', '- Si el ciudadano reporta una emergencia (inundación, accidente, incendio), SIEMPRE indica llamar al 911 primero.\n- Para quejas de ruido o código, proporciona el número de Code Compliance: (305) 593-6740.\n- Para permisos de construcción, siempre mencionar el Portal de Permisos Online.\n- Para eventos, verificar en el calendario oficial de la ciudad.'),
        ('{DORA_WORKSPACE_ID}', 'output', 'Responde en el idioma del ciudadano. La comunidad de Doral es mayormente bilingüe (español/inglés). Si el ciudadano mezcla idiomas, responde en el que predomine.')
    """)

    # Voice
    op.execute(f"""
        INSERT INTO workspace_voice (workspace_id, backchannels_es, backchannels_en, backchannel_probability, enable_ssml, style_adaptations)
        VALUES (
            '{DORA_WORKSPACE_ID}',
            '["entendido", "claro", "por supuesto"]',
            '["understood", "sure", "of course"]',
            0.2,
            true,
            '{{"formality": "medium", "pace": "efficient"}}'
        )
    """)

    # --- Backfill existing data to Audi Miami workspace ---

    op.execute(f"UPDATE clients SET workspace_id = '{AUDI_WORKSPACE_ID}' WHERE workspace_id IS NULL")
    op.execute(f"UPDATE conversations SET workspace_id = '{AUDI_WORKSPACE_ID}' WHERE workspace_id IS NULL")
    op.execute(f"UPDATE knowledge_documents SET workspace_id = '{AUDI_WORKSPACE_ID}' WHERE workspace_id IS NULL")
    op.execute(f"UPDATE events SET workspace_id = '{AUDI_WORKSPACE_ID}' WHERE workspace_id IS NULL")

    # --- Change unique constraint on clients ---

    op.drop_constraint("clients_external_id_key", "clients", type_="unique")
    op.create_unique_constraint("uq_clients_workspace_external", "clients", ["workspace_id", "external_id"])


def downgrade() -> None:
    # Restore clients unique constraint
    op.drop_constraint("uq_clients_workspace_external", "clients", type_="unique")
    op.create_unique_constraint("clients_external_id_key", "clients", ["external_id"])

    # Remove workspace_id columns
    op.drop_index("ix_events_workspace_id", "events")
    op.drop_column("events", "workspace_id")

    op.drop_index("ix_knowledge_documents_workspace_id", "knowledge_documents")
    op.drop_column("knowledge_documents", "workspace_id")

    op.drop_index("ix_conversations_workspace_id", "conversations")
    op.drop_column("conversations", "workspace_id")

    op.drop_index("ix_clients_workspace_id", "clients")
    op.drop_column("clients", "workspace_id")

    # Drop workspace tables (reverse order)
    op.drop_table("workspace_voice")
    op.drop_table("workspace_prompt_templates")
    op.drop_table("workspace_tactics")
    op.drop_table("workspace_strategies")
    op.drop_table("workspace_rules")
    op.drop_table("workspace_personality")
    op.drop_table("workspace_identity")
    op.drop_table("workspaces")
