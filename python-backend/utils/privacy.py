import os
import json
import re
from PIL import Image, ImageFilter
from typing import List, Dict, Any
import asyncio

class PrivacyRedactor:
    def __init__(self, prism_client):
        self.prism_client = prism_client
        self.sensitive_categories = [
            "passwords", 
            "credit_card_numbers", 
            "personal_emails", 
            "phone_numbers", 
            "physical_addresses",
            "faces",
            "bank_account_info"
        ]
        self._ocr_engine = None
        self._ocr_initialized = False
        
        self.local_patterns = {
            "credit_card": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
            "phone": re.compile(r'\b(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
            "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            "ssn": re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'),
        }

        # LOCAL SHIELD: Block these apps entirely for privacy
        self.sensitive_apps = [
            "1Password", "LastPass", "KeePass", "Bitwarden",
            "System Settings", "System Preferences", "Wallet",
            "Keychain Access", "Private Report", "Health"
        ]
    
    def _is_app_sensitive(self, app_name: str) -> bool:
        if not app_name:
            return False
        return any(s.lower() in app_name.lower() for s in self.sensitive_apps)

    def _init_local_ocr(self):
        self._ocr_initialized = True
        try:
            import easyocr
            from automation.visual_detector import visual_detector
            if hasattr(visual_detector, '_easyocr_reader') and visual_detector._easyocr_reader:
                self._ocr_engine = visual_detector._easyocr_reader
            else:
                self._ocr_engine = easyocr.Reader(['en'], gpu=False, verbose=False)
        except (ImportError, Exception):
            try:
                import easyocr
                self._ocr_engine = easyocr.Reader(['en'], gpu=False, verbose=False)
            except ImportError:
                pass

    def _ensure_ocr_engine(self):
        if not self._ocr_initialized:
            self._init_local_ocr()

    def perform_ocr(self, image_path: str) -> List[Any]:
        self._ensure_ocr_engine()
        if not self._ocr_engine:
            return []
        try:
            return self._ocr_engine.readtext(image_path)
        except Exception as e:
            return []

    def get_text(self, image_path: str) -> str:
        """Extract all text from an image"""
        results = self.perform_ocr(image_path)
        if not results:
            return ""
        return " ".join([r[1] for r in results])

    def _local_ocr_scan(self, image_path: str) -> List[Dict[str, Any]]:
        """Perform local OCR to find sensitive patterns before sending to API"""
        results = self.perform_ocr(image_path)
        if not results:
            return []
            
        try:
            boxes = []
            img = Image.open(image_path)
            width, height = img.size
            
            for (bbox, text, prob) in results:
                # Check against local patterns
                is_sensitive = False
                for pattern_name, pattern in self.local_patterns.items():
                    if pattern.search(text):
                        is_sensitive = True
                        break
                
                if is_sensitive:
                    # EasyOCR returns [top_left, top_right, bottom_right, bottom_left]
                    # We need to convert to [ymin, xmin, ymax, xmax] normalized 0-1000
                    xs = [p[0] for p in bbox]
                    ys = [p[1] for p in bbox]
                    
                    ymin = min(ys) * 1000 / height
                    xmin = min(xs) * 1000 / width
                    ymax = max(ys) * 1000 / height
                    xmax = max(xs) * 1000 / width
                    
                    boxes.append({
                        "box_2d": [ymin, xmin, ymax, xmax],
                        "label": "sensitive_text"
                    })
            
            return boxes
        except Exception as e:
            return []

    async def redact_image(self, image_path: str, output_path: str = None, use_local_first: bool = True, active_app: str = None) -> str:
        if not os.path.exists(image_path):
            logger.error(f"Cannot redact missing image: {image_path}")
            return image_path

        if output_path is None:
            output_path = image_path

        # LOCAL SHIELD: Entire screen redaction for sensitive apps
        if active_app and self._is_app_sensitive(active_app):
            try:
                img = Image.open(image_path)
                blurred = img.filter(ImageFilter.GaussianBlur(radius=50))
                blurred.save(output_path)
                return output_path
            except Exception as e:
                return image_path

        try:
            boxes = []
            
            if use_local_first and self._ocr_engine:
                boxes = self._local_ocr_scan(image_path)
            
            if not boxes:
                prompt = f"""
                Identify all sensitive information in this screenshot. 
                Categories to detect: {', '.join(self.sensitive_categories)}.
                
                Return ONLY a JSON array of bounding boxes in the format:
                [
                    {{"box_2d": [ymin, xmin, ymax, xmax], "label": "category"}}
                ]
                Coordinates should be normalized 0-1000.
                If no sensitive info is found, return [].
                """
                
                try:
                    image_part = self.prism_client._get_media_part(image_path)
                    response = await self.prism_client._safe_generate(
                        self.prism_client.model_id,
                        [image_part, prompt],
                        self.prism_client.config
                    )
                    
                    # CRASH FIX: Safely extract text from response
                    response_text = ""
                    if hasattr(response, "text"):
                        try:
                            response_text = response.text
                        except (ValueError, AttributeError):
                            # This happens if safety filters block the response
                            return image_path
                    elif hasattr(response, "candidates") and response.candidates:
                        # Fallback for candidates
                        candidate = response.candidates[0]
                        if hasattr(candidate, "content") and candidate.content.parts:
                            response_text = candidate.content.parts[0].text
                    
                    if response_text:
                        boxes = self._parse_boxes(response_text)
                except Exception as api_err:
                    return image_path

            if not boxes:
                return image_path

            try:
                img = Image.open(image_path)
                width, height = img.size
                
                for box_data in boxes:
                    box = box_data.get("box_2d")
                    if not box or len(box) != 4:
                        continue
                    
                    ymin, xmin, ymax, xmax = box
                    # Ensure coordinates are within bounds
                    left = max(0, min(width - 1, xmin * width / 1000))
                    top = max(0, min(height - 1, ymin * height / 1000))
                    right = max(0, min(width, xmax * width / 1000))
                    bottom = max(0, min(height, ymax * height / 1000))
                    
                    if right <= left or bottom <= top:
                        continue

                    region = img.crop((left, top, right, bottom))
                    blurred_region = region.filter(ImageFilter.GaussianBlur(radius=15))
                    img.paste(blurred_region, (int(left), int(top)))
                
                img.save(output_path)
                return output_path
            except Exception as img_err:
                return image_path

        except Exception as e:
            return image_path


    def _parse_boxes(self, text: str) -> List[Dict[str, Any]]:
        if not text or not text.strip():
            return []
            
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        # Clean up any potential non-JSON text
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            text = text[start:end+1]
        
        if not text.strip():
            return []
            
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return []

# Singleton instance will be initialized in main or executor
privacy_redactor = None

def init_privacy(prism_client):
    global privacy_redactor
    privacy_redactor = PrivacyRedactor(prism_client)
    return privacy_redactor
