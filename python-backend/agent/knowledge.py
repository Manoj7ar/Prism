import json
import os
from typing import Dict, List, Any

KNOWLEDGE_FILE = "user_knowledge.json"

DEFAULT_SHORTCUTS = {
    "chrome": ["Open YouTube", "New Tab", "Search Google"],
    "notepad": ["New Note", "Save File"],
    "explorer": ["Open Downloads", "Open Documents", "New Folder"],
    "code": ["Debug Error", "Fix Code", "Explain Selection", "Run Terminal"],
    "cursor": ["Fix with AI", "Debug Error", "Explain Code", "New File"],
    "antigravity": ["AI Debug", "Fix Error", "Refactor Code", "Terminal"],
    "intellij": ["Reformat Code", "Run Debug", "Find Usage", "Build Project"],
    "pycharm": ["Run Script", "Debug Test", "Refactor", "Terminal"],
    "discord": ["Check Mentions", "Join Voice"],
    "spotify": ["Next Track", "Play/Pause", "Liked Songs"]
}

class KnowledgeSystem:
    def __init__(self):
        self.knowledge_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), KNOWLEDGE_FILE)
        self.data = self._load_knowledge()

    def _load_knowledge(self) -> Dict[str, Any]:
        if os.path.exists(self.knowledge_path):
            try:
                with open(self.knowledge_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading knowledge: {e}")
        
        return {
            "app_shortcuts": DEFAULT_SHORTCUTS,
            "usage_stats": {}
        }

    def _save_knowledge(self):
        try:
            with open(self.knowledge_path, 'w') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"Error saving knowledge: {e}")

    def get_shortcuts(self, app_name: str) -> List[str]:
        app_name = app_name.lower()
        # Try to find a match in shortcuts
        for key in self.data["app_shortcuts"]:
            if key in app_name or app_name in key:
                return self.data["app_shortcuts"][key]
        
        return ["Open App", "Help"]

    def track_action(self, app_name: str, action: str):
        app_name = app_name.lower()
        if app_name not in self.data["usage_stats"]:
            self.data["usage_stats"][app_name] = {}
        
        stats = self.data["usage_stats"][app_name]
        stats[action] = stats.get(action, 0) + 1
        
        # If an action becomes frequent, add it to shortcuts
        if stats[action] >= 3 and action not in self.get_shortcuts(app_name):
            if app_name not in self.data["app_shortcuts"]:
                self.data["app_shortcuts"][app_name] = []
            
            # Add to top of shortcuts if not already there
            if action not in self.data["app_shortcuts"][app_name]:
                self.data["app_shortcuts"][app_name].insert(0, action)
                # Keep only top 5
                self.data["app_shortcuts"][app_name] = self.data["app_shortcuts"][app_name][:5]
        
        self._save_knowledge()

knowledge_system = KnowledgeSystem()
