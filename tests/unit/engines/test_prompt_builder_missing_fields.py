"""_format_missing_fields: tone by priority — the name is asked directly from the
greeting, other early fields gradually, the rest later; an org with no fields
gets no capture block at all."""

from learning_engine.core.models.qualification_schema import QualificationField, QualificationSchema
from learning_engine.engines.response.prompt_builder import PromptBuilder


def _schema(*fields):
    return QualificationSchema(fields=list(fields))


def test_empty_schema_produces_no_block():
    assert PromptBuilder()._format_missing_fields({}) == ""
    assert PromptBuilder()._format_missing_fields({"qualification_schema": _schema()}) == ""


def test_early_name_produces_direct_greeting_instruction():
    schema = _schema(
        QualificationField(key="full_name", label="Full name", ask_priority="early",
                           crm_field="full_name"),
    )
    out = PromptBuilder()._format_missing_fields({"qualification_schema": schema})
    assert "Right after greeting" in out
    assert "name first" in out


def test_early_non_name_is_gradual_not_greeting():
    schema = _schema(
        QualificationField(key="email", label="Email", type="email", ask_priority="early",
                           crm_field="email"),
    )
    out = PromptBuilder()._format_missing_fields({"qualification_schema": schema})
    assert "Right after greeting" not in out
    assert "gradually" in out
    assert "Email" in out


def test_rest_fields_come_up_later():
    schema = _schema(
        QualificationField(key="budget_amount", label="Budget", type="number"),
    )
    out = PromptBuilder()._format_missing_fields({"qualification_schema": schema})
    assert "naturally later" in out
    assert "Budget" in out


def test_required_for_scheduling_is_flagged():
    schema = _schema(
        QualificationField(key="email", label="Email", type="email", ask_priority="early",
                           required_for_scheduling=True, crm_field="email"),
    )
    out = PromptBuilder()._format_missing_fields({"qualification_schema": schema})
    assert "proposing a time" in out
    assert "Email" in out


def test_name_variants_detected():
    b = PromptBuilder()
    assert b._is_name_field(QualificationField(key="nombre", label="Nombre"))
    assert b._is_name_field(QualificationField(key="x", label="Name", crm_field="full_name"))
    assert not b._is_name_field(QualificationField(key="email", label="Email", crm_field="email"))
