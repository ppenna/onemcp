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

PROJECT_ROOT=$(git rev-parse --show-toplevel)
SCRIPTS_DIR=${PROJECT_ROOT}/scripts

#==================================================================================================
# Imports
#==================================================================================================

source "${SCRIPTS_DIR}/utils.sh"

#==================================================================================================
# Functions
#==================================================================================================

install_prerequisites() {
    print_status "Installing prerequisites..."
    sudo apt-get update
    sudo apt-get install -y \
      build-essential \
      ca-certificates \
      curl \
      git \
      gnupg \
      lsb-release \
      python3 \
      python3-dev \
      python3-pip \
      python3-venv
}

# Function to install Docker
install_docker() {
  # Skip Docker installation in CI environment.
  if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
    print_status "Skipping Docker installation (CI environment)"
    return 0
  fi

  print_status "Checking if Docker is installed..."

  if command -v docker &> /dev/null; then
    # Try to get Docker version using --format if available, else fallback
    if docker --version --format '{{.Server.Version}}' &> /dev/null; then
      DOCKER_VERSION=$(docker --version --format '{{.Server.Version}}')
    else
      DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
    fi
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

    # Install Docker using the universal installation script
    print_status "Installing Docker using Docker's universal installation script..."
    if command_exists apt-get; then
      sudo apt-get update
    else
      print_error "apt-get is not available on this system. Please use a Debian-based Linux distribution."
      exit 1
    fi

    # Install prerequisites
    install_prerequisites

  else
    print_error "Unsupported operating system: $OSTYPE"
    print_status "Please install Docker manually from: https://docs.docker.com/get-docker/"
    return 1
  fi
}

# Checks if Python version is compatible.
check_python_version() {
  print_status "Checking Python version..."
  if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    REQUIRED_VERSION="3.10"

    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then
      print_success "Python $PYTHON_VERSION found"
      return 0
    else
      print_error "Python 3.10+ is required. Found: $PYTHON_VERSION"
      return 1
    fi
  else
    print_error "Python 3 is not installed or not in PATH"
    return 1
  fi
}

create_venv() {
  print_status "Creating virtual environment..."
  if [ ! -d "${PROJECT_ROOT}/.venv" ]; then
    python3 -m venv "${PROJECT_ROOT}/.venv"
    print_success "Virtual environment created at ${PROJECT_ROOT}/.venv"
  else
    print_warning "Virtual environment already exists at ${PROJECT_ROOT}/.venv"
  fi
}

#==================================================================================================
# Main Script
#==================================================================================================

print_success "🚀 Setting up OneMCP development environment..."

if ! check_python_version; then
  print_error "Python version check failed. Please install Python 3.10+."
  exit 1
fi

install_docker

create_venv

activate_virtualenv

upgrade_pip
install_dev_deps

# Install git hooks
print_status "Installing git hooks..."
"${SCRIPTS_DIR}"/install-hooks.sh

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
