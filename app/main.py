from fastapi import FastAPI, Request, UploadFile, File
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
from time import perf_counter

from app.agent.memory import (
    get_history,
    add_message,
    search_memories,
    remember_if_requested,
)
from app.agent.planner import create_plan
from app.agent.router import detect_knowledge_source
from app.agent.executor import execute_plan
from app.agent.context_builder import (
    build_execution_context,
    build_rag_context,
)
from app.rag.retriever import retrieve_relevant_knowledge

from app.agent.approval import approve, reject
from app.agent.approval_store import get_approval
from app.agent.gmail_auth import (
    create_authorization_url,
    handle_oauth_callback,
    is_gmail_connected,
)

from app.voice.stt import transcribe_audio
from app.voice.tts import synthesize_file

# ==========================================================
# CAREER / RESUME AGENT
# ==========================================================

from app.agent.job_fetcher import fetch_job_page
from app.agent.job_analyzer import analyze_job
from app.agent.job_matcher import match_job_to_profile
from app.agent.experience_evaluator import evaluate_experience
from app.agent.career_profile import load_profile
from app.agent.resume_intake import (
    intake_resume,
    ResumeIntakeError,
)
from app.agent.resume_extractor import extract_resume

from app.media.processor import (
    process_file,
    MediaProcessingError,
)
from app.agent.application_form import (
    inspect_application_form,
)
from app.agent.application_mapper import (
    map_application_fields,
)



# ==========================================================
# APP
# ==========================================================

app = FastAPI(title="My Personal AI")

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

class ResumeExtractionRequest(BaseModel):
    file_id: str
class ApplicationFormRequest(BaseModel):
    job_url: str
class ApplicationMappingRequest(BaseModel):
    job_url: str
    resume_file_id: str

# ==========================================================
# RESPONSE MODE
# ==========================================================

def get_response_mode(message):
    text = message.lower().strip()

    detailed_words = [
        "solve",
        "debug",
        "write code",
        "write the code",
        "code",
        "implement",
        "implementation",
        "compare",
        "analyze",
        "how does",
        "how do",
        "why",
        "in java",
        "in python",
        "in c++",
        "in javascript",
    ]

    normal_words = [
        "explain",
        "describe",
        "example",
        "tell me about",
    ]

    if len(message) > 180 or any(
        word in text
        for word in detailed_words
    ):
        return "detailed"

    if any(
        word in text
        for word in normal_words
    ):
        return "normal"

    if len(message) < 40:
        return "short"

    return "normal"


# ==========================================================
# ROOT
# ==========================================================

@app.get("/")
def root():
    return FileResponse("frontend/index.html")


# ==========================================================
# HEALTH
# ==========================================================

@app.get("/health")
def health():
    return {"status": "healthy"}


# ==========================================================
# VOICE -> CHAT
# ==========================================================

@app.post("/voice/chat")
async def voice_chat(
    audio: UploadFile = File(...),
    session_id: str = "default",
):
    """
    Audio -> Whisper STT -> existing chat/agent pipeline
    -> Chatterbox TTS -> audio response.
    """

    if not audio.filename:
        return {
            "status": "error",
            "message": "Audio file is required.",
        }

    import tempfile
    from pathlib import Path

    suffix = Path(audio.filename).suffix or ".wav"
    temp_path = None

    try:
        audio_data = await audio.read()

        if not audio_data:
            return {
                "status": "error",
                "message": "Uploaded audio is empty.",
            }

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_file.write(audio_data)
            temp_path = temp_file.name

        transcription = transcribe_audio(
            temp_path,
            language="auto",
            use_vad=True,
        )

        text = transcription["text"].strip()

        if not text:
            return {
                "status": "error",
                "message": "No speech was detected.",
            }

        chat_request = ChatRequest(
            message=text,
            session_id=session_id,
        )

        chat_response = await chat(chat_request)

        full_response = ""

        async for chunk in chat_response.body_iterator:
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8")

            for line in chunk.splitlines():
                if not line.startswith("data:"):
                    continue

                data_text = line[5:].strip()

                if not data_text:
                    continue

                try:
                    data = json.loads(data_text)
                except json.JSONDecodeError:
                    continue

                if data.get("type") == "token":
                    full_response += data.get("content", "")

        full_response = full_response.strip()

        if not full_response:
            return {
                "status": "error",
                "message": "AI returned an empty response.",
                "text": text,
            }

        language = "en"

        if any("\u0900" <= char <= "\u097F" for char in full_response):
            language = "hi"

        speech = synthesize_file(
            full_response,
            language=language,
        )

        return {
            "status": "success",
            "text": text,
            "response": full_response,
            "language": language,
            "audio_path": speech["audio_path"],
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
        }

    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass


# ==========================================================
# GMAIL OAUTH
# ==========================================================

@app.get("/gmail/login")
def gmail_login():
    try:
        authorization_url = create_authorization_url()

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
def gmail_oauth_callback(request: Request):
    try:
        authorization_response = str(request.url)

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
                <p>{html.escape(str(error))}</p>
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
    connected = is_gmail_connected()

    return {
        "gmail_connected": connected
    }


# ==========================================================
# APPROVAL ENDPOINTS
# ==========================================================

@app.get("/approval/{approval_id}")
def get_approval_status(approval_id: str):
    approval = get_approval(approval_id)

    if not approval:
        return {
            "status": "error",
            "message": "Approval request not found.",
        }

    return approval


@app.post("/approval/{approval_id}/approve")
def approve_email(approval_id: str):
    return approve(approval_id)


@app.post("/approval/{approval_id}/reject")
def reject_email(approval_id: str):
    return reject(approval_id)


# ==========================================================
# CAREER ANALYSIS
# ==========================================================

@app.post("/career/analyze")
async def career_analyze(request: CareerRequest):
    """
    Analyze a user-provided job URL.

    Current responsibility:
        fetch -> analyze -> match -> experience evaluation

    Resume generation is intentionally NOT part of this endpoint.
    The user's own resume will be handled by the Career Assistant
    resume-intake/application workflow.
    """

    job_url = request.job_url.strip()

    if not job_url:
        return {
            "status": "error",
            "stage": "input",
            "message": "Job URL is required.",
        }

    try:
        # --------------------------------------------------
        # 1. FETCH JOB
        # --------------------------------------------------

        job_page = await fetch_job_page(job_url)

        if not isinstance(job_page, dict):
            return {
                "status": "error",
                "stage": "fetch",
                "message": "Job fetcher returned an invalid response.",
            }

        if job_page.get("status") != "success":
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

        analysis = await analyze_job(job_page)

        if not isinstance(analysis, dict):
            return {
                "status": "error",
                "stage": "analysis",
                "message": "Job analyzer returned an invalid response.",
            }

        if analysis.get("status") != "success":
            return {
                "status": "error",
                "stage": "analysis",
                "message": analysis.get(
                    "error",
                    "Could not analyze the job.",
                ),
            }

        job = analysis.get("job", {})

        if not isinstance(job, dict):
            return {
                "status": "error",
                "stage": "analysis",
                "message": "Job analysis did not produce valid job data.",
            }

        if not job.get("application_url"):
            job["application_url"] = job_url

        # --------------------------------------------------
        # 3. LOAD PROFILE + MATCH JOB
        # --------------------------------------------------

        profile = await load_profile()

        match_result = match_job_to_profile(
            job,
            profile,
        )

        if not isinstance(match_result, dict):
            return {
                "status": "error",
                "stage": "matching",
                "message": "Job matcher returned an invalid response.",
            }

        if match_result.get("status") != "success":
            return {
                "status": "error",
                "stage": "matching",
                "message": (
                    "Could not match the job against "
                    "the career profile."
                ),
                "match": match_result,
            }

        # --------------------------------------------------
        # 4. EXPERIENCE EVALUATION
        # --------------------------------------------------

        experience_result = evaluate_experience(
            profile,
            job,
        )

        # --------------------------------------------------
        # 5. RETURN JOB ANALYSIS
        # --------------------------------------------------

        skills = match_result.get("skills", {})

        return {
            "status": "success",
            "job": job,
            "match": {
                "overall_score": match_result.get(
                    "overall_score"
                ),
                "recommendation": match_result.get(
                    "recommendation"
                ),
                "role_score": match_result.get(
                    "role_score"
                ),
                "location_score": match_result.get(
                    "location_score"
                ),
                "work_mode_score": match_result.get(
                    "work_mode_score"
                ),
                "skills": skills,
            },
            "experience": experience_result,
        }

    except Exception as exc:
        return {
            "status": "error",
            "stage": "career_pipeline",
            "message": str(exc),
        }

# ==========================================================
# CAREER ASSISTANT - RESUME INTAKE
# ==========================================================

@app.post("/career/resume/upload")
async def career_resume_upload(
    file: UploadFile = File(...)
):
    """
    Accept the user's original resume PDF.

    The resume is preserved as the original uploaded file and
    processed through the existing unified media pipeline.

    This endpoint does not generate, tailor, modify, or submit
    a resume.
    """

    try:
        result = await intake_resume(file)

        return result

    except ResumeIntakeError as exc:
        return {
            "status": "error",
            "message": str(exc),
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": f"Resume intake failed: {exc}",
        }


# ==========================================================
# CHAT
# ==========================================================

@app.post("/chat")
async def chat(request: ChatRequest):
    request_started_at = perf_counter()

    session_id = (
        request.session_id.strip()
        if request.session_id
        and request.session_id.strip()
        else "default"
    )

    mode = get_response_mode(request.message)

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
            "For a straightforward question, answer in at most "
            "120 words using 3 to 6 short sentences. "
            "Do not add headings, long examples, or extra sections "
            "unless the user asks for them. "
            "When explaining a concept, give the core idea and, "
            "only if useful, one short example."
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
    # KNOWLEDGE SOURCE DECISION
    # ======================================================

    routing_started_at = perf_counter()

    knowledge_source = detect_knowledge_source(
        request.message
    )

    routing_duration_ms = (
        perf_counter() - routing_started_at
    ) * 1000

    # ======================================================
    # RAG RETRIEVAL
    # ======================================================
    #
    # Only retrieve documents after the user explicitly asks
    # about their own files, notes, report, resume, or project.

    rag_started_at = perf_counter()

    if knowledge_source == "rag":
        retrieved_knowledge = retrieve_relevant_knowledge(
            request.message
        )
    else:
        retrieved_knowledge = []

    rag_duration_ms = (
        perf_counter() - rag_started_at
    ) * 1000

    # ======================================================
    # AGENT PLANNING
    # ======================================================

    plan = create_plan(request.message)

    if (
        plan.get("intent") == "chat"
        and knowledge_source == "web"
    ):
        plan = {
            **plan,
            "intent": "web",
            "action": "search_web",
            "knowledge_source": "web",
        }
    else:
        plan = {
            **plan,
            "knowledge_source": knowledge_source,
        }

    routing_duration_ms = (
        perf_counter() - routing_started_at
    ) * 1000

    print("\n========== KNOWLEDGE ROUTING ==========")
    print("MESSAGE:", request.message)
    print("KNOWLEDGE SOURCE:", knowledge_source)
    print("PLAN:", plan)
    print("RAG RESULTS:", len(retrieved_knowledge))
    print("========================================\n")

    # ======================================================
    # AGENT EXECUTION
    # ======================================================

    execution_started_at = perf_counter()

    execution = await execute_plan(
        plan,
        request.message,
    )

    execution_duration_ms = (
        perf_counter() - execution_started_at
    ) * 1000

    execution_context = build_execution_context(
        execution
    )

    history = get_history(session_id)

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
                + json.dumps(approval_data)
                + "\n\n"
            )

            yield (
                "data: "
                + json.dumps({"type": "done"})
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
        execution.get("status") == "completed"
        and execution.get("action") == "analyze_job"
    ):
        job = execution["job"]

        async def job_stream():
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "job_analysis",
                        "source_url": execution["source_url"],
                        "job": job,
                    }
                )
                + "\n\n"
            )

            yield (
                "data: "
                + json.dumps({"type": "done"})
                + "\n\n"
            )

        return StreamingResponse(
            job_stream(),
            media_type="text/event-stream",
        )
    
    # ======================================================
    # COMPOUND JOB SEARCH + ANALYSIS RESPONSE
    # ======================================================

    steps = execution.get("steps", [])

    analysis_step = next(
        (
            step
            for step in steps
            if step.get("action") == "analyze_jobs"
        ),
        None,
    )

    if analysis_step is not None:

        analysis_result = analysis_step.get(
            "result",
            {},
        )

        if not isinstance(analysis_result, dict):
            analysis_result = {}

        jobs = analysis_result.get("jobs", [])
        failed_jobs = analysis_result.get(
            "failed_jobs",
            [],
        )

        if not isinstance(jobs, list):
            jobs = []

        if not isinstance(failed_jobs, list):
            failed_jobs = []

        async def job_search_analysis_stream():

            # Send one event for every successfully analyzed job.
            for job in jobs:

                if not isinstance(job, dict):
                    continue

                source_url = (
                    job.get("source_url")
                    or job.get("application_url")
                    or job.get("url")
                    or ""
                )

                yield (
                    "data: "
                    + json.dumps(
                        {
                            "type": "job_analysis",
                            "source_url": source_url,
                            "job": job,
                        }
                    )
                    + "\n\n"
                )

            # Send a final summary.
            if jobs:

                summary = (
                    f"Job analysis finished. "
                    f"Successfully analyzed {len(jobs)} job(s)."
                )

                if failed_jobs:
                    summary += (
                        f" {len(failed_jobs)} job(s) "
                        "could not be analyzed."
                    )

            else:

                summary = (
                    "The job search and analysis finished, "
                    "but no jobs were successfully analyzed."
                )

                error = analysis_result.get("error")

                if error:
                    summary += f" Reason: {error}"

            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "job_analysis_summary",
                        "content": summary,
                    }
                )
                + "\n\n"
            )

            yield (
                "data: "
                + json.dumps({"type": "done"})
                + "\n\n"
            )

        return StreamingResponse(
            job_search_analysis_stream(),
            media_type="text/event-stream",
        )


    # ======================================================
    # WEB SEARCH RESULTS
    # ======================================================

    web_context = ""

    if (
        execution.get("status") == "completed"
        and execution.get("action") == "search_web"
    ):
        results = execution.get("results", [])

        if results:
            web_parts = []

            for index, result in enumerate(
                results,
                start=1,
            ):
                title = result.get("title", "")
                url = result.get("url", "")
                content = result.get("content", "")

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

    memory_started_at = perf_counter()

    saved_memory = remember_if_requested(
        request.message
    )

    memories = search_memories(
        request.message,
        limit=5,
    )

    memory_duration_ms = (
        perf_counter() - memory_started_at
    ) * 1000

    if saved_memory:
        already_present = any(
            memory.get("id") == saved_memory.get("id")
            for memory in memories
        )

        if not already_present:
            memories.insert(0, saved_memory)

        memories = memories[:5]

    if memories:
        memory_context = "\n\n".join(
            f"- {memory.get('content', '')}"
            for memory in memories
        )

        personal_memory = (
            "Relevant personal memory:\n"
            f"{memory_context}"
        )
    else:
        personal_memory = ""

    # ======================================================
    # RAG KNOWLEDGE
    # ======================================================

    if knowledge_source == "rag":
        rag_context = build_rag_context(
            retrieved_knowledge
        )
    else:
        rag_context = ""

    # ======================================================
    # SYSTEM PROMPT
    # ======================================================

    system_prompt_parts = [
        (
            "You are My Personal AI, a CSE-focused personal "
            "assistant. Answer accurately and clearly."
        ),
        (
            "Use Markdown only when it makes the answer easier "
            "to read."
        ),
        (
            "For questions about what the user previously said, "
            "decided, preferred, or did, use only the supplied "
            "conversation history and relevant personal memory. "
            "Never invent a previous user statement."
        ),
        instructions[mode],
    ]

    if personal_memory:
        system_prompt_parts.append(
            f"{personal_memory}\n\n"
            "Use personal memory only when relevant. Do not "
            "mention the memory system."
        )

    if rag_context:
        system_prompt_parts.append(
            f"{rag_context}\n\n"
            "Use the supplied document information when it is "
            "relevant. Do not invent facts that are absent from it. "
            "If it is insufficient, say so clearly."
        )

    if web_context:
        system_prompt_parts.append(
            f"{web_context}\n\n"
            "Use supplied web results as the primary source for "
            "current information."
        )

    if execution_context:
        system_prompt_parts.append(
            "Tool results are authoritative. Use them directly.\n\n"
            f"{execution_context}"
        )

    system_prompt = "\n\n".join(system_prompt_parts)

    # ======================================================
    # MESSAGES
    # ======================================================

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    messages.extend(history)

    messages.append(
        {
            "role": "user",
            "content": request.message,
        }
    )

    # ======================================================
    # DEBUG
    # ======================================================

    print("\n========== DEBUG CHAT ==========")
    print("PLAN:", plan)
    print("EXECUTION:", execution)
    print("EXECUTION CONTEXT:", execution_context)
    print("KNOWLEDGE SOURCE:", knowledge_source)
    print("RAG RESULTS:", len(retrieved_knowledge))
    print("================================\n")

    print("\n========== SYSTEM PROMPT SENT TO QWEN ==========")
    print(system_prompt)
    print("========== END SYSTEM PROMPT ==========\n")

    print("\n========== USER MESSAGE SENT TO QWEN ==========")
    print(request.message)
    print("========== END USER MESSAGE ==========\n")

    pre_model_duration_ms = (
        perf_counter() - request_started_at
    ) * 1000

    print("\n========== CHAT TIMING ==========")
    print(f"RAG retrieval: {rag_duration_ms:.1f} ms")
    print(f"Routing and planning: {routing_duration_ms:.1f} ms")
    print(f"Tool execution: {execution_duration_ms:.1f} ms")
    print(f"Memory work: {memory_duration_ms:.1f} ms")
    print(f"Before Ollama: {pre_model_duration_ms:.1f} ms")
    print("=================================\n")

    # ======================================================
    # OLLAMA PAYLOAD
    # ======================================================

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": True,
        "think": False,
        "options": {
            "num_predict": limits[mode],
            "temperature": 0.2,
            "seed": 42,
            "repeat_penalty": 1.15,
        },
    }

    add_message(
        session_id,
        "user",
        request.message,
    )

    # ======================================================
    # STREAM RESPONSE
    # ======================================================

    async def generate():
        full_response = ""
        ollama_started_at = perf_counter()
        first_token_duration_ms = None

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                OLLAMA_URL,
                json=payload,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    data = json.loads(line)

                    content = (
                        data
                        .get("message", {})
                        .get("content", "")
                    )

                    if content:
                        if first_token_duration_ms is None:
                            first_token_duration_ms = (
                                perf_counter() - ollama_started_at
                            ) * 1000

                            print(
                                "Ollama first token: "
                                f"{first_token_duration_ms:.1f} ms"
                            )

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
                        ollama_duration_ms = (
                            perf_counter() - ollama_started_at
                        ) * 1000

                        total_duration_ms = (
                            perf_counter() - request_started_at
                        ) * 1000

                        print(
                            "Ollama generation: "
                            f"{ollama_duration_ms:.1f} ms"
                        )
                        print(
                            "Chat total: "
                            f"{total_duration_ms:.1f} ms"
                        )

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


# ==========================================================
# UNIFIED FILE UPLOAD
# ==========================================================

@app.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...)
):
    """
    Upload and process a supported document, image, audio,
    or video file through the unified media pipeline.
    """

    if not file.filename:
        return {
            "status": "error",
            "message": "No file was selected.",
        }

    from pathlib import Path
    import uuid

    upload_dir = Path("data/uploads")
    upload_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    original_name = Path(file.filename).name
    extension = Path(original_name).suffix.lower()

    if not extension:
        return {
            "status": "error",
            "message": "Uploaded file has no extension.",
        }

    try:
        file_data = await file.read()

        if not file_data:
            return {
                "status": "error",
                "message": "The uploaded file is empty.",
            }

        stored_name = (
            f"{uuid.uuid4().hex}{extension}"
        )

        stored_path = upload_dir / stored_name

        stored_path.write_bytes(file_data)

        try:
            result = process_file(stored_path)

        except MediaProcessingError as exc:
            return {
                "status": "error",
                "file_name": original_name,
                "message": str(exc),
            }

        return {
            "status": "success",
            "message": (
                f"{original_name} was "
                "successfully processed."
            ),
            "file_id": result.get("file_id"),
            "file_name": original_name,
            "file_path": result.get("file_path"),
            "file_type": extension,
            "media_type": result.get("media_type"),
            "processing_status": result.get(
                "processing_status"
            ),
            "processing_method": result.get(
                "processing_method"
            ),
            "rag_document_id": result.get(
                "document_id"
            ),
            "chunks": result.get(
                "total_chunks",
                result.get(
                    "chunks_added",
                    result.get(
                        "chunk_count",
                        0,
                    ),
                ),
            ),
        }

    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
        }

# ==========================================================
# CAREER ASSISTANT - RESUME EXTRACTION
# ==========================================================

@app.post("/career/extract-resume")
async def career_extract_resume(
    request: ResumeExtractionRequest
):
    """
    CA-4: Extract structured information from the
    user's uploaded resume.

    The uploaded original PDF is not modified.

    Extraction uses the existing resume extraction
    pipeline and returns:
        - structured resume data
        - extraction source
        - quality report
        - file metadata

    This endpoint does NOT:
        - modify the original resume
        - tailor the resume
        - fill an application form
        - submit an application
    """

    file_id = request.file_id.strip()

    if not file_id:
        return {
            "status": "error",
            "stage": "resume_extraction_input",
            "message": "Resume file ID is required.",
        }

    try:
        result = await extract_resume(file_id)

    except Exception as exc:
        return {
            "status": "error",
            "stage": "resume_extraction",
            "message": (
                "Resume extraction failed."
            ),
            "details": str(exc),
        }

    if not isinstance(result, dict):
        return {
            "status": "error",
            "stage": "resume_extraction",
            "message": (
                "Resume extractor returned an invalid response."
            ),
        }

    if result.get("status") != "success":
        return {
            "status": "error",
            "stage": "resume_extraction",
            "message": result.get(
                "message",
                result.get(
                    "error",
                    "Could not extract the resume.",
                ),
            ),
            "file_id": file_id,
            "extraction_result": result,
        }

    resume = result.get("resume")

    if not isinstance(resume, dict):
        return {
            "status": "error",
            "stage": "resume_extraction",
            "message": (
                "Resume extraction completed without "
                "valid structured resume data."
            ),
            "file_id": file_id,
        }

    quality = result.get("quality")

    if not isinstance(quality, dict):
        quality = {
            "status": "unknown",
            "can_use_for_application_mapping": False,
            "message": (
                "Resume quality information was not returned."
            ),
            "findings": [],
        }

    return {
        "status": "success",
        "stage": "resume_extraction",
        "file_id": file_id,
        "file_name": result.get("file_name"),
        "file_path": result.get("file_path"),
        "media_type": result.get("media_type"),
        "processing_status": result.get(
            "processing_status"
        ),
        "rag_document_id": result.get(
            "rag_document_id"
        ),
        "extraction_source": result.get(
            "extraction_source"
        ),
        "resume": resume,
        "quality": quality,
        "ready_for_application_mapping": (
            quality.get(
                "can_use_for_application_mapping",
                False,
            )
        ),
    }

@app.post("/career/application-form")
async def career_application_form(
    request: ApplicationFormRequest
):
    """
    CA-2: Detect and inspect the job application form.

    This endpoint:
        - opens the supplied job/application URL
        - detects the application form
        - identifies candidate fields
        - identifies required fields
        - returns application metadata

    This endpoint does NOT:
        - fill any fields
        - upload a resume
        - submit an application
    """

    job_url = request.job_url.strip()

    if not job_url:
        return {
            "status": "error",
            "stage": "application_form_input",
            "message": "Job URL is required.",
        }

    try:
        result = await inspect_application_form(
            job_url
        )

    except Exception as exc:
        return {
            "status": "error",
            "stage": "application_form_detection",
            "message": (
                "Application form detection failed."
            ),
            "details": str(exc),
        }

    if not isinstance(result, dict):
        return {
            "status": "error",
            "stage": "application_form_detection",
            "message": (
                "Application form inspector "
                "returned an invalid response."
            ),
        }

    return result

@app.post("/career/map-application")
async def career_map_application(
    request: ApplicationMappingRequest
):
    """
    CA-5: Build structured application data.

    Inputs:
        - job URL
        - uploaded original resume file ID

    The backend obtains:
        - CA-2 application form inspection
        - CA-4 resume extraction
        - original resume PDF path

    This endpoint does NOT:
        - fill the browser
        - modify the resume
        - submit an application
    """

    job_url = request.job_url.strip()
    resume_file_id = request.resume_file_id.strip()

    if not job_url:
        return {
            "status": "error",
            "stage": "application_mapping_input",
            "message": "Job URL is required.",
        }

    if not resume_file_id:
        return {
            "status": "error",
            "stage": "application_mapping_input",
            "message": "Resume file ID is required.",
        }

    # ---------------------------------------------------------
    # CA-2: Inspect application form
    # ---------------------------------------------------------

    try:
        application_result = (
            await inspect_application_form(
                job_url
            )
        )

    except Exception as exc:
        return {
            "status": "error",
            "stage": "application_form_detection",
            "message": (
                "Application form detection failed."
            ),
            "details": str(exc),
        }

    if not isinstance(
        application_result,
        dict,
    ):
        return {
            "status": "error",
            "stage": "application_form_detection",
            "message": (
                "Application form inspector "
                "returned an invalid response."
            ),
        }

    if application_result.get(
        "status"
    ) != "success":
        return application_result

    print(
        "\n[CA-5 DEBUG] application_result fields:"
    )

    for index, field in enumerate(
        application_result.get("fields", [])
    ):
        print(
            index,
            {
                "id": field.get("id"),
                "name": field.get("name"),
                "label": field.get("label"),
                "type": field.get("type"),
            },
        )

    print(
        "[CA-5 DEBUG] candidate_field_count:",
        application_result.get(
            "candidate_field_count"
        ),
    )

    # ---------------------------------------------------------
    # CA-4: Extract uploaded resume
    # ---------------------------------------------------------

    try:
        resume_extraction_result = (
            await extract_resume(
                resume_file_id
            )
        )

    except Exception as exc:
        return {
            "status": "error",
            "stage": "resume_extraction",
            "message": (
                "Resume extraction failed."
            ),
            "details": str(exc),
        }

    if not isinstance(
        resume_extraction_result,
        dict,
    ):
        return {
            "status": "error",
            "stage": "resume_extraction",
            "message": (
                "Resume extractor returned "
                "an invalid response."
            ),
        }

    if resume_extraction_result.get(
        "status"
    ) != "success":
        return resume_extraction_result

    # ---------------------------------------------------------
    # Recover original resume path
    # ---------------------------------------------------------

    original_resume_file_path = (
        resume_extraction_result.get(
            "file_path"
        )
    )

    # The extraction response may not expose the path.
    # The file registry remains the source of truth.
    if not original_resume_file_path:
        try:
            from app.media.file_registry import (
                get_file_record,
            )

            file_record = get_file_record(
                resume_file_id
            )

        except Exception as exc:
            return {
                "status": "error",
                "stage": "resume_file_lookup",
                "message": (
                    "Could not retrieve the "
                    "original resume from the "
                    "file registry."
                ),
                "details": str(exc),
            }

        if isinstance(
            file_record,
            dict,
        ):
            original_resume_file_path = (
                file_record.get(
                    "file_path"
                )
            )

    if not original_resume_file_path:
        return {
            "status": "error",
            "stage": "resume_file_lookup",
            "message": (
                "Original resume file path "
                "could not be recovered."
            ),
        }

    # ---------------------------------------------------------
    # CA-5: Build structured application data
    # ---------------------------------------------------------

    try:
        result = map_application_fields(
            application_result=(
                application_result
            ),
            resume_extraction_result=(
                resume_extraction_result
            ),
            original_resume_file_path=(
                original_resume_file_path
            ),
        )

    except Exception as exc:
        return {
            "status": "error",
            "stage": "application_mapping",
            "message": (
                "Application field mapping failed."
            ),
            "details": str(exc),
        }

    if not isinstance(
        result,
        dict,
    ):
        return {
            "status": "error",
            "stage": "application_mapping",
            "message": (
                "Application mapper returned "
                "an invalid response."
            ),
        }

    if result.get(
        "status"
    ) != "success":
        return result

    # ---------------------------------------------------------
    # Return CA-5 result
    # ---------------------------------------------------------

    return result