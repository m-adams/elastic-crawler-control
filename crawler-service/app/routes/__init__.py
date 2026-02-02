"""
Routes package for the Elastic Crawler Service.

This package contains modular route definitions:
- crawl: Crawl management endpoints (trigger, status, cancel, list)
- health: Health check endpoint
- chat: LLM-powered config generation chat endpoint
"""

from . import crawl, health, chat

__all__ = ["crawl", "health", "chat"]
