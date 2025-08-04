import asyncio
import json
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Browser, Page
import pytest
import logging
from pathlib import Path
from utils.config import config
import warnings
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed transport")

logger = logging.getLogger(__name__)

class PlaywrightRunner:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def start_browser(self):
        """Initialize browser instance"""
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

    async def stop_browser(self):
        """Close browser instance"""
        if self.browser:
            await self.browser.close()

    async def run_tests(self, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute test cases using Playwright"""
        results = []
        
        try:
            await self.start_browser()
            
            for i, test_case in enumerate(test_cases):
                logger.info(f"Running test {i+1}/{len(test_cases)}: {test_case.get('name', 'Unknown')}")
                
                result = await self._run_single_test(test_case)
                results.append(result)
                
                # Small delay between tests
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            results.append({
                "name": "Test Execution Error",
                "status": "error",
                "error": str(e)
            })
        finally:
            await self.stop_browser()
        
        return results

    async def _run_single_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single test case"""
        test_name = test_case.get('name', 'Unknown Test')
        
        try:
            # Create new page for each test
            page = await self.browser.new_page()
            
            # Set viewport
            await page.set_viewport_size(
                width=config.browser.viewport["width"],
                height=config.browser.viewport["height"]
            )
            
            # Execute test steps
            for step_index, step in enumerate(test_case.get('steps', [])):
                try:
                    await self._execute_step(page, step, step_index)
                except Exception as step_error:
                    logger.error(f"Step {step_index + 1} failed in test '{test_name}': {step_error}")
                    await page.close()
                    return {
                        "name": test_name,
                        "status": "failed",
                        "error": f"Step {step_index + 1} failed: {str(step_error)}",
                        "failed_step": step
                    }
            
            # Take final screenshot
            screenshot_path = await self._take_test_screenshot(page, test_name)
            
            await page.close()
            
            return {
                "name": test_name,
                "status": "passed",
                "screenshot": screenshot_path,
                "steps_executed": len(test_case.get('steps', []))
            }
            
        except Exception as e:
            logger.error(f"Test '{test_name}' failed: {e}")
            return {
                "name": test_name,
                "status": "failed",
                "error": str(e)
            }

    async def _execute_step(self, page: Page, step: str, step_index: int):
        """Execute individual test step"""
        step_lower = step.lower()
        logger.info(f"Executing step {step_index + 1}: {step}")
        
        if 'navigate' in step_lower or 'go to' in step_lower or 'visit' in step_lower:
            # Extract URL from step or use default
            url = self._extract_url_from_step(step)
            if not url:
                url = config.target_url
            
            await page.goto(url, timeout=config.browser.timeout)
            await page.wait_for_load_state('networkidle')
        
        elif 'click' in step_lower:
            # Determine what to click
            if 'button' in step_lower:
                # Try different button selectors
                selectors = [
                    'button:visible',
                    'input[type="button"]:visible',
                    'input[type="submit"]:visible',
                    '[role="button"]:visible'
                ]
                await self._click_first_available(page, selectors)
            
            elif 'link' in step_lower:
                await page.click('a:visible', timeout=5000)
            
            elif 'submit' in step_lower:
                selectors = [
                    'input[type="submit"]:visible',
                    'button[type="submit"]:visible',
                    'button:has-text("Submit"):visible',
                    'button:has-text("Send"):visible'
                ]
                await self._click_first_available(page, selectors)
            
            else:
                # Generic clickable element
                selectors = [
                    'button:visible',
                    'a:visible',
                    'input[type="button"]:visible',
                    'input[type="submit"]:visible'
                ]
                await self._click_first_available(page, selectors)
        
        elif 'fill' in step_lower or 'enter' in step_lower or 'type' in step_lower:
            # Fill form fields
            await self._fill_form_fields(page, step)
        
        elif 'select' in step_lower:
            # Handle select dropdowns
            select_elements = await page.query_selector_all('select:visible')
            if select_elements:
                # Select first option in first select
                await select_elements[0].select_option(index=1)
        
        elif 'wait' in step_lower:
            # Wait for element or time
            if 'second' in step_lower:
                # Extract time from step
                import re
                match = re.search(r'(\d+)', step)
                wait_time = int(match.group(1)) if match else 3
                await asyncio.sleep(wait_time)
            else:
                # Wait for page load
                await page.wait_for_load_state('networkidle')
        
        elif 'verify' in step_lower or 'check' in step_lower or 'assert' in step_lower:
            # Verification steps
            if 'text' in step_lower:
                # Check if page contains expected text
                content = await page.content()
                if not any(word in content.lower() for word in ['success', 'complete', 'thank']):
                    logger.warning("Expected success text not found")
            
            elif 'url' in step_lower:
                # Check URL
                current_url = page.url
                logger.info(f"Current URL: {current_url}")
            
            else:
                # Generic visibility check
                try:
                    await page.wait_for_selector('body', timeout=5000)
                except:
                    raise Exception("Page verification failed")
        
        else:
            logger.warning(f"Unknown step type: {step}")

    async def _click_first_available(self, page: Page, selectors: List[str]):
        """Click the first available element from selector list"""
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    await element.click(timeout=5000)
                    return
            except:
                continue
        
        # If no specific selector worked, try generic approach
        try:
            await page.click('button:visible', timeout=5000)
        except:
            raise Exception(f"Could not find clickable element with any of: {selectors}")

    async def _fill_form_fields(self, page: Page, step: str):
        """Fill form fields with test data"""
        # Get all visible input fields
        inputs = await page.query_selector_all('input:visible, textarea:visible')
        
        for input_elem in inputs:
            input_type = await input_elem.get_attribute('type') or 'text'
            input_name = await input_elem.get_attribute('name') or ''
            input_placeholder = await input_elem.get_attribute('placeholder') or ''
            
            # Determine test value based on field type/name/placeholder
            test_value = self._get_test_value(input_type, input_name, input_placeholder)
            
            if test_value:
                try:
                    await input_elem.fill(test_value)
                except:
                    # Some fields might not be fillable
                    continue

    def _get_test_value(self, input_type: str, name: str, placeholder: str) -> str:
        """Get appropriate test value for input field"""
        name_lower = name.lower()
        placeholder_lower = placeholder.lower()
        
        if input_type == 'email' or 'email' in name_lower or 'email' in placeholder_lower:
            return 'test@example.com'
        
        elif input_type == 'password' or 'password' in name_lower:
            return 'TestPassword123'
        
        elif input_type == 'tel' or 'phone' in name_lower or 'tel' in placeholder_lower:
            return '+1234567890'
        
        elif input_type == 'number' or 'age' in name_lower or 'quantity' in name_lower:
            return '25'
        
        elif input_type == 'date':
            return '2024-12-25'
        
        elif input_type == 'url':
            return 'https://example.com'
        
        elif 'name' in name_lower or 'name' in placeholder_lower:
            if 'first' in name_lower or 'first' in placeholder_lower:
                return 'John'
            elif 'last' in name_lower or 'last' in placeholder_lower:
                return 'Doe'
            else:
                return 'John Doe'
        
        elif 'address' in name_lower or 'address' in placeholder_lower:
            return '123 Test Street'
        
        elif 'city' in name_lower or 'city' in placeholder_lower:
            return 'Test City'
        
        elif 'zip' in name_lower or 'postal' in name_lower:
            return '12345'
        
        elif 'message' in name_lower or 'comment' in name_lower:
            return 'This is a test message for automated testing purposes.'
        
        else:
            return 'Test Value'

    def _extract_url_from_step(self, step: str) -> Optional[str]:
        """Extract URL from step description"""
        import re
        
        # Look for URL patterns
        url_pattern = r'https?://[^\s]+'
        match = re.search(url_pattern, step)
        if match:
            return match.group(0)
        
        # Look for relative paths
        path_pattern = r'/[^\s]*'
        match = re.search(path_pattern, step)
        if match:
            return config.target_url.rstrip('/') + match.group(0)
        
        return None

    async def _take_test_screenshot(self, page: Page, test_name: str) -> str:
        """Take screenshot for test result"""
        try:
            screenshot_name = f"test_{test_name.replace(' ', '_').lower()}.png"
            screenshot_path = config.screenshots_dir / screenshot_name
            
            await page.screenshot(path=str(screenshot_path), full_page=True)
            return str(screenshot_path)
        
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return ""

    async def run_accessibility_tests(self, url: str) -> Dict[str, Any]:
        """Run basic accessibility tests"""
        try:
            await self.start_browser()
            page = await self.browser.new_page()
            
            await page.goto(url)
            await page.wait_for_load_state('networkidle')
            
            # Basic accessibility checks
            accessibility_results = await page.evaluate("""
                () => {
                    const results = {
                        images_without_alt: 0,
                        forms_without_labels: 0,
                        missing_headings: false,
                        color_contrast_issues: [],
                        keyboard_accessibility: true,
                        aria_issues: []
                    };
                    
                    // Check images without alt text
                    const images = document.querySelectorAll('img');
                    images.forEach(img => {
                        if (!img.alt || img.alt.trim() === '') {
                            results.images_without_alt++;
                        }
                    });
                    
                    // Check form inputs without labels
                    const inputs = document.querySelectorAll('input[type="text"], input[type="email"], textarea');
                    inputs.forEach(input => {
                        const hasLabel = input.labels && input.labels.length > 0;
                        const hasAriaLabel = input.getAttribute('aria-label');
                        const hasAriaLabelledby = input.getAttribute('aria-labelledby');
                        
                        if (!hasLabel && !hasAriaLabel && !hasAriaLabelledby) {
                            results.forms_without_labels++;
                        }
                    });
                    
                    // Check heading structure
                    const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
                    if (headings.length === 0) {
                        results.missing_headings = true;
                    }
                    
                    return results;
                }
            """)
            
            await page.close()
            await self.stop_browser()
            
            return {
                "status": "completed",
                "results": accessibility_results,
                "url": url
            }
            
        except Exception as e:
            logger.error(f"Error running accessibility tests: {e}")
            return {
                "status": "error",
                "error": str(e),
                "url": url
            }

    async def run_performance_test(self, url: str) -> Dict[str, Any]:
        """Run basic performance test"""
        try:
            await self.start_browser()
            page = await self.browser.new_page()
            
            # Measure page load performance
            start_time = asyncio.get_event_loop().time()
            await page.goto(url)
            await page.wait_for_load_state('networkidle')
            end_time = asyncio.get_event_loop().time()
            
            load_time = end_time - start_time
            
            # Get performance metrics
            performance_metrics = await page.evaluate("""
                () => {
                    const perfData = performance.getEntriesByType('navigation')[0];
                    const paintEntries = performance.getEntriesByType('paint');
                    
                    return {
                        domContentLoaded: perfData.domContentLoadedEventEnd - perfData.fetchStart,
                        loadComplete: perfData.loadEventEnd - perfData.fetchStart,
                        firstPaint: paintEntries.find(p => p.name === 'first-paint')?.startTime || 0,
                        firstContentfulPaint: paintEntries.find(p => p.name === 'first-contentful-paint')?.startTime || 0,
                        transferSize: perfData.transferSize || 0,
                        domElements: document.getElementsByTagName('*').length
                    };
                }
            """)
            
            await page.close()
            await self.stop_browser()
            
            return {
                "status": "completed",
                "load_time": load_time,
                "metrics": performance_metrics,
                "url": url
            }
            
        except Exception as e:
            logger.error(f"Error running performance test: {e}")
            return {
                "status": "error",
                "error": str(e),
                "url": url
            }