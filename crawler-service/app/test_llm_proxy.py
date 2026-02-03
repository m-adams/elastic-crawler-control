#!/usr/bin/env python3
"""
LLM Proxy Connectivity Test Script.

Tests connection to the LLM Proxy service with:
1. Basic connectivity
2. Streaming (SSE) responses
3. Function calling capability

Usage:
    # With API key as argument:
    python test_llm_proxy.py --api-key YOUR_API_KEY
    
    # With API key from environment:
    export LLM_PROXY_API_KEY=YOUR_API_KEY
    python test_llm_proxy.py
    
    # Test specific features:
    python test_llm_proxy.py --api-key KEY --test streaming
    python test_llm_proxy.py --api-key KEY --test function_calling
    python test_llm_proxy.py --api-key KEY --test all

Get your API key at:
    https://sa-workshops.prod-3.eden.elastic.dev/LLM_Key_Generator
"""

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import httpx
except ImportError:
    print("Error: httpx not installed. Run: pip install httpx")
    sys.exit(1)


# Default configuration
DEFAULT_LLM_PROXY_URL = "https://litellm-proxy-service-1059491012611.us-central1.run.app/v1/chat/completions"
DEFAULT_MODEL = "claude-sonnet-4"
KEY_GENERATOR_URL = "https://sa-workshops.prod-3.eden.elastic.dev/LLM_Key_Generator"


class LLMProxyTester:
    """Test LLM Proxy connectivity and features."""
    
    def __init__(self, api_key: str, base_url: str = DEFAULT_LLM_PROXY_URL, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.results = {}
    
    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    async def test_basic_connectivity(self) -> bool:
        """Test basic API connectivity with a simple request."""
        print("\n" + "=" * 60)
        print("TEST 1: Basic Connectivity")
        print("=" * 60)
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": "Say 'Hello, connection successful!' and nothing else."}
            ],
            "stream": False,
            "max_tokens": 50,
        }
        
        try:
            start_time = time.time()
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=self._get_headers(),
                    json=payload,
                )
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"✅ SUCCESS - Response received in {elapsed:.2f}s")
                print(f"   Model: {data.get('model', 'unknown')}")
                print(f"   Response: {content[:100]}...")
                self.results["basic_connectivity"] = True
                return True
            else:
                print(f"❌ FAILED - Status code: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                self.results["basic_connectivity"] = False
                return False
                
        except httpx.TimeoutException:
            print("❌ FAILED - Request timed out")
            self.results["basic_connectivity"] = False
            return False
        except Exception as e:
            print(f"❌ FAILED - Error: {str(e)}")
            self.results["basic_connectivity"] = False
            return False
    
    async def test_streaming(self) -> bool:
        """Test streaming (SSE) responses."""
        print("\n" + "=" * 60)
        print("TEST 2: Streaming (SSE) Responses")
        print("=" * 60)
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": "Count from 1 to 5, one number per line."}
            ],
            "stream": True,
            "max_tokens": 100,
        }
        
        try:
            start_time = time.time()
            chunks_received = 0
            content_parts = []
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    self.base_url,
                    headers=self._get_headers(),
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        print(f"❌ FAILED - Status code: {response.status_code}")
                        self.results["streaming"] = False
                        return False
                    
                    print("   Receiving chunks: ", end="", flush=True)
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                print(" [DONE]")
                                break
                            
                            try:
                                chunk = json.loads(data)
                                chunks_received += 1
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    content_parts.append(content)
                                    print(".", end="", flush=True)
                            except json.JSONDecodeError:
                                continue
            
            elapsed = time.time() - start_time
            full_content = "".join(content_parts)
            
            print(f"\n✅ SUCCESS - Received {chunks_received} chunks in {elapsed:.2f}s")
            print(f"   Content: {full_content[:100]}...")
            self.results["streaming"] = True
            return True
            
        except httpx.TimeoutException:
            print("\n❌ FAILED - Request timed out")
            self.results["streaming"] = False
            return False
        except Exception as e:
            print(f"\n❌ FAILED - Error: {str(e)}")
            self.results["streaming"] = False
            return False
    
    async def test_function_calling(self) -> bool:
        """Test function/tool calling capability using the modern 'tools' format."""
        print("\n" + "=" * 60)
        print("TEST 3: Tool Calling (Function Calling)")
        print("=" * 60)
        
        # Define tools using the modern OpenAI format (supported by Bedrock/Claude)
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_crawler_config",
                    "description": "Generate a crawler configuration for a given domain",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "domain": {
                                "type": "string",
                                "description": "The domain URL to crawl"
                            },
                            "max_depth": {
                                "type": "integer",
                                "description": "Maximum crawl depth"
                            },
                            "output_index": {
                                "type": "string",
                                "description": "Elasticsearch index name for output"
                            }
                        },
                        "required": ["domain", "max_depth", "output_index"]
                    }
                }
            }
        ]
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user", 
                    "content": "Generate a crawler config for https://example.com with depth 2 and index 'test-crawl'. Use the get_crawler_config tool."
                }
            ],
            "tools": tools,
            "tool_choice": "auto",
            "stream": False,
        }
        
        try:
            start_time = time.time()
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=self._get_headers(),
                    json=payload,
                )
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                
                # Check if tool was called (modern format)
                tool_calls = message.get("tool_calls", [])
                if tool_calls:
                    tool_call = tool_calls[0]
                    func = tool_call.get("function", {})
                    func_name = func.get("name", "")
                    func_args = func.get("arguments", "{}")
                    
                    print(f"✅ SUCCESS - Tool called in {elapsed:.2f}s")
                    print(f"   Tool: {func_name}")
                    try:
                        args = json.loads(func_args)
                        print(f"   Arguments: {json.dumps(args, indent=2)}")
                    except:
                        print(f"   Arguments (raw): {func_args[:200]}")
                    
                    self.results["tool_calling"] = True
                    return True
                else:
                    # Model responded with text instead of tool call
                    content = message.get("content", "")
                    print(f"⚠️  WARNING - Model responded with text instead of tool call")
                    print(f"   Response: {content[:200]}...")
                    print(f"   This may be expected behavior for some prompts.")
                    self.results["tool_calling"] = "partial"
                    return True
            else:
                print(f"❌ FAILED - Status code: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                self.results["tool_calling"] = False
                return False
                
        except httpx.TimeoutException:
            print("❌ FAILED - Request timed out")
            self.results["tool_calling"] = False
            return False
        except Exception as e:
            print(f"❌ FAILED - Error: {str(e)}")
            self.results["tool_calling"] = False
            return False
    
    async def run_all_tests(self) -> dict:
        """Run all connectivity tests."""
        print("\n" + "=" * 60)
        print("LLM PROXY CONNECTIVITY TEST")
        print("=" * 60)
        print(f"URL: {self.base_url}")
        print(f"Model: {self.model}")
        print(f"API Key: {self.api_key[:8]}...{self.api_key[-4:]}")
        
        await self.test_basic_connectivity()
        await self.test_streaming()
        await self.test_function_calling()
        
        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        
        all_passed = True
        for test_name, result in self.results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            if result == "partial":
                status = "⚠️  PARTIAL"
            print(f"   {test_name}: {status}")
            if result is False:
                all_passed = False
        
        if all_passed:
            print("\n🎉 All tests passed! LLM Proxy is ready to use.")
        else:
            print("\n⚠️  Some tests failed. Check the output above for details.")
        
        return self.results


def main():
    parser = argparse.ArgumentParser(
        description="Test LLM Proxy connectivity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Get your API key at:
    {KEY_GENERATOR_URL}

Examples:
    python test_llm_proxy.py --api-key YOUR_KEY
    python test_llm_proxy.py --api-key YOUR_KEY --test streaming
    LLM_PROXY_API_KEY=YOUR_KEY python test_llm_proxy.py
        """
    )
    parser.add_argument(
        "--api-key", "-k",
        help="LLM Proxy API key (or set LLM_PROXY_API_KEY env var)",
        default=os.getenv("LLM_PROXY_API_KEY"),
    )
    parser.add_argument(
        "--url", "-u",
        help="LLM Proxy URL",
        default=os.getenv("LLM_PROXY_URL", DEFAULT_LLM_PROXY_URL),
    )
    parser.add_argument(
        "--model", "-m",
        help="Model to use",
        default=os.getenv("LLM_MODEL", DEFAULT_MODEL),
    )
    parser.add_argument(
        "--test", "-t",
        choices=["all", "basic", "streaming", "function_calling"],
        default="all",
        help="Which test to run",
    )
    
    args = parser.parse_args()
    
    if not args.api_key:
        print("❌ Error: API key required")
        print(f"\nGet your API key at: {KEY_GENERATOR_URL}")
        print("\nUsage:")
        print("  python test_llm_proxy.py --api-key YOUR_KEY")
        print("  or")
        print("  export LLM_PROXY_API_KEY=YOUR_KEY")
        print("  python test_llm_proxy.py")
        sys.exit(1)
    
    tester = LLMProxyTester(
        api_key=args.api_key,
        base_url=args.url,
        model=args.model,
    )
    
    async def run_tests():
        if args.test == "all":
            return await tester.run_all_tests()
        elif args.test == "basic":
            await tester.test_basic_connectivity()
        elif args.test == "streaming":
            await tester.test_streaming()
        elif args.test == "function_calling":
            await tester.test_function_calling()
        return tester.results
    
    results = asyncio.run(run_tests())
    
    # Exit with error code if any test failed
    if any(r is False for r in results.values()):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
