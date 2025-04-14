#!/bin/bash

# Script to build custom Basilisk visualization tools

# Ensure we're in the custom_tools directory
cd "$(dirname "$0")"

echo "Building Basilisk visualization tools..."

# Check if make exists
if ! command -v make &> /dev/null; then
    echo "Error: make command not found. Please install build tools."
    exit 1
fi

# Build the tools
make clean
make all

# Check if tools were built successfully
if [ ! -f "independent_viewer" ] || [ ! -f "v_view2D" ]; then
    echo "Error: Failed to build one or more tools."
    exit 1
fi

echo "Build successful!"
echo "Available tools:"

# List the tools
if [ -f "independent_viewer" ]; then
    echo " - independent_viewer ($(ls -lh independent_viewer | awk '{print $5}'))"
fi

if [ -f "v_view2D" ]; then
    echo " - v_view2D ($(ls -lh v_view2D | awk '{print $5}'))"
fi

if [ -f "v_view3D" ]; then
    echo " - v_view3D ($(ls -lh v_view3D | awk '{print $5}'))"
fi

echo 
echo "Usage instructions:"
echo " - For independent visualization: ./independent_viewer /path/to/restart"
echo " - For v_view2D visualization: ./v_view2D /path/to/restart"
echo
echo "Or use the visualizeResult.sh script in the testCases directory."
echo

exit 0 