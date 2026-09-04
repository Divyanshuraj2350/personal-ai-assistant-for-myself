def get_tool(action):

    tools = {
        "answer": "qwen",
        "calculate": "calculator",
        "draft_email": "email",
        "analyze_job": "job_analyzer",
        "search_jobs": "job_search",
        "prepare_post": "social",
        "search_web": "web",
    }

    return tools.get(action)