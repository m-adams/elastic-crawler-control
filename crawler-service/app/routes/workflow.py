"""
Workflow API endpoints with SSE streaming for Agno-powered config generation.

Integrates the Agno Workflow with FastAPI and provides:
- POST /generate - Main endpoint for SSE streaming (per Agno best practices)
- POST /workflow/start - Alias to /generate for backward compatibility
- POST /workflow/{session_id}/confirm - Submit confirmation response (HITL)
- GET /workflow/{session_id}/status - Get current workflow status
- DELETE /workflow/{session_id} - Cancel/clear a session

IMPORTANT: This uses Agno's BUILT-IN streaming via workflow.arun(stream=True).
- Uses `workflow.arun(input=..., stream=True)` for SSE streaming
- Uses Agno's WorkflowRunOutputEvent objects directly (NO custom SSE formatting)
- Uses `session_id` parameter for session management
- Handles Agent-level HITL via `is_paused` and `continue_run()`

Example client usage:
    const response = await fetch('/api/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({domain: 'https://example.com'})
    });
    const reader = response.body.getReader();
    // Read SSE events from Agno's WorkflowRunOutputEvent...
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents.orchestration_workflow import (
    create_config_workflow,
    run_workflow,
    run_workflow_streaming,
)
from agents.workflow_state import (
    WorkflowPhase,
    WorkflowInput,
    WorkflowOutput,
    WorkflowSessionState,
    create_initial_session_state,
    build_workflow_output,
)

router = APIRouter(prefix="/api", tags=["workflow"])

# Session storage for workflow state and paused agents
# In production, use a database or Redis
_workflow_sessions: Dict[str, WorkflowSessionState] = {}
_paused_responses: Dict[str, Any] = {}  # Store paused Agent responses for HITL


# =============================================================================
# Request/Response Models
# =============================================================================

class GenerateRequest(BaseModel):
    """Request for POST /generate endpoint."""
    domain: str = Field(..., description="Target domain URL (e.g., 'https://example.com')")
    seed_urls: Optional[list[str]] = Field(default=None, description="Optional seed URLs for crawling")
    output_sink: str = Field(default="file", description="Output type: 'console', 'file', or 'elasticsearch'")
    output_index: Optional[str] = Field(default=None, description="Elasticsearch index name (for ES output)")
    output_dir: str = Field(default="/config/results/output", description="Output directory for file output")
    content_type: Optional[str] = Field(default=None, description="Content type: 'blog', 'ecommerce', 'docs', or auto-detect")
    content_focus: Optional[str] = Field(default=None, description="Focus area for crawl rules (e.g., '/blog/')")
    max_crawl_depth: int = Field(default=2, description="Maximum crawl depth")
    custom_fields: Optional[list[dict]] = Field(default=None, description="Custom extraction fields")
    session_id: Optional[str] = Field(default=None, description="Optional session ID (generated if not provided)")


class WorkflowStartRequest(BaseModel):
    """Request to start a new config generation workflow (backward compat)."""
    domain: str = Field(..., description="Target domain URL (e.g., 'https://example.com')")
    seed_urls: Optional[list[str]] = Field(default=None, description="Optional seed URLs for crawling")
    output_sink: str = Field(default="file", description="Output type: 'console', 'file', or 'elasticsearch'")
    output_index: Optional[str] = Field(default=None, description="Elasticsearch index name (for ES output)")
    output_dir: str = Field(default="/config/results/output", description="Output directory for file output")
    content_type: Optional[str] = Field(default=None, description="Content type: 'blog', 'ecommerce', 'docs', or auto-detect")
    content_focus: Optional[str] = Field(default=None, description="Focus area for crawl rules (e.g., '/blog/')")
    max_crawl_depth: int = Field(default=2, description="Maximum crawl depth")
    custom_fields: Optional[list[dict]] = Field(default=None, description="Custom extraction fields")


class ConfirmRequest(BaseModel):
    """Request to confirm or reject a HITL action."""
    confirmed: bool = Field(..., description="True to confirm, False to reject")
    requirement_id: Optional[str] = Field(default=None, description="Specific requirement ID to respond to")


class WorkflowStatusResponse(BaseModel):
    """Response containing current workflow status."""
    session_id: str
    phase: str
    phase_display: str
    is_complete: bool
    is_error: bool
    is_paused: bool = False  # Added for HITL support
    error: Optional[str] = None
    
    # Progress info
    investigation_complete: bool = False
    config_complete: bool = False
    validation_complete: bool = False
    iteration_count: int = 0
    
    # HITL info
    pending_confirmations: Optional[list[Dict[str, Any]]] = None
    
    # Final outputs (if complete)
    yaml_content: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


def session_to_status(session_id: str, session_state: WorkflowSessionState) -> WorkflowStatusResponse:
    """Convert session state to a WorkflowStatusResponse."""
    phase_display_map = {
        WorkflowPhase.INITIAL.value: "Initializing",
        WorkflowPhase.INVESTIGATING.value: "Investigating Site",
        WorkflowPhase.GENERATING.value: "Generating Config",
        WorkflowPhase.VALIDATING.value: "Validating Config",
        WorkflowPhase.ITERATING.value: "Fixing Validation Issues",
        WorkflowPhase.COMPLETE.value: "Complete",
        WorkflowPhase.ERROR.value: "Error",
    }
    
    phase = session_state.get("phase", WorkflowPhase.INITIAL.value)
    
    # Check for paused state (HITL)
    is_paused = session_id in _paused_responses
    pending_confirmations = None
    if is_paused:
        paused_response = _paused_responses.get(session_id)
        if paused_response and hasattr(paused_response, 'active_requirements'):
            pending_confirmations = [
                {
                    "id": str(i),
                    "needs_confirmation": getattr(req, 'needs_confirmation', True),
                    "description": str(req) if req else "Confirmation required"
                }
                for i, req in enumerate(paused_response.active_requirements)
            ]
    
    response = WorkflowStatusResponse(
        session_id=session_id,
        phase=phase,
        phase_display=phase_display_map.get(phase, str(phase)),
        is_complete=phase == WorkflowPhase.COMPLETE.value,
        is_error=phase == WorkflowPhase.ERROR.value,
        is_paused=is_paused,
        error=session_state.get("error"),
        iteration_count=session_state.get("iteration_count", 0),
        pending_confirmations=pending_confirmations,
    )
    
    # Progress tracking
    if session_state.get("investigation_result"):
        response.investigation_complete = True
    if session_state.get("config_result"):
        response.config_complete = True
    if session_state.get("validation_result"):
        response.validation_complete = True
    
    # Final outputs
    if phase == WorkflowPhase.COMPLETE.value:
        response.yaml_content = session_state.get("final_yaml")
        response.config = session_state.get("final_config")
    
    return response


# =============================================================================
# API Endpoints - Main /generate endpoint (Agno best practices)
# =============================================================================

@router.post("/generate")
async def generate(request: GenerateRequest):
    """
    Generate config with SSE streaming using Agno's built-in streaming.
    
    This is the main endpoint following Agno best practices:
    - Uses `workflow.arun(input=..., stream=True)` for streaming
    - Uses Agno's WorkflowRunOutputEvent objects directly (NO custom SSE formatting)
    - Uses `session_id` parameter for session management
    - Handles Agent-level HITL via `is_paused` and `continue_run()`
    
    Args:
        request: GenerateRequest with domain and optional parameters
        
    Returns:
        StreamingResponse with SSE events from Agno's WorkflowRunOutputEvent
        
    Example:
        ```python
        @app.post('/generate')
        async def generate(domain: str):
            async def stream():
                async for event in workflow.arun(input=domain, stream=True):
                    yield f'data: {event.model_dump_json()}\\n\\n'
            return StreamingResponse(stream(), media_type='text/event-stream')
        ```
    """
    # Use provided session_id or generate new one
    session_id = request.session_id or f"workflow-{uuid.uuid4().hex[:8]}"
    
    async def stream():
        """
        Stream workflow events using Agno's built-in streaming.
        
        IMPORTANT: Uses Agno's event objects directly with model_dump_json().
        NO custom SSE formatting - just Agno's WorkflowRunOutputEvent serialized.
        """
        try:
            # Create workflow input
            workflow_input = WorkflowInput(
                domain=request.domain,
                seed_urls=request.seed_urls,
                output_sink=request.output_sink,
                output_index=request.output_index,
                output_dir=request.output_dir,
                content_type=request.content_type,
                content_focus=request.content_focus,
                max_crawl_depth=request.max_crawl_depth,
                custom_fields=request.custom_fields,
            )
            
            # Create initial session state
            session_state = create_initial_session_state(workflow_input)
            _workflow_sessions[session_id] = session_state
            
            # Create workflow with session_id for state management
            workflow = create_config_workflow(
                session_state=session_state,
                stream=True,
            )
            
            # Stream workflow execution using Agno's built-in streaming
            # CRITICAL: Uses workflow.arun(stream=True) as per acceptance criteria
            async for event in workflow.arun(
                input=workflow_input.model_dump(),
                stream=True,
                session_id=session_id,  # Pass session_id for session management
            ):
                # Check for Agent-level HITL (is_paused and active_requirements)
                if hasattr(event, 'is_paused') and event.is_paused:
                    # Store paused response for later continuation
                    _paused_responses[session_id] = event
                    # Add paused info to event before yielding
                    event_dict = event.model_dump() if hasattr(event, 'model_dump') else {"paused": True}
                    event_dict["session_id"] = session_id
                    event_dict["is_paused"] = True
                    if hasattr(event, 'active_requirements'):
                        event_dict["active_requirements"] = [
                            str(req) for req in event.active_requirements
                        ]
                    yield f"data: {json.dumps(event_dict)}\n\n"
                else:
                    # Standard event - use Agno's model_dump_json() directly
                    # NO custom SSE formatting - just the data line
                    if hasattr(event, 'model_dump_json'):
                        yield f"data: {event.model_dump_json()}\n\n"
                    else:
                        # Fallback for non-Pydantic events
                        event_data = {
                            "session_id": session_id,
                            "content": str(event),
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                    
                    # Update session state from event if available
                    if hasattr(event, 'content') and isinstance(event.content, dict):
                        _workflow_sessions[session_id].update(event.content)
                
        except Exception as e:
            # Error handling via try/except yields error events
            error_event = {
                "session_id": session_id,
                "error": str(e),
                "type": "workflow_error",
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Session-Id": session_id,
        },
    )


# =============================================================================
# HITL Endpoints
# =============================================================================

@router.post("/workflow/{session_id}/confirm")
async def confirm_workflow(session_id: str, request: ConfirmRequest):
    """
    Submit a confirmation response for Agent-level HITL.
    
    When a workflow is paused (is_paused=True), the client must call this
    endpoint to confirm or reject the pending action before the workflow
    can continue.
    
    Args:
        session_id: The workflow session ID
        request: ConfirmRequest with confirmed=True/False
        
    Returns:
        StreamingResponse with continued workflow events
        
    Raises:
        HTTPException: If session not found or not paused
    """
    if session_id not in _paused_responses:
        raise HTTPException(
            status_code=404, 
            detail=f"No paused workflow found for session {session_id}"
        )
    
    paused_response = _paused_responses[session_id]
    
    async def continue_stream():
        """Continue the paused workflow after confirmation."""
        try:
            # Handle confirmation for each active requirement
            if hasattr(paused_response, 'active_requirements'):
                for req in paused_response.active_requirements:
                    if hasattr(req, 'needs_confirmation') and req.needs_confirmation:
                        if request.confirmed:
                            if hasattr(req, 'confirm'):
                                req.confirm()
                        else:
                            if hasattr(req, 'reject'):
                                req.reject()
            
            # Remove from paused state
            del _paused_responses[session_id]
            
            # Continue workflow execution via continue_run()
            if hasattr(paused_response, 'agent') and hasattr(paused_response.agent, 'continue_run'):
                async for event in paused_response.agent.continue_run(run_response=paused_response):
                    if hasattr(event, 'model_dump_json'):
                        yield f"data: {event.model_dump_json()}\n\n"
                    else:
                        yield f"data: {json.dumps({'content': str(event)})}\n\n"
            else:
                # If no continue_run available, just acknowledge
                yield f"data: {json.dumps({'confirmed': request.confirmed, 'session_id': session_id})}\n\n"
                
        except Exception as e:
            error_event = {"error": str(e), "session_id": session_id}
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        continue_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# =============================================================================
# Backward Compatibility - /workflow/start endpoint
# =============================================================================

@router.post("/workflow/start")
async def start_workflow(request: WorkflowStartRequest):
    """
    Start a new config generation workflow with SSE streaming.
    
    NOTE: This is a backward-compatible alias for POST /generate.
    Prefer using POST /generate for new implementations.
    
    Args:
        request: Workflow start parameters including domain, output settings, etc.
        
    Returns:
        StreamingResponse with SSE events
    """
    # Convert to GenerateRequest and delegate to /generate
    generate_request = GenerateRequest(
        domain=request.domain,
        seed_urls=request.seed_urls,
        output_sink=request.output_sink,
        output_index=request.output_index,
        output_dir=request.output_dir,
        content_type=request.content_type,
        content_focus=request.content_focus,
        max_crawl_depth=request.max_crawl_depth,
        custom_fields=request.custom_fields,
    )
    return await generate(generate_request)


@router.post("/workflow/start/sync")
async def start_workflow_sync(request: WorkflowStartRequest) -> WorkflowStatusResponse:
    """
    Start a new config generation workflow (non-streaming).
    
    This endpoint starts a workflow and waits for completion.
    Use this if you don't want SSE streaming.
    
    Args:
        request: Workflow start parameters
        
    Returns:
        WorkflowStatusResponse with final workflow state
    """
    session_id = f"workflow-{uuid.uuid4().hex[:8]}"
    
    try:
        output = await run_workflow(
            domain=request.domain,
            seed_urls=request.seed_urls,
            output_sink=request.output_sink,
            output_index=request.output_index,
            output_dir=request.output_dir,
            content_type=request.content_type,
            content_focus=request.content_focus,
            max_crawl_depth=request.max_crawl_depth,
            custom_fields=request.custom_fields,
        )
        
        return WorkflowStatusResponse(
            session_id=session_id,
            phase=output.phase.value,
            phase_display="Complete" if output.success else "Error",
            is_complete=output.success,
            is_error=not output.success,
            error=output.error,
            iteration_count=output.iteration_count,
            yaml_content=output.yaml_content,
            config=output.config,
            investigation_complete=output.investigation_summary is not None,
            config_complete=output.config is not None,
            validation_complete=output.validation_summary is not None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running workflow: {str(e)}")


@router.get("/workflow/{session_id}/status")
async def get_workflow_status(session_id: str) -> WorkflowStatusResponse:
    """
    Get the current status of a workflow session.
    
    Args:
        session_id: The workflow session ID
        
    Returns:
        WorkflowStatusResponse with current state
        
    Raises:
        HTTPException: If session not found
    """
    session_state = _workflow_sessions.get(session_id)
    if session_state is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    return session_to_status(session_id, session_state)


@router.delete("/workflow/{session_id}")
async def cancel_workflow(session_id: str):
    """
    Cancel and clear a workflow session.
    
    Args:
        session_id: The workflow session ID
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If session not found
    """
    if session_id not in _workflow_sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    del _workflow_sessions[session_id]
    # Also clear any paused responses
    if session_id in _paused_responses:
        del _paused_responses[session_id]
    return {"message": f"Session {session_id} cancelled and cleared"}


@router.get("/workflow/sessions")
async def list_sessions():
    """
    List all active workflow sessions.
    
    Returns:
        List of session summaries
    """
    sessions = []
    for session_id, state in _workflow_sessions.items():
        sessions.append({
            "session_id": session_id,
            "phase": state.get("phase", "unknown"),
            "domain": state.get("domain"),
            "is_complete": state.get("phase") == WorkflowPhase.COMPLETE.value,
            "is_paused": session_id in _paused_responses,
        })
    
    return {
        "sessions": sessions,
        "total": len(sessions),
    }
