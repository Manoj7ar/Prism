import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Union, AsyncGenerator
from google.genai import types, Client
from .context_detector import ContextDetector
from utils.privacy import PrivacyRedactor
from .knowledge import KnowledgeSystem

from utils.screen_utils import get_screen_resolution, get_dpi_scale
from automation.visual_detector import visual_detector

logger = logging.getLogger("PrismClient")

class PrismClient:
    def __init__(self, model_id: str = "gemini-2.0-flash", thought_callback=None):
        self.model_id = model_id
        self.thought_callback = thought_callback
        api_key = os.getenv("GEMINI_API_KEY")
        self.client = Client(api_key=api_key, http_options={'api_version': 'v1beta'}) if api_key else None
        self.detector = ContextDetector()
        self.privacy = PrivacyRedactor(self)
        self.knowledge = KnowledgeSystem()
        self.total_tokens_used = 0
        self.last_usage = {}
        self.visual_detector = visual_detector
        
        # Action mappings
        self.action_space = {
            "read_files": "Read contents of specific files. Params: {file_paths: ['path1', 'path2']}",
            "read_and_summarize_files": "Read and provide detailed summaries of files. Params: {file_paths: ['path1', 'path2']}. IMPORTANT: Use the uploaded file path from context.",
            "browser_navigate": "Navigate to a URL",
            "browser_click": "Click a web element",
            "browser_type": "Type into a web element",
            "browser_extract": "Extract data from a webpage",
            "type_text": "Type text at cursor",
            "type_previous_result": "Type the result of a previous step",
            "press_keys": "Press keyboard shortcuts",
            "open_app": "Launch an application",
            "visual_click": "Use vision to find and click an element",
            "wait": "Pause execution",
            "wait_for_visual": "Wait until a visual state is reached",
            "reply": "Send final message to user",
            "debug_error": "Analyze and fix an error",

            "batch_process": "Process multiple files at once",
            "scroll": "Scroll the active window",
            "scroll_to_element": "Scroll until element is visible",
            "drag_drop": "Drag from A to B",
            "switch_window": "Switch active application",
            "minimize_window": "Minimize current window",
            "maximize_window": "Maximize current window",
            "snap_window": "Snap window to side",
            "close_window": "Close current window",
            "new_tab": "Open new browser tab",
            "close_tab": "Close current browser tab",
            "switch_tab": "Switch browser tabs",
            "go_back": "Browser back",
            "go_forward": "Browser forward",
            "refresh": "Refresh page",
            "focus_address_bar": "Focus URL bar",
            "search_in_page": "Find text on page",
            "select_all": "Select all text",
            "copy": "Copy to clipboard",
            "paste": "Paste from clipboard",
            "undo": "Undo action",
            "redo": "Redo action",
            "escape": "Press Escape",
            "enter": "Press Enter",
            "navigate_url": "Navigate to URL in the active browser window using keyboard (Ctrl+L, type URL, Enter)",
            "double_click": "Double click element",
            "right_click": "Right click element",
            "hover": "Hover over element",
            "triple_click": "Triple click element",
            "analyze_screen": "Detailed visual audit of the screen",
            "summarize": "Take a screenshot and provide a concise summary of the page/content",
            "toggle_bluetooth": "Toggle Bluetooth on/off directly (Windows). Params: {enable: true/false}",
            "system_setting": "Control system settings directly (bluetooth, wifi, etc). Params: {setting: 'bluetooth', action: 'enable'/'disable'/'toggle'}",
            "scan_screen": "Build a Visual DOM of the screen - detects all buttons, inputs, forms, menus. Use before fill_form or dom_click for speed.",
            "dom_click": "Click element using Visual DOM (faster than visual_click). Params: {element: 'description'}. Falls back to vision if not found.",
            "fill_form": "Fill multiple form fields at once using Visual DOM. Params: {fields: {'Label1': 'value1', 'Email': 'test@example.com'}}",
            "attach_file": "Attach the user-uploaded file to an application. Use after clicking an attach button when a file dialog opens. Params: {method: 'dialog' or 'clipboard'}. Uses the file path from user's upload.",
            "select_file_dialog": "Select a file in an already-open file dialog. Uses the user-uploaded file path automatically.",
            "copy_file_to_clipboard": "Copy the user-uploaded file to clipboard, then paste it. For apps like Discord, Teams, etc.",
            "web_click": "Click element in Chrome browser by CSS selector. Params: {selector: 'button.submit', by: 'css'|'text'|'role'|'label'|'placeholder'}. PREFERRED for web automation.",
            "web_click_text": "Click element in Chrome by visible text. Params: {text: 'Compose', exact: false}. Great for clicking buttons/links by their label.",
            "web_type": "Type into input field in Chrome. Params: {selector: 'input[name=q]', text: 'hello', by: 'css'|'placeholder'|'label'}",
            "web_type_submit": "Type into field and press Enter. Params: {selector: 'Search', text: 'query', by: 'placeholder'}. Great for search boxes.",
            "web_navigate": "Navigate Chrome to URL. Params: {url: 'https://gmail.com'}. Connects to existing Chrome or launches with debugging.",
            "web_scroll": "Scroll in Chrome. Params: {direction: 'down'|'up', amount: 500}",
            "web_new_tab": "Open new Chrome tab. Params: {url: 'https://youtube.com'} (optional)",
            "web_close_tab": "Close current Chrome tab",
            "web_switch_tab": "Switch Chrome tabs. Params: {index: 0} or {direction: 'next'|'prev'}",
            "web_back": "Go back in Chrome history",
            "web_forward": "Go forward in Chrome history",
            "web_refresh": "Refresh current Chrome page",
            "web_search_google": "Search on Google. Params: {query: 'search term'}. Opens Google with search results.",
            "web_search_youtube": "Search on YouTube. Params: {query: 'video name'}. Opens YouTube search results.",
            "web_gmail_compose": "Open Gmail compose. Params: {to: 'email@example.com', subject: 'Hi', body: 'Message'}",
            "web_fill_form": "Fill multiple form fields in Chrome. Params: {fields: {'Email': 'test@test.com', 'Password': '123'}}",
            "web_press_key": "Press keyboard key in Chrome. Params: {key: 'Enter'|'Tab'|'Escape'|'ArrowDown'}",
            "web_get_url": "Get current Chrome page URL",
            "web_get_title": "Get current Chrome page title"
        }

    @property
    def config(self):
        return types.GenerateContentConfig(
            response_mime_type="application/json"
        )

    def _get_thinking_config(self, level: str):
        budget = 4000
        if level == "deep": budget = 16000
        elif level == "frontier": budget = 32000
        return types.ThinkingConfig(include_thoughts=True, preview_py_threshold=budget)

    async def _safe_generate(self, model, contents, config):
        if not self.client:
            raise Exception("Gemini API Key not configured")
        
        max_retries = 5
        base_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                response = await self.client.aio.models.generate_content(model=model, contents=contents, config=config)
                self._track_usage(response)
                return response
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "resource_exhausted" in error_str or "quota" in error_str:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt) + (asyncio.get_event_loop().time() % 1.0)
                        logger.warning(f"Gemini rate limit (429). Retrying in {delay:.2f}s... (Attempt {attempt+1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                raise e
        return None

    def _track_usage(self, response):
        if hasattr(response, 'usage_metadata'):
            usage = {
                "prompt_tokens": response.usage_metadata.prompt_token_count,
                "candidates_tokens": response.usage_metadata.candidates_token_count,
                "total_tokens": response.usage_metadata.total_token_count
            }
            self.last_usage = usage
            self.total_tokens_used += usage["total_tokens"]

    def _get_app_specific_hints(self, element_description: str) -> str:
        desc_lower = element_description.lower()
        hints = []
        
        if any(kw in desc_lower for kw in ['liked songs', 'liked', 'spotify', 'playlist', 'library']):
            hints.append("""
SPOTIFY-SPECIFIC HINTS:
- The "Liked Songs" item is in the LEFT sidebar, typically has a heart icon or purple/gradient background
- It may appear as a playlist item with text "Liked Songs" or just a heart icon
- Look in the navigation panel on the left side of the screen
- The green play button appears when you HOVER over a playlist/album - look for a large green circle with white triangle""")
        
        if any(kw in desc_lower for kw in ['play', 'pause', 'shuffle', 'repeat', 'skip', 'next', 'previous']):
            hints.append("""
PLAYBACK CONTROL HINTS:
- Play buttons are usually GREEN circular buttons with a white triangle pointing right
- Playback controls (play/pause, skip, shuffle) are typically at the BOTTOM of the screen
- The main play button on a playlist/album is a large GREEN circle that appears on hover
- Shuffle and repeat buttons are usually near the play controls""")
        
        if any(kw in desc_lower for kw in ['search', 'home', 'browse', 'library', 'your library']):
            hints.append("""
NAVIGATION HINTS:
- Navigation icons (Home, Search, Library) are typically in the LEFT sidebar at the TOP
- Search is usually represented by a magnifying glass icon
- Home is usually a house icon
- Library may show as books or collection icon""")
        
        return "\n".join(hints) if hints else ""

    def _get_media_part(self, file_path: str):
        if not os.path.exists(file_path):
            logger.error(f"Media file not found: {file_path}")
            return types.Part.from_text(text=f"[Error: File {os.path.basename(file_path)} missing]")
            
        ext = file_path.split('.')[-1].lower()
        mime = "image/png"
        if ext == "jpg" or ext == "jpeg": mime = "image/jpeg"
        elif ext == "pdf": mime = "application/pdf"
        elif ext == "mp4": mime = "video/mp4"
        elif ext in ["mp3", "wav", "ogg", "flac"]: mime = f"audio/{ext}"
        
        with open(file_path, "rb") as f:
            return types.Part.from_bytes(data=f.read(), mime_type=mime)

    def reinitialize(self, api_key: str) -> bool:
        try:
            os.environ["GEMINI_API_KEY"] = api_key
            self.client = Client(api_key=api_key, http_options={'api_version': 'v1beta'})
            return True
        except Exception as e:
            logger.error(f"Reinitialization failed: {e}")
            return False

    async def emit_thought(self, message: str, type: str = "thought"):
        if self.thought_callback:
            await self.thought_callback(message, type=type)

    async def transcribe(self, file_path: str) -> str:
        await self.emit_thought(f"Transcribing audio: {os.path.basename(file_path)}...")
        part = self._get_media_part(file_path)
        response = await self._safe_generate(
            model=self.model_id,
            contents=[part, "Transcribe this audio file accurately. Return only the transcript."],
            config=None
        )
        return response.text.strip()

    async def parse_command(self, command: str, context: Dict[str, Any] = None, history: List[Dict[str, Any]] = None, visual_history: List[Dict[str, Any]] = None, thinking_level: Optional[str] = None):
        return await self.execute_query(command, history, context, visual_history, thinking_level)

    async def generate_content(self, prompt: str, context_text: Optional[str] = None) -> str:
        contents = [prompt]
        if context_text:
            contents.insert(0, f"Context Information:\n{context_text}\n---")
            
        response = await self._safe_generate(self.model_id, contents, None)
        return response.text.strip()

    async def generate_content_stream(self, prompt: str, context_text: Optional[str] = None) -> AsyncGenerator[str, None]:
        contents = [prompt]
        if context_text:
            contents.insert(0, f"Context Information:\n{context_text}\n---")
            
        max_retries = 5
        base_delay = 2.0
        
        for attempt in range(max_retries):
            try:
                # The SDK returns an async iterator directly from the coroutine
                stream = await self.client.aio.models.generate_content_stream(
                    model=self.model_id,
                    contents=contents,
                    config=types.GenerateContentConfig(tools=[]), # No tools for speed
                )
                async for chunk in stream:
                    if chunk.text:
                        yield chunk.text
                return # Success
            except Exception as e:
                error_str = str(e).lower()
                if ("429" in error_str or "resource_exhausted" in error_str or "quota" in error_str) and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + (asyncio.get_event_loop().time() % 1.0)
                    logger.warning(f"Stream rate limit (429). Retrying in {delay:.2f}s... (Attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"Stream error in PrismClient: {e}")
                yield f"Error: {str(e)}"
                break

    async def locate_element_visually(self, image_path: str, element_description: str) -> Optional[Dict[str, Any]]:
        await self.emit_thought(f"Locating '{element_description}' on screen...")
        
        part = self._get_media_part(image_path)
        width, height = get_screen_resolution()
        
        app_hints = self._get_app_specific_hints(element_description)
        
        prompt = f"""You are a UI element locator. The image is a {width}x{height} pixel screenshot.

Find the UI element: "{element_description}"

INSTRUCTIONS:
1. Scan the entire image carefully for the element
2. Look for text labels, buttons, toggles, icons, or visual indicators matching the description
3. For toggles/switches: target the actual switch control, not just the label
4. For menu items in sidebars: target the clickable text or icon area
5. For play buttons: look for circular green buttons with triangle play icons
6. Return the PIXEL coordinates of the element's center
{app_hints}
COMMON UI PATTERNS:
- "Liked Songs" on Spotify: Usually in left sidebar with a heart icon, may show as purple/pink gradient
- "Play" buttons: Often large green circular buttons with white triangle, or smaller play icons
- Sidebar navigation: Usually on the LEFT side of the screen
- Music controls: Usually at the BOTTOM of the screen

Return JSON: {{"x": <pixel_x>, "y": <pixel_y>}}
If not found: {{"x": -1, "y": -1}}

IMPORTANT: x must be 0-{width}, y must be 0-{height}. These are actual pixel coordinates, NOT normalized."""
        
        try:
            response = await self._safe_generate(
                model=self.model_id,
                contents=[part, prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            data = json.loads(response.text)
            
            x_val = data.get('x', -1)
            y_val = data.get('y', -1)
            
            if x_val >= 0 and y_val >= 0:
                # If Gemini returned normalized values (0-1000), convert them
                if x_val <= 1000 and y_val <= 1000 and (x_val > width or y_val > height or (x_val < 100 and y_val < 100)):
                    # Likely normalized, convert
                    approx_x = round(x_val * width / 1000)
                    approx_y = round(y_val * height / 1000)
                else:
                    # Already pixel coordinates
                    approx_x = round(x_val)
                    approx_y = round(y_val)
                
                # Sanity check
                if 0 <= approx_x <= width and 0 <= approx_y <= height:
                    return {
                        "x": approx_x,
                        "y": approx_y,
                        "method": "gemini_vision_direct"
                    }
                else:
                    return {
                        "x": max(0, min(width, approx_x)),
                        "y": max(0, min(height, approx_y)),
                        "method": "gemini_vision_clamped"
                    }
        except Exception as e:
            logger.warning(f"Visual grounding failed: {e}")

        return None


    async def _refine_with_crop(self, image_path: str, x: int, y: int, description: str) -> Optional[Dict[str, Any]]:
        """Crops a small area around the suspected point and asks for higher precision"""
        try:
            import cv2
            img = cv2.imread(image_path)
            if img is None: return None
            h, w, _ = img.shape
            
            # 300x300 crop
            crop_size = 300
            x1 = max(0, x - crop_size // 2)
            y1 = max(0, y - crop_size // 2)
            x2 = min(w, x1 + crop_size)
            y2 = min(h, y1 + crop_size)
            
            # Adjust if at edges
            x1 = max(0, x2 - crop_size)
            y1 = max(0, y2 - crop_size)
            
            crop = img[y1:y2, x1:x2]
            crop_path = image_path.replace(".png", "_crop.png")
            cv2.imwrite(crop_path, crop)
            
            part = self._get_media_part(crop_path)
            prompt = f"""This is a zoomed-in view of the screen. 
            Find the exact center of '{description}' in this crop.
            Return coordinates RELATIVE TO THIS CROP (0-1000).
            JSON: {{"x": int, "y": int}}"""
            
            response = await self._safe_generate(
                model=self.model_id,
                contents=[part, prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            data = json.loads(response.text)
            if data['x'] >= 0:
                # Convert crop coordinates back to full image pixels
                final_x = x1 + int(data['x'] * (x2 - x1) / 1000)
                final_y = y1 + int(data['y'] * (y2 - y1) / 1000)
                
                return {
                    "x": final_x,
                    "y": final_y,
                    "method": "precision_crop",
                    "confidence": 0.95
                }
        except Exception as e:
            logger.debug(f"Precision crop refinement failed: {e}")
        return None

    async def analyze_screen_state(self, image_path: str) -> str:
        part = self._get_media_part(image_path)
        prompt = "Perform a detailed visual audit of this screen. Identify open apps, active tasks, and potential issues."
        response = await self._safe_generate(self.model_id, [part, prompt], None)
        return response.text.strip()

    async def summarize_page_state(self, image_path: str) -> str:
        part = self._get_media_part(image_path)
        prompt = """Analyze this screenshot of a webpage or document. 
        Identify the main topic, key points, and provide a concise, structured summary.
        Focus on the visible content. If it's a news article, summarize the headline and lead.
        If it's a dashboard, summarize the key metrics.
        Keep the summary professional and easy to read."""
        response = await self._safe_generate(self.model_id, [part, prompt], None)
        return response.text.strip()

    async def analyze_coding_error(self, image_path: str) -> str:
        part = self._get_media_part(image_path)
        prompt = "Analyze the code and error message in this screenshot. Explain what's wrong and suggest a fix."
        response = await self._safe_generate(self.model_id, [part, prompt], None)
        return response.text.strip()

    async def verify_screen_state(self, image_path: str, condition: str) -> Dict[str, Any]:
        part = self._get_media_part(image_path)
        prompt = f"Does the screen state meet this condition: '{condition}'? Return JSON: {{\"success\": bool, \"issues\": \"string\"}}"
        response = await self._safe_generate(
            model=self.model_id,
            contents=[part, prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        try:
            return json.loads(response.text)
        except Exception:
            return {"success": False, "issues": "Failed to parse verification response"}

    async def wait_for_visual(self, condition: str, timeout_seconds: int = 15) -> bool:
        return True # Simplified: actual implementation would need a callback to capture screen

    async def generate_recovery_plan(self, task: Dict[str, Any], errors: List[str], status: str, image_path: Optional[str] = None) -> List[Dict[str, Any]]:
        parts = [f"Task failed: {task}. Errors: {errors}. Current status: {status}. Generate a 1-3 step recovery plan."]
        if image_path:
            parts.append(self._get_media_part(image_path))
            
        prompt = "Return ONLY a JSON array of tasks for recovery. Actions: " + ", ".join(self.action_space.keys())
        parts.append(prompt)
        
        response = await self._safe_generate(
            model=self.model_id,
            contents=parts,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        try:
            data = json.loads(response.text)
            return data if isinstance(data, list) else data.get('tasks', [])
        except Exception:
            return []

    def _parse_slash_commands(self, command: str) -> tuple[str, dict]:
        """Parse slash commands from user input. Returns (clean_command, flags)"""
        flags = {
            "visual_memory": False,
            "deep_think": False,
            "screen": False,
            "work": False,
        }
        
        clean_command = command
        
        # /vm or /visual - enable visual memory
        if command.startswith("/vm ") or command.startswith("/visual "):
            flags["visual_memory"] = True
            clean_command = command.split(" ", 1)[1] if " " in command else ""
        
        # /think - enable deep thinking
        elif command.startswith("/think "):
            flags["deep_think"] = True
            clean_command = command.split(" ", 1)[1] if " " in command else ""
        
        # /screen - analyze current screen
        elif command.startswith("/screen ") or command == "/screen":
            flags["screen"] = True
            clean_command = command.split(" ", 1)[1] if " " in command else "analyze screen"
        
        # /work - enable work/task automation mode
        elif command.startswith("/work "):
            flags["work"] = True
            clean_command = command.split(" ", 1)[1] if " " in command else ""
        
        # Multiple flags: /vm /think query
        if "/vm" in clean_command:
            flags["visual_memory"] = True
            clean_command = clean_command.replace("/vm", "").strip()
        if "/visual" in clean_command:
            flags["visual_memory"] = True
            clean_command = clean_command.replace("/visual", "").strip()
        if "/think" in clean_command:
            flags["deep_think"] = True
            clean_command = clean_command.replace("/think", "").strip()
        if "/screen" in clean_command:
            flags["screen"] = True
            clean_command = clean_command.replace("/screen", "").strip()
        if "/work" in clean_command:
            flags["work"] = True
            clean_command = clean_command.replace("/work", "").strip()
        
        cmd_lower = clean_command.lower()
        
        if not flags["visual_memory"]:
            visual_keywords = [
                "screen", "earlier", "ago", "before", "previous", "last time",
                "what was", "what did", "show me what", "remember when",
                "minutes ago", "hours ago", "seen", "looked at", "viewing",
                "on my screen", "my screen", "was on screen", "displayed",
                "what i was doing", "what was i doing", "doing earlier",
                "history", "recall", "what happened"
            ]
            if any(kw in cmd_lower for kw in visual_keywords):
                flags["visual_memory"] = True
        
        if not flags["work"]:
            work_keywords = [
                "automate", "do this for me", "run this", "execute", "perform",
                "open", "launch", "start", "close", "click", "type", "press",
                "fill out", "fill in", "submit", "download", "upload", "save",
                "copy", "paste", "move", "delete", "create", "make a", "set up",
                "install", "uninstall", "schedule", "send", "post", "tweet",
                "email", "message", "book", "order", "buy", "purchase",
                "can you do", "please do", "go ahead and", "i need you to"
            ]
            if any(kw in cmd_lower for kw in work_keywords):
                flags["work"] = True
        
        if not flags["deep_think"]:
            think_keywords = [
                "think deeply", "analyze carefully", "consider all", "thorough analysis",
                "complex problem", "difficult question", "need detailed", "comprehensive",
                "in depth", "reason through", "think hard", "carefully consider"
            ]
            if any(kw in cmd_lower for kw in think_keywords):
                flags["deep_think"] = True
              
        return clean_command.strip(), flags

    async def execute_query(self, command: str, history: List[Dict[str, Any]] = None, context: Dict[str, Any] = None, visual_history: List[Dict[str, Any]] = None, thinking_level: Optional[str] = None):
        # Parse slash commands
        clean_command, flags = self._parse_slash_commands(command)
        
        # Override thinking level if /think used
        if flags["deep_think"] and not thinking_level:
            thinking_level = "deep"
        
        # Work mode - agentic task execution
        work_mode = flags["work"]
        
        await self.emit_thought(f"Analyzing command: {clean_command}")

        visual_parts = []
        media_parts = []
        
        # Handle uploaded files in context
        if context and context.get('selected_files'):
            for f_path in context['selected_files']:
                try:
                    media_parts.append(self._get_media_part(f_path))
                except Exception as e:
                    logger.error(f"Failed to load context file {f_path}: {e}")

        uploaded_file_info = ""
        attached_file_path = ""
        file_content_instructions = ""
        if media_parts:
            uploaded_file_info = f"- User uploaded {len(media_parts)} file(s) - YOU CAN SEE AND READ THE FULL CONTENT OF THESE FILES.\n"
            file_content_instructions = """
FILE CONTENT AVAILABLE: You have access to the full content of the uploaded file(s).
- If user asks to fill a form using this file (e.g., CV, resume, document), EXTRACT the relevant data from the file content and use it to fill the form fields.
- Use scan_screen to detect form fields, then fill_form with data extracted from the uploaded file.
- Example: If user uploads CV and says "fill this form", extract name, email, phone, experience, etc. from the CV content and put those values in the form fields.
"""
        if context and context.get('uploaded_file'):
            attached_file_path = f"- ATTACHED FILE PATH: {context['uploaded_file']} (Use attach_file action to send this file)\n"

        windows_info = ""
        if context and context.get('all_windows'):
            windows_info = "- Visible Windows:\n" + "\n".join([f"  * {w['title']} ({w['app']})" for w in context['all_windows'][:5]]) + "\n"

        history_context = ""
        if history:
            history_context = "- Recent Chat History:\n" + "\n".join([f"  {m['role'].upper()}: {m['content'][:200]}" for m in history[-5:]])

        user_memory = ""

        # Visual memory ONLY loaded when /vm command is used
        if visual_history and flags["visual_memory"]:
            await self.emit_thought("Loading visual memory...")
            # Sample frames based on query type
            if len(visual_history) <= 5:
                selected_frames = visual_history
            else:
                step = max(1, len(visual_history) // 5)
                selected_frames = visual_history[::step][-5:]
            
            for frame in selected_frames:
                try:
                    part = self._get_media_part(frame["path"])
                    visual_parts.append(part)
                except Exception as e:
                    logger.debug(f"Skipping frame: {e}")
            
            if visual_parts:
                visual_parts.insert(0, types.Part.from_text(text="[VISUAL HISTORY - User requested /vm]"))

        work_rules = ""
        if work_mode:
            work_rules = """
WORK MODE ENABLED (/work):
You are in AUTONOMOUS EXECUTION mode. Execute the task efficiently and completely WITHOUT waiting for user input.
- Do NOT set "wait_for_user": true
- Do NOT ask for confirmation - just execute
- Chain multiple actions together to complete the entire workflow
- Be thorough: open apps, navigate, type, click, submit - do it all
- If you need to send an email: open the email client/website, compose, enter recipient, subject, body, and send
- If you need to open an app: find and launch it, wait for it to load, then continue
- Always verify actions completed before moving to next step
- Use parallel_group for independent actions that can run together
"""

        browser_url = context.get('browser_tab', {}).get('url') if context else None
        url_context = f"- Browser URL: {browser_url}\n" if browser_url else ""

        prompt = """
You are "Prism", a frontier AI agent powered by Gemini 3.
User Command: """ + clean_command + """

""" + user_memory + """

Context:
- Files: """ + str(context.get('selected_files', []) if context else []) + """
""" + uploaded_file_info + attached_file_path + """- Active: """ + str(context.get('active_window', 'Unknown') if context else 'Unknown') + """
""" + windows_info + """
""" + url_context + """- Clipboard: """ + str(context.get('clipboard', '') if context else '') + """
""" + history_context + """

""" + file_content_instructions + """

""" + work_rules + """

GEMINI 3 REASONING:
Leverage your native thinking capabilities. Break complex tasks into efficient chains.
Support PARALLEL execution for independent subtasks.
If the context is massive (long PDFs/history), analyze it thoroughly in one pass.

  If the user is just chatting, greeting you, or asking a question that doesn't require automation, return a single 'reply' task with the full response.

      Return ONLY JSON:
      {
        "intent": "str",
        "is_guided": bool,
        "source_url": "str or null",
        "tasks": [
          {
            "action": "str", 
            "params": {}, 
            "description": "Brief technical summary for the progress bar (e.g. 'Greeting user')",
            "narration": "What to say to the user if in guided mode",
            "annotation": { "type": "circle", "element": "..." },
            "wait_for_user": bool,
            "parallel_group": 0
          }
        ]
      }

ACTIONS: """ + ", ".join(self.action_space.keys()) + """.

###############################################################################
#                    CRITICAL: LITERAL INTERPRETATION RULES                   #
###############################################################################

**GOLDEN RULE**: Do EXACTLY what the user asks. NOTHING MORE. NOTHING LESS.

- If user says "open Chrome" -> ONLY open Chrome. Do NOT navigate anywhere.
- If user says "open Chrome and go to YouTube" -> Open Chrome AND navigate to YouTube.
- If user says "turn on Bluetooth" -> ONLY toggle Bluetooth. Don't open Settings unless necessary.

**PARSING THE USER'S COMMAND**:
1. Identify the EXPLICIT actions requested (usually connected by "and", "then", comma, or period)
2. For EACH explicit action, generate the necessary steps
3. Do NOT add implied actions the user didn't ask for
4. Do NOT "help" by going somewhere after opening an app unless they said to

**EXAMPLES OF CORRECT LITERAL INTERPRETATION**:

User: "Open Chrome"
CORRECT:
[
  {"action": "open_app", "params": {"app_name": "chrome"}, "description": "Opening Chrome"},
  {"action": "wait", "params": {"seconds": 2}, "description": "Waiting for Chrome"},
  {"action": "reply", "params": {"message": "Done! Chrome is now open."}, "description": "Task complete"}
]
WRONG (adds unwanted navigation):
[
  {"action": "open_app", "params": {"app_name": "chrome"}, "description": "Opening Chrome"},
  {"action": "navigate_url", "params": {"url": "https://google.com"}, "description": "Going to Google"}  // USER DID NOT ASK FOR THIS!
]

User: "Open Chrome and go to YouTube"
CORRECT:
[
  {"action": "open_app", "params": {"app_name": "chrome"}, "description": "Opening Chrome"},
  {"action": "wait", "params": {"seconds": 2}, "description": "Waiting for Chrome"},
  {"action": "navigate_url", "params": {"url": "https://youtube.com"}, "description": "Navigating to YouTube"},
  {"action": "reply", "params": {"message": "Done! Chrome is open with YouTube."}, "description": "Task complete"}
]

User: "Open Settings"
CORRECT:
[
  {"action": "open_app", "params": {"app_name": "settings"}, "description": "Opening Settings"},
  {"action": "wait", "params": {"seconds": 2}, "description": "Waiting for Settings"},
  {"action": "reply", "params": {"message": "Settings is now open."}, "description": "Task complete"}
]
WRONG (navigates without being asked):
[
  {"action": "open_app", "params": {"app_name": "settings"}, "description": "Opening Settings"},
  {"action": "visual_click", "params": {"element": "System"}, "description": "Going to System"}  // NOT REQUESTED!
]

User: "Turn on Bluetooth"
CORRECT:
[
  {"action": "toggle_bluetooth", "params": {"enable": true}, "description": "Turning on Bluetooth"},
  {"action": "reply", "params": {"message": "Bluetooth is now on."}, "description": "Task complete"}
]

User: "Open Settings and turn on Bluetooth"
CORRECT:
[
  {"action": "open_app", "params": {"app_name": "settings"}, "description": "Opening Settings"},
  {"action": "wait", "params": {"seconds": 2}, "description": "Waiting for Settings"},
  {"action": "visual_click", "params": {"element": "Bluetooth & devices or Devices"}, "description": "Going to Bluetooth settings"},
  {"action": "wait", "params": {"seconds": 1}, "description": "Waiting for page"},
  {"action": "visual_click", "params": {"element": "Bluetooth toggle"}, "description": "Turning on Bluetooth"},
  {"action": "reply", "params": {"message": "Done! Opened Settings and turned on Bluetooth."}, "description": "Task complete"}
]

###############################################################################
#                         END LITERAL INTERPRETATION RULES                    #
###############################################################################

RULES:
1. 'reply': Use this for conversation or final answers. The actual message MUST be in params: { "message": "The full response content" }. 
2. Priority: For simple questions/chat, ONLY return a 'reply' task. Do NOT include unnecessary 'analyze_screen' or 'read_files' unless specifically needed to answer the question.
3. If you used information from the provided Browser URL, include it in 'source_url'.
4. Long Context: Use your window to cross-reference multiple large files or long histories.
5. Multimodal: Analyze any provided images/videos/PDFs/audio.
6. 'scroll': Params: { "direction": "up|down", "amount": 3 }. Smart smooth scrolling.
8. 'scroll_to_element': Params: { "element": "description", "direction": "down", "max_scrolls": 10 }. Scrolls until element is found.
9. 'drag_drop': Params: { "start": { "element": "..." }, "end": { "element": "..." } } or { "start": { "x": 100, "y": 200 }, "end": { "x": 300, "y": 400 } }.
10. 'switch_window': Params: { "window": "window name" } or empty for Alt+Tab.
11. 'snap_window': Params: { "direction": "left|right" }. Snaps window to half screen.
12. 'switch_tab': Params: { "direction": "next|prev" }.
13. 'search_in_page': Params: { "text": "search query" }. Opens Ctrl+F and types search.
14. 'double_click', 'right_click', 'hover', 'triple_click': Params: { "element": "description" } or { "x": 100, "y": 200 }.
15. 'visual_click': Params: { "element": "description of what to click" }. Uses vision to find and click. ALWAYS add a 'wait' task after visual_click to let the UI respond.
16. 'analyze_screen': No params. Returns detailed analysis of current screen state.
17. 'summarize': No params. Returns a concise summary of the current screen/page content.
18. 'navigate_url': Params: { "url": "https://example.com" }. Navigates to URL in the ACTIVE browser window using keyboard shortcuts (Ctrl+L, type, Enter). Use this AFTER opening a browser with 'open_app'. Do NOT use browser_navigate if Chrome is already open - use navigate_url instead.
19. 'wait': ALWAYS include wait tasks (1-3 seconds) between actions that change UI state (opening apps, clicking buttons, navigating). This is CRITICAL for reliable execution.
20. 'toggle_bluetooth': PREFERRED for Bluetooth control. Params: { "enable": true/false }. Directly toggles Bluetooth on Windows without opening Settings. Use this instead of open_app + visual_click for Bluetooth.
21. 'system_setting': For other system settings. Params: { "setting": "bluetooth", "action": "enable"/"disable"/"toggle" }.

IMPORTANT SYSTEM SETTINGS SHORTCUTS:
- For "turn on/off Bluetooth": Use 'toggle_bluetooth' action directly. DO NOT open Settings app.
- For "enable/disable Bluetooth": Use 'toggle_bluetooth' with enable: true/false.

FILE ATTACHMENT WORKFLOW (for "send this file to X", "attach this to Y", etc.):
When user uploads a file and asks to send/attach it somewhere:
1. Open the target app (Discord, email client, etc.)
2. Navigate to the recipient/contact (visual_click on search, type name, click contact)
3. Click the attach/paperclip button
4. Use 'attach_file' action (it automatically uses the uploaded file path)
5. Click send button
6. Reply confirming the file was sent

Example: "Send this PDF to Alex on Discord"
[
  {"action": "open_app", "params": {"app_name": "discord"}, "description": "Opening Discord"},
  {"action": "wait", "params": {"seconds": 2}, "description": "Waiting for Discord"},
  {"action": "visual_click", "params": {"element": "Search or start a new chat"}, "description": "Clicking search"},
  {"action": "type_text", "params": {"text": "Alex"}, "description": "Typing contact name"},
  {"action": "wait", "params": {"seconds": 1}, "description": "Waiting for results"},
  {"action": "visual_click", "params": {"element": "Alex contact in search results"}, "description": "Selecting contact"},
  {"action": "wait", "params": {"seconds": 1}, "description": "Waiting for chat"},
  {"action": "visual_click", "params": {"element": "Attach or paperclip icon"}, "description": "Clicking attach"},
  {"action": "wait", "params": {"seconds": 0.5}, "description": "Waiting for menu"},
  {"action": "visual_click", "params": {"element": "Document option"}, "description": "Selecting document type"},
  {"action": "wait", "params": {"seconds": 1}, "description": "Waiting for file dialog"},
  {"action": "attach_file", "params": {"method": "dialog"}, "description": "Selecting the uploaded file"},
  {"action": "wait", "params": {"seconds": 1}, "description": "Waiting for upload"},
  {"action": "visual_click", "params": {"element": "Send button"}, "description": "Sending file"},
  {"action": "reply", "params": {"message": "Done! I sent the PDF to Alex on Discord."}, "description": "Task complete"}
]

WORKFLOW PATTERNS:
- Open app + do something: open_app -> wait(2s) -> action -> wait(1s) -> next action -> reply
- Settings navigation: open_app(settings) -> wait(2s) -> visual_click(menu) -> wait(1s) -> visual_click(toggle/button) -> reply
- Browser + URL: open_app(chrome) -> wait(2s) -> navigate_url -> reply
- BLUETOOTH: toggle_bluetooth(enable: true/false) -> reply (DO NOT open Settings!)

###############################################################################
#                    BROWSER AUTOMATION (web_* actions)                       #
###############################################################################

IMPORTANT: For tasks inside Chrome/web pages (Gmail compose, YouTube search, clicking web buttons),
use web_* actions instead of visual_click. They are MORE RELIABLE and FASTER.

**WHEN TO USE web_* actions:**
- Clicking buttons/links in web pages by their text: web_click_text
- Filling search boxes or form fields: web_type or web_type_submit
- Navigating to websites: web_navigate
- Gmail compose: web_gmail_compose
- YouTube search: web_search_youtube
- Google search: web_search_google
- Pressing Enter/Tab in browser: web_press_key

**BROWSER AUTOMATION EXAMPLES:**

User: "Search for cats on YouTube"
CORRECT:
[
  {"action": "web_search_youtube", "params": {"query": "cats"}, "description": "Searching YouTube for cats"},
  {"action": "wait", "params": {"seconds": 2}, "description": "Waiting for results"},
  {"action": "reply", "params": {"message": "Done! Searched for cats on YouTube."}, "description": "Task complete"}
]

User: "Click the Compose button in Gmail"
CORRECT:
[
  {"action": "web_navigate", "params": {"url": "https://mail.google.com"}, "description": "Opening Gmail"},
  {"action": "wait", "params": {"seconds": 3}, "description": "Waiting for Gmail to load"},
  {"action": "web_click_text", "params": {"text": "Compose"}, "description": "Clicking Compose button"},
  {"action": "wait", "params": {"seconds": 1}, "description": "Waiting for compose window"},
  {"action": "reply", "params": {"message": "Done! Opened Gmail compose."}, "description": "Task complete"}
]

User: "Send an email to john@example.com with subject Hello"
CORRECT:
[
  {"action": "web_gmail_compose", "params": {"to": "john@example.com", "subject": "Hello"}, "description": "Opening Gmail compose"},
  {"action": "wait", "params": {"seconds": 2}, "description": "Waiting for compose window"},
  {"action": "reply", "params": {"message": "Done! Opened Gmail compose with recipient and subject filled."}, "description": "Task complete"}
]

User: "Search Google for best restaurants near me"
CORRECT:
[
  {"action": "web_search_google", "params": {"query": "best restaurants near me"}, "description": "Searching Google"},
  {"action": "wait", "params": {"seconds": 2}, "description": "Waiting for results"},
  {"action": "reply", "params": {"message": "Done! Searched Google for best restaurants near me."}, "description": "Task complete"}
]

User: "Go to twitter.com and click on the search box"
CORRECT:
[
  {"action": "web_navigate", "params": {"url": "https://twitter.com"}, "description": "Navigating to Twitter"},
  {"action": "wait", "params": {"seconds": 3}, "description": "Waiting for page load"},
  {"action": "web_click", "params": {"selector": "Search", "by": "placeholder"}, "description": "Clicking search box"},
  {"action": "reply", "params": {"message": "Done! Opened Twitter and focused the search box."}, "description": "Task complete"}
]

User: "Fill the login form with email test@test.com and password secret123"
CORRECT:
[
  {"action": "web_fill_form", "params": {"fields": {"Email": "test@test.com", "Password": "secret123"}}, "description": "Filling login form"},
  {"action": "wait", "params": {"seconds": 1}, "description": "Waiting"},
  {"action": "reply", "params": {"message": "Done! Filled the login form."}, "description": "Task complete"}
]

**CHOOSE THE RIGHT ACTION:**
- For WEB/CHROME tasks: Use web_* actions (more reliable, can interact with page elements directly)
- For DESKTOP tasks: Use visual_click, open_app, type_text (for non-browser apps)
- If user says "in Chrome" or mentions a website: Default to web_* actions

ALWAYS end with a 'reply' task confirming what was done.
"""
        contents = visual_parts + media_parts + [types.Part.from_text(text=prompt)]
        
        config = self.config
        if thinking_level:
            config = types.GenerateContentConfig(
                tools=self.config.tools,
                thinking_config=self._get_thinking_config(thinking_level)
            )

        response = await self._safe_generate(self.model_id, contents, config)
        
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
            
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"intent": "Error", "tasks": []}
