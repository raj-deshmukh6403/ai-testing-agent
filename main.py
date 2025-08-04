#!/usr/bin/env python3
"""
AI Agent for Automated Testing
Main entry point for the testing agent
"""
#hi i am raj
import asyncio
import logging
import typer
from typing import Optional, List
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import json

import sys
sys.path.append("D:\\PProjects\\ML\\ai-testing-agent\\src")

from src.agents.test_agent import TestAgent
from src.agents.ui_analyzer import UIAnalyzer
from src.utils.config import config
from src.generators.test_generator import TestGenerator
from src.generators.api_test_generator import APITestGenerator
from src.generators.load_test_generator import LoadTestGenerator
from src.automation.visual_testing import VisualTester

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.data.get('logging', {}).get('level', 'INFO')),
    format=config.data.get('logging', {}).get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger = logging.getLogger(__name__)

app = typer.Typer(help="AI Agent for Automated Testing")
console = Console()

@app.command()
def analyze(
    url: str = typer.Argument(..., help="URL to analyze"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file for analysis results"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")
):
    """Analyze a web application and extract testing information"""
    
    async def run_analysis():
        console.print(f"🔍 Analyzing application: {url}", style="bold blue")
        
        agent = TestAgent()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing application...", total=None)
            
            try:
                analysis = await agent.analyze_application(url)
                progress.update(task, description="Analysis complete!")
                
                if "error" in analysis:
                    console.print(f"❌ Analysis failed: {analysis['error']}", style="bold red")
                    return
                
                # Display results
                console.print("\n✅ Analysis completed successfully!", style="bold green")
                
                if verbose:
                    _display_analysis_results(analysis)
                
                # Save results
                if output:
                    output_path = Path(output)
                else:
                    output_path = config.reports_dir / "analysis_results.json"
                
                with open(output_path, 'w') as f:
                    json.dump(analysis, f, indent=2)
                
                console.print(f"📄 Analysis saved to: {output_path}", style="green")
                
            except Exception as e:
                progress.update(task, description="Analysis failed!")
                console.print(f"❌ Error during analysis: {e}", style="bold red")
                logger.error(f"Analysis error: {e}")
    
    asyncio.run(run_analysis())

@app.command()
def generate_tests(
    analysis_file: Optional[str] = typer.Option(None, "--analysis", "-a", help="Analysis file to use"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="URL to analyze and generate tests for"),
    test_types: List[str] = typer.Option(["functional"], "--type", "-t", help="Types of tests to generate"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory for test files")
):
    """Generate test suite based on analysis"""
    
    async def run_generation():
        agent = TestAgent()
        
        # Get analysis
        if analysis_file:
            console.print(f"📖 Loading analysis from: {analysis_file}")
            with open(analysis_file, 'r') as f:
                analysis = json.load(f)
        elif url:
            console.print(f"🔍 Analyzing {url} for test generation...")
            analysis = await agent.analyze_application(url)
            if "error" in analysis:
                console.print(f"❌ Analysis failed: {analysis['error']}", style="bold red")
                return
        else:
            console.print("❌ Either --analysis or --url must be provided", style="bold red")
            return
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating test suite...", total=None)
            
            try:
                test_suite = await agent.generate_test_suite(analysis)
                progress.update(task, description="Test generation complete!")
                
                if "error" in test_suite:
                    console.print(f"❌ Test generation failed: {test_suite['error']}", style="bold red")
                    return
                
                console.print("\n✅ Test suite generated successfully!", style="bold green")
                _display_test_suite_summary(test_suite)
                
                # Save test files
                output_path = Path(output_dir) if output_dir else config.tests_dir
                await _save_test_files(test_suite, output_path)
                
                console.print(f"📁 Test files saved to: {output_path}", style="green")
                
            except Exception as e:
                progress.update(task, description="Test generation failed!")
                console.print(f"❌ Error during test generation: {e}", style="bold red")
                logger.error(f"Test generation error: {e}")
    
    asyncio.run(run_generation())

@app.command()
def run_tests(
    test_suite_file: Optional[str] = typer.Option(None, "--suite", "-s", help="Test suite file to execute"),
    test_types: List[str] = typer.Option(["functional"], "--type", "-t", help="Types of tests to run"),
    generate_report: bool = typer.Option(True, "--report", "-r", help="Generate HTML report")
):
    """Execute generated test suite"""
    
    async def run_execution():
        agent = TestAgent()
        
        # Load test suite
        if test_suite_file:
            console.print(f"📖 Loading test suite from: {test_suite_file}")
            with open(test_suite_file, 'r') as f:
                test_suite = json.load(f)
        else:
            # Try to load default test suite
            default_suite = config.tests_dir / "generated_test_suite.json"
            if default_suite.exists():
                console.print(f"📖 Loading default test suite: {default_suite}")
                with open(default_suite, 'r') as f:
                    test_suite = json.load(f)
            else:
                console.print("❌ No test suite found. Generate tests first.", style="bold red")
                return
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Executing tests...", total=None)
            
            try:
                results = await agent.execute_tests(test_suite)
                progress.update(task, description="Test execution complete!")
                
                if "error" in results:
                    console.print(f"❌ Test execution failed: {results['error']}", style="bold red")
                    return
                
                console.print("\n✅ Test execution completed!", style="bold green")
                _display_test_results(results)
                
                if generate_report:
                    report_path = await _generate_html_report(results)
                    console.print(f"📊 HTML report generated: {report_path}", style="green")
                
            except Exception as e:
                progress.update(task, description="Test execution failed!")
                console.print(f"❌ Error during test execution: {e}", style="bold red")
                logger.error(f"Test execution error: {e}")
    
    asyncio.run(run_execution())

@app.command()
def visual_test(
    url: str = typer.Argument(..., help="URL to test"),
    create_baseline: bool = typer.Option(False, "--baseline", "-b", help="Create baseline screenshots"),
    cross_browser: bool = typer.Option(False, "--cross-browser", "-c", help="Run cross-browser tests")
):
    """Run visual regression tests"""
    
    async def run_visual_tests():
        visual_tester = VisualTester()
        
        if create_baseline:
            console.print(f"📸 Creating baseline screenshots for: {url}")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Creating baselines...", total=None)
                
                try:
                    baseline_results = await visual_tester.create_baseline_suite([url])
                    progress.update(task, description="Baseline creation complete!")
                    
                    console.print(f"✅ Created {len(baseline_results['created'])} baseline screenshots", style="bold green")
                    
                    if baseline_results['failed']:
                        console.print(f"⚠️  Failed to create {len(baseline_results['failed'])} baselines", style="yellow")
                
                except Exception as e:
                    progress.update(task, description="Baseline creation failed!")
                    console.print(f"❌ Error creating baselines: {e}", style="bold red")
        
        else:
            console.print(f"🔍 Running visual regression tests for: {url}")
            
            test_config = {
                "name": "Visual Regression Test",
                "url": url,
                "type": "full_page"
            }
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Running visual tests...", total=None)
                
                try:
                    if cross_browser:
                        results = await visual_tester.run_cross_browser_visual_test(test_config)
                        progress.update(task, description="Cross-browser testing complete!")
                        _display_cross_browser_results(results)
                    else:
                        results = await visual_tester.run_visual_tests([test_config])
                        progress.update(task, description="Visual testing complete!")
                        _display_visual_test_results(results)
                    
                    # Generate report
                    if not cross_browser:
                        report_path = visual_tester.generate_visual_test_report(results)
                        console.print(f"📊 Visual test report: {report_path}", style="green")
                
                except Exception as e:
                    progress.update(task, description="Visual testing failed!")
                    console.print(f"❌ Error during visual testing: {e}", style="bold red")
    
    asyncio.run(run_visual_tests())

@app.command()
def continuous(
    url: str = typer.Argument(..., help="URL to monitor"),
    interval: int = typer.Option(3600, "--interval", "-i", help="Check interval in seconds"),
    max_runs: Optional[int] = typer.Option(None, "--max-runs", "-m", help="Maximum number of runs")
):
    """Run continuous testing"""
    
    async def run_continuous():
        console.print(f"🔄 Starting continuous testing for: {url}")
        console.print(f"⏰ Check interval: {interval} seconds")
        
        agent = TestAgent()
        
        try:
            await agent.continuous_testing(url, interval)
        except KeyboardInterrupt:
            console.print("\n⏹️  Continuous testing stopped by user", style="yellow")
        except Exception as e:
            console.print(f"❌ Continuous testing error: {e}", style="bold red")
    
    asyncio.run(run_continuous())

@app.command()
def load_test(
    url: str = typer.Argument(..., help="URL to load test"),
    users: int = typer.Option(10, "--users", "-u", help="Number of concurrent users"),
    duration: str = typer.Option("60s", "--duration", "-d", help="Test duration"),
    spawn_rate: int = typer.Option(2, "--spawn-rate", "-r", help="User spawn rate per second")
):
    """Run load tests"""
    
    console.print(f"⚡ Running load test for: {url}")
    console.print(f"👥 Users: {users}, Duration: {duration}, Spawn rate: {spawn_rate}/s")
    
    load_generator = LoadTestGenerator()
    
    # Generate basic user flows
    user_flows = [
        {
            "name": "Basic Navigation",
            "description": "Navigate through main pages",
            "weight": 3,
            "steps": [
                {"action": "visit", "url": "/", "description": "Visit homepage"},
                {"action": "wait", "duration": 2, "description": "Think time"}
            ]
        }
    ]
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating load test...", total=None)
        
        try:
            # Generate Locust test
            locust_test = load_generator.generate_locust_test(user_flows)
            test_file = load_generator.save_load_test(locust_test, 'locust')
            
            progress.update(task, description="Running load test...")
            
            # Use synchronous version for better compatibility
            results = load_generator.run_locust_test_sync(
                test_file, url, users, spawn_rate, duration
            )
            
            progress.update(task, description="Load test complete!", completed=True)
            
            if results.get('status') == 'completed':
                console.print("✅ Load test completed successfully!", style="bold green")
                html_report = results.get('reports', {}).get('html')
                if html_report and Path(html_report).exists():
                    console.print(f"📊 HTML report: {html_report}")
                    console.print(f"📈 Open in browser: file://{Path(html_report).absolute()}")
                
                # Show some basic stats from stdout
                stdout = results.get('stdout', '')
                if stdout:
                    lines = stdout.split('\n')
                    for line in lines:
                        if any(keyword in line.lower() for keyword in ['requests', 'rps', 'response time', 'failures']):
                            if line.strip():
                                console.print(f"📈 {line.strip()}")
                            
            else:
                error_msg = results.get('error', 'Unknown error')
                console.print(f"❌ Load test failed: {error_msg}", style="bold red")
                
                # Show debug info
                if results.get('stderr'):
                    console.print(f"[dim]Error details:[/dim] {results['stderr']}")
            
        except Exception as e:
            progress.update(task, description="Load test failed!", completed=True)
            console.print(f"❌ Error during load testing: {str(e)}", style="bold red")
            import traceback
            console.print(f"[dim]Traceback:[/dim]\n{traceback.format_exc()}", style="dim red")

@app.command()
def config_info():
    """Display current configuration"""
    
    table = Table(title="AI Testing Agent Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Target URL", config.target_url)
    table.add_row("Browser Type", config.browser.type)
    table.add_row("Headless Mode", str(config.browser.headless))
    table.add_row("Screenshots Dir", str(config.screenshots_dir))
    table.add_row("Reports Dir", str(config.reports_dir))
    table.add_row("Tests Dir", str(config.tests_dir))
    table.add_row("LLM Provider", config.llm.provider)
    table.add_row("LLM Model", config.llm.model)
    
    console.print(table)

def _display_analysis_results(analysis: dict):
    """Display analysis results in a formatted way"""
    
    table = Table(title="Application Analysis Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Pages", str(analysis.get("total_pages", 0)))
    table.add_row("Forms Found", str(len(analysis.get("forms", []))))
    table.add_row("API Endpoints", str(len(analysis.get("api_endpoints", []))))
    table.add_row("User Flows", str(len(analysis.get("user_flows", []))))
    
    console.print(table)

def _display_test_suite_summary(test_suite: dict):
    """Display test suite summary"""
    
    table = Table(title="Generated Test Suite Summary")
    table.add_column("Test Type", style="cyan")
    table.add_column("Count", style="green")
    
    table.add_row("Functional Tests", str(len(test_suite.get("functional_tests", []))))
    table.add_row("API Tests", str(len(test_suite.get("api_tests", []))))
    table.add_row("Visual Tests", str(len(test_suite.get("visual_tests", []))))
    table.add_row("Accessibility Tests", str(len(test_suite.get("accessibility_tests", []))))
    
    console.print(table)

def _display_test_results(results: dict):
    """Display test execution results"""
    
    summary = results.get("summary", {})
    
    table = Table(title="Test Execution Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Tests", str(summary.get("total", 0)))
    table.add_row("Passed", str(summary.get("passed", 0)))
    table.add_row("Failed", str(summary.get("failed", 0)))
    table.add_row("Success Rate", f"{summary.get('success_rate', 0):.1f}%")
    
    console.print(table)

def _display_visual_test_results(results: list):
    """Display visual test results"""
    
    table = Table(title="Visual Test Results")
    table.add_column("Test Name", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Similarity", style="yellow")
    
    for result in results:
        status_style = "green" if result.get("status") == "passed" else "red"
        similarity = result.get("similarity", 0)
        similarity_str = f"{similarity * 100:.1f}%" if similarity else "N/A"
        
        table.add_row(
            result.get("name", "Unknown"),
            f"[{status_style}]{result.get('status', 'unknown')}[/{status_style}]",
            similarity_str
        )
    
    console.print(table)

def _display_cross_browser_results(results: dict):
    """Display cross-browser test results"""
    
    table = Table(title="Cross-Browser Test Results")
    table.add_column("Browser", style="cyan")
    table.add_column("Status", style="green")
    
    for browser, result in results.items():
        if browser == 'cross_browser_comparison':
            continue
        
        status = result.get("status", "unknown")
        status_style = "green" if status == "success" else "red"
        
        table.add_row(
            browser.title(),
            f"[{status_style}]{status}[/{status_style}]"
        )
    
    console.print(table)
    
    # Display comparison results
    comparison = results.get('cross_browser_comparison', {})
    if comparison:
        console.print("\n🔍 Cross-Browser Comparisons:")
        for comp_key, comp_result in comparison.items():
            similarity = comp_result.get('similarity', 0)
            console.print(f"  {comp_key}: {similarity * 100:.1f}% similar")

async def _save_test_files(test_suite: dict, output_dir: Path):
    """Save generated test files"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    test_generator = TestGenerator()
    
    # Save functional tests
    if test_suite.get("functional_tests"):
        functional_code = test_generator.generate_functional_tests(test_suite["functional_tests"])
        with open(output_dir / "test_functional.py", 'w') as f:
            f.write(functional_code)
    
    # Save conftest
    conftest_code = test_generator.generate_conftest()
    with open(output_dir / "conftest.py", 'w') as f:
        f.write(conftest_code)
    
    # Save pytest config
    pytest_config = test_generator.generate_pytest_config()
    with open(output_dir / "pytest.ini", 'w') as f:
        f.write(pytest_config)

async def _generate_html_report(results: dict) -> str:
    """Generate HTML test report"""
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Execution Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .summary { background: #f5f5f5; padding: 15px; border-radius: 5px; }
        .passed { color: #4CAF50; }
        .failed { color: #f44336; }
        .test-section { margin: 20px 0; }
    </style>
</head>
<body>
    <h1>Test Execution Report</h1>
    
    <div class="summary">
        <h2>Summary</h2>
        <p>Total Tests: {{ summary.total }}</p>
        <p>Passed: <span class="passed">{{ summary.passed }}</span></p>
        <p>Failed: <span class="failed">{{ summary.failed }}</span></p>
        <p>Success Rate: {{ "%.1f"|format(summary.success_rate) }}%</p>
    </div>
    
    <div class="test-section">
        <h2>Test Results</h2>
        <!-- Add detailed test results here -->
    </div>
</body>
</html>
"""
    
    from jinja2 import Template
    template = Template(html_template)
    
    html_content = template.render(
        summary=results.get("summary", {}),
        results=results
    )
    
    report_path = config.reports_dir / "test_execution_report.html"
    with open(report_path, 'w') as f:
        f.write(html_content)
    
    return str(report_path)

if __name__ == "__main__":
    app()