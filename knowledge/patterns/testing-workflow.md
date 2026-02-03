# Fast Iteration Workflow

> Extracted from hive-mind open-crawler guides
> Last Updated: 2026-02-02
> Version: Open Crawler 0.4.2

## Overview

**Key Learning**: Always start with console output for rapid feedback. Never start with Elasticsearch for new configs.

## The Problem

Setting up Elasticsearch connection for every test:
- Adds complexity
- Slows down feedback loop
- Makes debugging harder
- Requires credentials/network

## The Solution: Console-First Development

```text
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│   urltest   │ →  │   validate   │ →  │   console   │ →  │     file     │ →  │ elasticsearch│
│ single URL  │    │    config    │    │ shallow crawl│    │    output    │    │  production  │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘    └──────────────┘
     Fast              Fast              Fast              Medium              Full
   (seconds)         (seconds)         (seconds)         (minutes)          (minutes)
```

## Step-by-Step Workflow

### Step 1: Test Single URL (Fastest)

**Purpose**: Verify the crawler can reach the site, see raw HTML structure

```bash
docker compose run --rm crawler bin/crawler urltest /config/crawler.yml https://example.com/page
```

**What to check**:
- Status code 200
- Content is in HTML (not JS-rendered)
- No bot protection (403, CAPTCHA)
- Expected content visible in output

### Step 2: Validate Configuration

**Purpose**: Catch config syntax errors before running

```bash
docker compose run --rm crawler bin/crawler validate /config/crawler.yml
```

**What it checks**:
- YAML syntax
- Required fields present
- Valid field values
- URL filter types
- join_as requirements

### Step 3: Console Crawl (See Output Directly)

**Purpose**: Verify crawl rules work, see what URLs are visited/denied

```yaml
# Config for console testing
output_sink: console
max_crawl_depth: 1  # Shallow crawl for speed
log_level: info     # or 'debug' for more detail

domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/
```

```bash
docker compose run --rm crawler bin/crawler crawl /config/crawler.yml
```

**What to check**:
- URLs discovered and visited
- Crawl rules working (check denied count)
- No timeouts or errors
- Expected pages found

### Step 4: File Output (Inspect Extracted Fields)

**Purpose**: Verify extraction rules work, inspect JSON structure

```yaml
# Config for file output
output_sink: file
output_dir: /config/results/test
max_crawl_depth: 2  # or 1 for speed

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
```

```bash
# Run crawl
docker compose run --rm crawler bin/crawler crawl /config/crawler.yml

# Inspect output
cat results/test/*.json | python3 -m json.tool | head -100
```

**What to check**:
- JSON files created
- Custom fields present
- Field values correct
- No empty extractions

**IMPORTANT**: Console output shows raw HTML, NOT extracted fields. Always use file output to debug extraction.

### Step 5: Validate Results (Before Indexing)

**Purpose**: Check data quality before indexing

```bash
# Count documents missing required fields
cat results/test/*.json | jq -c 'select(.url == null or ((.title == null or .title == "") and (.body == null or .body == "")))' | wc -l

# Check for very short content (possible extraction failure)
cat results/test/*.json | jq -c 'select(.body != null and (.body | length) < 50)' | wc -l

# View sample documents
cat results/test/*.json | jq -s '.[0:3]' | python3 -m json.tool
```

**Should return 0 for quality checks**

### Step 6: Elasticsearch Output (Only When Validated)

**Purpose**: Production indexing

```yaml
output_sink: elasticsearch
output_index: your-index

elasticsearch:
  host: https://your-cluster.es.cloud.com
  port: 443
  api_key: your-api-key
  ssl:
    enabled: true

domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/
    
    # Use validated extraction rules
    extraction_rulesets:
      - rules:
          - action: extract
            field_name: page_title
            selector: "h1"
            source: html
            join_as: string
```

```bash
docker compose run --rm crawler bin/crawler crawl /config/production.yml
```

## Feedback Time Comparison

| Approach | Feedback Time | Complexity | Debug Info |
|----------|--------------|------------|------------|
| urltest | Seconds | Low | High (raw HTML) |
| validate | Seconds | Low | High (syntax errors) |
| Console first | Seconds | Low | High (see output) |
| File output | Minutes | Low | High (inspect JSON) |
| ES first | Minutes | High | Lower (check index) |

## When to Use Each Command

| Scenario | Command | Config |
|----------|---------|--------|
| Testing new site | `urltest` | N/A |
| Check config syntax | `validate` | N/A |
| Debugging extraction rules | File output | `max_crawl_depth: 1` |
| Validating crawl rules | Console | `max_crawl_depth: 1`, `log_level: debug` |
| Testing full crawl | Console | `max_crawl_depth: 2-3` |
| Production indexing | ES output | Full depth |

## Anti-Patterns to Avoid

❌ Starting with ES output for new configs  
❌ Full-depth crawls during development  
❌ Skipping `urltest` and going straight to full crawl  
❌ Using console output to debug extraction (shows raw HTML, not fields)  
❌ Not using `--log-level debug` when troubleshooting  

## Debug Mode

Enable detailed logging for troubleshooting:

```yaml
log_level: debug
```

```bash
docker compose run --rm crawler bin/crawler crawl /config/crawler.yml
```

Debug output shows:
- Full config dump at startup
- Each URL added to queue
- Crawl rules evaluation
- HTTP execution progress
- Connection pool stats
- Extraction attempts

## Common Workflow Scenarios

### Scenario 1: New Site - Unknown Structure

```bash
# 1. Check if site is accessible
curl -I https://example.com

# 2. Test with crawler (see raw HTML)
docker compose run --rm crawler bin/crawler urltest /config/minimal.yml https://example.com

# 3. Shallow console crawl (see what's discovered)
# Set: output_sink: console, max_crawl_depth: 1
docker compose run --rm crawler bin/crawler crawl /config/minimal.yml

# 4. Add extraction rules, test with file output
# 5. Validate, then switch to ES
```

### Scenario 2: Debugging Extraction Rules

```bash
# 1. Test selector in browser console
# document.querySelectorAll('h1')

# 2. Create simple extraction rule
# 3. Run with file output, depth 1
docker compose run --rm crawler bin/crawler crawl /config/test.yml

# 4. Check JSON output
cat results/test/*.json | jq '.page_title'

# 5. Iterate on selector until working
# 6. Add more extraction rules
```

### Scenario 3: Debugging Crawl Rules

```bash
# 1. Run with console output and debug logging
# Set: output_sink: console, log_level: debug
docker compose run --rm crawler bin/crawler crawl /config/test.yml

# 2. Look for "Rule engine denied URL:"
# 3. Adjust crawl rules
# 4. Re-run and verify
```

## Helper Script

```bash
#!/bin/bash
# crawl-test.sh - Helper for fast iteration

CONFIG=${1:-crawler.yml}
URL=${2:-}

case "$1" in
  test-url)
    docker compose run --rm crawler bin/crawler urltest /config/$CONFIG $URL
    ;;
  validate)
    docker compose run --rm crawler bin/crawler validate /config/$CONFIG
    ;;
  console)
    docker compose run --rm crawler bin/crawler crawl /config/$CONFIG
    ;;
  file)
    docker compose run --rm crawler bin/crawler crawl /config/$CONFIG
    ls -la results/
    ;;
  check)
    cat results/*/*.json | jq -s 'length'
    cat results/*/*.json | jq -s '.[0] | keys'
    ;;
  *)
    echo "Usage: $0 {test-url|validate|console|file|check} [config.yml] [url]"
    ;;
esac
```

## Best Practices

1. **Always start with urltest**: See if the site is accessible
2. **Validate early and often**: Catch config errors before running
3. **Use shallow crawls**: `max_crawl_depth: 1` for fast testing
4. **Debug with file output**: Console shows raw HTML, not extracted fields
5. **Check result quality**: Validate JSON before indexing
6. **Only then use ES**: After config is proven to work

## Related Documents

- [Base Configuration](../config-structure/base-config.md)
- [Validation Checklist](../validation-rules/validation-checklist.md)
- [Docker Setup](./docker-setup.md)
- [Troubleshooting](../troubleshooting/common-errors.md)
