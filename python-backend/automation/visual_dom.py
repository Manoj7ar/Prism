import logging
import os
import cv2
import numpy as np
from PIL import Image
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import asyncio

logger = logging.getLogger("VisualDOM")

class ElementType(Enum):
    BUTTON = "button"
    INPUT = "input"
    TEXT_FIELD = "text_field"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    DROPDOWN = "dropdown"
    TOGGLE = "toggle"
    LINK = "link"
    LABEL = "label"
    HEADING = "heading"
    ICON = "icon"
    IMAGE = "image"
    MENU = "menu"
    MENU_ITEM = "menu_item"
    TAB = "tab"
    NAVIGATION = "navigation"
    TOOLBAR = "toolbar"
    SIDEBAR = "sidebar"
    MODAL = "modal"
    CARD = "card"
    LIST_ITEM = "list_item"
    TABLE_CELL = "table_cell"
    SCROLLBAR = "scrollbar"
    UNKNOWN = "unknown"

@dataclass
class BoundingBox:
    left: int
    top: int
    right: int
    bottom: int
    
    @property
    def width(self) -> int:
        return self.right - self.left
    
    @property
    def height(self) -> int:
        return self.bottom - self.top
    
    @property
    def center(self) -> Tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)
    
    @property
    def area(self) -> int:
        return self.width * self.height
    
    def contains(self, other: 'BoundingBox') -> bool:
        return (self.left <= other.left and self.right >= other.right and
                self.top <= other.top and self.bottom >= other.bottom)
    
    def overlaps(self, other: 'BoundingBox', threshold: float = 0.3) -> bool:
        x_overlap = max(0, min(self.right, other.right) - max(self.left, other.left))
        y_overlap = max(0, min(self.bottom, other.bottom) - max(self.top, other.top))
        intersection = x_overlap * y_overlap
        min_area = min(self.area, other.area)
        if min_area == 0:
            return False
        return intersection / min_area > threshold
    
    def to_dict(self) -> Dict:
        return {"left": self.left, "top": self.top, "right": self.right, "bottom": self.bottom}

@dataclass
class DOMElement:
    id: str
    element_type: ElementType
    bbox: BoundingBox
    text: Optional[str] = None
    confidence: float = 0.0
    is_interactive: bool = False
    is_focusable: bool = False
    state: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def center(self) -> Tuple[int, int]:
        return self.bbox.center
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.element_type.value,
            "bbox": self.bbox.to_dict(),
            "text": self.text,
            "confidence": self.confidence,
            "is_interactive": self.is_interactive,
            "is_focusable": self.is_focusable,
            "state": self.state,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids,
            "center": {"x": self.center[0], "y": self.center[1]},
            "attributes": self.attributes
        }

class VisualDOM:
    def __init__(self, prism_client=None):
        self.elements: Dict[str, DOMElement] = {}
        self.root_elements: List[str] = []
        self.screen_width: int = 0
        self.screen_height: int = 0
        self.last_scan_path: Optional[str] = None
        self.prism_client = prism_client
        self._element_counter = 0
        self._ocr_available = False
        self._easyocr_reader = None
        self._last_scan_time: float = 0
        self._cache_ttl: float = 3.0
        
    def _generate_id(self) -> str:
        self._element_counter += 1
        return f"el_{self._element_counter}"
    
    def _check_ocr(self):
        if self._ocr_available:
            return
        try:
            import easyocr
            self._easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            self._ocr_available = True
        except ImportError:
            logger.warning("EasyOCR not available for VisualDOM")
    
    def is_cache_valid(self) -> bool:
        import time
        return (time.time() - self._last_scan_time) < self._cache_ttl and len(self.elements) > 0
    
    def invalidate_cache(self):
        self._last_scan_time = 0
        self.elements.clear()
    
    async def scan(self, image_path: str, use_ai: bool = True) -> 'VisualDOM':
        import time
        self.elements.clear()
        self.root_elements.clear()
        self._element_counter = 0
        self.last_scan_path = image_path
        
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Failed to load image: {image_path}")
            return self
        
        self.screen_height, self.screen_width = img.shape[:2]
        
        text_elements = await self._detect_text_regions(image_path)
        shape_elements = self._detect_shape_elements(img)
        
        all_elements = text_elements + shape_elements
        all_elements = self._deduplicate_elements(all_elements)
        
        for el in all_elements:
            self.elements[el.id] = el
        
        if use_ai and self.prism_client:
            await self._classify_with_ai(image_path)
        else:
            self._classify_heuristic()
        
        self._build_hierarchy()
        self._detect_form_fields()
        self._identify_interactive_elements()
        
        self._last_scan_time = time.time()
        logger.info(f"VisualDOM scan complete: {len(self.elements)} elements detected")
        return self
    
    async def quick_scan(self, image_path: str) -> 'VisualDOM':
        import time
        self.elements.clear()
        self.root_elements.clear()
        self._element_counter = 0
        self.last_scan_path = image_path
        
        img = cv2.imread(image_path)
        if img is None:
            return self
        
        self.screen_height, self.screen_width = img.shape[:2]
        
        text_elements = await self._detect_text_regions(image_path)
        shape_elements = self._detect_shape_elements(img)
        
        all_elements = text_elements + shape_elements
        all_elements = self._deduplicate_elements(all_elements)
        
        for el in all_elements:
            self.elements[el.id] = el
        
        self._classify_heuristic()
        self._identify_interactive_elements()
        
        self._last_scan_time = time.time()
        logger.info(f"VisualDOM quick scan: {len(self.elements)} elements")
        return self
    
    async def _detect_text_regions(self, image_path: str) -> List[DOMElement]:
        elements = []
        self._check_ocr()
        
        if self._ocr_available and self._easyocr_reader:
            try:
                results = self._easyocr_reader.readtext(image_path)
                for (bbox, text, confidence) in results:
                    if confidence < 0.3 or not text.strip():
                        continue
                    (top_left, top_right, bottom_right, bottom_left) = bbox
                    el = DOMElement(
                        id=self._generate_id(),
                        element_type=ElementType.LABEL,
                        bbox=BoundingBox(
                            int(top_left[0]), int(top_left[1]),
                            int(bottom_right[0]), int(bottom_right[1])
                        ),
                        text=text.strip(),
                        confidence=confidence
                    )
                    elements.append(el)
            except Exception as e:
                logger.error(f"OCR failed: {e}")
        
        return elements
    
    def _detect_shape_elements(self, img: np.ndarray) -> List[DOMElement]:
        elements = []
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        edges = cv2.Canny(gray, 30, 100)
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
        
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 200 or area > (self.screen_width * self.screen_height * 0.5):
                continue
            
            x, y, w, h = cv2.boundingRect(contour)
            aspect = w / h if h > 0 else 0
            
            approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
            vertices = len(approx)
            
            element_type = ElementType.UNKNOWN
            
            if 4 <= vertices <= 6:
                if 2.5 < aspect < 8 and 20 < h < 60:
                    element_type = ElementType.BUTTON
                elif 3 < aspect < 20 and 15 < h < 50:
                    element_type = ElementType.INPUT
                elif 0.8 < aspect < 1.2 and 10 < w < 40:
                    element_type = ElementType.CHECKBOX
            
            if vertices > 6 and 0.8 < aspect < 1.2:
                element_type = ElementType.ICON
            
            el = DOMElement(
                id=self._generate_id(),
                element_type=element_type,
                bbox=BoundingBox(x, y, x + w, y + h),
                confidence=0.5,
                attributes={"vertices": vertices, "aspect_ratio": aspect}
            )
            elements.append(el)
        
        return elements
    
    def _deduplicate_elements(self, elements: List[DOMElement]) -> List[DOMElement]:
        if not elements:
            return []
        
        elements.sort(key=lambda e: -e.confidence)
        
        kept = []
        for el in elements:
            is_dup = False
            for kept_el in kept:
                if el.bbox.overlaps(kept_el.bbox, threshold=0.5):
                    if el.text and not kept_el.text:
                        kept_el.text = el.text
                    if el.confidence > kept_el.confidence:
                        kept_el.element_type = el.element_type
                        kept_el.confidence = el.confidence
                    is_dup = True
                    break
            if not is_dup:
                kept.append(el)
        
        return kept
    
    async def _classify_with_ai(self, image_path: str):
        if not self.prism_client:
            return
        
        try:
            from google.genai import types
            
            with open(image_path, "rb") as f:
                image_data = f.read()
            image_part = types.Part.from_bytes(data=image_data, mime_type="image/png")
            
            element_coords = [
                {"id": el.id, "bbox": el.bbox.to_dict(), "text": el.text}
                for el in list(self.elements.values())[:30]
            ]
            
            prompt = f"""Analyze this UI screenshot and classify the detected elements.

Elements detected at these coordinates:
{json.dumps(element_coords, indent=2)}

For each element ID, classify its type from:
button, input, text_field, checkbox, radio, dropdown, toggle, link, label, heading, icon, image, menu, menu_item, tab, navigation, toolbar, sidebar, modal, card, list_item, table_cell

Also identify:
- is_interactive: can user click/interact with it?
- is_focusable: can it receive keyboard focus?
- state: any states like "selected", "disabled", "checked", "expanded"

Return JSON:
{{
  "classifications": [
    {{"id": "el_1", "type": "button", "is_interactive": true, "is_focusable": true, "state": {{}}}},
    ...
  ]
}}"""
            
            response = await self.prism_client._safe_generate(
                model=self.prism_client.model_id,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(text)
            
            for classification in data.get("classifications", []):
                el_id = classification.get("id")
                if el_id in self.elements:
                    el = self.elements[el_id]
                    type_str = classification.get("type", "unknown")
                    try:
                        el.element_type = ElementType(type_str)
                    except ValueError:
                        el.element_type = ElementType.UNKNOWN
                    el.is_interactive = classification.get("is_interactive", False)
                    el.is_focusable = classification.get("is_focusable", False)
                    el.state = classification.get("state", {})
                    el.confidence = max(el.confidence, 0.8)
            
        except Exception as e:
            logger.warning(f"AI classification failed, using heuristics: {e}")
            self._classify_heuristic()
    
    def _classify_heuristic(self):
        for el in self.elements.values():
            if el.element_type != ElementType.UNKNOWN:
                continue
            
            text = (el.text or "").lower()
            w, h = el.bbox.width, el.bbox.height
            aspect = w / h if h > 0 else 1
            
            button_keywords = ["ok", "cancel", "submit", "save", "delete", "add", "edit", "next", "back", "close", "apply", "confirm", "send", "search"]
            if any(kw in text for kw in button_keywords):
                el.element_type = ElementType.BUTTON
                el.is_interactive = True
                el.is_focusable = True
                continue
            
            if 3 < aspect < 15 and 20 < h < 50 and w > 80:
                el.element_type = ElementType.INPUT
                el.is_interactive = True
                el.is_focusable = True
                continue
            
            if 0.8 < aspect < 1.3 and 12 < w < 30 and 12 < h < 30:
                el.element_type = ElementType.CHECKBOX
                el.is_interactive = True
                el.is_focusable = True
                continue
            
            link_keywords = ["click here", "learn more", "read more", "view", "see all"]
            if any(kw in text for kw in link_keywords) or (text and len(text) < 30 and el.bbox.top > self.screen_height * 0.1):
                if el.element_type == ElementType.UNKNOWN:
                    el.element_type = ElementType.LINK
                    el.is_interactive = True
                    continue
            
            if text and len(text) > 50:
                el.element_type = ElementType.LABEL
            elif text and text[0].isupper() and len(text) < 50:
                el.element_type = ElementType.HEADING
    
    def _build_hierarchy(self):
        sorted_elements = sorted(
            self.elements.values(),
            key=lambda e: e.bbox.area,
            reverse=True
        )
        
        for el in sorted_elements:
            el.parent_id = None
            el.children_ids = []
        
        for i, child in enumerate(sorted_elements):
            for parent in sorted_elements[:i]:
                if parent.id == child.id:
                    continue
                if parent.bbox.contains(child.bbox):
                    child.parent_id = parent.id
                    parent.children_ids.append(child.id)
                    break
        
        self.root_elements = [el.id for el in self.elements.values() if el.parent_id is None]
    
    def _detect_form_fields(self):
        labels = [el for el in self.elements.values() if el.element_type == ElementType.LABEL]
        inputs = [el for el in self.elements.values() if el.element_type in [ElementType.INPUT, ElementType.TEXT_FIELD]]
        
        for inp in inputs:
            closest_label = None
            min_dist = float('inf')
            
            for label in labels:
                if label.bbox.bottom <= inp.bbox.top:
                    dist = inp.bbox.top - label.bbox.bottom
                    if dist < min_dist and dist < 50:
                        min_dist = dist
                        closest_label = label
                
                elif label.bbox.right <= inp.bbox.left:
                    dist = inp.bbox.left - label.bbox.right
                    if dist < min_dist and dist < 100:
                        min_dist = dist
                        closest_label = label
            
            if closest_label:
                inp.attributes["associated_label"] = closest_label.id
                inp.attributes["label_text"] = closest_label.text
    
    def _identify_interactive_elements(self):
        interactive_types = {
            ElementType.BUTTON, ElementType.INPUT, ElementType.TEXT_FIELD,
            ElementType.CHECKBOX, ElementType.RADIO, ElementType.DROPDOWN,
            ElementType.TOGGLE, ElementType.LINK, ElementType.MENU_ITEM,
            ElementType.TAB
        }
        
        for el in self.elements.values():
            if el.element_type in interactive_types:
                el.is_interactive = True
                el.is_focusable = True
    
    def _fuzzy_match_score(self, query: str, text: str) -> float:
        if not text:
            return 0.0
        query_lower = query.lower()
        text_lower = text.lower()
        
        if query_lower == text_lower:
            return 1.0
        if query_lower in text_lower:
            return 0.9
        if text_lower in query_lower:
            return 0.8
        
        query_words = set(query_lower.split())
        text_words = set(text_lower.split())
        common = query_words & text_words
        if common:
            return 0.6 * len(common) / max(len(query_words), len(text_words))
        
        for qw in query_words:
            for tw in text_words:
                if qw in tw or tw in qw:
                    return 0.4
        return 0.0

    def find_element(self, description: str) -> Optional[DOMElement]:
        desc_lower = description.lower()
        
        for el in self.elements.values():
            if el.text and desc_lower == el.text.lower():
                return el
        
        for el in self.elements.values():
            if el.text and desc_lower in el.text.lower():
                return el
        
        candidates = []
        for el in self.elements.values():
            if el.text:
                score = self._fuzzy_match_score(description, el.text)
                if score > 0.3:
                    candidates.append((el, score))
        
        if candidates:
            candidates.sort(key=lambda x: (-x[1], x[0].bbox.area))
            return candidates[0][0]
        
        type_mapping = {
            "button": ElementType.BUTTON,
            "input": ElementType.INPUT,
            "field": ElementType.TEXT_FIELD,
            "checkbox": ElementType.CHECKBOX,
            "toggle": ElementType.TOGGLE,
            "switch": ElementType.TOGGLE,
            "dropdown": ElementType.DROPDOWN,
            "menu": ElementType.MENU,
            "link": ElementType.LINK,
            "tab": ElementType.TAB,
        }
        
        for keyword, el_type in type_mapping.items():
            if keyword in desc_lower:
                matching = [el for el in self.elements.values() if el.element_type == el_type]
                remaining_desc = desc_lower.replace(keyword, "").strip()
                if remaining_desc and matching:
                    for el in matching:
                        if el.text and remaining_desc in el.text.lower():
                            return el
                if matching:
                    return matching[0]
        
        return None
    
    def find_element_with_score(self, description: str) -> Tuple[Optional[DOMElement], float]:
        desc_lower = description.lower()
        
        for el in self.elements.values():
            if el.text and desc_lower == el.text.lower():
                return el, 1.0
        
        for el in self.elements.values():
            if el.text and desc_lower in el.text.lower():
                return el, 0.9
        
        candidates = []
        for el in self.elements.values():
            if el.text:
                score = self._fuzzy_match_score(description, el.text)
                if score > 0.3:
                    candidates.append((el, score))
        
        if candidates:
            candidates.sort(key=lambda x: (-x[1], x[0].bbox.area))
            return candidates[0]
        
        return None, 0.0
    
    def find_elements_by_type(self, element_type: ElementType) -> List[DOMElement]:
        return [el for el in self.elements.values() if el.element_type == element_type]
    
    def find_interactive_elements(self) -> List[DOMElement]:
        return [el for el in self.elements.values() if el.is_interactive]
    
    def find_form_fields(self) -> List[Dict[str, Any]]:
        fields = []
        for el in self.elements.values():
            if el.element_type in [ElementType.INPUT, ElementType.TEXT_FIELD, ElementType.DROPDOWN, ElementType.CHECKBOX, ElementType.RADIO]:
                field_info = {
                    "element": el,
                    "label": el.attributes.get("label_text"),
                    "type": el.element_type.value,
                    "center": el.center
                }
                fields.append(field_info)
        return fields
    
    def get_element_at(self, x: int, y: int) -> Optional[DOMElement]:
        candidates = []
        for el in self.elements.values():
            if (el.bbox.left <= x <= el.bbox.right and
                el.bbox.top <= y <= el.bbox.bottom):
                candidates.append(el)
        
        if not candidates:
            return None
        
        return min(candidates, key=lambda e: e.bbox.area)
    
    def get_navigation_elements(self) -> List[DOMElement]:
        nav_elements = []
        
        for el in self.elements.values():
            if el.element_type in [ElementType.NAVIGATION, ElementType.MENU, ElementType.TAB, ElementType.TOOLBAR]:
                nav_elements.append(el)
            elif el.bbox.top < self.screen_height * 0.15:
                if el.is_interactive:
                    nav_elements.append(el)
            elif el.bbox.left < self.screen_width * 0.2 and el.bbox.height > self.screen_height * 0.5:
                if el.element_type == ElementType.UNKNOWN:
                    el.element_type = ElementType.SIDEBAR
                nav_elements.append(el)
        
        return nav_elements
    
    def to_dict(self) -> Dict:
        return {
            "screen_size": {"width": self.screen_width, "height": self.screen_height},
            "element_count": len(self.elements),
            "root_elements": self.root_elements,
            "elements": {el_id: el.to_dict() for el_id, el in self.elements.items()},
            "summary": {
                "buttons": len(self.find_elements_by_type(ElementType.BUTTON)),
                "inputs": len(self.find_elements_by_type(ElementType.INPUT)),
                "links": len(self.find_elements_by_type(ElementType.LINK)),
                "interactive": len(self.find_interactive_elements()),
                "form_fields": len(self.find_form_fields())
            }
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
    
    def get_context_for_ai(self) -> str:
        interactive = self.find_interactive_elements()
        
        context = f"Screen Size: {self.screen_width}x{self.screen_height}\n"
        context += f"Total Elements: {len(self.elements)}\n"
        context += f"Interactive Elements: {len(interactive)}\n\n"
        
        context += "Clickable Elements:\n"
        for el in interactive[:20]:
            text_info = f' "{el.text}"' if el.text else ""
            context += f"  - [{el.id}] {el.element_type.value}{text_info} at ({el.center[0]}, {el.center[1]})\n"
        
        form_fields = self.find_form_fields()
        if form_fields:
            context += "\nForm Fields:\n"
            for field in form_fields[:10]:
                label = field.get("label", "Unlabeled")
                context += f"  - {label}: {field['type']} at {field['center']}\n"
        
        return context
    
    def draw_overlay(self, output_path: str) -> str:
        if not self.last_scan_path:
            return ""
        
        img = cv2.imread(self.last_scan_path)
        if img is None:
            return ""
        
        colors = {
            ElementType.BUTTON: (0, 255, 0),
            ElementType.INPUT: (255, 165, 0),
            ElementType.TEXT_FIELD: (255, 165, 0),
            ElementType.CHECKBOX: (255, 0, 255),
            ElementType.TOGGLE: (255, 0, 255),
            ElementType.LINK: (0, 255, 255),
            ElementType.DROPDOWN: (128, 0, 128),
            ElementType.MENU: (0, 128, 255),
            ElementType.TAB: (255, 128, 0),
            ElementType.LABEL: (128, 128, 128),
            ElementType.HEADING: (255, 255, 0),
        }
        
        for el in self.elements.values():
            color = colors.get(el.element_type, (200, 200, 200))
            b = el.bbox
            
            overlay = img.copy()
            cv2.rectangle(overlay, (b.left, b.top), (b.right, b.bottom), color, -1)
            cv2.addWeighted(overlay, 0.2, img, 0.8, 0, img)
            
            cv2.rectangle(img, (b.left, b.top), (b.right, b.bottom), color, 2)
            
            label = f"{el.id}: {el.element_type.value}"
            if el.text:
                label += f" '{el.text[:15]}...'" if len(el.text) > 15 else f" '{el.text}'"
            
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
            cv2.rectangle(img, (b.left, b.top - th - 4), (b.left + tw + 4, b.top), color, -1)
            cv2.putText(img, label, (b.left + 2, b.top - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        cv2.imwrite(output_path, img)
        return output_path


visual_dom = VisualDOM()
