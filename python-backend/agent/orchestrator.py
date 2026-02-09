import json
import logging
from typing import List, Dict, Any, Optional
from google.genai import types
from .prism_client import PrismClient

logger = logging.getLogger("IntentOrchestrator")

ORCHESTRATOR_SYSTEM_PROMPT = """
You are Prism's Intent Orchestrator. Analyze the user's screen state and query to determine the optimal mode and actions.

## Available Modes
- **work**: Code debugging, development tasks, technical problem-solving, automation
- **visual_memory**: Spatial recall, referencing previous screens/contexts
- **research**: Information gathering, comparative analysis
- **create**: Content generation, design, writing

## Input Format
You receive:
1. User query (text)
2. Screen analysis (visual context)
3. Active processes/applications
4. Recent session history (last 10 minutes)

## Output Format (JSON only)
{
  "mode": "work|visual_memory|research|create",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "sub_task": "specific_task_type",
  "context_signals": ["signal1", "signal2"],
  "recommended_tools": ["tool1", "tool2"],
  "proactive_actions": ["action1"]
}

## Detection Heuristics
- **work**: Code editors visible + error messages/stack traces + technical terminology + automation requests
- **visual_memory**: Vague references ("that thing from before") + no clear active task
- **research**: Multiple browser tabs + comparative language + information seeking
- **create**: Blank canvases + generative requests + design/writing tools

## Context Signals to Detect
- Frustration: Rapid undo, tab switching, repeated attempts
- Confusion: Long pauses, help queries, scattered attention
- Flow state: Steady progress, minimal context switching
- Context switch: Abrupt change in application/content type

Prioritize **implicit intent** over explicit keywords. The user should never need to say "switch to work mode."
"""

class IntentOrchestrator:
    def __init__(self, prism_client: PrismClient):
        self.prism_client = prism_client

    async def orchestrate(self, query: str, context: Dict[str, Any], visual_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze intent and determine mode based on query and screen state"""
        await self.prism_client.emit_thought("Orchestrating intent from visual context...")

        visual_parts = []
        if visual_history:
            # Send the most recent frame for current screen analysis
            latest_frame = visual_history[-1]
            try:
                part = self.prism_client._get_media_part(latest_frame["full_path"])
                visual_parts.append(part)
            except Exception as e:
                logger.error(f"Failed to load latest frame: {e}")

        # Add temporal context (metadata of last few frames)
        history_summary = []
        for frame in visual_history[-10:]:
            history_summary.append({
                "time": frame.get("timestamp"),
                "app": frame.get("metadata", {}).get("app_name"),
                "title": frame.get("metadata", {}).get("title"),
                "is_coding": frame.get("metadata", {}).get("is_coding")
            })

        input_data = {
            "query": query,
            "active_app": context.get("active_window"),
            "all_windows": [w["title"] for w in context.get("all_windows", [])[:5]],
            "recent_history_metadata": history_summary
        }

        prompt = f"{ORCHESTRATOR_SYSTEM_PROMPT}\n\nINPUT:\n{json.dumps(input_data, indent=2)}"
        
        contents = visual_parts + [types.Part.from_text(text=prompt)]
        
        try:
            response = await self.prism_client.client.aio.models.generate_content(
                model=self.prism_client.model_id,
                contents=contents,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            result = json.loads(response.text)
            await self.prism_client.emit_thought(f"Detected mode: {result.get('mode')} (Confidence: {result.get('confidence')})")
            return result
        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            return {
                "mode": "work",
                "confidence": 0.5,
                "reasoning": "Fallback due to error",
                "sub_task": "general"
            }
