"""
LLM Proxy client for OpenAI-compatible API calls.

Provides streaming chat completions via the Elastic LLM Proxy service.
Supports function calling for structured agent outputs.
"""

import json
from typing import AsyncIterator

import httpx

from utils.config import Config


class LLMClient:
    """
    Client for LLM Proxy (OpenAI-compatible).
    
    Usage:
        client = LLMClient()
        async for chunk in client.chat_completion(messages):
            print(chunk)
    """
    
    def __init__(self):
        """Initialize LLM client with configuration from environment."""
        self.base_url = Config.LLM_PROXY_URL
        self.api_key = Config.LLM_PROXY_API_KEY
        self.model = Config.LLM_MODEL
        
        if not self.api_key:
            raise ValueError(
                "LLM_PROXY_API_KEY must be set. "
                "Config generation features require an LLM proxy."
            )
    
    async def chat_completion(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = True,
        temperature: float = 0.7,
    ) -> AsyncIterator[dict]:
        """
        Call LLM Proxy chat completion endpoint with streaming.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tool definitions for tool calling (modern format)
                   Format: [{"type": "function", "function": {...}}]
            stream: Whether to stream responses (default: True)
            temperature: Sampling temperature (default: 0.7)
            
        Yields:
            Response chunks from the LLM in OpenAI format:
            {
                "choices": [{
                    "delta": {"content": "..."},
                    "finish_reason": null | "stop"
                }]
            }
            
        Raises:
            httpx.HTTPStatusError: If the API returns an error
            ValueError: If LLM is not configured
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
        }
        
        # Use modern 'tools' format (supported by Bedrock/Claude)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                self.base_url,
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        if data == "[DONE]":
                            break
                        
                        try:
                            chunk = json.loads(data)
                            yield chunk
                        except json.JSONDecodeError:
                            continue
