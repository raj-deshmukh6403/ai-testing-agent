
import pytest
import asyncio
from playwright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def browser():
    """Launch browser for test session"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()

@pytest.fixture
async def context(browser):
    """Create new browser context for each test"""
    context = await browser.new_context()
    yield context
    await context.close()

@pytest.fixture
async def page(context):
    """Create new page for each test"""
    page = await context.new_page()
    yield page
    await page.close()

def pytest_configure(config):
    """Pytest configuration hook"""
    config.addinivalue_line("markers", "functional: functional tests")
    config.addinivalue_line("markers", "visual: visual regression tests")
    config.addinivalue_line("markers", "api: API tests")
