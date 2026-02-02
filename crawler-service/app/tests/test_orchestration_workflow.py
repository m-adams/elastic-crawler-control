"""
Integration tests for the ConfigGenerationWorkflow.

Tests the complete orchestration workflow including:
- Full workflow execution (start to complete)
- Human-in-the-loop confirmation points
- Validation iteration loop
- State persistence across steps
- Error handling

Run with:
    cd elastic-crawler-control/crawler-service
    python -m pytest app/tests/test_orchestration_workflow.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.orchestration_workflow import (
    ConfigGenerationWorkflow,
    create_config_workflow,
)
from agents.workflow_models import (
    WorkflowPhase,
    WorkflowResult,
    ConfirmationType,
    ConfirmationResponse,
)


class TestWorkflowModels:
    """Tests for workflow data models."""
    
    def test_workflow_phase_enum(self):
        """Test WorkflowPhase enum values."""
        assert WorkflowPhase.INITIAL.value == "initial"
        assert WorkflowPhase.INVESTIGATING.value == "investigating"
        assert WorkflowPhase.COMPLETE.value == "complete"
        assert WorkflowPhase.ERROR.value == "error"
    
    def test_confirmation_type_enum(self):
        """Test ConfirmationType enum values."""
        assert ConfirmationType.INVESTIGATION_RESULTS.value == "investigation_results"
        assert ConfirmationType.CONFIG_PREVIEW.value == "config_preview"
        assert ConfirmationType.VALIDATION_FAILURE.value == "validation_failure"
    
    def test_confirmation_response_model(self):
        """Test ConfirmationResponse model."""
        response = ConfirmationResponse(
            confirmed=True,
            abort=False,
            feedback="Looks good!",
        )
        assert response.confirmed is True
        assert response.abort is False
        assert response.feedback == "Looks good!"
    
    def test_workflow_result_model(self):
        """Test WorkflowResult model."""
        result = WorkflowResult(
            success=True,
            phase=WorkflowPhase.COMPLETE,
            config={"output_sink": "file"},
            yaml_content="output_sink: file",
        )
        assert result.success is True
        assert result.phase == WorkflowPhase.COMPLETE


class TestConfigGenerationWorkflow:
    """Tests for ConfigGenerationWorkflow class."""
    
    @pytest.fixture
    def workflow(self):
        """Create a workflow instance with LLM features disabled."""
        return ConfigGenerationWorkflow(
            debug_mode=False,
            use_agno_llm=False,  # Disable LLM for faster tests
        )
    
    def test_workflow_initialization(self, workflow):
        """Test workflow initializes correctly."""
        assert workflow is not None
        assert workflow.debug_mode is False
        assert workflow.use_agno_llm is False
    
    def test_create_config_workflow_factory(self):
        """Test factory function creates workflow."""
        workflow = create_config_workflow(debug_mode=True)
        assert isinstance(workflow, ConfigGenerationWorkflow)
        assert workflow.debug_mode is True
    
    def test_session_state_management(self, workflow):
        """Test session state creation and retrieval."""
        session_id = "test-session-123"
        
        # Get or create state
        state = workflow._get_or_create_state(session_id)
        assert state is not None
        assert state.phase == WorkflowPhase.INITIAL
        
        # Update state
        state.phase = WorkflowPhase.INVESTIGATING
        workflow._update_state(session_id, state)
        
        # Retrieve updated state
        retrieved = workflow.get_session_state(session_id)
        assert retrieved.phase == WorkflowPhase.INVESTIGATING
        
        # Clear session
        assert workflow.clear_session(session_id) is True
        assert workflow.get_session_state(session_id) is None


class TestWorkflowInvestigationPhase:
    """Tests for the investigation phase of the workflow."""
    
    @pytest.fixture
    def workflow(self):
        """Create a workflow with mocked investigation agent."""
        wf = ConfigGenerationWorkflow(use_agno_llm=False)
        return wf
    
    @pytest.mark.asyncio
    async def test_investigation_returns_confirmation_request(self, workflow):
        """Test that investigation phase returns a confirmation request."""
        # Mock the investigation agent
        mock_result = {
            "domain": "https://example.com",
            "domain_name": "example.com",
            "status": "completed",
            "robots_txt": {"accessible": True},
            "sitemaps": {"sitemap_urls": []},
            "page_fetch_summary": {"successful": 5, "failed": 0},
            "page_structure_analysis": {},
            "recommendations": {},
        }
        
        workflow._investigation_agent = MagicMock()
        workflow._investigation_agent.investigate = AsyncMock(return_value=mock_result)
        
        # Start workflow
        result = await workflow.start(
            domain="https://example.com",
            session_id="test-investigation",
        )
        
        # Should pause for confirmation
        assert result.phase == WorkflowPhase.AWAITING_INVESTIGATION_CONFIRMATION
        assert result.pending_confirmation is not None
        assert result.pending_confirmation.confirmation_type == ConfirmationType.INVESTIGATION_RESULTS
    
    @pytest.mark.asyncio
    async def test_investigation_error_handling(self, workflow):
        """Test that investigation errors are handled correctly."""
        # Mock an investigation error
        mock_result = {
            "domain": "https://example.com",
            "domain_name": "example.com",
            "status": "error",
            "error": "Connection failed",
        }
        
        workflow._investigation_agent = MagicMock()
        workflow._investigation_agent.investigate = AsyncMock(return_value=mock_result)
        
        result = await workflow.start(
            domain="https://example.com",
            session_id="test-error",
        )
        
        # Should be in error state
        assert result.phase == WorkflowPhase.ERROR
        assert result.error is not None


class TestWorkflowGenerationPhase:
    """Tests for the generation phase of the workflow."""
    
    @pytest.fixture
    def workflow_with_investigation(self):
        """Create a workflow that has completed investigation."""
        wf = ConfigGenerationWorkflow(use_agno_llm=False)
        
        # Mock investigation result in state
        state = wf._get_or_create_state("test-generation")
        from agents.workflow_models import WorkflowInput, InvestigationResult
        
        state.input = WorkflowInput(
            domain="https://example.com",
            output_sink="file",
        )
        state.investigation_result = InvestigationResult(
            domain="https://example.com",
            domain_name="example.com",
            status="completed",
        )
        state.phase = WorkflowPhase.AWAITING_INVESTIGATION_CONFIRMATION
        wf._update_state("test-generation", state)
        
        return wf
    
    @pytest.mark.asyncio
    async def test_generation_after_confirmation(self, workflow_with_investigation):
        """Test generation phase after user confirms investigation."""
        # Mock generation agent
        mock_result = {
            "status": "completed",
            "domain": "https://example.com",
            "content_type": "general",
            "config": {"output_sink": "file", "domains": []},
            "yaml_content": "output_sink: file",
            "reasoning": ["Generated basic config"],
            "validation": {"valid": True},
        }
        
        workflow_with_investigation._generation_agent = MagicMock()
        workflow_with_investigation._generation_agent.generate = MagicMock(return_value=mock_result)
        
        # Set pending confirmation
        from agents.workflow_models import ConfirmationRequest
        state = workflow_with_investigation.get_session_state("test-generation")
        state.pending_confirmation = ConfirmationRequest(
            confirmation_type=ConfirmationType.INVESTIGATION_RESULTS,
            title="Test",
            message="Test",
            data={},
        )
        workflow_with_investigation._update_state("test-generation", state)
        
        # Confirm and continue
        result = await workflow_with_investigation.continue_workflow(
            session_id="test-generation",
            confirmation=ConfirmationResponse(confirmed=True),
        )
        
        # Should now be waiting for config confirmation
        assert result.phase == WorkflowPhase.AWAITING_CONFIG_CONFIRMATION
        assert result.pending_confirmation is not None
        assert result.pending_confirmation.confirmation_type == ConfirmationType.CONFIG_PREVIEW


class TestWorkflowValidationPhase:
    """Tests for the validation phase and iteration loop."""
    
    @pytest.fixture
    def workflow_with_config(self):
        """Create a workflow that has completed config generation."""
        wf = ConfigGenerationWorkflow(use_agno_llm=False)
        
        # Set up state with config result
        state = wf._get_or_create_state("test-validation")
        from agents.workflow_models import (
            WorkflowInput, InvestigationResult, ConfigGenerationResult
        )
        
        state.input = WorkflowInput(
            domain="https://example.com",
            output_sink="file",
        )
        state.investigation_result = InvestigationResult(
            domain="https://example.com",
            domain_name="example.com",
            status="completed",
        )
        state.config_result = ConfigGenerationResult(
            status="completed",
            domain="https://example.com",
            content_type="general",
            config={
                "output_sink": "file",
                "domains": [{
                    "url": "https://example.com",
                    "seed_urls": ["https://example.com/"],
                }]
            },
            yaml_content="output_sink: file",
        )
        state.phase = WorkflowPhase.AWAITING_CONFIG_CONFIRMATION
        wf._update_state("test-validation", state)
        
        return wf
    
    @pytest.mark.asyncio
    async def test_validation_success_completes_workflow(self, workflow_with_config):
        """Test that validation success completes the workflow."""
        # Mock validation agent with success
        mock_result = {
            "overall_status": "pass",
            "yaml_validation": {"valid": True},
            "schema_validation": {"valid": True},
            "report": {"all_errors": [], "all_warnings": []},
        }
        
        workflow_with_config._validation_agent = MagicMock()
        workflow_with_config._validation_agent.validate = AsyncMock(return_value=mock_result)
        
        # Set pending confirmation for config
        from agents.workflow_models import ConfirmationRequest
        state = workflow_with_config.get_session_state("test-validation")
        state.pending_confirmation = ConfirmationRequest(
            confirmation_type=ConfirmationType.CONFIG_PREVIEW,
            title="Test",
            message="Test",
            data={},
        )
        workflow_with_config._update_state("test-validation", state)
        
        # Confirm and continue
        result = await workflow_with_config.continue_workflow(
            session_id="test-validation",
            confirmation=ConfirmationResponse(confirmed=True),
        )
        
        # Should be complete
        assert result.phase == WorkflowPhase.COMPLETE
        assert result.success is True
        assert result.yaml_content is not None
    
    @pytest.mark.asyncio
    async def test_validation_failure_triggers_iteration(self, workflow_with_config):
        """Test that validation failure triggers iteration loop."""
        # Mock validation agent with failure
        mock_result = {
            "overall_status": "fail",
            "yaml_validation": {"valid": True},
            "schema_validation": {"valid": False, "errors": ["Missing field"]},
            "report": {
                "all_errors": ["Missing required field: extraction_rulesets"],
                "all_warnings": [],
            },
        }
        
        workflow_with_config._validation_agent = MagicMock()
        workflow_with_config._validation_agent.validate = AsyncMock(return_value=mock_result)
        
        # Set pending confirmation for config
        from agents.workflow_models import ConfirmationRequest
        state = workflow_with_config.get_session_state("test-validation")
        state.pending_confirmation = ConfirmationRequest(
            confirmation_type=ConfirmationType.CONFIG_PREVIEW,
            title="Test",
            message="Test",
            data={},
        )
        workflow_with_config._update_state("test-validation", state)
        
        # Confirm and continue
        result = await workflow_with_config.continue_workflow(
            session_id="test-validation",
            confirmation=ConfirmationResponse(confirmed=True),
        )
        
        # Should be in iteration phase with confirmation request
        assert result.phase == WorkflowPhase.ITERATING
        assert result.pending_confirmation is not None
        assert result.pending_confirmation.confirmation_type == ConfirmationType.VALIDATION_FAILURE
    
    @pytest.mark.asyncio
    async def test_max_iterations_reached(self, workflow_with_config):
        """Test that max iterations triggers error state."""
        # Mock validation agent with persistent failure
        mock_result = {
            "overall_status": "fail",
            "report": {"all_errors": ["Persistent error"], "all_warnings": []},
        }
        
        workflow_with_config._validation_agent = MagicMock()
        workflow_with_config._validation_agent.validate = AsyncMock(return_value=mock_result)
        
        # Set iteration count to max
        state = workflow_with_config.get_session_state("test-validation")
        state.iteration_count = 3  # At max
        state.max_iterations = 3
        state.phase = WorkflowPhase.VALIDATING
        workflow_with_config._update_state("test-validation", state)
        
        # Run validation
        result = await workflow_with_config._run_validation("test-validation")
        
        # Should be in error state
        assert result.phase == WorkflowPhase.ERROR
        assert "Max Iterations Reached" in result.pending_confirmation.title


class TestWorkflowHumanInTheLoop:
    """Tests for human-in-the-loop confirmation handling."""
    
    @pytest.fixture
    def workflow(self):
        """Create a workflow instance."""
        return ConfigGenerationWorkflow(use_agno_llm=False)
    
    @pytest.mark.asyncio
    async def test_abort_workflow(self, workflow):
        """Test aborting workflow via confirmation response."""
        # Set up state with pending confirmation
        state = workflow._get_or_create_state("test-abort")
        from agents.workflow_models import WorkflowInput, ConfirmationRequest
        
        state.input = WorkflowInput(domain="https://example.com")
        state.pending_confirmation = ConfirmationRequest(
            confirmation_type=ConfirmationType.INVESTIGATION_RESULTS,
            title="Test",
            message="Test",
            data={},
        )
        state.phase = WorkflowPhase.AWAITING_INVESTIGATION_CONFIRMATION
        workflow._update_state("test-abort", state)
        
        # Send abort confirmation
        result = await workflow.continue_workflow(
            session_id="test-abort",
            confirmation=ConfirmationResponse(confirmed=False, abort=True),
        )
        
        # Should be in error state
        assert result.phase == WorkflowPhase.ERROR
        assert "aborted" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_continue_without_confirmation(self, workflow):
        """Test continuing workflow when no confirmation is pending."""
        # Set up state without pending confirmation
        state = workflow._get_or_create_state("test-no-confirm")
        from agents.workflow_models import WorkflowInput
        
        state.input = WorkflowInput(domain="https://example.com")
        state.phase = WorkflowPhase.INITIAL
        workflow._update_state("test-no-confirm", state)
        
        # Try to continue without starting
        result = await workflow.continue_workflow(
            session_id="test-no-confirm",
        )
        
        # Should get error message
        assert result.error is not None


class TestFullWorkflowIntegration:
    """
    Full integration test of the complete workflow.
    
    This test runs the complete workflow with mocked agents.
    """
    
    @pytest.mark.asyncio
    async def test_full_workflow_success(self):
        """Test complete workflow from start to finish."""
        workflow = ConfigGenerationWorkflow(use_agno_llm=False)
        
        # Mock all agents
        investigation_result = {
            "domain": "https://example.com",
            "domain_name": "example.com",
            "status": "completed",
            "robots_txt": {"accessible": True},
            "sitemaps": {},
            "page_fetch_summary": {"successful": 5},
            "page_structure_analysis": {},
            "recommendations": {},
        }
        
        generation_result = {
            "status": "completed",
            "domain": "https://example.com",
            "content_type": "general",
            "config": {
                "output_sink": "file",
                "domains": [{
                    "url": "https://example.com",
                    "seed_urls": ["https://example.com/"],
                }]
            },
            "yaml_content": "output_sink: file\ndomains:\n  - url: https://example.com",
            "reasoning": ["Generated config"],
            "sample_document": {"title": "Example"},
            "validation": {"valid": True},
        }
        
        validation_result = {
            "overall_status": "pass",
            "yaml_validation": {"valid": True},
            "schema_validation": {"valid": True},
            "report": {"all_errors": [], "all_warnings": []},
        }
        
        workflow._investigation_agent = MagicMock()
        workflow._investigation_agent.investigate = AsyncMock(return_value=investigation_result)
        
        workflow._generation_agent = MagicMock()
        workflow._generation_agent.generate = MagicMock(return_value=generation_result)
        
        workflow._validation_agent = MagicMock()
        workflow._validation_agent.validate = AsyncMock(return_value=validation_result)
        
        # Step 1: Start workflow
        result = await workflow.start(
            domain="https://example.com",
            session_id="full-test",
        )
        
        assert result.phase == WorkflowPhase.AWAITING_INVESTIGATION_CONFIRMATION
        assert result.pending_confirmation is not None
        
        # Step 2: Confirm investigation
        result = await workflow.continue_workflow(
            session_id="full-test",
            confirmation=ConfirmationResponse(confirmed=True),
        )
        
        assert result.phase == WorkflowPhase.AWAITING_CONFIG_CONFIRMATION
        assert result.pending_confirmation is not None
        
        # Step 3: Confirm config
        result = await workflow.continue_workflow(
            session_id="full-test",
            confirmation=ConfirmationResponse(confirmed=True),
        )
        
        # Step 4: Workflow complete!
        assert result.phase == WorkflowPhase.COMPLETE
        assert result.success is True
        assert result.yaml_content is not None
        assert result.config is not None


@pytest.mark.skipif(
    True,  # Skip by default - enable manually for live tests
    reason="Live tests require network access and may be slow"
)
class TestLiveWorkflowIntegration:
    """
    Live integration tests with real network calls.
    
    These tests are skipped by default. Enable by setting skipif to False.
    Run with: pytest -v -k "LiveWorkflow"
    """
    
    @pytest.mark.asyncio
    async def test_live_investigation_example_com(self):
        """Live test: Investigate example.com (stable test site)."""
        workflow = ConfigGenerationWorkflow(use_agno_llm=False)
        
        result = await workflow.start(
            domain="https://example.com",
            session_id="live-test",
        )
        
        # Should pause for confirmation
        assert result.phase == WorkflowPhase.AWAITING_INVESTIGATION_CONFIRMATION
        assert result.pending_confirmation is not None
        
        # Check investigation data
        data = result.pending_confirmation.data
        assert data.get("domain") == "https://example.com"
        assert data.get("status") in ["completed", "warning"]
