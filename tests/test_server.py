# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for the OneMCP server implementation."""

import pytest
from pydantic import AnyUrl

from src.onemcp.server import (
    handle_call_tool,
    handle_list_resources,
    handle_list_tools,
    handle_read_resource,
)


class TestResources:
    """Test resource handling functionality."""

    @pytest.mark.asyncio
    async def test_list_resources(self) -> None:
        """Test that resources are listed correctly."""
        resources = await handle_list_resources()

        assert len(resources) == 2

        # Check server info resource
        info_resource = next((r for r in resources if "info" in str(r.uri)), None)
        assert info_resource is not None
        assert info_resource.name == "Server Information"
        assert info_resource.mimeType == "application/json"

        # Check server status resource
        status_resource = next((r for r in resources if "status" in str(r.uri)), None)
        assert status_resource is not None
        assert status_resource.name == "Server Status"
        assert status_resource.mimeType == "application/json"

    @pytest.mark.asyncio
    async def test_read_server_info_resource(self) -> None:
        """Test reading the server info resource."""
        uri = AnyUrl("onemcp://server/info")
        content = await handle_read_resource(uri)

        assert "OneMCP Server" in content
        assert "0.1.0" in content
        assert "Pedro Henrique Penna" in content
        assert "capabilities" in content

    @pytest.mark.asyncio
    async def test_read_server_status_resource(self) -> None:
        """Test reading the server status resource."""
        uri = AnyUrl("onemcp://server/status")
        content = await handle_read_resource(uri)

        assert "running" in content
        assert "uptime" in content
        assert "memory_usage" in content
        assert "active_connections" in content

    @pytest.mark.asyncio
    async def test_read_invalid_resource(self) -> None:
        """Test reading an invalid resource raises an error."""
        uri = AnyUrl("onemcp://invalid/path")

        with pytest.raises(ValueError, match="Unknown resource path"):
            await handle_read_resource(uri)

    @pytest.mark.asyncio
    async def test_read_invalid_scheme(self) -> None:
        """Test reading a resource with invalid scheme raises an error."""
        uri = AnyUrl("http://example.com/resource")

        with pytest.raises(ValueError, match="Unsupported URI scheme"):
            await handle_read_resource(uri)


class TestTools:
    """Test tool handling functionality."""

    @pytest.mark.asyncio
    async def test_list_tools(self) -> None:
        """Test that tools are listed correctly."""
        tools = await handle_list_tools()

        assert len(tools) == 2

        tool_names = [tool.name for tool in tools]
        assert "say_hello" in tool_names
        assert "get_greeting" in tool_names

        # Check say_hello tool
        say_hello_tool = next((t for t in tools if t.name == "say_hello"), None)
        assert say_hello_tool is not None
        assert "name" in say_hello_tool.inputSchema["properties"]
        assert "language" in say_hello_tool.inputSchema["properties"]
        assert say_hello_tool.inputSchema["required"] == ["name"]

        # Check get_greeting tool
        get_greeting_tool = next((t for t in tools if t.name == "get_greeting"), None)
        assert get_greeting_tool is not None
        assert "formal" in get_greeting_tool.inputSchema["properties"]
        assert get_greeting_tool.inputSchema["required"] == []

    @pytest.mark.asyncio
    async def test_say_hello_english(self) -> None:
        """Test the say_hello tool with English greeting."""
        result = await handle_call_tool("say_hello", {"name": "Alice"})

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Hello, Alice!" in result[0].text
        assert "Welcome to OneMCP Server!" in result[0].text
        assert "hello world MCP server" in result[0].text

    @pytest.mark.asyncio
    async def test_say_hello_spanish(self) -> None:
        """Test the say_hello tool with Spanish greeting."""
        result = await handle_call_tool(
            "say_hello", {"name": "Carlos", "language": "spanish"}
        )

        assert len(result) == 1
        assert result[0].type == "text"
        assert "¡Hola, Carlos!" in result[0].text
        assert "¡Bienvenido al Servidor OneMCP!" in result[0].text

    @pytest.mark.asyncio
    async def test_say_hello_portuguese(self) -> None:
        """Test the say_hello tool with Portuguese greeting."""
        result = await handle_call_tool(
            "say_hello", {"name": "Maria", "language": "portuguese"}
        )

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Olá, Maria!" in result[0].text
        assert "Bem-vindo ao Servidor OneMCP!" in result[0].text

    @pytest.mark.asyncio
    async def test_say_hello_french(self) -> None:
        """Test the say_hello tool with French greeting."""
        result = await handle_call_tool(
            "say_hello", {"name": "Pierre", "language": "french"}
        )

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Bonjour, Pierre!" in result[0].text
        assert "Bienvenue sur le serveur OneMCP!" in result[0].text

    @pytest.mark.asyncio
    async def test_say_hello_invalid_language(self) -> None:
        """Test the say_hello tool with invalid language defaults to English."""
        result = await handle_call_tool(
            "say_hello", {"name": "Bob", "language": "klingon"}
        )

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Hello, Bob!" in result[0].text

    @pytest.mark.asyncio
    async def test_say_hello_no_arguments(self) -> None:
        """Test the say_hello tool with no arguments defaults to 'World'."""
        result = await handle_call_tool("say_hello", {})

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Hello, World!" in result[0].text

    @pytest.mark.asyncio
    async def test_get_greeting_informal(self) -> None:
        """Test the get_greeting tool with informal greeting."""
        result = await handle_call_tool("get_greeting", {"formal": False})

        assert len(result) == 1
        assert result[0].type == "text"
        assert "OneMCP server" in result[0].text
        assert "Formal mode: disabled" in result[0].text

    @pytest.mark.asyncio
    async def test_get_greeting_formal(self) -> None:
        """Test the get_greeting tool with formal greeting."""
        result = await handle_call_tool("get_greeting", {"formal": True})

        assert len(result) == 1
        assert result[0].type == "text"
        assert "OneMCP server" in result[0].text
        assert "Formal mode: enabled" in result[0].text

    @pytest.mark.asyncio
    async def test_get_greeting_no_arguments(self) -> None:
        """Test the get_greeting tool with no arguments defaults to informal."""
        result = await handle_call_tool("get_greeting", {})

        assert len(result) == 1
        assert result[0].type == "text"
        assert "OneMCP server" in result[0].text
        assert "Formal mode: disabled" in result[0].text

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self) -> None:
        """Test calling an unknown tool raises an error."""
        with pytest.raises(ValueError, match="Unknown tool"):
            await handle_call_tool("unknown_tool", {})

    @pytest.mark.asyncio
    async def test_call_tool_with_none_arguments(self) -> None:
        """Test calling a tool with None arguments works."""
        result = await handle_call_tool("say_hello", None)

        assert len(result) == 1
        assert result[0].type == "text"
        assert "Hello, World!" in result[0].text


class TestSignalHandling:
    """Test signal handling and graceful shutdown functionality."""

    def test_setup_signal_handlers(self) -> None:
        """Test that signal handlers can be set up without errors."""
        import signal

        from src.onemcp.server import setup_signal_handlers

        # Store original handlers
        original_sigint = signal.signal(signal.SIGINT, signal.SIG_DFL)
        original_sigterm = signal.signal(signal.SIGTERM, signal.SIG_DFL)

        try:
            # Test setting up signal handlers
            setup_signal_handlers()

            # Verify handlers were set
            current_sigint = signal.signal(signal.SIGINT, signal.SIG_DFL)
            current_sigterm = signal.signal(signal.SIGTERM, signal.SIG_DFL)

            assert current_sigint != signal.SIG_DFL
            assert current_sigterm != signal.SIG_DFL

        finally:
            # Restore original handlers
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)

    def test_signal_handler_sets_shutdown_event(self) -> None:
        """Test that signal handler sets the shutdown event."""
        import signal

        from src.onemcp.server import shutdown_event, signal_handler

        # Clear the shutdown event
        shutdown_event.clear()
        assert not shutdown_event.is_set()

        # Call signal handler
        signal_handler(signal.SIGINT, None)

        # Verify shutdown event is set
        assert shutdown_event.is_set()

        # Clear for cleanup
        shutdown_event.clear()

    @pytest.mark.asyncio
    async def test_monitor_stdin_eof_interactive(self) -> None:
        """Test stdin monitoring for interactive terminals."""
        import sys

        from src.onemcp.server import monitor_stdin_eof

        # Mock sys.stdin.isatty to return True
        original_isatty = sys.stdin.isatty
        sys.stdin.isatty = lambda: True

        try:
            # This should not raise an exception and should not complete immediately
            # We'll use a timeout to test this
            import asyncio

            try:
                await asyncio.wait_for(monitor_stdin_eof(), timeout=0.1)
                # If we get here, the function returned too quickly
                raise AssertionError(
                    "monitor_stdin_eof returned too quickly for interactive terminal"
                )
            except asyncio.TimeoutError:
                # This is expected for interactive terminals
                pass

        finally:
            sys.stdin.isatty = original_isatty
