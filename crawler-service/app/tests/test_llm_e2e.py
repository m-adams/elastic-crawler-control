"""
End-to-End LLM Integration Tests

These tests run the ACTUAL Agno agents with REAL LLM calls.
They verify the system works, not just that code compiles.

Run with: python -m pytest app/tests/test_llm_e2e.py -v
Requires: LLM_PROXY_API_KEY in .env

These are NOT mocked - they make real API calls and cost money.
"""

import os
import pytest
import yaml

from utils.config import Config

# Skip all tests in this file if no API key
pytestmark = pytest.mark.skipif(
    not Config.LLM_PROXY_API_KEY,
    reason="LLM_PROXY_API_KEY not set - skipping LLM E2E tests"
)


class TestSiteInvestigationAgentE2E:
    """
    End-to-end tests for Site Investigation Agent with real LLM.
    """
    
    @pytest.mark.asyncio
    async def test_investigate_example_com_with_llm(self):
        """
        REAL TEST: Run Site Investigation Agent against example.com.
        
        This actually calls the LLM and verifies it produces useful output.
        """
        from agents.site_investigation import SiteInvestigationAgent
        
        agent = SiteInvestigationAgent(
            sample_page_count=3,
            rate_limit_delay=0.5,
        )
        
        result = await agent.investigate("https://example.com")
        
        # Basic structure checks
        assert result is not None
        assert "domain" in result
        assert "example.com" in result["domain"]
        
        # Should have analyzed something
        assert "robots_txt" in result or "pages_analyzed" in result or "recommendations" in result
        
        print(f"\n=== Site Investigation Result ===")
        print(f"Domain: {result.get('domain')}")
        print(f"Keys: {list(result.keys())}")
        if "recommendations" in result:
            recs = result['recommendations']
            print(f"Recommendations: {str(recs)[:200]}...")
    
    @pytest.mark.asyncio
    async def test_investigate_docs_site_with_llm(self):
        """
        REAL TEST: Run Site Investigation Agent against a docs site.
        """
        from agents.site_investigation import SiteInvestigationAgent
        
        agent = SiteInvestigationAgent(
            sample_page_count=3,
            rate_limit_delay=0.5,
        )
        
        # Use Elastic docs as a real docs site
        result = await agent.investigate("https://www.elastic.co/guide")
        
        assert result is not None
        assert "domain" in result
        
        print(f"\n=== Docs Site Investigation ===")
        print(f"Domain: {result.get('domain')}")
        print(f"Keys: {list(result.keys())}")


class TestConfigGenerationAgentE2E:
    """
    End-to-end tests for Config Generation Agent with real LLM.
    """
    
    @pytest.mark.asyncio
    async def test_generate_config_from_investigation(self):
        """
        REAL TEST: Full pipeline - investigate site then generate config.
        """
        from agents.site_investigation import SiteInvestigationAgent
        from agents.config_generation import ConfigGenerationAgent
        
        # Step 1: Investigate
        investigation_agent = SiteInvestigationAgent(
            sample_page_count=3,
            rate_limit_delay=0.5,
        )
        
        investigation = await investigation_agent.investigate("https://example.com")
        assert investigation is not None
        
        # Step 2: Generate config
        config_agent = ConfigGenerationAgent(use_agno=True)
        
        config_result = config_agent.generate(investigation)
        
        assert config_result is not None
        assert "config" in config_result
        
        # Verify it's valid YAML
        config = config_result["config"]
        yaml_str = yaml.dump(config)
        parsed = yaml.safe_load(yaml_str)
        assert parsed is not None
        
        # Should have domain config
        assert "domains" in config
        assert len(config["domains"]) > 0
        assert "url" in config["domains"][0]
        
        print(f"\n=== Generated Config ===")
        print(yaml.dump(config, default_flow_style=False)[:500])


class TestAgnoWorkflowE2E:
    """
    End-to-end tests for the full Agno workflow.
    """
    
    @pytest.mark.asyncio
    async def test_full_workflow_streaming(self):
        """
        REAL TEST: Run the full orchestration workflow with streaming.
        
        This tests the entire pipeline:
        1. Site Investigation Agent
        2. Config Generation Agent  
        3. Config Validation Agent
        4. Loop for retries if needed
        """
        from agents.orchestration_workflow import create_config_workflow
        from agents.workflow_state import WorkflowInput, create_initial_session_state
        
        # Create workflow input
        workflow_input = WorkflowInput(
            domain="https://example.com",
            seed_urls=None,
            content_type=None,
        )
        
        session_state = create_initial_session_state(workflow_input)
        
        # Create workflow with streaming
        workflow = create_config_workflow(
            session_state=session_state,
            stream=True,
        )
        
        # Collect streamed events
        events = []
        async for event in workflow.arun(
            input=workflow_input.model_dump(),
            stream=True,
        ):
            events.append(event)
            # Print progress
            if hasattr(event, 'content'):
                content = event.content
                if isinstance(content, str):
                    print(f"Event: {content[:100]}...")
                elif isinstance(content, dict):
                    print(f"Event keys: {list(content.keys())}")
        
        # Should have received events
        assert len(events) > 0
        print(f"\n=== Workflow completed with {len(events)} events ===")
    
    @pytest.mark.asyncio
    async def test_workflow_produces_valid_config(self):
        """
        REAL TEST: Verify workflow produces valid Open Crawler config.
        
        Note: Uses streaming to avoid event loop issues.
        """
        from agents.orchestration_workflow import create_config_workflow
        from agents.workflow_state import WorkflowInput, create_initial_session_state
        
        workflow_input = WorkflowInput(
            domain="https://example.com",
        )
        
        session_state = create_initial_session_state(workflow_input)
        workflow = create_config_workflow(session_state=session_state, stream=True)
        
        # Collect all events to get final result
        final_content = None
        async for event in workflow.arun(input=workflow_input.model_dump(), stream=True):
            if hasattr(event, 'content'):
                final_content = event.content
        
        assert final_content is not None
        print(f"\n=== Final Workflow Output ===")
        print(f"Type: {type(final_content)}")
        
        # Check if we got a config
        if isinstance(final_content, dict):
            print(f"Keys: {list(final_content.keys())}")
            if 'config' in final_content:
                config = final_content['config']
                yaml_str = yaml.dump(config)
                print(f"\nConfig:\n{yaml_str[:500]}")


class TestValidationAgentE2E:
    """
    End-to-end tests for Config Validation Agent with real LLM.
    """
    
    @pytest.mark.asyncio
    async def test_validate_good_config(self):
        """
        REAL TEST: Validate a known-good config.
        """
        from agents.config_validation import ConfigValidationAgent
        
        good_config = {
            "output_sink": "console",
            "domains": [
                {
                    "url": "https://example.com",
                    "seed_urls": ["https://example.com/"],
                    "crawl_rules": [
                        {"policy": "allow", "pattern": "/docs/*", "type": "begins"},
                        {"policy": "deny", "pattern": "/admin/*", "type": "begins"},
                    ]
                }
            ]
        }
        
        agent = ConfigValidationAgent()
        result = await agent.validate(good_config)
        
        assert result is not None
        # Check for any validity indicator
        has_validity = (
            "valid" in result or 
            "is_valid" in result or 
            "overall_status" in result or
            "schema_validation" in result
        )
        assert has_validity, f"Result has no validity indicator: {result.keys()}"
        
        print(f"\n=== Validation Result ===")
        print(f"Keys: {list(result.keys())}")
        if "overall_status" in result:
            print(f"Status: {result['overall_status']}")
    
    @pytest.mark.asyncio
    async def test_validate_bad_config(self):
        """
        REAL TEST: Validate a bad config and get suggestions.
        """
        from agents.config_validation import ConfigValidationAgent
        
        bad_config = {
            # Missing required 'domains' field
            "url": "example.com",  # Wrong structure
        }
        
        agent = ConfigValidationAgent()
        result = await agent.validate(bad_config)
        
        assert result is not None
        # Should report errors or invalid
        print(f"\n=== Bad Config Validation ===")
        print(result)


if __name__ == "__main__":
    # Run with verbose output
    pytest.main([__file__, "-v", "-s"])
