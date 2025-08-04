from typing import List, Dict, Any
import logging
from pathlib import Path
from jinja2 import Template
from utils.config import config
import warnings
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed transport")

logger = logging.getLogger(__name__)

class TestGenerator:
    def __init__(self):
        self.template_dir = Path(__file__).parent / "templates"
        self.template_dir.mkdir(exist_ok=True)

    def generate_playwright_test(self, test_case: Dict[str, Any]) -> str:
        """Generate Playwright test code from test case"""
        template_str = """
import pytest
from playwright.async_api import async_playwright, Page, Browser

class Test{{ class_name }}:
    @pytest.fixture(scope="class")
    async def browser(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            yield browser
            await browser.close()

    @pytest.fixture
    async def page(self, browser: Browser):
        page = await browser.new_page()
        yield page
        await page.close()

    @pytest.mark.asyncio
    async def test_{{ test_method_name }}(self, page: Page):
        \"\"\"{{ description }}\"\"\"
        
        {% for step in steps %}
        # {{ step }}
        {% if step.startswith('Navigate to') %}
        await page.goto("{{ url }}")
        {% elif step.startswith('Click') %}
        await page.click("{{ step | extract_selector }}")
        {% elif step.startswith('Fill') %}
        await page.fill("{{ step | extract_selector }}", "{{ step | extract_value }}")
        {% elif step.startswith('Wait for') %}
        await page.wait_for_selector("{{ step | extract_selector }}")
        {% endif %}
        {% endfor %}
        
        # Verify expected result
        # {{ expected_result }}
        # Add appropriate assertions here
        
"""
        
        template = Template(template_str)
        
        # Prepare template variables
        class_name = test_case.get('name', 'Unknown').replace(' ', '').replace('-', '')
        test_method_name = test_case.get('name', 'unknown').lower().replace(' ', '_').replace('-', '_')
        
        return template.render(
            class_name=class_name,
            test_method_name=test_method_name,
            description=test_case.get('description', ''),
            steps=test_case.get('steps', []),
            expected_result=test_case.get('expected_result', ''),
            url=test_case.get('url', '')
        )

    def generate_functional_tests(self, test_cases: List[Dict[str, Any]]) -> str:
        """Generate complete functional test file"""
        imports = """
import pytest
import asyncio
from playwright.async_api import async_playwright, Page, Browser, expect
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

"""
        
        fixture_code = """
@pytest.fixture(scope="session")
async def browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()

@pytest.fixture
async def page(browser: Browser):
    page = await browser.new_page()
    yield page
    await page.close()

"""
        
        test_methods = []
        
        for i, test_case in enumerate(test_cases):
            method_code = self._generate_test_method(test_case, i)
            test_methods.append(method_code)
        
        complete_code = imports + fixture_code + "\n\n".join(test_methods)
        return complete_code

    def _generate_test_method(self, test_case: Dict[str, Any], index: int) -> str:
        """Generate individual test method"""
        method_name = f"test_{test_case.get('name', f'case_{index}').lower().replace(' ', '_')}"
        
        method_code = f"""
@pytest.mark.asyncio
async def {method_name}(page: Page):
    \"\"\"
    {test_case.get('description', 'Generated test case')}
    Priority: {test_case.get('priority', 'medium')}
    Type: {test_case.get('type', 'functional')}
    \"\"\"
    try:
        # Test steps
"""
        
        for step in test_case.get('steps', []):
            method_code += f"        # {step}\n"
            method_code += self._generate_step_code(step)
        
        method_code += f"""
        
        # Expected result: {test_case.get('expected_result', 'Test should pass')}
        logger.info("Test {method_name} completed successfully")
        
    except Exception as e:
        logger.error(f"Test {method_name} failed: {{e}}")
        raise
"""
        
        return method_code

    def _generate_step_code(self, step: str) -> str:
        """Generate code for individual test step"""
        step_lower = step.lower()
        
        if 'navigate' in step_lower or 'go to' in step_lower:
            return '        await page.goto("{{ URL }}")\n        await page.wait_for_load_state("networkidle")\n'
        
        elif 'click' in step_lower:
            if 'button' in step_lower:
                return '        await page.click("button")\n'
            elif 'link' in step_lower:
                return '        await page.click("a")\n'
            else:
                return '        await page.click("{{ SELECTOR }}")\n'
        
        elif 'fill' in step_lower or 'enter' in step_lower or 'type' in step_lower:
            return '        await page.fill("input", "{{ VALUE }}")\n'
        
        elif 'select' in step_lower:
            return '        await page.select_option("select", "{{ VALUE }}")\n'
        
        elif 'wait' in step_lower:
            return '        await page.wait_for_selector("{{ SELECTOR }}")\n'
        
        elif 'verify' in step_lower or 'check' in step_lower or 'assert' in step_lower:
            return '        await expect(page.locator("{{ SELECTOR }}")).to_be_visible()\n'
        
        else:
            return f'        # TODO: Implement step: {step}\n'

    def generate_visual_regression_test(self, test_config: Dict[str, Any]) -> str:
        """Generate visual regression test"""
        template_str = """
import pytest
from playwright.async_api import Page, Browser
from pathlib import Path
import cv2
import numpy as np

@pytest.mark.asyncio
async def test_visual_regression_{{ test_name }}(page: Page):
    \"\"\"Visual regression test for {{ url }}\"\"\"
    
    # Navigate to page
    await page.goto("{{ url }}")
    await page.wait_for_load_state("networkidle")
    
    # Take screenshot
    screenshot_path = Path("screenshots/current_{{ test_name }}.png")
    await page.screenshot(path=str(screenshot_path), full_page=True)
    
    # Compare with baseline
    baseline_path = Path("{{ baseline_screenshot }}")
    
    if baseline_path.exists():
        # Load images
        current = cv2.imread(str(screenshot_path))
        baseline = cv2.imread(str(baseline_path))
        
        # Resize if different sizes
        if current.shape != baseline.shape:
            baseline = cv2.resize(baseline, (current.shape[1], current.shape[0]))
        
        # Calculate difference
        diff = cv2.absdiff(current, baseline)
        diff_percentage = np.sum(diff) / (diff.shape[0] * diff.shape[1] * diff.shape[2] * 255) * 100
        
        # Assert similarity
        assert diff_percentage < {{ threshold }}, f"Visual difference too high: {diff_percentage:.2f}%"
        
        # Save diff image if significant difference
        if diff_percentage > 1:  # 1% threshold for saving diff
            cv2.imwrite(f"screenshots/diff_{{ test_name }}.png", diff)
    else:
        # First run - save as baseline
        import shutil
        shutil.copy(str(screenshot_path), str(baseline_path))
        pytest.skip("Baseline screenshot created")
"""
        
        template = Template(template_str)
        
        return template.render(
            test_name=test_config.get('name', 'unknown').lower().replace(' ', '_'),
            url=test_config.get('url', ''),
            baseline_screenshot=test_config.get('baseline_screenshot', ''),
            threshold=test_config.get('threshold', 5)  # 5% difference threshold
        )

    def save_test_file(self, test_code: str, filename: str) -> str:
        """Save generated test code to file"""
        try:
            file_path = config.tests_dir / filename
            with open(file_path, 'w') as f:
                f.write(test_code)
            
            logger.info(f"Test file saved: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Error saving test file: {e}")
            return ""

    def generate_pytest_config(self) -> str:
        """Generate pytest configuration"""
        config_content = """
[tool:pytest]
testpaths = generated_tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v 
    --tb=short 
    --strict-markers
    --html=reports/report.html
    --self-contained-html
markers =
    functional: Functional tests
    visual: Visual regression tests
    api: API tests
    smoke: Smoke tests
    regression: Regression tests
asyncio_mode = auto
"""
        return config_content

    def generate_conftest(self) -> str:
        """Generate pytest conftest file"""
        conftest_content = """
import pytest
import asyncio
from playwright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture(scope="session")
def event_loop():
    \"\"\"Create an instance of the default event loop for the test session.\"\"\"
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def browser():
    \"\"\"Launch browser for test session\"\"\"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()

@pytest.fixture
async def context(browser):
    \"\"\"Create new browser context for each test\"\"\"
    context = await browser.new_context()
    yield context
    await context.close()

@pytest.fixture
async def page(context):
    \"\"\"Create new page for each test\"\"\"
    page = await context.new_page()
    yield page
    await page.close()

def pytest_configure(config):
    \"\"\"Pytest configuration hook\"\"\"
    config.addinivalue_line("markers", "functional: functional tests")
    config.addinivalue_line("markers", "visual: visual regression tests")
    config.addinivalue_line("markers", "api: API tests")
"""
        return conftest_content