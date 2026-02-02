#!/usr/bin/env python3
"""
Test script to verify Agno framework connectivity with the LLM Proxy.

This script can be run standalone to verify that:
1. The Agno package is installed correctly
2. The LLM Proxy is accessible
3. The model responds correctly

Usage:
    cd elastic-crawler-control/crawler-service/app
    python test_agno_connectivity.py

Requirements:
    - LLM_PROXY_API_KEY must be set in .env or environment
    - LLM_PROXY_BASE_URL should point to the LLM Proxy /v1 endpoint
"""

import sys
from pathlib import Path

# Add the app directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.agno_model import (
    get_model,
    create_simple_agent,
    verify_llm_connectivity,
    is_agno_available,
)
from utils.config import Config


def print_separator(title: str = "") -> None:
    """Print a visual separator line."""
    if title:
        print(f"\n{'='*60}")
        print(f" {title}")
        print(f"{'='*60}")
    else:
        print(f"\n{'-'*60}")


def main() -> int:
    """Run Agno connectivity tests."""
    print_separator("Agno Framework Connectivity Test")
    
    # Step 1: Check configuration
    print("\n1. Checking configuration...")
    print(f"   LLM_PROXY_BASE_URL: {Config.LLM_PROXY_BASE_URL}")
    print(f"   LLM_MODEL: {Config.LLM_MODEL}")
    print(f"   API Key configured: {'Yes' if is_agno_available() else 'No'}")
    
    if not is_agno_available():
        print("\n   ERROR: LLM_PROXY_API_KEY is not set!")
        print("   Please set it in your .env file or environment.")
        print("   Get your key at: https://sa-workshops.prod-3.eden.elastic.dev/LLM_Key_Generator")
        return 1
    
    # Step 2: Test model instantiation
    print_separator()
    print("2. Testing model instantiation...")
    try:
        model = get_model()
        print(f"   SUCCESS: Model created: {model.id}")
        print(f"   Base URL: {model.base_url}")
    except Exception as e:
        print(f"   ERROR: Failed to create model: {e}")
        return 1
    
    # Step 3: Test agent creation
    print_separator()
    print("3. Testing agent creation...")
    try:
        agent = create_simple_agent(
            name="TestAgent",
            description="A test agent for connectivity verification",
        )
        print(f"   SUCCESS: Agent created: {agent.name}")
    except Exception as e:
        print(f"   ERROR: Failed to create agent: {e}")
        return 1
    
    # Step 4: Test LLM connectivity with a real request
    print_separator()
    print("4. Testing LLM connectivity (making actual API call)...")
    print("   This may take a few seconds...")
    
    result = verify_llm_connectivity()
    
    if result["success"]:
        print(f"\n   SUCCESS: {result['message']}")
        print(f"   LLM Response: {result['response'][:100]}..." if len(result.get('response', '')) > 100 else f"   LLM Response: {result.get('response', 'N/A')}")
    else:
        print(f"\n   ERROR: {result['message']}")
        print(f"   Details: {result.get('error', 'Unknown error')}")
        return 1
    
    # Step 5: Test a more complex interaction
    print_separator()
    print("5. Testing structured interaction...")
    try:
        agent = create_simple_agent(
            name="StructuredTestAgent",
            description="An agent for testing structured responses",
            instructions=["Always respond in a helpful and concise manner"],
        )
        
        response = agent.run("What is 2 + 2? Reply with just the number.")
        content = response.content if hasattr(response, 'content') else str(response)
        print(f"   Question: What is 2 + 2?")
        print(f"   Response: {content}")
        print("   SUCCESS: Structured interaction works!")
    except Exception as e:
        print(f"   ERROR: Structured interaction failed: {e}")
        return 1
    
    print_separator("All Tests Passed!")
    print("\nAgno framework is correctly configured and connected to the LLM Proxy.")
    print("You can now use Agno agents in your application.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
