#!/usr/bin/env python3

# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

"""OneMCP Sandbox service with proper lifespan event handling."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .mock_sandbox import MockSandbox
from .sandbox_api import DiscoverRequest, StartRequest, StopRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("onemcp.sandbox")

# Global sandbox instance
sandbox_instance = MockSandbox()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application lifespan events using modern FastAPI pattern.

    This replaces the deprecated startup/shutdown event decorators
    with the recommended lifespan approach.
    """
    # Startup logic
    logger.info("Starting OneMCP Sandbox service...")
    logger.info("Sandbox service initialized")

    yield  # Application runs here

    # Shutdown logic
    logger.info("Shutting down OneMCP Sandbox service...")
    # Clean up any running sandbox instances
    if hasattr(sandbox_instance, '_sandbox_instances'):
        logger.info(f"Cleaning up {len(sandbox_instance._sandbox_instances)} sandbox instances")
        sandbox_instance._sandbox_instances.clear()
    logger.info("Sandbox service shutdown complete")


# Create FastAPI app with lifespan context manager
app = FastAPI(
    title="OneMCP Sandbox Service",
    description="Dynamic MCP server sandbox management",
    version="0.1.0",
    lifespan=lifespan  # Use lifespan instead of deprecated event handlers
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "running", "service": "OneMCP Sandbox"}


@app.post("/discover")
async def discover(request: DiscoverRequest):
    """Discover MCP servers from a repository."""
    try:
        response = sandbox_instance.discover(request)
        return response
    except Exception as e:
        logger.error(f"Discovery error: {e}")
        return JSONResponse(
            status_code=500,
            content={"response_code": "ERROR", "error_description": str(e)}
        )


@app.post("/start")
async def start(request: StartRequest):
    """Start a sandbox instance."""
    try:
        response = sandbox_instance.start(request)
        return response
    except Exception as e:
        logger.error(f"Start error: {e}")
        return JSONResponse(
            status_code=500,
            content={"response_code": "ERROR", "error_description": str(e)}
        )


@app.post("/stop")
async def stop(request: StopRequest):
    """Stop a sandbox instance."""
    try:
        response = sandbox_instance.stop(request)
        return response
    except Exception as e:
        logger.error(f"Stop error: {e}")
        return JSONResponse(
            status_code=500,
            content={"response_code": "ERROR", "error_description": str(e)}
        )


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting OneMCP Sandbox service on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
