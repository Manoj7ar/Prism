import ctypes
import pyautogui
from typing import Tuple, Optional
from dataclasses import dataclass

@dataclass
class VisualDetectionResult:
    x: int
    y: int
    width: int
    height: int
    confidence: float
    verified: bool = False
    
    @property
    def center_x(self) -> int:
        return self.x + self.width // 2
    
    @property
    def center_y(self) -> int:
        return self.y + self.height // 2

def get_dpi_scale() -> float:
    try:
        # Get physical vs logical resolution ratio
        import tkinter
        root = tkinter.Tk()
        width_physical = root.winfo_screenwidth()
        root.destroy()
        
        width_logical, _ = pyautogui.size()
        if width_logical > 0:
            return width_physical / width_logical
        return 1.0
    except Exception:
        try:
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            dpi = user32.GetDpiForSystem()
            return dpi / 96.0
        except Exception:
            return 1.0

def get_screen_resolution() -> Tuple[int, int]:
    """Returns the LOGICAL screen resolution (the one used by PyAutoGUI)"""
    try:
        return pyautogui.size()
    except Exception:
        try:
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
            return (width, height)
        except Exception:
            return (1920, 1080)

def normalize_coordinates(x: int, y: int, from_scale: float = 1.0) -> Tuple[int, int]:
    current_scale = get_dpi_scale()
    factor = current_scale / from_scale
    return (int(x * factor), int(y * factor))
