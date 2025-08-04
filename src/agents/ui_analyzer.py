import asyncio
from playwright.async_api import async_playwright, Page, Browser , TimeoutError
from typing import Dict, List, Any, Optional
import logging
from pathlib import Path
from utils.config import config
from utils.cv_utils import ComputerVisionUtils
import warnings
warnings.filterwarnings("ignore", category=ResourceWarning)


logger = logging.getLogger(__name__)

class UIAnalyzer:
    def __init__(self):
        self.cv_utils = ComputerVisionUtils()
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def start_browser(self):
        """Start browser instance"""
        playwright = await async_playwright().start()
        
        if config.browser.type == "chromium":
            self.browser = await playwright.chromium.launch(
                headless=config.browser.headless
            )
        elif config.browser.type == "firefox":
            self.browser = await playwright.firefox.launch(
                headless=config.browser.headless
            )
        else:
            self.browser = await playwright.webkit.launch(
                headless=config.browser.headless
            )
        
        self.page = await self.browser.new_page()
        await self.page.set_viewport_size({
            "width": config.browser.viewport["width"],
            "height": config.browser.viewport["height"]
        })


    async def stop_browser(self):
        """Stop browser instance"""
        if self.browser:
            await self.browser.close()

    async def analyze_page(self, url: str) -> Dict[str, Any]:
        """Analyze a web page and extract UI information"""
        try:
            if not self.page:
                await self.start_browser()
            
            for attempt in range(3):
                try:
                    await self.page.goto(
                        url,
                        timeout=config.browser.timeout,
                        wait_until="domcontentloaded"
                    )
                    break
                except TimeoutError:
                    print(f"⚠️ Timeout trying to load {url} (attempt {attempt+1}/3), retrying...")
                    if attempt == 2:
                        raise
            await self.page.wait_for_load_state('networkidle')
            
            # Take screenshot
            screenshot_path = await self._take_screenshot(url)
            
            # Extract page information
            page_info = await self._extract_page_info()
            
            # Detect UI elements using computer vision
            cv_elements = self.cv_utils.detect_ui_elements(screenshot_path)
            
            # Extract DOM elements
            dom_elements = await self._extract_dom_elements()
            
            # Combine and analyze
            analysis = {
                "url": url,
                "title": await self.page.title(),
                "screenshot": screenshot_path,
                "page_info": page_info,
                "cv_elements": cv_elements,
                "dom_elements": dom_elements,
                "forms": await self._analyze_forms(),
                "navigation": await self._analyze_navigation(),
                "accessibility": await self._analyze_accessibility()
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing page {url}: {e}")
            return {"error": str(e)}

    async def _take_screenshot(self, url: str) -> str:
        """Take screenshot of current page"""
        try:
            # Create filename from URL
            filename = url.replace("https://", "").replace("http://", "").replace("/", "_")
            if not filename.endswith(".png"):
                filename += ".png"
            
            screenshot_path = config.screenshots_dir / filename
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            
            return str(screenshot_path)
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return ""

    async def _extract_page_info(self) -> Dict[str, Any]:
        """Extract basic page information"""
        try:
            return await self.page.evaluate("""
                () => {
                    return {
                        url: window.location.href,
                        title: document.title,
                        meta_description: document.querySelector('meta[name="description"]')?.content || '',
                        viewport: {
                            width: window.innerWidth,
                            height: window.innerHeight
                        },
                        scroll_height: document.body.scrollHeight,
                        has_jquery: typeof window.jQuery !== 'undefined'
                    };
                }
            """)
        except Exception as e:
            logger.error(f"Error extracting page info: {e}")
            return {}

    async def _extract_dom_elements(self) -> Dict[str, List[Dict[str, Any]]]:
        """Extract DOM elements for testing"""
        try:
            return await self.page.evaluate("""
                () => {
                    const elements = {
                        buttons: [],
                        inputs: [],
                        links: [],
                        forms: [],
                        images: [],
                        headings: []
                    };
                    
                    // Extract buttons
                    document.querySelectorAll('button, input[type="button"], input[type="submit"]').forEach(el => {
                        const rect = el.getBoundingClientRect();
                        elements.buttons.push({
                            tag: el.tagName.toLowerCase(),
                            text: el.textContent?.trim() || el.value || '',
                            id: el.id || '',
                            class: el.className || '',
                            bounds: {
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height
                            },
                            visible: rect.width > 0 && rect.height > 0
                        });
                    });
                    
                    // Extract inputs
                    document.querySelectorAll('input, textarea, select').forEach(el => {
                        const rect = el.getBoundingClientRect();
                        elements.inputs.push({
                            tag: el.tagName.toLowerCase(),
                            type: el.type || '',
                            name: el.name || '',
                            id: el.id || '',
                            placeholder: el.placeholder || '',
                            required: el.required || false,
                            bounds: {
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height
                            },
                            visible: rect.width > 0 && rect.height > 0
                        });
                    });
                    
                    // Extract links
                    document.querySelectorAll('a[href]').forEach(el => {
                        const rect = el.getBoundingClientRect();
                        elements.links.push({
                            text: el.textContent?.trim() || '',
                            href: el.href || '',
                            id: el.id || '',
                            bounds: {
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height
                            },
                            visible: rect.width > 0 && rect.height > 0
                        });
                    });
                    
                    // Extract forms
                    document.querySelectorAll('form').forEach(el => {
                        const rect = el.getBoundingClientRect();
                        elements.forms.push({
                            action: el.action || '',
                            method: el.method || 'get',
                            id: el.id || '',
                            inputs_count: el.querySelectorAll('input, textarea, select').length,
                            bounds: {
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height
                            }
                        });
                    });
                    
                    // Extract images
                    document.querySelectorAll('img').forEach(el => {
                        const rect = el.getBoundingClientRect();
                        elements.images.push({
                            src: el.src || '',
                            alt: el.alt || '',
                            id: el.id || '',
                            bounds: {
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height
                            },
                            visible: rect.width > 0 && rect.height > 0
                        });
                    });
                    
                    // Extract headings
                    document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(el => {
                        const rect = el.getBoundingClientRect();
                        elements.headings.push({
                            tag: el.tagName.toLowerCase(),
                            text: el.textContent?.trim() || '',
                            id: el.id || '',
                            bounds: {
                                x: rect.x,
                                y: rect.y,
                                width: rect.width,
                                height: rect.height
                            },
                            visible: rect.width > 0 && rect.height > 0
                        });
                    });
                    
                    return elements;
                }
            """)
        except Exception as e:
            logger.error(f"Error extracting DOM elements: {e}")
            return {}

    async def _analyze_forms(self) -> List[Dict[str, Any]]:
        """Analyze forms on the page"""
        try:
            forms = await self.page.query_selector_all('form')
            form_analysis = []
            
            for form in forms:
                form_data = await form.evaluate("""
                    (form) => {
                        const inputs = Array.from(form.querySelectorAll('input, textarea, select')).map(input => ({
                            name: input.name || '',
                            type: input.type || '',
                            required: input.required || false,
                            placeholder: input.placeholder || ''
                        }));
                        
                        return {
                            action: form.action || '',
                            method: form.method || 'get',
                            inputs: inputs,
                            has_validation: form.querySelector('[required]') !== null
                        };
                    }
                """)
                
                form_analysis.append(form_data)
            
            return form_analysis
        except Exception as e:
            logger.error(f"Error analyzing forms: {e}")
            return []

    async def _analyze_navigation(self) -> Dict[str, Any]:
        """Analyze navigation elements"""
        try:
            return await self.page.evaluate("""
                () => {
                    const nav_elements = document.querySelectorAll('nav, .nav, .navbar, .navigation');
                    const menus = document.querySelectorAll('ul.menu, .dropdown, .menu');
                    const breadcrumbs = document.querySelectorAll('.breadcrumb, .breadcrumbs');
                    
                    return {
                        nav_count: nav_elements.length,
                        menu_count: menus.length,
                        breadcrumb_count: breadcrumbs.length,
                        has_mobile_menu: document.querySelector('.mobile-menu, .hamburger') !== null
                    };
                }
            """)
        except Exception as e:
            logger.error(f"Error analyzing navigation: {e}")
            return {}

    async def _analyze_accessibility(self) -> Dict[str, Any]:
        """Basic accessibility analysis"""
        try:
            return await self.page.evaluate("""
                () => {
                    const issues = [];
                    
                    // Check for missing alt attributes
                    const images_without_alt = document.querySelectorAll('img:not([alt])').length;
                    if (images_without_alt > 0) {
                        issues.push(`${images_without_alt} images missing alt text`);
                    }
                    
                    // Check for missing form labels
                    const inputs_without_labels = Array.from(document.querySelectorAll('input[type="text"], input[type="email"], textarea')).filter(input => {
                        return !input.getAttribute('aria-label') && 
                               !document.querySelector(`label[for="${input.id}"]`) &&
                               !input.closest('label');
                    }).length;
                    
                    if (inputs_without_labels > 0) {
                        issues.push(`${inputs_without_labels} form inputs missing labels`);
                    }
                    
                    // Check for heading structure
                    const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'));
                    const heading_levels = headings.map(h => parseInt(h.tagName.charAt(1)));
                    
                    return {
                        issues: issues,
                        images_total: document.querySelectorAll('img').length,
                        images_with_alt: document.querySelectorAll('img[alt]').length,
                        heading_structure: heading_levels,
                        has_skip_link: document.querySelector('a[href="#main"], a[href="#content"]') !== null
                    };
                }
            """)
        except Exception as e:
            logger.error(f"Error analyzing accessibility: {e}")
            return {}

    async def capture_element_screenshot(self, selector: str) -> str:
        """Capture screenshot of specific element"""
        try:
            element = await self.page.query_selector(selector)
            if element:
                screenshot_path = config.screenshots_dir / f"element_{selector.replace(' ', '_')}.png"
                await element.screenshot(path=str(screenshot_path))
                return str(screenshot_path)
        except Exception as e:
            logger.error(f"Error capturing element screenshot: {e}")
        return ""

    async def get_page_performance(self) -> Dict[str, Any]:
        """Get page performance metrics"""
        try:
            return await self.page.evaluate("""
                () => {
                    const perfData = performance.getEntriesByType('navigation')[0];
                    return {
                        load_time: perfData.loadEventEnd - perfData.fetchStart,
                        dom_content_loaded: perfData.domContentLoadedEventEnd - perfData.fetchStart,
                        first_paint: performance.getEntriesByType('paint').find(p => p.name === 'first-paint')?.startTime || 0,
                        first_contentful_paint: performance.getEntriesByType('paint').find(p => p.name === 'first-contentful-paint')?.startTime || 0
                    };
                }
            """)
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}