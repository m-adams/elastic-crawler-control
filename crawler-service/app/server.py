"""
Elastic Crawler Service - FastAPI Application.

This service provides:
1. Crawl Management - Trigger, monitor, and manage Open Crawler jobs
2. Config Generation - LLM-powered crawler configuration generation (optional)

The application uses a modular route structure:
- routes/crawl.py - Crawl job management endpoints
- routes/health.py - Health check endpoint
- routes/chat.py - LLM-powered config generation (requires LLM_PROXY_API_KEY)
"""

import os
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import modular routes
from routes import crawl, health, chat, workflow
from utils.config import config

# Validate configuration on startup
validation_errors = config.validate()
if validation_errors:
    print("⚠️  Configuration warnings:")
    for error in validation_errors:
        print(f"   - {error}")
    print("\nSome features may not work correctly without proper configuration.\n")

# Create FastAPI app
app = FastAPI(
    title="Elastic Crawler Service",
    description="Web crawler service with LLM-powered config generation and Agno workflow API",
    version="1.2.0",  # Bumped for Agno workflow API with SSE streaming
)

# CORS middleware (adjust origins as needed for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health.router)
app.include_router(crawl.router)
app.include_router(chat.router)
app.include_router(workflow.router)


@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint with service information."""
    return {
        "service": "Elastic Crawler Service",
        "version": "1.3.0",  # Bumped for Agno SSE streaming with /generate endpoint
        "status": "running",
        "features": {
            "crawl_management": True,
            "config_generation": config.llm_enabled(),
            "workflow_api": True,  # Agno-powered workflow with SSE
            "sse_streaming": True,  # Uses Agno's built-in SSE streaming
        },
        "endpoints": {
            "health": "/api/health",
            "crawl": "/api/crawl",
            "chat": "/api/chat" if config.llm_enabled() else "disabled",
            "chat_status": "/api/chat/status",
            # Workflow API (Agno-powered with SSE streaming)
            "generate": "/api/generate",  # Main SSE streaming endpoint
            "workflow_start": "/api/workflow/start",  # Backward compat alias
            "workflow_start_sync": "/api/workflow/start/sync",
            "workflow_confirm": "/api/workflow/{session_id}/confirm",
            "workflow_status": "/api/workflow/{session_id}/status",
            "workflow_sessions": "/api/workflow/sessions",
        },
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        reload=config.ENVIRONMENT == "development",
    )
