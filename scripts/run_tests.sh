#!/bin/bash

# Test execution script with different configurations

set -e

# Default values
URL="https://example.com"
TEST_TYPES="functional"
USERS=10
DURATION="60s"
SPAWN_RATE=2

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --url)
            URL="$2"
            shift 2
            ;;
        --types)
            TEST_TYPES="$2"
            shift 2
            ;;
        --users)
            USERS="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --spawn-rate)
            SPAWN_RATE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --url URL           Target URL to test"
            echo "  --types TYPES       Test types (functional,visual,api,load)"
            echo "  --users USERS       Number of users for load testing"
            echo "  --duration DURATION Load test duration"
            echo "  --spawn-rate RATE   User spawn rate for load testing"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "🚀 Starting AI Testing Agent"
echo "Target URL: $URL"
echo "Test Types: $TEST_TYPES"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Step 1: Analyze the application
echo "🔍 Step 1: Analyzing application..."
python main.py analyze "$URL" --verbose

# Step 2: Generate tests based on types
echo "📝 Step 2: Generating test suite..."
IFS=',' read -ra TYPES <<< "$TEST_TYPES"
TYPE_ARGS=""
for type in "${TYPES[@]}"; do
    TYPE_ARGS="$TYPE_ARGS --type $type"
done

python main.py generate-tests --url "$URL" $TYPE_ARGS

# Step 3: Run functional and visual tests
if [[ "$TEST_TYPES" == *"functional"* ]] || [[ "$TEST_TYPES" == *"visual"* ]]; then
    echo "🧪 Step 3: Running functional and visual tests..."
    python main.py run-tests --report
fi

# Step 4: Run load tests if requested
if [[ "$TEST_TYPES" == *"load"* ]]; then
    echo "⚡ Step 4: Running load tests..."
    python main.py load-test "$URL" --users "$USERS" --duration "$DURATION" --spawn-rate "$SPAWN_RATE"
fi

# Step 5: Run visual regression tests if requested
if [[ "$TEST_TYPES" == *"visual"* ]]; then
    echo "👁️  Step 5: Running visual regression tests..."
    python main.py visual-test "$URL"
fi

echo "✅ All tests completed!"
echo "📊 Check the reports/ directory for detailed results"
echo "📁 Generated tests are in generated_tests/ directory"