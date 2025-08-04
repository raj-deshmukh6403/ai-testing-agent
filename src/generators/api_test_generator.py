import asyncio
import json
from typing import List, Dict, Any, Optional
import aiohttp
import pytest
import logging
from pathlib import Path
from utils.config import config
import warnings
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed transport")

logger = logging.getLogger(__name__)

class APITestGenerator:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def generate_api_tests(self, endpoints: List[Dict[str, Any]]) -> str:
        """Generate API test code for given endpoints"""
        
        imports = """
import pytest
import aiohttp
import json
import asyncio
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

"""
        
        fixtures = """
@pytest.fixture
async def api_session():
    async with aiohttp.ClientSession() as session:
        yield session

"""
        
        test_methods = []
        
        for endpoint in endpoints:
            method_code = self._generate_endpoint_tests(endpoint)
            test_methods.append(method_code)
        
        complete_code = imports + fixtures + "\n\n".join(test_methods)
        return complete_code

    def _generate_endpoint_tests(self, endpoint: Dict[str, Any]) -> str:
        """Generate tests for a specific endpoint"""
        url = endpoint.get('url', '')
        method = endpoint.get('method', 'GET').upper()
        endpoint_name = self._sanitize_name(url)
        
        test_code = f"""
class Test{endpoint_name.title()}:
    \"\"\"Tests for {method} {url}\"\"\"
    
    BASE_URL = "{url}"
    
    @pytest.mark.asyncio
    async def test_{endpoint_name}_success(self, api_session):
        \"\"\"Test successful {method} request\"\"\"
        async with api_session.{method.lower()}(self.BASE_URL) as response:
            assert response.status == 200
            data = await response.json()
            assert data is not None
            logger.info(f"✓ {method} {url} - Success response received")
    
    @pytest.mark.asyncio
    async def test_{endpoint_name}_response_time(self, api_session):
        \"\"\"Test response time is acceptable\"\"\"
        import time
        start_time = time.time()
        
        async with api_session.{method.lower()}(self.BASE_URL) as response:
            end_time = time.time()
            response_time = end_time - start_time
            
            assert response_time < 5.0, f"Response time too slow: {{response_time:.2f}}s"
            logger.info(f"✓ {method} {url} - Response time: {{response_time:.2f}}s")
    
    @pytest.mark.asyncio
    async def test_{endpoint_name}_headers(self, api_session):
        \"\"\"Test response headers\"\"\"
        async with api_session.{method.lower()}(self.BASE_URL) as response:
            assert 'content-type' in response.headers
            assert response.headers.get('content-type', '').startswith('application/json')
            logger.info(f"✓ {method} {url} - Headers validated")
"""
        
        # Add method-specific tests
        if method == 'POST':
            test_code += self._generate_post_tests(endpoint_name, url)
        elif method == 'PUT':
            test_code += self._generate_put_tests(endpoint_name, url)
        elif method == 'DELETE':
            test_code += self._generate_delete_tests(endpoint_name, url)
        
        # Add error handling tests
        test_code += self._generate_error_tests(endpoint_name, url, method)
        
        return test_code

    def _generate_post_tests(self, endpoint_name: str, url: str) -> str:
        """Generate POST-specific tests"""
        return f"""
    @pytest.mark.asyncio
    async def test_{endpoint_name}_post_valid_data(self, api_session):
        \"\"\"Test POST with valid data\"\"\"
        test_data = {{"test": "data", "timestamp": "2024-01-01T00:00:00Z"}}
        
        async with api_session.post(self.BASE_URL, json=test_data) as response:
            assert response.status in [200, 201, 202]
            logger.info(f"✓ POST {url} - Valid data accepted")
    
    @pytest.mark.asyncio
    async def test_{endpoint_name}_post_invalid_data(self, api_session):
        \"\"\"Test POST with invalid data\"\"\"
        invalid_data = "invalid json string"
        
        async with api_session.post(self.BASE_URL, data=invalid_data) as response:
            assert response.status >= 400
            logger.info(f"✓ POST {url} - Invalid data rejected")
    
    @pytest.mark.asyncio
    async def test_{endpoint_name}_post_empty_data(self, api_session):
        \"\"\"Test POST with empty data\"\"\"
        async with api_session.post(self.BASE_URL, json={{}}) as response:
            # Accept either success (if empty data is valid) or client error
            assert response.status in [200, 201, 400, 422]
            logger.info(f"✓ POST {url} - Empty data handled")
"""

    def _generate_put_tests(self, endpoint_name: str, url: str) -> str:
        """Generate PUT-specific tests"""
        return f"""
    @pytest.mark.asyncio
    async def test_{endpoint_name}_put_update(self, api_session):
        \"\"\"Test PUT update operation\"\"\"
        update_data = {{"updated": True, "timestamp": "2024-01-01T00:00:00Z"}}
        
        async with api_session.put(self.BASE_URL, json=update_data) as response:
            assert response.status in [200, 201, 204]
            logger.info(f"✓ PUT {url} - Update successful")
"""

    def _generate_delete_tests(self, endpoint_name: str, url: str) -> str:
        """Generate DELETE-specific tests"""
        return f"""
    @pytest.mark.asyncio
    async def test_{endpoint_name}_delete(self, api_session):
        \"\"\"Test DELETE operation\"\"\"
        async with api_session.delete(self.BASE_URL) as response:
            assert response.status in [200, 202, 204, 404]
            logger.info(f"✓ DELETE {url} - Delete operation completed")
"""

    def _generate_error_tests(self, endpoint_name: str, url: str, method: str) -> str:
        """Generate error handling tests"""
        return f"""
    @pytest.mark.asyncio
    async def test_{endpoint_name}_unauthorized(self, api_session):
        \"\"\"Test unauthorized access\"\"\"
        headers = {{"Authorization": "Bearer invalid_token"}}
        
        async with api_session.{method.lower()}(self.BASE_URL, headers=headers) as response:
            # Should either work (no auth required) or return 401/403
            assert response.status in [200, 401, 403]
            logger.info(f"✓ {method} {url} - Authorization handled")
    
    @pytest.mark.asyncio
    async def test_{endpoint_name}_not_found_similar(self, api_session):
        \"\"\"Test similar but non-existent endpoint\"\"\"
        similar_url = self.BASE_URL + "_nonexistent"
        
        async with api_session.{method.lower()}(similar_url) as response:
            assert response.status == 404
            logger.info(f"✓ {method} {{similar_url}} - 404 for non-existent endpoint")
"""

    def _sanitize_name(self, url: str) -> str:
        """Convert URL to valid Python identifier"""
        import re
        # Remove protocol and domain
        name = url.split('/')[-1] if '/' in url else url
        # Remove query parameters
        name = name.split('?')[0]
        # Replace special characters
        name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # Remove leading/trailing underscores
        name = name.strip('_')
        # Ensure it doesn't start with a number
        if name and name[0].isdigit():
            name = 'endpoint_' + name
        
        return name or 'unknown_endpoint'

    async def execute_tests(self, test_code: str) -> List[Dict[str, Any]]:
        """Execute generated API tests"""
        results = []
        
        try:
            # Save test code to temporary file
            test_file = config.tests_dir / "temp_api_tests.py"
            with open(test_file, 'w') as f:
                f.write(test_code)
            
            # Run tests using pytest
            import subprocess
            result = subprocess.run([
                'python', '-m', 'pytest', str(test_file), '-v', '--tb=short'
            ], capture_output=True, text=True)
            
            # Parse results (simplified)
            if result.returncode == 0:
                results.append({
                    "test_type": "api",
                    "status": "passed",
                    "output": result.stdout
                })
            else:
                results.append({
                    "test_type": "api",
                    "status": "failed",
                    "output": result.stdout,
                    "error": result.stderr
                })
            
            # Clean up
            test_file.unlink(exist_ok=True)
            
        except Exception as e:
            logger.error(f"Error executing API tests: {e}")
            results.append({
                "test_type": "api",
                "status": "error",
                "error": str(e)
            })
        
        return results

    async def discover_endpoints(self, base_url: str) -> List[Dict[str, Any]]:
        """Discover API endpoints (basic implementation)"""
        endpoints = []
        
        try:
            async with aiohttp.ClientSession() as session:
                # Try common API paths
                common_paths = [
                    '/api', '/api/v1', '/api/v2',
                    '/rest', '/graphql',
                    '/health', '/status',
                    '/users', '/user', '/profile',
                    '/products', '/product',
                    '/orders', '/order'
                ]
                
                for path in common_paths:
                    test_url = base_url.rstrip('/') + path
                    
                    try:
                        async with session.get(test_url, timeout=5) as response:
                            if response.status != 404:
                                endpoints.append({
                                    'url': test_url,
                                    'method': 'GET',
                                    'status': response.status,
                                    'content_type': response.headers.get('content-type', '')
                                })
                    except asyncio.TimeoutError:
                        continue
                    except Exception:
                        continue
        
        except Exception as e:
            logger.error(f"Error discovering endpoints: {e}")
        
        return endpoints

    def generate_load_test_api(self, endpoints: List[Dict[str, Any]]) -> str:
        """Generate load test for API endpoints using Locust"""
        template = """
from locust import HttpUser, task, between
import json
import random

class APIUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        \"\"\"Setup for each user\"\"\"
        self.client.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'LoadTest/1.0'
        })
    
{% for endpoint in endpoints %}
    @task({{ loop.index }})
    def test_{{ endpoint.name }}(self):
        \"\"\"Load test for {{ endpoint.method }} {{ endpoint.url }}\"\"\"
        {% if endpoint.method == 'GET' %}
        response = self.client.get("{{ endpoint.path }}")
        {% elif endpoint.method == 'POST' %}
        test_data = {"load_test": True, "timestamp": "2024-01-01"}
        response = self.client.post("{{ endpoint.path }}", json=test_data)
        {% elif endpoint.method == 'PUT' %}
        update_data = {"updated": True, "load_test": True}
        response = self.client.put("{{ endpoint.path }}", json=update_data)
        {% elif endpoint.method == 'DELETE' %}
        response = self.client.delete("{{ endpoint.path }}")
        {% endif %}
        
        if response.status_code >= 400:
            print(f"{{ endpoint.method }} {{ endpoint.path }} failed: {response.status_code}")

{% endfor %}

# Run with: locust -f this_file.py --host=http://your-api-host.com
"""
        
        from jinja2 import Template
        jinja_template = Template(template)
        
        # Prepare endpoint data
        endpoint_data = []
        for i, endpoint in enumerate(endpoints):
            endpoint_data.append({
                'name': self._sanitize_name(endpoint.get('url', f'endpoint_{i}')),
                'method': endpoint.get('method', 'GET'),
                'url': endpoint.get('url', ''),
                'path': endpoint.get('url', '').split('/')[-1] if '/' in endpoint.get('url', '') else '/'
            })
        
        return jinja_template.render(endpoints=endpoint_data)