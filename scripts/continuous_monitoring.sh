#!/bin/bash

# Continuous monitoring script

set -e

URL="$1"
INTERVAL="${2:-3600}"  # Default 1 hour
MAX_RUNS="${3:-0}"     # Default unlimited

if [ -z "$URL" ]; then
    echo "Usage: $0 <URL> [INTERVAL] [MAX_RUNS]"
    echo "Example: $0 https://example.com 1800 24"
    exit 1
fi

echo "🔄 Starting continuous monitoring for: $URL"
echo "⏰ Check interval: $INTERVAL seconds"
echo "🔢 Max runs: $([ $MAX_RUNS -eq 0 ] && echo "unlimited" || echo $MAX_RUNS)"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Create monitoring log
LOG_FILE="reports/monitoring_$(date +%Y%m%d_%H%M%S).log"
echo "📝 Logging to: $LOG_FILE"

# Function to handle cleanup
cleanup() {
    echo "🛑 Stopping continuous monitoring..."
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Main monitoring loop
RUN_COUNT=0
while true; do
    RUN_COUNT=$((RUN_COUNT + 1))
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo "[$TIMESTAMP] 🔍 Run #$RUN_COUNT - Monitoring $URL" | tee -a "$LOG_FILE"
    
    # Run the monitoring
    if python main.py continuous "$URL" --interval "$INTERVAL" --max-runs 1 >> "$LOG_FILE" 2>&1; then
        echo "[$TIMESTAMP] ✅ Monitoring run completed successfully" | tee -a "$LOG_FILE"
    else
        echo "[$TIMESTAMP] ❌ Monitoring run failed" | tee -a "$LOG_FILE"
    fi
    
    # Check if we've reached max runs
    if [ $MAX_RUNS -gt 0 ] && [ $RUN_COUNT -ge $MAX_RUNS ]; then
        echo "[$TIMESTAMP] 🏁 Reached maximum runs ($MAX_RUNS)" | tee -a "$LOG_FILE"
        break
    fi
    
    # Wait for next interval
    echo "[$TIMESTAMP] ⏳ Waiting $INTERVAL seconds until next run..." | tee -a "$LOG_FILE"
    sleep "$INTERVAL"
done

echo "🏁 Continuous monitoring completed"