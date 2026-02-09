import asyncio
import os
import logging
import uuid
import json
import inspect
from typing import Dict, List, Any, Callable, Awaitable, Optional
from .context_detector import ContextDetector
from .prism_client import PrismClient
from automation.browser import BrowserAutomation
from automation.desktop import DesktopAutomation
from automation.file_system import FileSystemOperations
from automation.ui_highlighter import ui_highlighter
from automation.visual_dom import VisualDOM
from .memory import memory_system
from .task_planner import TaskPlanner
from utils.privacy import init_privacy

logger = logging.getLogger("TaskExecutor")

MAX_TOTAL_ACTIONS = 50
MAX_REPETITIVE_ACTIONS = 5
MAX_AGENTIC_LOOPS = 10
RECOVERY_RETRY_LIMIT = 3

class TaskExecutor:
    def __init__(self, prism_client: PrismClient):
        self.browser = BrowserAutomation()
        self.desktop = DesktopAutomation()
        self.files = FileSystemOperations()
        self.prism_client = prism_client
        self.context_detector = ContextDetector()
        self.planner = TaskPlanner(prism_client)
        self.privacy = init_privacy(prism_client)
        self.visual_dom = VisualDOM(prism_client)
        self.total_actions_performed = 0
        self.last_action_sig = None
        self.repetition_count = 0
        self.last_result = None
        self.agentic_loop_count = 0
        self.should_stop = False
        self.overlay_callback = None
        self.confirm_event = asyncio.Event()
        self._dom_cache_valid = False
        self.attached_file = None
    
    def set_attached_file(self, file_context: Optional[Dict[str, str]]):
        """Set the currently attached file context from user upload"""
        self.attached_file = file_context
    
    def get_attached_file_path(self) -> Optional[str]:
        """Get the path of the currently attached file"""
        return self.attached_file.get("path") if self.attached_file else None
    
    def force_stop(self):
        self.should_stop = True
    
    def reset_stop(self):
        self.should_stop = False

    @property
    def _action_map(self):
        return {
            'read_files': self.files.read_files,
            'read_and_summarize_files': self._handle_read_summarize,
            'browser_navigate': self.browser.navigate,
            'browser_click': self.browser.click_element,
            'browser_type': self.browser.type_text,
            'browser_extract': self.browser.extract_content,
            'type_text': self._handle_type_text,
            'type_previous_result': self._handle_type_previous_result,
            'press_keys': self._handle_press_keys,
            'open_app': self._handle_open_app,
            'visual_click': self._handle_visual_click,
            'wait': self._handle_wait,
            'wait_for_visual': self._handle_wait_for_visual,
            'reply': self._handle_reply,
            'debug_error': self._handle_debug_error,

            'batch_process': self._handle_batch_process,
            'scroll': self._handle_scroll,
            'scroll_to_element': self._handle_scroll_to_element,
            'drag_drop': self._handle_drag_drop,
            'switch_window': self._handle_switch_window,
            'minimize_window': self._handle_minimize_window,
            'maximize_window': self._handle_maximize_window,
            'snap_window': self._handle_snap_window,
            'close_window': self._handle_close_window,
            'switch_tab': self._handle_switch_tab,
            'new_tab': self._handle_new_tab,
            'close_tab': self._handle_close_tab,
            'go_back': self._handle_go_back,
            'go_forward': self._handle_go_forward,
            'refresh': self._handle_refresh,
            'focus_address_bar': self._handle_focus_address_bar,
            'search_in_page': self._handle_search_in_page,
            'select_all': self._handle_select_all,
            'copy': self._handle_copy,
            'paste': self._handle_paste,
            'undo': self._handle_undo,
            'redo': self._handle_redo,
            'escape': self._handle_escape,
            'enter': self._handle_enter,
            'navigate_url': self._handle_navigate_url,
            'double_click': lambda p: self._handle_visual_action('double_click_at', p),
            'right_click': lambda p: self._handle_visual_action('right_click_at', p),
            'hover': lambda p: self._handle_visual_action('move_to', p),
            'triple_click': lambda p: self._handle_visual_action('triple_click_at', p),
            'analyze_screen': self._handle_analyze_screen,
            'summarize': self._handle_summarize,
            'toggle_bluetooth': self._handle_toggle_bluetooth,
            'system_setting': self._handle_system_setting,
            'scan_screen': self._handle_scan_screen,
            'dom_click': self._handle_dom_click,
            'fill_form': self._handle_fill_form,
            'attach_file': self._handle_attach_file,
            'select_file_dialog': self._handle_select_file_dialog,
            'copy_file_to_clipboard': self._handle_copy_file_to_clipboard,
            'web_click': self._handle_web_click,
            'web_click_text': self._handle_web_click_text,
            'web_type': self._handle_web_type,
            'web_type_submit': self._handle_web_type_submit,
            'web_navigate': self._handle_web_navigate,
            'web_scroll': self._handle_web_scroll,
            'web_new_tab': self._handle_web_new_tab,
            'web_close_tab': self._handle_web_close_tab,
            'web_switch_tab': self._handle_web_switch_tab,
            'web_back': self._handle_web_back,
            'web_forward': self._handle_web_forward,
            'web_refresh': self._handle_web_refresh,
            'web_search_google': self._handle_web_search_google,
            'web_search_youtube': self._handle_web_search_youtube,
            'web_gmail_compose': self._handle_web_gmail_compose,
            'web_fill_form': self._handle_web_fill_form,
            'web_press_key': self._handle_web_press_key,
            'web_get_url': self._handle_web_get_url,
            'web_get_title': self._handle_web_get_title,
        }

    async def wait_for_user_confirm(self, timeout: int = 300):
        """Wait for user to click 'Next' in Companion Mode"""
        self.confirm_event.clear()
        try:
            await asyncio.wait_for(self.confirm_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def execute_tasks(self, tasks: List[Dict[str, Any]], status_list: List[Dict[str, Any]] = None, history: List[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        results = []
        self.total_actions_performed = 0
        self.should_stop = False
        
        for idx, task in enumerate(tasks):
            if self.should_stop:
                raise Exception("STOPPED")
            
            res = await self.execute_with_retry(task, status_list, idx)
            results.append(res)
            
            if not res.get('success') and not res.get('recovered'):
                logger.info("Task failed. Attempting replan...")
                new_plan = await self.planner.replan(task, res.get('error', 'Error'), history, self.context_detector.get_context())
                if new_plan:
                    results.extend(await self.execute_tasks(new_plan, status_list, history))
                    break

        if tasks:
            memory_system.add_command(tasks[0].get('description', 'Task'), all(r.get('success') for r in results))
        return results

    async def execute_with_retry(self, task: Dict[str, Any], status_list: List[Dict[str, Any]] = None, idx: int = None, companion_mode: bool = False) -> Dict[str, Any]:
        if status_list and idx is not None:
            status_list[idx]['status'] = 'in_progress'
        
        is_companion = companion_mode or task.get('wait_for_user', False)
        
        if is_companion:
            return await self._execute_companion_step(task, status_list, idx)
            
        if self.overlay_callback and (task.get('annotation') or task.get('narration')):
            annotation = task.get('annotation', {})
            if annotation and annotation.get('element') and not annotation.get('x'):
                try:
                    path = f"overlay_temp_{uuid.uuid4().hex[:8]}.png"
                    await self.capture_and_redact(path)
                    coords = await self.prism_client.locate_element_visually(path, annotation['element'])
                    if os.path.exists(path): os.remove(path)
                    if coords:
                        annotation['x'] = coords['x']
                        annotation['y'] = coords['y']
                except Exception as e:
                    logger.warning(f"Could not locate element for annotation: {e}")

            await self.overlay_callback({
                "type": "draw",
                "annotation": annotation,
                "narration": task.get('narration')
            })

        try:
            result = await self.perform_action(task)

            if status_list and idx is not None:
                status_list[idx]['status'] = 'completed'
            
            if self.overlay_callback and task.get('annotation'):
                 if not task.get('wait_for_user'):
                     await asyncio.sleep(1.0)
                 await self.overlay_callback({"type": "clear"})

            return {"task": task, "action": task.get('action'), "success": True, "output": result}
        except Exception as e:
            logger.error(f"Task failed: {task.get('action')} - {e}")
            recovery = await self._attempt_recovery(task, str(e))
            if status_list and idx is not None:
                status_list[idx]['status'] = 'completed' if recovery.get('recovered') else 'pending'
            return {"task": task, "action": task.get('action'), "success": recovery.get('recovered', False), "error": str(e), "recovered": recovery.get('recovered', False)}

    async def _execute_companion_step(self, task: Dict[str, Any], status_list: List[Dict[str, Any]] = None, idx: int = None) -> Dict[str, Any]:
        """Execute a task in companion/teaching mode - guide user through each step"""
        action = task.get('action')
        params = task.get('params', {})
        narration = task.get('narration', task.get('description', ''))
        annotation = task.get('annotation', {})
        
        target_coords = None
        
        if action in ['visual_click', 'double_click', 'right_click', 'hover'] or annotation.get('element'):
            element_desc = params.get('element') or annotation.get('element')
            if element_desc:
                try:
                    path = f"companion_temp_{uuid.uuid4().hex[:8]}.png"
                    await self.capture_and_redact(path)
                    coords = await self.prism_client.locate_element_visually(path, element_desc)
                    if os.path.exists(path): os.remove(path)
                    if coords:
                        target_coords = coords
                except Exception as e:
                    logger.warning(f"Companion mode: Could not locate element '{element_desc}': {e}")
        
        if target_coords:
            self.desktop.smooth_move_to(target_coords['x'], target_coords['y'], duration=0.5)
            
            if self.overlay_callback:
                await self.overlay_callback({
                    "type": "draw",
                    "annotation": {
                        "type": annotation.get('type', 'circle'),
                        "x": target_coords['x'],
                        "y": target_coords['y'],
                        "width": annotation.get('width', 80),
                        "height": annotation.get('height', 80),
                    },
                    "narration": narration
                })
        elif narration and self.overlay_callback:
            await self.overlay_callback({
                "type": "draw",
                "annotation": annotation if annotation.get('type') else None,
                "narration": narration
            })
        
        if self.overlay_callback:
            wait_condition = task.get('wait_condition', self._get_wait_condition(task))
            await self.overlay_callback({
                "type": "draw",
                "annotation": {"type": "waiting", "value": True, "condition": wait_condition},
                "narration": narration
            })
        
        logger.info(f"Companion Mode: Waiting for user to perform action. Condition: {task.get('wait_condition', 'Complete step')}")
        confirmed = await self.wait_for_user_confirm(timeout=300)
        
        if self.overlay_callback:
            await self.overlay_callback({
                "type": "draw",
                "annotation": {"type": "waiting", "value": False},
            })
            await self.overlay_callback({"type": "clear"})
        
        if status_list and idx is not None:
            status_list[idx]['status'] = 'completed'
        
        return {
            "task": task, 
            "action": action, 
            "success": True, 
            "output": f"User completed: {narration}",
            "companion_mode": True
        }
    
    def _get_wait_condition(self, task: Dict[str, Any]) -> str:
        """Generate a human-readable wait condition based on the task"""
        action = task.get('action', '')
        params = task.get('params', {})
        
        if action == 'visual_click':
            return f"Click on {params.get('element', 'the highlighted element')}"
        elif action == 'open_app':
            return f"Open {params.get('app_name', params.get('name', 'the application'))}"
        elif action == 'type_text':
            return f"Type the text"
        elif action == 'browser_navigate':
            return f"Navigate to the website"
        elif action == 'scroll':
            return f"Scroll {params.get('direction', 'down')}"
        else:
            return task.get('description', 'Complete this step')

    async def perform_action(self, task: Dict[str, Any]) -> Any:
        if self.total_actions_performed >= MAX_TOTAL_ACTIONS:
            raise Exception("Maximum actions reached")
            
        action = task.get('action')
        params = task.get('params', {})
        
        sig = f"{action}:{str(params)}"
        self.repetition_count = (self.repetition_count + 1) if sig == self.last_action_sig else 1
        self.last_action_sig = sig
        
        if self.repetition_count > MAX_REPETITIVE_ACTIONS:
            raise Exception("Repetitive action detected")
            
        self.total_actions_performed += 1
        handler = self._action_map.get(action)
        if not handler:
            raise ValueError(f"Unknown action: {action}")
            
        res = handler(params)
        if inspect.isawaitable(res):
            res = await res
            
        if action in ['read_files', 'browser_extract', 'summarize', 'read_and_summarize_files']:
            self.last_result = res
        return res

    async def _handle_type_text(self, params):
        return self.desktop.type_text(params.get('text', ''))

    async def _handle_type_previous_result(self, _):
        return self.desktop.type_text(str(self.last_result))

    async def _handle_press_keys(self, params):
        return self.desktop.press_keys(params.get('keys', []))

    async def _handle_open_app(self, params):
        return self.desktop.open_application(params.get('app_name', params.get('name', '')))

    async def _handle_wait(self, params):
        await asyncio.sleep(params.get('seconds', 1))
        return f"Waited {params.get('seconds', 1)}s"

    async def _handle_reply(self, _):
        return None

    async def _handle_scroll(self, params):
        return self.desktop.smart_scroll(params.get('direction', 'down'), params.get('amount', 3))

    async def _handle_minimize_window(self, _):
        return self.desktop.minimize_window()

    async def _handle_maximize_window(self, _):
        return self.desktop.maximize_window()

    async def _handle_snap_window(self, params):
        direction = params.get('direction', 'left')
        if direction == 'left':
            return self.desktop.snap_window_left()
        else:
            return self.desktop.snap_window_right()

    async def _handle_close_window(self, _):
        return self.desktop.close_window()

    async def _handle_switch_tab(self, params):
        direction = params.get('direction', 'next')
        if direction == 'next':
            return self.desktop.switch_tab_next()
        else:
            return self.desktop.switch_tab_prev()

    async def _handle_new_tab(self, _):
        return self.desktop.new_tab()

    async def _handle_close_tab(self, _):
        return self.desktop.close_tab()

    async def _handle_go_back(self, _):
        return self.desktop.go_back()

    async def _handle_go_forward(self, _):
        return self.desktop.go_forward()

    async def _handle_refresh(self, _):
        return self.desktop.refresh_page()

    async def _handle_focus_address_bar(self, _):
        return self.desktop.focus_address_bar()

    async def _handle_search_in_page(self, params):
        return self.desktop.search_in_page(params.get('text', ''))

    async def _handle_select_all(self, _):
        return self.desktop.select_all()

    async def _handle_copy(self, _):
        return self.desktop.copy_selection()

    async def _handle_paste(self, _):
        return self.desktop.paste()

    async def _handle_undo(self, _):
        return self.desktop.undo()

    async def _handle_redo(self, _):
        return self.desktop.redo()

    async def _handle_escape(self, _):
        return self.desktop.escape()

    async def _handle_enter(self, _):
        return self.desktop.enter()

    async def _handle_navigate_url(self, params):
        return self.desktop.navigate_to_url(
            params.get('url', ''),
            params.get('browser_name', params.get('browser', ''))
        )

    async def _handle_batch_process(self, params):
        results = []
        for f in params.get('file_paths', []):
            try:
                content = await self.files.read_files([f])
                if content and content[0]['success']:
                    res = await self.prism_client.generate_content(f"{params.get('operation', 'Summarize')}:\n{content[0]['content']}")
                    results.append({"file": f, "output": res})
            except Exception as e:
                results.append({"file": f, "error": str(e)})
        return results

    async def _handle_read_summarize(self, params):
        file_paths = params.get('file_paths') or params.get('file_patths') or params.get('files')
        if not file_paths and isinstance(params, list):
            file_paths = params
            
        if not file_paths:
            return "No files provided for summary."
            
        # Emit a special thought to trigger the PDF reading animation
        await self.prism_client.emit_thought("Reading and summarizing PDF...", type="reading_pdf")
            
        files = await self.files.read_files(file_paths)
        combined = "\n".join([f"--- {r['path']} ---\n{r['content']}" for r in files if r.get('success')])
        return await self.prism_client.generate_content(f"Summarize:\n{combined}") if combined else "No content."

    async def _handle_visual_click(self, params):
        element_desc = params.get('element', '')
        use_dom_first = params.get('use_dom', True)
        hover_first = params.get('hover_first', False)
        
        desc_lower = element_desc.lower()
        needs_hover = hover_first or any(kw in desc_lower for kw in ['play button', 'green play', 'play icon', 'play on'])
        
        path = f"click_temp_{uuid.uuid4().hex[:8]}.png"
        await self.capture_and_redact(path)
        
        if use_dom_first:
            try:
                if not self.visual_dom.is_cache_valid():
                    await self.visual_dom.quick_scan(path)
                
                element, score = self.visual_dom.find_element_with_score(element_desc)
                
                if element and score >= 0.6:
                    x, y = element.center
                    logger.info(f"[DOM_CLICK] Found '{element_desc}' via DOM (score={score:.2f}) at ({x}, {y})")
                    if os.path.exists(path): os.remove(path)
                    if needs_hover:
                        self.desktop.move_to(x, y)
                        await asyncio.sleep(0.5)
                        await self.capture_and_redact(path)
                        new_coords = await self.prism_client.locate_element_visually(path, element_desc)
                        if os.path.exists(path): os.remove(path)
                        if new_coords:
                            return self.desktop.click_at(new_coords['x'], new_coords['y'])
                    return self.desktop.click_at(x, y)
                elif element and score >= 0.4:
                    x, y = element.center
                    logger.info(f"[DOM_CLICK] Low-confidence match '{element_desc}' (score={score:.2f}), verifying with vision...")
            except Exception as e:
                logger.warning(f"[DOM_CLICK] DOM scan failed: {e}, falling back to vision")
        
        coords = await self.prism_client.locate_element_visually(path, element_desc)
        
        if coords and needs_hover:
            self.desktop.move_to(coords['x'], coords['y'])
            await asyncio.sleep(0.5)
            path2 = f"click_hover_{uuid.uuid4().hex[:8]}.png"
            await self.capture_and_redact(path2)
            new_coords = await self.prism_client.locate_element_visually(path2, element_desc)
            if os.path.exists(path2): os.remove(path2)
            if new_coords:
                coords = new_coords
        
        if os.path.exists(path): os.remove(path)
        
        if coords:
            self.visual_dom.invalidate_cache()
            return self.desktop.click_at(coords['x'], coords['y'])
        raise Exception(f"Not found: {element_desc}")

    async def _handle_wait_for_visual(self, params):
        if not await self.prism_client.wait_for_visual(params['condition'], params.get('timeout', 15)):
            raise Exception(f"Timeout: {params['condition']}")
        return f"Met: {params['condition']}"

    async def _handle_debug_error(self, _):
        path = self.context_detector.capture_active_window()
        if not path: return "Capture failed."
        res = await self.prism_client.analyze_coding_error(path)
        if os.path.exists(path): os.remove(path)
        return res

    async def _handle_agentic_goal(self, params):
        goal = params.get('goal')
        if not goal: return "No goal."
        
        self.agentic_loop_count = 0
        all_res = []
        while self.agentic_loop_count < MAX_AGENTIC_LOOPS:
            self.agentic_loop_count += 1
            check = await self.prism_client.generate_content(f"Goal: {goal}. Prev: {str(all_res[-2:])}. Achieved? JSON: {{\"achieved\": bool}}")
            try:
                if json.loads(check.strip()).get("achieved"): return {"success": True, "results": all_res}
            except Exception:
                pass
            
            tasks = await self.planner.plan(goal, self.context_detector.get_context())
            if not tasks: break
            res = await self.execute_tasks(tasks)
            all_res.extend(res)
            if all(not r.get('success') for r in res): break
            
        return {"success": False, "results": all_res}

    async def _handle_scroll_to_element(self, params):
        for i in range(params.get('max_scrolls', 10)):
            path = f"scroll_{i}.png"
            await self.capture_and_redact(path)
            coords = await self.prism_client.locate_element_visually(path, params['element'])
            if os.path.exists(path): os.remove(path)
            if coords: return f"Found {params['element']}"
            self.desktop.smart_scroll(params.get('direction', 'down'), 3)
            await asyncio.sleep(0.3)
        raise Exception(f"Not found: {params['element']}")

    async def _handle_drag_drop(self, params):
        def get_coords(p):
            if p.get('element'):
                return 0, 0
            return p.get('x', 0), p.get('y', 0)
        sx, sy = get_coords(params.get('start', {}))
        ex, ey = get_coords(params.get('end', {}))
        return self.desktop.drag_drop(sx, sy, ex, ey)

    async def _handle_switch_window(self, params):
        name = params.get('window')
        if name and self.desktop.switch_to_window_by_name(name): return f"Switched to {name}"
        return self.desktop.switch_window()

    async def _handle_visual_action(self, method, params):
        element_desc = params.get('element')
        
        if element_desc:
            path = f"vis_temp_{uuid.uuid4().hex[:8]}.png"
            await self.capture_and_redact(path)
            
            try:
                if not self.visual_dom.is_cache_valid():
                    await self.visual_dom.quick_scan(path)
                
                element, score = self.visual_dom.find_element_with_score(element_desc)
                if element and score >= 0.6:
                    x, y = element.center
                    logger.info(f"[DOM_{method.upper()}] Found '{element_desc}' via DOM (score={score:.2f}) at ({x}, {y})")
                    if os.path.exists(path): os.remove(path)
                    return getattr(self.desktop, method)(x, y)
            except Exception as e:
                logger.warning(f"[DOM_{method.upper()}] DOM failed: {e}, falling back to vision")
            
            coords = await self.prism_client.locate_element_visually(path, element_desc)
            if os.path.exists(path): os.remove(path)
            
            if coords:
                self.visual_dom.invalidate_cache()
                return getattr(self.desktop, method)(coords['x'], coords['y'])
            raise Exception(f"Not found: {element_desc}")
        
        return getattr(self.desktop, method)(params.get('x', 0), params.get('y', 0))

    async def _handle_analyze_screen(self, _):
        path = f"analyze_{uuid.uuid4().hex[:8]}.png"
        await self.capture_and_redact(path)
        res = await self.prism_client.analyze_screen_state(path)
        if os.path.exists(path): os.remove(path)
        return res

    async def _handle_summarize(self, _):
        path = f"summary_{uuid.uuid4().hex[:8]}.png"
        await self.capture_and_redact(path)
        res = await self.prism_client.summarize_page_state(path)
        if os.path.exists(path): os.remove(path)
        return res

    async def _handle_toggle_bluetooth(self, params):
        enable = params.get('enable', True)
        if isinstance(enable, str):
            enable = enable.lower() in ['true', 'on', '1', 'yes']
        return self.desktop.toggle_bluetooth(enable)

    async def _handle_system_setting(self, params):
        setting = params.get('setting', '').lower()
        action = params.get('action', 'toggle').lower()
        
        if 'bluetooth' in setting:
            enable = action in ['enable', 'on', 'turn_on', 'true']
            if action == 'toggle':
                status = self.desktop.get_bluetooth_status()
                enable = not status.get('enabled', False)
            return self.desktop.toggle_bluetooth(enable)
        
        return f"Unknown system setting: {setting}"

    async def _handle_scan_screen(self, params):
        """Scan screen and build Visual DOM for intelligent element detection"""
        path = f"dom_scan_{uuid.uuid4().hex[:8]}.png"
        await self.capture_and_redact(path)
        
        use_ai = params.get('use_ai', True)
        await self.visual_dom.scan(path, use_ai=use_ai)
        self._dom_cache_valid = True
        
        if os.path.exists(path): 
            os.remove(path)
        
        summary = self.visual_dom.to_dict().get("summary", {})
        return {
            "elements_found": len(self.visual_dom.elements),
            "interactive": summary.get("interactive", 0),
            "buttons": summary.get("buttons", 0),
            "inputs": summary.get("inputs", 0),
            "form_fields": summary.get("form_fields", 0)
        }

    async def _handle_dom_click(self, params):
        """Click element using Visual DOM - faster than vision-based click"""
        element_desc = params.get('element', '')
        
        if not self._dom_cache_valid or not self.visual_dom.elements:
            await self._handle_scan_screen({})
        
        element = self.visual_dom.find_element(element_desc)
        
        if element:
            x, y = element.center
            return self.desktop.click_at(x, y)
        
        return await self._handle_visual_click(params)

    async def _handle_fill_form(self, params):
        """Fill form fields intelligently using Visual DOM"""
        fields_to_fill = params.get('fields', {})
        
        if not self._dom_cache_valid or not self.visual_dom.elements:
            await self._handle_scan_screen({})
        
        form_fields = self.visual_dom.find_form_fields()
        results = []
        
        for label_text, value in fields_to_fill.items():
            matched_field = None
            label_lower = label_text.lower()
            
            for field in form_fields:
                field_label = (field.get('label') or '').lower()
                if label_lower in field_label or field_label in label_lower:
                    matched_field = field
                    break
            
            if matched_field:
                x, y = matched_field['center']
                self.desktop.click_at(x, y)
                await asyncio.sleep(0.2)
                self.desktop.type_text(str(value))
                results.append({"field": label_text, "success": True})
            else:
                results.append({"field": label_text, "success": False, "error": "Field not found"})
        
        self._dom_cache_valid = False
        return results

    async def _handle_attach_file(self, params):
        """Attach the user-uploaded file to an application (e.g., chat app, email)
        This handles the full flow: click attach button, navigate file dialog, select file
        """
        file_path = params.get('file_path') or self.get_attached_file_path()
        if not file_path:
            raise Exception("No file attached. Please attach a file first.")
        
        if not os.path.exists(file_path):
            raise Exception(f"File not found: {file_path}")
        
        method = params.get('method', 'dialog')
        
        if method == 'clipboard':
            result = self.desktop.copy_file_to_clipboard(file_path)
            await asyncio.sleep(0.3)
            self.desktop.paste()
            return f"Attached via clipboard: {file_path}"
        else:
            await asyncio.sleep(0.5)
            return self.desktop.select_file_in_dialog(file_path)

    async def _handle_select_file_dialog(self, params):
        """Select a file in an already-open file dialog"""
        file_path = params.get('file_path') or self.get_attached_file_path()
        if not file_path:
            raise Exception("No file path provided")
        return self.desktop.select_file_in_dialog(file_path)

    async def _handle_copy_file_to_clipboard(self, params):
        """Copy a file to clipboard for pasting"""
        file_path = params.get('file_path') or self.get_attached_file_path()
        if not file_path:
            raise Exception("No file path provided")
        return self.desktop.copy_file_to_clipboard(file_path)

    async def _handle_web_click(self, params):
        """Click element in browser using selector"""
        selector = params.get('selector', '')
        by = params.get('by', 'css')
        result = await self.browser.click_element(selector, by)
        if not result.get('success'):
            raise Exception(result.get('error', 'Click failed'))
        return result.get('message', 'Clicked')

    async def _handle_web_click_text(self, params):
        """Click element in browser by visible text"""
        text = params.get('text', '')
        exact = params.get('exact', False)
        result = await self.browser.click_by_text(text, exact)
        if not result.get('success'):
            raise Exception(result.get('error', 'Click failed'))
        return result.get('message', 'Clicked')

    async def _handle_web_type(self, params):
        """Type text into browser input field"""
        selector = params.get('selector', '')
        text = params.get('text', '')
        by = params.get('by', 'css')
        result = await self.browser.type_text(selector, text, by)
        if not result.get('success'):
            raise Exception(result.get('error', 'Type failed'))
        return result.get('message', 'Typed')

    async def _handle_web_type_submit(self, params):
        """Type text and press Enter"""
        selector = params.get('selector', '')
        text = params.get('text', '')
        by = params.get('by', 'css')
        result = await self.browser.type_and_submit(selector, text, by)
        if not result.get('success'):
            raise Exception(result.get('error', 'Type and submit failed'))
        return result.get('message', 'Typed and submitted')

    async def _handle_web_navigate(self, params):
        """Navigate browser to URL"""
        url = params.get('url', '')
        if not url:
            raise Exception("No URL provided")
        return await self.browser.navigate(url)

    async def _handle_web_scroll(self, params):
        """Scroll in browser"""
        direction = params.get('direction', 'down')
        amount = params.get('amount', 500)
        result = await self.browser.scroll(direction, amount)
        if not result.get('success'):
            raise Exception(result.get('error', 'Scroll failed'))
        return result.get('message', 'Scrolled')

    async def _handle_web_new_tab(self, params):
        """Open new browser tab"""
        url = params.get('url')
        result = await self.browser.new_tab(url)
        if not result.get('success'):
            raise Exception(result.get('error', 'New tab failed'))
        return result.get('message', 'Opened new tab')

    async def _handle_web_close_tab(self, params):
        """Close current browser tab"""
        result = await self.browser.close_tab()
        if not result.get('success'):
            raise Exception(result.get('error', 'Close tab failed'))
        return result.get('message', 'Closed tab')

    async def _handle_web_switch_tab(self, params):
        """Switch browser tabs"""
        index = params.get('index')
        direction = params.get('direction')
        result = await self.browser.switch_tab(index, direction)
        if not result.get('success'):
            raise Exception(result.get('error', 'Switch tab failed'))
        return result.get('message', 'Switched tab')

    async def _handle_web_back(self, params):
        """Browser back"""
        result = await self.browser.go_back()
        if not result.get('success'):
            raise Exception(result.get('error', 'Back failed'))
        return result.get('message', 'Went back')

    async def _handle_web_forward(self, params):
        """Browser forward"""
        result = await self.browser.go_forward()
        if not result.get('success'):
            raise Exception(result.get('error', 'Forward failed'))
        return result.get('message', 'Went forward')

    async def _handle_web_refresh(self, params):
        """Refresh browser page"""
        result = await self.browser.refresh()
        if not result.get('success'):
            raise Exception(result.get('error', 'Refresh failed'))
        return result.get('message', 'Refreshed')

    async def _handle_web_search_google(self, params):
        """Search on Google"""
        query = params.get('query', '')
        if not query:
            raise Exception("No search query provided")
        result = await self.browser.search_google(query)
        return f"Searched Google for: {query}"

    async def _handle_web_search_youtube(self, params):
        """Search on YouTube"""
        query = params.get('query', '')
        if not query:
            raise Exception("No search query provided")
        result = await self.browser.search_youtube(query)
        return f"Searched YouTube for: {query}"

    async def _handle_web_gmail_compose(self, params):
        """Open Gmail compose window"""
        to = params.get('to', '')
        subject = params.get('subject', '')
        body = params.get('body', '')
        result = await self.browser.open_gmail_compose(to, subject, body)
        return f"Opened Gmail compose"

    async def _handle_web_fill_form(self, params):
        """Fill form fields in browser"""
        fields = params.get('fields', {})
        if not fields:
            raise Exception("No fields provided")
        result = await self.browser.fill_form(fields)
        return result

    async def _handle_web_press_key(self, params):
        """Press a key in browser"""
        key = params.get('key', '')
        if not key:
            raise Exception("No key provided")
        result = await self.browser.press_key(key)
        if not result.get('success'):
            raise Exception(result.get('error', 'Key press failed'))
        return result.get('message', f'Pressed {key}')

    async def _handle_web_get_url(self, params):
        """Get current browser URL"""
        return await self.browser.get_current_url()

    async def _handle_web_get_title(self, params):
        """Get current page title"""
        return await self.browser.get_page_title()

    async def _attempt_recovery(self, task, error):
        path = None
        try:
            os.makedirs("temp", exist_ok=True)
            path = os.path.abspath(f"temp/fail_{uuid.uuid4().hex[:8]}.png")
            await self.capture_and_redact(path)
            
            await self.prism_client.emit_thought(f"Analyzing failure: {error}")
            
            plan = await self.prism_client.generate_recovery_plan(task, [error], "Failed", path)
            
            if plan:
                await self.prism_client.emit_thought(f"Executing recovery plan: {len(plan)} tasks")
                for t in plan[:RECOVERY_RETRY_LIMIT]:
                    await self.perform_action(t)
                
                await asyncio.sleep(1.0)
                verify_path = os.path.abspath(f"temp/verify_fix_{uuid.uuid4().hex[:8]}.png")
                await self.capture_and_redact(verify_path)
                
                expected = task.get('description', 'Action completed')
                verification = await self.prism_client.verify_screen_state(verify_path, f"State after: {expected}")
                
                if os.path.exists(verify_path): os.remove(verify_path)
                
                if verification.get('success'):
                    await self.prism_client.emit_thought("Recovery verified successfully.")
                    return {"recovered": True}
                else:
                    await self.prism_client.emit_thought(f"Recovery failed verification: {verification.get('issues')}")
            
            if path and os.path.exists(path): os.remove(path)
        except Exception as e:
            logger.error(f"Recovery failed: {e}")
            if path and os.path.exists(path): os.remove(path)
        return {"recovered": False}

    async def capture_and_redact(self, path):
        self.desktop.get_screenshot(path)
        active_info = self.context_detector.get_active_window_info()
        active_app = active_info.get("app_name", "Desktop")
        return await self.privacy.redact_image(path, active_app=active_app)

    async def close(self):
        await self.browser.close()
