#!/bin/bash
# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

# Install Git hooks for OneMCP project

set -euo pipefail

#==================================================================================================
# Main Script
#==================================================================================================

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

# Copy post-merge hook
cp hooks/post-merge .git/hooks/post-merge

# Make hooks executable
chmod +x .git/hooks/pre-push
chmod +x .git/hooks/post-merge

echo "Git hooks installed successfully!"
echo "The pre-push hook will now run before each push to ensure code quality."
echo "The post-merge hook will now run after git pull to refresh virtual environment when dependencies change."
