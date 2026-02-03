"""
Open Crawler Client

Client for interacting with the Open Crawler binary.
Wraps validate, urltest, and crawl commands.

**Important**: This uses the REAL crawler binary, not simulations.

Usage:
    from utils.crawler_client import CrawlerClient
    
    client = CrawlerClient()
    
    # Validate a config
    result = await client.validate(config_dict)
    
    # Test extraction on a single URL
    result = await client.urltest(config_dict, "https://example.com/page")
    
    # Run a full crawl
    result = await client.crawl(config_dict)
"""

import asyncio
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class ValidationResult:
    """Result from bin/crawler validate."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    raw_output: str = ""
    return_code: int = 0


@dataclass
class UrlTestResult:
    """Result from bin/crawler urltest."""
    success: bool
    url: str
    extracted_document: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    raw_output: str = ""
    return_code: int = 0
    
    # Crawlability info
    blocked: bool = False
    block_reason: Optional[str] = None


@dataclass
class CrawlResult:
    """Result from bin/crawler crawl."""
    success: bool
    pages_visited: int = 0
    documents_indexed: int = 0
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    raw_output: str = ""
    return_code: int = 0


class CrawlerClient:
    """
    Client for Open Crawler binary commands.
    
    Uses the actual crawler at /crawler/bin/crawler.
    All methods run real commands, no mocking.
    """
    
    def __init__(
        self,
        crawler_path: str = "/crawler",
        timeout_seconds: int = 120,
    ):
        """
        Initialize crawler client.
        
        Args:
            crawler_path: Path to Open Crawler installation
            timeout_seconds: Default timeout for commands
        """
        self.crawler_path = crawler_path
        self.bin_path = os.path.join(crawler_path, "bin", "crawler")
        self.timeout_seconds = timeout_seconds
    
    def is_available(self) -> bool:
        """Check if Open Crawler binary is available."""
        return os.path.exists(self.bin_path)
    
    async def _run_command(
        self,
        args: List[str],
        timeout: Optional[int] = None,
    ) -> tuple[int, str, str]:
        """
        Run a crawler command.
        
        Args:
            args: Command arguments (e.g., ["validate", "config.yml"])
            timeout: Command timeout in seconds
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        if not self.is_available():
            raise RuntimeError(
                f"Open Crawler not found at {self.bin_path}. "
                "Ensure Open Crawler is installed and CRAWLER_PATH is correct."
            )
        
        timeout = timeout or self.timeout_seconds
        
        # Build full command
        cmd = ["jruby", self.bin_path] + args
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.crawler_path,
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
            
            return (
                process.returncode or 0,
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
            )
            
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise TimeoutError(f"Crawler command timed out after {timeout}s: {' '.join(args)}")
    
    def _write_temp_config(self, config: Dict[str, Any]) -> str:
        """Write config to temporary file and return path."""
        config_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yml",
            delete=False,
            dir="/tmp",
        )
        yaml.dump(config, config_file, default_flow_style=False)
        config_file.close()
        return config_file.name
    
    def _cleanup_temp_config(self, config_path: str):
        """Remove temporary config file."""
        try:
            if os.path.exists(config_path):
                os.unlink(config_path)
        except Exception:
            pass
    
    async def validate(self, config: Dict[str, Any]) -> ValidationResult:
        """
        Validate a crawler config.
        
        Runs: bin/crawler validate config.yml
        
        Args:
            config: Crawler configuration dict
            
        Returns:
            ValidationResult with errors/warnings
        """
        config_path = self._write_temp_config(config)
        
        try:
            return_code, stdout, stderr = await self._run_command(
                ["validate", config_path],
                timeout=30,
            )
            
            output = stdout + stderr
            
            # Parse validation output
            errors = []
            warnings = []
            
            for line in output.split("\n"):
                line_lower = line.lower()
                if "error" in line_lower:
                    errors.append(line.strip())
                elif "warning" in line_lower:
                    warnings.append(line.strip())
                elif "invalid" in line_lower:
                    errors.append(line.strip())
            
            # Check for specific validation errors
            if "missing required" in output.lower():
                # Extract missing field
                match = re.search(r"missing required[^:]*:\s*(\w+)", output, re.I)
                if match:
                    errors.append(f"Missing required field: {match.group(1)}")
            
            valid = return_code == 0 and len(errors) == 0
            
            return ValidationResult(
                valid=valid,
                errors=errors,
                warnings=warnings,
                raw_output=output,
                return_code=return_code,
            )
            
        finally:
            self._cleanup_temp_config(config_path)
    
    def _read_crawled_doc(self) -> Optional[Dict[str, Any]]:
        """
        Read the extracted document from crawled_docs directory.
        
        The urltest command saves documents to ./crawled_docs/{domain}.json
        relative to the crawler_path.
        """
        crawled_docs_dir = os.path.join(self.crawler_path, "crawled_docs")
        
        if not os.path.exists(crawled_docs_dir):
            return None
        
        # Find the most recent JSON file
        json_files = [
            f for f in os.listdir(crawled_docs_dir) 
            if f.endswith(".json")
        ]
        
        if not json_files:
            return None
        
        # Read the first (should be only) JSON file
        json_path = os.path.join(crawled_docs_dir, json_files[0])
        try:
            with open(json_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    
    def _cleanup_crawled_docs(self):
        """Remove all files from crawled_docs directory."""
        crawled_docs_dir = os.path.join(self.crawler_path, "crawled_docs")
        
        if os.path.exists(crawled_docs_dir):
            for f in os.listdir(crawled_docs_dir):
                try:
                    os.unlink(os.path.join(crawled_docs_dir, f))
                except Exception:
                    pass

    async def urltest(
        self,
        config: Dict[str, Any],
        url: str,
    ) -> UrlTestResult:
        """
        Test extraction on a single URL.
        
        Runs: bin/crawler urltest config.yml URL
        
        The crawler saves the extracted document to ./crawled_docs/{domain}.json
        
        Args:
            config: Crawler configuration dict
            url: URL to test
            
        Returns:
            UrlTestResult with extracted document or error
        """
        config_path = self._write_temp_config(config)
        
        # Clean up any previous crawled docs
        self._cleanup_crawled_docs()
        
        try:
            return_code, stdout, stderr = await self._run_command(
                ["urltest", config_path, url],
                timeout=30,  # Reduced from 60s to avoid blocking workflow
            )
            
            output = stdout + stderr
            
            # Check for common block indicators
            blocked = False
            block_reason = None
            
            if self._detect_blocked(output, return_code):
                blocked = True
                block_reason = self._identify_block_reason(output)
            
            # Try to read extracted document from crawled_docs/
            extracted_doc = None
            error = None
            
            if return_code == 0 and not blocked:
                # Read document from crawled_docs directory
                extracted_doc = self._read_crawled_doc()
                
                # Fallback: try to parse from output (older versions)
                if not extracted_doc:
                    extracted_doc = self._parse_urltest_output(output)
                
                if not extracted_doc:
                    error = "No document extracted - check extraction rules"
            else:
                # Extract error message
                error = self._extract_error_message(output)
            
            return UrlTestResult(
                success=return_code == 0 and not blocked and extracted_doc is not None,
                url=url,
                extracted_document=extracted_doc,
                error=error,
                raw_output=output,
                return_code=return_code,
                blocked=blocked,
                block_reason=block_reason,
            )
            
        finally:
            self._cleanup_temp_config(config_path)
            self._cleanup_crawled_docs()
    
    async def urltest_batch(
        self,
        config: Dict[str, Any],
        urls: List[str],
        stop_on_error: bool = False,
    ) -> List[UrlTestResult]:
        """
        Test extraction on multiple URLs.
        
        Args:
            config: Crawler configuration dict
            urls: List of URLs to test
            stop_on_error: Stop on first error
            
        Returns:
            List of UrlTestResult for each URL
        """
        results = []
        
        for url in urls:
            result = await self.urltest(config, url)
            results.append(result)
            
            if stop_on_error and not result.success:
                break
        
        return results
    
    async def crawl(
        self,
        config: Dict[str, Any],
        timeout: Optional[int] = None,
    ) -> CrawlResult:
        """
        Run a full crawl.
        
        Runs: bin/crawler crawl config.yml
        
        Args:
            config: Crawler configuration dict
            timeout: Crawl timeout (default: 3300s / 55min)
            
        Returns:
            CrawlResult with statistics
        """
        config_path = self._write_temp_config(config)
        timeout = timeout or 3300
        
        try:
            return_code, stdout, stderr = await self._run_command(
                ["crawl", config_path],
                timeout=timeout,
            )
            
            output = stdout + stderr
            
            # Parse crawl stats
            pages_visited = 0
            documents_indexed = 0
            duration_seconds = 0.0
            errors = []
            
            for line in output.split("\n"):
                if "Pages visited:" in line:
                    try:
                        pages_visited = int(line.split(":")[-1].strip())
                    except ValueError:
                        pass
                elif "Documents upserted:" in line:
                    try:
                        documents_indexed = int(line.split(":")[-1].strip())
                    except ValueError:
                        pass
                elif "Crawl duration" in line:
                    try:
                        duration_seconds = float(line.split(":")[-1].strip().replace("s", ""))
                    except ValueError:
                        pass
                elif "error" in line.lower():
                    errors.append(line.strip())
            
            return CrawlResult(
                success=return_code == 0,
                pages_visited=pages_visited,
                documents_indexed=documents_indexed,
                duration_seconds=duration_seconds,
                errors=errors,
                raw_output=output,
                return_code=return_code,
            )
            
        finally:
            self._cleanup_temp_config(config_path)
    
    def _parse_urltest_output(self, output: str) -> Optional[Dict[str, Any]]:
        """
        Parse extracted document from urltest output.
        
        The crawler outputs JSON for the extracted document.
        """
        # Look for JSON in output
        # Crawler typically outputs the document as JSON
        json_patterns = [
            r'\{[^{}]*"url"[^{}]*\}',  # Simple JSON with url field
            r'\{[\s\S]*\}',  # Any JSON object
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, output)
            for match in matches:
                try:
                    doc = json.loads(match)
                    # Verify it looks like an extracted document
                    if isinstance(doc, dict) and ("url" in doc or "title" in doc or "body" in doc):
                        return doc
                except json.JSONDecodeError:
                    continue
        
        # Try to find document markers
        if "Extracted document:" in output:
            doc_start = output.find("Extracted document:")
            remaining = output[doc_start:]
            # Look for JSON after marker
            json_match = re.search(r'\{[\s\S]*\}', remaining)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
        
        return None
    
    def _detect_blocked(self, output: str, return_code: int) -> bool:
        """Detect if the request was blocked."""
        output_lower = output.lower()
        
        block_indicators = [
            "access denied",
            "403 forbidden",
            "captcha",
            "cloudflare",
            "bot detection",
            "rate limit",
            "too many requests",
            "blocked",
            "robot check",
        ]
        
        for indicator in block_indicators:
            if indicator in output_lower:
                return True
        
        # Non-zero return code with error indicators
        if return_code != 0:
            if "failed to fetch" in output_lower or "connection refused" in output_lower:
                return True
        
        return False
    
    def _identify_block_reason(self, output: str) -> str:
        """Identify the specific reason for blocking."""
        output_lower = output.lower()
        
        if "cloudflare" in output_lower:
            return "Cloudflare protection detected"
        if "captcha" in output_lower:
            return "CAPTCHA challenge required"
        if "403" in output_lower or "forbidden" in output_lower:
            return "Access forbidden (403)"
        if "rate limit" in output_lower or "too many" in output_lower:
            return "Rate limited"
        if "robot" in output_lower and "check" in output_lower:
            return "Bot/robot check required"
        if "access denied" in output_lower:
            return "Access denied"
        
        return "Site blocked request"
    
    def _extract_error_message(self, output: str) -> str:
        """Extract a meaningful error message from output."""
        lines = output.split("\n")
        
        for line in lines:
            line_lower = line.lower()
            if "error" in line_lower or "failed" in line_lower:
                return line.strip()
        
        # Return last non-empty line as fallback
        for line in reversed(lines):
            if line.strip():
                return line.strip()[:200]
        
        return "Unknown error"


# Singleton instance
_client: Optional[CrawlerClient] = None


def get_crawler_client() -> CrawlerClient:
    """Get or create the crawler client singleton."""
    global _client
    
    if _client is None:
        crawler_path = os.environ.get("CRAWLER_PATH", "/crawler")
        _client = CrawlerClient(crawler_path=crawler_path)
    
    return _client


# Convenience functions
async def validate_config(config: Dict[str, Any]) -> ValidationResult:
    """Validate a crawler config."""
    return await get_crawler_client().validate(config)


async def test_url(config: Dict[str, Any], url: str) -> UrlTestResult:
    """Test extraction on a single URL."""
    return await get_crawler_client().urltest(config, url)


async def test_urls(config: Dict[str, Any], urls: List[str]) -> List[UrlTestResult]:
    """Test extraction on multiple URLs."""
    return await get_crawler_client().urltest_batch(config, urls)
