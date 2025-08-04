import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class BrowserConfig(BaseModel):
    type: str = "chromium"
    headless: bool = True
    viewport: Dict[str, int] = {"width": 1920, "height": 1080}
    timeout: int = 30000

class LLMConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4"
    temperature: float = 0.3
    max_tokens: int = 2000

class TestingConfig(BaseModel):
    visual_regression: Dict[str, Any] = {
        "enabled": True,
        "threshold": 0.95,
        "pixel_diff_threshold": 0.1
    }
    api_testing: Dict[str, Any] = {
        "enabled": True,
        "timeout": 10
    }
    load_testing: Dict[str, Any] = {
        "enabled": True,
        "users": 10,
        "spawn_rate": 2,
        "duration": 60
    }

class Config:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
        
        with open(config_path, 'r') as file:
            self.data = yaml.safe_load(file)
        
        self.browser = BrowserConfig(**self.data.get('browser', {}))
        self.llm = LLMConfig(**self.data.get('llm', {}))
        self.testing = TestingConfig(**self.data.get('testing', {}))
        
        # Environment variables
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        self.target_url = os.getenv('TARGET_URL', 'https://example.com')
        
        # Directories
        self.screenshots_dir = Path(self.data.get('output', {}).get('screenshots_dir', './screenshots'))
        self.reports_dir = Path(self.data.get('output', {}).get('reports_dir', './reports'))
        self.tests_dir = Path(self.data.get('output', {}).get('tests_dir', './generated_tests'))
        
        # Create directories if they don't exist
        for dir_path in [self.screenshots_dir, self.reports_dir, self.tests_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

# Global config instance
config = Config()