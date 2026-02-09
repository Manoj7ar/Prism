import json
import os
from typing import List, Dict, Any

class MemorySystem:
    def __init__(self, memory_file: str = "session_memory/user_memory.json"):
        self.memory_file = memory_file
        self.memory = {
            "habits": {},
            "past_commands": [],
            "preferences": {}
        }
        self._ensure_dir()
        self.load()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)

    def load(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r') as f:
                    self.memory = json.load(f)
            except Exception as e:
                print(f"[Memory] Failed to load: {e}")

    def save(self):
        try:
            with open(self.memory_file, 'w') as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            print(f"[Memory] Failed to save: {e}")

    def add_command(self, command: str, success: bool):
        self.memory["past_commands"].append({
            "command": command,
            "success": success
        })
        # Keep only last 50 commands
        self.memory["past_commands"] = self.memory["past_commands"][-50:]
        self.save()

    def update_habit(self, key: str, value: Any):
        self.memory["habits"][key] = value
        self.save()

    def get_context(self) -> str:
        """Returns a string representation of memory for prompting"""
        context = "User Habits & Preferences:\n"
        for k, v in self.memory["habits"].items():
            context += f"- {k}: {v}\n"
        
        if self.memory["past_commands"]:
            context += "\nRecent Successful Commands:\n"
            successes = [c["command"] for c in self.memory["past_commands"] if c["success"]][-5:]
            for cmd in successes:
                context += f"- {cmd}\n"
        
        return context

    def clear(self):
        self.memory = {
            "habits": {},
            "past_commands": [],
            "preferences": {}
        }
        self.save()

memory_system = MemorySystem()
