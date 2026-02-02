"""
Utils package for the Elastic Crawler Service.

This package contains shared utilities:
- config: Environment-based configuration management
- llm_client: LLM proxy client for chat completions (legacy, direct httpx)
- agno_model: Agno framework model provider for AI agents
"""

from .config import config
from .llm_client import LLMClient
from .agno_model import get_model, create_simple_agent, verify_llm_connectivity, is_agno_available

__all__ = [
    "config",
    "LLMClient",
    # Agno utilities
    "get_model",
    "create_simple_agent",
    "verify_llm_connectivity",
    "is_agno_available",
]
