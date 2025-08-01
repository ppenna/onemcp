#!/bin/bash

REPOSITORY_URL=

if [ -z "${REPOSITORY_URL}" ]; then
    echo "Error: REPOSITORY_URL is not set. Please provide a valid repository URL." >&2
    exit 1
fi
REPOSITORY_NAME=$(basename "${REPOSITORY_URL}" .git)

# Install necessary packages
apt update
apt install -y git python3 python3-pip python3-venv curl

# Clone the repository
git clone ${REPOSITORY_URL}
cd "${REPOSITORY_NAME}"

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install the MCP server using pip inside the virtual environment
pip install .

# Final fallback: try to extract from pyproject.toml or setup.py
if [ -f "pyproject.toml" ]; then
    PACKAGE_NAME=$(grep -E "^name\s*=" pyproject.toml | sed 's/.*=\s*["\x27]\([^"\x27]*\)["\x27].*/\1/' | tr '-' '_')
fi

if [ -z "${PACKAGE_NAME}" ] && [ -f "setup.py" ]; then
    PACKAGE_NAME=$(python3 setup.py --name 2>/dev/null | tr '-' '_')
fi

if [ -z "${PACKAGE_NAME}" ]; then
    echo "Warning: Could not determine package name. Using default value 'default_package_name'." >&2
    PACKAGE_NAME="default_package_name"
fi
# Generate a script to run the MCP server
echo "#!/bin/bash
source $(pwd)/venv/bin/activate
python3 -m ${PACKAGE_NAME}" > /run_mcp.sh
chmod +x /run_mcp.sh
