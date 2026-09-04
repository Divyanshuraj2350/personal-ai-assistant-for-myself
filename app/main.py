from fastapi import FastAPI, Request
from fastapi.responses import (
    FileResponse,
    StreamingResponse,
    RedirectResponse,
    HTMLResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

import httpx
import json
import html
import markdown

from app.rag.store import search_documents

from app.agent.memory import (
    get_history,
    add_message,
    search_memories,
    remember_if_requested,
)
from app.agent.planner import create_plan
from app.agent.executor import execute_plan
from app.rag.retriever import (
    retrieve_relevant_knowledge,
)
from app.agent.context_builder import (
    build_execution_context,
    build_rag_context, 
)

from app.agent.approval import approve, reject
from app.agent.approval_store import get_approval

from app.agent.gmail_auth import (
    create_authorization_url,
    handle_oauth_callback,
    is_gmail_connected,
)

# ==========================================================
# CAREER / RESUME AGENT
# ==========================================================

from app.agent.job_fetcher import fetch_job_page
from app.agent.job_analyzer import analyze_job
from app.agent.job_matcher import match_job
from app.agent.experience_evaluator import evaluate_experience
from app.agent.resume_tailor import tailor_resume
from app.agent.resume_ai import create_ai_resume
from app.agent.resume_validator import validate_resume
from app.agent.resume_renderer import render_resume_pdf
from app.agent.career_profile import load_profile


# ==========================================================
# APP
# ==========================================================

app = FastAPI(
    title="My Personal AI"
)


app.mount(
    "/frontend",
    StaticFiles(directory="frontend"),
    name="frontend",
)


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:8b"


# ==========================================================
# REQUEST MODELS
# ==========================================================

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class CareerRequest(BaseModel):
    job_url: str


# ==========================================================
# RESPONSE MODE
# ==========================================================

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

    if (
        len(message) > 180
        or any(
            word in text
            for word in detailed_words
        )
    ):
        return "detailed"

    if len(message) < 40:
        return "short"

    return "normal"


# ==========================================================
# ROOT
# ==========================================================

@app.get("/")
def root():

    return FileResponse(
        "frontend/index.html"
    )


# ==========================================================
# HEALTH
# ==========================================================

@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# ==========================================================
# GMAIL OAUTH
# ==========================================================

@app.get("/gmail/login")
def gmail_login():

    try:

        authorization_url = (
            create_authorization_url()
        )

        return RedirectResponse(
            url=authorization_url
        )

    except Exception as error:

        return HTMLResponse(
            content=f"""
            <h2>Gmail OAuth Error</h2>
            <p>{html.escape(str(error))}</p>
            """,
            status_code=500,
        )


@app.get("/gmail/oauth2callback")
def gmail_oauth_callback(
    request: Request
):

    try:

        authorization_response = str(
            request.url
        )

        handle_oauth_callback(
            authorization_response
        )

        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>

            <head>
                <title>Gmail Connected</title>
            </head>

            <body style="
                font-family: Arial, sans-serif;
                background: #212121;
                color: white;
                text-align: center;
                padding-top: 100px;
            ">

                <h1>✅ Gmail Connected</h1>

                <p>
                    My Personal AI is now authorized
                    to send emails through Gmail.
                </p>

                <p>
                    You can close this window and return
                    to My Personal AI.
                </p>

            </body>

            </html>
            """,
            status_code=200,
        )

    except Exception as error:

        return HTMLResponse(
            content=f"""
            <!DOCTYPE html>
            <html>

            <head>
                <title>Gmail OAuth Error</title>
            </head>

            <body style="
                font-family: Arial, sans-serif;
                background: #212121;
                color: white;
                padding: 40px;
            ">

                <h1>❌ Gmail Connection Failed</h1>

                <p>
                    {html.escape(str(error))}
                </p>

                <p>
                    Please try the Gmail connection again.
                </p>

            </body>

            </html>
            """,
            status_code=500,
        )


@app.get("/gmail/status")
def gmail_status():

    connected = (
        is_gmail_connected()
    )

    return {
        "gmail_connected": connected
    }


# ==========================================================
# APPROVAL ENDPOINTS
# ==========================================================

@app.get(
    "/approval/{approval_id}"
)
def get_approval_status(
    approval_id: str
):

    approval = get_approval(
        approval_id
    )

    if not approval:

        return {
            "status": "error",
            "message": (
                "Approval request not found."
            ),
        }

    return approval


@app.post(
    "/approval/{approval_id}/approve"
)
def approve_email(
    approval_id: str
):

    return approve(
        approval_id
    )


@app.post(
    "/approval/{approval_id}/reject"
)
def reject_email(
    approval_id: str
):

    return reject(
        approval_id
    )


# ==========================================================
# CAREER / RESUME PIPELINE
# ==========================================================

@app.post("/career/analyze")
async def career_analyze(
    request: CareerRequest
):

    job_url = request.job_url.strip()

    if not job_url:

        return {
            "status": "error",
            "stage": "input",
            "message": (
                "Job URL is required."
            ),
        }

    try:

        # --------------------------------------------------
        # 1. FETCH JOB
        # --------------------------------------------------

        job_page = await fetch_job_page(
            job_url
        )

        if not isinstance(
            job_page,
            dict,
        ):

            return {
                "status": "error",
                "stage": "fetch",
                "message": (
                    "Job fetcher returned "
                    "an invalid response."
                ),
            }

        if (
            job_page.get("status")
            != "success"
        ):

            return {
                "status": "error",
                "stage": "fetch",
                "message": job_page.get(
                    "error",
                    "Could not fetch the job posting.",
                ),
            }

        # --------------------------------------------------
        # 2. ANALYZE JOB
        # --------------------------------------------------

        analysis = await analyze_job(
            job_page
        )

        if not isinstance(
            analysis,
            dict,
        ):

            return {
                "status": "error",
                "stage": "analysis",
                "message": (
                    "Job analyzer returned "
                    "an invalid response."
                ),
            }

        if (
            analysis.get("status")
            != "success"
        ):

            return {
                "status": "error",
                "stage": "analysis",
                "message": analysis.get(
                    "error",
                    "Could not analyze the job.",
                ),
            }

        job = analysis.get(
            "job",
            {},
        )

        if not isinstance(
            job,
            dict,
        ):

            return {
                "status": "error",
                "stage": "analysis",
                "message": (
                    "Job analysis did not "
                    "produce valid job data."
                ),
            }

        # Make sure source URL survives
        if not job.get(
            "application_url"
        ):

            job[
                "application_url"
            ] = job_url

        # --------------------------------------------------
        # 3. MATCH JOB
        # --------------------------------------------------

        match_result = match_job(
            job
        )

        if not isinstance(
            match_result,
            dict,
        ):

            return {
                "status": "error",
                "stage": "matching",
                "message": (
                    "Job matcher returned "
                    "an invalid response."
                ),
            }

        if (
            match_result.get("status")
            != "success"
        ):

            return {
                "status": "error",
                "stage": "matching",
                "message": (
                    "Could not match the job "
                    "against the career profile."
                ),
                "match": match_result,
            }

        # --------------------------------------------------
        # 4. EXPERIENCE EVALUATION
        # --------------------------------------------------

        profile = load_profile()

        experience_result = (
            evaluate_experience(
                profile,
                job,
            )
        )

        # --------------------------------------------------
        # 5. RESUME TAILORING PLAN
        # --------------------------------------------------

        tailoring_result = (
            tailor_resume(
                job,
                match_result,
            )
        )

        if not isinstance(
            tailoring_result,
            dict,
        ):

            return {
                "status": "error",
                "stage": "tailoring",
                "message": (
                    "Resume tailoring returned "
                    "an invalid response."
                ),
            }

        if (
            tailoring_result.get("status")
            != "success"
        ):

            return {
                "status": "error",
                "stage": "tailoring",
                "message": (
                    "Could not build the "
                    "resume tailoring plan."
                ),
            }

        # --------------------------------------------------
        # 6. GENERATE GROUNDED AI RESUME
        # --------------------------------------------------

        ai_result = await create_ai_resume(
            job,
            match_result,
        )

        if not isinstance(
            ai_result,
            dict,
        ):

            return {
                "status": "error",
                "stage": "resume_generation",
                "message": (
                    "Resume AI returned "
                    "an invalid response."
                ),
            }

        if (
            ai_result.get("status")
            not in [
                "success",
                "draft",
            ]
        ):

            return {
                "status": "error",
                "stage": "resume_generation",
                "message": ai_result.get(
                    "message",
                    "Could not generate the resume.",
                ),
            }

        resume = ai_result.get(
            "resume"
        )

        if not isinstance(
            resume,
            dict,
        ):

            return {
                "status": "error",
                "stage": "resume_generation",
                "message": (
                    "Generated resume "
                    "is invalid."
                ),
            }

        # --------------------------------------------------
        # 7. VALIDATE
        # --------------------------------------------------

        validation = (
            validate_resume(
                resume
            )
        )

        if not isinstance(
            validation,
            dict,
        ):

            return {
                "status": "error",
                "stage": "validation",
                "message": (
                    "Resume validator "
                    "returned an invalid response."
                ),
            }

        if not validation.get(
            "valid",
            False,
        ):

            return {
                "status": "error",
                "stage": "validation",
                "message": (
                    "Generated resume failed "
                    "factual validation."
                ),
                "validation": validation,
                "resume": resume,
            }

        # --------------------------------------------------
        # 8. RENDER PDF
        # --------------------------------------------------

        pdf_result = (
            render_resume_pdf(
                resume
            )
        )

        if not isinstance(
            pdf_result,
            dict,
        ):

            return {
                "status": "error",
                "stage": "pdf",
                "message": (
                    "Resume renderer returned "
                    "an invalid response."
                ),
            }

        if (
            pdf_result.get("status")
            != "success"
        ):

            return {
                "status": "error",
                "stage": "pdf",
                "message": (
                    "Resume PDF generation failed."
                ),
                "pdf": pdf_result,
            }

        pdf_path = pdf_result.get(
            "path"
        )

        # --------------------------------------------------
        # 9. RETURN COMPLETE RESULT
        # --------------------------------------------------

        skills = match_result.get(
            "skills",
            {},
        )

        return {
            "status": "success",

            "job": job,

            "match": {
                "overall_score":
                    match_result.get(
                        "overall_score"
                    ),

                "recommendation":
                    match_result.get(
                        "recommendation"
                    ),

                "role_score":
                    match_result.get(
                        "role_score"
                    ),

                "location_score":
                    match_result.get(
                        "location_score"
                    ),

                "work_mode_score":
                    match_result.get(
                        "work_mode_score"
                    ),

                "skills": skills,
            },

            "experience":
                experience_result,

            "tailoring": {
                "priority_skills":
                    tailoring_result.get(
                        "priority_skills",
                        [],
                    ),

                "priority_projects":
                    tailoring_result.get(
                        "priority_projects",
                        [],
                    ),

                "missing_requirements":
                    tailoring_result.get(
                        "missing_requirements",
                        {},
                    ),
            },

            "validation": validation,

            "resume": resume,

            "pdf": {
                "status":
                    pdf_result.get(
                        "status"
                    ),

                "path": pdf_path,
            },
        }

    except Exception as exc:

        return {
            "status": "error",
            "stage": "career_pipeline",
            "message": str(exc),
        }


# ==========================================================
# DOWNLOAD GENERATED RESUME
# ==========================================================

@app.get("/career/resume")
def download_resume(
    path: str
):

    if not path:

        return {
            "status": "error",
            "message": (
                "Resume path is required."
            ),
        }

    try:

        import os

        # Prevent arbitrary absolute paths
        normalized = os.path.normpath(
            path
        )

        allowed_directory = os.path.abspath(
            "data/generated_resumes"
        )

        absolute_path = os.path.abspath(
            normalized
        )

        if not absolute_path.startswith(
            allowed_directory
        ):

            return {
                "status": "error",
                "message": (
                    "Invalid resume path."
                ),
            }

        if not os.path.isfile(
            absolute_path
        ):

            return {
                "status": "error",
                "message": (
                    "Resume file not found."
                ),
            }

        return FileResponse(
            absolute_path,
            media_type="application/pdf",
            filename=os.path.basename(
                absolute_path
            ),
        )

    except Exception as exc:

        return {
            "status": "error",
            "message": str(exc),
        }


# ==========================================================
# CHAT
# ==========================================================

@app.post("/chat")
async def chat(
    request: ChatRequest
):

    session_id = (
        request.session_id.strip()
        if request.session_id
        and request.session_id.strip()
        else "default"
    )

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

    execution_context = ""

    execution = await execute_plan(
        plan,
        request.message
    )


    execution_context = build_execution_context(
        execution
    )
    history = get_history(
        session_id
    )

    # ======================================================
    # EMAIL APPROVAL RESPONSE
    # ======================================================

    if (
        execution.get("status")
        == "pending_approval"
    ):

        approval_data = {
            "type": "approval",
            "approval_id":
                execution[
                    "approval_id"
                ],
            "tool":
                execution["tool"],
            "action":
                execution["action"],
            "recipient":
                execution["recipient"],
            "subject":
                execution["subject"],
            "body":
                execution["body"],
            "approved":
                execution["approved"],
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
    # JOB ANALYSIS RESPONSE
    # ======================================================

    if (
        execution.get("status")
        == "completed"
        and execution.get("action")
        == "analyze_job"
    ):

        job = execution["job"]

        async def job_stream():

            yield (
                "data: "
                + json.dumps(
                    {
                        "type":
                            "job_analysis",

                        "source_url":
                            execution[
                                "source_url"
                            ],

                        "job":
                            job,
                    }
                )
                + "\n\n"
            )

            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "done",
                    }
                )
                + "\n\n"
            )

        return StreamingResponse(
            job_stream(),
            media_type="text/event-stream",
        )

    # ======================================================
    # NORMAL AI RESPONSE
    # ======================================================

    history = get_history(
        session_id
    )

    # ======================================================
    # WEB SEARCH RESULTS
    # ======================================================

    web_context = ""

    if (
        execution.get("status") == "completed"
        and execution.get("action") == "search_web"
    ):

        results = execution.get(
            "results",
            []
        )

        if results:

            web_parts = []

            for index, result in enumerate(
                results,
                start=1,
            ):

                title = result.get(
                    "title",
                    "",
                )

                url = result.get(
                    "url",
                    "",
                )

                content = result.get(
                    "content",
                    "",
                )

                web_parts.append(
                    f"[Source {index}]\n"
                    f"Title: {title}\n"
                    f"URL: {url}\n"
                    f"Content: {content}"
                )

            web_context = (
                "\n\n"
                "CURRENT WEB SEARCH RESULTS:\n\n"
                + "\n\n".join(web_parts)
                + "\n\n"
                "Use these web results to answer the user's "
                "question. Prefer the information from these "
                "results for current or time-sensitive facts. "
                "Do not claim that you lack web access when "
                "search results are provided. "
                "Do not invent information that is not supported "
                "by the search results."
            )


    # ======================================================
    # LONG-TERM PERSONAL MEMORY
    # ======================================================

    # Save explicit user memory requests before retrieval.
    saved_memory = remember_if_requested(
        request.message
    )

    # Retrieve memories relevant to the current message.
    memories = search_memories(
        request.message,
        limit=5,
    )

    # Make a newly saved memory available immediately.
    if saved_memory:

        already_present = any(
            memory.get("id")
            == saved_memory.get("id")
            for memory in memories
        )

        if not already_present:

            memories.insert(
                0,
                saved_memory,
            )

        memories = memories[:5]


    if memories:

        memory_context = "\n\n".join(
            f"- {memory.get('content', '')}"
            for memory in memories
        )

        personal_memory = (
            "\n\n"
            "Relevant personal memory:\n"
            f"{memory_context}\n\n"
            "Use these memories only when relevant. "
            "Do not mention the memory system to the user."
        )

    else:

        personal_memory = ""


    # ======================================================
    # RAG KNOWLEDGE
    # ======================================================

    retrieved_knowledge = (
        retrieve_relevant_knowledge(
            request.message
        )
    )

    rag_context = build_rag_context(
        retrieved_knowledge
    )

    system_prompt = (

        "You are My Personal AI, "
        "a CSE-focused personal assistant. "

        "Answer accurately and clearly. "

        "Use Markdown for headings, "
        "lists and code blocks. "

        "When answering questions about what the user "
        "previously said, mentioned, preferred, decided, "
        "or did, use only the current conversation history "
        "and relevant personal memory provided to you. "

        "Never invent or guess a previous user statement. "

        "If the requested information is not present in "
        "the current conversation history or relevant "
        "personal memory, clearly say that you do not have "
        "that information. "

        f"{instructions[mode]}"

        f"{personal_memory}"

        f"{rag_context}"

        f"{execution_context}"
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
            "num_predict":
                limits[mode],
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

                async for line in (
                    response.aiter_lines()
                ):

                    if not line:
                        continue

                    data = json.loads(
                        line
                    )

                    content = (
                        data
                        .get(
                            "message",
                            {}
                        )
                        .get(
                            "content",
                            ""
                        )
                    )

                    if content:

                        full_response += (
                            content
                        )

                        yield (
                            "data: "
                            + json.dumps(
                                {
                                    "type":
                                        "token",

                                    "content":
                                        content,
                                }
                            )
                            + "\n\n"
                        )

                    if data.get(
                        "done"
                    ):

                        add_message(
                            session_id,
                            "assistant",
                            full_response,
                        )

                        safe_text = (
                            html.escape(
                                full_response
                            )
                        )

                        formatted = (
                            markdown.markdown(
                                safe_text,
                                extensions=[
                                    "fenced_code",
                                    "tables",
                                ],
                            )
                        )

                        yield (
                            "data: "
                            + json.dumps(
                                {
                                    "type":
                                        "done",

                                    "html":
                                        formatted,
                                }
                            )
                            + "\n\n"
                        )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )