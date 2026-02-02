"""
Chat endpoint with SSE streaming for LLM-powered config generation.

Follows A2A Coordinator Pattern from hive-mind for streaming LLM responses.
Accepts structured input and streams workflow progress via Server-Sent Events.
"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from models import ConfigGenerationRequest, DomainInput
from utils.config import Config
from utils.llm_client import LLMClient

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat_endpoint(request: ConfigGenerationRequest):
    """
    Main chat endpoint for LLM-powered config generation workflows.
    
    Accepts structured form input and streams workflow progress via SSE.
    
    Workflow phases:
    1. Initial Validation & Setup
    2. Site Investigation  
    3. User Confirmation - Investigation Results
    4. Config Generation
    5. User Confirmation - Config Preview
    6. Config Validation
    7. Iteration Loop (if needed)
    8. Final Output
    
    Args:
        request: ConfigGenerationRequest with domains, demo scenario, etc.
        
    Returns:
        StreamingResponse with SSE events:
        - event: progress - Workflow status updates
        - event: content - LLM response content chunks
        - event: done - Stream completion signal
        - event: error - Error information
    """
    # Check if LLM is enabled
    if not Config.llm_enabled():
        raise HTTPException(
            status_code=503,
            detail="LLM features not available. Set LLM_PROXY_API_KEY to enable."
        )
    
    client = LLMClient()
    
    # Build context from structured input
    crawl_scope_list = []
    for domain in request.domains:
        crawl_scope_list.append(f"  Domain: {domain.url}")
        if domain.seed_urls:
            crawl_scope_list.append("  Seed URLs:")
            crawl_scope_list.extend([f"    - {url}" for url in domain.seed_urls])
        if domain.path_pattern:
            crawl_scope_list.append(f"  Path Pattern: {domain.path_pattern}")
    
    content_types = ", ".join([ct.value for ct in request.expected_content_types]) if request.expected_content_types else "Not specified"
    
    # Create initial system message and user request
    messages = [
        {
            "role": "system",
            "content": """You are an expert AI assistant helping to generate Elastic Open Crawler configurations.
You follow best practices from the hive-mind knowledge base:
- Start with file/console output for testing
- Use shallow crawl depth initially (1-2)
- Reference extraction pattern library for common fields
- Respect robots.txt and sitemaps
- Generate configs that follow Open Crawler v0.4.2 patterns

Provide clear, step-by-step guidance and explain your reasoning."""
        },
        {
            "role": "user",
            "content": f"""I want to generate an Open Crawler configuration.

Domains and Crawl Scope:
{chr(10).join(crawl_scope_list)}

Demo Scenario: {request.demo_scenario}

Content Focus: {request.content_focus}

Expected Content Types: {content_types}
{f"Specific Fields Needed: {', '.join(request.specific_fields)}" if request.specific_fields else ""}
{f"Crawl Depth Preference: {request.crawl_depth_preference}" if request.crawl_depth_preference else ""}
{f"Output Index: {request.output_index}" if request.output_index else ""}
{f"Additional Notes: {request.notes}" if request.notes else ""}

Please explain the workflow we'll follow to generate a tested, validated crawler configuration.
Focus on the phases: investigation, generation, validation, and iteration."""
        }
    ]
    
    async def event_generator():
        """Generate SSE events from LLM streaming."""
        try:
            # Send initial progress event
            yield f"event: progress\n"
            yield f"data: {json.dumps({'step': 'initializing', 'message': 'Connecting to LLM...'})}\n\n"
            
            # Stream LLM response
            async for chunk in client.chat_completion(messages=messages, stream=True):
                if "choices" in chunk and len(chunk["choices"]) > 0:
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    
                    if content:
                        # Send content chunk as SSE event
                        yield f"event: content\n"
                        yield f"data: {json.dumps({'content': content})}\n\n"
                    
                    # Check for completion
                    finish_reason = chunk["choices"][0].get("finish_reason")
                    if finish_reason:
                        yield f"event: done\n"
                        yield f"data: {json.dumps({'reason': finish_reason, 'message': 'Stream completed'})}\n\n"
                        break
            
            # Send final event with summary
            domains_str = ", ".join([d.url for d in request.domains])
            yield f"event: complete\n"
            yield f"data: {json.dumps({'message': 'Workflow completed', 'domains': domains_str, 'demo_scenario': request.demo_scenario})}\n\n"
            
        except Exception as e:
            # Send error event
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': str(e), 'message': 'An error occurred during processing'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering for nginx
        }
    )


@router.get("/chat/status")
async def chat_status():
    """
    Check if chat/LLM features are available.
    
    Returns:
        Status of LLM configuration
    """
    return {
        "enabled": Config.llm_enabled(),
        "model": Config.LLM_MODEL if Config.llm_enabled() else None,
        "message": "LLM features available" if Config.llm_enabled() else "Set LLM_PROXY_API_KEY to enable",
        "key_generator_url": "https://sa-workshops.prod-3.eden.elastic.dev/LLM_Key_Generator",
    }


@router.post("/chat/test")
async def test_llm_connection():
    """
    Test LLM Proxy connectivity.
    
    Performs a quick connectivity test to verify the LLM proxy is working.
    
    Returns:
        Test results including status, response time, and model info
    """
    import time
    
    if not Config.llm_enabled():
        return {
            "success": False,
            "error": "LLM not configured",
            "message": "Set LLM_PROXY_API_KEY to enable LLM features",
            "key_generator_url": "https://sa-workshops.prod-3.eden.elastic.dev/LLM_Key_Generator",
        }
    
    try:
        client = LLMClient()
        
        messages = [
            {"role": "user", "content": "Say 'Connection successful!' and nothing else."}
        ]
        
        start_time = time.time()
        response_content = ""
        
        async for chunk in client.chat_completion(messages=messages, stream=True):
            if "choices" in chunk and len(chunk["choices"]) > 0:
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    response_content += content
        
        elapsed = time.time() - start_time
        
        return {
            "success": True,
            "response_time_seconds": round(elapsed, 2),
            "model": Config.LLM_MODEL,
            "response": response_content.strip(),
            "message": "LLM Proxy connection successful",
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "model": Config.LLM_MODEL,
            "message": "LLM Proxy connection failed",
        }
