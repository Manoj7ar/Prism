from typing import Dict, Any, List, Optional
import os
import re
from .prism_client import PrismClient

MAX_TASKS_PER_PLAN = 50 # Increased for long-context chaining

class TaskPlanner:
    def __init__(self, prism_client: PrismClient):
        self.prism_client = prism_client

    def _extract_open_app_name(self, command: str) -> Optional[str]:
        raw = command.strip()
        lower = raw.lower()

        prefixes = ("open ", "launch ", "start ")
        prefix = next((p for p in prefixes if lower.startswith(p)), None)
        if not prefix:
            return None

        app_part = raw[len(prefix):].strip()
        # Keep only the first clause for deterministic open-app intents.
        app_part = re.split(r"\b(and|then)\b|[,.!?]", app_part, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        app_part = re.sub(r"^(the\s+)?(app|application)\s+", "", app_part, flags=re.IGNORECASE).strip()
        return app_part or None

    def _has_non_reply_actions(self, tasks: List[Dict[str, Any]]) -> bool:
        return any((t.get("action") or "").strip() != "reply" for t in tasks)
    
    async def plan(self, command: str, context: Dict[str, Any], file_path: Optional[str] = None, history: List[Dict[str, str]] = None, visual_history: List[Dict[str, Any]] = None, orchestration: Dict[str, Any] = None) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """Plan a sequence of tasks based on user command and system context and history"""
        await self.prism_client.emit_thought(f"Analyzing command: \"{command}\"")
        if file_path:
            context['uploaded_file'] = file_path
            await self.prism_client.emit_thought(f"Processing uploaded file: {os.path.basename(file_path)}")
            
        # Use default thinking level for fast planning
        await self.prism_client.emit_thought("Planning execution strategy...")
        
        # Apply orchestration results to context/flags
        if orchestration:
            mode = orchestration.get('mode')
            context['detected_mode'] = mode
            context['sub_task'] = orchestration.get('sub_task')

        response = await self.prism_client.parse_command(command, context, history, visual_history)
        tasks = response.get('tasks', [])
        source_url = response.get('source_url')

        # Reliability fallback for simple "open <app>" commands.
        open_app_name = self._extract_open_app_name(command)
        if open_app_name and not self._has_non_reply_actions(tasks):
            await self.prism_client.emit_thought(
                f"Using deterministic app-launch fallback for '{open_app_name}'."
            )
            tasks = [
                {
                    "action": "open_app",
                    "params": {"app_name": open_app_name},
                    "description": f"Opening {open_app_name}"
                },
                {
                    "action": "wait",
                    "params": {"seconds": 0.6},
                    "description": f"Waiting for {open_app_name}"
                },
                {
                    "action": "reply",
                    "params": {"message": f"Done! Opened {open_app_name}."},
                    "description": "Task complete"
                }
            ]
        
        await self.prism_client.emit_thought(f"Generated plan with {len(tasks)} steps.")
        
        # Guardrail: Limit the number of tasks in a single plan
        if len(tasks) > MAX_TASKS_PER_PLAN:
            print(f"[GUARDRAIL] Planned {len(tasks)} tasks exceeds limit of {MAX_TASKS_PER_PLAN}. Truncating.")
            tasks = tasks[:MAX_TASKS_PER_PLAN]
            
        return tasks, source_url

    async def replan(self, failed_task: Dict[str, Any], error: str, history: List[Dict[str, str]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Adaptive replanning when a step fails"""
        await self.prism_client.emit_thought(f"Task failed: {failed_task.get('action')}. Error: {error}", type="error")
        await self.prism_client.emit_thought("Attempting to replan and recover...")
        prompt = f"""
ADAPTIVE REPLANNING (GEMINI 3):
The following task failed: {failed_task}
Error: {error}

Context:
- Active Window: {context.get('active_window')}
- Selected Files: {context.get('selected_files')}

Please suggest an alternative plan to achieve the user's original goal, leveraging your native thinking.
Return ONLY JSON tasks array.
"""
        # High thinking level for recovery reasoning (if supported by model)
        response = await self.prism_client.parse_command(prompt, context, history, thinking_level="high")
        tasks = response.get('tasks', [])
        await self.prism_client.emit_thought(f"New recovery plan generated with {len(tasks)} steps.")
        return tasks
