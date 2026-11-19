from learning_engine.core.enums import ConversationStage
from learning_engine.core.models.plan import NextAction, SalesPlan

STAGE_GOALS: dict[ConversationStage, SalesPlan] = {
    ConversationStage.OPENING: SalesPlan(
        goal="Establish rapport and identify needs",
        next_action=NextAction(
            description="Greet warmly and ask what they're looking for",
            prompt_instruction="Greet the client warmly. Ask what type of vehicle they're interested in.",
        ),
        fallback=NextAction(
            description="Ask open question about their needs",
            prompt_instruction="Ask an open-ended question about their transportation needs.",
        ),
        exit_condition="Client expresses specific need or interest",
    ),
    ConversationStage.DISCOVERY: SalesPlan(
        goal="Understand client needs deeply",
        next_action=NextAction(
            description="Ask qualifying questions",
            prompt_instruction="Ask about budget, usage, family size, preferences to qualify the lead.",
        ),
        fallback=NextAction(
            description="Share relevant product info",
            prompt_instruction="Share interesting facts about popular models to keep engagement.",
        ),
        exit_condition="Client has expressed clear preferences",
    ),
    ConversationStage.PRESENTATION: SalesPlan(
        goal="Present best matching options",
        next_action=NextAction(
            description="Present tailored recommendations",
            prompt_instruction="Present 1-2 vehicle options that match the client's expressed needs.",
        ),
        fallback=NextAction(
            description="Highlight key differentiators",
            prompt_instruction="Highlight what makes these options stand out from competitors.",
        ),
        exit_condition="Client shows interest in specific model",
    ),
    ConversationStage.OBJECTION_HANDLING: SalesPlan(
        goal="Address concerns and maintain interest",
        next_action=NextAction(
            description="Address the specific objection",
            prompt_instruction="Acknowledge the concern, then address it with facts and value.",
        ),
        fallback=NextAction(
            description="Offer alternative or financing",
            prompt_instruction="Offer an alternative option or financing solution.",
        ),
        exit_condition="Client's concern is resolved",
    ),
    ConversationStage.CLOSING: SalesPlan(
        goal="Schedule test drive or appointment",
        next_action=NextAction(
            description="Propose next step",
            prompt_instruction="Propose scheduling a test drive or visit to the dealership.",
        ),
        fallback=NextAction(
            description="Create urgency",
            prompt_instruction="Mention current promotions or limited availability.",
        ),
        exit_condition="Client agrees to appointment",
    ),
}


def get_plan_for_stage(stage: ConversationStage) -> SalesPlan:
    return STAGE_GOALS.get(stage, STAGE_GOALS[ConversationStage.OPENING])
