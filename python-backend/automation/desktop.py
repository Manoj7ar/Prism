import pyautogui
import time
import os
import logging
import platform
import subprocess
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger("DesktopAutomation")

SYSTEM = platform.system()

if SYSTEM == "Windows":
    import win32gui
    import win32con
    import win32process
    import win32api
elif SYSTEM == "Darwin":
    pass
elif SYSTEM == "Linux":
    pass

class DesktopAutomation:
    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.0 
        self.system = SYSTEM
    
    def type_text(self, text: str):
        pyautogui.write(text, interval=0.0)
        return f"Typed: {text[:50]}..."
    
    def press_keys(self, keys: list):
        pyautogui.hotkey(*keys)
        return f"Pressed: {' + '.join(keys)}"
    
    def click_at(self, x: int, y: int):
        pyautogui.click(x, y)
        return f"Clicked at ({x}, {y})"
    
    def double_click_at(self, x: int, y: int):
        pyautogui.doubleClick(x, y)
        return f"Double-clicked at ({x}, {y})"
    
    def right_click_at(self, x: int, y: int):
        pyautogui.rightClick(x, y)
        return f"Right-clicked at ({x}, {y})"
    
    def move_to(self, x: int, y: int):
        pyautogui.moveTo(x, y)
        return f"Moved to ({x}, {y})"
    
    def scroll(self, clicks: int, x: int = None, y: int = None):
        pyautogui.scroll(clicks, x, y)
        return f"Scrolled {clicks} clicks"
    
    def get_screenshot(self, output_path: str):
        screenshot = pyautogui.screenshot()
        screenshot.save(output_path)
        return output_path
    
    def get_screen_size(self) -> tuple:
        return pyautogui.size()
    
    def get_mouse_position(self) -> tuple:
        return pyautogui.position()

    def focus_window(self, hwnd_or_name):
        if self.system == "Windows":
            return self._focus_window_windows(hwnd_or_name)
        elif self.system == "Darwin":
            return self._focus_window_macos(hwnd_or_name)
        elif self.system == "Linux":
            return self._focus_window_linux(hwnd_or_name)
        return False

    def _focus_window_windows(self, hwnd):
        try:
            # Ensure the window is shown and restored
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            else:
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            
            # Bring to top
            win32gui.BringWindowToTop(hwnd)
            
            # Try setting foreground window directly first
            try:
                win32gui.SetForegroundWindow(hwnd)
                return True
            except:
                pass

            # Alt key trick to bypass focus restrictions
            pyautogui.press('alt')
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception as e:
            # Final attempt using thread attachment if everything else fails
            try:
                curr_thread = win32api.GetCurrentThreadId()
                fore_thread = win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[0]
                dest_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
                
                if fore_thread != dest_thread:
                    win32api.AttachThreadInput(curr_thread, fore_thread, True)
                    win32api.AttachThreadInput(curr_thread, dest_thread, True)
                    win32gui.SetForegroundWindow(hwnd)
                    win32api.AttachThreadInput(curr_thread, dest_thread, False)
                    win32api.AttachThreadInput(curr_thread, fore_thread, False)
                    return True
            except:
                pass
                
            logger.error(f"Error focusing window: {e}")
            return False

    def _focus_window_macos(self, app_name: str):
        try:
            script = f'''
            tell application "{app_name}"
                activate
            end tell
            '''
            subprocess.run(['osascript', '-e', script], check=True)
            return True
        except Exception as e:
            print(f"Error focusing window on macOS: {e}")
            return False

    def _focus_window_linux(self, window_name: str):
        try:
            result = subprocess.run(
                ['wmctrl', '-a', window_name],
                capture_output=True, text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            try:
                result = subprocess.run(
                    ['xdotool', 'search', '--name', window_name, 'windowactivate'],
                    capture_output=True, text=True
                )
                return result.returncode == 0
            except FileNotFoundError:
                print("Neither wmctrl nor xdotool found. Install one for window management on Linux.")
                return False

    def find_window(self, search_term: str) -> Optional[Any]:
        if self.system == "Windows":
            return self._find_window_windows(search_term)
        elif self.system == "Darwin":
            return self._find_window_macos(search_term)
        elif self.system == "Linux":
            return self._find_window_linux(search_term)
        return None

    def _find_window_windows(self, search_term: str):
        found_window = {"hwnd": None, "title": None}
        def enum_handler(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if search_term.lower() in title.lower():
                    found_window["hwnd"] = hwnd
                    found_window["title"] = title
        
        win32gui.EnumWindows(enum_handler, None)
        return found_window["hwnd"] if found_window["hwnd"] else None

    def _find_window_macos(self, search_term: str) -> Optional[str]:
        try:
            script = '''
            tell application "System Events"
                set windowList to {}
                repeat with proc in (every process whose background only is false)
                    repeat with win in (every window of proc)
                        set end of windowList to (name of proc & ": " & name of win)
                    end repeat
                end repeat
                return windowList
            end tell
            '''
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True, text=True
            )
            windows = result.stdout.strip().split(', ')
            for window in windows:
                if search_term.lower() in window.lower():
                    return window.split(':')[0].strip()
            return None
        except Exception:
            return None

    def _find_window_linux(self, search_term: str) -> Optional[str]:
        try:
            result = subprocess.run(
                ['wmctrl', '-l'],
                capture_output=True, text=True
            )
            for line in result.stdout.strip().split('\n'):
                if search_term.lower() in line.lower():
                    parts = line.split()
                    if len(parts) > 3:
                        return ' '.join(parts[3:])
            return None
        except Exception:
            try:
                result = subprocess.run(
                    ['xdotool', 'search', '--name', search_term],
                    capture_output=True, text=True
                )
                if result.stdout.strip():
                    return result.stdout.strip().split('\n')[0]
                return None
            except Exception:
                return None

    def get_all_open_windows(self) -> List[str]:
        if self.system == "Windows":
            return self._get_windows_windows()
        elif self.system == "Darwin":
            return self._get_windows_macos()
        elif self.system == "Linux":
            return self._get_windows_linux()
        return []

    def _get_windows_windows(self) -> List[str]:
        titles = []
        def enum_handler(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    titles.append(title)
        win32gui.EnumWindows(enum_handler, None)
        return titles

    def _get_windows_macos(self) -> List[str]:
        try:
            script = '''
            tell application "System Events"
                set windowList to {}
                repeat with proc in (every process whose background only is false)
                    repeat with win in (every window of proc)
                        set end of windowList to name of win
                    end repeat
                end repeat
                return windowList
            end tell
            '''
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True, text=True
            )
            return [w.strip() for w in result.stdout.strip().split(', ') if w.strip()]
        except Exception:
            return []

    def _get_windows_linux(self) -> List[str]:
        try:
            result = subprocess.run(
                ['wmctrl', '-l'],
                capture_output=True, text=True
            )
            titles = []
            for line in result.stdout.strip().split('\n'):
                parts = line.split()
                if len(parts) > 3:
                    titles.append(' '.join(parts[3:]))
            return titles
        except Exception:
            return []

    def open_application(self, app_name: str):
        app_lower = app_name.lower()
        
        if app_lower in ["browser", "web browser", "internet", "edge", "msedge", "microsoft edge"]:
            app_name = "chrome"
            app_lower = "chrome"

        hwnd = self.find_window(app_name)
        if hwnd:
            self.focus_window(hwnd)
            return f"Focused existing {app_name}"

        if app_lower in ["chrome", "google chrome"]:
            return self._open_chrome()

        if self.system == "Windows":
            direct_result = self._open_application_windows_direct(app_name)
            if direct_result:
                return direct_result

        if self.system == "Windows":
            pyautogui.press('win')
            time.sleep(0.35)
            pyautogui.write(app_name, interval=0.02)
            time.sleep(0.2)
            pyautogui.press('enter')
        elif self.system == "Darwin":
            pyautogui.hotkey('command', 'space')
            time.sleep(0.3)
            pyautogui.write(app_name, interval=0.0)
            pyautogui.press('enter')
        elif self.system == "Linux":
            try:
                subprocess.Popen(['gtk-launch', app_name])
            except Exception:
                try:
                    subprocess.Popen([app_name])
                except Exception:
                    pyautogui.hotkey('alt', 'F2')
                    time.sleep(0.3)
                    pyautogui.write(app_name, interval=0.0)
                    pyautogui.press('enter')
        
        return f"Opened {app_name}"

    def _open_application_windows_direct(self, app_name: str) -> Optional[str]:
        app_lower = app_name.strip().lower()

        # Deterministic launches for common built-in apps.
        direct_targets = {
            "settings": "ms-settings:",
            "windows settings": "ms-settings:",
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "paint": "mspaint.exe",
            "wordpad": "write.exe",
            "explorer": "explorer.exe",
            "file explorer": "explorer.exe",
            "command prompt": "cmd.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "task manager": "taskmgr.exe",
            "control panel": "control.exe",
        }

        target = direct_targets.get(app_lower)
        if target:
            try:
                if target == "ms-settings:":
                    subprocess.Popen(["explorer", target])
                else:
                    subprocess.Popen([target])
                return f"Opened {app_name}"
            except Exception as e:
                logger.warning(f"Direct launch failed for '{app_name}': {e}")

        # Try Windows process launcher for arbitrary app names.
        try:
            start_cmd = f'Start-Process -FilePath "{app_name}"'
            run_res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", start_cmd],
                capture_output=True,
                text=True,
                timeout=6
            )
            if run_res.returncode == 0:
                return f"Opened {app_name}"
        except Exception as e:
            logger.debug(f"Start-Process launch failed for '{app_name}': {e}")

        # Last direct fallback before UI automation.
        try:
            subprocess.Popen(["cmd", "/c", "start", "", app_name])
            return f"Opened {app_name}"
        except Exception as e:
            logger.debug(f"cmd /c start launch failed for '{app_name}': {e}")

        return None

    def _open_chrome(self):
        if self.system == "Windows":
            chrome_paths = [
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
            ]
            for path in chrome_paths:
                if os.path.exists(path):
                    subprocess.Popen([path])
                    return "Opened Google Chrome"
            return self._open_app_fallback("Google Chrome")
        elif self.system == "Darwin":
            chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            if os.path.exists(chrome_path):
                subprocess.Popen([chrome_path])
                return "Opened Google Chrome"
            subprocess.Popen(['open', '-a', 'Google Chrome'])
            return "Opened Google Chrome"
        else:
            try:
                subprocess.Popen(['google-chrome'])
                return "Opened Google Chrome"
            except FileNotFoundError:
                subprocess.Popen(['chromium-browser'])
                return "Opened Chromium"
        return "Chrome not found"

    def _open_app_fallback(self, app_name: str):
        pyautogui.press('win')
        time.sleep(0.3)
        pyautogui.write(app_name, interval=0.02)
        time.sleep(0.2)
        pyautogui.press('enter')
        return f"Opened {app_name} via search"

    def capture_frame_sequence(self, count: int = 5, interval: float = 0.2) -> List[str]:
        frames = []
        if not os.path.exists("frames"):
            os.makedirs("frames")
            
        for i in range(count):
            path = f"frames/frame_{i}.png"
            self.get_screenshot(path)
            frames.append(path)
            time.sleep(interval)
        return frames

    def smooth_move_to(self, x: int, y: int, duration: float = 0.3):
        pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeOutQuad)
        return f"Smoothly moved to ({x}, {y})"

    def drag_to(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5):
        pyautogui.moveTo(start_x, start_y)
        pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration)
        return f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})"

    def drag_drop(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5):
        pyautogui.click(start_x, start_y)
        time.sleep(0.1)
        pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration, button='left')
        return f"Drag-dropped from ({start_x}, {start_y}) to ({end_x}, {end_y})"

    def scroll_at(self, clicks: int, x: int, y: int):
        pyautogui.moveTo(x, y)
        time.sleep(0.05)
        pyautogui.scroll(clicks)
        return f"Scrolled {clicks} clicks at ({x}, {y})"

    def smart_scroll(self, direction: str = "down", amount: int = 3, smooth: bool = True):
        clicks = -amount if direction.lower() == "down" else amount
        if smooth:
            for _ in range(abs(amount)):
                pyautogui.scroll(-1 if direction.lower() == "down" else 1)
                time.sleep(0.05)
        else:
            pyautogui.scroll(clicks)
        return f"Smart scrolled {direction} by {amount}"

    def scroll_to_bottom(self, max_scrolls: int = 20):
        for _ in range(max_scrolls):
            pyautogui.scroll(-5)
            time.sleep(0.1)
        return "Scrolled to bottom"

    def scroll_to_top(self, max_scrolls: int = 20):
        for _ in range(max_scrolls):
            pyautogui.scroll(5)
            time.sleep(0.1)
        return "Scrolled to top"

    def triple_click_at(self, x: int, y: int):
        pyautogui.click(x, y, clicks=3)
        return f"Triple-clicked at ({x}, {y})"

    def select_all(self):
        mod = 'command' if self.system == "Darwin" else 'ctrl'
        pyautogui.hotkey(mod, 'a')
        return "Selected all"

    def copy_selection(self):
        mod = 'command' if self.system == "Darwin" else 'ctrl'
        pyautogui.hotkey(mod, 'c')
        time.sleep(0.1)
        return "Copied selection"

    def paste(self):
        mod = 'command' if self.system == "Darwin" else 'ctrl'
        pyautogui.hotkey(mod, 'v')
        return "Pasted"

    def undo(self):
        mod = 'command' if self.system == "Darwin" else 'ctrl'
        pyautogui.hotkey(mod, 'z')
        return "Undone"

    def redo(self):
        mod = 'command' if self.system == "Darwin" else 'ctrl'
        pyautogui.hotkey(mod, 'shift', 'z') if self.system == "Darwin" else pyautogui.hotkey('ctrl', 'y')
        return "Redone"

    def switch_window(self):
        if self.system == "Darwin":
            pyautogui.hotkey('command', 'tab')
        else:
            pyautogui.hotkey('alt', 'tab')
        return "Switched window"

    def switch_to_window_by_name(self, name: str) -> bool:
        hwnd = self.find_window(name)
        if hwnd:
            return self.focus_window(hwnd)
        return False

    def minimize_window(self, hwnd=None):
        if self.system == "Windows":
            if hwnd is None:
                hwnd = win32gui.GetForegroundWindow()
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return "Minimized window"
        elif self.system == "Darwin":
            pyautogui.hotkey('command', 'm')
            return "Minimized window"
        else:
            pyautogui.hotkey('super', 'h')
            return "Minimized window"

    def maximize_window(self, hwnd=None):
        if self.system == "Windows":
            if hwnd is None:
                hwnd = win32gui.GetForegroundWindow()
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            return "Maximized window"
        elif self.system == "Darwin":
            pyautogui.hotkey('command', 'ctrl', 'f')
            return "Maximized window"
        else:
            pyautogui.hotkey('super', 'up')
            return "Maximized window"

    def restore_window(self, hwnd=None):
        if self.system == "Windows":
            if hwnd is None:
                hwnd = win32gui.GetForegroundWindow()
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            return "Restored window"
        return "Restored window"

    def snap_window_left(self):
        if self.system == "Windows":
            pyautogui.hotkey('win', 'left')
        elif self.system == "Darwin":
            pass
        else:
            pyautogui.hotkey('super', 'left')
        return "Snapped window left"

    def snap_window_right(self):
        if self.system == "Windows":
            pyautogui.hotkey('win', 'right')
        elif self.system == "Darwin":
            pass
        else:
            pyautogui.hotkey('super', 'right')
        return "Snapped window right"

    def close_window(self):
        if self.system == "Darwin":
            pyautogui.hotkey('command', 'w')
        else:
            pyautogui.hotkey('alt', 'F4')
        return "Closed window"

    def new_tab(self):
        mod = 'command' if self.system == "Darwin" else 'ctrl'
        pyautogui.hotkey(mod, 't')
        return "Opened new tab"

    def close_tab(self):
        mod = 'command' if self.system == "Darwin" else 'ctrl'
        pyautogui.hotkey(mod, 'w')
        return "Closed tab"

    def switch_tab_next(self):
        mod = 'command' if self.system == "Darwin" else 'ctrl'
        pyautogui.hotkey(mod, 'tab')
        return "Switched to next tab"

    def switch_tab_prev(self):
        mod = 'command' if self.system == "Darwin" else 'ctrl'
        pyautogui.hotkey(mod, 'shift', 'tab')
        return "Switched to previous tab"

    def go_back(self):
        if self.system == "Darwin":
            pyautogui.hotkey('command', '[')
        else:
            pyautogui.hotkey('alt', 'left')
        return "Went back"

    def go_forward(self):
        if self.system == "Darwin":
            pyautogui.hotkey('command', ']')
        else:
            pyautogui.hotkey('alt', 'right')
        return "Went forward"

    def refresh_page(self):
        mod = 'command' if self.system == "Darwin" else 'ctrl'
        pyautogui.hotkey(mod, 'r')
        return "Refreshed page"

    def focus_address_bar(self):
        mod = 'command' if self.system == "Darwin" else 'ctrl'
        pyautogui.hotkey(mod, 'l')
        return "Focused address bar"

    def search_in_page(self, text: str = None):
        mod = 'command' if self.system == "Darwin" else 'ctrl'
        pyautogui.hotkey(mod, 'f')
        if text:
            time.sleep(0.2)
            pyautogui.write(text, interval=0.02)
        return f"Opened search{' and typed: ' + text if text else ''}"

    def escape(self):
        pyautogui.press('escape')
        return "Pressed escape"

    def enter(self):
        pyautogui.press('enter')
        return "Pressed enter"

    def _focus_known_browser_window(self, browser_hint: str = "") -> bool:
        hint = (browser_hint or "").strip().lower()
        candidates = []

        if hint in ["chrome", "google chrome"]:
            candidates = ["google chrome", "chrome"]
        elif hint in ["edge", "microsoft edge", "msedge"]:
            candidates = ["microsoft edge", "edge"]
        elif hint == "firefox":
            candidates = ["firefox"]
        elif hint == "brave":
            candidates = ["brave"]
        else:
            candidates = ["google chrome", "chrome", "microsoft edge", "edge", "firefox", "brave"]

        for name in candidates:
            hwnd = self.find_window(name)
            if hwnd and self.focus_window(hwnd):
                return True
        return False

    def navigate_to_url(self, url: str, browser_hint: str = ""):
        """Navigate to URL in a browser using a deterministic keyboard sequence."""
        target = (url or "").strip()
        if not target:
            raise ValueError("Missing URL")

        # Bring the intended browser forward before typing into the address bar.
        self._focus_known_browser_window(browser_hint)
        time.sleep(0.3)

        mod = 'command' if self.system == "Darwin" else 'ctrl'
        pyautogui.hotkey(mod, 'l')
        time.sleep(0.15)
        pyautogui.hotkey(mod, 'a')
        time.sleep(0.08)
        pyautogui.write(target, interval=0.0)
        time.sleep(0.08)
        pyautogui.press('enter')
        time.sleep(0.2)
        return f"Navigated to {target}"

    def tab(self):
        pyautogui.press('tab')
        return "Pressed tab"

    def shift_tab(self):
        pyautogui.hotkey('shift', 'tab')
        return "Pressed shift+tab"

    def arrow_key(self, direction: str, count: int = 1):
        for _ in range(count):
            pyautogui.press(direction)
            time.sleep(0.05)
        return f"Pressed {direction} arrow {count} times"

    def page_down(self):
        pyautogui.press('pagedown')
        return "Page down"

    def page_up(self):
        pyautogui.press('pageup')
        return "Page up"

    def home_key(self):
        pyautogui.press('home')
        return "Pressed home"

    def end_key(self):
        pyautogui.press('end')
        return "Pressed end"

    def toggle_bluetooth(self, enable: bool = True) -> str:
        """Toggle Bluetooth radio on/off on Windows using WinRT API"""
        if self.system != "Windows":
            return "Bluetooth toggle only supported on Windows"
        
        try:
            state = "On" if enable else "Off"
            ps_script = f'''
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }})[0]
Function Await($WinRtTask, $ResultType) {{
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}}
[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Radios.RadioState,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
$radios = Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus])
if ($radios -ne 'Allowed') {{ Write-Output "Access denied"; exit 1 }}
$allRadios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
$bluetooth = $allRadios | Where-Object {{ $_.Kind -eq 'Bluetooth' }}
if ($bluetooth) {{
    Await ($bluetooth.SetStateAsync([Windows.Devices.Radios.RadioState]::{state})) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
    Write-Output "Bluetooth {state}"
}} else {{
    Write-Output "No Bluetooth radio found"
}}
'''
            result = subprocess.run(
                ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_script],
                capture_output=True, text=True, timeout=30
            )
            
            output = result.stdout.strip()
            if f"Bluetooth {state}" in output:
                return f"Bluetooth {'enabled' if enable else 'disabled'} successfully"
            elif "Access denied" in output:
                return self._toggle_bluetooth_via_settings(enable)
            elif "No Bluetooth radio" in output:
                return "No Bluetooth radio found on this device"
            else:
                error = result.stderr.strip() if result.stderr else output
                return self._toggle_bluetooth_via_settings(enable)
        except subprocess.TimeoutExpired:
            return "Bluetooth toggle timed out"
        except Exception as e:
            return self._toggle_bluetooth_via_settings(enable)

    def _toggle_bluetooth_via_settings(self, enable: bool) -> str:
        """Fallback: Toggle Bluetooth via Settings app using ms-settings URI"""
        try:
            subprocess.Popen(['explorer', 'ms-settings:bluetooth'], shell=True)
            time.sleep(2)
            
            pyautogui.press('tab')
            time.sleep(0.2)
            pyautogui.press('tab')
            time.sleep(0.2)
            
            pyautogui.press('space')
            time.sleep(0.5)
            
            return f"Toggled Bluetooth via Settings (attempted to {'enable' if enable else 'disable'})"
        except Exception as e:
            return f"Bluetooth toggle via Settings failed: {e}"

    def get_bluetooth_status(self) -> dict:
        """Check if Bluetooth is enabled on Windows"""
        if self.system != "Windows":
            return {"enabled": False, "error": "Only supported on Windows"}
        
        try:
            cmd = 'powershell -Command "Get-PnpDevice -Class Bluetooth | Select-Object Status, FriendlyName | ConvertTo-Json"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                import json as json_mod
                devices = json_mod.loads(result.stdout)
                if not isinstance(devices, list):
                    devices = [devices]
                
                enabled = any(d.get('Status') == 'OK' for d in devices)
                return {"enabled": enabled, "devices": devices}
            return {"enabled": False, "error": "Could not query Bluetooth status"}
        except Exception as e:
            return {"enabled": False, "error": str(e)}

    def take_screenshot_region(self, x: int, y: int, width: int, height: int, output_path: str) -> str:
        screenshot = pyautogui.screenshot(region=(x, y, width, height))
        screenshot.save(output_path)
        return output_path

    def get_pixel_color(self, x: int, y: int) -> Tuple[int, int, int]:
        return pyautogui.pixel(x, y)

    def select_file_in_dialog(self, file_path: str) -> str:
        """Select a file in an open file dialog by typing the path and pressing Enter"""
        if not os.path.exists(file_path):
            return f"File not found: {file_path}"
        
        time.sleep(0.3)
        
        if self.system == "Windows":
            pyautogui.hotkey('alt', 'd')
            time.sleep(0.2)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            
            dir_path = os.path.dirname(file_path)
            pyautogui.write(dir_path, interval=0.01)
            time.sleep(0.1)
            pyautogui.press('enter')
            time.sleep(0.5)
            
            file_name = os.path.basename(file_path)
            pyautogui.hotkey('alt', 'n')
            time.sleep(0.2)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.write(file_name, interval=0.01)
            time.sleep(0.1)
            pyautogui.press('enter')
        elif self.system == "Darwin":
            pyautogui.hotkey('command', 'shift', 'g')
            time.sleep(0.3)
            pyautogui.write(file_path, interval=0.01)
            time.sleep(0.1)
            pyautogui.press('enter')
            time.sleep(0.3)
            pyautogui.press('enter')
        else:
            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.2)
            pyautogui.write(file_path, interval=0.01)
            time.sleep(0.1)
            pyautogui.press('enter')
        
        return f"Selected file: {file_path}"

    def copy_file_to_clipboard(self, file_path: str) -> str:
        """Copy a file to clipboard so it can be pasted in chat apps"""
        if not os.path.exists(file_path):
            return f"File not found: {file_path}"
        
        if self.system == "Windows":
            try:
                ps_script = f'''
Add-Type -AssemblyName System.Windows.Forms
$files = [System.Collections.Specialized.StringCollection]::new()
$files.Add("{file_path}")
[System.Windows.Forms.Clipboard]::SetFileDropList($files)
Write-Output "Copied"
'''
                result = subprocess.run(
                    ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_script],
                    capture_output=True, text=True, timeout=10
                )
                if "Copied" in result.stdout:
                    return f"Copied file to clipboard: {file_path}"
                return f"Failed to copy: {result.stderr}"
            except Exception as e:
                return f"Copy failed: {e}"
        elif self.system == "Darwin":
            try:
                script = f'''
                set theFile to POSIX file "{file_path}"
                tell application "Finder"
                    set the clipboard to theFile
                end tell
                '''
                subprocess.run(['osascript', '-e', script], check=True)
                return f"Copied file to clipboard: {file_path}"
            except Exception as e:
                return f"Copy failed: {e}"
        else:
            return "File clipboard copy not supported on Linux"

    def open_file_explorer_at(self, folder_path: str) -> str:
        """Open file explorer at a specific folder"""
        if not os.path.exists(folder_path):
            folder_path = os.path.dirname(folder_path)
        
        if self.system == "Windows":
            subprocess.Popen(['explorer', folder_path])
        elif self.system == "Darwin":
            subprocess.Popen(['open', folder_path])
        else:
            subprocess.Popen(['xdg-open', folder_path])
        
        return f"Opened explorer at: {folder_path}"

    def get_active_window_info(self) -> Dict[str, Any]:
        if self.system == "Windows":
            return self._get_active_window_windows()
        elif self.system == "Darwin":
            return self._get_active_window_macos()
        elif self.system == "Linux":
            return self._get_active_window_linux()
        return {"title": "Unknown", "app_name": "Unknown", "is_coding": False}

    def _get_active_window_windows(self) -> Dict[str, Any]:
        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            
            import psutil
            process = psutil.Process(pid)
            app_name = process.name().replace('.exe', '')
            
            coding_apps = ['code', 'pycharm', 'idea', 'webstorm', 'vim', 'nvim', 'sublime', 'atom', 'notepad++']
            is_coding = any(ca in app_name.lower() or ca in title.lower() for ca in coding_apps)
            
            return {
                "title": title,
                "app_name": app_name,
                "is_coding": is_coding,
                "hwnd": hwnd
            }
        except Exception:
            return {"title": "Unknown", "app_name": "Unknown", "is_coding": False}

    def _get_active_window_macos(self) -> Dict[str, Any]:
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
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True, text=True
            )
            parts = result.stdout.strip().split('|||')
            app_name = parts[0] if len(parts) > 0 else "Unknown"
            title = parts[1] if len(parts) > 1 else ""
            
            coding_apps = ['code', 'pycharm', 'idea', 'webstorm', 'vim', 'nvim', 'sublime', 'atom', 'xcode', 'terminal', 'iterm']
            is_coding = any(ca in app_name.lower() or ca in title.lower() for ca in coding_apps)
            
            return {
                "title": title,
                "app_name": app_name,
                "is_coding": is_coding
            }
        except Exception:
            return {"title": "Unknown", "app_name": "Unknown", "is_coding": False}

    def _get_active_window_linux(self) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowname'],
                capture_output=True, text=True
            )
            title = result.stdout.strip()
            
            result2 = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowpid'],
                capture_output=True, text=True
            )
            pid = result2.stdout.strip()
            
            app_name = "Unknown"
            if pid:
                try:
                    result3 = subprocess.run(
                        ['ps', '-p', pid, '-o', 'comm='],
                        capture_output=True, text=True
                    )
                    app_name = result3.stdout.strip()
                except Exception:
                    pass
            
            coding_apps = ['code', 'pycharm', 'idea', 'webstorm', 'vim', 'nvim', 'sublime', 'atom', 'gedit', 'kate']
            is_coding = any(ca in app_name.lower() or ca in title.lower() for ca in coding_apps)
            
            return {
                "title": title,
                "app_name": app_name,
                "is_coding": is_coding
            }
        except Exception:
            return {"title": "Unknown", "app_name": "Unknown", "is_coding": False}
