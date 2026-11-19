"""Multi-turn eval suite — runs YAML scenarios through the REAL production
pipeline (same PipelineRunner as `POST /conversation/message` and voice; see
`scripts/eval_conversation.py` for the single-turn version this builds on)
and grades each turn two ways:

1. Deterministic checks from the scenario file (`expect.intent`,
   `expect.strategy_type`, `expect.must_mention`, `expect.must_not_mention`).
2. An LLM-as-judge holistic score (relevance, tactic adherence, no invented
   facts, correct language) — catches quality regressions the deterministic
   checks can't (e.g. a technically-correct-intent reply that's rude, or
   invents a discount that was never offered).

A scenario "passes" only if every deterministic check passes AND the judge
score clears --threshold. Exit code is nonzero if any scenario fails, so this
is usable as a CI/pre-publish gate (Fase 3.2/`make eval`), not just a report.

Usage:
    python -m scripts.eval_suite --agent <agent_version_id>
    python -m scripts.eval_suite --agent <id> --scenarios tests/evals/scenarios --json
    python -m scripts.eval_suite --agent <id> --threshold 0.75
"""

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import yaml

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

sys.path.insert(0, str(Path(__file__).parent.parent))

from learning_engine.api.v1.dependencies import get_redis_cache  # noqa: E402
from learning_engine.di.container import create_llm_provider  # noqa: E402
from learning_engine.infrastructure.database.connection import async_session_factory  # noqa: E402
from learning_engine.infrastructure.database.models import ConversationModel  # noqa: E402
from learning_engine.infrastructure.database.repositories.client import SQLClientRepository  # noqa: E402
from learning_engine.infrastructure.database.repositories.conversation import (  # noqa: E402
    SQLConversationRepository,
)
from learning_engine.infrastructure.llm.provider import LLMMessage  # noqa: E402
from learning_engine.services.pipeline_runner import PipelineRunner  # noqa: E402

# Reuse eval_conversation's AgentContext loader — same convention (no invented
# organization_id), one definition instead of two drifting copies.
from scripts.eval_conversation import _load_agent_context  # noqa: E402

# SQLAlchemy's dev-mode echo (connection.py: echo=app_env=="development") sets
# this logger's level to INFO and attaches its own stdout handler the moment the
# engine module above gets imported — overriding any level set earlier. Silence
# it here, after that import, so --json output piped to a file stays clean.
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

DEFAULT_SCENARIOS_DIR = Path(__file__).parent.parent / "tests" / "evals" / "scenarios"

JUDGE_RUBRIC = """Sos un evaluador estricto de conversaciones de ventas. Te doy el mensaje
del cliente, el CONTEXTO REAL que el agente tenía disponible (documentos recuperados de su
base de conocimiento — puede estar vacío) y la respuesta del agente. Calificá la respuesta en
4 criterios, cada uno 0.0-1.0:

- relevance: ¿responde directamente lo que el cliente preguntó/planteó?
- tactic_adherence: ¿sigue la táctica de venta indicada (si la hay)?
- no_fabrication: comparación estricta contra el CONTEXTO REAL dado, no contra lo que te
  parezca plausible. 1.0 si todo dato concreto (precio, descuento, stock, garantía, plazo)
  que menciona está respaldado por el contexto O es una afirmación genérica sin números
  concretos (ej. "podemos ver opciones de financiamiento" sin inventar una tasa). 0.0 si
  menciona un dato concreto y específico que NO aparece en el contexto. Si el contexto está
  vacío y la respuesta no menciona ningún dato concreto, no hay fabricación posible: 1.0.
- language_correct: 1.0 si responde en el idioma esperado y con tono profesional; 0.0 si no.

Devolvé SOLO JSON: {"relevance": 0-1, "tactic_adherence": 0-1, "no_fabrication": 0-1,
"language_correct": 0-1, "rationale": "una frase breve explicando el puntaje más bajo"}"""


@dataclass
class TurnResult:
    client_message: str
    response: str
    analysis: dict = field(default_factory=dict)
    knowledge: dict = field(default_factory=dict)
    checks: dict = field(default_factory=dict)
    judge: dict = field(default_factory=dict)
    judge_score: float = 0.0
    passed: bool = False


@dataclass
class ScenarioResult:
    name: str
    turns: list = field(default_factory=list)
    passed: bool = True
    avg_judge_score: float = 0.0


def _load_scenarios(scenarios_dir: Path) -> list[dict]:
    files = sorted(scenarios_dir.glob("*.yaml")) + sorted(scenarios_dir.glob("*.yml"))
    if not files:
        print(f"No scenario files found in {scenarios_dir}", file=sys.stderr)
        sys.exit(1)
    scenarios = []
    for f in files:
        data = yaml.safe_load(f.read_text())
        data["_file"] = f.name
        scenarios.append(data)
    return scenarios


def _run_checks(turn_cfg: dict, analysis: dict, strategy: dict, response: str) -> dict:
    expect = turn_cfg.get("expect", {}) or {}
    checks = {}

    if "intent" in expect:
        checks["intent"] = analysis.get("intent") == expect["intent"]
    if "strategy_type" in expect:
        checks["strategy_type"] = (strategy or {}).get("strategy_type") == expect["strategy_type"]
    if expect.get("must_mention"):
        low = response.lower()
        checks["must_mention"] = all(m.lower() in low for m in expect["must_mention"])
    if expect.get("must_not_mention"):
        low = response.lower()
        checks["must_not_mention"] = all(m.lower() not in low for m in expect["must_not_mention"])

    return checks


def _format_knowledge(knowledge: dict) -> str:
    docs = (knowledge or {}).get("documents") or []
    if not docs:
        return "CONTEXTO REAL: (vacío — el agente no recuperó ningún documento para este turno)"
    formatted = "\n".join(f"- {d.get('title', '(sin título)')}: {d.get('content', '')[:500]}" for d in docs)
    return f"CONTEXTO REAL (lo único que el agente tenía disponible):\n{formatted}"


async def _judge(llm, client_message: str, response: str, tactic: str | None, knowledge: dict) -> dict:
    tactic_line = f"Táctica indicada al agente: {tactic}" if tactic else "Sin táctica específica indicada."
    messages = [
        LLMMessage(role="system", content=JUDGE_RUBRIC),
        LLMMessage(
            role="user",
            content=f"{tactic_line}\n\n{_format_knowledge(knowledge)}\n\n"
                    f"Cliente: {client_message}\n\nAgente: {response}",
        ),
    ]
    try:
        result = await llm.complete_json(messages, temperature=0.0)
    except Exception as e:  # noqa: BLE001 — judge failure must not crash the whole suite
        return {"relevance": 0, "tactic_adherence": 0, "no_fabrication": 0,
                "language_correct": 0, "rationale": f"judge call failed: {e}"}
    return result


def _judge_score(judge: dict) -> float:
    keys = ["relevance", "tactic_adherence", "no_fabrication", "language_correct"]
    vals = [float(judge.get(k, 0) or 0) for k in keys]
    return round(sum(vals) / len(vals), 3) if vals else 0.0


async def run_scenario(scenario: dict, agent_version_id: UUID, cache, llm, threshold: float) -> ScenarioResult:
    name = scenario.get("name", scenario["_file"])
    result = ScenarioResult(name=name)

    async with async_session_factory() as session:
        agent_context = await _load_agent_context(session, agent_version_id)
        client_repo = SQLClientRepository(session)
        conv_repo = SQLConversationRepository(session)
        client = await client_repo.get_or_create(
            f"eval-suite-{uuid4()}", organization_id=agent_context.organization_id
        )
        conversation = ConversationModel(
            id=uuid4(),
            client_id=client.id,
            organization_id=agent_context.organization_id,
            agent_version_id=agent_version_id,
        )
        await conv_repo.save(conversation)
        await session.commit()
        client_id, conversation_id = client.id, conversation.id

    runner = PipelineRunner(async_session_factory, cache=cache)

    for turn_cfg in scenario.get("turns", []):
        client_message = turn_cfg["client"]
        pr = await runner.run(
            message=client_message,
            client_id=client_id,
            conversation_id=conversation_id,
            agent_context=agent_context,
        )

        checks = _run_checks(turn_cfg, pr.analysis_summary, pr.strategy_summary, pr.response)
        tactic = (pr.strategy_summary or {}).get("tactic_instruction")
        judge = await _judge(llm, client_message, pr.response, tactic, pr.knowledge_summary)
        score = _judge_score(judge)

        turn_passed = all(checks.values()) and score >= threshold
        result.turns.append(TurnResult(
            client_message=client_message,
            response=pr.response,
            analysis={
                "intent": pr.analysis_summary.get("intent"),
                "strategy_type": (pr.strategy_summary or {}).get("strategy_type"),
            },
            knowledge=pr.knowledge_summary,
            checks=checks,
            judge=judge,
            judge_score=score,
            passed=turn_passed,
        ))
        if not turn_passed:
            result.passed = False

    result.avg_judge_score = (
        round(sum(t.judge_score for t in result.turns) / len(result.turns), 3)
        if result.turns else 0.0
    )
    return result


def _print_human(results: list[ScenarioResult]) -> None:
    for r in results:
        status = "✅ PASS" if r.passed else "❌ FAIL"
        print(f"\n{'═' * 70}\n{status}  {r.name}  (avg judge score: {r.avg_judge_score})\n{'═' * 70}")
        for i, t in enumerate(r.turns, 1):
            mark = "✅" if t.passed else "❌"
            n_docs = len((t.knowledge or {}).get("documents") or [])
            print(f"\n  Turn {i} {mark} judge={t.judge_score}  intent={t.analysis.get('intent')} "
                  f"strategy={t.analysis.get('strategy_type')}  knowledge_docs={n_docs}")
            print(f"    Cliente: {t.client_message}")
            print(f"    Agente:  {t.response[:200]}")
            failed_checks = [k for k, v in t.checks.items() if not v]
            if failed_checks:
                print(f"    checks fallados: {failed_checks}")
            if t.judge.get("rationale"):
                print(f"    judge: {t.judge['rationale']}")

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    print(f"\n{'─' * 70}\n{passed}/{total} escenarios pasaron\n{'─' * 70}")


def _to_json(results: list[ScenarioResult]) -> dict:
    return {
        "scenarios": [
            {
                "name": r.name,
                "passed": r.passed,
                "avg_judge_score": r.avg_judge_score,
                "turns": [
                    {
                        "client_message": t.client_message,
                        "response": t.response,
                        "analysis": t.analysis,
                        "knowledge": t.knowledge,
                        "checks": t.checks,
                        "judge": t.judge,
                        "judge_score": t.judge_score,
                        "passed": t.passed,
                    }
                    for t in r.turns
                ],
            }
            for r in results
        ],
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
        },
    }


async def run(args: argparse.Namespace) -> int:
    agent_version_id = UUID(args.agent)
    cache = get_redis_cache()
    llm = create_llm_provider()
    scenarios = _load_scenarios(Path(args.scenarios))

    results = []
    for scenario in scenarios:
        results.append(await run_scenario(scenario, agent_version_id, cache, llm, args.threshold))

    if args.output:
        # SQLAlchemy's dev-mode echo (connection.py) writes its own stdout
        # handler that basicConfig/setLevel can't reliably suppress once the
        # engine has been used — write straight to a file so machine-readable
        # output (e.g. a committed baseline) is never corrupted by log noise.
        Path(args.output).write_text(json.dumps(_to_json(results), indent=2, ensure_ascii=False))
        print(f"Wrote results to {args.output}", file=sys.stderr)
    elif args.json:
        print(json.dumps(_to_json(results), indent=2, ensure_ascii=False))
    else:
        _print_human(results)

    return 0 if all(r.passed for r in results) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent", required=True, help="agent_version_id (UUID) to eval against")
    parser.add_argument(
        "--scenarios", default=str(DEFAULT_SCENARIOS_DIR),
        help=f"directory of *.yaml scenario files (default: {DEFAULT_SCENARIOS_DIR})",
    )
    parser.add_argument("--threshold", type=float, default=0.7, help="min avg judge score to pass a turn")
    parser.add_argument("--json", action="store_true", help="machine-readable output on stdout")
    parser.add_argument("--output", help="write machine-readable JSON straight to this file path")
    args = parser.parse_args()
    exit_code = asyncio.run(run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
