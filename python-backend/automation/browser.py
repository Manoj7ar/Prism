import asyncio
import os
import platform
import subprocess
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("BrowserAutomation")

class BrowserAutomation:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._playwright_available = False
        self._connected = False
        self._chrome_debug_port = 9222
        self._check_playwright()

    def _check_playwright(self):
        try:
            from playwright.async_api import async_playwright
            self._playwright_available = True
        except ImportError:
            logger.warning("Playwright not installed. Run: pip install playwright")
            self._playwright_available = False

    def _get_chrome_path(self) -> Optional[str]:
        if platform.system() == "Windows":
            paths = [
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
            ]
            for p in paths:
                if os.path.exists(p): 
                    return p
        elif platform.system() == "Darwin":
            p = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            if os.path.exists(p): 
                return p
        else:
            for cmd in ['google-chrome', 'chromium-browser', 'chromium']:
                try:
                    result = subprocess.run(['which', cmd], capture_output=True, text=True)
                    if result.returncode == 0:
                        return result.stdout.strip()
                except:
                    pass
        return None

    async def _is_chrome_debug_running(self) -> bool:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f'http://localhost:{self._chrome_debug_port}/json/version', timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    return resp.status == 200
        except:
            return False

    async def _launch_chrome_with_debugging(self) -> bool:
        chrome_path = self._get_chrome_path()
        if not chrome_path:
            logger.error("Chrome not found")
            return False

        try:
            if platform.system() == "Windows":
                user_data = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
                subprocess.Popen([
                    chrome_path,
                    f'--remote-debugging-port={self._chrome_debug_port}',
                    '--remote-allow-origins=*',
                    f'--user-data-dir={user_data}',
                ], creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            elif platform.system() == "Darwin":
                user_data = os.path.expanduser("~/Library/Application Support/Google/Chrome")
                subprocess.Popen([
                    chrome_path,
                    f'--remote-debugging-port={self._chrome_debug_port}',
                    '--remote-allow-origins=*',
                    f'--user-data-dir={user_data}',
                ])
            else:
                subprocess.Popen([
                    chrome_path,
                    f'--remote-debugging-port={self._chrome_debug_port}',
                    '--remote-allow-origins=*',
                ])
            
            await asyncio.sleep(3)
            return await self._is_chrome_debug_running()
        except Exception as e:
            logger.error(f"Failed to launch Chrome: {e}")
            return False

    async def connect(self) -> bool:
        if self._connected and self.browser:
            try:
                if self.browser.is_connected():
                    return True
            except:
                pass
            self._connected = False

        if not self._playwright_available:
            logger.error("Playwright not available")
            return False

        try:
            from playwright.async_api import async_playwright

            if not await self._is_chrome_debug_running():
                logger.info("Chrome debug port not available. Launching Chrome with debugging...")
                if not await self._launch_chrome_with_debugging():
                    logger.error("Failed to launch Chrome with debugging port")
                    return False

            if not self.playwright:
                self.playwright = await async_playwright().start()

            logger.info(f"Connecting to Chrome at localhost:{self._chrome_debug_port}")
            self.browser = await self.playwright.chromium.connect_over_cdp(
                f"http://localhost:{self._chrome_debug_port}"
            )
            
            contexts = self.browser.contexts
            if contexts:
                self.context = contexts[0]
                pages = self.context.pages
                if pages:
                    self.page = pages[0]
                else:
                    self.page = await self.context.new_page()
            else:
                self.context = await self.browser.new_context()
                self.page = await self.context.new_page()

            self._connected = True
            logger.info("Successfully connected to Chrome browser")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Chrome: {e}")
            self._connected = False
            return False

    async def _ensure_connected(self) -> bool:
        if not self._connected:
            return await self.connect()
        return True

    async def get_active_tab(self):
        if not await self._ensure_connected():
            return None
        
        try:
            pages = self.context.pages
            if pages:
                self.page = pages[-1]
                return self.page
        except:
            pass
        return self.page

    async def get_all_tabs(self) -> List[Dict[str, str]]:
        if not await self._ensure_connected():
            return []
        
        tabs = []
        try:
            for i, page in enumerate(self.context.pages):
                tabs.append({
                    "index": i,
                    "title": await page.title(),
                    "url": page.url
                })
        except Exception as e:
            logger.error(f"Failed to get tabs: {e}")
        return tabs

    async def navigate(self, url: str) -> str:
        if not await self._ensure_connected():
            return await self._fallback_navigate(url)
        
        try:
            page = await self.get_active_tab()
            if page:
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                return f"Navigated to {url}"
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
        
        return await self._fallback_navigate(url)

    async def _fallback_navigate(self, url: str) -> str:
        try:
            chrome_path = self._get_chrome_path()
            if chrome_path:
                subprocess.Popen([chrome_path, url])
                return f"Opened {url} in Chrome"
            return f"Chrome not found - cannot navigate to {url}"
        except Exception as e:
            return f"Failed to open {url}: {str(e)}"

    async def click_element(self, selector: str, by: str = "css") -> Dict[str, Any]:
        if not await self._ensure_connected():
            return {"success": False, "error": "Not connected to browser"}
        
        try:
            page = await self.get_active_tab()
            if not page:
                return {"success": False, "error": "No active page"}

            if by == "text":
                await page.get_by_text(selector).click(timeout=10000)
            elif by == "role":
                parts = selector.split(":", 1)
                role = parts[0]
                name = parts[1] if len(parts) > 1 else None
                if name:
                    await page.get_by_role(role, name=name).click(timeout=10000)
                else:
                    await page.get_by_role(role).first.click(timeout=10000)
            elif by == "label":
                await page.get_by_label(selector).click(timeout=10000)
            elif by == "placeholder":
                await page.get_by_placeholder(selector).click(timeout=10000)
            else:
                await page.click(selector, timeout=10000)
            
            return {"success": True, "message": f"Clicked {selector}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click_by_text(self, text: str, exact: bool = False) -> Dict[str, Any]:
        if not await self._ensure_connected():
            return {"success": False, "error": "Not connected to browser"}
        
        try:
            page = await self.get_active_tab()
            if not page:
                return {"success": False, "error": "No active page"}

            await page.get_by_text(text, exact=exact).click(timeout=10000)
            return {"success": True, "message": f"Clicked text: {text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def type_text(self, selector: str, text: str, by: str = "css") -> Dict[str, Any]:
        if not await self._ensure_connected():
            return {"success": False, "error": "Not connected to browser"}
        
        try:
            page = await self.get_active_tab()
            if not page:
                return {"success": False, "error": "No active page"}

            if by == "placeholder":
                await page.get_by_placeholder(selector).fill(text)
            elif by == "label":
                await page.get_by_label(selector).fill(text)
            elif by == "role":
                await page.get_by_role("textbox", name=selector).fill(text)
            else:
                await page.fill(selector, text)
            
            return {"success": True, "message": f"Typed text into {selector}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def type_and_submit(self, selector: str, text: str, by: str = "css") -> Dict[str, Any]:
        result = await self.type_text(selector, text, by)
        if result["success"]:
            try:
                page = await self.get_active_tab()
                await page.keyboard.press("Enter")
                result["message"] += " and pressed Enter"
            except Exception as e:
                result["warning"] = f"Typed but Enter failed: {e}"
        return result

    async def press_key(self, key: str) -> Dict[str, Any]:
        if not await self._ensure_connected():
            return {"success": False, "error": "Not connected to browser"}
        
        try:
            page = await self.get_active_tab()
            if not page:
                return {"success": False, "error": "No active page"}

            await page.keyboard.press(key)
            return {"success": True, "message": f"Pressed {key}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def scroll(self, direction: str = "down", amount: int = 500) -> Dict[str, Any]:
        if not await self._ensure_connected():
            return {"success": False, "error": "Not connected to browser"}
        
        try:
            page = await self.get_active_tab()
            if not page:
                return {"success": False, "error": "No active page"}

            delta = amount if direction == "down" else -amount
            await page.mouse.wheel(0, delta)
            return {"success": True, "message": f"Scrolled {direction} by {amount}px"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def wait_for_element(self, selector: str, timeout: int = 10000) -> bool:
        if not await self._ensure_connected():
            return False
        
        try:
            page = await self.get_active_tab()
            if page:
                await page.wait_for_selector(selector, timeout=timeout)
                return True
        except:
            pass
        return False

    async def get_page_content(self) -> str:
        if not await self._ensure_connected():
            return ""
        
        try:
            page = await self.get_active_tab()
            if page:
                return await page.content()
        except:
            pass
        return ""

    async def get_text_content(self, selector: str = "body") -> str:
        if not await self._ensure_connected():
            return ""
        
        try:
            page = await self.get_active_tab()
            if page:
                element = await page.query_selector(selector)
                if element:
                    return await element.inner_text()
        except:
            pass
        return ""

    async def get_current_url(self) -> str:
        if not await self._ensure_connected():
            return ""
        
        try:
            page = await self.get_active_tab()
            if page:
                return page.url
        except:
            pass
        return ""

    async def get_page_title(self) -> str:
        if not await self._ensure_connected():
            return ""
        
        try:
            page = await self.get_active_tab()
            if page:
                return await page.title()
        except:
            pass
        return ""

    async def screenshot(self, path: str = "browser_screenshot.png") -> str:
        if not await self._ensure_connected():
            return ""
        
        try:
            page = await self.get_active_tab()
            if page:
                await page.screenshot(path=path, full_page=False)
                return path
        except:
            pass
        return ""

    async def new_tab(self, url: str = None) -> Dict[str, Any]:
        if not await self._ensure_connected():
            return {"success": False, "error": "Not connected to browser"}
        
        try:
            self.page = await self.context.new_page()
            if url:
                await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            return {"success": True, "message": f"Opened new tab{' with ' + url if url else ''}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def close_tab(self) -> Dict[str, Any]:
        if not await self._ensure_connected():
            return {"success": False, "error": "Not connected to browser"}
        
        try:
            page = await self.get_active_tab()
            if page:
                await page.close()
                pages = self.context.pages
                if pages:
                    self.page = pages[-1]
                return {"success": True, "message": "Closed current tab"}
            return {"success": False, "error": "No active page"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def switch_tab(self, index: int = None, direction: str = None) -> Dict[str, Any]:
        if not await self._ensure_connected():
            return {"success": False, "error": "Not connected to browser"}
        
        try:
            pages = self.context.pages
            if not pages:
                return {"success": False, "error": "No tabs available"}

            if index is not None:
                if 0 <= index < len(pages):
                    self.page = pages[index]
                    await self.page.bring_to_front()
                    return {"success": True, "message": f"Switched to tab {index}"}
                return {"success": False, "error": f"Invalid tab index: {index}"}

            if direction:
                current_idx = pages.index(self.page) if self.page in pages else 0
                if direction == "next":
                    new_idx = (current_idx + 1) % len(pages)
                else:
                    new_idx = (current_idx - 1) % len(pages)
                self.page = pages[new_idx]
                await self.page.bring_to_front()
                return {"success": True, "message": f"Switched to tab {new_idx}"}

            return {"success": False, "error": "Specify index or direction"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def go_back(self) -> Dict[str, Any]:
        if not await self._ensure_connected():
            return {"success": False, "error": "Not connected to browser"}
        
        try:
            page = await self.get_active_tab()
            if page:
                await page.go_back()
                return {"success": True, "message": "Went back"}
            return {"success": False, "error": "No active page"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def go_forward(self) -> Dict[str, Any]:
        if not await self._ensure_connected():
            return {"success": False, "error": "Not connected to browser"}
        
        try:
            page = await self.get_active_tab()
            if page:
                await page.go_forward()
                return {"success": True, "message": "Went forward"}
            return {"success": False, "error": "No active page"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def refresh(self) -> Dict[str, Any]:
        if not await self._ensure_connected():
            return {"success": False, "error": "Not connected to browser"}
        
        try:
            page = await self.get_active_tab()
            if page:
                await page.reload()
                return {"success": True, "message": "Refreshed page"}
            return {"success": False, "error": "No active page"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def search_google(self, query: str) -> Dict[str, Any]:
        result = await self.navigate(f"https://www.google.com/search?q={query}")
        await asyncio.sleep(2)
        return {"success": True, "query": query, "message": result}

    async def search_youtube(self, query: str) -> Dict[str, Any]:
        result = await self.navigate(f"https://www.youtube.com/results?search_query={query}")
        await asyncio.sleep(2)
        return {"success": True, "query": query, "message": result}

    async def open_gmail_compose(self, to: str = "", subject: str = "", body: str = "") -> Dict[str, Any]:
        url = "https://mail.google.com/mail/?view=cm"
        if to:
            url += f"&to={to}"
        if subject:
            url += f"&su={subject}"
        if body:
            url += f"&body={body}"
        
        await self.navigate(url)
        await asyncio.sleep(2)
        return {"success": True, "message": f"Opened Gmail compose"}

    async def fill_form(self, fields: Dict[str, str]) -> Dict[str, Any]:
        if not await self._ensure_connected():
            return {"success": False, "error": "Not connected to browser"}
        
        results = []
        try:
            page = await self.get_active_tab()
            if not page:
                return {"success": False, "error": "No active page"}

            for selector_or_label, value in fields.items():
                try:
                    try:
                        await page.get_by_label(selector_or_label).fill(value, timeout=3000)
                        results.append({"field": selector_or_label, "success": True, "method": "label"})
                        continue
                    except:
                        pass

                    try:
                        await page.get_by_placeholder(selector_or_label).fill(value, timeout=3000)
                        results.append({"field": selector_or_label, "success": True, "method": "placeholder"})
                        continue
                    except:
                        pass

                    try:
                        await page.fill(selector_or_label, value, timeout=3000)
                        results.append({"field": selector_or_label, "success": True, "method": "selector"})
                        continue
                    except:
                        pass

                    results.append({"field": selector_or_label, "success": False, "error": "Field not found"})
                except Exception as e:
                    results.append({"field": selector_or_label, "success": False, "error": str(e)})

            return {"success": True, "results": results}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def extract_content(self, url: str = None) -> Dict[str, Any]:
        if url:
            await self.navigate(url)
            await asyncio.sleep(2)

        if not await self._ensure_connected():
            return {"success": False, "error": "Not connected to browser"}
        
        try:
            page = await self.get_active_tab()
            if page:
                title = await page.title()
                text = await self.get_text_content()
                return {
                    "success": True,
                    "title": title,
                    "content": text[:5000],
                    "url": page.url
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "No page available"}

    async def evaluate_script(self, script: str) -> Any:
        if not await self._ensure_connected():
            return None
        
        try:
            page = await self.get_active_tab()
            if page:
                return await page.evaluate(script)
        except:
            pass
        return None

    async def close(self):
        try:
            if self.browser:
                await self.browser.close()
        except:
            pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except:
            pass
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        self._connected = False

    async def disconnect(self):
        self._connected = False
        self.page = None
        self.context = None
        if self.browser:
            try:
                await self.browser.close()
            except:
                pass
        self.browser = None
