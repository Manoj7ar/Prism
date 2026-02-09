from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse
from pydantic import BaseModel
import uvicorn
import asyncio
import os
import shutil
import json
import logging
import time
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from google.genai import types
from agent.prism_client import PrismClient
from agent.task_planner import TaskPlanner
from agent.executor import TaskExecutor
from agent.context_detector import ContextDetector
from agent.session_recorder import SessionRecorder
from agent.orchestrator import IntentOrchestrator
from agent.ide_delegator import IDEDelegator
from agent.memory import memory_system
from automation.visual_dom import VisualDOM
from config import HOST, PORT, DEBUG, GEMINI_MODEL, CORS_ORIGINS

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PrismBackend")

app = FastAPI(title="Prism Agent Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thinking & Screenshot Queues
thinking_queue = asyncio.Queue()
screenshot_queue = asyncio.Queue()

async def emit_thought(thought: str, type: str = "thought"):
    """Helper to push a thought to the queue and log it"""
    await thinking_queue.put({"type": type, "content": thought})

async def notify_screenshot():
    """Notify when a screenshot is taken"""
    await screenshot_queue.put({"type": "screenshot", "timestamp": time.time()})

# Initialize components
prism_client = PrismClient(model_id=GEMINI_MODEL, thought_callback=emit_thought)
task_planner = TaskPlanner(prism_client)
orchestrator = IntentOrchestrator(prism_client)
ide_delegator = IDEDelegator(prism_client)
executor = TaskExecutor(prism_client)
context_detector = ContextDetector()
visual_dom_instance = VisualDOM(prism_client)
session_recorder = SessionRecorder(
    interval=15, 
    redactor=executor.privacy, 
    on_screenshot=notify_screenshot,
    get_metadata=context_detector.get_active_window_info
)

# Global status
is_visible = False
current_task_status = []
current_execution_task = None
current_stream_task = None
attached_file_context = None  # Stores {"path": str, "name": str} for user-attached files
fast_mode_enabled = True

SETTINGS_FILE = Path(__file__).parent / "session_memory" / "app_settings.json"

def _load_app_settings() -> Dict[str, Any]:
    defaults = {"fast_mode_enabled": True}
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {**defaults, **data}
    except Exception as e:
        logger.warning(f"Failed to load app settings: {e}")
    return defaults

def _save_app_settings() -> None:
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"fast_mode_enabled": fast_mode_enabled}, f)
    except Exception as e:
        logger.warning(f"Failed to save app settings: {e}")

def _extract_fast_open_app(command: str) -> Optional[str]:
    """Return app name for simple open/launch/start commands suitable for fast-path execution."""
    text = (command or "").strip()
    if not text:
        return None

    lower = text.lower()
    if any(token in lower for token in [" and ", " then ", ",", ";"]):
        return None

    match = re.match(r"^(open|launch|start)\s+(?:the\s+)?(?:app(?:lication)?\s+)?(.+?)\s*$", text, flags=re.IGNORECASE)
    if not match:
        return None

    app_name = match.group(2).strip()
    return app_name or None

def _is_screen_summary_command(command: str) -> bool:
    """Detect direct user intent to summarize currently visible screen/page."""
    text = (command or "").strip().lower()
    if not text:
        return False

    # Normalize trailing punctuation/whitespace
    text = re.sub(r"[\s\.\!\?]+$", "", text)

    direct_phrases = {
        "summarize",
        "summarise",
        "summarize this",
        "summarise this",
        "summarize this screen",
        "summarise this screen",
        "summarize screen",
        "summarise screen",
        "summarize this page",
        "summarise this page",
        "summarize page",
        "summarise page",
    }
    if text in direct_phrases:
        return True

    return bool(re.match(r"^(please\s+)?summari[sz]e\s+(this|this screen|this page|screen|page)$", text))

def _is_fast_chat_command(command: str) -> bool:
    """Detect question/chat prompts that do not require automation planning."""
    text = (command or "").strip()
    if not text:
        return False

    lower = text.lower()

    # Keep automation and summary commands on the normal execution path.
    automation_signals = [
        "open ", "launch ", "start ", "click", "type ", "scroll", "press ", "navigate",
        "turn on", "turn off", "enable", "disable", "switch ", "close ", "minimize",
        "maximize", "drag", "drop", "send ", "attach", "upload", "download", "summari",
    ]
    if any(sig in lower for sig in automation_signals):
        return False

    question_starts = (
        "what", "why", "how", "when", "where", "who", "which", "can you", "could you",
        "would you", "explain", "tell me", "help me", "describe", "compare", "review",
    )
    return text.endswith("?") or lower.startswith(question_starts)

def _is_contextual_question(command: str) -> bool:
    text = (command or "").strip().lower()
    if not text:
        return False
    context_phrases = [
        "what can this do",
        "what is this",
        "what am i looking at",
        "what's on the screen",
        "what is on the screen",
        "what's on this page",
        "what is on this page",
        "what's this page",
        "what is this page",
        "unique features",
        "what features",
        "what does this do",
        "what can i do here",
        "what is on my screen",
        "what can this app do",
        "tell me more",
    ]
    if any(p in text for p in context_phrases):
        return True
    # Any question that refers to "this" or "screen/page" likely needs context.
    return (text.endswith("?") and ("this" in text or "screen" in text or "page" in text))

def _normalize_browser_url(target: str) -> Optional[str]:
    value = (target or "").strip().lower()
    if not value:
        return None

    known_sites = {
        "spotify": "https://open.spotify.com",
        "youtube": "https://www.youtube.com",
        "gmail": "https://mail.google.com",
        "google": "https://www.google.com",
        "netflix": "https://www.netflix.com",
        "twitter": "https://x.com",
        "x": "https://x.com",
        "linkedin": "https://www.linkedin.com",
        "github": "https://github.com",
    }
    if value in known_sites:
        return known_sites[value]

    if value.startswith("http://") or value.startswith("https://"):
        return value

    # e.g. "spotify.com" or "open.spotify.com"
    if "." in value and " " not in value:
        return f"https://{value}"

    # fallback: search-like phrase is not deterministic website navigation
    return None

def _extract_browser_navigation_intent(command: str) -> Optional[Dict[str, str]]:
    text = (command or "").strip()
    if not text:
        return None

    # Deterministic pattern:
    # "open chrome and go to spotify"
    # "launch browser then navigate to youtube.com"
    pattern = re.compile(
        r"^(open|launch|start)\s+"
        r"(chrome|google chrome|edge|microsoft edge|msedge|firefox|brave|browser|web browser)\s+"
        r"(?:and|then)\s+"
        r"(?:go to|navigate to|visit|open)\s+(.+?)\s*$",
        flags=re.IGNORECASE
    )
    match = pattern.match(text)
    if not match:
        return None

    browser_raw = match.group(2).strip().lower()
    target_raw = match.group(3).strip().rstrip(".!?")

    browser_map = {
        "google chrome": "chrome",
        "chrome": "chrome",
        "browser": "chrome",
        "web browser": "chrome",
        "edge": "edge",
        "microsoft edge": "edge",
        "msedge": "edge",
        "firefox": "firefox",
        "brave": "brave",
    }
    browser = browser_map.get(browser_raw, "chrome")
    url = _normalize_browser_url(target_raw)
    if not url:
        return None

    return {"browser": browser, "url": url, "target": target_raw}

def _is_file_summary_to_google_doc_command(command: str, has_file: bool) -> bool:
    if not has_file:
        return False

    text = (command or "").strip().lower()
    if not text:
        return False

    has_summary_intent = any(token in text for token in ["summarize", "summarise", "summary"])
    has_google_doc_intent = (
        "google doc" in text
        or "google docs" in text
        or "google document" in text
        or "google documents" in text
        or "gdoc" in text
        or "docs.new" in text
        or "doc.new" in text
        or "new doc" in text
        or ("google" in text and "doc" in text)
    )
    has_write_intent = any(token in text for token in ["paste", "write", "put", "insert"])

    return has_summary_intent and has_google_doc_intent and has_write_intent

def _sanitize_summary_text(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    cleaned = cleaned.replace("**", "")
    cleaned = cleaned.replace("#", "")
    cleaned = cleaned.replace("—", "-")
    cleaned = cleaned.replace("–", "-")
    cleaned = cleaned.replace("•", "-")
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()

def _extract_whatsapp_file_send_intent(command: str, has_file: bool) -> Optional[Dict[str, str]]:
    if not has_file:
        return None

    text = (command or "").strip()
    lower = text.lower()
    if not text:
        return None

    has_whatsapp = ("whatsapp" in lower) or ("what's app" in lower) or ("whats app" in lower)
    has_send = any(token in lower for token in ["send", "share", "forward"])
    if not (has_whatsapp and has_send):
        return None

    recipient = ""
    patterns = [
        r"\bto\s+(.+?)\s+on\s+whats?app\b",
        r"\bto\s+(.+?)\s+in\s+whats?app\b",
        r"\bto\s+(.+?)$",
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            recipient = m.group(1).strip()
            break

    recipient = re.sub(r"\s+", " ", recipient)
    recipient = re.sub(r"\b(on|in)\s+whats?app\b", "", recipient, flags=re.IGNORECASE).strip()
    recipient = recipient.strip(" .,!?:;\"'")
    if not recipient:
        return None

    return {"recipient": recipient}

class GenericResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None

class PresetRequest(BaseModel):
    steps: List[str]
    history: Optional[List[Dict[str, Any]]] = None

class FastModeRequest(BaseModel):
    enabled: bool

@app.on_event("startup")
async def startup_event():
    global fast_mode_enabled
    settings = _load_app_settings()
    fast_mode_enabled = bool(settings.get("fast_mode_enabled", True))
    await session_recorder.start()
    logger.info("Session Recorder started.")

@app.on_event("shutdown")
async def shutdown_event():
    await session_recorder.stop()
    await executor.close()

@app.get("/screenshot/events")
async def screenshot_events():
    async def event_generator():
        while True:
            try:
                data = await screenshot_queue.get()
                yield f"data: {json.dumps(data)}\n\n"
            except asyncio.CancelledError:
                break
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/thinking/events")
async def thinking_events():
    async def event_generator():
        while True:
            try:
                data = await thinking_queue.get()
                yield f"data: {json.dumps(data)}\n\n"
            except asyncio.CancelledError:
                break
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/visibility", response_model=GenericResponse)
async def set_visibility(request: Dict[str, bool]):
    global is_visible
    is_visible = request.get("visible", True)
    if is_visible:
        session_recorder.resume()
    else:
        session_recorder.pause()
    return {"success": True}

@app.get("/tasks")
async def get_tasks():
    return {"tasks": current_task_status}

class AuthRequest(BaseModel):
    key: str

@app.post("/set-key", response_model=GenericResponse)
async def set_api_key(request: AuthRequest):
    from config import save_key
    
    # Test key validity
    if prism_client.reinitialize(request.key):
        # Allow a simple test call
        try:
            await prism_client.client.aio.models.generate_content(
                model=prism_client.model_id, 
                contents="Test",
                config=types.GenerateContentConfig(tools=[]) # No tools for quick test
            )
            save_key(request.key)
            return {"success": True, "message": "Key saved and verified"}
        except Exception as e:
             return {"success": False, "error": f"Invalid Key: {str(e)}"}
    return {"success": False, "error": "Failed to initialize client"}

@app.get("/check-auth")
async def check_auth():
    return {"authenticated": prism_client.client is not None}

@app.get("/settings")
async def get_settings():
    return {
        "success": True,
        "fast_mode_enabled": fast_mode_enabled
    }

@app.post("/settings/fast-mode")
async def set_fast_mode(request: FastModeRequest):
    global fast_mode_enabled
    fast_mode_enabled = bool(request.enabled)
    _save_app_settings()
    return {
        "success": True,
        "fast_mode_enabled": fast_mode_enabled
    }

@app.get("/session/status")
async def session_status():
    status = session_recorder.get_status()
    history = session_recorder.get_history()
    return {
        **status,
        "recent_frames": len(history),
        "latest_frame": history[-1] if history else None
    }

@app.post("/execute")
async def execute_command(command: str = Form(...), history: Optional[str] = Form(None)):
    """Non-streaming execution endpoint for simple IPC callers."""
    try:
        parsed_history = json.loads(history) if history else []
    except Exception:
        parsed_history = []

    try:
        result = await run_execution(command, history=parsed_history)
        return {
            "success": result.get("success", False),
            "results": result.get("results", []),
            "reply": result.get("reply")
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/execute-stream")
async def execute_command_stream(
    command: str = Form(...),
    file: Optional[UploadFile] = File(None),
    history: Optional[str] = Form(None)
):
    async def stream_generator():
        global current_task_status, attached_file_context, current_stream_task
        current_stream_task = asyncio.current_task()
        
        executor.reset_stop()
        
        if not prism_client.client:
            yield f"data: {json.dumps({'type': 'error', 'code': 'MISSING_KEY', 'content': 'API Key not set'})}\n\n"
            return

        try:
            current_task_status = []
            parsed_history = json.loads(history) if history else []
            
            file_path = None
            if file:
                os.makedirs("temp", exist_ok=True)
                file_path = os.path.abspath(f"temp/{file.filename}")
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                attached_file_context = {"path": file_path, "name": file.filename}
            
            executor.set_attached_file(attached_file_context)

            # FAST PATH: direct Q&A without automation planning.
            if fast_mode_enabled and _is_fast_chat_command(command) and not file_path:
                # Contextual questions should use a fresh screenshot and screen analysis.
                if _is_contextual_question(command):
                    await emit_thought("Analyzing the current screen for context...")
                    try:
                        os.makedirs("temp", exist_ok=True)
                        context_path = os.path.abspath("temp/context_question.png")
                        await executor.capture_and_redact(context_path)
                        screen_summary = await prism_client.summarize_page_state(context_path)
                        if os.path.exists(context_path):
                            os.remove(context_path)
                    except Exception:
                        screen_summary = ""

                    prompt = (
                        "Answer the user's question using the on-screen context. "
                        "Be concise and specific to what is visible. "
                        "If it looks like a product page, explain what the product is, key features, price cues, and what it's for. "
                        "If it looks like a news or article page, summarize the story and key points. "
                        "Avoid markdown formatting, bullets, or special symbols.\n\n"
                        f"User: {command}"
                    )
                    reply = await prism_client.generate_content(prompt, context_text=screen_summary or None)
                    reply = _sanitize_summary_text(reply)
                    yield f"data: {json.dumps({'type': 'reply_start'})}\n\n"
                    yield f"data: {json.dumps({'type': 'reply_chunk', 'content': reply})}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'results': [{'action': 'reply', 'success': True, 'output': reply}]})}\n\n"
                    return

                yield f"data: {json.dumps({'type': 'reply_start'})}\n\n"

                history_lines = []
                for item in parsed_history[-4:]:
                    role = item.get("role", "user")
                    content = item.get("content", "")
                    if content:
                        history_lines.append(f"{role.upper()}: {content}")
                history_text = "\n".join(history_lines)

                chat_prompt = (
                    "You are Prism. Answer the user quickly and clearly. "
                    "Prefer concise responses unless detail is requested.\n\n"
                    f"Recent chat:\n{history_text}\n\n"
                    f"User: {command}"
                )

                assembled = ""
                async for chunk in prism_client.generate_content_stream(chat_prompt):
                    if executor.should_stop:
                        yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                        return
                    assembled += chunk
                    yield f"data: {json.dumps({'type': 'reply_chunk', 'content': chunk})}\n\n"

                assembled = _sanitize_summary_text(assembled)
                yield f"data: {json.dumps({'type': 'done', 'results': [{'action': 'reply', 'success': True, 'output': assembled}]})}\n\n"
                return

            context = context_detector.get_context()
            visual_history = session_recorder.get_history()
            
            yield f"data: {json.dumps({'type': 'thought', 'content': 'Analyzing system context...'})}\n\n"
            
            if executor.should_stop:
                yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                return

            # FAST PATH: simple app-launch command should not pay orchestration+planning latency.
            fast_open_app = _extract_fast_open_app(command)
            if fast_open_app and not file_path:
                await emit_thought(f"Fast launching {fast_open_app}...")
                tasks = [
                    {"action": "open_app", "params": {"app_name": fast_open_app}, "description": f"Opening {fast_open_app}"},
                    {"action": "reply", "params": {"message": f"Done! Opened {fast_open_app}."}, "description": "Task complete"}
                ]

                local_status = [
                    {"id": f"s_{idx}", "label": t.get('description', t.get('action')), "status": "pending"}
                    for idx, t in enumerate(tasks)
                ]
                current_task_status = local_status
                yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                results = []
                for idx, task in enumerate(tasks):
                    if executor.should_stop:
                        yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                        return

                    local_status[idx]['status'] = 'in_progress'
                    current_task_status = local_status
                    yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                    if task.get('action') == 'reply':
                        results.append({"action": "reply", "success": True, "output": task.get('params', {}).get('message', '')})
                        local_status[idx]['status'] = 'completed'
                    else:
                        try:
                            res = await executor.execute_with_retry(task, local_status, idx)
                            results.append(res)
                        except Exception as e:
                            results.append({"action": task.get('action'), "success": False, "error": str(e)})

                    current_task_status = local_status
                    yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                yield f"data: {json.dumps({'type': 'reply_start'})}\n\n"
                message = f"Done! Opened {fast_open_app}."
                yield f"data: {json.dumps({'type': 'reply_chunk', 'content': message})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'results': results})}\n\n"
                return

            # STRICT PATH: browser launch + website navigation with deterministic steps.
            browser_nav = _extract_browser_navigation_intent(command)
            if browser_nav and not file_path:
                browser_name = browser_nav["browser"]
                target_url = browser_nav["url"]
                target_label = browser_nav["target"]
                await emit_thought(f"Opening {browser_name} and navigating to {target_label}...")

                tasks = [
                    {"action": "open_app", "params": {"app_name": browser_name}, "description": f"Opening {browser_name}"},
                    {"action": "wait", "params": {"seconds": 1.4}, "description": "Waiting for browser"},
                    {"action": "navigate_url", "params": {"url": target_url, "browser_name": browser_name}, "description": f"Navigating to {target_url}"},
                    {"action": "reply", "params": {"message": f"Done! Opened {browser_name} and navigated to {target_label}."}, "description": "Task complete"},
                ]

                local_status = [
                    {"id": f"s_{idx}", "label": t.get('description', t.get('action')), "status": "pending"}
                    for idx, t in enumerate(tasks)
                ]
                current_task_status = local_status
                yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                results = []
                sanitized_summary = None
                for idx, task in enumerate(tasks):
                    if executor.should_stop:
                        yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                        return

                    local_status[idx]['status'] = 'in_progress'
                    current_task_status = local_status
                    yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                    if task.get('action') == 'reply':
                        results.append({"action": "reply", "success": True, "output": task.get('params', {}).get('message', '')})
                        local_status[idx]['status'] = 'completed'
                    else:
                        try:
                            if task.get('action') == 'type_previous_result' and sanitized_summary:
                                # Replace with sanitized text paste
                                replacement = {"action": "type_text", "params": {"text": sanitized_summary}, "description": "Pasting summary into document"}
                                res = await executor.execute_with_retry(replacement, local_status, idx)
                            else:
                                res = await executor.execute_with_retry(task, local_status, idx)
                            results.append(res)
                            if task.get('action') == 'read_and_summarize_files' and res.get('success'):
                                summary_text = res.get('output') or ""
                                sanitized_summary = _sanitize_summary_text(str(summary_text))
                        except Exception as e:
                            results.append({"action": task.get('action'), "success": False, "error": str(e)})

                    current_task_status = local_status
                    yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                yield f"data: {json.dumps({'type': 'done', 'results': results})}\n\n"
                return

            # STRICT PATH: summarize attached file and paste into a brand new Google Doc.
            if _is_file_summary_to_google_doc_command(command, bool(file_path)):
                await emit_thought("Summarizing attached file and opening a new Google Doc...")

                tasks = [
                    {"action": "read_and_summarize_files", "params": {"file_paths": [file_path]}, "description": "Summarizing attached file"},
                    {"action": "open_app", "params": {"app_name": "chrome"}, "description": "Opening Chrome"},
                    {"action": "wait", "params": {"seconds": 1.4}, "description": "Waiting for browser"},
                    {"action": "navigate_url", "params": {"url": "https://docs.new", "browser_name": "chrome"}, "description": "Opening a new Google Doc"},
                    {"action": "wait", "params": {"seconds": 1.4}, "description": "Waiting for document editor"},
                    {"action": "type_previous_result", "params": {}, "description": "Pasting summary into document"},
                    {"action": "reply", "params": {"message": "Done! I summarized the attached file and added it to a new Google Doc."}, "description": "Task complete"},
                ]

                local_status = [
                    {"id": f"s_{idx}", "label": t.get('description', t.get('action')), "status": "pending"}
                    for idx, t in enumerate(tasks)
                ]
                current_task_status = local_status
                yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                results = []
                for idx, task in enumerate(tasks):
                    if executor.should_stop:
                        yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                        return

                    local_status[idx]['status'] = 'in_progress'
                    current_task_status = local_status
                    yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                    if task.get('action') == 'reply':
                        results.append({"action": "reply", "success": True, "output": task.get('params', {}).get('message', '')})
                        local_status[idx]['status'] = 'completed'
                    else:
                        try:
                            res = await executor.execute_with_retry(task, local_status, idx)
                            results.append(res)
                        except Exception as e:
                            results.append({"action": task.get('action'), "success": False, "error": str(e)})

                    current_task_status = local_status
                    yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                yield f"data: {json.dumps({'type': 'reply_start'})}\n\n"
                message = "Summary pasted into a new Google Doc."
                yield f"data: {json.dumps({'type': 'reply_chunk', 'content': message})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'results': results})}\n\n"
                return

            # STRICT PATH: send attached file to a WhatsApp contact.
            whatsapp_send = _extract_whatsapp_file_send_intent(command, bool(file_path))
            if whatsapp_send and file_path:
                recipient = whatsapp_send["recipient"]
                await emit_thought(f"Sending attached file to {recipient} on WhatsApp...")

                tasks = [
                    {"action": "open_app", "params": {"app_name": "chrome"}, "description": "Opening Chrome"},
                    {"action": "wait", "params": {"seconds": 1.4}, "description": "Waiting for browser"},
                    {"action": "navigate_url", "params": {"url": "https://web.whatsapp.com", "browser_name": "chrome"}, "description": "Opening WhatsApp Web"},
                    {"action": "wait", "params": {"seconds": 2.0}, "description": "Waiting for WhatsApp"},
                    {"action": "visual_click", "params": {"element": "Search or start new chat input"}, "description": "Clicking search"},
                    {"action": "wait", "params": {"seconds": 0.6}, "description": "Waiting for search input"},
                    {"action": "type_text", "params": {"text": recipient}, "description": f"Typing contact: {recipient}"},
                    {"action": "wait", "params": {"seconds": 1.0}, "description": "Waiting for contact results"},
                    {"action": "visual_click", "params": {"element": f"{recipient} contact in results"}, "description": f"Selecting {recipient}"},
                    {"action": "wait", "params": {"seconds": 0.8}, "description": "Waiting for chat to open"},
                    {"action": "visual_click", "params": {"element": "Attach or plus icon"}, "description": "Opening attachment menu"},
                    {"action": "wait", "params": {"seconds": 0.7}, "description": "Waiting for attachment menu"},
                    {"action": "visual_click", "params": {"element": "Document option"}, "description": "Selecting document upload"},
                    {"action": "wait", "params": {"seconds": 0.9}, "description": "Waiting for file picker"},
                    {"action": "attach_file", "params": {"method": "dialog"}, "description": "Selecting attached file"},
                    {"action": "wait", "params": {"seconds": 1.2}, "description": "Waiting for file preview"},
                    {"action": "visual_click", "params": {"element": "Send button"}, "description": "Sending file"},
                    {"action": "reply", "params": {"message": f"Done! I sent the attached file to {recipient} on WhatsApp."}, "description": "Task complete"},
                ]

                local_status = [
                    {"id": f"s_{idx}", "label": t.get('description', t.get('action')), "status": "pending"}
                    for idx, t in enumerate(tasks)
                ]
                current_task_status = local_status
                yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                results = []
                for idx, task in enumerate(tasks):
                    if executor.should_stop:
                        yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                        return

                    local_status[idx]['status'] = 'in_progress'
                    current_task_status = local_status
                    yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                    if task.get('action') == 'reply':
                        results.append({"action": "reply", "success": True, "output": task.get('params', {}).get('message', '')})
                        local_status[idx]['status'] = 'completed'
                    else:
                        try:
                            res = await executor.execute_with_retry(task, local_status, idx)
                            results.append(res)
                        except Exception as e:
                            results.append({"action": task.get('action'), "success": False, "error": str(e)})

                    current_task_status = local_status
                    yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                yield f"data: {json.dumps({'type': 'reply_start'})}\n\n"
                message = f"Done! I sent the attached file to {recipient} on WhatsApp."
                yield f"data: {json.dumps({'type': 'reply_chunk', 'content': message})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'results': results})}\n\n"
                return

            # FAST PATH: explicit "summarise this" screen summary requests.
            if _is_screen_summary_command(command) and not file_path:
                await emit_thought("Capturing screen and summarizing...")
                tasks = [
                    {"action": "summarize", "params": {}, "description": "Summarizing current screen"}
                ]

                local_status = [
                    {"id": f"s_{idx}", "label": t.get('description', t.get('action')), "status": "pending"}
                    for idx, t in enumerate(tasks)
                ]
                current_task_status = local_status
                yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                results = []
                for idx, task in enumerate(tasks):
                    if executor.should_stop:
                        yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                        return

                    local_status[idx]['status'] = 'in_progress'
                    current_task_status = local_status
                    yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                    try:
                        res = await executor.execute_with_retry(task, local_status, idx)
                        results.append(res)
                    except Exception as e:
                        results.append({"action": task.get('action'), "success": False, "error": str(e)})

                    current_task_status = local_status
                    yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                summary_result = next((r.get('output') for r in results if r.get('action') == 'summarize' and r.get('success')), None)

                yield f"data: {json.dumps({'type': 'reply_start'})}\n\n"
                if summary_result:
                    words = summary_result.split(' ')
                    for i in range(0, len(words), 3):
                        if executor.should_stop:
                            yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                            return
                        chunk = ' '.join(words[i:i+3]) + ' '
                        yield f"data: {json.dumps({'type': 'reply_chunk', 'content': chunk})}\n\n"
                        await asyncio.sleep(0)
                else:
                    yield f"data: {json.dumps({'type': 'reply_chunk', 'content': 'I could not summarize the current screen right now.'})}\n\n"

                yield f"data: {json.dumps({'type': 'done', 'results': results})}\n\n"
                return
            
            # 1. ORCHESTRATION - Determine intent and mode first
            orchestration_result = await orchestrator.orchestrate(command, context, visual_history)
            mode = orchestration_result.get('mode', 'work')
            
            # Emit the detected mode to the frontend via SSE
            yield f"data: {json.dumps({'type': 'mode_change', 'mode': mode, 'sub_task': orchestration_result.get('sub_task')})}\n\n"
            
            # 1.5. IDE DELEGATION CHECK - If user is in IDE and asking about code
            ide_info = ide_delegator.detect_ide(context)
            if ide_info.get("detected"):
                # Check if user is confirming a pending delegation
                confirm_phrases = ["yes", "yeah", "yep", "do it", "go ahead", "sure", "ok", "okay", "send it", "please"]
                if ide_delegator.has_pending_delegation() and any(p in command.lower() for p in confirm_phrases):
                    ide_name = ide_delegator.pending_delegation["ide_info"]["ide_name"]
                    yield f"data: {json.dumps({'type': 'thought', 'content': 'Sending prompt to ' + ide_name + '...'})}\n\n"
                    
                    from automation.desktop import DesktopAutomation
                    desktop = DesktopAutomation()
                    result = await ide_delegator.execute_delegation(desktop)
                    
                    if result.get("success"):
                        yield f"data: {json.dumps({'type': 'reply_start'})}\n\n"
                        msg = f"Done! I've sent the prompt to {result['ide_name']}'s AI. It should start implementing now."
                        for word in msg.split():
                            yield f"data: {json.dumps({'type': 'reply_chunk', 'content': word + ' '})}\n\n"
                            await asyncio.sleep(0)
                        yield f"data: {json.dumps({'type': 'done', 'results': [{'action': 'ide_delegation', 'success': True}]})}\n\n"
                        return
                    else:
                        error_msg = result.get("error", "Unknown error")
                        yield f"data: {json.dumps({'type': 'error', 'content': 'Failed to send to IDE: ' + str(error_msg)})}\n\n"
                        return
                
                # Check if this is a coding question that could be delegated
                code_question_signals = ["implement", "create", "add", "fix", "debug", "refactor", "write", "make", "build", "what was", "what is", "how do", "can you"]
                is_code_question = any(s in command.lower() for s in code_question_signals)
                
                if is_code_question and not ide_delegator.has_pending_delegation():
                    delegation_offer = await ide_delegator.offer_delegation(command, context, visual_history)
                    
                    if delegation_offer.get("should_delegate"):
                        yield f"data: {json.dumps({'type': 'ide_delegation_offer', 'ide_name': delegation_offer['ide_name'], 'prompt': delegation_offer['generated_prompt'], 'confidence': delegation_offer.get('confidence', 0.8)})}\n\n"
                        yield f"data: {json.dumps({'type': 'reply_start'})}\n\n"
                        
                        offer_msg = delegation_offer.get("offer_message", f"I see you're in {delegation_offer['ide_name']}. Want me to have the IDE implement this?")
                        words = offer_msg.split()
                        for i in range(0, len(words), 2):
                            chunk = ' '.join(words[i:i+2]) + ' '
                            yield f"data: {json.dumps({'type': 'reply_chunk', 'content': chunk})}\n\n"
                            await asyncio.sleep(0)
                        
                        yield f"data: {json.dumps({'type': 'done', 'results': [{'action': 'ide_offer', 'waiting_confirmation': True}]})}\n\n"
                        return
            
            # 2. PLANNING - Plan tasks based on orchestration
            tasks, source_url = await task_planner.plan(command, context, file_path, parsed_history, visual_history, orchestration=orchestration_result)
            
            # Inject file_path into tasks that need it (read_and_summarize_files, read_files)
            if file_path:
                for task in tasks:
                    if task.get('action') in ['read_and_summarize_files', 'read_files']:
                        if 'params' not in task:
                            task['params'] = {}
                        if not task['params'].get('file_paths'):
                            task['params']['file_paths'] = [file_path]
            
            if source_url:
                yield f"data: {json.dumps({'type': 'source_url', 'url': source_url})}\n\n"
            
            # Use local status list to avoid IndexError from global state changes
            local_status = [
                {"id": f"s_{idx}", "label": t.get('description', t.get('action')), "status": "pending"}
                for idx, t in enumerate(tasks)
            ]
            current_task_status = local_status
            
            yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

            results = []
            reply_task_pending = None
            max_agentic_loops = 2
            agentic_loop_count = 0
            original_command = command
            all_tasks_completed = []
            
            while agentic_loop_count < max_agentic_loops:
                agentic_loop_count += 1
                
                for idx, task in enumerate(tasks):
                    if executor.should_stop:
                        yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                        return
                    
                    if idx < len(local_status):
                        local_status[idx]['status'] = 'in_progress'
                    current_task_status = local_status
                    yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"
                    
                    if task.get('action') == 'reply':
                        reply_task_pending = task
                        if idx < len(local_status):
                            local_status[idx]['status'] = 'completed'
                        results.append({"action": "reply", "success": True, "output": task.get('params', {}).get('message', '')})
                    else:
                        try:
                            res = await executor.execute_with_retry(task, local_status, idx)
                            results.append(res)
                            all_tasks_completed.append(task.get('description', task.get('action')))
                        except Exception as e:
                            results.append({"action": task.get('action'), "success": False, "error": str(e)})
                        current_task_status = local_status
                        yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"

                if executor.should_stop:
                    yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                    return
                
                # If we already have a reply task from the planner, we're likely done with the main flow
                if reply_task_pending and agentic_loop_count >= 1:
                    break
                    
                has_failures = any(not r.get('success') and not r.get('recovered') for r in results if r.get('action') != 'reply')
                has_automation_tasks = any(t.get('action') not in ['reply', 'analyze_screen', 'summarize'] for t in tasks)
                
                # Only verify if we have automation tasks and it's the first loop
                if has_automation_tasks and agentic_loop_count == 1:
                    yield f"data: {json.dumps({'type': 'thought', 'content': 'Verifying goal completion...'})}\n\n"
                    
                    verification_prompt = f"""
CRITICAL: Analyze if the user's COMPLETE goal has been achieved.

Original user command: "{original_command}"
Tasks completed so far: {all_tasks_completed}
Results: {[r.get('action') + ': ' + ('success' if r.get('success') else 'failed') for r in results if r.get('action') != 'reply']}

IMPORTANT: The user's command may have MULTIPLE parts. Analyze carefully:
- "Open X and do Y" = TWO tasks (opening X, then doing Y)
- "Go to X and click Y" = TWO tasks (navigating to X, then clicking Y)
- "Open Settings and turn on Bluetooth" = MULTIPLE tasks (open settings, find bluetooth, toggle it ON)

Did we complete EVERY part of the command?
- If only the first part was done, the goal is NOT complete
- If the app was opened but nothing was done inside it, the goal is NOT complete
- If navigation happened but the final action wasn't taken, the goal is NOT complete

Return JSON: {{"goal_complete": true/false, "missing_steps": "specific description of what still needs to be done"}}
"""
                    try:
                        verification_response = await prism_client.generate_content(verification_prompt)
                        verification_text = verification_response.strip()
                        if "```json" in verification_text:
                            verification_text = verification_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in verification_text:
                            verification_text = verification_text.split("```")[1].split("```")[0].strip()
                        
                        verification = json.loads(verification_text)
                        
                        if verification.get('goal_complete', False):
                            yield f"data: {json.dumps({'type': 'thought', 'content': 'Goal verified complete.'})}\n\n"
                            break
                        else:
                            missing = verification.get('missing_steps', 'Continue with remaining steps')
                            yield f"data: {json.dumps({'type': 'thought', 'content': f'Goal incomplete. {missing}'})}\n\n"
                            
                            context = context_detector.get_context()
                            visual_history = session_recorder.get_history()
                            continuation_command = f"""CONTINUE EXECUTION - DO NOT STOP
Original goal: {original_command}
Already completed: {all_tasks_completed}
Still needed: {missing}

Generate the REMAINING steps to complete the goal. DO NOT repeat completed steps.
DO NOT include a reply task until ALL automation steps are done."""
                            
                            new_tasks, _ = await task_planner.plan(continuation_command, context, file_path, parsed_history, visual_history, orchestration=orchestration_result)
                            
                            non_reply_tasks = [t for t in new_tasks if t.get('action') != 'reply']
                            if non_reply_tasks and len(non_reply_tasks) > 0:
                                tasks = non_reply_tasks
                                reply_task_pending = None
                                new_status = [
                                    {"id": f"s_{len(local_status) + idx}", "label": t.get('description', t.get('action')), "status": "pending"}
                                    for idx, t in enumerate(tasks)
                                ]
                                local_status.extend(new_status)
                                current_task_status = local_status
                                yield f"data: {json.dumps({'type': 'tasks', 'tasks': local_status})}\n\n"
                            else:
                                break
                    except Exception as e:
                        logger.warning(f"Goal verification failed: {e}")
                        break
                else:
                    break
            
            # Check for summary results to include in final reply
            summary_result = next((r.get('output') for r in results if r.get('action') in ['summarize', 'read_and_summarize_files'] and r.get('success')), None)
            
            # If we have a summary result and user asked for summary/summarize, use it directly
            if summary_result and any(kw in command.lower() for kw in ['summar', 'explain', 'what is', 'describe']):
                yield f"data: {json.dumps({'type': 'reply_start'})}\n\n"
                words = summary_result.split(' ')
                for i in range(0, len(words), 3):
                    if executor.should_stop:
                        yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                        return
                    chunk = ' '.join(words[i:i+3]) + ' '
                    yield f"data: {json.dumps({'type': 'reply_chunk', 'content': chunk})}\n\n"
                    await asyncio.sleep(0)
                yield f"data: {json.dumps({'type': 'done', 'results': results})}\n\n"
                return
            
            if reply_task_pending:
                message = reply_task_pending.get('params', {}).get('message') or reply_task_pending.get('params', {}).get('content') or reply_task_pending.get('description', '')
                yield f"data: {json.dumps({'type': 'reply_start'})}\n\n"
                
                if summary_result and "summary" in command.lower():
                    # If we have a summary and user asked for it, prioritize it or append it
                    message = summary_result
                
                if message:
                    words = message.split(' ')
                    for i in range(0, len(words), 3):
                        if executor.should_stop:
                            yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                            return
                        chunk = ' '.join(words[i:i+3]) + ' '
                        yield f"data: {json.dumps({'type': 'reply_chunk', 'content': chunk})}\n\n"
                        await asyncio.sleep(0)
                else:
                    async for chunk in prism_client.generate_content_stream(f"User: {command}. Tasks completed: {all_tasks_completed}. Reply naturally confirming what was done.", context_text=str(results)):
                        if executor.should_stop:
                            yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                            return
                        yield f"data: {json.dumps({'type': 'reply_chunk', 'content': chunk})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'reply_start'})}\n\n"
                
                if summary_result and "summary" in command.lower():
                    # Stream the summary directly
                    words = summary_result.split(' ')
                    for i in range(0, len(words), 3):
                        if executor.should_stop:
                            yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                            return
                        chunk = ' '.join(words[i:i+3]) + ' '
                        yield f"data: {json.dumps({'type': 'reply_chunk', 'content': chunk})}\n\n"
                        await asyncio.sleep(0)
                else:
                    async for chunk in prism_client.generate_content_stream(f"User command: {command}. Tasks completed: {all_tasks_completed}. Provide a natural, concise reply to the user.", context_text=str(results)):
                        if executor.should_stop:
                            yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                            return
                        yield f"data: {json.dumps({'type': 'reply_chunk', 'content': chunk})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'results': results})}\n\n"

        except Exception as e:
            error_msg = str(e)
            error_type = "error"
            error_code = None
            
            if "EXPIRED_API_KEY" in error_msg:
                error_msg = "Your Gemini API Key has expired. Please update it in Settings."
                error_code = "EXPIRED_KEY"
            elif "MISSING_API_KEY" in error_msg:
                error_msg = "Gemini API Key is missing. Please set it in Settings."
                error_code = "MISSING_KEY"

            logger.error(f"Stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg, 'code': error_code})}\n\n"
        finally:
            if current_stream_task is asyncio.current_task():
                current_stream_task = None

    return StreamingResponse(stream_generator(), media_type="text/event-stream")

@app.post("/execute-preset")
async def execute_preset(request: PresetRequest):
    global current_execution_task, current_task_status
    try:
        current_task_status = []
        current_execution_task = asyncio.create_task(run_preset_execution(request.steps, request.history))
        results = await asyncio.wait_for(current_execution_task, timeout=300) # 5 min limit for presets
        return results
    except Exception as e:
        logger.error(f"Preset error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        current_execution_task = None

async def run_preset_execution(steps: List[str], history: List[Dict[str, Any]] = None):
    all_results = []
    current_history = history or []
    overall_success = True
    
    global current_task_status
    current_task_status = []
    
    for i, step in enumerate(steps):
        step_marker = {"id": f"step_{i}", "label": f"Step {i+1}: {step}", "status": "in_progress"}
        current_task_status.append(step_marker)
        
        res = await run_execution(step, history=current_history, append_tasks=True)
        all_results.append(res)
        
        if not res.get("success"):
            overall_success = False
            step_marker["status"] = "error"
            break
        
        step_marker["status"] = "completed"
        current_history.append({"role": "user", "content": step})
        if res.get("reply"):
            current_history.append({"role": "assistant", "content": res.get("reply")})
            
    return {
        "success": overall_success,
        "results": all_results,
        "reply": "Workflow completed successfully." if overall_success else "Workflow interrupted due to error."
    }

async def run_execution(command: str, file_path: Optional[str] = None, history: List[Dict[str, str]] = None, append_tasks: bool = False):
    global current_task_status
    context = context_detector.get_context()
    visual_history = session_recorder.get_history()
    tasks, _ = await task_planner.plan(command, context, file_path, history, visual_history)
    
    new_task_status = [
        {"id": f"t_{idx}_{os.urandom(4).hex()}", "label": t.get('description', t.get('action')), "status": "pending"}
        for idx, t in enumerate(tasks)
    ]
    
    if append_tasks:
        current_task_status.extend(new_task_status)
    else:
        current_task_status = new_task_status
    
    results = await executor.execute_tasks(tasks, current_task_status, history)
    success = all(r.get('success') or r.get('recovered') for r in results)
    
    reply = next((r.get('output') for r in results if r.get('action') == 'reply' and r.get('success')), None)
    if not reply and success:
        reply = f"Task '{command}' finished."
    
    return {"success": success, "results": results, "reply": reply}

@app.post("/reset", response_model=GenericResponse)
async def reset_backend():
    global current_execution_task, current_stream_task, current_task_status, attached_file_context
    
    executor.force_stop()
    
    if current_execution_task and not current_execution_task.done():
        current_execution_task.cancel()
    if current_stream_task and not current_stream_task.done():
        current_stream_task.cancel()
    
    await executor.close()
    current_task_status = []
    attached_file_context = None
    executor.set_attached_file(None)
    session_recorder.clear()
    
    if os.path.exists("temp"):
        shutil.rmtree("temp")
        os.makedirs("temp")
                
    return {"success": True, "message": "Backend reset successfully"}

@app.get("/context")
async def get_context():
    try:
        return {"success": True, "context": context_detector.get_context()}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/stop", response_model=GenericResponse)
async def stop_execution():
    global current_execution_task, current_stream_task
    executor.force_stop()

    if current_execution_task and not current_execution_task.done():
        current_execution_task.cancel()
    if current_stream_task and not current_stream_task.done():
        current_stream_task.cancel()

    return {"success": True, "message": "Execution stopped"}

@app.get("/active-app")
async def get_active_app():
    try:
        info = context_detector.get_active_window_info()
        return {
            "success": True,
            "app_name": info["app_name"],
            "title": info["title"],
            "is_coding": info.get("is_coding", False)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/weather")
async def get_weather():
    import datetime
    try:
        prompt = f"""Estimate user location from system time/timezone. Provide current weather.
Time: {datetime.datetime.now().isoformat()}
JSON: {{"city": "City", "temp": 22, "condition": "sunny"}}
Conditions: sunny, cloudy, partly_cloudy, rainy, stormy, clear_night"""

        response = await prism_client.client.aio.models.generate_content(
            model=prism_client.model_id,
            contents=prompt
        )
        
        text = response.text.strip()
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        
        data = json.loads(text)
        return {"success": True, **data}
    except Exception as e:
        logger.error(f"Weather error: {e}")
        return {"success": False, "city": "Unknown", "temp": 20, "condition": "sunny"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    os.makedirs("temp", exist_ok=True)
    file_path = f"temp/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        text = await prism_client.transcribe(file_path)
        return {"success": True, "transcription": text}
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@app.get("/memory-status")
async def get_memory_status():
    return {
        "success": True, 
        **session_recorder.get_status()
    }

class MemoryToggleRequest(BaseModel):
    disabled: bool = False

@app.post("/memory-toggle")
async def toggle_visual_memory(request: MemoryToggleRequest):
    session_recorder.set_disabled(request.disabled)
    return {
        "success": True,
        "disabled": request.disabled,
        "message": "Visual memory disabled" if request.disabled else "Visual memory enabled"
    }

@app.post("/memory-clear")
async def clear_memory():
    try:
        session_recorder.clear()
        memory_system.clear()
        return {"success": True, "message": "Memory cleared"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/tokens")
async def get_token_usage():
    return {
        "success": True,
        "total": prism_client.total_tokens_used,
        "session": prism_client.last_usage.get("total_tokens", 0)
    }

@app.post("/ide/confirm-delegation")
async def confirm_ide_delegation():
    """User confirmed delegation - execute the pending IDE prompt"""
    try:
        from automation.desktop import DesktopAutomation
        desktop = DesktopAutomation()
        result = await ide_delegator.execute_delegation(desktop)
        return result
    except Exception as e:
        logger.error(f"IDE delegation failed: {e}")
        return {"success": False, "error": str(e)}

@app.post("/ide/cancel-delegation")
async def cancel_ide_delegation():
    """User cancelled delegation"""
    ide_delegator.clear_pending()
    return {"success": True, "message": "Delegation cancelled"}

@app.get("/ide/pending")
async def get_pending_delegation():
    """Check if there's a pending IDE delegation"""
    if ide_delegator.has_pending_delegation():
        return {
            "has_pending": True,
            "ide_name": ide_delegator.pending_delegation.get("ide_info", {}).get("ide_name"),
            "prompt": ide_delegator.pending_delegation.get("prompt")
        }
    return {"has_pending": False}

# Overlay endpoints (no-op if no overlay service is running)
@app.post("/overlay/show")
async def overlay_show(_: Dict[str, Any]):
    return {"success": True}

@app.post("/overlay/draw")
async def overlay_draw(_: Dict[str, Any]):
    return {"success": True}

@app.post("/overlay/clear")
async def overlay_clear():
    return {"success": True}

@app.post("/visual-dom/scan")
async def scan_screen_visual_dom(use_ai: bool = True):
    """Scan the current screen and build a Visual DOM"""
    try:
        import pyautogui
        os.makedirs("temp", exist_ok=True)
        screenshot_path = os.path.abspath("temp/visual_dom_scan.png")
        screenshot = pyautogui.screenshot()
        screenshot.save(screenshot_path)
        
        await visual_dom_instance.scan(screenshot_path, use_ai=use_ai)
        
        return {
            "success": True,
            "dom": visual_dom_instance.to_dict(),
            "context": visual_dom_instance.get_context_for_ai()
        }
    except Exception as e:
        logger.error(f"Visual DOM scan failed: {e}")
        return {"success": False, "error": str(e)}

@app.get("/visual-dom/elements")
async def get_visual_dom_elements():
    """Get the current Visual DOM elements"""
    if not visual_dom_instance.elements:
        return {"success": False, "error": "No scan performed yet. Call /visual-dom/scan first."}
    return {
        "success": True,
        "elements": {el_id: el.to_dict() for el_id, el in visual_dom_instance.elements.items()},
        "summary": visual_dom_instance.to_dict().get("summary", {})
    }

@app.get("/visual-dom/interactive")
async def get_interactive_elements():
    """Get all interactive elements from the Visual DOM"""
    if not visual_dom_instance.elements:
        return {"success": False, "error": "No scan performed yet."}
    interactive = visual_dom_instance.find_interactive_elements()
    return {
        "success": True,
        "count": len(interactive),
        "elements": [el.to_dict() for el in interactive]
    }

@app.get("/visual-dom/forms")
async def get_form_fields():
    """Get all form fields from the Visual DOM"""
    if not visual_dom_instance.elements:
        return {"success": False, "error": "No scan performed yet."}
    fields = visual_dom_instance.find_form_fields()
    return {
        "success": True,
        "count": len(fields),
        "fields": [
            {"label": f.get("label"), "type": f.get("type"), "center": f.get("center")}
            for f in fields
        ]
    }

@app.get("/visual-dom/find")
async def find_element_in_dom(description: str):
    """Find an element in the Visual DOM by description"""
    if not visual_dom_instance.elements:
        return {"success": False, "error": "No scan performed yet."}
    
    element = visual_dom_instance.find_element(description)
    if element:
        return {
            "success": True,
            "found": True,
            "element": element.to_dict()
        }
    return {
        "success": True,
        "found": False,
        "message": f"Element '{description}' not found in Visual DOM"
    }

@app.get("/visual-dom/overlay")
async def get_visual_dom_overlay():
    """Generate an overlay image showing detected elements"""
    if not visual_dom_instance.last_scan_path:
        return {"success": False, "error": "No scan performed yet."}
    
    try:
        output_path = os.path.abspath("temp/visual_dom_overlay.png")
        visual_dom_instance.draw_overlay(output_path)
        return {
            "success": True,
            "overlay_path": output_path
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
