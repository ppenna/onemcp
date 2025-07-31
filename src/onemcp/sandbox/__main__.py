# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

"""HTTP API wrapper for the Docker Sandbox implementation."""

import json
import logging
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request

from src.onemcp.sandbox.docker_sandbox_registry import DockerSandboxRegistry

logger = logging.getLogger(__name__)

app = FastAPI(title="OneMCP Sandbox API", version="1.0.0")

# Global sandbox instance
sandbox = DockerSandboxRegistry()


class SandboxAPI:
    """HTTP API wrapper for the Docker Sandbox."""

    def __init__(self, sandbox_instance: DockerSandboxRegistry):
        self.sandbox = sandbox_instance


@app.post("/sandbox")
async def sandbox_endpoint(
    request: Request,
    x_onemcp_message_type: str = Header(..., alias="X-OneMCP-Message-Type"),
) -> dict[str, Any]:
    """Main sandbox endpoint that handles all operations based on message type.

    Supported message types:
    - DISCOVER: Discover MCP server capabilities
    - START: Start a sandbox instance
    - STOP: Stop a sandbox instance
    """
    try:
        body = await request.json()

        if x_onemcp_message_type == "DISCOVER":
            return await handle_discover(body)
        elif x_onemcp_message_type == "START":
            return await handle_start(body)
        elif x_onemcp_message_type == "STOP":
            return await handle_stop(body)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported message type: {x_onemcp_message_type}",
            )

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400, detail="Invalid JSON in request body"
        ) from e
    except Exception as e:
        logger.error(f"Sandbox API error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


async def handle_discover(body: dict[str, Any]) -> dict[str, Any]:
    """Handle DISCOVER message type.

    Expected payload:
    {
        "repository_url": "<URL>"
    }
    """
    if "repository_url" not in body:
        return {
            "response_code": "400",
            "error_description": "Missing required field: repository_url",
        }

    repository_url = body["repository_url"]
    result = await sandbox.discover(repository_url)

    return result


async def handle_start(body: dict[str, Any]) -> dict[str, Any]:
    """Handle START message type.

    Expected payload:
    {
        "bootstrap_metadata": {...}
    }
    """
    if "bootstrap_metadata" not in body:
        return {
            "response_code": "400",
            "error_description": "Missing required field: bootstrap_metadata",
        }

    bootstrap_metadata = body["bootstrap_metadata"]
    result = await sandbox.start(bootstrap_metadata)

    return result


async def handle_stop(body: dict[str, Any]) -> dict[str, Any]:
    """Handle STOP message type.

    Expected payload:
    {
        "sandbox_id": "..."
    }
    """
    if "sandbox_id" not in body:
        return {
            "response_code": "400",
            "error_description": "Missing required field: sandbox_id",
        }

    sandbox_id = body["sandbox_id"]
    result = await sandbox.stop(sandbox_id)

    return result


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "OneMCP Sandbox API"}


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up resources on shutdown."""
    logger.info("Shutting down sandbox API, cleaning up instances...")
    await sandbox.cleanup_all()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    return app


def run_server(
    host: str = "0.0.0.0", port: int = 8080, log_level: str = "info"
) -> None:
    """Run the sandbox API server.

    Args:
        host: Host to bind the server to
        port: Port to bind the server to
        log_level: Logging level
    """
    logger.info(f"Starting OneMCP Sandbox API server on {host}:{port}")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
        reload=False,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OneMCP Sandbox API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--log-level", default="info", help="Log level")

    args = parser.parse_args()
    run_server(args.host, args.port, args.log_level)
