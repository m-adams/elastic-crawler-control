"""
Workflow state models for the Agno-powered Config Generation Workflow.

Defines minimal models for workflow state management with Agno's session_state.
These models are designed to work with Agno's Workflow class.

Note: Agno handles most state management internally via session_state parameter.
These models provide type hints and structured data for the API layer.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowPhase(str, Enum):
    """Workflow execution phases for UI display."""
    INITIAL = "initial"
    INVESTIGATING = "investigating"
    GENERATING = "generating"
    VALIDATING = "validating"
    ITERATING = "iterating"
    COMPLETE = "complete"
    ERROR = "error"


class WorkflowInput(BaseModel):
    """
    Input parameters for the Config Generation Workflow.
    
    Passed to workflow.run() or workflow.arun().
    """
    domain: str = Field(..., description="Target domain URL")
    seed_urls: Optional[List[str]] = Field(default=None, description="Optional seed URLs")
    output_sink: str = Field(default="file", description="Output type")
    output_index: Optional[str] = Field(default=None, description="ES index name")
    output_dir: str = Field(default="/config/results/output", description="Output directory")
    content_type: Optional[str] = Field(default=None, description="Content type hint")
    content_focus: Optional[str] = Field(default=None, description="Focus area for crawl rules")
    max_crawl_depth: int = Field(default=2, description="Maximum crawl depth")
    custom_fields: Optional[List[Dict[str, Any]]] = Field(default=None, description="Custom extraction fields")
    # User context and LLM configuration
    user_context: Optional[str] = Field(default=None, description="Free-text description of user goals/use case")
    llm_api_key: Optional[str] = Field(default=None, description="LLM Proxy API key")
    
    model_config = {"extra": "allow"}


class WorkflowOutput(BaseModel):
    """
    Output from the Config Generation Workflow.
    
    Returned from workflow.run() or workflow.arun().
    """
    success: bool = Field(..., description="Whether workflow completed successfully")
    phase: WorkflowPhase = Field(default=WorkflowPhase.COMPLETE, description="Final phase")
    
    # Results
    config: Optional[Dict[str, Any]] = Field(default=None, description="Final config dictionary")
    yaml_content: Optional[str] = Field(default=None, description="Final YAML content")
    
    # Summaries
    investigation_summary: Optional[Dict[str, Any]] = Field(default=None)
    validation_summary: Optional[Dict[str, Any]] = Field(default=None)
    
    # Metadata
    iteration_count: int = Field(default=0, description="Validation iterations")
    
    # Errors
    error: Optional[str] = Field(default=None, description="Error message if failed")
    
    model_config = {"extra": "allow"}


# Type alias for session state dictionary
# This is what gets passed to Workflow(session_state={...})
WorkflowSessionState = Dict[str, Any]


def create_initial_session_state(workflow_input: WorkflowInput) -> WorkflowSessionState:
    """
    Create the initial session state for a workflow run.
    
    Args:
        workflow_input: The workflow input parameters
        
    Returns:
        Initial session state dictionary
    """
    return {
        # Input parameters
        "domain": workflow_input.domain,
        "seed_urls": workflow_input.seed_urls,
        "output_sink": workflow_input.output_sink,
        "output_index": workflow_input.output_index,
        "output_dir": workflow_input.output_dir,
        "content_type": workflow_input.content_type,
        "content_focus": workflow_input.content_focus,
        "max_crawl_depth": workflow_input.max_crawl_depth,
        "custom_fields": workflow_input.custom_fields,
        "user_context": workflow_input.user_context,  # User's goals/use case
        
        # Phase tracking
        "phase": WorkflowPhase.INITIAL.value,
        
        # Step results (populated as workflow progresses)
        "investigation_result": None,
        "config_result": None,
        "validation_result": None,
        
        # Iteration tracking
        "iteration_count": 0,
        "max_iterations": 3,
        
        # Final outputs
        "final_config": None,
        "final_yaml": None,
        
        # Error tracking
        "error": None,
    }


def build_workflow_output(session_state: WorkflowSessionState) -> WorkflowOutput:
    """
    Build a WorkflowOutput from session state.
    
    Args:
        session_state: The workflow session state
        
    Returns:
        WorkflowOutput model
    """
    phase = session_state.get("phase", WorkflowPhase.ERROR.value)
    is_complete = phase == WorkflowPhase.COMPLETE.value
    has_error = session_state.get("error") is not None
    
    return WorkflowOutput(
        success=is_complete and not has_error,
        phase=WorkflowPhase(phase) if phase in [p.value for p in WorkflowPhase] else WorkflowPhase.ERROR,
        config=session_state.get("final_config"),
        yaml_content=session_state.get("final_yaml"),
        investigation_summary=_get_investigation_summary(session_state),
        validation_summary=_get_validation_summary(session_state),
        iteration_count=session_state.get("iteration_count", 0),
        error=session_state.get("error"),
    )


def _get_investigation_summary(session_state: WorkflowSessionState) -> Optional[Dict[str, Any]]:
    """Extract investigation summary from session state."""
    result = session_state.get("investigation_result")
    if not result:
        return None
    return {
        "domain": result.get("domain"),
        "status": result.get("status"),
        "pages_analyzed": result.get("page_fetch_summary", {}).get("successful", 0),
    }


def _get_validation_summary(session_state: WorkflowSessionState) -> Optional[Dict[str, Any]]:
    """Extract validation summary from session state."""
    result = session_state.get("validation_result")
    if not result:
        return None
    report = result.get("report", {})
    return {
        "status": result.get("overall_status"),
        "errors": len(report.get("all_errors", [])),
        "warnings": len(report.get("all_warnings", [])),
    }
