# Crawl Rules

> Extracted from hive-mind open-crawler guides
> Last Updated: 2026-02-02
> Version: Open Crawler 0.4.2

## Overview

Crawl rules control which URLs the crawler follows. They are evaluated in order, with the first matching rule determining whether a URL is allowed or denied.

## Basic Structure

```yaml
domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/
    
    crawl_rules:
      - policy: allow
        type: begins
        pattern: /blog/
      - policy: deny
        type: regex
        pattern: ".*"
```

## Rule Fields

| Field | Required | Values | Description |
|-------|----------|--------|-------------|
| `policy` | Yes | `allow`, `deny` | Allow or block URLs |
| `type` | Yes | `begins`, `ends`, `contains`, `regex`, `equals` | Pattern type |
| `pattern` | Yes | string | Pattern to match against URL path |

## Pattern Types

| Type | Description | Example | Matches |
|------|-------------|---------|---------|
| `begins` | Path starts with | `/blog/` | `/blog/post1`, `/blog/category/tech` |
| `ends` | Path ends with | `.html` | `/page.html`, `/blog/post.html` |
| `contains` | Path contains | `product` | `/products/item`, `/category/product-list` |
| `equals` | Path exactly matches | `/about` | `/about` (only) |
| `regex` | Regular expression | `"/page/\\d+"` | `/page/1`, `/page/42` |

## Common Patterns

### Allow Specific Section

```yaml
crawl_rules:
  # Allow blog section
  - policy: allow
    type: begins
    pattern: /blog/
  
  # Deny everything else
  - policy: deny
    type: regex
    pattern: ".*"
```

### Exclude Specific Paths

```yaml
crawl_rules:
  # Block admin and login pages
  - policy: deny
    type: begins
    pattern: /admin/
  
  - policy: deny
    type: begins
    pattern: /login/
  
  # Allow everything else (implicitly)
```

### Multiple Allowed Sections

```yaml
crawl_rules:
  # Allow multiple sections
  - policy: allow
    type: begins
    pattern: /blog/
  
  - policy: allow
    type: begins
    pattern: /docs/
  
  - policy: allow
    type: begins
    pattern: /guides/
  
  # Deny everything else
  - policy: deny
    type: regex
    pattern: ".*"
```

### File Type Filtering

```yaml
crawl_rules:
  # Block media files
  - policy: deny
    type: regex
    pattern: "\\.(pdf|zip|mp4|jpg|png|gif)$"
  
  # Block query parameters
  - policy: deny
    type: contains
    pattern: "?"
```

### Exact Page Matching

```yaml
crawl_rules:
  # Allow specific pages
  - policy: allow
    type: equals
    pattern: /
  
  - policy: allow
    type: equals
    pattern: /about
  
  - policy: allow
    type: equals
    pattern: /contact
  
  # Deny everything else
  - policy: deny
    type: regex
    pattern: ".*"
```

## Rule Evaluation Order

Rules are evaluated **in order** from top to bottom. The first matching rule wins.

```yaml
# Example: Only allow /blog/ posts, not category pages
crawl_rules:
  # Block category pages first
  - policy: deny
    type: begins
    pattern: /blog/category/
  
  # Then allow blog posts
  - policy: allow
    type: begins
    pattern: /blog/
  
  # Deny everything else
  - policy: deny
    type: regex
    pattern: ".*"
```

**Order matters!** If you reversed these rules, `/blog/category/` would be allowed by the second rule.

## Regex Patterns

### Common Regex Examples

```yaml
# Match year-based URLs
- policy: allow
  type: regex
  pattern: "/\\d{4}/"  # Matches /2024/, /2023/, etc.

# Match numbered pages
- policy: allow
  type: regex
  pattern: "/page/\\d+"  # Matches /page/1, /page/42

# Exclude query strings
- policy: deny
  type: regex
  pattern: "\\?"  # Matches any URL with ?

# Exclude file extensions
- policy: deny
  type: regex
  pattern: "\\.(pdf|zip|exe)$"

# Match specific format
- policy: allow
  type: regex
  pattern: "^/products/[a-z0-9-]+$"
```

### Regex Escaping

**Important**: In YAML strings, backslashes must be escaped:

```yaml
# ❌ WRONG - will not work as expected
pattern: "/page/\d+"

# ✅ CORRECT - escape backslashes
pattern: "/page/\\d+"

# OR use single quotes (no escaping needed)
pattern: '/page/\d+'
```

## Default Behavior

If no crawl rules are specified:
- All URLs on the same domain are crawled
- External links are not followed
- Respects `max_crawl_depth` setting

## Testing Crawl Rules

### Step 1: Use Console Output

```yaml
output_sink: console
max_crawl_depth: 1  # Shallow test
log_level: debug    # See rule evaluation
```

### Step 2: Run Crawl

```bash
docker compose run --rm crawler bin/crawler crawl /config/test.yml
```

### Step 3: Check Stats

```
urls_denied={:rule_engine_denied=>199, :already_seen=>92, :link_too_deep=>136}
```

| Stat | Meaning |
|------|---------|
| `rule_engine_denied` | Blocked by your crawl rules |
| `already_seen` | Deduplicated (same URL visited) |
| `link_too_deep` | Exceeded `max_crawl_depth` |
| `domain_filter` | URL on different domain |

## Common Patterns by Site Type

### Documentation Site

```yaml
# Crawl all docs, exclude navigation/search
crawl_rules:
  - policy: allow
    type: begins
    pattern: /docs/
  
  - policy: deny
    type: contains
    pattern: /search
  
  - policy: deny
    type: regex
    pattern: ".*"
```

### Blog Site

```yaml
# Posts only, no archives/categories
crawl_rules:
  - policy: deny
    type: begins
    pattern: /category/
  
  - policy: deny
    type: begins
    pattern: /tag/
  
  - policy: deny
    type: begins
    pattern: /author/
  
  - policy: allow
    type: begins
    pattern: /blog/
  
  - policy: deny
    type: regex
    pattern: ".*"
```

### E-commerce Site

```yaml
# Product pages only
crawl_rules:
  - policy: allow
    type: begins
    pattern: /products/
  
  # Exclude filters, cart, checkout
  - policy: deny
    type: contains
    pattern: "?"
  
  - policy: deny
    type: begins
    pattern: /cart
  
  - policy: deny
    type: begins
    pattern: /checkout
  
  - policy: deny
    type: regex
    pattern: ".*"
```

## Debugging

### Problem: Too Many URLs Denied

**Check**: Are your rules too restrictive?

```bash
# Run with debug logging
docker compose run --rm crawler bin/crawler crawl /config/test.yml --log-level debug
```

Look for: `Rule engine denied URL: ...`

### Problem: Wrong Pages Crawled

**Check**: Rule order and specificity

```yaml
# Common mistake: broad rule before specific one
# ❌ WRONG ORDER
- policy: allow
  type: begins
  pattern: /blog/  # This allows /blog/category/ too!

- policy: deny
  type: begins
  pattern: /blog/category/  # Never reached!

# ✅ CORRECT ORDER
- policy: deny
  type: begins
  pattern: /blog/category/  # Specific first

- policy: allow
  type: begins
  pattern: /blog/  # Broad second
```

### Problem: External Links Followed

External links are not followed by default. If they are:

```yaml
# Explicitly deny external domains
crawl_rules:
  - policy: deny
    type: regex
    pattern: "^https?://(?!example\\.com)"
```

## Combining with max_crawl_depth

```yaml
domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/blog/
    
    crawl_rules:
      - policy: allow
        type: begins
        pattern: /blog/

# Controls crawl depth from seed URLs
max_crawl_depth: 2  # seed + 2 levels deep
```

## Best Practices

1. **Start permissive, then restrict**: Test without rules first
2. **Use debug logging**: See which URLs are denied and why
3. **Test with shallow depth**: Use `max_crawl_depth: 1` for testing
4. **Specific before general**: Put specific rules before broad ones
5. **Always validate**: Use `bin/crawler validate` before running

## Validation

```bash
# Validate crawl rules
docker compose run --rm crawler bin/crawler validate /config/your-config.yml
```

## Related Documents

- [Base Configuration](../config-structure/base-config.md)
- [Extraction Rules](../extraction-rules/extraction-basics.md)
- [Testing Workflow](../patterns/testing-workflow.md)
