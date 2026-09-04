from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import httpx
import json
import html
import markdown

from app.rag.store import search_documents

from app.agent.memory import get_history, add_message
from app.agent.planner import create_plan
from app.agent.executor import execute_plan

from app.agent.approval import approve, reject
from app.agent.approval_store import get_approval


app = FastAPI(title="My Personal AI")

app.mount(
    "/frontend",
    StaticFiles(directory="frontend"),
    name="frontend",
)


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:8b"


class ChatRequest(BaseModel):
    message: str


def get_response_mode(message):

    text = message.lower()

    detailed_words = [
        "explain",
        "solve",
        "debug",
        "write code",
        "write the code",
        "code",
        "implement",
        "implementation",
        "compare",
        "analyze",
        "describe",
        "how does",
        "how do",
        "why",
        "example",
        "in java",
        "in python",
        "in c++",
        "in javascript",
    ]

    if len(message) > 180 or any(
        word in text for word in detailed_words
    ):
        return "detailed"

    if len(message) < 40:
        return "short"

    return "normal"


@app.get("/")
def root():

    return FileResponse(
        "frontend/index.html"
    )


@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# ==========================================================
# APPROVAL ENDPOINTS
# ==========================================================


@app.get("/approval/{approval_id}")
def get_approval_status(approval_id: str):

    approval = get_approval(
        approval_id
    )

    if not approval:

        return {
            "status": "error",
            "message": "Approval request not found.",
        }

    return approval


@app.post("/approval/{approval_id}/approve")
def approve_email(approval_id: str):

    return approve(
        approval_id
    )


@app.post("/approval/{approval_id}/reject")
def reject_email(approval_id: str):

    return reject(
        approval_id
    )


# ==========================================================
# CHAT
# ==========================================================


@app.post("/chat")
async def chat(request: ChatRequest):

    session_id = "default"

    mode = get_response_mode(
        request.message
    )

    limits = {
        "short": 512,
        "normal": 1024,
        "detailed": 4096,
    }

    instructions = {

        "short": (
            "Answer briefly and directly. "
            "Give only the information necessary "
            "to answer the question."
        ),

        "normal": (
            "Give a clear explanation with enough detail "
            "to answer completely. "
            "Avoid unnecessary information."
        ),

        "detailed": (
            "Think carefully about the request before answering. "
            "Complete every part of the user's request. "
            "If code is requested, provide complete executable code. "
            "Check the code for syntax and logical errors before answering. "
            "Do not stop before completing the requested answer."
        ),
    }


    # ======================================================
    # AGENT PLANNING / EXECUTION
    # ======================================================

    plan = create_plan(
        request.message
    )

    execution = await execute_plan(
        plan,
        request.message
    )


    # ======================================================
    # EMAIL APPROVAL RESPONSE
    # ======================================================

    if execution.get("status") == "pending_approval":

        approval_data = {
            "type": "approval",
            "approval_id": execution["approval_id"],
            "tool": execution["tool"],
            "action": execution["action"],
            "recipient": execution["recipient"],
            "subject": execution["subject"],
            "body": execution["body"],
            "approved": execution["approved"],
        }

        async def approval_stream():

            yield (
                "data: "
                + json.dumps(
                    approval_data
                )
                + "\n\n"
            )

            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "done"
                    }
                )
                + "\n\n"
            )

        return StreamingResponse(
            approval_stream(),
            media_type="text/event-stream",
        )


    # ======================================================
    # NORMAL AI RESPONSE
    # ======================================================

    history = get_history(
        session_id
    )


    context = search_documents(
        request.message
    )


    if context:

        rag_context = "\n\n".join(
            context
        )

        knowledge = (
            "\n\n"
            "Use the following retrieved knowledge "
            "when relevant. "
            "Do not mention the retrieval process.\n\n"
            f"Retrieved knowledge:\n"
            f"{rag_context}"
        )

    else:

        knowledge = ""


    system_prompt = (

        "You are My Personal AI, "
        "a CSE-focused assistant. "

        "Answer accurately and clearly. "

        "Use Markdown for headings, "
        "lists and code blocks. "

        f"{instructions[mode]}"

        f"{knowledge}"
    )


    messages = [

        {
            "role": "system",
            "content": system_prompt,
        }

    ]


    messages.extend(
        history
    )


    messages.append(

        {
            "role": "user",
            "content": request.message,
        }

    )


    payload = {

        "model": MODEL_NAME,

        "messages": messages,

        "stream": True,

        "think": False,

        "options": {
            "num_predict": limits[mode],
        },
    }


    add_message(
        session_id,
        "user",
        request.message,
    )


    async def generate():

        full_response = ""


        async with httpx.AsyncClient(
            timeout=None
        ) as client:

            async with client.stream(
                "POST",
                OLLAMA_URL,
                json=payload,
            ) as response:

                response.raise_for_status()


                async for line in response.aiter_lines():

                    if not line:
                        continue


                    data = json.loads(
                        line
                    )


                    content = data.get(
                        "message",
                        {}
                    ).get(
                        "content",
                        ""
                    )


                    if content:

                        full_response += content


                        yield (

                            "data: "
                            + json.dumps(
                                {
                                    "type": "token",
                                    "content": content,
                                }
                            )
                            + "\n\n"
                        )


                    if data.get("done"):

                        add_message(
                            session_id,
                            "assistant",
                            full_response,
                        )


                        safe_text = html.escape(
                            full_response
                        )


                        formatted = markdown.markdown(

                            safe_text,

                            extensions=[
                                "fenced_code",
                                "tables",
                            ],
                        )


                        yield (

                            "data: "
                            + json.dumps(
                                {
                                    "type": "done",
                                    "html": formatted,
                                }
                            )
                            + "\n\n"
                        )


    return StreamingResponse(

        generate(),

        media_type="text/event-stream",
    )