from openai import OpenAI
import asyncio
from typing import List, Dict, Any, Optional
from utils.config import config
import logging
import json
import warnings
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed transport")

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        if config.llm.provider == "openai":
            # Initialize the OpenAI client with API key
            self.openai_client = OpenAI(api_key=config.openai_api_key)
        self.provider = config.llm.provider
        self.model = config.llm.model
        self.temperature = config.llm.temperature
        self.max_tokens = config.llm.max_tokens

    async def generate_test_cases(self, page_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate test cases based on page analysis"""
        prompt = self._create_test_generation_prompt(page_info)
        
        try:
            response = await self._call_llm(prompt)
            return self._parse_test_cases(response)
        except Exception as e:
            logger.error(f"Error generating test cases: {e}")
            return []

    async def analyze_ui_elements(self, elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze UI elements and suggest test scenarios"""
        prompt = self._create_ui_analysis_prompt(elements)
        
        try:
            response = await self._call_llm(prompt)
            return self._parse_ui_analysis(response)
        except Exception as e:
            logger.error(f"Error analyzing UI elements: {e}")
            return {}

    async def generate_api_tests(self, api_endpoints: List[Dict[str, Any]]) -> List[str]:
        """Generate API test code"""
        prompt = self._create_api_test_prompt(api_endpoints)
        
        try:
            response = await self._call_llm(prompt)
            return self._parse_api_tests(response)
        except Exception as e:
            logger.error(f"Error generating API tests: {e}")
            return []

    async def generate_load_tests(self, user_flows: List[Dict[str, Any]]) -> str:
        """Generate load testing script"""
        prompt = self._create_load_test_prompt(user_flows)
        
        try:
            response = await self._call_llm(prompt)
            return self._parse_load_test(response)
        except Exception as e:
            logger.error(f"Error generating load tests: {e}")
            return ""

    async def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM"""
        if self.provider == "openai":
            return await self._call_openai(prompt)
        else:
            raise NotImplementedError(f"Provider {self.provider} not implemented")

    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API using the new client"""
        try:
            # Run the synchronous OpenAI call in a thread pool to make it async
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert QA engineer and test automation specialist."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def _create_test_generation_prompt(self, page_info: Dict[str, Any]) -> str:
        """Create prompt for test case generation"""
        return f"""
        Based on the following web page analysis, generate comprehensive test cases:

        Page URL: {page_info.get('url', 'N/A')}
        Page Title: {page_info.get('title', 'N/A')}
        Forms: {page_info.get('forms', [])}
        Buttons: {page_info.get('buttons', [])}
        Links: {page_info.get('links', [])}
        Input Fields: {page_info.get('inputs', [])}

        Please generate test cases in the following JSON format:
        {{
            "test_cases": [
                {{
                    "name": "Test case name",
                    "description": "Test case description",
                    "steps": ["Step 1", "Step 2", "Step 3"],
                    "expected_result": "Expected outcome",
                    "priority": "high|medium|low",
                    "type": "functional|ui|integration"
                }}
            ]
        }}

        Focus on:
        1. Form validation tests
        2. Navigation tests
        3. UI interaction tests
        4. Edge cases and error scenarios
        5. Accessibility tests
        """

    def _create_ui_analysis_prompt(self, elements: List[Dict[str, Any]]) -> str:
        """Create prompt for UI element analysis"""
        return f"""
        Analyze the following UI elements and provide testing recommendations:

        Elements: {elements}

        Please provide analysis in JSON format:
        {{
            "critical_elements": ["element1", "element2"],
            "test_scenarios": ["scenario1", "scenario2"],
            "accessibility_concerns": ["concern1", "concern2"],
            "usability_issues": ["issue1", "issue2"]
        }}
        """

    def _create_api_test_prompt(self, api_endpoints: List[Dict[str, Any]]) -> str:
        """Create prompt for API test generation"""
        return f"""
        Generate Python API test code using pytest and requests for these endpoints:

        {api_endpoints}

        Include tests for:
        1. Happy path scenarios
        2. Error handling
        3. Authentication
        4. Data validation
        5. Performance boundaries

        Format as complete Python test file.
        """

    def _create_load_test_prompt(self, user_flows: List[Dict[str, Any]]) -> str:
        """Create prompt for load test generation"""
        return f"""
        Generate a Locust load testing script for these user flows:

        {user_flows}

        Include:
        1. User behavior simulation
        2. Realistic wait times
        3. Error handling
        4. Performance metrics
        5. Scalable task distribution

        Format as complete Python Locust file.
        """

    def _parse_test_cases(self, response: str) -> List[Dict[str, Any]]:
        """Parse test cases from LLM response"""
        try:
            # Extract JSON from response if wrapped in markdown
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
            elif "```" in response:
                # Handle cases where JSON is in code blocks without language specification
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
            
            data = json.loads(response)
            return data.get('test_cases', [])
        except Exception as e:
            logger.error(f"Error parsing test cases: {e}")
            logger.debug(f"Response that failed to parse: {response}")
            return []

    def _parse_ui_analysis(self, response: str) -> Dict[str, Any]:
        """Parse UI analysis from LLM response"""
        try:
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
            
            return json.loads(response)
        except Exception as e:
            logger.error(f"Error parsing UI analysis: {e}")
            logger.debug(f"Response that failed to parse: {response}")
            return {}

    def _parse_api_tests(self, response: str) -> List[str]:
        """Parse API tests from LLM response"""
        try:
            # Extract Python code blocks
            if "```python" in response:
                python_start = response.find("```python") + 9
                python_end = response.find("```", python_start)
                code = response[python_start:python_end].strip()
                return [code]
            elif "```" in response:
                # Handle code blocks without language specification
                python_start = response.find("```") + 3
                python_end = response.find("```", python_start)
                code = response[python_start:python_end].strip()
                return [code]
            return [response]
        except Exception as e:
            logger.error(f"Error parsing API tests: {e}")
            return [response]

    def _parse_load_test(self, response: str) -> str:
        """Parse load test from LLM response"""
        try:
            if "```python" in response:
                python_start = response.find("```python") + 9
                python_end = response.find("```", python_start)
                return response[python_start:python_end].strip()
            elif "```" in response:
                python_start = response.find("```") + 3
                python_end = response.find("```", python_start)
                return response[python_start:python_end].strip()
            return response
        except Exception as e:
            logger.error(f"Error parsing load test: {e}")
            return response

    # Optional: Add a method to handle different OpenAI models
    def set_model(self, model: str):
        """Set the OpenAI model to use"""
        self.model = model

    # Optional: Add a method to adjust temperature
    def set_temperature(self, temperature: float):
        """Set the temperature for responses"""
        self.temperature = max(0.0, min(2.0, temperature))  # Clamp between 0 and 2