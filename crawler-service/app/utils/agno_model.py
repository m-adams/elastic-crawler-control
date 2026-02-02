"""
Agno model provider configuration for the Elastic LLM Proxy.

Provides a pre-configured OpenAILike model that connects to the Elastic LLM Proxy
(or any OpenAI-compatible endpoint). This module is the standard way to get an
LLM model instance for use with Agno agents.

Usage:
    from utils.agno_model import get_model, create_simple_agent
    
    # Get the configured model
    model = get_model()
    
    # Or create a simple agent directly
    agent = create_simple_agent()
    response = agent.run("Hello, world!")

Environment Variables Required:
    LLM_PROXY_BASE_URL: Base URL for OpenAI-compatible API (default: Elastic LLM Proxy /v1)
    LLM_PROXY_API_KEY: API key for authentication (required)
    LLM_MODEL: Model name (default: claude-sonnet-4)
"""

from typing import Optional

from agno.agent import Agent
from agno.models.openai.like import OpenAILike

from utils.config import Config


def get_model(
    model_id: Optional[str] = None,
    temperature: Optional[float] = None,
) -> OpenAILike:
    """
    Get a configured Agno OpenAILike model for the LLM Proxy.
    
    This is the standard way to get an LLM model instance for use with Agno agents.
    The model is configured from environment variables, with optional overrides.
    
    Args:
        model_id: Override the default model ID (default: from LLM_MODEL env var)
        temperature: Override the default temperature (default: model default)
        
    Returns:
        Configured OpenAILike model instance
        
    Raises:
        ValueError: If LLM_PROXY_API_KEY is not configured
        
    Example:
        >>> model = get_model()
        >>> agent = Agent(model=model)
        >>> response = agent.run("Hello!")
    """
    if not Config.LLM_PROXY_API_KEY:
        raise ValueError(
            "LLM_PROXY_API_KEY not set. "
            "Agno features require an LLM proxy API key. "
            "Get one at: https://sa-workshops.prod-3.eden.elastic.dev/LLM_Key_Generator"
        )
    
    model_kwargs = {
        "id": model_id or Config.LLM_MODEL,
        "api_key": Config.LLM_PROXY_API_KEY,
        "base_url": Config.LLM_PROXY_BASE_URL,
    }
    
    if temperature is not None:
        model_kwargs["temperature"] = temperature
    
    return OpenAILike(**model_kwargs)


def create_simple_agent(
    model_id: Optional[str] = None,
    name: str = "SimpleAgent",
    description: str = "A simple AI assistant",
    instructions: Optional[list[str]] = None,
    markdown: bool = True,
) -> Agent:
    """
    Create a simple Agno agent with the LLM Proxy model.
    
    This is a convenience function for creating basic agents without
    needing to configure the model separately.
    
    Args:
        model_id: Override the default model ID
        name: Agent name (for logging/debugging)
        description: Agent description
        instructions: List of instruction strings for the agent
        markdown: Whether to format responses as markdown (default: True)
        
    Returns:
        Configured Agno Agent instance
        
    Example:
        >>> agent = create_simple_agent(name="Helper")
        >>> response = agent.run("What is the capital of France?")
        >>> print(response.content)
    """
    model = get_model(model_id=model_id)
    
    return Agent(
        model=model,
        name=name,
        description=description,
        instructions=instructions or [],
        markdown=markdown,
    )


def verify_llm_connectivity() -> dict:
    """
    Verify connectivity to the LLM Proxy.
    
    Sends a simple test message to verify the LLM Proxy is accessible
    and responding correctly.
    
    Returns:
        dict with keys:
            - success: bool indicating if test passed
            - message: Human-readable status message
            - response: LLM response content (if successful)
            - error: Error message (if failed)
            
    Example:
        >>> result = verify_llm_connectivity()
        >>> if result["success"]:
        ...     print("LLM Proxy is working!")
        ... else:
        ...     print(f"Error: {result['error']}")
    """
    try:
        agent = create_simple_agent(
            name="ConnectivityTest",
            description="Test agent for verifying LLM connectivity",
        )
        
        # Send a simple test message
        response = agent.run("Say 'Hello from Agno!' and nothing else.")
        
        content = response.content if hasattr(response, 'content') else str(response)
        
        return {
            "success": True,
            "message": "LLM Proxy connectivity verified successfully",
            "response": content,
        }
        
    except ValueError as e:
        # Configuration error (missing API key)
        return {
            "success": False,
            "message": "Configuration error",
            "error": str(e),
        }
    except Exception as e:
        # Connection or other error
        return {
            "success": False,
            "message": "Failed to connect to LLM Proxy",
            "error": str(e),
        }


# Module-level check for LLM availability (non-blocking)
def is_agno_available() -> bool:
    """
    Check if Agno features are available (API key is configured).
    
    This is a quick check that doesn't make any network calls.
    Use verify_llm_connectivity() for a full connectivity test.
    
    Returns:
        True if LLM_PROXY_API_KEY is set, False otherwise
    """
    return Config.llm_enabled()
