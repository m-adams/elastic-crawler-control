# Open Crawler Integration Specification

## Purpose
Define how this project integrates with Elastic Open Crawler. **No mocking or simulation** - all testing must use the actual crawler binary.

## Open Crawler Commands

The crawler binary (`/crawler/bin/crawler`) supports these commands:

| Command | Purpose | Use Case |
|---------|---------|----------|
| `validate config.yml` | Validate config syntax and schema | Before any crawl/test |
| `urltest config.yml URL` | Test single URL extraction | Preview what crawler extracts |
| `crawl config.yml` | Full crawl to output sink | Production crawling |

## Requirements

### Requirement: Config Validation
The system SHALL validate configs using Open Crawler's validate command.

#### Scenario: Validate Config Before Use
- GIVEN a generated or user-provided config
- WHEN validation is requested
- THEN run `bin/crawler validate config.yml`
- AND parse output for errors/warnings
- AND return validation result with specific issues

#### Scenario: Validation Failure
- GIVEN a config with issues
- WHEN validation fails
- THEN extract error messages from crawler output
- AND identify which config section caused the error
- AND suggest fixes based on error type

### Requirement: URL Testing
The system SHALL test extraction using Open Crawler's urltest command.

#### Scenario: Test Single URL
- GIVEN a valid config
- AND a URL to test
- WHEN user requests extraction preview
- THEN run `bin/crawler urltest config.yml URL`
- AND parse extracted document from output
- AND return extracted fields to user

#### Scenario: Test Multiple URLs
- GIVEN a valid config
- AND multiple test URLs
- WHEN user requests batch test
- THEN run urltest for each URL (sequentially or parallel)
- AND aggregate results
- AND show extraction success rate

#### Scenario: URL Test Failure
- GIVEN a URL that cannot be crawled
- WHEN urltest fails
- THEN capture error (blocked, timeout, 404, etc.)
- AND report specific failure reason
- AND suggest remediation (e.g., "Site blocks crawlers - consider robots.txt exclusion")

### Requirement: Site Crawlability Detection
The system SHALL detect when a site will block the crawler.

#### Scenario: Blocked by robots.txt
- GIVEN a site's robots.txt disallows crawling
- WHEN site investigation runs
- THEN detect disallow rules for our user-agent
- AND warn user before config generation
- AND suggest: contact site owner, or exclude blocked paths

#### Scenario: JavaScript-Required Sites
- GIVEN a site requires JavaScript to render content
- WHEN site investigation detects minimal HTML
- THEN warn user: "This site requires JavaScript rendering"
- AND inform: Open Crawler has limited JS support
- AND suggest: test with urltest to verify

#### Scenario: Anti-Bot Protection
- GIVEN a site returns CAPTCHA or access denied
- WHEN urltest returns error page
- THEN detect common block patterns (Cloudflare, etc.)
- AND warn user: "Site has anti-bot protection"
- AND suggest: reduce crawl rate, contact site owner

### Requirement: Extraction Rule Testing
The system SHALL test extraction rules against real pages.

#### Scenario: Test Extraction Rules
- GIVEN a config with extraction_rulesets
- AND sample URLs
- WHEN testing extraction
- THEN run urltest on each URL
- AND parse extracted fields from output
- AND compare against expected fields (from content type)
- AND report: which fields extracted, which missing, which empty

#### Scenario: Iterate on Extraction Rules
- GIVEN extraction test shows missing fields
- WHEN user requests improvement
- THEN analyze urltest output
- AND LLM suggests selector adjustments
- AND update config and re-test

### Requirement: Full Crawl Testing
The system SHALL support test crawls to temporary indices.

#### Scenario: Test Crawl
- GIVEN a validated config
- WHEN user requests full test crawl
- THEN create temporary Elasticsearch index
- AND run `bin/crawler crawl config.yml` with temp index
- AND wait for completion (with timeout)
- AND show crawl stats (pages visited, documents indexed)
- AND allow user to query/browse indexed documents
- AND clean up temp index after review (optional)

## Technical Implementation

### Crawler Client (`utils/crawler_client.py`)

```python
class CrawlerClient:
    """Client for Open Crawler binary commands."""
    
    def __init__(self, crawler_path: str = "/crawler"):
        self.crawler_path = crawler_path
        self.bin_path = f"{crawler_path}/bin/crawler"
    
    async def validate(self, config_path: str) -> ValidationResult:
        """Run bin/crawler validate."""
        result = await self._run_command(["validate", config_path])
        return self._parse_validation_output(result)
    
    async def urltest(self, config_path: str, url: str) -> UrlTestResult:
        """Run bin/crawler urltest."""
        result = await self._run_command(["urltest", config_path, url])
        return self._parse_urltest_output(result)
    
    async def crawl(self, config_path: str) -> CrawlResult:
        """Run bin/crawler crawl."""
        result = await self._run_command(["crawl", config_path])
        return self._parse_crawl_output(result)
```

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/crawler/validate` | POST | Validate a config |
| `/api/crawler/urltest` | POST | Test single URL extraction |
| `/api/crawler/urltest/batch` | POST | Test multiple URLs |
| `/api/crawler/test-crawl` | POST | Run test crawl to temp index |

### Output Parsing

Open Crawler outputs must be parsed to extract:
- Validation errors and warnings
- Extracted document JSON from urltest
- Crawl statistics (pages, documents, errors)
- Error messages and stack traces

## Error Handling

| Error Type | Detection | User Message |
|------------|-----------|--------------|
| Config invalid | validate returns non-zero | "Config has errors: {details}" |
| URL unreachable | urltest timeout/error | "Cannot reach {url}: {reason}" |
| Blocked by site | 403/captcha in response | "Site blocks crawlers" |
| No extraction | urltest returns empty doc | "No content extracted - check selectors" |
| Crawler not available | bin/crawler not found | "Open Crawler not installed" |

## Environment Requirements

```bash
# Required for Open Crawler integration
CRAWLER_PATH=/crawler              # Path to Open Crawler installation
ES_URL=https://...                 # Elasticsearch for crawl output
ES_API_KEY=...                     # Elasticsearch API key
```

## Constraints

1. **No simulation**: All tests use actual Open Crawler binary
2. **Real pages**: urltest fetches real pages, not cached/mocked
3. **Actual extraction**: Extraction rules tested by crawler, not Python
4. **Production parity**: Test behavior matches production crawling
