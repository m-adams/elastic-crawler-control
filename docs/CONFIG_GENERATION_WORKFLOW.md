# Config Generation Workflow

**Last Updated**: 2026-02-03  
**Status**: Implemented and tested

This document describes the complete logical flow from target site URL to validated Open Crawler configuration.

---

## Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CONFIG GENERATION PIPELINE                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [1. PREFLIGHT]  →  [2. DEEP CHECK]  →  [3. SITE INVESTIGATION]        │
│       ~0.3s            ~0.1s               ~30-60s                      │
│                                                                         │
│       ↓                                                                 │
│                                                                         │
│  [4. CONFIG GENERATION]  →  [5. VALIDATION LOOP]  →  [6. COMPLETION]   │
│        ~10-20s                 ~30-60s                                  │
│                                                                         │
│  Total time: ~60-90 seconds average                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Preflight Checks (~0.3s)

**Purpose**: Quick validation before engaging any heavy processing

**Endpoint**: `POST /api/domain/preflight`

**Steps**:
1. **URL Validation** - Verify URL format is valid
2. **DNS Resolution** - Check domain resolves to an IP
3. **HTTP Connectivity** - Verify site is reachable (HEAD request)
4. **Robots.txt Fetch** - Quick check if robots.txt exists

**Output**:
```json
{
  "url_valid": true,
  "dns_resolves": true,
  "http_reachable": true,
  "viable": true,
  "issues": []
}
```

**Exit Conditions**:
- If `viable: false` → Stop and return error to user
- If `viable: true` → Proceed to Deep Check

---

## Phase 2: Deep Check (~0.1s)

**Purpose**: Detect crawling challenges that may require alternative approaches

**Endpoint**: `POST /api/domain/deep-check`

**Steps**:
1. **Bot Protection Detection**
   - Check for Cloudflare, Akamai, Imperva, DataDome, PerimeterX
   - Analyze response headers and page content
   
2. **JavaScript Rendering Check**
   - Detect if page requires JS to render content
   - Check for SPA frameworks (React, Vue, Angular)
   
3. **Content Analysis**
   - Check for minimal content (may indicate JS rendering needed)

**Output**:
```json
{
  "bot_protection_detected": true,
  "bot_protection_provider": "Cloudflare",
  "javascript_required": false,
  "viable_for_open_crawler": true,
  "firecrawl_recommended": true,
  "issues": [
    {"severity": "warning", "code": "BOT_PROTECTION", "message": "Cloudflare detected"}
  ]
}
```

**Exit Conditions**:
- If `viable_for_open_crawler: false` → Return recommendation for Firecrawl
- Otherwise → Proceed to Site Investigation

---

## Phase 3: Site Investigation (~30-60s)

**Purpose**: Understand the site structure, content patterns, and crawlability

**Agent**: `SiteInvestigationAgent`

**Data Flow**: 
- Receives `preflight_data` (robots.txt already fetched)
- Receives `user_context` (user's goals/use case)
- Stores `html_samples` for use by Config Generation and Validation

**Steps**:

### 3.1 Robots.txt Analysis
- **Reuses robots.txt from Preflight** (avoids duplicate fetch)
- Extract rules for `User-agent: *` only (not bot-specific blocks)
- Filter out overly broad patterns like `Disallow: /`
- Extract sitemap URLs
- Note any crawl-delay directives

### 3.2 Sitemap Discovery & Parsing
- Fetch sitemaps listed in robots.txt (max 5)
- Parse sitemap indexes, follow nested sitemaps (max depth 1)
- Limit: max 10 sitemaps, max 500 URLs total
- Extract sample URLs for analysis

### 3.3 Sample Page Fetching
- Select sample pages (from sitemaps or seed URLs)
- Fetch 3-10 pages with rate limiting (1 req/sec)
- Detect bot protection on fetched pages
- Store HTML content for analysis

### 3.4 Page Structure Analysis
- Parse HTML structure (headings, metadata, content areas)
- Identify common patterns across pages
- Detect content types (article, product, doc)
- Find potential extraction selectors

### 3.5 Generate Recommendations
- Crawl rules based on robots.txt
- Extraction opportunities based on patterns
- Challenges identified (bot protection, dynamic content)

**Output**: Site analysis report including:
- `robots_txt`: Parsed rules and sitemaps
- `sitemaps`: URLs discovered
- `page_samples`: Fetched pages
- `page_structure_analysis`: Common patterns
- `recommendations`: Suggested crawl/extraction rules

**Timeout**: 120 seconds (safety limit)

---

## Phase 4: Config Generation (~10-20s)

**Purpose**: Generate a valid Open Crawler YAML configuration

**Agent**: `ConfigGenerationAgent`

**Data Flow**:
- Receives `site_analysis` with `html_samples` (actual HTML from investigation)
- Receives `user_context` (user's goals/use case)
- Uses LLM to generate tailored extraction rules based on actual HTML

**Steps**:

### 4.1 Load Knowledge Patterns
- Load extraction templates for content type (blog, ecommerce, docs)
- Load extraction rules guide (naming conventions, suffixes)
- Load crawl rule best practices

### 4.2 Detect Content Type
If not specified, detect from:
1. **user_context** keywords (e.g., "blog", "products", "docs")
2. Site analysis patterns (article tags, price elements)
- `blog`: Articles with author, date, tags
- `ecommerce`: Products with price, SKU
- `docs`: Documentation with sections, code blocks
- `general`: Default catch-all

### 4.3 Generate Domain Config
```yaml
domains:
- url: https://example.com  # No trailing slash
  seed_urls:
  - https://example.com/
```

### 4.4 Generate Crawl Rules
Based on recommendations from site investigation:
```yaml
  crawl_rules:
  # Deny patterns from robots.txt (User-agent: * only)
  - policy: deny
    type: begins
    pattern: /admin/
  # Common exclusions
  - policy: deny
    type: contains
    pattern: '?'
  # Never block seed URL with patterns like "/"
```

### 4.5 Generate Extraction Rules (LLM-Powered)

**NEW**: The LLM analyzes actual HTML samples to generate tailored extraction rules.

**LLM Receives**:
1. **user_context**: User's goals (e.g., "extract article titles and author names")
2. **html_samples**: Actual HTML from the site (up to 15KB per page)
3. **extraction_guide**: Naming conventions, field suffixes, reserved fields

**LLM Generates**:
- CSS selectors based on actual HTML structure (not generic guesses)
- Appropriate field name suffixes based on content type
- Correct `join_as` values (string vs array)

**Default Fields (NOT extracted - crawler handles automatically)**:
- `title` - Page title (semantic search enabled)
- `body` - Main content (semantic search enabled)
- `headings` - All h1-h6 (semantic search enabled)
- `links`, `meta_description`, `url` components

**Example LLM-Generated Rules** (for Python docs):
```yaml
  extraction_rulesets:
  - rules:
    - action: extract
      field_name: doc_title_text           # From actual HTML: h1
      selector: h1
      source: html
      join_as: string
    - action: extract
      field_name: code_examples_text       # From actual HTML: .highlight pre
      selector: pre code, .highlight pre, .codehilite pre
      source: html
      join_as: array
    - action: extract
      field_name: main_content_semantic    # From actual HTML: .body[role='main']
      selector: .body[role='main']
      source: html
      join_as: string
```

**Field Naming Suffixes**:
| Suffix | ES Mapping | Use Case |
|--------|------------|----------|
| `_semantic` | text + ELSER + vector | Long content for AI search |
| `_text` | text + keyword | Short searchable text |
| `_keyword` | keyword only | Exact match, filtering (also for arrays of keywords) |
| `_date` | date | Date/time values |
| `_num` | float | Numeric values |

**Note**: The suffix indicates the VALUE TYPE, not whether it's an array. Use `join_as: array` for multiple values.

### 4.6 Validate Structure
- Check all required fields present
- Verify `join_as` on all extraction rules
- Check for reserved field names

**Output**: 
- `config`: Complete config dictionary
- `yaml_content`: YAML string ready for file

---

## Phase 5: Validation Loop (max 3 iterations)

**Purpose**: Ensure config is valid and extraction rules work

**Agent**: `ConfigValidationAgent`

**Loop Structure** (Agno Workflow Loop):
```
[validate_config_step] → [regenerate_config_step] → [validate_config_step] → ...
         ↓                                                    ↓
    if valid=true                                      if iteration >= 3
         ↓                                                    ↓
      [EXIT]                                           [EXIT with error]
```

### 5.1 YAML Syntax Validation
- Parse YAML for syntax errors
- Check it produces a valid dictionary

### 5.2 Schema Validation
- Required fields: `output_sink`, `domains`
- Domain URL format (no trailing slash)
- Crawl rule structure
- Extraction rule requirements (`join_as` on all rules)
- No reserved field names

### 5.3 Crawler Binary Validation (if available)
- Run `bin/crawler validate config.yml`
- Catch crawler-specific errors

### 5.4 Extraction Rule Testing
- **Reuses HTML samples from Investigation** (avoids duplicate fetch)
- Apply CSS selectors to pages
- Check match rates per field
- **Stores actual extracted values** for `extraction_preview`
- Flag fields with 0% match rate as warnings

### 5.5 Crawl Rule Testing
- Test seed URLs against crawl rules
- **Critical**: Seed URL must NOT be denied
- Check for contradictory rules

### 5.6 Generate Report
```json
{
  "overall_status": "pass|warning|fail",
  "all_errors": ["..."],      // Blocking issues
  "all_warnings": ["..."],    // Non-blocking
  "recommendations": ["..."]
}
```

**Exit Conditions**:
- `status: pass` → Complete successfully
- `status: warning` → Complete with warnings (acceptable)
- `status: fail` → Regenerate config with feedback (up to 3 times)

---

## Phase 6: Completion

**Purpose**: Return final config to user via SSE with extraction preview

**SSE Event**:
```json
{
  "session_id": "workflow-xxx",
  "content": {
    "phase": "complete",
    "message": "Config generation complete",
    "config": { ... },
    "yaml_content": "output_sink: file\n...",
    "iteration_count": 1,
    "validation_status": "warning",
    "extraction_preview": {
      "article_title_text": {"value": "Example Article", "matched": true, "selector": "h1"},
      "author_name_text": {"value": null, "matched": false, "selector": ".author"}
    },
    "extraction_test_summary": {
      "total_fields": 5,
      "fields_matched": 4,
      "fields_failed": 1,
      "issues": ["Field 'author_name_text' matched 0 pages"]
    }
  }
}
```

**Extraction Preview**:
- Shows actual extracted values from validation testing
- User can verify selectors work before using the config
- Frontend displays in "Extraction Preview" tab with ✓/✗ indicators

---

## Data Flow Between Phases

**Key principle**: Data is fetched once and reused to avoid duplicate requests.

```
┌─────────────┐       robots_txt        ┌─────────────────────┐
│  Preflight  │ ──────────────────────▶ │  Site Investigation │
└─────────────┘                         └─────────────────────┘
                                                │
                                                │ html_samples
                                                │ user_context
                                                ▼
                                        ┌─────────────────────┐
                                        │  Config Generation  │
                                        └─────────────────────┘
                                                │
                                                │ html_samples (reused)
                                                ▼
                                        ┌─────────────────────┐
                                        │     Validation      │ ──▶ extraction_preview
                                        └─────────────────────┘
```

| Data | Source | Consumers | Benefit |
|------|--------|-----------|---------|
| `robots_txt` | Preflight | Investigation | Avoids duplicate fetch |
| `html_samples` | Investigation | Config Gen, Validation | LLM sees real HTML, consistent testing |
| `user_context` | User input | Investigation, Config Gen | Guides LLM decisions |
| `extraction_preview` | Validation | Completion event | User sees actual results |

---

## Error Handling

### Timeout Handling
- **Investigation timeout (120s)**: Returns error, prevents infinite hang
- **HTTP timeout (30s per request)**: Moves to next URL
- **Thread timeout**: Raises `TimeoutError`, caught by workflow

### Common Errors

| Error | Phase | Handling |
|-------|-------|----------|
| Invalid URL | Preflight | Return immediately |
| DNS failure | Preflight | Return immediately |
| Bot protection | Deep Check | Warning + Firecrawl recommendation |
| Sitemap timeout | Investigation | Skip sitemap, continue |
| Seed URL blocked | Validation | Regenerate with feedback |
| Max iterations | Validation | Return best config with errors |

---

## SSE Event Stream

Events are streamed via `POST /api/generate`:

```
data: {"session_id": "...", "content": {"phase": "preflight", ...}}
data: {"session_id": "...", "content": {"phase": "deep_check", ...}}
data: {"session_id": "...", "content": {"phase": "starting_workflow", ...}}
: keepalive
data: {"session_id": "...", "content": {"phase": "investigating", ...}}
data: {"session_id": "...", "content": {"phase": "generating", ...}}
data: {"session_id": "...", "content": {"phase": "validating", ...}}
data: {"session_id": "...", "content": {"phase": "complete", ...}}
```

**Keepalive**: Empty comments (`: keepalive\n\n`) sent every 1s to prevent buffering.

---

## Performance Characteristics

| Phase | Typical Time | Notes |
|-------|--------------|-------|
| Preflight | 0.2-0.5s | DNS + HTTP check |
| Deep Check | 0.1-0.2s | Header analysis |
| Investigation | 30-60s | Sitemap + page fetching |
| Generation | 10-20s | LLM config generation |
| Validation | 30-60s | Page fetching + testing |
| **Total** | **60-90s** | Varies by site complexity |

---

## File Locations

| Component | File |
|-----------|------|
| Preflight/Deep Check | `routes/domain.py` |
| SSE Endpoint | `routes/workflow.py` |
| Orchestration | `agents/orchestration_workflow.py` |
| Site Investigation | `agents/site_investigation.py` |
| Config Generation | `agents/config_generation.py` |
| Config Validation | `agents/config_validation.py` |
| Robots Parser | `utils/robots_parser.py` |
| Sitemap Parser | `utils/sitemap_parser.py` |
| Page Fetcher | `utils/page_fetcher.py` |

---

## Configuration

### Environment Variables
```bash
LLM_PROXY_API_KEY=xxx          # Required for LLM agents
LLM_PROXY_BASE_URL=https://... # LLM proxy endpoint
CRAWLER_PATH=/crawler          # Optional: path to Open Crawler
```

### Tunable Parameters
| Parameter | Default | Location |
|-----------|---------|----------|
| Max sitemaps | 10 | `sitemap_parser.py` |
| Max URLs from sitemaps | 500 | `sitemap_parser.py` |
| Sample pages to fetch | 10 | `site_investigation.py` |
| Rate limit delay | 1.0s | `page_fetcher.py` |
| HTTP timeout | 30s | `page_fetcher.py` |
| Investigation timeout | 120s | `orchestration_workflow.py` |
| Max validation iterations | 3 | `orchestration_workflow.py` |

---

## Example: BBC News

**Input**:
```json
{"domain": "https://www.bbc.co.uk/news", "content_type": "blog"}
```

**Flow**:
1. Preflight: URL valid, DNS resolves, HTTP reachable ✓
2. Deep Check: Cloudflare detected (warning), viable ✓
3. Investigation: 
   - robots.txt has 30+ disallow patterns
   - 13 sitemaps found, 10 processed
   - Bot-specific blocks filtered out (ClaudeBot, GPTBot, etc.)
4. Generation: Blog template applied
5. Validation: Warning (some selectors don't match example.com structure)
6. Complete: Config with 31 crawl rules, 5 extraction fields

**Output fields**:
- `article_title_text`
- `article_author_text`
- `publish_date`
- `article_body_semantic`
- `article_tags_keyword`

**Time**: ~85 seconds
