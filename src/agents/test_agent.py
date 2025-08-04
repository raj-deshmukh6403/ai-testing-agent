import asyncio
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging
from agents.ui_analyzer import UIAnalyzer
from utils.llm_client import LLMClient
from utils.config import config
from generators.test_generator import TestGenerator
from generators.api_test_generator import APITestGenerator
from generators.load_test_generator import LoadTestGenerator
from automation.playwright_runner import PlaywrightRunner
from automation.visual_testing import VisualTester
import warnings
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed transport")

logger = logging.getLogger(__name__)

class TestAgent:
    def __init__(self):
        self.ui_analyzer = UIAnalyzer()
        self.llm_client = LLMClient()
        self.test_generator = TestGenerator()
        self.api_test_generator = APITestGenerator()
        self.load_test_generator = LoadTestGenerator()
        self.playwright_runner = PlaywrightRunner()
        self.visual_tester = VisualTester()
        
        self.session_id = None
        self.current_analysis = None

    async def analyze_application(self, url: str) -> Dict[str, Any]:
        """Comprehensive application analysis"""
        logger.info(f"Starting analysis of {url}")
        
        try:
            # Initialize browser
            await self.ui_analyzer.start_browser()
            
            # Analyze main page
            main_analysis = await self.ui_analyzer.analyze_page(url)
            
            # Discover additional pages
            additional_pages = await self._discover_pages(url)
            
            # Analyze discovered pages
            page_analyses = [main_analysis]
            for page_url in additional_pages[:5]:  # Limit to 5 additional pages
                try:
                    analysis = await self.ui_analyzer.analyze_page(page_url)
                    page_analyses.append(analysis)
                except Exception as e:
                    logger.warning(f"Failed to analyze {page_url}: {e}")
            
            # Combine analyses
            combined_analysis = self._combine_page_analyses(page_analyses)
            
            # Store analysis for later use
            self.current_analysis = combined_analysis
            
            return combined_analysis
            
        except Exception as e:
            logger.error(f"Error during application analysis: {e}")
            return {"error": str(e)}
        finally:
            await self.ui_analyzer.stop_browser()

    async def generate_test_suite(self, analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate comprehensive test suite based on analysis"""
        if analysis is None:
            analysis = self.current_analysis
        
        if not analysis:
            raise ValueError("No analysis available. Please run analyze_application first.")
        
        logger.info("Generating test suite")
        
        # Generate different types of tests
        test_suite = {
            "functional_tests": [],
            "api_tests": [],
            "load_tests": [],
            "visual_tests": [],
            "accessibility_tests": []
        }
        
        try:
            # Generate functional tests using LLM
            for page in analysis.get("pages", []):
                functional_tests = await self.llm_client.generate_test_cases(page)
                test_suite["functional_tests"].extend(functional_tests)
            
            # Generate API tests if endpoints discovered
            api_endpoints = self._extract_api_endpoints(analysis)
            if api_endpoints:
                api_tests = await self.llm_client.generate_api_tests(api_endpoints)
                test_suite["api_tests"] = api_tests
            
            # Generate load tests
            user_flows = self._extract_user_flows(analysis)
            if user_flows:
                load_test = await self.llm_client.generate_load_tests(user_flows)
                test_suite["load_tests"] = load_test
            
            # Generate visual regression tests
            visual_tests = self._generate_visual_tests(analysis)
            test_suite["visual_tests"] = visual_tests
            
            # Generate accessibility tests
            accessibility_tests = self._generate_accessibility_tests(analysis)
            test_suite["accessibility_tests"] = accessibility_tests
            
            # Save test suite
            await self._save_test_suite(test_suite)
            
            return test_suite
            
        except Exception as e:
            logger.error(f"Error generating test suite: {e}")
            return {"error": str(e)}

    async def execute_tests(self, test_suite: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute generated test suite"""
        if test_suite is None:
            # Load test suite from file
            test_suite = await self._load_test_suite()
        
        if not test_suite:
            raise ValueError("No test suite available")
        
        logger.info("Executing test suite")
        
        results = {
            "functional_results": [],
            "api_results": [],
            "load_results": [],
            "visual_results": [],
            "accessibility_results": [],
            "summary": {}
        }
        
        try:
            # Execute functional tests
            if test_suite.get("functional_tests"):
                results["functional_results"] = await self.playwright_runner.run_tests(
                    test_suite["functional_tests"]
                )
            
            # Execute API tests
            if test_suite.get("api_tests"):
                results["api_results"] = await self.api_test_generator.execute_tests(
                    test_suite["api_tests"]
                )
            
            # Execute visual tests
            if test_suite.get("visual_tests"):
                results["visual_results"] = await self.visual_tester.run_visual_tests(
                    test_suite["visual_tests"]
                )
            
            # Generate summary
            results["summary"] = self._generate_test_summary(results)
            
            # Save results
            await self._save_test_results(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error executing tests: {e}")
            return {"error": str(e)}

    async def continuous_testing(self, url: str, interval: int = 3600) -> None:
        """Run continuous testing at specified intervals"""
        logger.info(f"Starting continuous testing for {url} every {interval} seconds")
        
        baseline_analysis = None
        
        while True:
            try:
                # Analyze application
                current_analysis = await self.analyze_application(url)
                
                if baseline_analysis is None:
                    baseline_analysis = current_analysis
                    logger.info("Baseline analysis established")
                else:
                    # Compare with baseline
                    changes = self._detect_changes(baseline_analysis, current_analysis)
                    if changes:
                        logger.info(f"Changes detected: {changes}")
                        
                        # Generate and execute tests for changes
                        test_suite = await self.generate_test_suite(current_analysis)
                        results = await self.execute_tests(test_suite)
                        
                        # Update baseline if tests pass
                        if self._tests_passed(results):
                            baseline_analysis = current_analysis
                            logger.info("Baseline updated after successful tests")
                
                # Wait for next iteration
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in continuous testing: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def _discover_pages(self, base_url: str) -> List[str]:
        """Discover additional pages to test"""
        try:
            page = self.ui_analyzer.page
            links = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    return links.map(link => link.href).filter(href => 
                        href.startsWith(window.location.origin) && 
                        !href.includes('#') && 
                        !href.includes('mailto:') &&
                        !href.includes('tel:')
                    );
                }
            """)
            
            # Remove duplicates and limit
            unique_links = list(set(links))[:10]
            return unique_links
            
        except Exception as e:
            logger.error(f"Error discovering pages: {e}")
            return []

    def _combine_page_analyses(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine multiple page analyses into one comprehensive analysis"""
        combined = {
            "pages": analyses,
            "total_pages": len(analyses),
            "forms": [],
            "api_endpoints": [],
            "user_flows": [],
            "common_elements": {},
            "accessibility_issues": []
        }
        
        # Aggregate data from all pages
        for analysis in analyses:
            if "forms" in analysis:
                combined["forms"].extend(analysis["forms"])
            
            # Extract potential API endpoints from forms and AJAX calls
            if "page_info" in analysis:
                # This would need enhancement to detect actual API calls
                pass
        
        return combined

    def _extract_api_endpoints(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract potential API endpoints from analysis"""
        endpoints = []
        
        # Extract from forms
        for form in analysis.get("forms", []):
            if form.get("action"):
                endpoints.append({
                    "url": form["action"],
                    "method": form.get("method", "POST").upper(),
                    "type": "form_submission"
                })
        
        # TODO: Add detection of AJAX calls, fetch requests, etc.
        
        return endpoints

    def _extract_user_flows(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract common user flows from analysis"""
        flows = []
        
        # Basic flow: navigation through pages
        if len(analysis.get("pages", [])) > 1:
            flows.append({
                "name": "Page Navigation Flow",
                "steps": [
                    {"action": "visit", "url": page.get("url", "")}
                    for page in analysis["pages"][:3]
                ]
            })
        
        # Form submission flows
        for i, form in enumerate(analysis.get("forms", [])[:2]):
            flow_steps = [
                {"action": "visit", "url": form.get("page_url", "")},
                {"action": "fill_form", "form_data": form}
            ]
            flows.append({
                "name": f"Form Submission Flow {i+1}",
                "steps": flow_steps
            })
        
        return flows

    def _generate_visual_tests(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate visual regression tests"""
        visual_tests = []
        
        for page in analysis.get("pages", []):
            if page.get("screenshot"):
                visual_tests.append({
                    "name": f"Visual test for {page.get('url', 'unknown')}",
                    "url": page.get("url"),
                    "baseline_screenshot": page["screenshot"],
                    "type": "full_page"
                })
        
        return visual_tests

    def _generate_accessibility_tests(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate accessibility tests"""
        accessibility_tests = []
        
        for page in analysis.get("pages", []):
            accessibility_tests.append({
                "name": f"Accessibility test for {page.get('url', 'unknown')}",
                "url": page.get("url"),
                "checks": [
                    "alt_text",
                    "form_labels",
                    "heading_structure",
                    "color_contrast",
                    "keyboard_navigation"
                ]
            })
        
        return accessibility_tests

    async def _save_test_suite(self, test_suite: Dict[str, Any]) -> None:
        """Save test suite to file"""
        try:
            output_path = config.tests_dir / "generated_test_suite.json"
            with open(output_path, 'w') as f:
                json.dump(test_suite, f, indent=2)
            logger.info(f"Test suite saved to {output_path}")
        except Exception as e:
            logger.error(f"Error saving test suite: {e}")

    async def _load_test_suite(self) -> Optional[Dict[str, Any]]:
        """Load test suite from file"""
        try:
            suite_path = config.tests_dir / "generated_test_suite.json"
            if suite_path.exists():
                with open(suite_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading test suite: {e}")
        return None

    async def _save_test_results(self, results: Dict[str, Any]) -> None:
        """Save test results to file"""
        try:
            output_path = config.reports_dir / "test_results.json"
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Test results saved to {output_path}")
        except Exception as e:
            logger.error(f"Error saving test results: {e}")

    def _detect_changes(self, baseline: Dict[str, Any], current: Dict[str, Any]) -> List[str]:
        """Detect changes between baseline and current analysis"""
        changes = []
        
        # Compare number of pages
        baseline_pages = len(baseline.get("pages", []))
        current_pages = len(current.get("pages", []))
        
        if baseline_pages != current_pages:
            changes.append(f"Page count changed: {baseline_pages} -> {current_pages}")
        
        # Compare forms
        baseline_forms = len(baseline.get("forms", []))
        current_forms = len(current.get("forms", []))
        
        if baseline_forms != current_forms:
            changes.append(f"Form count changed: {baseline_forms} -> {current_forms}")
        
        return changes

    def _tests_passed(self, results: Dict[str, Any]) -> bool:
        """Check if all tests passed"""
        summary = results.get("summary", {})
        return summary.get("failed", 0) == 0

    def _generate_test_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate test execution summary"""
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        
        # Count results from all test types
        for test_type, test_results in results.items():
            if test_type == "summary":
                continue
            
            if isinstance(test_results, list):
                for result in test_results:
                    total_tests += 1
                    if result.get("status") == "passed":
                        passed_tests += 1
                    else:
                        failed_tests += 1
        
        return {
            "total": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0
        }