"""Main LangGraph StateGraph — Cognitive Pipeline."""

from langgraph.graph import END, StateGraph

from prosales.engines.analyzers.contact_signals import ContactSignalDetector
from prosales.engines.analyzers.intent import IntentDetector
from prosales.engines.analyzers.language import LanguageDetector
from prosales.engines.analyzers.orchestrator import AnalyzerOrchestrator
from prosales.engines.analyzers.sentiment import SentimentDetector
from prosales.engines.analyzers.stage import ConversationStageDetector
from prosales.engines.analyzers.urgency import UrgencyDetector
from prosales.engines.context_builder.engine import ContextBuilderEngine
from prosales.engines.conversation_manager.engine import ConversationManager
from prosales.engines.decision.engine import DecisionEngine
from prosales.engines.identity.engine import IdentityEngine
from prosales.engines.knowledge.engine import KnowledgeEngine
from prosales.engines.learning.engine import LearningEngine
from prosales.engines.learning.event_store import EventStore
from prosales.engines.memory.engine import MemoryEngine
from prosales.engines.personality.engine import PersonalityEngine
from prosales.engines.planner.engine import SalesPlannerEngine
from prosales.engines.response.planner import ResponsePlanner
from prosales.engines.response.post_processor import PostProcessor
from prosales.engines.response.prompt_builder import PromptBuilder
from prosales.engines.strategy.engine import StrategyEngine
from prosales.engines.voice.engine import VoiceLayerEngine
from prosales.infrastructure.llm.provider import LLMProvider
from prosales.pipeline.edges import route_by_path
from prosales.pipeline.nodes import (
    create_analyze_node,
    create_context_build_node,
    create_decision_node,
    create_identity_node,
    create_knowledge_node,
    create_learn_node,
    create_llm_call_node,
    create_personality_node,
    create_plan_node,
    create_post_processor_node,
    create_prompt_builder_node,
    create_remember_node,
    create_response_planner_node,
    create_route_node,
    create_store_node,
    create_strategy_node,
    create_voice_node,
)
from prosales.pipeline.state import CognitivePipelineState


def build_cognitive_graph(
    primary_llm: LLMProvider,
    analyzer_llm: LLMProvider,
    session_factory=None,
    analyzer_model: str = "gpt-4o-mini",
    event_store: EventStore | None = None,
    # Agent providers
    personality_provider=None,
    rule_provider=None,
    strategy_provider=None,
    prompt_provider=None,
    voice_provider=None,
    identity_provider=None,
    style_provider=None,
    pattern_retriever=None,
    # Episodic memory (production loads past episodes; test mode skips it)
    use_episodic: bool = True,
    # Test playground overrides
    knowledge_engine=None,
    memory_engine=None,
    persist_messages: bool = True,
) -> StateGraph:
    """Build the full cognitive pipeline as a LangGraph StateGraph.

    DB-touching engines (memory, knowledge, providers, store) open SHORT sessions
    via ``session_factory`` so no connection is held across the LLM-heavy nodes.
    Production passes ``async_session_factory``; the Test Playground passes a
    ``live_session_factory`` that reuses its request session (to see uncommitted
    temp docs) and injects ``memory_engine``/``knowledge_engine`` +
    ``persist_messages=False`` so ``store`` writes nothing.
    """

    # Instantiate engines (allow injected overrides for isolated test mode)
    if memory_engine is None:
        memory_engine = MemoryEngine(session_factory, use_episodic=use_episodic)
    context_engine = ContextBuilderEngine()
    analyzer_orchestrator = AnalyzerOrchestrator(
        intent=IntentDetector(analyzer_llm, analyzer_model),
        sentiment=SentimentDetector(analyzer_llm, analyzer_model),
        language=LanguageDetector(),
        urgency=UrgencyDetector(),
        stage=ConversationStageDetector(analyzer_llm, analyzer_model),
        contact_signals=ContactSignalDetector(analyzer_llm, analyzer_model),
    )
    conversation_manager = ConversationManager()
    identity_engine = IdentityEngine(identity_provider=identity_provider)
    if knowledge_engine is None:
        knowledge_engine = KnowledgeEngine(session_factory)
    decision_engine = DecisionEngine(rule_provider=rule_provider)
    strategy_engine = StrategyEngine(strategy_provider=strategy_provider)
    planner_engine = SalesPlannerEngine()
    personality_engine = PersonalityEngine(personality_provider=personality_provider)
    response_planner = ResponsePlanner()
    prompt_builder = PromptBuilder(
        prompt_provider=prompt_provider,
        style_provider=style_provider,
        pattern_retriever=pattern_retriever,
    )
    post_processor = PostProcessor()
    voice_engine = VoiceLayerEngine(voice_provider=voice_provider)
    learning_engine = LearningEngine(event_store=event_store)

    # Build graph
    graph = StateGraph(CognitivePipelineState)

    # Add nodes (all with event_store for timing)
    graph.add_node("remember", create_remember_node(memory_engine, event_store))
    graph.add_node("context_build", create_context_build_node(context_engine, event_store))
    graph.add_node("analyze", create_analyze_node(analyzer_orchestrator, event_store))
    graph.add_node("route", create_route_node(conversation_manager, event_store))
    graph.add_node("identify", create_identity_node(identity_engine, event_store))

    # Full path nodes
    graph.add_node("retrieve", create_knowledge_node(knowledge_engine, event_store))
    graph.add_node("decide", create_decision_node(decision_engine, event_store))
    graph.add_node("strategize", create_strategy_node(strategy_engine, event_store))
    graph.add_node("plan", create_plan_node(planner_engine, event_store))

    # Common nodes (both paths)
    graph.add_node("personify", create_personality_node(personality_engine, event_store))
    graph.add_node("response_plan", create_response_planner_node(response_planner, event_store))
    graph.add_node("build_prompt", create_prompt_builder_node(prompt_builder, event_store))
    graph.add_node("llm_call", create_llm_call_node(primary_llm, event_store=event_store))
    graph.add_node("post_process", create_post_processor_node(post_processor, event_store))
    graph.add_node("voice_layer", create_voice_node(voice_engine, event_store))
    graph.add_node("store", create_store_node(session_factory, event_store, persist=persist_messages))
    graph.add_node("learn", create_learn_node(learning_engine, event_store))

    # Edges
    graph.set_entry_point("remember")
    graph.add_edge("remember", "context_build")
    graph.add_edge("context_build", "analyze")
    graph.add_edge("analyze", "route")
    graph.add_edge("route", "identify")

    # Conditional routing (after identity)
    graph.add_conditional_edges(
        "identify",
        route_by_path,
        {
            "fast_path": "personify",
            "full_path": "retrieve",
        },
    )

    # Full path chain
    graph.add_edge("retrieve", "decide")
    graph.add_edge("decide", "strategize")
    graph.add_edge("strategize", "plan")
    graph.add_edge("plan", "personify")

    # Common chain (after personify)
    graph.add_edge("personify", "response_plan")
    graph.add_edge("response_plan", "build_prompt")
    graph.add_edge("build_prompt", "llm_call")
    graph.add_edge("llm_call", "post_process")
    graph.add_edge("post_process", "voice_layer")
    graph.add_edge("voice_layer", "store")
    graph.add_edge("store", "learn")
    graph.add_edge("learn", END)

    return graph
