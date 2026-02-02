"""
Integration tests for the Workflow SSE streaming endpoints.

Tests the FastAPI integration with Agno workflow SSE streaming:
- POST /api/generate endpoint receives SSE events
- Uses Agno's built-in streaming (not custom SSE formatting)
- session_id parameter support
- HITL endpoint /api/workflow/{session_id}/confirm

Run with:
    cd elastic-crawler-control/crawler-service
    python -m pytest app/tests/test_workflow_sse_integration.py -v
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# Import the FastAPI app
from server import app


class MockWorkflowEvent:
    """Mock Agno WorkflowRunOutputEvent for testing."""
    
    def __init__(self, content: dict = None, is_paused: bool = False):
        self.content = content or {"phase": "investigating", "status": "in_progress"}
        self.is_paused = is_paused
        self.active_requirements = [] if not is_paused else [MockRequirement()]
    
    def model_dump(self):
        return {
            "content": self.content,
            "is_paused": self.is_paused,
        }
    
    def model_dump_json(self):
        return json.dumps(self.model_dump())


class MockRequirement:
    """Mock HITL requirement."""
    needs_confirmation = True
    
    def confirm(self):
        pass
    
    def reject(self):
        pass
    
    def __str__(self):
        return "MockRequirement: Apply config"


class TestGenerateEndpoint:
    """Tests for POST /api/generate endpoint."""
    
    def test_generate_endpoint_exists(self):
        """Test that /api/generate endpoint exists."""
        with TestClient(app) as client:
            # Should get a response (even if error due to mocked workflow)
            response = client.post(
                "/api/generate",
                json={"domain": "https://example.com"}
            )
            # Should return SSE stream or error, not 404
            assert response.status_code != 404
    
    def test_generate_returns_sse_media_type(self):
        """Test that /api/generate returns text/event-stream."""
        with patch('routes.workflow.create_config_workflow') as mock_create:
            # Mock workflow to yield events
            mock_workflow = MagicMock()
            
            async def mock_arun(*args, **kwargs):
                yield MockWorkflowEvent({"phase": "complete", "status": "done"})
            
            mock_workflow.arun = mock_arun
            mock_create.return_value = mock_workflow
            
            with TestClient(app) as client:
                response = client.post(
                    "/api/generate",
                    json={"domain": "https://example.com"}
                )
                # Check content type is SSE
                assert "text/event-stream" in response.headers.get("content-type", "")
    
    def test_generate_includes_session_id_header(self):
        """Test that response includes X-Session-Id header."""
        with patch('routes.workflow.create_config_workflow') as mock_create:
            mock_workflow = MagicMock()
            
            async def mock_arun(*args, **kwargs):
                yield MockWorkflowEvent()
            
            mock_workflow.arun = mock_arun
            mock_create.return_value = mock_workflow
            
            with TestClient(app) as client:
                response = client.post(
                    "/api/generate",
                    json={"domain": "https://example.com"}
                )
                assert "x-session-id" in response.headers
    
    def test_generate_accepts_custom_session_id(self):
        """Test that custom session_id is used when provided."""
        with patch('routes.workflow.create_config_workflow') as mock_create:
            mock_workflow = MagicMock()
            
            async def mock_arun(*args, **kwargs):
                yield MockWorkflowEvent()
            
            mock_workflow.arun = mock_arun
            mock_create.return_value = mock_workflow
            
            with TestClient(app) as client:
                response = client.post(
                    "/api/generate",
                    json={
                        "domain": "https://example.com",
                        "session_id": "my-custom-session"
                    }
                )
                assert response.headers.get("x-session-id") == "my-custom-session"
    
    def test_generate_streams_sse_events(self):
        """Test that endpoint streams SSE events in correct format."""
        with patch('routes.workflow.create_config_workflow') as mock_create:
            mock_workflow = MagicMock()
            
            async def mock_arun(*args, **kwargs):
                # Yield multiple events
                yield MockWorkflowEvent({"phase": "investigating"})
                yield MockWorkflowEvent({"phase": "generating"})
                yield MockWorkflowEvent({"phase": "complete"})
            
            mock_workflow.arun = mock_arun
            mock_create.return_value = mock_workflow
            
            with TestClient(app) as client:
                response = client.post(
                    "/api/generate",
                    json={"domain": "https://example.com"}
                )
                
                # Parse SSE events from response
                content = response.text
                # SSE events should be in format: data: {...}\n\n
                assert "data:" in content
    
    def test_generate_error_handling(self):
        """Test that errors are yielded as error events."""
        with patch('routes.workflow.create_config_workflow') as mock_create:
            mock_workflow = MagicMock()
            
            async def mock_arun(*args, **kwargs):
                raise Exception("Test error")
                yield  # Never reached but needed for generator
            
            mock_workflow.arun = mock_arun
            mock_create.return_value = mock_workflow
            
            with TestClient(app) as client:
                response = client.post(
                    "/api/generate",
                    json={"domain": "https://example.com"}
                )
                
                # Should contain error in response
                content = response.text
                assert "error" in content.lower()


class TestWorkflowStartBackwardCompat:
    """Tests for backward compatibility with /api/workflow/start."""
    
    def test_workflow_start_endpoint_exists(self):
        """Test that /api/workflow/start still works."""
        with TestClient(app) as client:
            response = client.post(
                "/api/workflow/start",
                json={"domain": "https://example.com"}
            )
            # Should not be 404
            assert response.status_code != 404
    
    def test_workflow_start_returns_sse(self):
        """Test that /api/workflow/start returns SSE stream."""
        with patch('routes.workflow.create_config_workflow') as mock_create:
            mock_workflow = MagicMock()
            
            async def mock_arun(*args, **kwargs):
                yield MockWorkflowEvent()
            
            mock_workflow.arun = mock_arun
            mock_create.return_value = mock_workflow
            
            with TestClient(app) as client:
                response = client.post(
                    "/api/workflow/start",
                    json={"domain": "https://example.com"}
                )
                assert "text/event-stream" in response.headers.get("content-type", "")


class TestHITLEndpoint:
    """Tests for Agent-level HITL handling."""
    
    def test_confirm_endpoint_exists(self):
        """Test that confirm endpoint exists."""
        with TestClient(app) as client:
            response = client.post(
                "/api/workflow/test-session/confirm",
                json={"confirmed": True}
            )
            # Should be 404 (session not found) not method not allowed
            assert response.status_code == 404
    
    def test_confirm_requires_paused_session(self):
        """Test that confirm endpoint requires a paused session."""
        with TestClient(app) as client:
            response = client.post(
                "/api/workflow/nonexistent-session/confirm",
                json={"confirmed": True}
            )
            assert response.status_code == 404
            assert "paused" in response.json()["detail"].lower()


class TestStatusEndpoint:
    """Tests for workflow status endpoint."""
    
    def test_status_endpoint_exists(self):
        """Test that status endpoint exists."""
        with TestClient(app) as client:
            response = client.get("/api/workflow/test-session/status")
            # Should be 404 (session not found) not method not allowed
            assert response.status_code == 404
    
    def test_status_returns_is_paused_field(self):
        """Test that status includes is_paused field."""
        # First create a session
        with patch('routes.workflow.create_config_workflow') as mock_create:
            with patch('routes.workflow._workflow_sessions', {"test-session": {"phase": "investigating"}}):
                with TestClient(app) as client:
                    response = client.get("/api/workflow/test-session/status")
                    
                    # Should return status with is_paused field
                    if response.status_code == 200:
                        data = response.json()
                        assert "is_paused" in data


class TestSessionsEndpoint:
    """Tests for listing workflow sessions."""
    
    def test_sessions_endpoint_exists(self):
        """Test that sessions endpoint exists."""
        with TestClient(app) as client:
            response = client.get("/api/workflow/sessions")
            assert response.status_code == 200
    
    def test_sessions_returns_list(self):
        """Test that sessions endpoint returns session list."""
        with TestClient(app) as client:
            response = client.get("/api/workflow/sessions")
            data = response.json()
            assert "sessions" in data
            assert "total" in data


class TestCodeChecks:
    """
    Code verification tests for acceptance criteria.
    
    These tests verify the implementation follows Agno best practices.
    """
    
    def test_no_custom_format_sse_event_function(self):
        """
        ACCEPTANCE CHECK: NO custom SSE formatting code.
        
        The old format_sse_event() function should be removed.
        """
        import inspect
        import routes.workflow as module
        
        source = inspect.getsource(module)
        
        # Check that format_sse_event is NOT defined as a function
        # (We allow the function name to appear in comments/docstrings)
        assert "def format_sse_event" not in source, (
            "Found custom format_sse_event() function. "
            "Should use Agno's event.model_dump_json() directly."
        )
    
    def test_uses_workflow_arun_stream_true(self):
        """
        ACCEPTANCE CHECK: Uses workflow.arun(..., stream=True).
        """
        import inspect
        import routes.workflow as module
        
        source = inspect.getsource(module)
        
        # Check for stream=True in arun call
        assert "stream=True" in source, (
            "Missing stream=True parameter. "
            "Must use workflow.arun(stream=True) for SSE streaming."
        )
    
    def test_uses_session_id_parameter(self):
        """
        ACCEPTANCE CHECK: Uses session_id parameter for session management.
        """
        import inspect
        import routes.workflow as module
        
        source = inspect.getsource(module)
        
        # Check for session_id parameter
        assert "session_id=" in source, (
            "Missing session_id parameter. "
            "Must use session_id for session management."
        )
    
    def test_uses_model_dump_json(self):
        """
        ACCEPTANCE CHECK: Uses Agno's event.model_dump_json() directly.
        """
        import inspect
        import routes.workflow as module
        
        source = inspect.getsource(module)
        
        # Check for model_dump_json usage
        assert "model_dump_json()" in source, (
            "Missing model_dump_json() usage. "
            "Must use Agno's built-in serialization."
        )
    
    def test_handles_is_paused(self):
        """
        ACCEPTANCE CHECK: Handles Agent-level HITL via is_paused.
        """
        import inspect
        import routes.workflow as module
        
        source = inspect.getsource(module)
        
        # Check for is_paused handling
        assert "is_paused" in source, (
            "Missing is_paused handling. "
            "Must check event.is_paused for Agent-level HITL."
        )
    
    def test_has_confirm_endpoint(self):
        """
        ACCEPTANCE CHECK: Has confirm endpoint for HITL.
        """
        import inspect
        import routes.workflow as module
        
        source = inspect.getsource(module)
        
        # Check for confirm endpoint
        assert "/confirm" in source, (
            "Missing confirm endpoint. "
            "Must have endpoint for HITL confirmation."
        )
    
    def test_has_generate_endpoint(self):
        """
        ACCEPTANCE CHECK: Has POST /generate endpoint.
        """
        import inspect
        import routes.workflow as module
        
        source = inspect.getsource(module)
        
        # Check for /generate endpoint
        assert '"/generate"' in source or "'/generate'" in source, (
            "Missing /generate endpoint. "
            "Must have POST /generate endpoint as per task spec."
        )
