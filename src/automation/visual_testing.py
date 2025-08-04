import asyncio
import cv2
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
from playwright.async_api import async_playwright, Browser, Page, Playwright
from utils.config import config
from utils.cv_utils import ComputerVisionUtils
import warnings
warnings.filterwarnings("ignore", category=ResourceWarning)

logger = logging.getLogger(__name__)

class VisualTester:
    def __init__(self):
        self.cv_utils = ComputerVisionUtils()
        self.browser: Optional[Browser] = None
        self.playwright: Optional[Playwright] = None  # Add playwright instance
        self.baseline_dir = config.screenshots_dir / "baselines"
        self.current_dir = config.screenshots_dir / "current"
        self.diff_dir = config.screenshots_dir / "diffs"
        
        # Create directories
        for dir_path in [self.baseline_dir, self.current_dir, self.diff_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    async def start_browser(self):
        """Initialize browser for visual testing"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--disable-web-security', '--disable-dev-shm-usage', '--no-sandbox']
        )

    async def stop_browser(self):
        """Stop browser and playwright"""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    async def run_visual_tests(self, visual_tests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run visual regression tests"""
        results = []
        
        try:
            await self.start_browser()
            
            for test in visual_tests:
                logger.info(f"Running visual test: {test.get('name', 'Unknown')}")
                result = await self._run_single_visual_test(test)
                results.append(result)
                
        except Exception as e:
            logger.error(f"Error running visual tests: {e}")
            results.append({
                "name": "Visual Testing Error",
                "status": "error",
                "error": str(e)
            })
        finally:
            await self.stop_browser()
        
        return results

    async def _run_single_visual_test(self, test: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single visual regression test"""
        test_name = test.get('name', 'unknown_test')
        url = test.get('url', config.target_url)
        test_type = test.get('type', 'full_page')
        
        page = None
        try:
            page = await self.browser.new_page()
            
            # Set consistent viewport - FIXED: Use correct method signature
            await page.set_viewport_size({
                "width": config.browser.viewport["width"],
                "height": config.browser.viewport["height"]
            })

            # Set timeouts - FIXED: Add proper timeout handling
            page.set_default_timeout(60000)  # 60 seconds
            page.set_default_navigation_timeout(60000)
            
            # Navigate to page with retry logic
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_load_state('networkidle', timeout=30000)
            except Exception as e:
                logger.warning(f"First attempt failed, retrying with longer timeout: {e}")
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                await page.wait_for_load_state('networkidle', timeout=60000)
            
            # Take current screenshot
            current_screenshot = await self._take_screenshot(page, test_name, test_type)
            
            # Compare with baseline
            comparison_result = await self._compare_with_baseline(test_name, current_screenshot)
            
            return {
                "name": test_name,
                "url": url,
                "status": "passed" if comparison_result.get("passed", False) else "failed",
                "similarity": comparison_result.get("similarity", 0),
                "current_screenshot": current_screenshot,
                "baseline_screenshot": comparison_result.get("baseline_path", ""),
                "diff_screenshot": comparison_result.get("diff_path", ""),
                "differences_found": comparison_result.get("differences_found", False)
            }
            
        except Exception as e:
            logger.error(f"Visual test '{test_name}' failed: {e}")
            return {
                "name": test_name,
                "status": "error",
                "error": str(e)
            }
        finally:
            if page:
                await page.close()

    async def _take_screenshot(self, page: Page, test_name: str, test_type: str) -> str:
        """Take screenshot based on test type"""
        screenshot_name = f"{test_name.replace(' ', '_').lower()}.png"
        screenshot_path = self.current_dir / screenshot_name
        
        # Wait a bit for any animations to complete
        await page.wait_for_timeout(1000)
        
        if test_type == 'full_page':
            await page.screenshot(path=str(screenshot_path), full_page=True)
        elif test_type == 'viewport':
            await page.screenshot(path=str(screenshot_path), full_page=False)
        elif test_type == 'element':
            # For element screenshots, we'd need a selector
            # For now, default to viewport
            await page.screenshot(path=str(screenshot_path), full_page=False)
        
        return str(screenshot_path)

    async def _compare_with_baseline(self, test_name: str, current_path: str) -> Dict[str, Any]:
        """Compare current screenshot with baseline"""
        baseline_name = f"{test_name.replace(' ', '_').lower()}.png"
        baseline_path = self.baseline_dir / baseline_name
        
        if not baseline_path.exists():
            # First run - create baseline
            import shutil
            shutil.copy(current_path, baseline_path)
            
            return {
                "passed": True,
                "similarity": 1.0,
                "baseline_path": str(baseline_path),
                "first_run": True,
                "message": "Baseline screenshot created"
            }
        
        # Compare images
        comparison = self.cv_utils.compare_screenshots(str(baseline_path), current_path)
        
        if "error" in comparison:
            return {
                "passed": False,
                "error": comparison["error"],
                "baseline_path": str(baseline_path)
            }
        
        # Create diff image if differences found
        diff_path = ""
        if comparison.get("differences_found", False):
            diff_path = await self._create_diff_visualization(
                str(baseline_path), current_path, test_name
            )
        
        return {
            "passed": comparison.get("passed", False),
            "similarity": comparison.get("similarity", 0),
            "baseline_path": str(baseline_path),
            "diff_path": diff_path,
            "differences_found": comparison.get("differences_found", False)
        }

    async def _create_diff_visualization(self, baseline_path: str, current_path: str, test_name: str) -> str:
        """Create visual diff image"""
        try:
            diff_name = f"{test_name.replace(' ', '_').lower()}_diff.png"
            diff_path = self.diff_dir / diff_name
            
            # Load images
            baseline_img = cv2.imread(baseline_path)
            current_img = cv2.imread(current_path)
            
            if baseline_img is None or current_img is None:
                return ""
            
            # Ensure same size
            if baseline_img.shape != current_img.shape:
                current_img = cv2.resize(current_img, (baseline_img.shape[1], baseline_img.shape[0]))
            
            # Create side-by-side comparison
            comparison_img = self._create_side_by_side_comparison(
                baseline_img, current_img, test_name
            )
            
            cv2.imwrite(str(diff_path), comparison_img)
            return str(diff_path)
            
        except Exception as e:
            logger.error(f"Error creating diff visualization: {e}")
            return ""

    def _create_side_by_side_comparison(self, baseline: np.ndarray, current: np.ndarray, test_name: str) -> np.ndarray:
        """Create side-by-side comparison image"""
        height, width = baseline.shape[:2]
        
        # Create combined image
        combined = np.zeros((height, width * 3, 3), dtype=np.uint8)
        
        # Place baseline on left
        combined[:, :width] = baseline
        
        # Place current in middle
        combined[:, width:width*2] = current
        
        # Create diff on right
        diff = cv2.absdiff(baseline, current)
        
        # Enhance differences
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
        
        # Color differences in red
        diff_colored = current.copy()
        diff_colored[mask > 0] = [0, 0, 255]
        
        combined[:, width*2:] = diff_colored
        
        # Add labels
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(combined, 'BASELINE', (10, 30), font, 1, (255, 255, 255), 2)
        cv2.putText(combined, 'CURRENT', (width + 10, 30), font, 1, (255, 255, 255), 2)
        cv2.putText(combined, 'DIFF', (width * 2 + 10, 30), font, 1, (255, 255, 255), 2)
        
        return combined

    async def create_baseline_suite(self, urls: List[str]) -> Dict[str, Any]:
        """Create baseline screenshots for a list of URLs"""
        results = {
            "created": [],
            "failed": [],
            "total": len(urls)
        }
        
        try:
            await self.start_browser()
            
            for i, url in enumerate(urls):
                test_name = f"baseline_{i+1}"
                logger.info(f"Creating baseline for {url}")
                
                page = None
                try:
                    page = await self.browser.new_page()
                    
                    # FIXED: Use correct method signature for viewport
                    await page.set_viewport_size({
                        "width": config.browser.viewport["width"],
                        "height": config.browser.viewport["height"]
                    })
                    
                    # Set timeouts
                    page.set_default_timeout(60000)
                    page.set_default_navigation_timeout(60000)
                    
                    try:
                        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                        await page.wait_for_load_state('networkidle', timeout=30000)
                    except Exception as e:
                        logger.warning(f"Retrying with longer timeout for {url}: {e}")
                        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                        await page.wait_for_load_state('networkidle', timeout=60000)
                    
                    # Wait a bit for animations
                    await page.wait_for_timeout(1000)
                    
                    # Take screenshot
                    baseline_name = f"{test_name}.png"
                    baseline_path = self.baseline_dir / baseline_name
                    
                    await page.screenshot(path=str(baseline_path), full_page=True)
                    
                    results["created"].append({
                        "url": url,
                        "baseline_path": str(baseline_path),
                        "test_name": test_name
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to create baseline for {url}: {e}")
                    results["failed"].append({
                        "url": url,
                        "error": str(e)
                    })
                finally:
                    if page:
                        await page.close()
                    
        except Exception as e:
            logger.error(f"Error creating baseline suite: {e}")
        finally:
            await self.stop_browser()
        
        return results

    async def run_cross_browser_visual_test(self, test: Dict[str, Any]) -> Dict[str, Any]:
        """Run visual test across multiple browsers"""
        browsers = ['chromium', 'firefox', 'webkit']
        results = {}
        
        playwright = None
        try:
            playwright = await async_playwright().start()
            
            for browser_name in browsers:
                browser = None
                page = None
                try:
                    logger.info(f"Running visual test in {browser_name}")
                    
                    if browser_name == 'chromium':
                        browser = await playwright.chromium.launch(
                            headless=True,
                            args=['--disable-web-security', '--disable-dev-shm-usage', '--no-sandbox']
                        )
                    elif browser_name == 'firefox':
                        browser = await playwright.firefox.launch(headless=True)
                    else:
                        browser = await playwright.webkit.launch(headless=True)
                    
                    page = await browser.new_page()
                    
                    # FIXED: Use correct method signature
                    await page.set_viewport_size({
                        "width": config.browser.viewport["width"],
                        "height": config.browser.viewport["height"]
                    })
                    
                    # Set timeouts
                    page.set_default_timeout(60000)
                    page.set_default_navigation_timeout(60000)
                    
                    try:
                        await page.goto(test.get('url', config.target_url), wait_until='domcontentloaded', timeout=30000)
                        await page.wait_for_load_state('networkidle', timeout=30000)
                    except Exception as e:
                        logger.warning(f"Retrying {browser_name} with longer timeout: {e}")
                        await page.goto(test.get('url', config.target_url), wait_until='domcontentloaded', timeout=60000)
                        await page.wait_for_load_state('networkidle', timeout=60000)
                    
                    # Wait for animations
                    await page.wait_for_timeout(1000)
                    
                    # Take screenshot
                    screenshot_name = f"{test.get('name', 'test')}_{browser_name}.png"
                    screenshot_path = self.current_dir / screenshot_name
                    await page.screenshot(path=str(screenshot_path), full_page=True)
                    
                    results[browser_name] = {
                        "status": "success",
                        "screenshot": str(screenshot_path)
                    }
                    
                except Exception as e:
                    logger.error(f"Error testing in {browser_name}: {e}")
                    results[browser_name] = {
                        "status": "error",
                        "error": str(e)
                    }
                finally:
                    if page:
                        await page.close()
                    if browser:
                        await browser.close()
        
            # Compare screenshots between browsers
            if len([r for r in results.values() if r.get('status') == 'success']) > 1:
                cross_browser_comparison = await self._compare_cross_browser_screenshots(results, test.get('name', 'test'))
                results['cross_browser_comparison'] = cross_browser_comparison
        
        finally:
            if playwright:
                await playwright.stop()
        
        return results

    async def _compare_cross_browser_screenshots(self, browser_results: Dict[str, Any], test_name: str) -> Dict[str, Any]:
        """Compare screenshots across browsers"""
        comparisons = {}
        
        browser_screenshots = {
            browser: result.get('screenshot', '')
            for browser, result in browser_results.items()
            if result.get('status') == 'success' and 'screenshot' in result
        }
        
        browsers = list(browser_screenshots.keys())
        
        for i in range(len(browsers)):
            for j in range(i + 1, len(browsers)):
                browser1, browser2 = browsers[i], browsers[j]
                
                comparison_key = f"{browser1}_vs_{browser2}"
                
                try:
                    comparison = self.cv_utils.compare_screenshots(
                        browser_screenshots[browser1],
                        browser_screenshots[browser2]
                    )
                    
                    comparisons[comparison_key] = {
                        "similarity": comparison.get("similarity", 0),
                        "passed": comparison.get("passed", False),
                        "differences_found": comparison.get("differences_found", False)
                    }
                    
                    # Create diff if needed
                    if comparison.get("differences_found", False):
                        diff_name = f"{test_name}_{comparison_key}_diff.png"
                        diff_path = self.diff_dir / diff_name
                        
                        # Create cross-browser diff
                        baseline_img = cv2.imread(browser_screenshots[browser1])
                        current_img = cv2.imread(browser_screenshots[browser2])
                        
                        if baseline_img is not None and current_img is not None:
                            if baseline_img.shape != current_img.shape:
                                current_img = cv2.resize(current_img, (baseline_img.shape[1], baseline_img.shape[0]))
                            
                            diff_img = self._create_side_by_side_comparison(
                                baseline_img, current_img, f"{browser1} vs {browser2}"
                            )
                            cv2.imwrite(str(diff_path), diff_img)
                            comparisons[comparison_key]["diff_image"] = str(diff_path)
                
                except Exception as e:
                    logger.error(f"Error comparing {browser1} vs {browser2}: {e}")
                    comparisons[comparison_key] = {
                        "error": str(e)
                    }
        
        return comparisons

    def generate_visual_test_report(self, results: List[Dict[str, Any]]) -> str:
        """Generate HTML report for visual tests"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Visual Regression Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .test-result { border: 1px solid #ddd; margin: 20px 0; padding: 15px; }
        .passed { border-left: 5px solid #4CAF50; }
        .failed { border-left: 5px solid #f44336; }
        .error { border-left: 5px solid #ff9800; }
        .screenshot { max-width: 300px; margin: 10px; }
        .comparison { display: flex; gap: 10px; }
        .similarity { font-weight: bold; }
        .high-similarity { color: #4CAF50; }
        .low-similarity { color: #f44336; }
    </style>
</head>
<body>
    <h1>Visual Regression Test Report</h1>
    <p>Generated on: {{ timestamp }}</p>
    
    <div class="summary">
        <h2>Summary</h2>
        <p>Total Tests: {{ total_tests }}</p>
        <p>Passed: {{ passed_tests }}</p>
        <p>Failed: {{ failed_tests }}</p>
        <p>Errors: {{ error_tests }}</p>
    </div>
    
    {% for result in results %}
    <div class="test-result {{ result.status }}">
        <h3>{{ result.name }}</h3>
        <p><strong>URL:</strong> {{ result.url }}</p>
        <p><strong>Status:</strong> {{ result.status }}</p>
        
        {% if result.similarity %}
        <p><strong>Similarity:</strong> 
            <span class="similarity {{ 'high-similarity' if result.similarity > 0.95 else 'low-similarity' }}">
                {{ "%.2f"|format(result.similarity * 100) }}%
            </span>
        </p>
        {% endif %}
        
        {% if result.current_screenshot %}
        <div class="comparison">
            {% if result.baseline_screenshot %}
            <div>
                <h4>Baseline</h4>
                <img src="{{ result.baseline_screenshot }}" class="screenshot" alt="Baseline">
            </div>
            {% endif %}
            
            <div>
                <h4>Current</h4>
                <img src="{{ result.current_screenshot }}" class="screenshot" alt="Current">
            </div>
            
            {% if result.diff_screenshot %}
            <div>
                <h4>Differences</h4>
                <img src="{{ result.diff_screenshot }}" class="screenshot" alt="Diff">
            </div>
            {% endif %}
        </div>
        {% endif %}
        
        {% if result.error %}
        <p><strong>Error:</strong> {{ result.error }}</p>
        {% endif %}
    </div>
    {% endfor %}
</body>
</html>
"""
        
        from jinja2 import Template
        from datetime import datetime
        
        template = Template(html_template)
        
        # Calculate summary
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.get('status') == 'passed')
        failed_tests = sum(1 for r in results if r.get('status') == 'failed')
        error_tests = sum(1 for r in results if r.get('status') == 'error')
        
        html_content = template.render(
            results=results,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            error_tests=error_tests
        )
        
        # Save report
        report_path = config.reports_dir / 'visual_test_report.html'
        with open(report_path, 'w') as f:
            f.write(html_content)
        
        return str(report_path)