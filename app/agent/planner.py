from app.agent.router import get_routing_decision


def create_plan(message):
    """
    Create an execution plan from the user's message.

    Supports:

    1. Normal single-intent requests
    2. Compound requests

    Example:

        "search for Python internships"

    becomes:

        {
            "intent": "job_search",
            "action": "search_jobs",
            "requires_approval": False
        }

    Example:

        "search latest ML jobs and analyze them"

    becomes:

        {
            "intent": "job_search",
            "compound": True,
            "steps": [
                {
                    "intent": "job_search",
                    "action": "search_jobs",
                    "requires_approval": False
                },
                {
                    "intent": "job_analysis",
                    "action": "analyze_jobs",
                    "requires_approval": False
                }
            ]
        }
    """

    # ==========================================================
    # GET ROUTING DECISION
    # ==========================================================

    routing = get_routing_decision(message)

    intent = routing.get(
        "intent",
        "chat",
    )

    compound = routing.get(
        "compound",
        False,
    )

    secondary_intents = routing.get(
        "secondary_intents",
        [],
    )

    # Make sure secondary_intents is always a list.
    if not isinstance(
        secondary_intents,
        list,
    ):
        secondary_intents = []

    # ==========================================================
    # NORMAL SINGLE-STEP PLANS
    # ==========================================================

    plans = {
        "chat": {
            "intent": "chat",
            "action": "answer",
            "requires_approval": False,
        },

        "calculation": {
            "intent": "calculation",
            "action": "calculate",
            "requires_approval": False,
        },

        "email": {
            "intent": "email",
            "action": "draft_email",
            "requires_approval": True,
        },

        "job_analysis": {
            "intent": "job_analysis",
            "action": "analyze_job",
            "requires_approval": False,
        },

        "job_search": {
            "intent": "job_search",
            "action": "search_jobs",
            "requires_approval": False,
        },

        "social": {
            "intent": "social",
            "action": "prepare_post",
            "requires_approval": True,
        },

        "web": {
            "intent": "web",
            "action": "search_web",
            "requires_approval": False,
        },
    }

    # ==========================================================
    # COMPOUND JOB SEARCH + JOB ANALYSIS
    # ==========================================================

    if (
        compound
        and intent == "job_search"
        and "job_analysis" in secondary_intents
    ):
        return {
            "intent": "job_search",
            "compound": True,
            "secondary_intents": [
                "job_analysis"
            ],
            "action": None,
            "requires_approval": False,
            "steps": [
                {
                    "intent": "job_search",
                    "action": "search_jobs",
                    "requires_approval": False,
                },
                {
                    "intent": "job_analysis",
                    "action": "analyze_jobs",
                    "requires_approval": False,
                },
            ],
        }

    # ==========================================================
    # GENERIC COMPOUND PLAN
    # ==========================================================

    if compound and secondary_intents:

        steps = []

        # ------------------------------------------------------
        # PRIMARY INTENT
        # ------------------------------------------------------

        primary_plan = plans.get(
            intent
        )

        if primary_plan:
            steps.append(
                {
                    "intent": primary_plan["intent"],
                    "action": primary_plan["action"],
                    "requires_approval": primary_plan[
                        "requires_approval"
                    ],
                }
            )

        # ------------------------------------------------------
        # SECONDARY INTENTS
        # ------------------------------------------------------

        for secondary_intent in secondary_intents:

            secondary_plan = plans.get(
                secondary_intent
            )

            if not secondary_plan:
                continue

            steps.append(
                {
                    "intent": secondary_plan["intent"],
                    "action": secondary_plan["action"],
                    "requires_approval": secondary_plan[
                        "requires_approval"
                    ],
                }
            )

        # ------------------------------------------------------
        # RETURN COMPOUND PLAN
        # ------------------------------------------------------

        if len(steps) > 1:

            return {
                "intent": intent,
                "compound": True,
                "secondary_intents": secondary_intents,
                "action": None,
                "requires_approval": any(
                    step["requires_approval"]
                    for step in steps
                ),
                "steps": steps,
            }

    # ==========================================================
    # NORMAL SINGLE-STEP PLAN
    # ==========================================================

    plan = plans.get(
        intent
    )

    if plan is None:

        # Safe fallback.
        return {
            "intent": "chat",
            "action": "answer",
            "requires_approval": False,
        }

    return {
        **plan,
        "compound": False,
        "secondary_intents": [],
    }