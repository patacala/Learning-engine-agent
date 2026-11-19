from learning_engine.core.enums import StrategyType
from learning_engine.core.models.strategy import Strategy, Tactic

STRATEGY_CATALOG: dict[StrategyType, Strategy] = {
    # --- Original 8 (enriched with multi-tactic) ---
    StrategyType.CONSULTIVE: Strategy(
        type=StrategyType.CONSULTIVE,
        name="Consultive Selling",
        description="Focus on understanding needs and providing tailored solutions",
        tactics=[
            Tactic(
                name="needs_discovery",
                description="Ask open questions to understand needs",
                prompt_instruction="Ask open-ended questions to understand the client's needs. Listen actively.",
            ),
            Tactic(
                name="solution_mapping",
                description="Map needs to product features",
                prompt_instruction="Connect the client's expressed needs to specific product features and benefits.",
            ),
        ],
    ),
    StrategyType.SPIN_SELLING: Strategy(
        type=StrategyType.SPIN_SELLING,
        name="SPIN Selling",
        description="Situation, Problem, Implication, Need-payoff questioning",
        tactics=[
            Tactic(
                name="situation_question",
                description="Understand current situation",
                prompt_instruction="Ask about the client's current situation: what they have, how they use it, what their setup looks like.",
            ),
            Tactic(
                name="problem_question",
                description="Uncover problems",
                prompt_instruction="Ask about difficulties, frustrations, or dissatisfactions with their current situation.",
            ),
            Tactic(
                name="implication_question",
                description="Amplify consequences",
                prompt_instruction="Ask about the consequences and impact of the problems they described. Help them see the cost of inaction.",
            ),
            Tactic(
                name="need_payoff_question",
                description="Envision the solution",
                prompt_instruction="Ask how solving these problems would benefit them. Let them describe the value of a solution.",
            ),
        ],
    ),
    StrategyType.CHALLENGER: Strategy(
        type=StrategyType.CHALLENGER,
        name="Challenger Sale",
        description="Teach, tailor, take control — challenge assumptions with insights",
        tactics=[
            Tactic(
                name="teach_insight",
                description="Share a provocative insight",
                prompt_instruction="Share a surprising insight or data point that challenges the client's current thinking.",
            ),
            Tactic(
                name="tailor_message",
                description="Customize to their context",
                prompt_instruction="Connect the insight directly to the client's specific industry, role, or situation.",
            ),
            Tactic(
                name="take_control",
                description="Guide toward decision",
                prompt_instruction="Confidently guide the conversation toward a clear recommendation. Be assertive but respectful.",
            ),
        ],
    ),
    StrategyType.URGENCY: Strategy(
        type=StrategyType.URGENCY,
        name="Urgency",
        description="Create urgency through time-limited offers or scarcity",
        tactics=[
            Tactic(
                name="time_pressure",
                description="Highlight time-sensitive opportunity",
                prompt_instruction="Mention current promotions, limited availability, or time-sensitive benefits.",
            ),
            Tactic(
                name="cost_of_delay",
                description="Show what waiting costs",
                prompt_instruction="Explain what the client loses by waiting — rising prices, missed benefits, continued problems.",
            ),
        ],
    ),
    StrategyType.SOCIAL_PROOF: Strategy(
        type=StrategyType.SOCIAL_PROOF,
        name="Social Proof",
        description="Use testimonials and popular choices",
        tactics=[
            Tactic(
                name="popularity",
                description="Reference what others choose",
                prompt_instruction="Reference how other families/clients in similar situations chose this option.",
            ),
            Tactic(
                name="success_story",
                description="Share a specific success case",
                prompt_instruction="Share a specific example of a similar client who achieved great results with this solution.",
            ),
        ],
    ),
    StrategyType.SCARCITY: Strategy(
        type=StrategyType.SCARCITY,
        name="Scarcity",
        description="Emphasize limited availability to drive action",
        tactics=[
            Tactic(
                name="limited_stock",
                description="Highlight limited availability",
                prompt_instruction="Mention that availability is limited — few units, spots, or time left at this offer.",
            ),
            Tactic(
                name="exclusive_access",
                description="Frame as exclusive opportunity",
                prompt_instruction="Position the offer as exclusive or available only to select clients.",
            ),
        ],
    ),
    StrategyType.VALUE_FIRST: Strategy(
        type=StrategyType.VALUE_FIRST,
        name="Value First",
        description="Lead with value proposition before discussing price",
        tactics=[
            Tactic(
                name="value_stack",
                description="Build value before price",
                prompt_instruction="Emphasize the total value, benefits, and ROI before any price discussion.",
            ),
            Tactic(
                name="roi_calculation",
                description="Quantify the return",
                prompt_instruction="Help the client calculate the return on investment. Use concrete numbers and timeframes.",
            ),
        ],
    ),
    StrategyType.PRICE_DEFENSE: Strategy(
        type=StrategyType.PRICE_DEFENSE,
        name="Price Defense",
        description="Handle price objections effectively",
        tactics=[
            Tactic(
                name="reframe_value",
                description="Reframe price as investment",
                prompt_instruction="Reframe the price as a long-term investment. Break down cost per day/month.",
            ),
            Tactic(
                name="comparison_framing",
                description="Compare to alternatives",
                prompt_instruction="Compare the cost to alternatives: competitor prices, cost of not solving the problem, or everyday expenses.",
            ),
        ],
    ),
    # --- Discovery ---
    StrategyType.NEEDS_DIAGNOSIS: Strategy(
        type=StrategyType.NEEDS_DIAGNOSIS,
        name="Needs Diagnosis",
        description="Systematic discovery of client needs through structured questioning",
        tactics=[
            Tactic(
                name="current_state",
                description="Understand where they are now",
                prompt_instruction="Ask about the client's current situation — what tools, processes, or solutions they use today.",
            ),
            Tactic(
                name="desired_state",
                description="Understand where they want to be",
                prompt_instruction="Ask what their ideal outcome looks like. What would success mean for them?",
            ),
            Tactic(
                name="gap_identification",
                description="Identify the gap",
                prompt_instruction="Help the client articulate the gap between where they are and where they want to be.",
            ),
        ],
    ),
    StrategyType.PAIN_AMPLIFICATION: Strategy(
        type=StrategyType.PAIN_AMPLIFICATION,
        name="Pain Amplification",
        description="Deepen awareness of the cost of the current problem",
        tactics=[
            Tactic(
                name="surface_pain",
                description="Bring the pain to light",
                prompt_instruction="Ask about frustrations, wasted time, missed opportunities, or recurring problems they face.",
            ),
            Tactic(
                name="quantify_impact",
                description="Put numbers to the problem",
                prompt_instruction="Help the client quantify the cost of their problem — in time, money, stress, or missed revenue.",
            ),
        ],
    ),
    StrategyType.FUTURE_PACING: Strategy(
        type=StrategyType.FUTURE_PACING,
        name="Future Pacing",
        description="Help the client visualize life after the purchase",
        tactics=[
            Tactic(
                name="paint_future",
                description="Describe the improved future",
                prompt_instruction="Help the client imagine their life or business after adopting the solution. Use vivid, specific language.",
            ),
            Tactic(
                name="emotional_anchor",
                description="Connect to emotions",
                prompt_instruction="Connect the future vision to emotions they care about: relief, confidence, pride, security.",
            ),
        ],
    ),
    # --- Closing ---
    StrategyType.ASSUMPTIVE_CLOSE: Strategy(
        type=StrategyType.ASSUMPTIVE_CLOSE,
        name="Assumptive Close",
        description="Proceed as if the decision is already made",
        tactics=[
            Tactic(
                name="proceed_assumption",
                description="Move forward naturally",
                prompt_instruction="Proceed as if the client has already decided. Ask about next steps, delivery preferences, or implementation details.",
            ),
            Tactic(
                name="handle_hesitation",
                description="Address any pause gently",
                prompt_instruction="If the client hesitates, gently address their concern without backing away from the assumed decision.",
            ),
        ],
    ),
    StrategyType.ALTERNATIVE_CLOSE: Strategy(
        type=StrategyType.ALTERNATIVE_CLOSE,
        name="Alternative Close",
        description="Offer two positive options instead of yes/no",
        tactics=[
            Tactic(
                name="present_options",
                description="Offer two choices",
                prompt_instruction="Present two specific options (both favorable). Frame as 'Would you prefer A or B?' instead of 'Would you like to buy?'",
            ),
            Tactic(
                name="guide_choice",
                description="Help them decide between options",
                prompt_instruction="Help the client compare the two options based on their stated needs. Gently recommend the best fit.",
            ),
        ],
    ),
    StrategyType.TRIAL_CLOSE: Strategy(
        type=StrategyType.TRIAL_CLOSE,
        name="Trial Close",
        description="Test readiness with low-commitment questions",
        tactics=[
            Tactic(
                name="temperature_check",
                description="Gauge interest level",
                prompt_instruction="Ask a soft question to gauge readiness: 'How does this sound so far?' or 'Does this align with what you're looking for?'",
            ),
            Tactic(
                name="advance_or_address",
                description="Move forward or handle concern",
                prompt_instruction="If positive, move toward closing. If hesitant, ask what's holding them back and address it.",
            ),
        ],
    ),
    StrategyType.SUMMARY_CLOSE: Strategy(
        type=StrategyType.SUMMARY_CLOSE,
        name="Summary Close",
        description="Summarize all benefits before asking for commitment",
        tactics=[
            Tactic(
                name="recap_benefits",
                description="List all benefits discussed",
                prompt_instruction="Summarize all the key benefits, features, and value points discussed during the conversation.",
            ),
            Tactic(
                name="ask_commitment",
                description="Ask for the decision",
                prompt_instruction="After the summary, ask for the commitment: 'Shall we move forward?' or 'Would you like to get started?'",
            ),
        ],
    ),
    StrategyType.PUPPY_DOG_CLOSE: Strategy(
        type=StrategyType.PUPPY_DOG_CLOSE,
        name="Puppy Dog Close",
        description="Let the client try before committing",
        tactics=[
            Tactic(
                name="offer_trial",
                description="Propose a trial or demo",
                prompt_instruction="Offer a free trial, demo, or sample. Emphasize there's no obligation and they can decide after experiencing it.",
            ),
            Tactic(
                name="reduce_risk",
                description="Remove barriers to trying",
                prompt_instruction="Address any concerns about the trial: no credit card needed, easy to cancel, full support included.",
            ),
        ],
    ),
    # --- Objection Handling ---
    StrategyType.FEEL_FELT_FOUND: Strategy(
        type=StrategyType.FEEL_FELT_FOUND,
        name="Feel, Felt, Found",
        description="Empathize, relate, then redirect with evidence",
        tactics=[
            Tactic(
                name="acknowledge_feeling",
                description="Validate the concern",
                prompt_instruction="Acknowledge the client's concern with empathy: 'I understand how you feel about that.'",
            ),
            Tactic(
                name="share_similar",
                description="Relate with others' experience",
                prompt_instruction="Share that others have felt the same way: 'Many of our clients initially felt the same.'",
            ),
            Tactic(
                name="reveal_outcome",
                description="Show what they found",
                prompt_instruction="Share what those clients discovered after moving forward: 'What they found was...' with specific positive outcomes.",
            ),
        ],
    ),
    StrategyType.BOOMERANG: Strategy(
        type=StrategyType.BOOMERANG,
        name="Boomerang",
        description="Turn the objection into a reason to buy",
        tactics=[
            Tactic(
                name="catch_objection",
                description="Acknowledge the objection",
                prompt_instruction="Acknowledge the objection clearly and respectfully. Show you heard them.",
            ),
            Tactic(
                name="flip_to_benefit",
                description="Turn it into a positive",
                prompt_instruction="Reframe the objection as a reason to buy: 'That's exactly why you need this — because...'",
            ),
        ],
    ),
    StrategyType.ACKNOWLEDGE_REDIRECT: Strategy(
        type=StrategyType.ACKNOWLEDGE_REDIRECT,
        name="Acknowledge & Redirect",
        description="Validate the concern, then refocus on value",
        tactics=[
            Tactic(
                name="validate_concern",
                description="Show understanding",
                prompt_instruction="Validate the client's concern without being dismissive: 'That's a fair point, and I appreciate you raising it.'",
            ),
            Tactic(
                name="redirect_to_value",
                description="Steer back to benefits",
                prompt_instruction="Redirect the conversation to the key value or benefit that addresses their underlying need.",
            ),
        ],
    ),
    StrategyType.ISOLATION: Strategy(
        type=StrategyType.ISOLATION,
        name="Objection Isolation",
        description="Isolate the real objection from surface concerns",
        tactics=[
            Tactic(
                name="isolate_concern",
                description="Find the real objection",
                prompt_instruction="Ask: 'If we could address this concern, would everything else work for you?' to isolate the real blocker.",
            ),
            Tactic(
                name="solve_specific",
                description="Address the isolated issue",
                prompt_instruction="Focus entirely on solving the one isolated concern with a specific, concrete solution.",
            ),
        ],
    ),
    # --- Rapport ---
    StrategyType.RAPPORT_BUILDING: Strategy(
        type=StrategyType.RAPPORT_BUILDING,
        name="Rapport Building",
        description="Build trust and connection before business",
        tactics=[
            Tactic(
                name="warm_opening",
                description="Create a welcoming atmosphere",
                prompt_instruction="Start with a warm, genuine greeting. Show interest in the person, not just the sale.",
            ),
            Tactic(
                name="find_common_ground",
                description="Discover shared interests",
                prompt_instruction="Find common ground: shared interests, similar experiences, or mutual connections. Be genuine, not scripted.",
            ),
        ],
    ),
    StrategyType.EMPATHIC_LISTENING: Strategy(
        type=StrategyType.EMPATHIC_LISTENING,
        name="Empathic Listening",
        description="Deep listening to understand emotions and needs",
        tactics=[
            Tactic(
                name="reflect_back",
                description="Mirror what was said",
                prompt_instruction="Reflect back what the client said in your own words. Show you truly heard and understood them.",
            ),
            Tactic(
                name="explore_deeper",
                description="Ask about feelings",
                prompt_instruction="Gently ask about the emotions behind their words: 'How does that make you feel?' or 'That sounds frustrating.'",
            ),
        ],
    ),
    StrategyType.STORYTELLING: Strategy(
        type=StrategyType.STORYTELLING,
        name="Storytelling",
        description="Use relevant stories to illustrate value",
        tactics=[
            Tactic(
                name="relevant_anecdote",
                description="Tell a relevant story",
                prompt_instruction="Share a brief, relevant story about a similar client or situation. Make it specific and relatable.",
            ),
            Tactic(
                name="draw_parallel",
                description="Connect story to their situation",
                prompt_instruction="Explicitly connect the story to the client's situation: 'Your case is very similar because...'",
            ),
        ],
    ),
    StrategyType.MIRRORING: Strategy(
        type=StrategyType.MIRRORING,
        name="Mirroring",
        description="Match the client's communication style",
        tactics=[
            Tactic(
                name="match_style",
                description="Adapt to their pace and tone",
                prompt_instruction="Match the client's communication style: if they're formal, be formal. If casual, be casual. Mirror their pace.",
            ),
            Tactic(
                name="repeat_key_phrases",
                description="Echo their language",
                prompt_instruction="Naturally repeat key words or phrases the client uses. This builds unconscious rapport.",
            ),
        ],
    ),
    # --- Retention ---
    StrategyType.FOLLOW_UP_VALUE: Strategy(
        type=StrategyType.FOLLOW_UP_VALUE,
        name="Follow-Up Value",
        description="Deliver value in follow-up to maintain engagement",
        tactics=[
            Tactic(
                name="share_resource",
                description="Provide helpful content",
                prompt_instruction="Offer a relevant resource, tip, or piece of information that adds value beyond the sale.",
            ),
            Tactic(
                name="check_satisfaction",
                description="Ask about their experience",
                prompt_instruction="Ask how things are going with their previous purchase or interaction. Show genuine interest in their satisfaction.",
            ),
        ],
    ),
    StrategyType.REACTIVATION: Strategy(
        type=StrategyType.REACTIVATION,
        name="Reactivation",
        description="Re-engage dormant or lost clients",
        tactics=[
            Tactic(
                name="recall_history",
                description="Reference past interactions",
                prompt_instruction="Reference their previous interest or purchase. Show you remember them and value the relationship.",
            ),
            Tactic(
                name="new_offer",
                description="Present something new",
                prompt_instruction="Share what's new or improved since their last interaction. Give them a reason to re-engage.",
            ),
        ],
    ),
    StrategyType.LOYALTY_REINFORCEMENT: Strategy(
        type=StrategyType.LOYALTY_REINFORCEMENT,
        name="Loyalty Reinforcement",
        description="Strengthen relationship with existing clients",
        tactics=[
            Tactic(
                name="acknowledge_loyalty",
                description="Recognize their commitment",
                prompt_instruction="Acknowledge their loyalty and history. Thank them for being a valued client.",
            ),
            Tactic(
                name="exclusive_benefit",
                description="Offer loyalty perks",
                prompt_instruction="Share exclusive benefits, early access, or special offers available to loyal clients.",
            ),
        ],
    ),
    # --- Specialized ---
    StrategyType.COMPARISON_ADVANTAGE: Strategy(
        type=StrategyType.COMPARISON_ADVANTAGE,
        name="Comparison Advantage",
        description="Win the comparison by highlighting unique strengths",
        tactics=[
            Tactic(
                name="acknowledge_competition",
                description="Respect competitors",
                prompt_instruction="Acknowledge competitors respectfully. Never disparage them — it reflects poorly.",
            ),
            Tactic(
                name="highlight_differentiators",
                description="Show unique advantages",
                prompt_instruction="Clearly articulate what makes your solution uniquely better for their specific needs.",
            ),
        ],
    ),
    StrategyType.EDUCATIONAL_SELLING: Strategy(
        type=StrategyType.EDUCATIONAL_SELLING,
        name="Educational Selling",
        description="Educate the client to build trust and informed decisions",
        tactics=[
            Tactic(
                name="teach_concept",
                description="Explain relevant concepts",
                prompt_instruction="Teach the client something relevant about their problem domain. Position yourself as a helpful expert.",
            ),
            Tactic(
                name="guide_evaluation",
                description="Help them evaluate options",
                prompt_instruction="Provide a framework or criteria for evaluating solutions. Help them make an informed decision.",
            ),
        ],
    ),
    StrategyType.SILENCE_ENGAGEMENT: Strategy(
        type=StrategyType.SILENCE_ENGAGEMENT,
        name="Silence Engagement",
        description="Draw out quiet or unresponsive clients",
        tactics=[
            Tactic(
                name="open_gentle_question",
                description="Ask a soft, inviting question",
                prompt_instruction="Ask a gentle, easy-to-answer question: 'What brings you here today?' or 'Is there something specific you're looking for?'",
            ),
            Tactic(
                name="patience_signal",
                description="Show patience and openness",
                prompt_instruction="Signal that you're in no rush: 'Take your time' or 'I'm here whenever you're ready.' Be warm, not pushy.",
            ),
            Tactic(
                name="offer_help",
                description="Provide a low-pressure offer",
                prompt_instruction="Offer concrete but low-pressure help: 'I can share some information if that would be helpful.'",
            ),
        ],
    ),
    StrategyType.RISK_REVERSAL: Strategy(
        type=StrategyType.RISK_REVERSAL,
        name="Risk Reversal",
        description="Remove perceived risk from the purchase decision",
        tactics=[
            Tactic(
                name="identify_risk",
                description="Acknowledge what they're risking",
                prompt_instruction="Acknowledge the risk the client perceives: money, time, reputation. Show you understand their hesitation.",
            ),
            Tactic(
                name="offer_guarantee",
                description="Present risk mitigation",
                prompt_instruction="Offer guarantees, refund policies, trial periods, or other risk-reducing mechanisms.",
            ),
        ],
    ),
    StrategyType.ANCHORING: Strategy(
        type=StrategyType.ANCHORING,
        name="Anchoring",
        description="Set a reference point to make the actual offer attractive",
        tactics=[
            Tactic(
                name="set_high_anchor",
                description="Establish a high reference",
                prompt_instruction="Present the premium option or full price first. Establish a high reference point before showing the actual offer.",
            ),
            Tactic(
                name="present_actual_offer",
                description="Show the favorable comparison",
                prompt_instruction="Present the actual offer as a favorable comparison to the anchor. Highlight the savings or better value.",
            ),
        ],
    ),
}
