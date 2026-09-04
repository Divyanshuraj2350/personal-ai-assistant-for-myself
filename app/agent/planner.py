from app.agent.router import detect_intent


def create_plan(message):

    intent = detect_intent(message)

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

    return plans[intent]