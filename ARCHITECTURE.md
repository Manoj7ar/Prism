# Prism Architecture

Prism is a Windows-first desktop agent with an Electron shell (renderer UI) and a FastAPI backend that plans and executes automation using Google Gemini.

## System Overview

```mermaid
graph TB
    subgraph "Frontend"
        RENDERER[Electron Renderer UI]
        MAIN[Electron Main + Tray]
        RENDERER --- MAIN
    end

    subgraph "Backend (FastAPI)"
        API[HTTP + SSE API]
        ORCH[Intent Orchestrator]
        PLAN[Task Planner]
        EXEC[Task Executor]
        REC[Session Recorder]
    end

    subgraph "Automation"
        DESK[Desktop Automation (PyAutoGUI)]
        WEB[Browser Automation (Playwright + Chrome CDP)]
        VDOM[Visual DOM (OCR + CV + optional Gemini classification)]
    end

    subgraph "Intelligence"
        GEM[Google Gemini (google.genai)]
        REDACT[Privacy Redactor (OCR + Gemini)]
    end

    RENDERER -- "/execute-stream" --> API
    API --- ORCH
    ORCH --- PLAN
    PLAN --- EXEC
    API --- REC

    EXEC --> DESK
    EXEC --> WEB
    EXEC --> VDOM
    EXEC --> GEM
    REC --> REDACT
```

---

## Core Components

### 1) UI Layer
- **Electron renderer UI** (`electron-app/src/renderer/`) renders chat, task bubbles, settings, presets, and status updates.
- **Electron shell** (`electron-app/`) provides tray, global hotkey (`Alt+Space`), window positioning, and an automation glow overlay.
- **Summary window** is opened from Electron to show screen summaries.

### 2) FastAPI Backend
- **`/execute-stream`** is the main endpoint; it streams task status and responses via SSE.
- **`/thinking/events`** and **`/screenshot/events`** stream status and visual memory events.
- **`/settings`, `/memory-status`, `/memory-toggle`** expose app and visual memory settings.
- **`/transcribe`** accepts recorded audio and returns a transcript (currently unused by the Electron UI).

### 3) Orchestration & Planning
- **Intent Orchestrator** selects a mode from: `work`, `visual_memory`, `research`, `create` based on context and a recent screenshot.
- **Task Planner** calls Gemini to produce a JSON task list, with a fallback for simple "open app" commands.

### 4) Execution & Automation
- **Task Executor** runs actions with retries, recovery, and optional companion steps.
- **Desktop Automation** uses PyAutoGUI for clicks, typing, scrolling, window controls, and OS actions.
- **Browser Automation** uses Playwright connected to Chrome via remote debugging.
- **Visual DOM** builds a semantic map of UI elements using OCR + CV; Gemini-based classification is optional.

### 5) Visual Memory & Privacy
- **Session Recorder** captures screenshots on an interval and stores them locally under `python-backend/session_memory/`.
- **Privacy Redactor** blurs sensitive text and apps using local OCR patterns and Gemini vision.
- Screenshots are auto-cleaned based on age and storage limits.

---

## Data Flow

1. User submits a command from the UI.
2. Backend gathers context (active window, clipboard, recent frames).
3. Orchestrator selects a mode; planner produces tasks.
4. Executor performs tasks and streams status/events via SSE.
5. UI renders task bubbles, replies, and summary windows.

---

## Configuration

- Model and API key are configured via `.env` (root):
  - `GEMINI_API_KEY` (required)
  - `GEMINI_MODEL` (defaults to `gemini-2.0-flash`)

---

## Platform Notes

- Desktop automation and Bluetooth toggling are implemented for Windows; macOS/Linux support is best-effort.
- Chrome URL detection via UI Automation is Windows-only.
- Presets and the automation glow overlay are Electron-only features.
