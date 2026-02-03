# Open Crawler Client

Client for interacting with the Elastic Open Crawler binary.

## Location

`elastic-crawler-control/crawler-service/app/utils/crawler_client.py`

## Purpose

Provides a Python interface to Open Crawler's command-line tools:
- `bin/crawler validate` - Validate configuration syntax and schema
- `bin/crawler urltest` - Test extraction on a single URL
- `bin/crawler crawl` - Run a full crawl

**Important**: This uses the REAL crawler binary. No mocking or simulation.

## Usage

### Basic Usage

```python
from utils.crawler_client import CrawlerClient

client = CrawlerClient()

# Check if crawler is available
if client.is_available():
    print("Crawler ready")
```

### Validate a Config

```python
config = {
    "domains": [{"url": "https://example.com"}],
    "output_sink": "console",
}

result = await client.validate(config)

if result.valid:
    print("Config is valid")
else:
    print(f"Errors: {result.errors}")
    print(f"Warnings: {result.warnings}")
```

### Test Extraction on a URL

```python
result = await client.urltest(config, "https://example.com/page")

if result.success:
    print(f"Extracted: {result.extracted_document}")
else:
    print(f"Error: {result.error}")
    
if result.blocked:
    print(f"Site blocked crawler: {result.block_reason}")
```

### Test Multiple URLs

```python
urls = [
    "https://example.com/page1",
    "https://example.com/page2",
    "https://example.com/page3",
]

results = await client.urltest_batch(config, urls)

for result in results:
    print(f"{result.url}: {'✓' if result.success else '✗'}")
```

### Run a Full Crawl

```python
result = await client.crawl(config, timeout=3600)

print(f"Pages visited: {result.pages_visited}")
print(f"Documents indexed: {result.documents_indexed}")
print(f"Duration: {result.duration_seconds}s")
```

## Convenience Functions

For quick one-off operations:

```python
from utils.crawler_client import validate_config, test_url, test_urls

# Validate
result = await validate_config(config)

# Test single URL
result = await test_url(config, "https://example.com/page")

# Test multiple URLs
results = await test_urls(config, urls)
```

## Return Types

### ValidationResult

```python
@dataclass
class ValidationResult:
    valid: bool              # True if config is valid
    errors: List[str]        # Error messages
    warnings: List[str]      # Warning messages
    raw_output: str          # Raw crawler output
    return_code: int         # Process return code
```

### UrlTestResult

```python
@dataclass
class UrlTestResult:
    success: bool                           # True if extraction succeeded
    url: str                                # URL that was tested
    extracted_document: Optional[Dict]      # Extracted fields
    error: Optional[str]                    # Error message if failed
    raw_output: str                         # Raw crawler output
    return_code: int                        # Process return code
    blocked: bool                           # True if site blocked crawler
    block_reason: Optional[str]             # Why it was blocked
```

### CrawlResult

```python
@dataclass
class CrawlResult:
    success: bool            # True if crawl succeeded
    pages_visited: int       # Number of pages crawled
    documents_indexed: int   # Documents written to output
    duration_seconds: float  # Crawl duration
    errors: List[str]        # Error messages
    raw_output: str          # Raw crawler output
    return_code: int         # Process return code
```

## Block Detection

The client automatically detects when sites block the crawler:

| Block Type | Detection |
|------------|-----------|
| Cloudflare | "cloudflare" in output |
| CAPTCHA | "captcha" in output |
| 403 Forbidden | "403" or "forbidden" |
| Rate Limiting | "rate limit" or "too many" |
| Bot Check | "robot check" in output |
| Access Denied | "access denied" |

When blocked, `UrlTestResult.blocked` is `True` and `block_reason` describes why.

## Configuration

### Environment Variables

```bash
CRAWLER_PATH=/crawler  # Path to Open Crawler installation (default: /crawler)
```

### Custom Path

```python
client = CrawlerClient(
    crawler_path="/custom/path/to/crawler",
    timeout_seconds=300,
)
```

## Error Handling

```python
try:
    result = await client.validate(config)
except RuntimeError as e:
    print(f"Crawler not found: {e}")
except TimeoutError as e:
    print(f"Command timed out: {e}")
```

## Differences from crawler.py

| Feature | `crawler.py` | `crawler_client.py` |
|---------|--------------|---------------------|
| Commands | crawl only | validate, urltest, crawl |
| Interface | Sync | Async |
| State | DB tracking, logs | Stateless |
| Output | Elasticsearch | Returns result |
| Use case | Production crawls | Testing/validation |

Use `crawler.py` for production crawls with full state management.
Use `crawler_client.py` for quick validation and testing.

## Tests

Unit tests (no crawler required):
```bash
pytest app/tests/test_crawler_client.py -v
```

Live tests (requires crawler at /crawler):
```bash
pytest app/tests/test_crawler_client.py -v -m crawler
```
