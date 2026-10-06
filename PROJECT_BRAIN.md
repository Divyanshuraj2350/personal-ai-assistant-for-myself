# Personal AI — Project Brain

> **Status:** verified against the local project on 2026-09-15.  
> **Purpose:** this is the single authoritative handoff document for project context, confirmed implementation state, decisions, constraints, and the next investigation. Update this file whenever verified project state changes. Do not create parallel `ROADMAP`, `CONTEXT`, or duplicate handoff files.

## 1. Project vision

Personal AI is a local-first CSE-focused assistant built with FastAPI and a browser frontend. It combines normal Qwen-powered chat, deterministic tools, persistent conversation/personal memory, RAG over user files, current-web lookup, media processing, local voice interaction, Gmail approval flows, and a safety-first Career Assistant.

The user tests changes in VS Code. Before suggesting or making a code change, inspect the relevant live files in this project; pasted snippets and historical context are supporting information, not a substitute for the current codebase.

## 2. Non-negotiable development rules

1. `app/main.py` is the authoritative current integration baseline. Do not replace it with a backup or an old chat version.
2. Preserve the tested response caps in `app/main.py` exactly:
   - `short = 512`
   - `normal = 1024`
   - `detailed = 4096`
3. Keep the normal chat request streaming and keep `think: False` in the Ollama payload unless there is a separately tested, explicitly approved reason to change either.
4. Do not make unrelated changes while diagnosing or implementing a narrowly scoped task.
5. Preserve the original resume. Career resume intake/extraction must not silently rewrite, tailor, fabricate, or substitute facts from `data/career_profile.json`.
6. Never infer work authorization, sponsorship, visa, citizenship, or other legal eligibility details.
7. Job URLs must come from real search/fetch results; never invent links, employers, roles, qualifications, or application data.
8. Sending email and any future external action must remain approval-gated.
9. Reuse existing shared pipelines and storage where appropriate. Do not introduce duplicate parsers, databases, or redundant context files without a demonstrated need.
10. The repository currently contains user work and deliberate backup files. Do not clean, reset, delete, or mass-format it without explicit approval.

## 3. Verified project map

```text
My ai/
├── app/
│   ├── main.py                 # FastAPI integration baseline
│   ├── agent/                  # router, planner, executor, tools, memory, career flow
│   ├── rag/                    # Chroma store, ingestion, retrieval
│   ├── media/                  # unified document/image/audio/video processing
│   └── voice/                  # local Whisper STT and Chatterbox TTS
├── frontend/                   # index.html, app.js, style.css
├── data/                       # sessions, memory, career profile, Chroma, uploads, voice output
├── tests/                      # current pipeline test(s)
├── requirements.txt
├── README.md                   # older/basic project description; this file is the current handoff source
└── PROJECT_BRAIN.md            # this document
```

The repository has one initial commit and substantial uncommitted/in-progress work. That is expected; preserve it.

## 4. Current architecture

```text
Browser / API request
        |
        +-- /chat --------------------------------------------------------+
        |   response-mode -> RAG retrieval -> source routing -> planner  |
        |   -> executor/tool -> history + personal memory -> Qwen3       |
        |   -> SSE streaming response                                     |
        |                                                                  |
        +-- /files/upload -> unified media pipeline -> file registry -> RAG
        |
        +-- /voice/chat -> Whisper.cpp STT -> /chat -> Chatterbox TTS
        |
        +-- /career/analyze -> fetch job -> structured analysis -> profile match
        |                      -> experience evaluation
        |
        +-- /career/resume/upload -> preserve original PDF -> media pipeline
                                     -> file registry + RAG document
```

### Core chat modules

- `app/main.py`: endpoint integration; source of truth for active chat behavior and response limits.
- `app/agent/router.py`: rule-based intent and knowledge-source routing (`chat`, calculation, email, job analysis, job search, social, web; `qwen`, RAG, or web knowledge).
- `app/agent/planner.py`: maps intent to an action plan.
- `app/agent/executor.py`: executes tools, including calculator, web, email approval, job analysis, and job search.
- `app/agent/memory.py`: JSON-backed short-term session history (last 12 messages) and explicit long-term memory.
- `app/rag/store.py`, `ingest.py`, and `retriever.py`: Chroma-backed document retrieval, relevance filtering, ranking, and document-aware expansion.

### Model configuration

- Local model: `qwen3:8b` through Ollama at `http://localhost:11434/api/chat`.
- Normal `/chat` payload is streaming, has `think: False`, and uses temperature `0.2`, seed `42`, repeat penalty `1.15`, plus the protected mode-specific `num_predict` limits.
- Structured job analysis and resume extraction use non-streaming JSON mode with `think: False` and low/zero temperature.

## 5. Completed / working platform capabilities

The following are present in the live codebase and have been exercised during development:

- FastAPI chat API with SSE token streaming and frontend.
- Rule-based intent routing and plans for ordinary chat, calculator, web, email drafting/approval, social draft approval, job analysis, and job search.
- Deterministic calculator path.
- Persistent session history and explicit personal memory.
- RAG ingestion/retrieval for text, PDF, DOCX, image/OCR, audio, and video through the unified media layer.
- File registry and user upload storage.
- Current-web search, cleaning, and relevance filtering.
- Gmail OAuth/status plumbing and approval storage/approval endpoints.
- Local voice flow: Whisper.cpp (large-v3-turbo with optional Silero VAD) for STT; Chatterbox Multilingual v3 via `mlx_audio` with a local reference WAV for TTS. The `/voice/chat` endpoint transcribes, calls the existing chat pipeline, detects Devanagari output for Hindi selection, then synthesizes a WAV.
- Career job analysis endpoint: fetches a supplied job URL, extracts supported structured job data using Qwen JSON output, matches it to the saved career profile, and evaluates experience.
- Career resume intake (CA-3): PDF only, stores the uploaded original, processes it through the existing media/RAG pipeline, and returns `file_id` plus `rag_document_id`.
- Career resume extraction (CA-4, functional but not quality-complete): reads every RAG chunk belonging to exactly the uploaded resume, joins them in chunk order, and asks Qwen for structured JSON. It does not semantic-search only a subset of resume chunks.

## 6. Career Assistant roadmap and state

The Career Assistant is designed to be source-grounded and non-deceptive. The original resume and a saved career profile are related but separate sources.

| Area | Verified state | Notes |
| --- | --- | --- |
| CA-1 / career job intelligence | Working | Job fetch, analysis, matching, and experience evaluation are wired into `/career/analyze`. |
| CA-2 / profile-aware matching | Working | Uses `data/career_profile.json`; must not be treated as a substitute for a particular uploaded resume. |
| CA-3 / resume intake | Complete | `/career/resume/upload` accepts PDF only, preserves the original, processes it through existing media/RAG storage. |
| CA-4 / structured resume extraction | Functionally complete; quality validation pending | `resume_extractor.py` retrieves all chunks via `rag_document_id`, uses `think: False` and `format: "json"`, then normalizes the result. |
| CA-5 / application data mapping | Not yet confirmed complete | Application mapper/form/proposal/validator/filler modules exist, but must be audited and tested against CA-4 before being treated as production-ready. |
| Career UI / explicit resume workflow | Deferred | Do not connect generic `/files/upload` directly to Career resume intake. Career needs its own intentional Resume Upload action. |
| Submission / external application completion | Not authorized/implemented as an automatic action | Must preserve human review and explicit approval. |

### Career workflow

```text
Job URL
  -> fetch_job_page()
  -> analyze_job() [grounded JSON]
  -> load_profile()
  -> match_job_to_profile()
  -> evaluate_experience()

Original resume PDF
  -> /career/resume/upload
  -> resume_intake.intake_resume()
  -> unified media processor + file registry + RAG document
  -> resume_extractor.extract_resume(file_id)
  -> get every chunk for its rag_document_id, in chunk order
  -> Qwen JSON extraction
  -> validation before any application mapping
```

### CA-4 real test and quality issue

An actual uploaded resume passed CA-3 with a file record and six RAG chunks. CA-4 then successfully returned a structured object. However, the extracted PDF text had character corruption such as `Ins7tute`, `Pra7nik`, `PlaGorm`, `OperaWng`, and duplicated/garbled responsibility lines. Qwen preserved some of that corruption.

Therefore, CA-4 is **not** ready to feed application mapping blindly. Next Career work must add a source-grounded extraction-quality validation/correction step. It must be traceable to the uploaded resume; do not manually edit extracted JSON and present it as source-derived, and do not use profile fallback to fill missing fields.

### Job Finder status

- Router detects job-search language and routes it to `search_jobs`.
- `app/agent/job_search.py` derives role/location preferences, chooses relevant profile skills, builds targeted web queries, filters obvious non-job results, deduplicates URLs, ranks likely individual postings, and returns real result URLs.
- Supporting modules include job fetcher, verifier, analyzer, matcher, experience evaluator, application proposal/form/mapper/validator/filler.
- The full application-mapping/filling chain needs a fresh code audit and end-to-end test after CA-4 quality validation; do not claim it is complete merely because modules exist.

## 7. Current latency investigation — immediate priority

The user explicitly asked to pause feature work and solve slow normal-chat responses. Do **not** reduce the 512/1024/4096 response limits as a shortcut.

### Measurements already obtained

For a simple binary-search request:

- Direct Ollama call with `think: False`: about **23.4 seconds** in one benchmark, with roughly **22.2 seconds** spent generating 452 tokens.
- Full `/chat`: about **29.3 seconds**.
- Therefore roughly **6 seconds** is added by the agent pipeline, while most of the elapsed time is Qwen generation/output length.
- A tiny JSON direct API test with `think: False` completed in about **2.46 seconds** for 14 output tokens. The earlier equivalent call with thinking enabled took about **32 seconds** and emitted 241 thinking/output tokens. This validates that disabling thinking is important and already correctly applied in the current `/chat` payload.

### Confirmed code path contributing avoidable work

`app/main.py` currently does the following for every `/chat` request before choosing a source:

1. Calls `retrieve_relevant_knowledge(request.message)`.
2. Passes any results into `detect_knowledge_source()`; any non-empty relevant result can cause RAG selection.
3. Creates and executes a plan, even for ordinary chat.
4. Searches persistent long-term memory for every request.

`retrieve_relevant_knowledge()` queries Chroma for up to 30 candidates, ranks them, and may expand an entire matched document through `get_document_chunks()`. This is potentially expensive and can also cause a normal question to be treated as RAG-backed simply because semantic retrieval found a result.

`memory.py` uses JSON files for session and long-term memory; it performs disk reads/writes/search operations in the regular request path.

### Required diagnostic order

1. Add timing instrumentation only (no behavior change) around RAG retrieval, source routing/planning/execution, memory search, Ollama first-token time, and total generation time.
2. Repeat the same controlled simple request through direct Ollama and `/chat`; record generated token count and all phase timings.
3. If confirmed, design the smallest safe routing change so ordinary chat does not perform RAG retrieval/document expansion by default. RAG should run for explicit personal-document requests, or after a deliberately chosen lightweight routing decision—not merely because an always-run retrieval happened to return a match.
4. Evaluate whether memory search can be gated to explicit memory/history/relevant-personal questions, without breaking the explicit-memory feature.
5. Keep streaming enabled, preserve the protected limits, and test relevant RAG, web, calculator, and memory cases after any optimization.

Do not claim the cause is fully proven until instrumented timings are captured on the live system. The current evidence supports two contributors: unnecessary pipeline work (~6 seconds in the benchmark) and a large Qwen response for simple prompts.

## 8. Known issues, cautions, and deferred cleanup

- Resume text extraction quality can be corrupted even when `processing_method` is `pdf_text`; CA-4 needs grounded validation before downstream use.
- The Hugging Face unauthenticated warning observed during extraction is not the root cause of the successful extraction flow, but it may affect download rate limits when a model is not already cached.
- Existing `main.py` emits extensive debug/system-prompt logging. This is useful for diagnosis but may be noisy and can expose user context in local logs; review it later as a scoped privacy/observability task, not during unrelated work.
- `app/main.py` has named backups (`main_backup.py`, `main_before_career_cleanup.py`) and Career modules have several backup variants. They are historical safety copies, not current baselines.
- Old resume-generation/tailoring modules and associated tests are deleted in the working tree. Do not restore them unless there is an explicit product decision.
- Security cleanup and secret/configuration audit remain pending. Do not print credentials, OAuth tokens, reference-audio personal data, or uploaded-resume contents unnecessarily.
- The generic file-upload UX and the Career resume-upload workflow intentionally remain separate.

## 9. Important files for future work

- `app/main.py` — routes, integration, protected response modes, chat pipeline.
- `app/agent/router.py` — intent and source-routing policy.
- `app/agent/planner.py`, `app/agent/executor.py`, `app/agent/tools.py` — tool dispatch.
- `app/agent/memory.py` — persistent session/personal memory.
- `app/rag/retriever.py`, `app/rag/store.py` — RAG behavior and document chunk access.
- `app/media/processor.py`, `app/media/document_processor.py`, `app/media/file_registry.py` — unified media and registration path.
- `app/voice/stt.py`, `app/voice/tts.py` — local voice configuration.
- `app/agent/job_fetcher.py`, `job_analyzer.py`, `job_matcher.py`, `experience_evaluator.py`, `job_search.py` — current Career/Job Finder core.
- `app/agent/resume_intake.py`, `resume_extractor.py` — CA-3 and CA-4.
- `app/agent/application_*.py` — application workflow components; audit before relying on their status.
- `frontend/index.html`, `frontend/app.js`, `frontend/style.css` — existing UI.

## 10. Handoff protocol

For every new task:

1. Read this document first.
2. Inspect the exact live files relevant to the task and check `git status` before editing.
3. State what is verified versus what is only historical context.
4. Make the smallest coherent change that satisfies the request.
5. Run focused checks/tests appropriate to the change and record material changes in this document.
6. Do not overwrite user changes, restore backups, or change protected response limits without explicit approval.

## 11. Next task

**Immediate next task: instrument and measure normal-chat latency in the current live `/chat` pipeline.**

Deliverable: a small, reversible diagnostic change or a measurement plan that reports phase timings for a controlled normal query, followed by evidence-based recommendations. No response-limit reduction, model replacement, broad refactor, or unrelated Career feature work belongs in that task.
