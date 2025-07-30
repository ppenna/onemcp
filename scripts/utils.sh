#!/bin/bash

# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

#==================================================================================================
# Constants
#==================================================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_ROOT=$(git rev-parse --show-toplevel)

#==================================================================================================
# Functions
#==================================================================================================

print_status() {
  echo -e "${BLUE}[HOOK]${NC} $1"
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

# Activates the virtual environment if it exists.
activate_virtualenv() {
  if [ -d "${PROJECT_ROOT}/.venv" ]; then
    source "${PROJECT_ROOT}/.venv/bin/activate"
    print_success "Virtual environment activated"
  else
    print_error "Virtual environment not found. Run ./scripts/setup.sh first."
    exit 1
  fi
}
