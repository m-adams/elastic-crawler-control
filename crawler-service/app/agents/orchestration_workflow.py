"""
Config Generation Orchestration Workflow (Agno-powered).

Orchestrates the complete config generation pipeline:
1. Site Investigation → 2. User Confirmation → 3. Config Generation →
4. User Confirmation → 5. Validation → 6. Iteration Loop (if needed)

Uses Agno's Workflow class with:
- Steps for each phase
- Loop for validation retries (max 3 iterations)
- Session state for persistence across steps
- Human-in-the-loop confirmation points

This module provides:
- ConfigGenerationWorkflow: Main workflow class
- create_config_workflow(): Factory function for creating workflows

Example:
    >>> workflow = create_config_workflow()
    >>> result = await workflow.arun(
    ...     input={"domain": "https://example.com"},
    ...     session_id="user-session-123",
    ... )
    >>> if result.output.pending_confirmation:
    ...     # Handle human-in-the-loop
    ...     pass
    >>> else:
    ...     print(result.output.yaml_content)
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Iterator, Optional, Union

from agno.workflow import Workflow, Step, Loop, StepInput, StepOutput

from agents.site_investigation import SiteInvestigationAgent
from agents.config_generation import ConfigGenerationAgent
from agents.config_validation import ConfigValidationAgent
from agents.workflow_models import (
    WorkflowInput,
    WorkflowState,
    WorkflowPhase,
    WorkflowResult,
    InvestigationResult,
    ConfigGenerationResult,
    ValidationResult,
    ConfirmationType,
    ConfirmationRequest,
    ConfirmationResponse,
)
from utils.agno_model import is_agno_available


# Maximum validation retry iterations
MAX_VALIDATION_ITERATIONS = 3


class ConfigGenerationWorkflow:
    """
    Orchestration workflow for Open Crawler config generation.
    
    This class wraps an Agno Workflow and provides the complete config
    generation pipeline with human-in-the-loop confirmation points.
    
    The workflow maintains state across executions, allowing:
    - Pausing for user confirmation
    - Resuming from checkpoints
    - Tracking iteration history
    
    Workflow phases:
    1. INITIAL: Waiting for input
    2. INVESTIGATING: Site investigation in progress
    3. AWAITING_INVESTIGATION_CONFIRMATION: User review of recommendations
    4. GENERATING: Config generation in progress
    5. AWAITING_CONFIG_CONFIRMATION: User review of draft config
    6. VALIDATING: Config validation in progress
    7. ITERATING: Fixing validation issues (max 3 iterations)
    8. COMPLETE: Final config ready
    9. ERROR: Critical failure
    
    Example:
        >>> orchestrator = ConfigGenerationWorkflow()
        >>> 
        >>> # Start workflow
        >>> result = await orchestrator.start(
        ...     domain="https://example.com",
        ...     output_sink="file",
        ... )
        >>> 
        >>> # Check if confirmation needed
        >>> if result.pending_confirmation:
        ...     # Show confirmation UI, get response
        ...     response = ConfirmationResponse(confirmed=True)
        ...     result = await orchestrator.continue_with_confirmation(
        ...         session_id=result.session_id,
        ...         confirmation=response,
        ...     )
        >>> 
        >>> # Final config ready
        >>> print(result.yaml_content)
    """
    
    def __init__(
        self,
        debug_mode: bool = False,
        use_agno_llm: bool = True,
    ):
        """
        Initialize the orchestration workflow.
        
        Args:
            debug_mode: Enable debug output for agents
            use_agno_llm: Use Agno LLM features (requires API key)
        """
        self.debug_mode = debug_mode
        self.use_agno_llm = use_agno_llm and is_agno_available()
        
        # Initialize agents (lazy loading)
        self._investigation_agent: Optional[SiteInvestigationAgent] = None
        self._generation_agent: Optional[ConfigGenerationAgent] = None
        self._validation_agent: Optional[ConfigValidationAgent] = None
        
        # State storage for sessions (in-memory for now)
        # In production, this would use a database
        self._sessions: Dict[str, WorkflowState] = {}
    
    @property
    def investigation_agent(self) -> SiteInvestigationAgent:
        """Get or create the site investigation agent."""
        if self._investigation_agent is None:
            self._investigation_agent = SiteInvestigationAgent(
                sample_page_count=10,
                rate_limit_delay=1.0,
                use_agno=self.use_agno_llm,
                debug_mode=self.debug_mode,
            )
        return self._investigation_agent
    
    @property
    def generation_agent(self) -> ConfigGenerationAgent:
        """Get or create the config generation agent."""
        if self._generation_agent is None:
            self._generation_agent = ConfigGenerationAgent(
                use_agno=self.use_agno_llm,
                debug_mode=self.debug_mode,
            )
        return self._generation_agent
    
    @property
    def validation_agent(self) -> ConfigValidationAgent:
        """Get or create the config validation agent."""
        if self._validation_agent is None:
            self._validation_agent = ConfigValidationAgent(
                use_agno=self.use_agno_llm,
                debug_mode=self.debug_mode,
            )
        return self._validation_agent
    
    def _get_or_create_state(self, session_id: str) -> WorkflowState:
        """Get existing state or create new one for session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = WorkflowState(
                workflow_id=session_id,
                started_at=datetime.utcnow().isoformat(),
            )
        return self._sessions[session_id]
    
    def _update_state(self, session_id: str, state: WorkflowState) -> None:
        """Update state for session."""
        state.updated_at = datetime.utcnow().isoformat()
        self._sessions[session_id] = state
    
    async def start(
        self,
        domain: str,
        seed_urls: Optional[list[str]] = None,
        output_sink: str = "file",
        output_index: Optional[str] = None,
        output_dir: str = "/config/results/output",
        content_type: Optional[str] = None,
        content_focus: Optional[str] = None,
        max_crawl_depth: int = 2,
        custom_fields: Optional[list[dict]] = None,
        session_id: Optional[str] = None,
    ) -> WorkflowResult:
        """
        Start a new config generation workflow.
        
        This initiates the workflow from the beginning, running through
        the investigation phase and pausing for user confirmation.
        
        Args:
            domain: Target domain URL
            seed_urls: Optional seed URLs for crawling
            output_sink: Output type ('console', 'file', or 'elasticsearch')
            output_index: Elasticsearch index name (for ES output)
            output_dir: Output directory for file output
            content_type: Content type ('blog', 'ecommerce', 'docs', or auto)
            content_focus: Focus area for crawl rules
            max_crawl_depth: Maximum crawl depth
            custom_fields: Custom extraction fields
            session_id: Session ID (auto-generated if not provided)
            
        Returns:
            WorkflowResult with current state, may include pending_confirmation
        """
        # Generate session ID if not provided
        if session_id is None:
            session_id = f"workflow-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        
        # Create workflow input
        workflow_input = WorkflowInput(
            domain=domain,
            seed_urls=seed_urls,
            output_sink=output_sink,
            output_index=output_index,
            output_dir=output_dir,
            content_type=content_type,
            content_focus=content_focus,
            max_crawl_depth=max_crawl_depth,
            custom_fields=custom_fields,
        )
        
        # Initialize state
        state = self._get_or_create_state(session_id)
        state.input = workflow_input
        state.phase = WorkflowPhase.INVESTIGATING
        self._update_state(session_id, state)
        
        # Run investigation phase
        return await self._run_investigation(session_id)
    
    async def continue_workflow(
        self,
        session_id: str,
        confirmation: Optional[ConfirmationResponse] = None,
    ) -> WorkflowResult:
        """
        Continue a paused workflow with optional confirmation response.
        
        Call this after the user has responded to a confirmation request.
        
        Args:
            session_id: Session ID from previous result
            confirmation: User's confirmation response (required if pending)
            
        Returns:
            WorkflowResult with updated state, may include new pending_confirmation
        """
        state = self._get_or_create_state(session_id)
        
        # Check if we're waiting for confirmation
        if state.needs_confirmation():
            if confirmation is None:
                # Return current state with pending confirmation
                return self._build_result(state, session_id)
            
            # Process confirmation response
            if confirmation.abort:
                state.phase = WorkflowPhase.ERROR
                state.error = "Workflow aborted by user"
                state.pending_confirmation = None
                self._update_state(session_id, state)
                return self._build_result(state, session_id)
            
            if not confirmation.confirmed:
                # User rejected, return to appropriate phase for modifications
                return await self._handle_rejection(session_id, state, confirmation)
            
            # Store confirmation response
            state.confirmation_responses.append({
                "type": state.pending_confirmation.confirmation_type.value,
                "confirmed": confirmation.confirmed,
                "modifications": confirmation.modifications,
                "feedback": confirmation.feedback,
                "timestamp": datetime.utcnow().isoformat(),
            })
            
            # Apply any modifications
            if confirmation.modifications:
                await self._apply_modifications(state, confirmation.modifications)
            
            # Clear pending confirmation
            confirmation_type = state.pending_confirmation.confirmation_type
            state.pending_confirmation = None
            self._update_state(session_id, state)
            
            # Continue to next phase based on confirmation type
            if confirmation_type == ConfirmationType.INVESTIGATION_RESULTS:
                return await self._run_generation(session_id)
            elif confirmation_type == ConfirmationType.CONFIG_PREVIEW:
                return await self._run_validation(session_id)
            elif confirmation_type == ConfirmationType.VALIDATION_FAILURE:
                return await self._run_iteration(session_id)
        
        # No pending confirmation, continue from current phase
        if state.phase == WorkflowPhase.INITIAL:
            return self._build_result(state, session_id, 
                error="Workflow not started. Call start() first.")
        elif state.phase == WorkflowPhase.INVESTIGATING:
            return await self._run_investigation(session_id)
        elif state.phase == WorkflowPhase.GENERATING:
            return await self._run_generation(session_id)
        elif state.phase == WorkflowPhase.VALIDATING:
            return await self._run_validation(session_id)
        elif state.phase == WorkflowPhase.ITERATING:
            return await self._run_iteration(session_id)
        elif state.phase == WorkflowPhase.COMPLETE:
            return self._build_result(state, session_id)
        elif state.phase == WorkflowPhase.ERROR:
            return self._build_result(state, session_id)
        else:
            return self._build_result(state, session_id,
                error=f"Unknown workflow phase: {state.phase}")
    
    async def _run_investigation(self, session_id: str) -> WorkflowResult:
        """
        Execute the site investigation step.
        
        Investigates the target domain and pauses for user confirmation.
        """
        state = self._get_or_create_state(session_id)
        state.phase = WorkflowPhase.INVESTIGATING
        self._update_state(session_id, state)
        
        try:
            print(f"[Workflow] Starting investigation for {state.input.domain}...")
            
            # Run investigation
            result = await self.investigation_agent.investigate(
                domain=state.input.domain,
                seed_urls=state.input.seed_urls,
            )
            
            # Store investigation result
            state.investigation_result = InvestigationResult(**result)
            
            # Check for critical errors
            if result.get("status") == "error":
                state.phase = WorkflowPhase.ERROR
                state.error = result.get("error", "Investigation failed")
                state.error_phase = WorkflowPhase.INVESTIGATING
                self._update_state(session_id, state)
                return self._build_result(state, session_id)
            
            # Pause for user confirmation
            state.phase = WorkflowPhase.AWAITING_INVESTIGATION_CONFIRMATION
            state.pending_confirmation = ConfirmationRequest(
                confirmation_type=ConfirmationType.INVESTIGATION_RESULTS,
                title="Site Investigation Complete",
                message="Please review the investigation results and recommendations before proceeding to config generation.",
                data={
                    "domain": result.get("domain"),
                    "status": result.get("status"),
                    "robots_txt": result.get("robots_txt"),
                    "sitemaps": result.get("sitemaps"),
                    "page_fetch_summary": result.get("page_fetch_summary"),
                    "page_structure_analysis": result.get("page_structure_analysis"),
                    "recommendations": result.get("recommendations"),
                    "llm_analysis": result.get("llm_analysis"),
                },
                can_modify=True,
                can_abort=True,
            )
            self._update_state(session_id, state)
            
            print(f"[Workflow] Investigation complete. Waiting for user confirmation.")
            return self._build_result(state, session_id)
            
        except Exception as e:
            state.phase = WorkflowPhase.ERROR
            state.error = f"Investigation error: {str(e)}"
            state.error_phase = WorkflowPhase.INVESTIGATING
            self._update_state(session_id, state)
            return self._build_result(state, session_id)
    
    async def _run_generation(self, session_id: str) -> WorkflowResult:
        """
        Execute the config generation step.
        
        Generates config based on investigation results and pauses for confirmation.
        """
        state = self._get_or_create_state(session_id)
        state.phase = WorkflowPhase.GENERATING
        self._update_state(session_id, state)
        
        try:
            print(f"[Workflow] Starting config generation for {state.input.domain}...")
            
            # Convert investigation result to dict for generation
            site_analysis = state.investigation_result.model_dump() if state.investigation_result else {}
            
            # Run generation
            result = self.generation_agent.generate(
                site_analysis=site_analysis,
                output_sink=state.input.output_sink,
                output_index=state.input.output_index,
                output_dir=state.input.output_dir,
                content_type=state.input.content_type,
                content_focus=state.input.content_focus,
                max_crawl_depth=state.input.max_crawl_depth,
                custom_fields=state.input.custom_fields,
            )
            
            # Store generation result
            state.config_result = ConfigGenerationResult(**result)
            
            # Check for errors
            if result.get("status") == "error":
                state.phase = WorkflowPhase.ERROR
                state.error = result.get("error", "Config generation failed")
                state.error_phase = WorkflowPhase.GENERATING
                self._update_state(session_id, state)
                return self._build_result(state, session_id)
            
            # Pause for user confirmation
            state.phase = WorkflowPhase.AWAITING_CONFIG_CONFIRMATION
            state.pending_confirmation = ConfirmationRequest(
                confirmation_type=ConfirmationType.CONFIG_PREVIEW,
                title="Config Generation Complete",
                message="Please review the generated configuration and sample document preview before validation.",
                data={
                    "domain": result.get("domain"),
                    "content_type": result.get("content_type"),
                    "yaml_content": result.get("yaml_content"),
                    "config": result.get("config"),
                    "reasoning": result.get("reasoning"),
                    "sample_document": result.get("sample_document"),
                    "validation": result.get("validation"),
                },
                can_modify=True,
                can_abort=True,
            )
            self._update_state(session_id, state)
            
            print(f"[Workflow] Config generation complete. Waiting for user confirmation.")
            return self._build_result(state, session_id)
            
        except Exception as e:
            state.phase = WorkflowPhase.ERROR
            state.error = f"Config generation error: {str(e)}"
            state.error_phase = WorkflowPhase.GENERATING
            self._update_state(session_id, state)
            return self._build_result(state, session_id)
    
    async def _run_validation(self, session_id: str) -> WorkflowResult:
        """
        Execute the config validation step.
        
        Validates the generated config and either completes or enters iteration loop.
        """
        state = self._get_or_create_state(session_id)
        state.phase = WorkflowPhase.VALIDATING
        self._update_state(session_id, state)
        
        try:
            print(f"[Workflow] Starting config validation...")
            
            # Get config to validate
            config = state.config_result.config if state.config_result else None
            if config is None:
                state.phase = WorkflowPhase.ERROR
                state.error = "No config to validate"
                state.error_phase = WorkflowPhase.VALIDATING
                self._update_state(session_id, state)
                return self._build_result(state, session_id)
            
            # Run validation
            result = await self.validation_agent.validate(
                config_input=config,
                fetch_sample_pages=True,
                max_pages_to_fetch=5,
            )
            
            # Store validation result
            state.validation_result = ValidationResult(
                overall_status=result.get("overall_status", "fail"),
                yaml_validation=result.get("yaml_validation"),
                schema_validation=result.get("schema_validation"),
                extraction_test=result.get("extraction_test"),
                crawl_rule_test=result.get("crawl_rule_test"),
                report=result.get("report"),
                llm_analysis=result.get("llm_analysis"),
                errors=result.get("report", {}).get("all_errors", []),
                warnings=result.get("report", {}).get("all_warnings", []),
            )
            
            # Check validation result
            if result.get("overall_status") == "pass":
                # Success! Complete the workflow
                return await self._complete_workflow(session_id)
            
            elif result.get("overall_status") == "warning":
                # Warnings only - complete with warnings
                return await self._complete_workflow(session_id, with_warnings=True)
            
            else:
                # Validation failed - check if we can retry
                if state.can_retry():
                    # Enter iteration loop
                    state.iteration_count += 1
                    state.iteration_history.append({
                        "iteration": state.iteration_count,
                        "timestamp": datetime.utcnow().isoformat(),
                        "errors": state.validation_result.errors,
                        "warnings": state.validation_result.warnings,
                    })
                    
                    # Pause for user confirmation before retrying
                    state.phase = WorkflowPhase.ITERATING
                    state.pending_confirmation = ConfirmationRequest(
                        confirmation_type=ConfirmationType.VALIDATION_FAILURE,
                        title=f"Validation Failed (Attempt {state.iteration_count}/{state.max_iterations})",
                        message="Validation found issues. Review the errors and confirm to auto-fix and retry.",
                        data={
                            "iteration": state.iteration_count,
                            "max_iterations": state.max_iterations,
                            "errors": state.validation_result.errors,
                            "warnings": state.validation_result.warnings,
                            "report": result.get("report"),
                        },
                        can_modify=True,
                        can_abort=True,
                    )
                    self._update_state(session_id, state)
                    
                    print(f"[Workflow] Validation failed. Iteration {state.iteration_count}/{state.max_iterations}. Waiting for confirmation.")
                    return self._build_result(state, session_id)
                else:
                    # Max iterations reached - return to user with failure
                    state.phase = WorkflowPhase.ERROR
                    state.error = f"Validation failed after {state.max_iterations} iterations"
                    state.error_phase = WorkflowPhase.VALIDATING
                    state.pending_confirmation = ConfirmationRequest(
                        confirmation_type=ConfirmationType.CRITICAL_ERROR,
                        title="Max Iterations Reached",
                        message=f"Validation failed after {state.max_iterations} attempts. Review the errors and decide how to proceed.",
                        data={
                            "iterations": state.iteration_count,
                            "errors": state.validation_result.errors,
                            "warnings": state.validation_result.warnings,
                            "config": state.config_result.config if state.config_result else None,
                        },
                        can_modify=True,
                        can_abort=True,
                    )
                    self._update_state(session_id, state)
                    
                    print(f"[Workflow] Validation failed after {state.max_iterations} iterations.")
                    return self._build_result(state, session_id)
            
        except Exception as e:
            state.phase = WorkflowPhase.ERROR
            state.error = f"Validation error: {str(e)}"
            state.error_phase = WorkflowPhase.VALIDATING
            self._update_state(session_id, state)
            return self._build_result(state, session_id)
    
    async def _run_iteration(self, session_id: str) -> WorkflowResult:
        """
        Execute one iteration of the validation fix loop.
        
        Regenerates config with validation feedback and re-validates.
        """
        state = self._get_or_create_state(session_id)
        
        try:
            print(f"[Workflow] Iteration {state.iteration_count}: Regenerating config with fixes...")
            
            # Build feedback for generation agent
            validation_feedback = {
                "errors": state.validation_result.errors if state.validation_result else [],
                "warnings": state.validation_result.warnings if state.validation_result else [],
                "iteration": state.iteration_count,
            }
            
            # Get site analysis
            site_analysis = state.investigation_result.model_dump() if state.investigation_result else {}
            
            # Add validation feedback to site analysis
            site_analysis["validation_feedback"] = validation_feedback
            site_analysis["previous_config"] = state.config_result.config if state.config_result else None
            
            # Regenerate config
            state.phase = WorkflowPhase.GENERATING
            self._update_state(session_id, state)
            
            result = self.generation_agent.generate(
                site_analysis=site_analysis,
                output_sink=state.input.output_sink,
                output_index=state.input.output_index,
                output_dir=state.input.output_dir,
                content_type=state.input.content_type or (
                    state.config_result.content_type if state.config_result else None
                ),
                content_focus=state.input.content_focus,
                max_crawl_depth=state.input.max_crawl_depth,
                custom_fields=state.input.custom_fields,
            )
            
            # Update config result
            state.config_result = ConfigGenerationResult(**result)
            
            if result.get("status") == "error":
                state.phase = WorkflowPhase.ERROR
                state.error = result.get("error", "Regeneration failed")
                state.error_phase = WorkflowPhase.ITERATING
                self._update_state(session_id, state)
                return self._build_result(state, session_id)
            
            # Re-validate
            return await self._run_validation(session_id)
            
        except Exception as e:
            state.phase = WorkflowPhase.ERROR
            state.error = f"Iteration error: {str(e)}"
            state.error_phase = WorkflowPhase.ITERATING
            self._update_state(session_id, state)
            return self._build_result(state, session_id)
    
    async def _complete_workflow(
        self,
        session_id: str,
        with_warnings: bool = False,
    ) -> WorkflowResult:
        """
        Complete the workflow successfully.
        
        Stores final config and returns success result.
        """
        state = self._get_or_create_state(session_id)
        state.phase = WorkflowPhase.COMPLETE
        
        # Store final config
        if state.config_result:
            state.final_config = state.config_result.config
            state.final_yaml = state.config_result.yaml_content
        
        state.pending_confirmation = None
        self._update_state(session_id, state)
        
        status = "completed with warnings" if with_warnings else "completed"
        print(f"[Workflow] Workflow {status}.")
        
        return self._build_result(state, session_id)
    
    async def _handle_rejection(
        self,
        session_id: str,
        state: WorkflowState,
        confirmation: ConfirmationResponse,
    ) -> WorkflowResult:
        """
        Handle user rejection of a confirmation request.
        
        Returns to appropriate phase based on rejection type.
        """
        confirmation_type = state.pending_confirmation.confirmation_type
        
        if confirmation_type == ConfirmationType.INVESTIGATION_RESULTS:
            # User wants to modify investigation approach
            # For now, just re-run investigation
            state.pending_confirmation = None
            self._update_state(session_id, state)
            return await self._run_investigation(session_id)
        
        elif confirmation_type == ConfirmationType.CONFIG_PREVIEW:
            # User wants to modify config
            # Apply modifications and regenerate
            state.pending_confirmation = None
            if confirmation.modifications:
                await self._apply_modifications(state, confirmation.modifications)
            self._update_state(session_id, state)
            return await self._run_generation(session_id)
        
        elif confirmation_type == ConfirmationType.VALIDATION_FAILURE:
            # User rejected auto-fix, return with current state
            state.pending_confirmation = None
            self._update_state(session_id, state)
            return self._build_result(state, session_id)
        
        else:
            # Unknown type, just return current state
            state.pending_confirmation = None
            self._update_state(session_id, state)
            return self._build_result(state, session_id)
    
    async def _apply_modifications(
        self,
        state: WorkflowState,
        modifications: Dict[str, Any],
    ) -> None:
        """
        Apply user modifications to workflow state.
        
        Updates input, config, or other state based on modifications.
        """
        # Apply input modifications
        if "input" in modifications and state.input:
            for key, value in modifications["input"].items():
                if hasattr(state.input, key):
                    setattr(state.input, key, value)
        
        # Apply config modifications
        if "config" in modifications and state.config_result:
            state.config_result.config = modifications["config"]
        
        # Apply content type override
        if "content_type" in modifications and state.input:
            state.input.content_type = modifications["content_type"]
    
    def _build_result(
        self,
        state: WorkflowState,
        session_id: str,
        error: Optional[str] = None,
    ) -> WorkflowResult:
        """
        Build a WorkflowResult from current state.
        
        Includes all relevant information for the current phase.
        """
        if error:
            state.error = error
            state.phase = WorkflowPhase.ERROR
        
        # Calculate duration if we have start time
        total_duration = None
        if state.started_at:
            try:
                start = datetime.fromisoformat(state.started_at)
                total_duration = (datetime.utcnow() - start).total_seconds()
            except Exception:
                pass
        
        return WorkflowResult(
            success=state.phase == WorkflowPhase.COMPLETE,
            phase=state.phase,
            
            # Final outputs
            config=state.final_config,
            yaml_content=state.final_yaml,
            sample_document=(
                state.config_result.sample_document
                if state.config_result else None
            ),
            
            # Summaries
            investigation_summary=(
                {
                    "domain": state.investigation_result.domain,
                    "status": state.investigation_result.status,
                    "pages_analyzed": state.investigation_result.page_fetch_summary.get("successful", 0)
                    if state.investigation_result and state.investigation_result.page_fetch_summary else 0,
                }
                if state.investigation_result else None
            ),
            validation_summary=(
                {
                    "status": state.validation_result.overall_status,
                    "errors": len(state.validation_result.errors),
                    "warnings": len(state.validation_result.warnings),
                }
                if state.validation_result else None
            ),
            
            # Metadata
            iteration_count=state.iteration_count,
            total_duration_seconds=total_duration,
            
            # Errors
            error=state.error,
            error_details=(
                {
                    "phase": state.error_phase.value if state.error_phase else None,
                    "validation_errors": state.validation_result.errors if state.validation_result else [],
                }
                if state.error else None
            ),
            
            # Human-in-the-loop
            pending_confirmation=state.pending_confirmation,
        )
    
    def get_session_state(self, session_id: str) -> Optional[WorkflowState]:
        """Get the current state for a session."""
        return self._sessions.get(session_id)
    
    def clear_session(self, session_id: str) -> bool:
        """Clear a session's state."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False


def create_config_workflow(
    debug_mode: bool = False,
    use_agno_llm: bool = True,
) -> ConfigGenerationWorkflow:
    """
    Factory function to create a ConfigGenerationWorkflow.
    
    Args:
        debug_mode: Enable debug output
        use_agno_llm: Use Agno LLM features (requires API key)
        
    Returns:
        Configured ConfigGenerationWorkflow instance
        
    Example:
        >>> workflow = create_config_workflow()
        >>> result = await workflow.start(domain="https://example.com")
    """
    return ConfigGenerationWorkflow(
        debug_mode=debug_mode,
        use_agno_llm=use_agno_llm,
    )


# Alias for backward compatibility and discoverability
OrchestrationWorkflow = ConfigGenerationWorkflow
