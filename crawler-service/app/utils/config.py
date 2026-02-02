"""
Configuration management for the Elastic Crawler Service.

Loads environment variables from .env file using python-dotenv with override=True
to ensure local variables take precedence.

Environment Variables:
    LLM_PROXY_BASE_URL: Base URL for LLM proxy service (OpenAI-compatible, e.g., .../v1)
    LLM_PROXY_URL: Full URL for LLM proxy chat completions (legacy, for direct httpx calls)
    LLM_PROXY_API_KEY: API key for LLM proxy
    LLM_MODEL: Model name to use (default: claude-sonnet-4)
    ES_URL: Elasticsearch URL
    ES_API_KEY: Elasticsearch API key
    ES_CLOUD_ID: Elasticsearch Cloud ID (alternative to ES_URL)
    PORT: Server port (default: 8000)
    ENVIRONMENT: Environment name (default: development)
"""

import os
from typing import Optional

from dotenv import load_dotenv

# Load environment variables with override=True to ensure local vars take precedence
load_dotenv(override=True)


class Config:
    """Application configuration loaded from environment variables."""

    # LLM Proxy Configuration
    # Base URL for Agno (OpenAILike) - should end with /v1
    LLM_PROXY_BASE_URL: str = os.getenv(
        "LLM_PROXY_BASE_URL",
        "https://litellm-proxy-service-1059491012611.us-central1.run.app/v1",
    )
    # Full URL for direct httpx calls (legacy llm_client.py)
    LLM_PROXY_URL: str = os.getenv(
        "LLM_PROXY_URL",
        "https://litellm-proxy-service-1059491012611.us-central1.run.app/v1/chat/completions",
    )
    LLM_PROXY_API_KEY: str = os.getenv("LLM_PROXY_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-sonnet-4")

    # Elasticsearch Configuration
    ES_URL: Optional[str] = os.getenv("ES_URL")
    ES_API_KEY: Optional[str] = os.getenv("ES_API_KEY")
    ES_CLOUD_ID: Optional[str] = os.getenv("ES_CLOUD_ID")

    # Backend Configuration
    PORT: int = int(os.getenv("PORT", "8000"))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    @classmethod
    def validate(cls) -> list[str]:
        """
        Validate required configuration values.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # LLM proxy is optional (only needed for config generation)
        if not cls.LLM_PROXY_API_KEY:
            errors.append("LLM_PROXY_API_KEY not set - config generation features disabled")
        
        return errors
    
    @classmethod
    def llm_enabled(cls) -> bool:
        """Check if LLM features are enabled (API key is set)."""
        return bool(cls.LLM_PROXY_API_KEY)


# Global config instance
config = Config()
