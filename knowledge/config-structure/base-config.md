# Open Crawler Base Configuration Structure

> Extracted from hive-mind open-crawler guides
> Last Updated: 2026-02-02
> Version: Open Crawler 0.4.2

## Overview

Open Crawler uses YAML configuration files with a flat (non-nested) structure for core settings. This is the v0.4+ format.

## Critical Configuration Rules

### 1. Config Format is Flat (v0.4+)

```yaml
# ✅ CORRECT (v0.4 format)
output_sink: elasticsearch
output_index: my-index
user_agent: "MyCrawler/1.0"
request_timeout: 30
max_crawl_depth: 3
log_level: info

# ❌ WRONG (v0.1 format - will fail)
http:
  user_agent: "MyCrawler/1.0"
  request_timeout: 30
```

### 2. Domain URL Must Not Have Path

```yaml
# ❌ WRONG
domains:
  - url: https://example.com/

# ✅ CORRECT
domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/
```

### 3. No Environment Variable Substitution

Open Crawler does NOT natively support `${VAR}` substitution:

```yaml
# ❌ DOES NOT WORK
elasticsearch:
  host: "${ES_HOST}"
  
# ✅ Workaround: Shell expansion
# Use: cat > config.yml << EOF ... EOF
# Or: envsubst < template.yml > config.yml
```

## Required Fields

```yaml
# Minimum viable config
output_sink: console | file | elasticsearch
domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/path
```

## Top-Level Settings

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `output_sink` | string | Yes | - | `console`, `file`, or `elasticsearch` |
| `output_index` | string | For ES | - | Elasticsearch index name |
| `output_dir` | string | For file | - | Container path (e.g., `/config/results/test`) |
| `max_crawl_depth` | integer | No | 2 | **Must be ≥1 for file output** |
| `user_agent` | string | No | Default | Custom user agent string |
| `request_timeout` | integer | No | 30 | Request timeout in seconds |
| `log_level` | string | No | `info` | `info` or `debug` |
| `max_unique_url_count` | integer | No | - | Limit total URLs crawled |
| `max_response_size` | integer | No | 10485760 | Max response size (bytes) |

## Output Sink Configurations

### Console Output (Testing)

```yaml
output_sink: console
domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/
max_crawl_depth: 1
user_agent: "TestCrawler/1.0"
```

**Use for**: Quick testing, seeing raw HTML, verifying crawl rules

### File Output (Debugging)

```yaml
output_sink: file
output_dir: /config/results/test  # Container path!
domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/
    extraction_rulesets:
      - rules:
          - action: extract
            field_name: page_title
            selector: "h1"
            source: html
            join_as: string
max_crawl_depth: 1  # CRITICAL: Must be ≥1 for file output
```

**Use for**: Inspecting extracted JSON, debugging extraction rules

**CRITICAL**: 
- File output requires `max_crawl_depth: 1` or higher (NOT 0)
- Use docker-compose with separate volume mounts
- Output path must be container path, not host path

### Elasticsearch Output (Production)

```yaml
output_sink: elasticsearch
output_index: production-content

elasticsearch:
  host: https://your-cluster.es.cloud.com
  port: 443
  api_key: your-api-key-here
  ssl:
    enabled: true

domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/
```

**Use for**: Production indexing, regular crawls

## Domain Configuration

```yaml
domains:
  - url: https://example.com  # No trailing slash or path
    seed_urls:
      - https://example.com/start-page
      - https://example.com/another-page
    
    # Optional: Crawl rules
    crawl_rules:
      - policy: allow
        type: begins
        pattern: /blog/
      - policy: deny
        type: regex
        pattern: ".*"
    
    # Optional: Extraction rules
    extraction_rulesets:
      - rules:
          - action: extract
            field_name: custom_field
            selector: ".selector"
            source: html
            join_as: string
    
    # Optional: Authentication
    auth:
      type: basic
      username: ${AUTH_USER}
      password: ${AUTH_PASS}
```

## Scale and Performance Settings

```yaml
# Rate limiting
request_timeout: 30
connect_timeout: 10
socket_timeout: 10

# Scale limits
max_crawl_depth: 3
max_unique_url_count: 10000
max_response_size: 10485760  # 10MB

# Logging
log_level: info  # or 'debug' for troubleshooting
```

## Reserved Field Names (Auto-Generated)

**NEVER use these as extraction field names:**

- `id`, `title`, `body`, `body_content`
- `url`, `url_host`, `url_path`, `url_port`, `url_scheme`
- `links`, `headings`
- `meta_description`, `meta_keywords`
- `last_crawled_at`, `domains`
- `additional_urls`

**Always use prefixed names:**
- `article_title` (not `title`)
- `blog_content` (not `body`)
- `product_price` (not `price` - unless prefixed)
- `custom_field` (always safe)

## Field Naming Conventions for Elasticsearch Mapping

The crawler controller uses **suffix-based conventions** to automatically apply the correct Elasticsearch mapping. Use these suffixes in your `field_name` to control indexing behavior:

| Suffix | Mapping | Use Case |
|--------|---------|----------|
| `_semantic` | text + keyword + ELSER + Jina | Semantic/conceptual search |
| `_text` | text + keyword | Regular full-text search |
| `_keyword` | keyword | Exact match, filtering, aggregations |
| `_date` | date | Timestamps |
| `_num`, `_count`, `_price`, `_score` | float | Numeric values |
| (no suffix) | text + keyword | Default text handling |

### Examples

```yaml
extraction_rulesets:
  - rules:
      # Semantic search (ELSER + Jina embeddings)
      - action: extract
        field_name: product_description_semantic
        selector: ".description"
        source: html
        join_as: string
      
      # Regular text search
      - action: extract
        field_name: author_name_text
        selector: ".author"
        source: html
        join_as: string
      
      # Exact match / filtering
      - action: extract
        field_name: category_keyword
        selector: ".category"
        source: html
        join_as: string
      
      # Numeric
      - action: extract
        field_name: product_price
        selector: ".price"
        source: html
        join_as: string
```

**Note:** Default crawler fields (`title`, `body`, `headings`) automatically get semantic search - no suffix needed.

## Validation Commands

```bash
# Validate configuration
docker compose run --rm crawler bin/crawler validate /config/your-config.yml

# Test single URL
docker compose run --rm crawler bin/crawler urltest /config/your-config.yml https://example.com

# Run crawl
docker compose run --rm crawler bin/crawler crawl /config/your-config.yml

# Debug mode
docker compose run --rm crawler bin/crawler crawl /config/your-config.yml --log-level debug
```

## Docker Compose Setup (Required for File Output)

```yaml
# docker-compose.yml
version: '3.8'

services:
  crawler:
    image: docker.elastic.co/integrations/crawler:0.4.2
    volumes:
      # Mount configs and results SEPARATELY
      - ./configs:/config/configs:ro
      - ./results:/config/results
    entrypoint: ["jruby"]
    command: ["bin/crawler", "--help"]
```

## Common Configuration Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Unexpected configuration options: [:http]` | v0.1 format | Use flat structure |
| `Domain cannot have a path` | Trailing slash | Remove from domain URL |
| `join_as is invalid` | Missing field | Add `join_as: array` or `join_as: string` |
| `bad URI: "${ES_HOST}"` | Variable substitution | Use shell expansion |

## Related Documents

- [Crawl Rules](../validation-rules/crawl-rules.md)
- [Extraction Rules](../extraction-rules/extraction-basics.md)
- [Docker Setup](../patterns/docker-setup.md)
