"""
Unit tests for Agno framework integration with the LLM Proxy.

These tests verify:
1. Model configuration is correct
2. Agent creation works
3. LLM connectivity (requires valid API key)

Run with:
    cd elastic-crawler-control/crawler-service
    python -m pytest app/tests/test_agno_integration.py -v
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import Config


class TestAgnoConfiguration:
    """Tests for Agno model configuration."""
    
    def test_config_has_base_url(self):
        """Config should have LLM_PROXY_BASE_URL defined."""
        assert hasattr(Config, 'LLM_PROXY_BASE_URL')
        assert Config.LLM_PROXY_BASE_URL.endswith('/v1')
    
    def test_config_has_model(self):
        """Config should have LLM_MODEL defined."""
        assert hasattr(Config, 'LLM_MODEL')
        assert Config.LLM_MODEL  # Should not be empty
    
    def test_llm_enabled_check(self):
        """llm_enabled should return True only when API key is set."""
        # Save original value
        original = Config.LLM_PROXY_API_KEY
        
        try:
            # Test with empty key
            Config.LLM_PROXY_API_KEY = ""
            assert Config.llm_enabled() is False
            
            # Test with key set
            Config.LLM_PROXY_API_KEY = "test-key"
            assert Config.llm_enabled() is True
        finally:
            # Restore original
            Config.LLM_PROXY_API_KEY = original


class TestAgnoModelProvider:
    """Tests for the Agno model provider utilities."""
    
    def test_is_agno_available(self):
        """is_agno_available should reflect API key status."""
        from utils.agno_model import is_agno_available
        
        original = Config.LLM_PROXY_API_KEY
        try:
            Config.LLM_PROXY_API_KEY = ""
            assert is_agno_available() is False
            
            Config.LLM_PROXY_API_KEY = "test-key"
            assert is_agno_available() is True
        finally:
            Config.LLM_PROXY_API_KEY = original
    
    def test_get_model_raises_without_api_key(self):
        """get_model should raise ValueError without API key."""
        from utils.agno_model import get_model
        
        original = Config.LLM_PROXY_API_KEY
        try:
            Config.LLM_PROXY_API_KEY = ""
            
            with pytest.raises(ValueError) as exc_info:
                get_model()
            
            assert "LLM_PROXY_API_KEY not set" in str(exc_info.value)
        finally:
            Config.LLM_PROXY_API_KEY = original
    
    def test_get_model_with_api_key(self):
        """get_model should return OpenAILike model when API key is set."""
        from utils.agno_model import get_model
        from agno.models.openai.like import OpenAILike
        
        original = Config.LLM_PROXY_API_KEY
        try:
            Config.LLM_PROXY_API_KEY = "test-api-key"
            
            model = get_model()
            
            assert isinstance(model, OpenAILike)
            assert model.id == Config.LLM_MODEL
            assert model.api_key == "test-api-key"
            assert model.base_url == Config.LLM_PROXY_BASE_URL
        finally:
            Config.LLM_PROXY_API_KEY = original
    
    def test_get_model_with_overrides(self):
        """get_model should accept model_id override."""
        from utils.agno_model import get_model
        
        original = Config.LLM_PROXY_API_KEY
        try:
            Config.LLM_PROXY_API_KEY = "test-api-key"
            
            model = get_model(model_id="custom-model")
            
            assert model.id == "custom-model"
        finally:
            Config.LLM_PROXY_API_KEY = original
    
    def test_create_simple_agent(self):
        """create_simple_agent should return configured Agent."""
        from utils.agno_model import create_simple_agent
        from agno.agent import Agent
        
        original = Config.LLM_PROXY_API_KEY
        try:
            Config.LLM_PROXY_API_KEY = "test-api-key"
            
            agent = create_simple_agent(
                name="TestAgent",
                description="Test description",
            )
            
            assert isinstance(agent, Agent)
            assert agent.name == "TestAgent"
            assert agent.description == "Test description"
        finally:
            Config.LLM_PROXY_API_KEY = original


@pytest.mark.skipif(
    not os.getenv("LLM_PROXY_API_KEY"),
    reason="LLM_PROXY_API_KEY not set - skipping live connectivity test"
)
class TestAgnoLiveConnectivity:
    """
    Live connectivity tests that require a valid LLM_PROXY_API_KEY.
    
    These tests are skipped if no API key is available.
    Run with a valid key to test actual LLM connectivity:
        LLM_PROXY_API_KEY=your-key python -m pytest app/tests/test_agno_integration.py -v
    """
    
    def test_verify_llm_connectivity(self):
        """Live test: verify_llm_connectivity should succeed with valid key."""
        from utils.agno_model import verify_llm_connectivity
        
        result = verify_llm_connectivity()
        
        assert result["success"] is True
        assert "response" in result
        assert result["response"]  # Should have some content
    
    def test_simple_agent_run(self):
        """Live test: Simple agent should respond to prompts."""
        from utils.agno_model import create_simple_agent
        
        agent = create_simple_agent(name="LiveTestAgent")
        response = agent.run("Say 'test passed' and nothing else.")
        
        content = response.content if hasattr(response, 'content') else str(response)
        assert content  # Should have some response
        # Note: We don't check exact content as LLM responses vary
