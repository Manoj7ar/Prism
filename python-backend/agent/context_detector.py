import pyperclip
import os
import psutil
import platform
import subprocess
from typing import Dict, List, Any

SYSTEM = platform.system()

if SYSTEM == "Windows":
    try:
        import win32gui
        import win32process
        import win32api
        import win32com.client
    except ImportError:
        pass

class ContextDetector:
    """Detects what user has selected or is looking at across platforms"""
    
    def get_context(self) -> Dict[str, Any]:
        """Get current user context with peripheral vision"""
        open_windows_info = self.get_open_windows()
        open_windows_titles = [w['title'] for w in open_windows_info]
        files_context = self.get_selected_files()
        
        return {
            "selected_files": files_context["all"],
            "selected_media": files_context["media"],
            "active_window": self.get_active_window(),
            "open_windows": open_windows_titles,
            "clipboard": self.get_clipboard(),
            "browser_tab": self.get_browser_tab(),
            "active_processes": self.get_active_processes()
        }
    
    def get_open_windows(self) -> List[Dict[str, Any]]:
        """Get list of all open window titles and their handles/identifiers"""
        if SYSTEM == "Windows":
            return self._get_open_windows_windows()
        elif SYSTEM == "Darwin":
            return self._get_open_windows_macos()
        elif SYSTEM == "Linux":
            return self._get_open_windows_linux()
        return []

    def _get_open_windows_windows(self) -> List[Dict[str, Any]]:
        windows = []
        def enum_handler(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    windows.append({"title": title, "hwnd": hwnd})
        try:
            win32gui.EnumWindows(enum_handler, None)
            return windows
        except Exception as e:
            print(f"Error enumerating windows: {e}")
            return []

    def _get_open_windows_macos(self) -> List[Dict[str, Any]]:
        try:
            script = 'tell application "System Events" to get name of every window of (every process whose background only is false)'
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            titles = [t.strip() for t in result.stdout.replace(',', '').split('\n') if t.strip()]
            return [{"title": t, "id": i} for i, t in enumerate(titles)]
        except Exception as e:
            print(f"Error enumerating macOS windows: {e}")
            return []

    def _get_open_windows_linux(self) -> List[Dict[str, Any]]:
        try:
            result = subprocess.run(['wmctrl', '-l'], capture_output=True, text=True)
            windows = []
            for line in result.stdout.strip().split('\n'):
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    windows.append({"title": parts[3], "id": parts[0]})
            return windows
        except Exception:
            try:
                result = subprocess.run(['xdotool', 'search', '--name', '.*'], capture_output=True, text=True)
                ids = result.stdout.strip().split('\n')
                windows = []
                for wid in ids:
                    title = subprocess.run(['xdotool', 'getwindowname', wid], capture_output=True, text=True).stdout.strip()
                    if title: windows.append({"title": title, "id": wid})
                return windows
            except Exception:
                return []

    def get_active_processes(self) -> List[str]:
        """Get list of common active processes for context"""
        common = ['chrome', 'outlook', 'excel', 'word', 'discord', 'code', 'cursor']
        active = []
        for proc in psutil.process_iter(['name']):
            try:
                name = proc.info['name'].lower()
                for c in common:
                    if c in name and name not in active:
                        active.append(name)
            except Exception:
                pass
        return active
    
    def find_window(self, search_term: str) -> Dict[str, Any]:
        """Find a window by title (case-insensitive partial match)"""
        open_windows = self.get_open_windows()
        search_term = search_term.lower()
        
        for window in open_windows:
            if search_term in window["title"].lower():
                return window
        return None
    
    def get_selected_files(self) -> Dict[str, List[str]]:
        """Get files selected in File Explorer / Finder / etc"""
        if SYSTEM == "Windows":
            return self._get_selected_files_windows()
        elif SYSTEM == "Darwin":
            return self._get_selected_files_macos()
        return {"all": [], "media": []}

    def _get_selected_files_windows(self) -> Dict[str, List[str]]:
        selected_files = []
        media_files = []
        try:
            shell = win32com.client.Dispatch("Shell.Application")
            windows = shell.Windows()
            media_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.mp4', '.mov', '.avi', '.mp3', '.wav', '.pdf']
            for window in windows:
                try:
                    if window.FullName and "explorer.exe" in window.FullName.lower():
                        items = window.Document.SelectedItems()
                        for item in items:
                            path = item.Path
                            selected_files.append(path)
                            if any(path.lower().endswith(ext) for ext in media_extensions):
                                media_files.append(path)
                except Exception: continue
            return {"all": list(set(selected_files)), "media": list(set(media_files))}
        except Exception:
            return {"all": [], "media": []}

    def _get_selected_files_macos(self) -> Dict[str, List[str]]:
        try:
            script = '''
            tell application "Finder"
                set selectionList to selection as alias list
                set out to ""
                repeat with i from 1 to count of selectionList
                    set out to out & POSIX path of item i of selectionList & "\n"
                end repeat
                return out
            end tell
            '''
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            paths = [p.strip() for p in result.stdout.split('\n') if p.strip()]
            media_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.mp4', '.mov', '.avi', '.mp3', '.wav', '.pdf']
            media = [p for p in paths if any(p.lower().endswith(ext) for ext in media_extensions)]
            return {"all": paths, "media": media}
        except Exception:
            return {"all": [], "media": []}

    def get_active_window_info(self) -> Dict[str, Any]:
        """Get title and app name of active window"""
        if SYSTEM == "Windows":
            return self._get_active_window_info_windows()
        elif SYSTEM == "Darwin":
            return self._get_active_window_info_macos()
        elif SYSTEM == "Linux":
            return self._get_active_window_info_linux()
        return {"title": "Desktop", "app_name": "Desktop", "is_coding": False}

    def _get_active_window_info_windows(self) -> Dict[str, Any]:
        try:
            ignored_names = ["electron", "python", "prism", "node", "bun", "powershell", "cmd", "taskmgr", "conhost"]
            ignored_titles = ["prism", "electron", "task manager"]

            def is_ignored(name, title):
                if not name: return True
                n_low = name.lower()
                t_low = title.lower() if title else ""
                return any(ign in n_low for ign in ignored_names) or any(ign in t_low for ign in ignored_titles)

            def get_info(h):
                if not h: return None, None, None
                try:
                    _, p = win32process.GetWindowThreadProcessId(h)
                    proc = psutil.Process(p)
                    n = proc.name().lower()
                    t = win32gui.GetWindowText(h)
                    return p, n, t
                except Exception:
                    return None, None, None

            cursor_pos = win32api.GetCursorPos()
            hwnd = win32gui.WindowFromPoint(cursor_pos)
            if hwnd: hwnd = win32gui.GetAncestor(hwnd, 2)
            
            _, app_name, title = get_info(hwnd)
            
            if not hwnd or is_ignored(app_name, title):
                hwnd = win32gui.GetForegroundWindow()
                _, app_name, title = get_info(hwnd)
                
                if not hwnd or is_ignored(app_name, title):
                    def enum_handler(h, results):
                        if win32gui.IsWindowVisible(h):
                            _, n, t = get_info(h)
                            if n and not is_ignored(n, t):
                                results.append((h, n, t))
                                return False
                        return True
                    results = []
                    win32gui.EnumWindows(enum_handler, results)
                    if results: hwnd, app_name, title = results[0]

            if not app_name: return {"title": "Desktop", "app_name": "Desktop"}

            app_name = app_name.replace(".exe", "").capitalize()
            # Normalization...
            for key in ["Chrome", "Explorer", "VS Code", "Cursor", "IntelliJ", "PyCharm", "Zed", "Sublime"]:
                if key.lower() in app_name.lower(): app_name = key; break

            is_coding = any(ide in app_name.lower() for ide in ["code", "cursor", "intellij", "pycharm", "zed", "sublime", "studio", "webstorm"])
            return {"title": title or "Desktop", "app_name": app_name, "is_coding": is_coding}
        except Exception:
            return {"title": "Desktop", "app_name": "Desktop", "is_coding": False}

    def _get_active_window_info_macos(self) -> Dict[str, Any]:
        try:
            script = '''
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
                set frontWindow to ""
                try
                    tell process frontApp
                        set frontWindow to name of front window
                    end tell
                end try
                return frontApp & "|||" & frontWindow
            end tell
            '''
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            parts = result.stdout.strip().split('|||')
            app_name = parts[0] if len(parts) > 0 else "Desktop"
            title = parts[1] if len(parts) > 1 else "Desktop"
            is_coding = any(ide in app_name.lower() for ide in ["code", "cursor", "intellij", "pycharm", "zed", "sublime", "studio", "terminal", "iterm"])
            return {"title": title, "app_name": app_name, "is_coding": is_coding}
        except Exception:
            return {"title": "Desktop", "app_name": "Desktop", "is_coding": False}

    def _get_active_window_info_linux(self) -> Dict[str, Any]:
        try:
            title = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'], capture_output=True, text=True).stdout.strip()
            pid = subprocess.run(['xdotool', 'getactivewindow', 'getwindowpid'], capture_output=True, text=True).stdout.strip()
            app_name = "Desktop"
            if pid:
                app_name = subprocess.run(['ps', '-p', pid, '-o', 'comm='], capture_output=True, text=True).stdout.strip()
            is_coding = any(ide in app_name.lower() for ide in ["code", "cursor", "intellij", "pycharm", "zed", "sublime", "studio", "terminal", "gnome-terminal", "konsole"])
            return {"title": title or "Desktop", "app_name": app_name or "Desktop", "is_coding": is_coding}
        except Exception:
            return {"title": "Desktop", "app_name": "Desktop", "is_coding": False}

    def capture_active_window(self) -> str:
        """Capture screenshot of active window and return path"""
        try:
            import pyautogui
            import time
            os.makedirs("temp", exist_ok=True)
            path = os.path.abspath(f"temp/active_window_{int(time.time())}.png")
            
            if SYSTEM == "Windows":
                hwnd = win32gui.GetForegroundWindow()
                rect = win32gui.GetWindowRect(hwnd)
                x, y, x1, y1 = rect
                screenshot = pyautogui.screenshot(region=(x, y, x1-x, y1-y))
            else:
                # On Mac/Linux, simpler to just take full screenshot or use app-specific logic
                # For now, full screenshot as fallback or try to get region
                screenshot = pyautogui.screenshot()
            
            screenshot.save(path)
            return path
        except Exception as e:
            print(f"Error capturing active window: {e}")
            return ""

    def get_active_window(self) -> str:
        """Get title of active window"""
        return self.get_active_window_info()["title"]
    
    def get_clipboard(self) -> str:
        """Get clipboard content"""
        try:
            return pyperclip.paste()
        except Exception:
            return ""
    
    def get_browser_tab(self) -> Dict[str, Any]:
        """Get current browser tab URL and title using UI Automation on Windows"""
        active_info = self.get_active_window_info()
        app_name = active_info["app_name"].lower()
        title = active_info["title"]
        
        url = None
        if SYSTEM == "Windows" and "chrome" in app_name:
            try:
                # Use UI Automation to find the address bar
                import comtypes.client
                from comtypes.gen import UIAutomationClient
                
                uia = comtypes.client.CreateObject(UIAutomationClient.CUIAutomation)
                window = uia.GetFocusedElement()
                
                # Walk up to the main window if needed
                while window:
                    if window.CurrentClassName == "Chrome_WidgetWin_1":
                        break
                    window = uia.CreateTreeWalker(uia.RawViewCondition).GetParentElement(window)
                
                if window:
                    # Find the address bar (Edit control)
                    condition = uia.CreatePropertyCondition(
                        UIAutomationClient.UIA_ControlTypePropertyId,
                        UIAutomationClient.UIA_EditControlTypeId
                    )
                    address_bar = window.FindFirst(UIAutomationClient.TreeScope_Descendants, condition)
                    
                    if address_bar:
                        # Get the URL from the Value pattern
                        pattern = address_bar.GetCurrentPattern(UIAutomationClient.UIA_ValuePatternId)
                        value_pattern = pattern.QueryInterface(UIAutomationClient.IUIAutomationValuePattern)
                        url = value_pattern.CurrentValue
                        if url and not url.startswith(("http://", "https://")):
                            url = "https://" + url
            except Exception as e:
                print(f"Error getting Chrome URL: {e}")
                # Fallback to a simpler search if focused element fails
                try:
                    shell = win32com.client.Dispatch("Shell.Application")
                    # This is more for IE/Explorer, but sometimes useful
                    pass
                except Exception:
                    pass

        browsers = ["chrome", "firefox", "brave", "safari", "edge"]
        is_browser = any(b in app_name for b in browsers)
        
        return {
            "url": url,
            "title": title if is_browser else None,
            "browser_name": app_name if is_browser else None
        }
