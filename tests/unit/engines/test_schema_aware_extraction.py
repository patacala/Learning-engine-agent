"""Schema-aware extraction: the facts instruction lists the agent's configured
qualification fields (so each industry captures its own), falling back to a
generic example when there's no schema."""

from learning_engine.core.models.qualification_schema import QualificationField, QualificationSchema
from learning_engine.engines.analyzers.contact_signals import build_facts_instruction


def test_no_schema_uses_default_example():
    instr = build_facts_instruction(None)
    assert "product_interest" in instr
    assert "ej:" in instr  # the generic example form


def test_schema_lists_exact_keys():
    schema = QualificationSchema(fields=[
        QualificationField(key="zona", label="Zona de interés", type="text"),
        QualificationField(key="habitaciones", label="Habitaciones", type="number"),
        QualificationField(key="modo", label="Operación", type="enum", options=["compra", "renta"]),
        QualificationField(key="off", label="Disabled", type="text", enabled=False),
    ])
    instr = build_facts_instruction(schema)
    assert "zona (Zona de interés; text)" in instr
    assert "habitaciones (Habitaciones; number)" in instr
    assert "modo (Operación; uno de: compra, renta)" in instr
    assert "off" not in instr  # disabled fields excluded


def test_empty_schema_falls_back():
    assert "ej:" in build_facts_instruction(QualificationSchema(fields=[]))


def test_field_hint_is_injected():
    schema = QualificationSchema(fields=[
        QualificationField(key="product_interest", label="Product of interest", type="text",
                           hint="The car model, never the operation."),
    ])
    instr = build_facts_instruction(schema)
    assert "product_interest (Product of interest; text) — The car model, never the operation." in instr
