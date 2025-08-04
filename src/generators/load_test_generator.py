from typing import List, Dict, Any
import logging
from pathlib import Path
from jinja2 import Template
import subprocess
import asyncio
from utils.config import config
import warnings
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed transport")

logger = logging.getLogger(__name__)

class LoadTestGenerator:
    def __init__(self):
        pass

    def generate_locust_test(self, user_flows: List[Dict[str, Any]]) -> str:
        """Generate Locust load test script"""
        
        # Updated template without problematic event listeners
        template_str = """
from locust import HttpUser, task, between
import random
import json
import time
import logging

logger = logging.getLogger(__name__)

class WebsiteUser(HttpUser):
    wait_time = between({{ min_wait }}, {{ max_wait }})
    
    def on_start(self):
        \"\"\"Called when a user starts\"\"\"
        self.client.headers.update({
            'User-Agent': 'LoadTest-Agent/1.0'
        })
        logger.info(f"User started")
    
    def on_stop(self):
        \"\"\"Called when a user stops\"\"\"
        logger.info(f"User stopped")

{% for flow in user_flows %}
    @task({{ flow.weight | default(1) }})
    def {{ flow.method_name }}(self):
        \"\"\"{{ flow.description }}\"\"\"
        try:
            {% for step in flow.steps %}
            # {{ step.description }}
            {% if step.action == 'visit' %}
            with self.client.get("{{ step.url }}", catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Got status code {response.status_code}")
                    logger.warning(f"GET {{ step.url }} returned {response.status_code}")
            
            {% elif step.action == 'fill_form' %}
            form_data = {{ step.data | tojson }}
            with self.client.post("{{ step.url }}", data=form_data, catch_response=True) as response:
                if response.status_code in [200, 201, 302]:
                    response.success()
                else:
                    response.failure(f"Got status code {response.status_code}")
                    logger.warning(f"POST {{ step.url }} returned {response.status_code}")
            
            {% elif step.action == 'click_link' %}
            with self.client.get("{{ step.url }}", catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Got status code {response.status_code}")
                    logger.warning(f"GET {{ step.url }} returned {response.status_code}")
            
            {% elif step.action == 'wait' %}
            time.sleep({{ step.duration | default(1) }})
            
            {% elif step.action == 'api_call' %}
            {% if step.method == 'POST' %}
            with self.client.post("{{ step.url }}", json={{ step.data | tojson }}, catch_response=True) as response:
                if response.status_code < 400:
                    response.success()
                else:
                    response.failure(f"Got status code {response.status_code}")
                    logger.warning(f"POST {{ step.url }} returned {response.status_code}")
            {% else %}
            with self.client.get("{{ step.url }}", catch_response=True) as response:
                if response.status_code < 400:
                    response.success()
                else:
                    response.failure(f"Got status code {response.status_code}")
                    logger.warning(f"GET {{ step.url }} returned {response.status_code}")
            {% endif %}
            {% endif %}
            
            {% endfor %}
            
            # Random think time
            time.sleep(random.uniform(0.5, 2.0))
            
        except Exception as e:
            logger.error(f"Error in {{ flow.method_name }}: {str(e)}")

{% endfor %}

# Usage:
# locust -f generated_load_test.py --host=https://your-target-site.com
# locust -f generated_load_test.py --host=https://your-target-site.com --users=50 --spawn-rate=5 -t 300s
"""
        
        template = Template(template_str)
        
        # Process user flows for template
        processed_flows = []
        for i, flow in enumerate(user_flows):
            method_name = f"user_flow_{i+1}"
            if 'name' in flow:
                method_name = flow['name'].lower().replace(' ', '_').replace('-', '_')
            
            processed_steps = []
            for step in flow.get('steps', []):
                if isinstance(step, dict):
                    processed_steps.append(step)
                elif isinstance(step, str):
                    # Convert string steps to structured format
                    processed_steps.append(self._parse_step_string(step))
            
            processed_flows.append({
                'method_name': method_name,
                'description': flow.get('description', f'User flow {i+1}'),
                'weight': flow.get('weight', 1),
                'steps': processed_steps
            })
        
        return template.render(
            user_flows=processed_flows,
            min_wait=1,
            max_wait=5
        )

    def _parse_step_string(self, step: str) -> Dict[str, Any]:
        """Parse a step string into structured format"""
        step_lower = step.lower()
        
        if 'navigate' in step_lower or 'visit' in step_lower:
            return {
                'action': 'visit',
                'description': step,
                'url': '/',  # Default, should be replaced with actual URL
            }
        elif 'fill' in step_lower or 'submit' in step_lower:
            return {
                'action': 'fill_form',
                'description': step,
                'url': '/submit',  # Default
                'data': {'test': 'data'}  # Default
            }
        elif 'click' in step_lower:
            return {
                'action': 'click_link',
                'description': step,
                'url': '/'  # Default
            }
        elif 'wait' in step_lower:
            return {
                'action': 'wait',
                'description': step,
                'duration': 2
            }
        else:
            return {
                'action': 'custom',
                'description': step,
                'url': '/'
            }

    def generate_artillery_test(self, user_flows: List[Dict[str, Any]]) -> str:
        """Generate Artillery.io load test configuration"""
        config_template = """
config:
  target: "{{ target_url }}"
  phases:
    - duration: 60
      arrivalRate: 5
      name: "Warm up"
    - duration: 120
      arrivalRate: 10
      name: "Ramp up load"
    - duration: 180
      arrivalRate: 20
      name: "Sustained load"
  payload:
    path: "./test-data.csv"
    fields:
      - "username"
      - "password"
  defaults:
    headers:
      User-Agent: "Artillery Load Test"

scenarios:
{% for flow in user_flows %}
  - name: "{{ flow.name }}"
    weight: {{ flow.weight | default(1) }}
    flow:
    {% for step in flow.steps %}
      {% if step.action == 'visit' %}
      - get:
          url: "{{ step.url }}"
          expect:
            - statusCode: 200
      {% elif step.action == 'fill_form' %}
      - post:
          url: "{{ step.url }}"
          form: {{ step.data | tojson }}
          expect:
            - statusCode: [200, 201, 302]
      {% elif step.action == 'wait' %}
      - think: {{ step.duration | default(2) }}
      {% endif %}
    {% endfor %}
{% endfor %}
"""
        
        template = Template(config_template)
        return template.render(
            target_url="{{ TARGET_URL }}",  # Will be replaced when running
            user_flows=user_flows
        )

    def generate_k6_test(self, user_flows: List[Dict[str, Any]]) -> str:
        """Generate k6 load test script"""
        script_template = """
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
export let errorRate = new Rate('errors');

// Test configuration
export let options = {
  stages: [
    { duration: '30s', target: 10 },  // Ramp up
    { duration: '1m', target: 20 },   // Stay at 20 users
    { duration: '30s', target: 50 },  // Ramp up to 50
    { duration: '2m', target: 50 },   // Stay at 50
    { duration: '30s', target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% of requests must complete below 500ms
    errors: ['rate<0.1'], // Error rate must be below 10%
  },
};

export default function() {
  // Choose random user flow
  const flows = [
    {% for flow in user_flows %}
    {{ flow.name | tojson }},
    {% endfor %}
  ];
  
  const selectedFlow = flows[Math.floor(Math.random() * flows.length)];
  
  {% for flow in user_flows %}
  {% if loop.first %}if{% else %}else if{% endif %} (selectedFlow === {{ flow.name | tojson }}) {
    // {{ flow.description }}
    {% for step in flow.steps %}
    {% if step.action == 'visit' %}
    let response{{ loop.index }} = http.get('{{ step.url }}');
    check(response{{ loop.index }}, {
      'status is 200': (r) => r.status === 200,
      'response time < 500ms': (r) => r.timings.duration < 500,
    });
    errorRate.add(response{{ loop.index }}.status !== 200);
    
    {% elif step.action == 'fill_form' %}
    let formData{{ loop.index }} = {{ step.data | tojson }};
    let response{{ loop.index }} = http.post('{{ step.url }}', formData{{ loop.index }});
    check(response{{ loop.index }}, {
      'form submission successful': (r) => r.status >= 200 && r.status < 400,
    });
    errorRate.add(response{{ loop.index }}.status >= 400);
    
    {% elif step.action == 'wait' %}
    sleep({{ step.duration | default(1) }});
    {% endif %}
    {% endfor %}
  }
  {% endfor %}
  
  // Random sleep between iterations
  sleep(Math.random() * 3 + 1);
}

export function handleSummary(data) {
  return {
    'load-test-results.json': JSON.stringify(data),
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
  };
}
"""
        
        template = Template(script_template)
        return template.render(user_flows=user_flows)

    async def run_locust_test(self, test_file: str, target_url: str, 
                             users: int = 10, spawn_rate: int = 2, 
                             duration: str = "60s") -> Dict[str, Any]:
        """Run Locust load test"""
        try:
            # Ensure reports directory exists
            config.reports_dir.mkdir(parents=True, exist_ok=True)
            
            cmd = [
                'locust',
                '-f', test_file,
                '--host', target_url,
                '--users', str(users),
                '--spawn-rate', str(spawn_rate),
                '-t', duration,
                '--headless',
                '--csv', str(config.reports_dir / 'load_test'),
                '--html', str(config.reports_dir / 'load_test_report.html')
            ]
            
            logger.info(f"Running Locust test: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            result = {
                'status': 'completed' if process.returncode == 0 else 'failed',
                'return_code': process.returncode,
                'stdout': stdout.decode(),
                'stderr': stderr.decode(),
                'reports': {
                    'html': str(config.reports_dir / 'load_test_report.html'),
                    'csv_stats': str(config.reports_dir / 'load_test_stats.csv'),
                    'csv_history': str(config.reports_dir / 'load_test_stats_history.csv')
                }
            }
            
            if process.returncode != 0:
                result['error'] = stderr.decode() or stdout.decode() or f'Process exited with code {process.returncode}'
            
            return result
            
        except Exception as e:
            logger.error(f"Error running Locust test: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def run_locust_test_sync(self, test_file: str, target_url: str, 
                            users: int = 10, spawn_rate: int = 2, 
                            duration: str = "60s") -> Dict[str, Any]:
        """Run Locust load test synchronously"""
        try:
            # Ensure reports directory exists
            config.reports_dir.mkdir(parents=True, exist_ok=True)
            
            cmd = [
                'locust',
                '-f', test_file,
                '--host', target_url,
                '--users', str(users),
                '--spawn-rate', str(spawn_rate),
                '-t', duration,
                '--headless',
                '--csv', str(config.reports_dir / 'load_test'),
                '--html', str(config.reports_dir / 'load_test_report.html')
            ]
            
            logger.info(f"Running Locust test: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                return {
                    'status': 'completed',
                    'reports': {
                        'html': str(config.reports_dir / 'load_test_report.html'),
                        'csv_stats': str(config.reports_dir / 'load_test_stats.csv'),
                        'csv_history': str(config.reports_dir / 'load_test_stats_history.csv')
                    },
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
            else:
                return {
                    'status': 'failed',
                    'error': result.stderr or result.stdout or f'Process exited with code {result.returncode}',
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'return_code': result.returncode
                }
                
        except subprocess.TimeoutExpired:
            return {
                'status': 'failed',
                'error': 'Test timed out after 5 minutes'
            }
        except FileNotFoundError:
            return {
                'status': 'failed',
                'error': 'Locust not found. Please install with: pip install locust'
            }
        except Exception as e:
            return {
                'status': 'failed',
                'error': str(e)
            }

    def generate_performance_test_suite(self, analysis: Dict[str, Any]) -> Dict[str, str]:
        """Generate complete performance test suite"""
        
        user_flows = analysis.get('user_flows', [])
        
        if not user_flows:
            # Generate default flows based on pages
            user_flows = self._generate_default_flows(analysis)
        
        test_suite = {
            'locust': self.generate_locust_test(user_flows),
            'artillery': self.generate_artillery_test(user_flows),
            'k6': self.generate_k6_test(user_flows)
        }
        
        return test_suite

    def _generate_default_flows(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate default user flows from analysis"""
        flows = []
        
        pages = analysis.get('pages', [])
        if not pages:
            return flows
        
        # Simple navigation flow
        if len(pages) > 1:
            flow_steps = [
                {
                    'action': 'visit',
                    'url': page.get('url', '/'),
                    'description': f"Visit {page.get('title', 'page')}"
                }
                for page in pages[:3]  # Limit to first 3 pages
            ]
            
            flows.append({
                'name': 'Navigation Flow',
                'description': 'Basic page navigation',
                'weight': 3,
                'steps': flow_steps
            })
        
        # Form submission flow
        forms = analysis.get('forms', [])
        if forms:
            form = forms[0]  # Use first form
            flows.append({
                'name': 'Form Submission Flow',
                'description': 'Submit forms with test data',
                'weight': 2,
                'steps': [
                    {
                        'action': 'visit',
                        'url': form.get('page_url', '/'),
                        'description': 'Visit form page'
                    },
                    {
                        'action': 'fill_form',
                        'url': form.get('action', '/submit'),
                        'data': self._generate_form_data(form),
                        'description': 'Submit form with test data'
                    }
                ]
            })
        
        return flows

    def _generate_form_data(self, form: Dict[str, Any]) -> Dict[str, Any]:
        """Generate test data for form"""
        test_data = {}
        
        for input_field in form.get('inputs', []):
            field_name = input_field.get('name', '')
            field_type = input_field.get('type', 'text')
            
            if field_name:
                if field_type == 'email':
                    test_data[field_name] = 'test@example.com'
                elif field_type == 'password':
                    test_data[field_name] = 'TestPassword123'
                elif field_type == 'number':
                    test_data[field_name] = '42'
                elif field_type == 'date':
                    test_data[field_name] = '2024-01-01'
                else:
                    test_data[field_name] = 'Test Value'
        
        return test_data

    def save_load_test(self, test_code: str, test_type: str = 'locust') -> str:
        """Save load test to file"""
        try:
            # Ensure tests directory exists
            config.tests_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"load_test_{test_type}.py" if test_type == 'locust' else f"load_test_{test_type}.js"
            file_path = config.tests_dir / filename
            
            with open(file_path, 'w') as f:
                f.write(test_code)
            
            logger.info(f"Load test saved: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Error saving load test: {e}")
            return ""