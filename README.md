# AI Agent for Automated Testing

A comprehensive AI-powered testing agent that automatically generates and executes test cases for web applications using Playwright, computer vision, and Large Language Models (LLMs).

## Features

- **🤖 AI-Powered Test Generation**: Uses LLMs to automatically generate comprehensive test cases
- **🎭 Browser Automation**: Playwright-based testing across Chromium, Firefox, and WebKit
- **👁️ Computer Vision**: Visual regression testing and UI element detection
- **🔍 Comprehensive Analysis**: Deep web application analysis including forms, navigation, and accessibility
- **⚡ Load Testing**: Automated load test generation using Locust
- **🌐 API Testing**: Automatic API endpoint discovery and test generation
- **📊 Rich Reporting**: HTML reports with screenshots and detailed results
- **🔄 Continuous Testing**: Monitor applications for changes and run tests automatically

## Installation

### Prerequisites

- Python 3.8 or higher
- Node.js (for Playwright browsers)

### Setup

1. **Clone the repository**:
```bash
git clone <repository-url>
cd ai-testing-agent
```

2. **Create virtual environment**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Install Playwright browsers**:
```bash
playwright install
```

5. **Setup environment variables**:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

Required environment variables:
- `OPENAI_API_KEY`: Your OpenAI API key for LLM-powered test generation
- `TARGET_URL`: Default URL to test (optional)

## Quick Start

### 1. Analyze a Web Application

```bash
python main.py analyze https://example.com --verbose
```

This will:
- Analyze the web application structure
- Detect UI elements using computer vision
- Extract forms, navigation, and accessibility information
- Save analysis results to `reports/analysis_results.json`

### 2. Generate Test Suite

```bash
python main.py generate-tests --url https://example.com --type functional --type visual
```

This will:
- Generate functional tests based on the analysis
- Create visual regression tests
- Save test files to `generated_tests/` directory

### 3. Execute Tests

```bash
python main.py run-tests --report
```

This will:
- Execute all generated tests
- Generate an HTML report with results
- Save screenshots and test artifacts

### 4. Visual Regression Testing

Create baseline screenshots:
```bash
python main.py visual-test https://example.com --baseline
```

Run visual regression tests:
```bash
python main.py visual-test https://example.com
```

Cross-browser visual testing:
```bash
python main.py visual-test https://example.com --cross-browser
```

### 5. Load Testing

```bash
python main.py load-test https://example.com --users 50 --duration 300s --spawn-rate 5
```

### 6. Continuous Testing

```bash
python main.py continuous https://example.com --interval 3600
```

## Configuration

The agent uses a YAML configuration file at `config/settings.yaml`. Key settings include:

```yaml
agent:
  name: "AI Testing Agent"
  max_iterations: 10

llm:
  provider: "openai"  # openai or anthropic
  model: "gpt-4"
  temperature: 0.3

browser:
  type: "chromium"  # chromium, firefox, webkit
  headless: true
  viewport:
    width: 1920
    height: 1080

testing:
  visual_regression:
    enabled: true
    threshold: 0.95
  api_testing:
    enabled: true
  load_testing:
    enabled: true
    users: 10
    duration: 60
```

## Project Structure

```
ai-testing-agent/
├── src/
│   ├── agents/           # Core AI agents
│   │   ├── test_agent.py     # Main testing orchestrator
│   │   └── ui_analyzer.py    # UI analysis and element detection
│   ├── automation/       # Test execution engines
│   │   ├── playwright_runner.py  # Playwright test execution
│   │   └── visual_testing.py     # Visual regression testing
│   ├── generators/       # Test code generators
│   │   ├── test_generator.py     # Functional test generation
│   │   ├── api_test_generator.py # API test generation
│   │   └── load_test_generator.py # Load test generation
│   └── utils/           # Utilities and helpers
│       ├── config.py         # Configuration management
│       ├── llm_client.py     # LLM integration
│       └── cv_utils.py       # Computer vision utilities
├── config/
│   └── settings.yaml     # Main configuration file
├── generated_tests/      # Generated test files
├── screenshots/          # Screenshots and visual artifacts
├── reports/             # Test reports and results
├── main.py              # CLI entry point
└── requirements.txt     # Python dependencies
```

## Advanced Usage

### Custom Test Generation

You can extend the test generation by modifying the LLM prompts in `src/utils/llm_client.py` or by creating custom test templates in the generators.

### Adding New Test Types

1. Create a new generator in `src/generators/`
2. Implement the test generation logic
3. Integrate with the main `TestAgent` class
4. Add CLI commands in `main.py`

### Computer Vision Customization

Modify `src/utils/cv_utils.py` to:
- Adjust visual similarity thresholds
- Add custom UI element detection
- Implement domain-specific visual checks

### API Integration

The agent can integrate with various APIs:
- **CI/CD Systems**: Jenkins, GitHub Actions, GitLab CI
- **Test Management**: TestRail, Zephyr, qTest
- **Monitoring**: Datadog, New Relic, Grafana

## Examples

### Testing an E-commerce Site

```bash
# Analyze the site
python main.py analyze https://shop.example.com --verbose

# Generate comprehensive tests
python main.py generate-tests --url https://shop.example.com \
  --type functional --type visual --type api

# Run tests with detailed reporting
python main.py run-tests --report

# Load test the checkout process
python main.py load-test https://shop.example.com \
  --users 100 --duration 600s --spawn-rate 10
```

### Testing a SaaS Application

```bash
# Continuous monitoring
python main.py continuous https://app.example.com --interval 1800

# Cross-browser visual testing
python main.py visual-test https://app.example.com --cross-browser

# API endpoint testing
python main.py generate-tests --url https://app.example.com --type api
```

## Troubleshooting

### Common Issues

1. **Playwright Installation Issues**:
```bash
playwright install --force
```

2. **OpenAI API Errors**:
- Check your API key in `.env`
- Verify you have sufficient credits
- Check rate limits

3. **Visual Test Failures**:
- Ensure consistent viewport sizes
- Check for dynamic content
- Adjust similarity thresholds

4. **Load Test Issues**:
- Verify target server can handle load
- Check network connectivity
- Monitor resource usage

### Debug Mode

Enable verbose logging:
```bash
export LOG_LEVEL=DEBUG
python main.py analyze https://example.com --verbose
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Create an issue on GitHub
- Check the documentation
- Review the troubleshooting guide

## Roadmap

- [ ] Integration with more LLM providers (Anthropic, Cohere)
- [ ] Mobile app testing support
- [ ] Advanced AI-powered test maintenance
- [ ] Integration with popular CI/CD platforms
- [ ] Real-time collaboration features
- [ ] Advanced performance testing scenarios
- [ ] Machine learning-based test optimization