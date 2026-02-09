import logging
import os
import cv2
import numpy as np
from PIL import Image
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("VisualDetector")

class VisualDetector:
    def __init__(self):
        self._ocr_available = False
        self._tesseract_available = False
        self._easyocr_reader = None
        # OCR is slow, only initialize when explicitly needed via find_text_on_screen
    
    def _check_ocr(self):
        if self._ocr_available:
            return
            
        try:
            # Try to see if privacy_redactor already has an engine
            try:
                from utils.privacy import privacy_redactor
                if privacy_redactor and privacy_redactor._ocr_engine:
                    self._easyocr_reader = privacy_redactor._ocr_engine
                    self._ocr_available = True
                    logger.info("Reusing EasyOCR engine from PrivacyRedactor")
                    return
            except Exception:
                pass

            import easyocr
            self._easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            self._ocr_available = True
            logger.info("EasyOCR initialized")
        except ImportError:
            try:
                import pytesseract
                pytesseract.get_tesseract_version()
                self._tesseract_available = True
                self._ocr_available = True
                logger.info("Tesseract OCR initialized")
            except Exception:
                logger.warning("No OCR engine available. Install easyocr or pytesseract for fallback detection.")

    def find_text_on_screen(self, image_path: str, target_text: str) -> Optional[Dict[str, int]]:
        self._check_ocr()
        if not self._ocr_available:
            return None
        
        try:
            if self._easyocr_reader:
                return self._find_text_easyocr(image_path, target_text)
            elif self._tesseract_available:
                return self._find_text_tesseract(image_path, target_text)
        except Exception as e:
            print(f"[VisualDetector] OCR error: {e}")
        return None

    def _find_text_easyocr(self, image_path: str, target_text: str) -> Optional[Dict[str, int]]:
        if not self._easyocr_reader: return None
        results = self._easyocr_reader.readtext(image_path)
        target_lower = target_text.lower()
        
        for (bbox, text, confidence) in results:
            if target_lower in text.lower() and confidence > 0.3:
                (top_left, top_right, bottom_right, bottom_left) = bbox
                center_x = int((top_left[0] + bottom_right[0]) / 2)
                center_y = int((top_left[1] + bottom_right[1]) / 2)
                return {"x": center_x, "y": center_y, "confidence": confidence, "text": text}
        
        best_match = None
        best_score = 0
        for (bbox, text, confidence) in results:
            score = self._fuzzy_match_score(target_lower, text.lower())
            if score > best_score and score > 0.6:
                best_score = score
                (top_left, top_right, bottom_right, bottom_left) = bbox
                center_x = int((top_left[0] + bottom_right[0]) / 2)
                center_y = int((top_left[1] + bottom_right[1]) / 2)
                best_match = {"x": center_x, "y": center_y, "confidence": score, "text": text}
        
        return best_match

    def _find_text_tesseract(self, image_path: str, target_text: str) -> Optional[Dict[str, int]]:
        import pytesseract
        img = Image.open(image_path)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        
        target_lower = target_text.lower()
        n_boxes = len(data['text'])
        
        for i in range(n_boxes):
            text = data['text'][i]
            conf = int(data['conf'][i])
            
            if text and target_lower in text.lower() and conf > 30:
                x = data['left'][i]
                y = data['top'][i]
                w = data['width'][i]
                h = data['height'][i]
                center_x = x + w // 2
                center_y = y + h // 2
                return {"x": center_x, "y": center_y, "confidence": conf / 100, "text": text}
        
        return None

    def _fuzzy_match_score(self, s1: str, s2: str) -> float:
        if s1 == s2:
            return 1.0
        
        if len(s1) == 0 or len(s2) == 0:
            return 0.0
        
        m = len(s1)
        n = len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
        
        max_len = max(m, n)
        return 1 - (dp[m][n] / max_len)

    def template_match(self, image_path: str, template_path: str, threshold: float = 0.8) -> Optional[Dict[str, int]]:
        try:
            img = cv2.imread(image_path)
            template = cv2.imread(template_path)
            
            if img is None or template is None:
                return None
            
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            
            result = cv2.matchTemplate(img_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= threshold:
                h, w = template_gray.shape
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                return {"x": center_x, "y": center_y, "confidence": max_val}
            
            return None
        except Exception as e:
            print(f"[VisualDetector] Template matching error: {e}")
            return None

    def find_ui_element_by_color(self, image_path: str, color_rgb: Tuple[int, int, int], tolerance: int = 30) -> Optional[Dict[str, int]]:
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None
            
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            lower = np.array([max(0, c - tolerance) for c in color_rgb])
            upper = np.array([min(255, c + tolerance) for c in color_rgb])
            
            mask = cv2.inRange(img_rgb, lower, upper)
            
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                largest = max(contours, key=cv2.contourArea)
                M = cv2.moments(largest)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    return {"x": cx, "y": cy, "confidence": 0.8}
            
            return None
        except Exception as e:
            print(f"[VisualDetector] Color detection error: {e}")
            return None

    def find_button_shapes(self, image_path: str) -> List[Dict[str, Any]]:
        try:
            img = cv2.imread(image_path)
            if img is None:
                return []
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            buttons = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if 500 < area < 50000:
                    approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
                    if 4 <= len(approx) <= 8:
                        x, y, w, h = cv2.boundingRect(contour)
                        aspect = w / h if h > 0 else 0
                        if 0.3 < aspect < 10:
                            cx = x + w // 2
                            cy = y + h // 2
                            buttons.append({
                                "x": cx, "y": cy,
                                "width": w, "height": h,
                                "area": area
                            })
            
            return sorted(buttons, key=lambda b: b["area"], reverse=True)[:20]
        except Exception as e:
            print(f"[VisualDetector] Button detection error: {e}")
            return []

    def get_all_text_regions(self, image_path: str) -> List[Dict[str, Any]]:
        self._check_ocr()
        if not self._ocr_available:
            # Contour-based fallback for text-like regions
            return self._detect_text_like_regions(image_path)
        
        try:
            if self._easyocr_reader:
                results = self._easyocr_reader.readtext(image_path)
                regions = []
                for (bbox, text, confidence) in results:
                    if confidence > 0.3 and text.strip():
                        (top_left, top_right, bottom_right, bottom_left) = bbox
                        regions.append({
                            "text": text,
                            "x": int((top_left[0] + bottom_right[0]) / 2),
                            "y": int((top_left[1] + bottom_right[1]) / 2),
                            "bbox": {
                                "left": int(top_left[0]),
                                "top": int(top_left[1]),
                                "right": int(bottom_right[0]),
                                "bottom": int(bottom_right[1])
                            },
                            "confidence": confidence
                        })
                return regions
        except Exception:
            pass
        return self._detect_text_like_regions(image_path)

    def _detect_text_like_regions(self, image_path: str) -> List[Dict[str, Any]]:
        """Finds regions that look like text or UI elements using OpenCV"""
        try:
            img = cv2.imread(image_path)
            if img is None: return []
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Use MSER or thresholding to find text-like blobs
            mser = cv2.MSER_create()
            regions, _ = mser.detectRegions(gray)
            
            candidates = []
            for p in regions:
                x, y, w, h = cv2.boundingRect(p.reshape(-1, 1, 2))
                if 10 < w < 500 and 5 < h < 100:
                    candidates.append((x, y, w, h))
            
            # Merge overlapping boxes
            if not candidates: return []
            candidates.sort()
            
            merged = []
            if candidates:
                curr = list(candidates[0])
                for next_box in candidates[1:]:
                    # If close or overlapping
                    if next_box[0] < curr[0] + curr[2] + 10 and \
                       abs(next_box[1] - curr[1]) < 10:
                        # Expand curr
                        new_right = max(curr[0] + curr[2], next_box[0] + next_box[2])
                        new_bottom = max(curr[1] + curr[3], next_box[1] + next_box[3])
                        curr[2] = new_right - curr[0]
                        curr[3] = new_bottom - curr[1]
                    else:
                        merged.append(curr)
                        curr = list(next_box)
                merged.append(curr)
            
            results = []
            for i, (x, y, w, h) in enumerate(merged):
                results.append({
                    "text": f"Element {i}",
                    "x": x + w // 2,
                    "y": y + h // 2,
                    "bbox": {"left": x, "top": y, "right": x + w, "bottom": y + h},
                    "confidence": 0.5
                })
            return results
        except Exception:
            return []

    def draw_som(self, image_path: str, output_path: str) -> Dict[int, Dict[str, Any]]:
        """Generates a Set-of-Marks (SoM) image and returns the label mapping"""
        try:
            img = cv2.imread(image_path)
            if img is None: return {}
            
            # 1. Collect potential regions
            text_regions = self.get_all_text_regions(image_path)
            button_regions = self.find_button_shapes(image_path)
            
            all_regions = []
            for r in text_regions:
                all_regions.append({
                    "center": (r["x"], r["y"]),
                    "bbox": (r["bbox"]["left"], r["bbox"]["top"], r["bbox"]["right"], r["bbox"]["bottom"]),
                    "type": "text"
                })
            
            for r in button_regions:
                # Avoid duplicates with text regions
                is_dup = False
                for tr in all_regions:
                    dist = ((r["x"] - tr["center"][0])**2 + (r["y"] - tr["center"][1])**2)**0.5
                    if dist < 20:
                        is_dup = True
                        break
                if not is_dup:
                    all_regions.append({
                        "center": (r["x"], r["y"]),
                        "bbox": (r["x"] - r["width"]//2, r["y"] - r["height"]//2, r["x"] + r["width"]//2, r["y"] + r["height"]//2),
                        "type": "button"
                    })
            
            # 2. Draw marks
            mapping = {}
            for i, region in enumerate(all_regions[:50]): # Limit to 50 marks for clarity
                x1, y1, x2, y2 = region["bbox"]
                label_id = i + 1
                
                # Draw translucent box
                overlay = img.copy()
                color = (0, 255, 0) if region["type"] == "text" else (255, 0, 0)
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
                cv2.addWeighted(overlay, 0.3, img, 0.7, 0, img)
                
                # Draw border
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                
                # Draw label bubble
                label_text = str(label_id)
                (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(img, (x1, y1 - th - 10), (x1 + tw + 10, y1), color, -1)
                cv2.putText(img, label_text, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                mapping[label_id] = {
                    "x": region["center"][0],
                    "y": region["center"][1],
                    "bbox": region["bbox"],
                    "type": region["type"]
                }
            
            cv2.imwrite(output_path, img)
            return mapping
        except Exception as e:
            logger.error(f"Error drawing SoM: {e}")
            return {}

visual_detector = VisualDetector()
