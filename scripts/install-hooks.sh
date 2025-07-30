#!/bin/bash
# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

# Install Git hooks for OneMCP project

set -e

echo "Installing Git hooks..."

# Check if we're in a git repository
if [ ! -d ".git" ]; then
  echo "Error: Not in a git repository"
  exit 1
fi

# Create .git/hooks directory if it doesn't exist
mkdir -p .git/hooks

# Copy pre-push hook
cp hooks/pre-push .git/hooks/pre-push

# Make hook executable
chmod +x .git/hooks/pre-push

echo "Git hooks installed successfully!"
echo "The pre-push hook will now run before each push to ensure code quality."
