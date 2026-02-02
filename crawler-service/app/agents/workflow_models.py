"""
Workflow state models for the Config Generation Workflow.

Defines Pydantic models for:
- Workflow input parameters
- Workflow state (persisted across steps)
- Step outputs (passed between steps)
- Human-in-the-loop confirmation requests/responses

These models ensure type safety and clear contracts between workflow steps.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowPhase(str, Enum):
    """Workflow execution phases."""
    INITIAL = "initial"
    INVESTIGATING = "investigating"
    AWAITING_INVESTIGATION_CONFIRMATION = "awaiting_investigation_confirmation"
    GENERATING = "generating"
    AWAITING_CONFIG_CONFIRMATION = "awaiting_config_confirmation"
    VALIDATING = "validating"
    ITERATING = "iterating"
    COMPLETE = "complete"
    ERROR = "error"


class WorkflowInput(BaseModel):
    """
    Input parameters for the Config Generation Workflow.
    
    Contains all user-provided configuration for the workflow.
    """
    domain: str = Field(..., description="Target domain URL (e.g., 'https://example.com')")
    seed_urls: Optional[List[str]] = Field(default=None, description="Optional seed URLs for crawling")
    output_sink: str = Field(default="file", description="Output type: 'console', 'file', or 'elasticsearch'")
    output_index: Optional[str] = Field(default=None, description="Elasticsearch index name (for ES output)")
    output_dir: str = Field(default="/config/results/output", description="Output directory for file output")
    content_type: Optional[str] = Field(default=None, description="Content type: 'blog', 'ecommerce', 'docs', or auto-detect")
    content_focus: Optional[str] = Field(default=None, description="Focus area for crawl rules (e.g., '/blog/')")
    max_crawl_depth: int = Field(default=2, description="Maximum crawl depth")
    custom_fields: Optional[List[Dict[str, Any]]] = Field(default=None, description="Custom extraction fields")
    
    model_config = {"extra": "allow"}


class InvestigationResult(BaseModel):
    """
    Results from the site investigation step.
    
    Contains all findings from analyzing the target domain.
    """
    domain: str = Field(..., description="Investigated domain URL")
    domain_name: str = Field(..., description="Domain hostname")
    status: str = Field(..., description="Investigation status: 'completed', 'warning', or 'error'")
    
    robots_txt: Optional[Dict[str, Any]] = Field(default=None, description="Parsed robots.txt data")
    sitemaps: Optional[Dict[str, Any]] = Field(default=None, description="Discovered sitemaps info")
    page_fetch_summary: Optional[Dict[str, Any]] = Field(default=None, description="Page fetch statistics")
    page_structure_analysis: Optional[Dict[str, Any]] = Field(default=None, description="HTML pattern analysis")
    page_samples: Optional[List[Dict[str, Any]]] = Field(default=None, description="Sample page structures")
    recommendations: Optional[Dict[str, Any]] = Field(default=None, description="Crawl recommendations")
    llm_analysis: Optional[Dict[str, Any]] = Field(default=None, description="LLM-generated analysis")
    
    error: Optional[str] = Field(default=None, description="Error message if investigation failed")
    warning: Optional[str] = Field(default=None, description="Warning message if issues detected")
    
    model_config = {"extra": "allow"}


class ConfigGenerationResult(BaseModel):
    """
    Results from the config generation step.
    
    Contains the generated configuration and reasoning.
    """
    status: str = Field(..., description="Generation status: 'completed' or 'error'")
    domain: str = Field(..., description="Target domain")
    content_type: str = Field(..., description="Detected or specified content type")
    
    config: Optional[Dict[str, Any]] = Field(default=None, description="Generated config dictionary")
    yaml_content: Optional[str] = Field(default=None, description="YAML string for the config")
    reasoning: Optional[List[str]] = Field(default=None, description="Generation decisions and reasoning")
    sample_document: Optional[Dict[str, Any]] = Field(default=None, description="Example extracted document")
    validation: Optional[Dict[str, Any]] = Field(default=None, description="Initial validation results")
    llm_reasoning: Optional[Dict[str, Any]] = Field(default=None, description="LLM-generated reasoning")
    
    error: Optional[str] = Field(default=None, description="Error message if generation failed")
    
    model_config = {"extra": "allow"}


class ValidationResult(BaseModel):
    """
    Results from the config validation step.
    
    Contains validation findings and recommendations.
    """
    overall_status: str = Field(..., description="Validation status: 'pass', 'fail', or 'warning'")
    
    yaml_validation: Optional[Dict[str, Any]] = Field(default=None, description="YAML syntax validation")
    schema_validation: Optional[Dict[str, Any]] = Field(default=None, description="Schema validation results")
    extraction_test: Optional[Dict[str, Any]] = Field(default=None, description="Extraction rule test results")
    crawl_rule_test: Optional[Dict[str, Any]] = Field(default=None, description="Crawl rule test results")
    report: Optional[Dict[str, Any]] = Field(default=None, description="Comprehensive validation report")
    llm_analysis: Optional[Dict[str, Any]] = Field(default=None, description="LLM-generated analysis")
    
    errors: List[str] = Field(default_factory=list, description="List of validation errors")
    warnings: List[str] = Field(default_factory=list, description="List of validation warnings")
    
    model_config = {"extra": "allow"}


class ConfirmationType(str, Enum):
    """Types of confirmation requests."""
    INVESTIGATION_RESULTS = "investigation_results"
    CONFIG_PREVIEW = "config_preview"
    VALIDATION_FAILURE = "validation_failure"
    CRITICAL_ERROR = "critical_error"


class ConfirmationRequest(BaseModel):
    """
    Human-in-the-loop confirmation request.
    
    Sent when the workflow needs user confirmation to proceed.
    """
    confirmation_type: ConfirmationType = Field(..., description="Type of confirmation needed")
    title: str = Field(..., description="Title/summary of what needs confirmation")
    message: str = Field(..., description="Detailed message for the user")
    data: Dict[str, Any] = Field(default_factory=dict, description="Associated data for review")
    
    can_modify: bool = Field(default=True, description="Whether user can modify the data")
    can_abort: bool = Field(default=True, description="Whether user can abort the workflow")
    
    model_config = {"extra": "allow"}


class ConfirmationResponse(BaseModel):
    """
    Human-in-the-loop confirmation response.
    
    User's response to a confirmation request.
    """
    confirmed: bool = Field(..., description="Whether user confirmed/approved")
    abort: bool = Field(default=False, description="Whether user wants to abort workflow")
    modifications: Optional[Dict[str, Any]] = Field(default=None, description="User modifications to data")
    feedback: Optional[str] = Field(default=None, description="User feedback or notes")
    
    model_config = {"extra": "allow"}


class WorkflowState(BaseModel):
    """
    Complete workflow state, persisted across steps.
    
    This state is stored in the Agno session and allows:
    - Resuming workflows after interruption
    - Passing data between steps
    - Tracking progress and history
    """
    # Workflow metadata
    workflow_id: Optional[str] = Field(default=None, description="Unique workflow run ID")
    phase: WorkflowPhase = Field(default=WorkflowPhase.INITIAL, description="Current workflow phase")
    started_at: Optional[str] = Field(default=None, description="Workflow start timestamp")
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp")
    
    # Input parameters
    input: Optional[WorkflowInput] = Field(default=None, description="Original workflow input")
    
    # Step results
    investigation_result: Optional[InvestigationResult] = Field(default=None, description="Site investigation results")
    config_result: Optional[ConfigGenerationResult] = Field(default=None, description="Config generation results")
    validation_result: Optional[ValidationResult] = Field(default=None, description="Latest validation results")
    
    # Iteration tracking
    iteration_count: int = Field(default=0, description="Number of validation iterations")
    max_iterations: int = Field(default=3, description="Maximum validation iterations")
    iteration_history: List[Dict[str, Any]] = Field(default_factory=list, description="History of iterations")
    
    # Confirmation tracking
    pending_confirmation: Optional[ConfirmationRequest] = Field(default=None, description="Pending confirmation request")
    confirmation_responses: List[Dict[str, Any]] = Field(default_factory=list, description="History of user confirmations")
    
    # Final output
    final_config: Optional[Dict[str, Any]] = Field(default=None, description="Final validated config")
    final_yaml: Optional[str] = Field(default=None, description="Final YAML output")
    
    # Error tracking
    error: Optional[str] = Field(default=None, description="Error message if workflow failed")
    error_phase: Optional[WorkflowPhase] = Field(default=None, description="Phase where error occurred")
    
    model_config = {"extra": "allow"}
    
    def is_complete(self) -> bool:
        """Check if workflow has reached completion."""
        return self.phase in [WorkflowPhase.COMPLETE, WorkflowPhase.ERROR]
    
    def needs_confirmation(self) -> bool:
        """Check if workflow is waiting for user confirmation."""
        return self.pending_confirmation is not None
    
    def can_retry(self) -> bool:
        """Check if validation can be retried."""
        return self.iteration_count < self.max_iterations


class WorkflowResult(BaseModel):
    """
    Final workflow result returned to the caller.
    
    Contains the complete outcome of the workflow execution.
    """
    success: bool = Field(..., description="Whether workflow completed successfully")
    phase: WorkflowPhase = Field(..., description="Final workflow phase")
    
    # Final outputs (if successful)
    config: Optional[Dict[str, Any]] = Field(default=None, description="Final validated config")
    yaml_content: Optional[str] = Field(default=None, description="Final YAML content")
    sample_document: Optional[Dict[str, Any]] = Field(default=None, description="Sample extracted document")
    
    # Reports
    investigation_summary: Optional[Dict[str, Any]] = Field(default=None, description="Investigation summary")
    validation_summary: Optional[Dict[str, Any]] = Field(default=None, description="Validation summary")
    
    # Metadata
    iteration_count: int = Field(default=0, description="Total validation iterations")
    total_duration_seconds: Optional[float] = Field(default=None, description="Total workflow duration")
    
    # Errors (if failed)
    error: Optional[str] = Field(default=None, description="Error message if workflow failed")
    error_details: Optional[Dict[str, Any]] = Field(default=None, description="Detailed error information")
    
    # Confirmation state (for human-in-the-loop)
    pending_confirmation: Optional[ConfirmationRequest] = Field(default=None, description="Pending confirmation if paused")
    
    model_config = {"extra": "allow"}
