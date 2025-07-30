#!/bin/bash

# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

# Setup script for OneMCP development environment

#==================================================================================================

# Exit on any error
set -euo pipefail

#==================================================================================================
# Constants
#==================================================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

#==================================================================================================
# Functions
#==================================================================================================

# Function to print colored output
print_status() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
  echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

#==================================================================================================
# Main Script
#==================================================================================================

echo "🚀 Setting up OneMCP development environment..."

# Check if Python 3.9+ is available
print_status "Checking Python version..."
if command -v python3 &> /dev/null; then
  PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
  REQUIRED_VERSION="3.9"

  if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then
    print_success "Python $PYTHON_VERSION found"
    PYTHON_CMD="python3"
  else
    print_error "Python 3.9+ is required. Found: $PYTHON_VERSION"
    exit 1
  fi
else
  print_error "Python 3 is not installed or not in PATH"
  exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
  print_status "Creating virtual environment..."
  $PYTHON_CMD -m venv .venv
  print_success "Virtual environment created"
else
  print_warning "Virtual environment already exists"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install development dependencies
print_status "Installing development dependencies..."
pip install -e ".[dev]"

# Install git hooks
print_status "Installing git hooks..."
./scripts/install-hooks.sh

print_success "Setup complete! 🎉"

echo ""
echo "To activate the virtual environment, run:"
echo "  source .venv/bin/activate"
echo ""
echo "To run the MCP server:"
echo "  python -m onemcp.server"
echo ""
echo "To run tests:"
echo "  pytest"
echo ""
echo "To run linting:"
echo "  ruff check src tests"
echo ""
echo "To format code:"
echo "  ruff format src tests"
