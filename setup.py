
from setuptools import setup, find_packages

setup(
    name="ai-testing-agent",
    version="1.0.0",
    description="AI Agent for Automated Testing with Playwright and LLM",
    author="AI Testing Team",
    author_email="team@aitesting.com",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "playwright>=1.40.0",
        "openai>=1.3.0",
        "opencv-python>=4.8.1.78",
        "pytest>=7.4.3",
        "pytest-asyncio>=0.21.1",
        "requests>=2.31.0",
        "locust>=2.17.0",
        "Pillow>=10.1.0",
        "PyYAML>=6.0.1",
        "python-dotenv>=1.0.0",
        "aiohttp>=3.9.1",
        "beautifulsoup4>=4.12.2",
        "selenium>=4.15.2",
        "numpy>=1.24.3",
        "scikit-image>=0.22.0",
        "jinja2>=3.1.2",
        "rich>=13.7.0",
        "typer>=0.9.0",
        "pydantic>=2.5.0",
    ],
    entry_points={
        "console_scripts": [
            "ai-test-agent=main:app",
        ],
    },
)