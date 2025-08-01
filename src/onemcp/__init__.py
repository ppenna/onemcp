# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

"""OneMCP - A Dynamic Orchestrator for MCP Servers"""

from .discovery import MockRegistry, Registry, RegistryInterface, ServerEntry, ToolEntry

__version__ = "0.1.0"
__author__ = "Pedro Henrique Penna"
__email__ = "pedro.penna@example.com"

__all__ = ["Registry", "RegistryInterface", "ServerEntry", "ToolEntry", "MockRegistry"]
