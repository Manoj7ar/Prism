import requests
import os
from typing import Optional
from utils.screen_utils import VisualDetectionResult

class UIHighlighter:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url

    def show_overlay(self, show: bool = True):
        try:
            requests.post(f"{self.base_url}/overlay/show", json={"show": show})
        except Exception:
            pass

    def draw_annotation(self, type: str, x: int, y: int, width: int = 50, height: int = 50, narration: str = ""):
        try:
            requests.post(f"{self.base_url}/overlay/draw", json={
                "type": type,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "narration": narration
            })
        except Exception:
            pass

    def set_waiting(self, waiting: bool, condition: str = ""):
        try:
            requests.post(f"{self.base_url}/overlay/draw", json={
                "type": "waiting",
                "value": waiting,
                "condition": condition
            })
        except Exception:
            pass

    def clear(self):
        try:
            requests.post(f"{self.base_url}/overlay/clear")
        except Exception:
            pass

    async def highlight_element_robust(
        self, 
        description: str, 
        prism_client, 
        screenshot_path: Optional[str] = None
    ) -> bool:
        from automation.desktop import DesktopAutomation
        desktop = DesktopAutomation()
        
        if not screenshot_path:
            screenshot_path = "highlight_temp.png"
            desktop.get_screenshot(screenshot_path)
        
        detection = await prism_client.locate_element_visually_robust(
            screenshot_path, 
            description,
            verify=True
        )
        
        if not detection:
            detection = await self._fallback_ocr_detection(screenshot_path, description)
        
        if screenshot_path == "highlight_temp.png" and os.path.exists(screenshot_path):
            os.remove(screenshot_path)
        
        if not detection:
            print(f"[UIHighlighter] Could not reliably locate: {description}")
            return False
        
        if detection.confidence < 0.7:
            print(f"[UIHighlighter] Warning: Low confidence ({detection.confidence:.2f}) for {description}")
        
        radius = max(detection.width, detection.height) // 2 + 25
        self.draw_annotation(
            "circle",
            detection.center_x,
            detection.center_y,
            radius,
            radius
        )
        
        return True

    async def _fallback_ocr_detection(self, screenshot_path: str, description: str) -> Optional[VisualDetectionResult]:
        try:
            import pytesseract
            from PIL import Image
            
            img = Image.open(screenshot_path)
            ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            
            search_terms = description.lower().split()
            
            for i, text in enumerate(ocr_data['text']):
                if not text.strip():
                    continue
                text_lower = text.lower()
                if any(term in text_lower for term in search_terms):
                    x = ocr_data['left'][i]
                    y = ocr_data['top'][i]
                    w = ocr_data['width'][i]
                    h = ocr_data['height'][i]
                    conf = ocr_data['conf'][i]
                    
                    if conf > 50:
                        return VisualDetectionResult(x, y, w, h, conf / 100.0)
            
            return None
        except ImportError:
            print("[UIHighlighter] pytesseract not installed, OCR fallback unavailable")
            return None
        except Exception as e:
            print(f"[UIHighlighter] OCR fallback failed: {e}")
            return None


ui_highlighter = UIHighlighter()
