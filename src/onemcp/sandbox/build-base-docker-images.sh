#!/bin/bash

set -euo pipefail

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]:-${(%):-%x}}" )" >/dev/null 2>&1 && pwd )"

pushd ${THIS_DIR} > /dev/null

docker build -t onemcp/base/python:v1 -f install_python_mcp.dockerfile .

popd > /dev/null
