<p align="center">
  <img src="electron-app/assets/icon_512.png" alt="Prism Logo" width="140" />
</p>
<h1 align="center">Prism</h1>
<p align="center"><strong>Windows Desktop AI Agent</strong></p>

# Prism

Prism is a desktop AI assistant with:
- an Electron desktop UI (`electron-app`)
- a FastAPI automation backend (`python-backend`)
- multimodal planning/execution using Gemini + local desktop/browser automation

## Architecture

- `electron-app`
- always-on-top desktop shell, tray integration, global shortcuts, renderer chat UI
- talks to backend over HTTP/SSE (`http://127.0.0.1:8000`)

- `python-backend`
- FastAPI service for planning, execution, streaming task updates, memory/session capture
- desktop automation via PyAutoGUI + Windows integrations
- browser automation via keyboard/URL flows and Playwright-backed actions

## Implemented Features

### Core execution
- Natural language command execution (`/execute`, `/execute-stream`)
- Streaming task progress and reply chunks over SSE
- Preset workflow execution (`/execute-preset`)
- Stop/reset controls (`/stop`, `/reset`)

### Fast and strict intent paths
- Fast direct chat path (question-style prompts)
- Fast app open path (`open/launch/start <app>`)
- Strict browser navigation path (`open <browser> and go to <site>`)
- Strict attached-file summary -> new Google Doc path (`https://docs.new`)
- Strict attached-file send -> WhatsApp Web path (`https://web.whatsapp.com`)

### Desktop automation actions
- Open/focus apps and windows
- Click/type/scroll/drag/drop
- Tab/window navigation, back/forward/refresh, address-bar navigation
- System actions (including Windows Bluetooth toggle)
- File attachment helpers:
- select file in dialog
- copy file to clipboard and paste

### File workflows
- Attach files from UI (picker + drag/drop)
- Supports document-centric flows (read/summarize and downstream actions)
- Attachment bubble lifecycle in UI

### Visual memory
- Periodic screenshot session capture (default every `15s`)
- OCR + redaction integration
- Memory status endpoint (`/memory-status`)
- Toggle endpoint (`/memory-toggle`)
- Clear endpoint (`/memory-clear`)
- Auto wipe by time window (default `180 min`)
- Auto reset when storage cap is exceeded (default `500 MB`)

### Visual understanding
- Screen analysis and summarization actions
- Visual DOM scan/endpoints:
- `/visual-dom/scan`
- `/visual-dom/elements`
- `/visual-dom/interactive`
- `/visual-dom/forms`
- `/visual-dom/find`
- `/visual-dom/overlay`

### Electron UX
- Global shortcut support (`Alt+Space`)
- Settings panel, API-key setup flow, task/status UI
- Automation overlay support from main process IPC

## API Surface (Backend)

Main endpoints in `python-backend/main.py`:
- `/health`
- `/execute`
- `/execute-stream`
- `/execute-preset`
- `/tasks`
- `/thinking/events`
- `/screenshot/events`
- `/stop`
- `/reset`
- `/settings`
- `/settings/fast-mode`
- `/memory-status`
- `/memory-toggle`
- `/memory-clear`
- `/tokens`
- `/active-app`
- `/context`
- `/set-key`
- `/check-auth`
- `/visual-dom/*`

## Prerequisites

- Windows (primary supported automation target)
- Python 3.11 recommended
- Node.js + npm
- Google Gemini API key

Optional:
- Bun (not required for current baseline run command)

## Local Run

### 1) Start backend
```powershell
cd C:\Users\manoj\orchids-projects\Prism\python-backend
C:\Users\manoj\AppData\Local\Programs\Python\Python311\python.exe -u main.py
```

### 2) Start Electron UI
```powershell
cd C:\Users\manoj\orchids-projects\Prism\electron-app
npx electron .
```

## Configuration

Expected backend env values (from `python-backend/config.py` usage):
- `GEMINI_API_KEY` (required)
- `GEMINI_MODEL` (optional override)
- `CORS_ORIGINS` (optional)

## Notes

- This repo currently runs Electron directly from `npx electron .` in local development.
- Backend must be reachable at `127.0.0.1:8000`.
- If automation appears stuck, verify active app/window focus and backend logs in `python-backend`.

## Repository Layout

```text
Prism/
  electron-app/      # Electron shell + renderer UI
  python-backend/    # FastAPI backend + automation + visual memory
```
