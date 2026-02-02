"""
Routes package for the Elastic Crawler Service.

This package contains modular route definitions:
- crawl: Crawl management endpoints (trigger, status, cancel, list)
- health: Health check endpoint
- chat: LLM-powered config generation chat endpoint (legacy)
- workflow: Agno-powered config generation workflow with SSE streaming
"""

from . import crawl, health, chat, workflow

__all__ = ["crawl", "health", "chat", "workflow"]
