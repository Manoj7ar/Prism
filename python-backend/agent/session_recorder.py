import os
import json
import asyncio
import time
import pyautogui
from PIL import Image
from collections import deque
from datetime import datetime
from typing import List, Dict, Any

class SessionRecorder:
    MAX_SESSION_AGE_HOURS = 4
    MAX_SESSION_SIZE_MB = 500
    CLEANUP_CHECK_INTERVAL = 10

    def __init__(self, interval: int = 15, max_frames: int = 720, redactor=None, on_screenshot=None, get_metadata=None):
        self.interval = interval
        self.max_frames = max_frames
        self.redactor = redactor
        self.on_screenshot = on_screenshot
        self.get_metadata = get_metadata
        self.frames = deque(maxlen=max_frames)
        self.is_recording = False
        self.is_paused = True
        self.is_disabled = False
        self.ocr_queue = asyncio.Queue()
        
        self.accumulated_time = 0.0
        self.last_resume_time = None
        self.wipe_interval = 10800
        
        self._frame_count_since_cleanup = 0
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.storage_path = os.path.join(base_dir, "session_memory")
        self.settings_path = os.path.join(base_dir, "session_memory", "settings.json")
        os.makedirs(self.storage_path, exist_ok=True)
        self._load_settings()
        self._load_metadata()
        self._enforce_storage_limits()

    async def start(self):
        if not self.is_recording:
            self.is_recording = True
            asyncio.create_task(self._record_loop())
            asyncio.create_task(self._ocr_worker())

    async def _ocr_worker(self):
        while self.is_recording:
            try:
                frame_data = await self.ocr_queue.get()
                if not self.redactor:
                    continue
                
                path = frame_data["path"]
                if os.path.exists(path):
                    text_content = self.redactor.get_text(path)
                    
                    if text_content:
                        for frame in self.frames:
                            if frame["path"] == path:
                                frame["metadata"]["ocr_text"] = text_content
                                self._save_metadata()
                                break
                
                self.ocr_queue.task_done()
            except Exception:
                await asyncio.sleep(0.5)

    async def stop(self):
        self.is_recording = False

    def _load_settings(self):
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r") as f:
                    settings = json.load(f)
                    self.is_disabled = settings.get("disabled", False)
        except Exception:
            pass

    def _save_settings(self):
        try:
            with open(self.settings_path, "w") as f:
                json.dump({"disabled": self.is_disabled}, f)
        except Exception:
            pass

    def set_disabled(self, disabled: bool):
        self.is_disabled = disabled
        self._save_settings()
        if disabled:
            self.clear()

    def pause(self):
        if not self.is_paused:
            if self.last_resume_time:
                self.accumulated_time += time.time() - self.last_resume_time
            self.is_paused = True
            self.last_resume_time = None

    def resume(self):
        if self.is_paused:
            self.is_paused = False
            self.last_resume_time = time.time()

    def _get_total_elapsed(self) -> float:
        total = self.accumulated_time
        if not self.is_paused and self.last_resume_time:
            total += time.time() - self.last_resume_time
        return total

    def _save_metadata(self):
        try:
            meta_path = os.path.join(self.storage_path, "metadata.json")
            data = list(self.frames)
            with open(meta_path, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _load_metadata(self):
        try:
            meta_path = os.path.join(self.storage_path, "metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r") as f:
                    data = json.load(f)
                    valid_data = []
                    for item in data:
                        if os.path.exists(item.get("path", "")) or os.path.exists(item.get("full_path", "")):
                            valid_data.append(item)
                    self.frames.extend(valid_data)
        except Exception:
            pass

    def _get_storage_size_mb(self) -> float:
        total_size = 0
        try:
            for f in os.listdir(self.storage_path):
                if f.endswith(".png"):
                    file_path = os.path.join(self.storage_path, f)
                    total_size += os.path.getsize(file_path)
        except Exception:
            pass
        return total_size / (1024 * 1024)

    def _enforce_storage_limits(self):
        now = time.time()
        max_age_seconds = self.MAX_SESSION_AGE_HOURS * 3600
        
        frames_to_remove = []
        for frame in self.frames:
            frame_time = frame.get("time", 0)
            if now - frame_time > max_age_seconds:
                frames_to_remove.append(frame)
        
        for frame in frames_to_remove:
            self._delete_frame_files(frame)
            if frame in self.frames:
                self.frames.remove(frame)
        
        current_size = self._get_storage_size_mb()
        if current_size > self.MAX_SESSION_SIZE_MB:
            # Hard reset when memory storage is full for a clean new capture window.
            self.clear()
            return
        
        self._save_metadata()

    def _delete_frame_files(self, frame: Dict):
        try:
            thumb_path = frame.get("path")
            full_path = frame.get("full_path")
            if thumb_path and os.path.exists(thumb_path):
                os.remove(thumb_path)
            if full_path and os.path.exists(full_path):
                os.remove(full_path)
        except Exception:
            pass

    async def _record_loop(self):
        while self.is_recording:
            if self._get_total_elapsed() > self.wipe_interval:
                self.clear()

            if not self.is_paused and not self.is_disabled:
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    full_filename = f"frame_{timestamp}_full.png"
                    thumb_filename = f"frame_{timestamp}_thumb.png"
                    
                    full_path = os.path.join(self.storage_path, full_filename)
                    thumb_path = os.path.join(self.storage_path, thumb_filename)
                    
                    screenshot = pyautogui.screenshot()
                    
                    screenshot.save(full_path, "PNG", optimize=True)
                    
                    base_width = 512
                    w_percent = (base_width / float(screenshot.size[0]))
                    h_size = int((float(screenshot.size[1]) * float(w_percent)))
                    thumb_img = screenshot.resize((base_width, h_size), Image.Resampling.LANCZOS)
                    
                    thumb_img.save(thumb_path, "PNG", optimize=True)
                    
                    metadata = {}
                    if self.get_metadata:
                        try:
                            metadata = self.get_metadata()
                        except Exception:
                            pass

                    if self.redactor:
                        try:
                            active_app = metadata.get("app_name")
                            await self.redactor.redact_image(full_path, active_app=active_app)
                            await self.redactor.redact_image(thumb_path, active_app=active_app)
                        except Exception:
                            pass

                    frame_data = {
                        "timestamp": timestamp,
                        "path": thumb_path,
                        "full_path": full_path,
                        "time": time.time(),
                        "metadata": metadata
                    }
                    self.frames.append(frame_data)
                    self._save_metadata()

                    await self.ocr_queue.put(frame_data)

                    if self.on_screenshot:
                        try:
                            if asyncio.iscoroutinefunction(self.on_screenshot):
                                await self.on_screenshot()
                            else:
                                self.on_screenshot()
                        except Exception:
                            pass

                    self._frame_count_since_cleanup += 1
                    if self._frame_count_since_cleanup >= self.CLEANUP_CHECK_INTERVAL:
                        self._frame_count_since_cleanup = 0
                        self._enforce_storage_limits()

                    current_thumb_paths = {f["path"] for f in self.frames}
                    current_full_paths = {f.get("full_path") for f in self.frames}
                    
                    for f in os.listdir(self.storage_path):
                        full_f_path = os.path.join(self.storage_path, f)
                        if (f.endswith(".png") and 
                            full_f_path not in current_thumb_paths and 
                            full_f_path not in current_full_paths):
                            try:
                                os.remove(full_f_path)
                            except Exception:
                                pass

                except Exception:
                    pass

            await asyncio.sleep(self.interval)

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self.frames)

    def get_status(self) -> Dict[str, Any]:
        total_elapsed = self._get_total_elapsed()
        recording_active = self.is_recording and (not self.is_paused) and (not self.is_disabled)
        return {
            "is_recording": self.is_recording,
            "is_paused": self.is_paused,
            "is_disabled": self.is_disabled,
            "recording": recording_active,
            "frame_count": len(self.frames),
            "elapsed_seconds": int(total_elapsed),
            "duration_minutes": int(total_elapsed // 60),
            "max_minutes": self.wipe_interval // 60,
            "seconds_remaining": int(max(0, self.wipe_interval - total_elapsed)),
            "storage_mb": round(self._get_storage_size_mb(), 2),
            "capture_interval_seconds": self.interval,
            "max_storage_mb": self.MAX_SESSION_SIZE_MB
        }

    def clear(self):
        self.frames.clear()
        self.accumulated_time = 0.0
        if not self.is_paused:
            self.last_resume_time = time.time()
        self._cleanup_old_files()

    def _cleanup_old_files(self):
        try:
            for f in os.listdir(self.storage_path):
                if f.endswith(".png"):
                    try:
                        os.remove(os.path.join(self.storage_path, f))
                    except Exception:
                        pass
        except Exception:
            pass
