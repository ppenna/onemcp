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

# Function to install Docker
install_docker() {
  print_status "Checking if Docker is installed..."

  if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
    print_success "Docker $DOCKER_VERSION is already installed"

    # Check if Docker daemon is running
    if docker info &> /dev/null; then
      print_success "Docker daemon is running"
    else
      print_warning "Docker is installed but daemon is not running"
      print_status "You may need to start Docker manually or run: sudo systemctl start docker"
    fi
    return 0
  fi

  print_status "Docker not found. Installing Docker..."

  # Detect OS
  if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux installation
    print_status "Detected Linux. Installing Docker via official script..."

    # Update package index
    print_status "Updating package index..."
    sudo apt-get update

    # Install prerequisites
    print_status "Installing prerequisites..."
    sudo apt-get install -y \
      ca-certificates \
      curl \
      gnupg \
      lsb-release

    # Add Docker's official GPG key
    print_status "Adding Docker GPG key..."
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

    # Set up the repository
    print_status "Setting up Docker repository..."
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Update package index again
    sudo apt-get update

    # Install Docker Engine
    print_status "Installing Docker Engine..."
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Add current user to docker group
    print_status "Adding user to docker group..."
    sudo usermod -aG docker $USER
    print_warning "You need to log out and back in for the group changes to take effect."
    print_status "Alternatively, you can run 'exec su -l $USER' to apply the changes immediately."

    if docker ps >/dev/null 2>&1; then
      print_success "Docker installed successfully!"
    else
      print_error "Failed to install docker!"
    fi

  elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS installation
    print_status "Detected macOS. Please install Docker Desktop manually:"
    echo "1. Visit: https://docs.docker.com/desktop/install/mac-install/"
    echo "2. Download Docker Desktop for Mac"
    echo "3. Install the .dmg file"
    echo "4. Start Docker Desktop from Applications"
    print_warning "Manual installation required for macOS"

  else
    print_error "Unsupported operating system: $OSTYPE"
    print_status "Please install Docker manually from: https://docs.docker.com/get-docker/"
    return 1
  fi
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

# Install Docker
print_warning "About to install Docker, this step requires sudo"
install_docker

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
echo ""
echo "Docker commands:"
echo "  docker --version    # Check Docker version"
echo "  docker info         # Check Docker daemon status"
echo "  docker run hello-world  # Test Docker installation"
