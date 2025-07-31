# FastAPI Lifespan Events Migration Guide

This document shows how to migrate from deprecated `@app.on_event` decorators to the modern lifespan pattern in FastAPI.

## ❌ Deprecated Pattern (DO NOT USE)

```python
from fastapi import FastAPI

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """This pattern is deprecated and should be avoided."""
    print("Starting up...")

@app.on_event("shutdown")
async def shutdown_event():
    """This pattern is deprecated and should be avoided."""
    print("Shutting down...")
```

## ✅ Modern Pattern (RECOMMENDED)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifespan events using modern pattern."""
    # Startup logic
    print("Starting up...")
    
    yield  # Application runs here
    
    # Shutdown logic
    print("Shutting down...")

app = FastAPI(lifespan=lifespan)
```

## Benefits of the Modern Pattern

1. **Better resource management**: The context manager ensures proper cleanup
2. **Error handling**: Exceptions in startup/shutdown are handled more gracefully
3. **Type safety**: Better type checking support
4. **Future-proof**: Follows FastAPI's recommended patterns

## Implementation in OneMCP Sandbox

The OneMCP sandbox service (`src/onemcp/sandboxing/__main__.py`) implements the modern lifespan pattern to:

- Initialize sandbox resources on startup
- Clean up running sandbox instances on shutdown
- Provide proper logging for lifecycle events

See the implementation for a complete example of the recommended pattern.