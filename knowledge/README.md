# Open Crawler Knowledge Base

> Extracted from elastic/hive-mind repository
> Last Updated: 2026-02-02
> Version: Open Crawler 0.4.2

## Overview

This knowledge base contains structured patterns, rules, and best practices for working with Elastic Open Crawler, extracted from the hive-mind repository guides.

## Agno Framework Guide

**IMPORTANT**: This project uses the [Agno AI Framework](https://docs.agno.com/) for agent orchestration.

- **[Agno Workflow Guide](agno/workflow-guide.md)** - Critical reference for building workflows
  - Workflow instantiation (NOT custom wrapper classes)
  - Step, Loop, Parallel, Condition, Router patterns
  - Streaming with `stream=True`
  - Human-in-the-Loop (Agent level only)
  - FastAPI integration

**Read this guide before modifying any agent code.**

## Source Documents

Patterns extracted from:
- `hive-mind/patterns/elastic/open-crawler-complete-guide.md`
- `hive-mind/patterns/elastic/open-crawler-configs.md`
- `hive-mind/patterns/elastic/open-crawler-extraction.md`
- `hive-mind/patterns/elastic/open-crawler-extraction-patterns.md`
- `hive-mind/patterns/elastic/open-crawler-extraction-testing.md`
- `hive-mind/patterns/elastic/open-crawler-elasticsearch.md`
- `hive-mind/patterns/elastic/open-crawler-fast-iteration.md`
- `hive-mind/patterns/elastic/open-crawler-quickstart.md`
- `hive-mind/patterns/elastic/open-crawler-reference.md`
- `hive-mind/troubleshooting/open-crawler-common-issues.md`
- `hive-mind/troubleshooting/open-crawler-file-output-issues.md`

## Knowledge Structure

### 1. Configuration Structure

Core configuration format and settings:

- **[Base Configuration](config-structure/base-config.md)**
  - Config format (v0.4 flat structure)
  - Required fields
  - Output sink configurations
  - Domain configuration
  - Reserved field names
  - Docker setup requirements

### 2. Extraction Rules

Rules for extracting structured data from HTML:

- **[Extraction Basics](extraction-rules/extraction-basics.md)**
  - Critical rule: `join_as` required
  - Basic structure
  - URL filters for extraction
  - Common mistakes
  - Testing workflow

- **[Extraction Patterns](extraction-rules/extraction-patterns.md)**
  - Reusable patterns for common data types:
    - Publish dates
    - Authors
    - Prices and ratings
    - Categories and tags
    - Content extraction
    - E-commerce patterns
    - Blog/article patterns
    - Documentation patterns

### 3. Validation Rules

Rules for controlling crawl behavior and validating configs:

- **[Crawl Rules](validation-rules/crawl-rules.md)**
  - Pattern types (begins, ends, contains, regex, equals)
  - Rule evaluation order
  - Common patterns by site type
  - Debugging crawl rules

- **[Validation Checklist](validation-rules/validation-checklist.md)**
  - Critical validation rules
  - Field validation
  - Reserved field names
  - Value constraints
  - Validation commands
  - Common validation errors

### 4. Patterns

Workflow patterns and best practices:

- **[Testing Workflow](patterns/testing-workflow.md)**
  - Fast iteration workflow (console-first)
  - Step-by-step testing strategy
  - When to use each command
  - Anti-patterns to avoid
  - Debug mode

- **[Docker Setup](patterns/docker-setup.md)**
  - Docker compose configuration
  - Directory structure
  - File output requirements
  - Environment variables
  - Helper scripts
  - Production considerations

### 5. Troubleshooting

Common errors and solutions:

- **[Common Errors](troubleshooting/common-errors.md)**
  - Configuration errors
  - Connection errors
  - Crawl issues
  - Extraction issues
  - Docker issues
  - Performance issues
  - Quick fixes reference

## Quick Start Guide

### New to Open Crawler?

1. Read: [Base Configuration](config-structure/base-config.md)
2. Read: [Testing Workflow](patterns/testing-workflow.md)
3. Read: [Docker Setup](patterns/docker-setup.md)
4. Start with console output, then file, then ES

### Working on Extraction Rules?

1. Read: [Extraction Basics](extraction-rules/extraction-basics.md)
2. Browse: [Extraction Patterns](extraction-rules/extraction-patterns.md)
3. Test with file output
4. Use browser console to test selectors

### Debugging Issues?

1. Check: [Common Errors](troubleshooting/common-errors.md)
2. Enable: `log_level: debug`
3. Validate: `bin/crawler validate /config/your-config.yml`
4. Test single URL: `bin/crawler urltest`

## Critical Rules to Remember

### 1. Config Format is Flat (v0.4+)

```yaml
# ✅ CORRECT
user_agent: "MyCrawler/1.0"
max_crawl_depth: 3

# ❌ WRONG (v0.1 format)
http:
  user_agent: "MyCrawler/1.0"
```

### 2. join_as is REQUIRED

```yaml
# ✅ CORRECT
- action: extract
  field_name: author
  selector: ".author"
  source: html
  join_as: string

# ❌ WRONG (missing join_as)
- action: extract
  field_name: author
  selector: ".author"
  source: html
```

### 3. File Output Requires max_crawl_depth ≥ 1

```yaml
# ✅ CORRECT
output_sink: file
max_crawl_depth: 1

# ❌ WRONG (no files created)
output_sink: file
max_crawl_depth: 0
```

### 4. No Environment Variable Substitution

```yaml
# ❌ DOES NOT WORK
elasticsearch:
  host: "${ES_HOST}"

# ✅ Use shell expansion
# cat > config.yml << EOF
# elasticsearch:
#   host: $ES_HOST
# EOF
```

### 5. Domain URL Must Not Have Path

```yaml
# ✅ CORRECT
domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/

# ❌ WRONG
domains:
  - url: https://example.com/
```

## Fast Iteration Workflow

```text
urltest → validate → console → file → validate results → elasticsearch
fastest    check      debug     inspect     quality check      production
```

Always start with simple, fast tests. Only use Elasticsearch after config is proven to work.

## Common Use Cases

### Case 1: Blog Site

**Documents to read**:
1. [Base Configuration](config-structure/base-config.md)
2. [Crawl Rules](validation-rules/crawl-rules.md) - section: "Blog Site"
3. [Extraction Patterns](extraction-rules/extraction-patterns.md) - section: "Blog / Article Patterns"

### Case 2: E-commerce Site

**Documents to read**:
1. [Base Configuration](config-structure/base-config.md)
2. [Crawl Rules](validation-rules/crawl-rules.md) - section: "E-commerce Site"
3. [Extraction Patterns](extraction-rules/extraction-patterns.md) - section: "E-commerce / Products"

### Case 3: Documentation Site

**Documents to read**:
1. [Base Configuration](config-structure/base-config.md)
2. [Crawl Rules](validation-rules/crawl-rules.md) - section: "Documentation Site"
3. [Extraction Patterns](extraction-rules/extraction-patterns.md) - section: "Documentation Patterns"

## Validation Commands

```bash
# Validate config syntax
docker compose run --rm crawler bin/crawler validate /config/configs/test.yml

# Test single URL
docker compose run --rm crawler bin/crawler urltest /config/configs/test.yml https://example.com

# Run crawl
docker compose run --rm crawler bin/crawler crawl /config/configs/test.yml

# Debug mode
docker compose run --rm crawler bin/crawler crawl /config/configs/test.yml --log-level debug
```

## Reserved Field Names (NEVER USE)

- `id`, `title`, `body`, `body_content`
- `url`, `url_host`, `url_path`, `url_port`, `url_scheme`
- `links`, `headings`
- `meta_description`, `meta_keywords`
- `last_crawled_at`, `domains`, `additional_urls`

**Always use prefixed names**: `article_title`, `blog_content`, `product_price`, `custom_field`

## URL Filter Types by Context

| Type | crawl_rules | extraction_rulesets |
|------|-------------|---------------------|
| `begins` | ✅ | ✅ |
| `ends` | ✅ | ✅ |
| `contains` | ✅ | ✅ |
| `regex` | ✅ | ✅ |
| `equals` | ✅ | ❌ NOT SUPPORTED |

## Document Cross-References

### For Config Generation Agents

Key documents to reference when generating configs:

1. **Base structure**: [Base Configuration](config-structure/base-config.md)
2. **Extraction rules**: [Extraction Basics](extraction-rules/extraction-basics.md)
3. **Patterns library**: [Extraction Patterns](extraction-rules/extraction-patterns.md)
4. **Validation**: [Validation Checklist](validation-rules/validation-checklist.md)

### For Site Investigation Agents

Key documents to reference when analyzing sites:

1. **Selector patterns**: [Extraction Patterns](extraction-rules/extraction-patterns.md)
2. **Testing workflow**: [Testing Workflow](patterns/testing-workflow.md)
3. **Troubleshooting**: [Common Errors](troubleshooting/common-errors.md)

### For Config Validation Agents

Key documents to reference when validating configs:

1. **Validation rules**: [Validation Checklist](validation-rules/validation-checklist.md)
2. **Common errors**: [Common Errors](troubleshooting/common-errors.md)
3. **Base config**: [Base Configuration](config-structure/base-config.md)

## Version Information

- **Crawler Version**: 0.4.2
- **Docker Image**: `docker.elastic.co/integrations/crawler:0.4.2`
- **Config Format**: v0.4 (flat structure)
- **Knowledge Base Created**: 2026-02-02
- **Source**: elastic/hive-mind repository

## Updates and Maintenance

This knowledge base should be updated when:
- Open Crawler releases new versions
- New patterns discovered in hive-mind
- Critical issues identified
- Validation rules change

## Related Resources

- [Open Crawler GitHub](https://github.com/elastic/crawler)
- [Elastic Hive-mind](https://github.com/elastic/hive-mind)
- [Open Crawler Documentation](https://github.com/elastic/crawler/tree/main/docs)

---

**Next Steps**:
1. Start with [Base Configuration](config-structure/base-config.md)
2. Follow [Testing Workflow](patterns/testing-workflow.md)
3. Reference patterns as needed
4. Troubleshoot with [Common Errors](troubleshooting/common-errors.md)
