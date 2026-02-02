"""
Utils package for the Elastic Crawler Service.

This package contains shared utilities:
- config: Environment-based configuration management
- llm_client: LLM proxy client for chat completions
"""

from .config import config
from .llm_client import LLMClient

__all__ = ["config", "LLMClient"]
