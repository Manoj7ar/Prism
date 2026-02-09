import json
import logging
import asyncio
import time
from typing import Dict, Any, Optional, List
from google.genai import types

logger = logging.getLogger("IDEDelegator")

IDE_APPS = {
    "cursor": {"name": "Cursor", "chat_shortcut": ["ctrl", "l"], "chat_shortcut_mac": ["command", "l"]},
    "code": {"name": "VS Code", "chat_shortcut": ["ctrl", "shift", "i"], "chat_shortcut_mac": ["command", "shift", "i"]},
    "antigravity": {"name": "AntiGravity", "chat_shortcut": ["ctrl", "k"], "chat_shortcut_mac": ["command", "k"]},
    "windsurf": {"name": "Windsurf", "chat_shortcut": ["ctrl", "l"], "chat_shortcut_mac": ["command", "l"]},
    "zed": {"name": "Zed", "chat_shortcut": ["ctrl", "shift", "a"], "chat_shortcut_mac": ["command", "shift", "a"]},
    "pycharm": {"name": "PyCharm", "chat_shortcut": ["alt", "enter"], "chat_shortcut_mac": ["option", "enter"]},
    "webstorm": {"name": "WebStorm", "chat_shortcut": ["alt", "enter"], "chat_shortcut_mac": ["option", "enter"]},
    "idea": {"name": "IntelliJ IDEA", "chat_shortcut": ["alt", "enter"], "chat_shortcut_mac": ["option", "enter"]},
}

PROMPT_GENERATOR_SYSTEM = """
You are a Master Prompt Engineer for AI coding assistants. Your job is to transform a user's casual question about their code/screen into a precise, actionable prompt that will get the best results from an IDE's AI assistant (like Cursor, VS Code Copilot, etc.).

## Rules:
1. Be SPECIFIC and ACTIONABLE - the IDE AI should know exactly what to do
2. Include relevant context from the user's question and screen state
3. If the user referenced "that thing" or "what I was doing" - use the visual context to fill in the blanks
4. Format for IMPLEMENTATION - the IDE AI will write/modify code
5. Keep it concise but complete (under 500 chars ideally)
6. Start with a clear action verb: "Implement", "Fix", "Add", "Refactor", "Create", etc.

## Output Format (JSON only):
{
  "prompt": "The optimized prompt to send to the IDE AI",
  "confidence": 0.0-1.0,
  "needs_clarification": false,
  "clarification_question": null
}

If the user's intent is too vague even with visual context, set needs_clarification=true and provide a clarification_question.
"""

class IDEDelegator:
    def __init__(self, prism_client):
        self.prism_client = prism_client
        self.pending_delegation = None
        
    def detect_ide(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        active_app = context.get("active_window", "").lower()
        active_title = context.get("active_title", "").lower()
        
        for ide_key, ide_info in IDE_APPS.items():
            if ide_key in active_app or ide_key in active_title or ide_info["name"].lower() in active_title:
                return {
                    "detected": True,
                    "ide_key": ide_key,
                    "ide_name": ide_info["name"],
                    "chat_shortcut": ide_info["chat_shortcut"],
                    "chat_shortcut_mac": ide_info["chat_shortcut_mac"]
                }
        
        code_patterns = ["visual studio code", "vs code", ".py -", ".js -", ".ts -", ".tsx -", ".jsx -", ".go -", ".rs -", ".cpp -", ".c -"]
        for pattern in code_patterns:
            if pattern in active_title:
                return {
                    "detected": True,
                    "ide_key": "code",
                    "ide_name": "VS Code",
                    "chat_shortcut": ["ctrl", "shift", "i"],
                    "chat_shortcut_mac": ["command", "shift", "i"]
                }
        
        return {"detected": False}

    async def generate_ide_prompt(self, user_query: str, context: Dict[str, Any], visual_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        await self.prism_client.emit_thought("Generating optimized prompt for IDE AI...")
        
        visual_parts = []
        if visual_history and len(visual_history) > 0:
            latest_frame = visual_history[-1]
            try:
                part = self.prism_client._get_media_part(latest_frame["full_path"])
                visual_parts.append(part)
            except Exception as e:
                logger.error(f"Failed to load frame for IDE prompt: {e}")

        input_data = {
            "user_query": user_query,
            "active_ide": context.get("active_window"),
            "window_title": context.get("active_title"),
            "recent_files": context.get("recent_files", [])[:5],
        }

        prompt = f"{PROMPT_GENERATOR_SYSTEM}\n\nINPUT:\n{json.dumps(input_data, indent=2)}"
        contents = visual_parts + [types.Part.from_text(text=prompt)]

        try:
            response = await self.prism_client.client.aio.models.generate_content(
                model=self.prism_client.model_id,
                contents=contents,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            result = json.loads(response.text)
            return result
        except Exception as e:
            logger.error(f"IDE prompt generation failed: {e}")
            return {
                "prompt": user_query,
                "confidence": 0.5,
                "needs_clarification": False
            }

    async def offer_delegation(self, user_query: str, context: Dict[str, Any], visual_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        ide_info = self.detect_ide(context)
        
        if not ide_info.get("detected"):
            return {"should_delegate": False}

        generated = await self.generate_ide_prompt(user_query, context, visual_history)
        
        if generated.get("needs_clarification"):
            return {
                "should_delegate": False,
                "needs_clarification": True,
                "clarification_question": generated.get("clarification_question")
            }

        self.pending_delegation = {
            "ide_info": ide_info,
            "prompt": generated.get("prompt"),
            "original_query": user_query,
            "timestamp": time.time()
        }

        return {
            "should_delegate": True,
            "ide_name": ide_info["ide_name"],
            "generated_prompt": generated.get("prompt"),
            "confidence": generated.get("confidence", 0.8),
            "offer_message": f"I see you're in {ide_info['ide_name']}. Want me to have the IDE's AI implement this? I've prepared this prompt:\n\n\"{generated.get('prompt')}\"\n\nSay 'yes' to send it to {ide_info['ide_name']}'s AI chat."
        }

    async def execute_delegation(self, desktop_automation) -> Dict[str, Any]:
        if not self.pending_delegation:
            return {"success": False, "error": "No pending delegation"}

        ide_info = self.pending_delegation["ide_info"]
        prompt = self.pending_delegation["prompt"]
        
        await self.prism_client.emit_thought(f"Sending prompt to {ide_info['ide_name']} AI...")

        try:
            import platform
            system = platform.system()
            shortcut = ide_info["chat_shortcut_mac"] if system == "Darwin" else ide_info["chat_shortcut"]
            
            import pyautogui
            pyautogui.hotkey(*shortcut)
            await asyncio.sleep(0.5)
            
            pyautogui.write(prompt, interval=0.01)
            await asyncio.sleep(0.2)
            
            pyautogui.press('enter')
            
            self.pending_delegation = None
            
            return {
                "success": True,
                "ide_name": ide_info["ide_name"],
                "prompt_sent": prompt
            }
        except Exception as e:
            logger.error(f"IDE delegation failed: {e}")
            return {"success": False, "error": str(e)}

    def has_pending_delegation(self) -> bool:
        if not self.pending_delegation:
            return False
        if time.time() - self.pending_delegation.get("timestamp", 0) > 120:
            self.pending_delegation = None
            return False
        return True

    def clear_pending(self):
        self.pending_delegation = None
