#!/bin/bash

source ../.project_config

# Check if a directory argument was provided
if [ -z "$1" ]; then
    echo "Usage: $0 <directory>"
    echo "Example: $0 burstingBubbleHB"
    exit 1
fi

RESTART_DIR="$1"
RESTART_FILE="$RESTART_DIR/restart"
REFRESH_INTERVAL=2  # Seconds between file checks
VIEWER_PID=""

# Path to our custom visualization tools
INDEPENDENT_VIEWER="../custom_tools/independent_viewer"
V_VIEW="../custom_tools/v_view2D"

# Ensure cleanup on script exit
cleanup() {
    if [ ! -z "$VIEWER_PID" ] && ps -p $VIEWER_PID > /dev/null; then
        echo "Cleaning up viewer process..."
        kill $VIEWER_PID 2>/dev/null
    fi
    
    echo "Visualization terminated."
    exit 0
}

trap cleanup EXIT INT TERM

echo "Monitoring $RESTART_FILE for changes..."
echo "Press Ctrl+C to stop."

# Check if our independent viewer exists and is executable
if [ -x "$INDEPENDENT_VIEWER" ]; then
    # Start independent viewer with auto-refresh
    if [ -f "$RESTART_FILE" ]; then
        echo "Starting independent viewer with auto-refresh..."
        "$INDEPENDENT_VIEWER" -interval $REFRESH_INTERVAL "$RESTART_FILE" &
        VIEWER_PID=$!
        echo "Independent viewer started with PID: $VIEWER_PID"
        echo "This viewer will automatically update when the file changes."
        echo "IMPORTANT: The simulation runs independently from this viewer."
    else
        echo "Warning: $RESTART_FILE does not exist yet. Will wait for it to be created."
        
        # Wait for file to be created
        while true; do
            if [ -f "$RESTART_FILE" ]; then
                echo "File created, starting visualization..."
                "$INDEPENDENT_VIEWER" -interval $REFRESH_INTERVAL "$RESTART_FILE" &
                VIEWER_PID=$!
                echo "Independent viewer started with PID: $VIEWER_PID"
                echo "This viewer will automatically update when the file changes."
                echo "IMPORTANT: The simulation runs independently from this viewer."
                break
            fi
            sleep 1
        done
    fi
# Check if our v_view2D exists and is executable
elif [ -x "$V_VIEW" ]; then
    # Start v_view with auto-refresh
    if [ -f "$RESTART_FILE" ]; then
        echo "Starting v_view2D with auto-refresh..."
        "$V_VIEW" -interval $REFRESH_INTERVAL "$RESTART_FILE" &
        VIEWER_PID=$!
        echo "v_view2D started with PID: $VIEWER_PID"
        echo "This viewer will automatically update when the file changes."
    else
        echo "Warning: $RESTART_FILE does not exist yet. Will wait for it to be created."
        
        # Wait for file to be created
        while true; do
            if [ -f "$RESTART_FILE" ]; then
                echo "File created, starting visualization..."
                "$V_VIEW" -interval $REFRESH_INTERVAL "$RESTART_FILE" &
                VIEWER_PID=$!
                echo "v_view2D started with PID: $VIEWER_PID"
                echo "This viewer will automatically update when the file changes."
                break
            fi
            sleep 1
        done
    fi
else
    echo "Custom viewers not found. Using standard bview2D (requires manual refresh)..."
    
    # Start viewer if file exists
    if [ -f "$RESTART_FILE" ]; then
        bview2D "$RESTART_FILE" &
        VIEWER_PID=$!
        echo "Started bview2D with PID: $VIEWER_PID"
        echo "NOTE: You will need to manually refresh your browser when the file changes."
    else
        echo "Warning: $RESTART_FILE does not exist yet. Will wait for it to be created."
        
        # Wait for file to be created
        while true; do
            if [ -f "$RESTART_FILE" ]; then
                echo "File created, starting visualization..."
                bview2D "$RESTART_FILE" &
                VIEWER_PID=$!
                echo "Started bview2D with PID: $VIEWER_PID"
                echo "NOTE: You will need to manually refresh your browser when the file changes."
                break
            fi
            sleep 1
        done
    fi
fi

# Monitor to ensure the viewer is still running
while true; do
    if [ ! -z "$VIEWER_PID" ] && ! ps -p $VIEWER_PID > /dev/null; then
        echo "Viewer process crashed, restarting..."
        
        # Restart the viewer
        if [ -f "$RESTART_FILE" ]; then
            if [ -x "$INDEPENDENT_VIEWER" ]; then
                "$INDEPENDENT_VIEWER" -interval $REFRESH_INTERVAL "$RESTART_FILE" &
                VIEWER_PID=$!
                echo "Independent viewer restarted with PID: $VIEWER_PID"
            elif [ -x "$V_VIEW" ]; then
                "$V_VIEW" -interval $REFRESH_INTERVAL "$RESTART_FILE" &
                VIEWER_PID=$!
                echo "v_view2D restarted with PID: $VIEWER_PID"
            else
                bview2D "$RESTART_FILE" &
                VIEWER_PID=$!
                echo "bview2D restarted with PID: $VIEWER_PID"
            fi
        fi
    fi
    
    # Sleep to reduce CPU usage
    sleep 2
done