from google import genai
from google.genai import types
import os
import json
import asyncio
import base64
from typing import List, Dict, Any
from config import GEMINI_API_KEY, GEMINI_PRO_MODEL, GEMINI_FLASH_MODEL
from PIL import Image

class GeminiClient:
    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        self.client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1beta'})
        self.pro_model = GEMINI_PRO_MODEL
        self.flash_model = GEMINI_FLASH_MODEL
        
        self.total_tokens_used = 0
        self.last_usage = {}

    def _get_config(self, model_id: str) -> types.GenerateContentConfig:
        is_thinking = "thinking" in model_id.lower()
        kwargs = {"temperature": 0.0}
        if not is_thinking:
            kwargs['tools'] = [types.Tool(google_search=types.GoogleSearch())]
        return types.GenerateContentConfig(**kwargs)

    def _select_model(self, task_type: str, command: str = "") -> str:
        """Select model based on task complexity. Pro for 'pro' needs, Flash for 'light' works."""
        pro_tasks = ["parsing", "coding", "planning", "visual_history", "video_analysis", "complex_reply"]
        
        # If explicitly a pro task type
        if task_type in pro_tasks:
            return self.pro_model
            
        # Heuristic for command complexity if provided
        if command:
            command_lower = command.lower()
            # Complex reasoning or debugging needs Pro
            pro_keywords = ["fix", "error", "debug", "code", "explain", "summarize session", "why", "how to"]
            if any(kw in command_lower for kw in pro_keywords):
                return self.pro_model
                
            # Long commands often need more reasoning
            if len(command) > 100:
                return self.pro_model

        # Fallback to Flash for small light works
        return self.flash_model

    def _update_usage(self, response):
        """Update token usage metrics from response metadata"""
        try:
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                self.last_usage = {
                    "prompt_tokens": usage.prompt_token_count,
                    "candidates_tokens": usage.candidates_token_count,
                    "total_tokens": usage.total_token_count
                }
                self.total_tokens_used += usage.total_token_count
                print(f"[Gemini] Usage: {self.last_usage} | Session Total: {self.total_tokens_used}")
        except Exception as e:
            print(f"Error updating usage metadata: {e}")
    
    def _get_image_part(self, image_path: str) -> types.Part:
        """Helper to create an inline image part from a file path"""
        with open(image_path, "rb") as f:
            data = f.read()
        return types.Part.from_bytes(data=data, mime_type="image/png")

    def _select_relevant_frames(self, command: str, visual_history: List[Dict[str, Any]], max_frames: int = 20) -> List[Dict[str, Any]]:
        """Intelligently select frames based on the user's command and metadata"""
        if not visual_history:
            return []
            
        if len(visual_history) <= max_frames:
            return visual_history
            
        # 1. Always include the most recent 3 frames
        recent_frames = visual_history[-3:]
        remaining_history = visual_history[:-3]
        
        # 2. Extract keywords from command
        command_lower = command.lower()
        # Simple keyword extraction (exclude common small words)
        ignore_words = {"what", "was", "the", "this", "that", "how", "when", "where", "saw", "earlier", "on", "in", "my", "screen"}
        keywords = [w for w in re.findall(r'\w+', command_lower) if len(w) > 2 and w not in ignore_words]
        
        # 3. Find frames matching keywords in metadata (App, Title, and OCR Text)
        relevant_frames = []
        if keywords:
            for frame in remaining_history:
                metadata = frame.get("metadata", {})
                app_name = metadata.get("app_name", "").lower()
                title = metadata.get("title", "").lower()
                ocr_text = metadata.get("ocr_text", "").lower()
                
                if any(kw in app_name or kw in title or kw in ocr_text for kw in keywords):
                    relevant_frames.append(frame)
        
        # 4. If we found relevant frames, take up to 10 of them (spread out)
        final_selection = []
        if relevant_frames:
            step = max(1, len(relevant_frames) // 10)
            final_selection.extend(relevant_frames[::step][:10])
        
        # 5. Fill remaining slots with general historical samples
        slots_left = max_frames - len(recent_frames) - len(final_selection)
        if slots_left > 0:
            # Avoid re-adding frames already in final_selection or recent_frames
            already_selected_paths = {f["path"] for f in final_selection + recent_frames}
            general_history = [f for f in remaining_history if f["path"] not in already_selected_paths]
            
            if general_history:
                step = max(1, len(general_history) // slots_left)
                final_selection.extend(general_history[::step][:slots_left])
        
        # Add recent frames back
        final_selection.extend(recent_frames)
        
        # Sort by time to keep chronological order
        final_selection.sort(key=lambda x: x.get("time", 0))
        
        return final_selection

    async def parse_command(self, command: str, context: Dict[str, Any], history: List[Dict[str, str]] = None, visual_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Parse user command and understand intent with context, history, and visual session memory"""
        uploaded_file_info = ""
        if context.get('uploaded_file'):
            uploaded_file_info = f"- UPLOADED FILE: {context.get('uploaded_file')}\n"

        open_windows = context.get('open_windows', [])
        windows_info = "- Visible Windows: " + (", ".join(open_windows) if open_windows else "None")

        history_context = ""
        if history:
            history_context = "- Conversation History:\n"
            for msg in history:
                role = "User" if msg.get("role") == "user" else "Assistant"
                history_context += f"  {role}: {msg.get('content')}\n"

        # Prepare visual history parts
        visual_parts = []
        if visual_history:
            # Intelligently select relevant frames instead of brute force sampling
            selected_frames = self._select_relevant_frames(command, visual_history, max_frames=20)
            
            for frame in selected_frames:
                try:
                    part = self._get_image_part(frame["path"])
                    visual_parts.append(part)
                except Exception as e:
                    continue
            
            if visual_parts:
                visual_parts.insert(0, types.Part.from_text(text="[VISUAL SESSION HISTORY - Screens from the last hour of user activity]"))

        prompt = f"""
You are "Gemini Hands", a Windows automation agent.
User Command: {command}

Context:
- Files: {context.get('selected_files', [])}
{uploaded_file_info}- Active: {context.get('active_window', 'Unknown')}
{windows_info}
- Clipboard: {context.get('clipboard', '')[:200]}
{history_context}

VISUAL HISTORY INSTRUCTIONS:
The images provided represent a film strip of the user's screen history over the last hour. 
Use them to answer questions about past activity (e.g. "What was that error I saw earlier?", "What was the price on that site I visited?").

Return ONLY JSON:
{{
  "intent": "summary",
    "tasks": [
{{"action": "name", "params": {{}}, "description": "..."}}
]
}}

ACTIONS: read_and_summarize_files, browser_navigate, type_text, type_previous_result, press_keys, open_app, visual_click, wait, wait_for_visual, reply, debug_error.

RULES:
1. Use 'debug_error' whenever the user is in an IDE (e.g. VS Code, Cursor) and asks for help with code, fixing errors, or debugging.
2. Use 'browser_navigate' for ALL URLs, websites, or web tasks.
3. Use 'reply' for info questions, greetings, or conversational responses. ALWAYS include a "message" parameter in "params" for the reply action.
4. Use 'visual_click' for UI elements.
5. Be concise.
"""
        # Combine visual history with text prompt
        contents = visual_parts + [types.Part.from_text(text=prompt)]
        
        # Pro model for command parsing as it involves complex intent and visual history
        model_id = self._select_model("parsing", command)
        if visual_history:
            model_id = self._select_model("visual_history", command)

        response = self.client.models.generate_content(
            model=model_id,
            contents=contents,
            config=self._get_config(model_id)
        )
        self._update_usage(response)
        
        text = response.text.strip()
        print(f"[Gemini] Raw Response: {text}") # Debug logging
        if "```json" in text:

            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
            
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"intent": "Error", "tasks": []}

    async def generate_content(self, prompt: str, context_text: str = "") -> str:
        full_prompt = f"Context:\n{context_text}\n\nTask: {prompt}" if context_text else prompt
        model_id = self._select_model("complex_reply" if len(full_prompt) > 200 else "light_work", full_prompt)
        
        response = self.client.models.generate_content(
            model=model_id,
            contents=full_prompt,
            config=self._get_config(model_id)
        )
        self._update_usage(response)
        return response.text

    async def analyze_coding_error(self, screenshot_path: str) -> str:
        """Analyze a screenshot of an IDE for coding errors and provide fixes"""
        try:
            image_part = self._get_image_part(screenshot_path)
            prompt = """
            You are a Senior Coding Assistant. 
            Analyze this screenshot of the user's IDE/editor.
            1. Identify any visible errors (red squiggles, error logs, terminal output).
            2. Explain what the error is.
            3. Provide a clear solution or fix.
            4. If no error is visible, offer to explain the code or suggest improvements.
            
            Be concise and helpful. Use markdown.
            """
            
            model_id = self._select_model("coding")
            response = self.client.models.generate_content(
                model=model_id,
                contents=[image_part, prompt],
                config=self._get_config(model_id)
            )
            self._update_usage(response)
            return response.text
        except Exception as e:
            return f"Coding analysis failed: {str(e)}"

    async def transcribe(self, audio_path: str) -> str:
        try:
            # For audio, File API is still better/necessary
            audio_file = self.client.files.upload(path=audio_path)
            while audio_file.state == "PROCESSING":
                await asyncio.sleep(0.5)
                audio_file = self.client.files.get(name=audio_file.name)
            
            response = self.client.models.generate_content(
                model=self._select_model("light_work"),
                contents=[audio_file, "Transcribe. Return text only."]
            )
            try:
                self.client.files.delete(name=audio_file.name)
            except Exception:
                pass
            return response.text.strip()
        except Exception as e:
            return f"Error: {str(e)}"

    async def locate_element_visually(self, image_path: str, element_description: str, refined: bool = False) -> Dict[str, int]:
        """Locate element using inline data (much faster than File API)"""
        try:
            image_part = self._get_image_part(image_path)
            prompt = f"Find UI element: \"{element_description}\". Return [ymin, xmin, ymax, xmax] (0-1000)."
            
            model_id = self._select_model("light_work")
            response = self.client.models.generate_content(
                model=model_id,
                contents=[image_part, prompt],
                config=self._get_config(model_id)
            )
            text = response.text.strip()
            if "[" in text and "]" in text:
                text = text[text.find("["):text.rfind("]")+1]
            coords = json.loads(text)
            
            if len(coords) == 4:
                import pyautogui
                width, height = pyautogui.size()
                ymin, xmin, ymax, xmax = coords
                center_x = int(((xmin + xmax) / 2) * width / 1000)
                center_y = int(((ymin + ymax) / 2) * height / 1000)

                # SPEED OPTIMIZATION: Removed default refined pass. 
                # Only use if explicitly requested.
                if refined:
                    crop_size = 400
                    left = max(0, center_x - crop_size // 2)
                    top = max(0, center_y - crop_size // 2)
                    right = min(width, left + crop_size)
                    bottom = min(height, top + crop_size)
                    
                    img = Image.open(image_path)
                    crop_img = img.crop((left, top, right, bottom))
                    crop_img = crop_img.resize((800, 800), Image.Resampling.LANCZOS)
                    crop_path = "crop_refined_temp.png"
                    crop_img.save(crop_path)
                    
                    refined_coords = await self.locate_element_visually_in_crop(crop_path, element_description)
                    if os.path.exists(crop_path): os.remove(crop_path)
                        
                    if refined_coords:
                        ref_x = (refined_coords['x'] * crop_size) // 1000
                        ref_y = (refined_coords['y'] * crop_size) // 1000
                        return {"x": left + ref_x, "y": top + ref_y}

                return {"x": center_x, "y": center_y}
            return None
        except Exception as e:
            print(f"Visual detection error: {e}")
            return None

    async def locate_element_visually_in_crop(self, crop_path: str, description: str) -> Dict[str, int]:
        try:
            image_part = self._get_image_part(crop_path)
            prompt = f"In this crop, find: {description}. Return [ymin, xmin, ymax, xmax] (0-1000)."
            model_id = self._select_model("light_work")
            response = self.client.models.generate_content(
                model=model_id,
                contents=[image_part, prompt],
                config=self._get_config(model_id)
            )
            text = response.text.strip()
            if "[" in text and "]" in text:
                text = text[text.find("["):text.rfind("]")+1]
            coords = json.loads(text)
            if len(coords) == 4:
                ymin, xmin, ymax, xmax = coords
                return {"x": (xmin + xmax) // 2, "y": (ymin + ymax) // 2}
            return None
            except Exception:
                return None

    async def wait_for_visual(self, condition: str, timeout: int = 15) -> bool:
        """Faster waiting with inline data and 0.8s polling"""
        start_time = asyncio.get_event_loop().time()
        import pyautogui
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            temp_path = "wait_check_temp.png"
            pyautogui.screenshot().save(temp_path)
            
            try:
                image_part = self._get_image_part(temp_path)
                prompt = f"Is this condition met: '{condition}'? YES or NO."
                model_id = self._select_model("light_work")
                response = self.client.models.generate_content(
                    model=model_id,
                    contents=[image_part, prompt],
                    config=self._get_config(model_id)
                )
                if os.path.exists(temp_path): os.remove(temp_path)
                
                if "YES" in response.text.upper():
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.8) # Faster polling
        return False

    async def verify_screen_state(self, image_path: str, expected_state: str) -> Dict[str, Any]:
        """Verify screen state using inline data"""
        try:
            image_part = self._get_image_part(image_path)
            prompt = f"""Screenshot check. Expected: {expected_state}
Return JSON ONLY:
{{
  "success": bool,
  "popup_detected": bool,
  "issues": [],
  "current_state": "str",
  "suggestion": "str"
}}"""
            model_id = self._select_model("light_work")
            response = self.client.models.generate_content(
                model=model_id,
                contents=[image_part, prompt],
                config=self._get_config(model_id)
            )
            text = response.text.strip()
            if "{" in text and "}" in text:
                text = text[text.find("{"):text.rfind("}")+1]
            return json.loads(text)
        except Exception as e:
            return {"success": False, "issues": [str(e)]}

    async def generate_recovery_plan(self, failed_task: Dict[str, Any], issues: List[str], current_state: str, suggestion: str) -> List[Dict[str, Any]]:
        """Generate a quick recovery plan"""
        prompt = f"""Task failed: {failed_task}
Issues: {issues}
Current State: {current_state}
Suggestion: {suggestion}

Return ONLY a JSON array of 1-3 simple recovery tasks (actions).
"""
        response = await self.generate_content(prompt)
        text = response.strip()
        if "[" in text and "]" in text:
            text = text[text.find("["):text.rfind("]")+1]
        try:
            return json.loads(text)
        except Exception:
            return []

    async def analyze_failure_video(self, video_frames: List[str], error: str) -> str:
        try:
            parts = [self._get_image_part(f) for f in video_frames]
            prompt = f"Frames show failure with error: {error}. Explain briefly."
            model_id = self._select_model("video_analysis")
            response = self.client.models.generate_content(
                model=model_id,
                contents=parts + [prompt],
                config=self._get_config(model_id)
            )
            return response.text
        except Exception as e:
            return f"Analysis failed: {str(e)}"
