# Configuration Validation Rules

> Extracted from hive-mind open-crawler guides
> Last Updated: 2026-02-02
> Version: Open Crawler 0.4.2

## Overview

This document contains validation rules and constraints for Open Crawler configurations. These rules help ensure configs are valid before running crawls.

## Critical Validation Rules

### 1. Config Format Must Be Flat (v0.4+)

```yaml
# ✅ VALID (v0.4 format)
user_agent: "MyCrawler/1.0"
request_timeout: 30
max_crawl_depth: 3

# ❌ INVALID (v0.1 format)
http:
  user_agent: "MyCrawler/1.0"
  request_timeout: 30
```

**Error**: `Unexpected configuration options: [:http]`

### 2. Domain URL Must Not Have Path

```yaml
# ❌ INVALID
domains:
  - url: https://example.com/
  - url: https://example.com/path

# ✅ VALID
domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/
      - https://example.com/path
```

**Error**: `Domain cannot have a path`

### 3. Extraction Rules Require join_as

```yaml
# ❌ INVALID - missing join_as
- action: extract
  field_name: author
  selector: ".author"
  source: html

# ✅ VALID
- action: extract
  field_name: author
  selector: ".author"
  source: html
  join_as: string  # or 'array'
```

**Error**: `join_as is invalid` or `join_as is required`

### 4. URL Filter Type Constraints

Different URL filter types are supported in different contexts:

| Type | crawl_rules | extraction_rulesets |
|------|-------------|---------------------|
| `begins` | ✅ | ✅ |
| `ends` | ✅ | ✅ |
| `contains` | ✅ | ✅ |
| `regex` | ✅ | ✅ |
| `equals` | ✅ | ❌ **NOT SUPPORTED** |

```yaml
# ❌ INVALID - equals not supported in extraction URL filters
extraction_rulesets:
  - url_filters:
      - type: equals
        pattern: /about

# ✅ VALID - use regex instead
extraction_rulesets:
  - url_filters:
      - type: regex
        pattern: "^/about$"
```

**Error**: `url_filter equals is invalid`

### 5. max_crawl_depth for File Output

```yaml
# ❌ INVALID - file output won't work
output_sink: file
output_dir: /config/results
max_crawl_depth: 0  # Files will NOT be created

# ✅ VALID
output_sink: file
output_dir: /config/results
max_crawl_depth: 1  # Minimum for file output
```

**Issue**: Crawler reports success but no files are created. `max_crawl_depth: 0` means seed URLs are never crawled.

### 6. No Environment Variable Substitution

```yaml
# ❌ DOES NOT WORK - literal string used
elasticsearch:
  host: "${ES_HOST}"
  api_key: "${ES_API_KEY}"

# ✅ WORKAROUND - use shell expansion
# cat > config.yml << EOF
# elasticsearch:
#   host: $ES_HOST
#   api_key: $ES_API_KEY
# EOF
```

**Error**: `bad URI(is not URI?): "${ES_HOST}"`

## Field Validation

### Required Fields

```yaml
# Minimum required fields
output_sink: console  # Required
domains:              # Required
  - url: https://example.com  # Required
    seed_urls:        # Required
      - https://example.com/  # At least one seed URL
```

### Output Sink Validation

```yaml
# Console output
output_sink: console
# No additional fields required

# File output
output_sink: file
output_dir: /config/results  # Required
# Must be container path, not host path

# Elasticsearch output
output_sink: elasticsearch
output_index: my-index  # Required

elasticsearch:  # Required
  host: https://your-host  # Required
  port: 443  # Required
  api_key: your-key  # Required
```

### Extraction Rule Validation

```yaml
# All fields required for extraction rules
- action: extract      # Required: 'extract' or 'set'
  field_name: author   # Required: custom field name
  selector: ".author"  # Required: CSS selector or regex
  source: html         # Required: 'html' or 'url'
  join_as: string      # Required: 'string' or 'array'
```

### Crawl Rule Validation

```yaml
# All fields required for crawl rules
- policy: allow       # Required: 'allow' or 'deny'
  type: begins        # Required: begins, ends, contains, regex, equals
  pattern: /blog/     # Required: pattern to match
```

## Reserved Field Names

**NEVER use these as extraction field names:**

```yaml
# ❌ Reserved - will cause conflicts or be ignored
- id
- title
- body
- body_content
- url
- url_host
- url_path
- url_port
- url_scheme
- links
- headings
- meta_description
- meta_keywords
- last_crawled_at
- domains
- additional_urls

# ✅ Use prefixed names instead
- article_title
- blog_content
- product_price
- custom_field
```

## Value Constraints

### Numeric Fields

| Field | Type | Min | Max | Default |
|-------|------|-----|-----|---------|
| `max_crawl_depth` | integer | 0 | unlimited | 2 |
| `request_timeout` | integer | 1 | unlimited | 30 |
| `connect_timeout` | integer | 1 | unlimited | 10 |
| `socket_timeout` | integer | 1 | unlimited | 10 |
| `max_unique_url_count` | integer | 1 | unlimited | unlimited |
| `max_response_size` | integer | 1 | unlimited | 10485760 |
| `port` | integer | 1 | 65535 | 443/9200 |

### String Fields

| Field | Allowed Values |
|-------|---------------|
| `output_sink` | `console`, `file`, `elasticsearch` |
| `log_level` | `info`, `debug` |
| `policy` | `allow`, `deny` |
| `action` | `extract`, `set` |
| `source` | `html`, `url` |
| `join_as` | `string`, `array` |

### URL Pattern Types

| Type | Context | Description |
|------|---------|-------------|
| `begins` | Both | Path starts with pattern |
| `ends` | Both | Path ends with pattern |
| `contains` | Both | Path contains pattern |
| `regex` | Both | Regex match |
| `equals` | `crawl_rules` only | Exact path match |

## Validation Commands

### Validate Configuration

```bash
docker compose run --rm crawler bin/crawler validate /config/your-config.yml
```

Expected output on success:
```
Validating configuration...
Configuration is valid!
```

### Test Single URL

```bash
docker compose run --rm crawler bin/crawler urltest /config/your-config.yml https://example.com
```

Tests:
- Can reach the URL
- Respects robots.txt
- Applies extraction rules (if any)

### Validate Before Crawl

```bash
# 1. Validate config
docker compose run --rm crawler bin/crawler validate /config/test.yml

# 2. Test single URL
docker compose run --rm crawler bin/crawler urltest /config/test.yml https://example.com

# 3. Shallow crawl (console output)
# Set: output_sink: console, max_crawl_depth: 1
docker compose run --rm crawler bin/crawler crawl /config/test.yml

# 4. File output (inspect JSON)
# Set: output_sink: file
docker compose run --rm crawler bin/crawler crawl /config/test.yml
cat results/*.json | python3 -m json.tool

# 5. Production crawl (ES output)
# Set: output_sink: elasticsearch
docker compose run --rm crawler bin/crawler crawl /config/production.yml
```

## Common Validation Errors

| Error Message | Cause | Fix |
|---------------|-------|-----|
| `Unexpected configuration options: [:http]` | Using v0.1 format | Use flat structure |
| `Domain cannot have a path` | Trailing slash in domain | Remove slash, use seed_urls |
| `join_as is invalid` | Missing join_as | Add `join_as: array` or `join_as: string` |
| `url_filter equals is invalid` | equals in extraction rules | Use `regex` with `^pattern$` |
| `bad URI: "${ES_HOST}"` | Variable substitution | Use shell expansion |
| `output_dir is required` | Missing output_dir with file output | Add output_dir path |

## Validation Checklist

Before running a crawl, verify:

### Configuration Structure
- [ ] Using flat config format (v0.4+)
- [ ] No nested `http:` block
- [ ] Domain URL has no trailing slash or path
- [ ] Seed URLs provided in `seed_urls` array

### Output Settings
- [ ] `output_sink` is one of: console, file, elasticsearch
- [ ] For file: `output_dir` uses container path
- [ ] For file: `max_crawl_depth` ≥ 1
- [ ] For ES: `output_index`, `elasticsearch` block provided

### Extraction Rules
- [ ] Every rule has `action`, `field_name`, `selector`, `source`, `join_as`
- [ ] Field names are not reserved
- [ ] URL filters use valid types (not `equals`)
- [ ] Selectors are valid CSS or regex

### Crawl Rules
- [ ] Every rule has `policy`, `type`, `pattern`
- [ ] Patterns are properly escaped (regex)
- [ ] Rule order is correct (specific before general)

### General
- [ ] No environment variable placeholders in config
- [ ] All required fields provided
- [ ] Numeric values in valid ranges
- [ ] String values from allowed sets

## Automated Validation

The crawler provides built-in validation:

```bash
# Returns exit code 0 on success, non-zero on failure
docker compose run --rm crawler bin/crawler validate /config/test.yml
echo $?  # 0 = valid, 1 = invalid
```

Use in scripts:
```bash
#!/bin/bash
if docker compose run --rm crawler bin/crawler validate /config/test.yml; then
  echo "Config is valid, running crawl..."
  docker compose run --rm crawler bin/crawler crawl /config/test.yml
else
  echo "Config validation failed!"
  exit 1
fi
```

## Related Documents

- [Base Configuration](../config-structure/base-config.md)
- [Crawl Rules](./crawl-rules.md)
- [Extraction Basics](../extraction-rules/extraction-basics.md)
- [Common Errors](../troubleshooting/common-errors.md)
