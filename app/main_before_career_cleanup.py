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

from app.media.processor import (
    process_file,
    MediaProcessingError,
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

    if len(message) > 180 or any(
        word in text for word in detailed_words
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
# CHAT
# ==========================================================

@app.post("/chat")
async def chat(request: ChatRequest):
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
    # RAG RETRIEVAL
    # ======================================================

    retrieved_knowledge = retrieve_relevant_knowledge(
        request.message
    )

    # ======================================================
    # KNOWLEDGE SOURCE DECISION
    # ======================================================

    knowledge_source = detect_knowledge_source(
        request.message,
        rag_results=retrieved_knowledge,
    )

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

    print("\n========== KNOWLEDGE ROUTING ==========")
    print("MESSAGE:", request.message)
    print("KNOWLEDGE SOURCE:", knowledge_source)
    print("PLAN:", plan)
    print("RAG RESULTS:", len(retrieved_knowledge))
    print("========================================\n")

    # ======================================================
    # AGENT EXECUTION
    # ======================================================

    execution = await execute_plan(
        plan,
        request.message,
    )

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

    saved_memory = remember_if_requested(
        request.message
    )

    memories = search_memories(
        request.message,
        limit=5,
    )

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

    if knowledge_source == "rag":
        rag_context = build_rag_context(
            retrieved_knowledge
        )
    else:
        rag_context = ""

    # ======================================================
    # SYSTEM PROMPT
    # ======================================================

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

        # --------------------------------------------------
        # RAG GROUNDING
        # --------------------------------------------------

        "When retrieved knowledge from the user's uploaded "
        "documents is provided below, treat that retrieved "
        "knowledge as available information that you can "
        "read and use. "

        "The uploaded document information may come from "
        "PDFs, images, audio, video, or other supported files. "

        "If the user's question can be answered from the "
        "retrieved knowledge, answer it directly using that "
        "knowledge. "

        "Do not say that you cannot access the user's device, "
        "files, images, audio, video, or personal data when "
        "the relevant information is explicitly present in "
        "the retrieved knowledge below. "

        "For example, if retrieved knowledge contains screen "
        "time values from an uploaded screenshot, use those "
        "values directly to answer the question. "

        "Do not invent facts that are not present in the "
        "retrieved knowledge. "

        "If the retrieved knowledge genuinely does not "
        "contain the requested information, clearly say that "
        "the available document information is insufficient. "

        # --------------------------------------------------
        # WEB GROUNDING
        # --------------------------------------------------

        "When current web search results are provided, "
        "use them as the primary source for current or "
        "time-sensitive information. "

        "Do not claim that you lack web access when "
        "search results are provided. "

        f"{instructions[mode]}"

        f"{personal_memory}"
        f"{rag_context}"
        f"{web_context}"

        # --------------------------------------------------
        # TOOL RESULTS
        # --------------------------------------------------

        "Tool results are authoritative. "

        "When a tool has already produced a result, "
        "use that result directly. "

        "Do not replace a tool result with code, "
        "an unevaluated expression, or a different "
        "calculation. "

        "For calculator results, return the numerical "
        "result directly. "

        f"{execution_context}"
    )

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
