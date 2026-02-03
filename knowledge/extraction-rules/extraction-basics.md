# Extraction Rules Basics

> Extracted from hive-mind open-crawler guides
> Last Updated: 2026-02-02
> Version: Open Crawler 0.4.2

## Overview

Extraction rules let you pull specific content from HTML into custom Elasticsearch fields. This is essential for structured data extraction (prices, authors, dates, etc.).

## Critical Rule: `join_as` is REQUIRED

Every extraction rule **must** include `join_as`:

```yaml
# ❌ FAILS - missing join_as
- action: extract
  field_name: author
  selector: ".author"
  source: html

# ✅ WORKS
- action: extract
  field_name: author
  selector: ".author"
  source: html
  join_as: array  # or 'string' - REQUIRED!
```

## Basic Structure

```yaml
domains:
  - url: https://example.com
    extraction_rulesets:
      - url_filters:           # Optional - scope to specific URLs
          - type: begins
            pattern: /products/
        rules:
          - action: extract
            field_name: price
            selector: ".price"
            source: html
            join_as: array
```

## Extraction Rule Fields

| Field | Required | Values | Description |
|-------|----------|--------|-------------|
| `action` | Yes | `extract`, `set` | Extract from HTML or set fixed value |
| `field_name` | Yes | string | Custom field name in ES document |
| `selector` | Yes | CSS selector | What to extract |
| `source` | Yes | `html`, `url` | Extract from HTML or URL |
| `join_as` | **Yes!** | `array`, `string` | How to combine multiple matches |

## join_as Values

| Value | Result | Use Case |
|-------|--------|----------|
| `array` | `["value1", "value2"]` | Multiple items (tags, prices, headings) |
| `string` | `"value1 value2"` | Single concatenated value (joined with space) |

```yaml
# Multiple values as array
- action: extract
  field_name: tags
  selector: ".tag"
  source: html
  join_as: array
# Result: {"tags": ["tag1", "tag2", "tag3"]}

# Multiple values as string
- action: extract
  field_name: full_text
  selector: "p"
  source: html
  join_as: string
# Result: {"full_text": "para1 para2 para3"}
```

## URL Filters for Extraction Rules

URL filters scope extraction rules to specific URL patterns:

| Type | Supported? | Description | Example |
|------|-----------|-------------|---------|
| `begins` | ✅ | Path starts with | `/blog/` |
| `ends` | ✅ | Path ends with | `.html` |
| `contains` | ✅ | Path contains | `product` |
| `regex` | ✅ | Regex pattern | `"^/about$"` |
| `equals` | ❌ | **NOT SUPPORTED** | Use regex instead |

```yaml
# ❌ WRONG - equals not supported in extraction URL filters
extraction_rulesets:
  - url_filters:
      - type: equals
        pattern: /about

# ✅ CORRECT - use regex for exact match
extraction_rulesets:
  - url_filters:
      - type: regex
        pattern: "^/about$"
```

## Basic Extraction Patterns

### Single Field Extraction

```yaml
extraction_rulesets:
  - rules:
      - action: extract
        field_name: article_title
        selector: "h1"
        source: html
        join_as: string
```

### Multiple Fields

```yaml
extraction_rulesets:
  - rules:
      - action: extract
        field_name: article_title
        selector: "h1"
        source: html
        join_as: string
      
      - action: extract
        field_name: article_author
        selector: ".author"
        source: html
        join_as: string
      
      - action: extract
        field_name: tags
        selector: ".tag"
        source: html
        join_as: array
```

### URL-Specific Extraction

```yaml
extraction_rulesets:
  # Blog posts
  - url_filters:
      - type: begins
        pattern: /blog/
    rules:
      - action: extract
        field_name: blog_title
        selector: "h1.post-title"
        source: html
        join_as: string
  
  # Product pages
  - url_filters:
      - type: begins
        pattern: /products/
    rules:
      - action: extract
        field_name: product_price
        selector: ".price"
        source: html
        join_as: string
```

## CSS Selector Basics

| Selector | Matches | Example |
|----------|---------|---------|
| `.class` | Elements with class | `.price` |
| `#id` | Element with ID | `#main-content` |
| `.parent .child` | Nested elements | `.article .author` |
| `h1, h2` | Multiple selectors | `h1, h2, h3` |
| `[data-price]` | Elements with attribute | `[data-price]` |
| `table tr:first-child` | First child | `ul li:first-child` |

### Finding CSS Selectors

1. Open browser DevTools (F12)
2. Click element selector tool (arrow icon)
3. Click on content you want
4. Right-click in Elements panel → Copy → Copy selector
5. Test in Console: `document.querySelectorAll('your-selector')`

**Tip:** Browser-copied selectors are often too specific. Simplify them!

## Debugging Extraction

### Problem: Extracted fields not appearing

1. **Use file output** (not console):

```yaml
output_sink: file
output_dir: /config/results/test
max_crawl_depth: 1
```

2. **Check the JSON:**

```bash
cat results/test/*.json | python3 -m json.tool
```

3. **Console shows raw HTML** - you won't see extracted fields there!

### Problem: URL filters not matching

**Solution:** Remove URL filters first, verify extraction works, then add filters back.

```yaml
# Start simple - no filters
extraction_rulesets:
  - rules:  # No url_filters
      - action: extract
        field_name: test
        selector: "h1"
        source: html
        join_as: string
```

## Common Mistakes

1. **Missing `join_as`** - Config will fail validation
2. **Using console to debug extraction** - Use file output instead
3. **Complex selectors** - Start simple, add specificity later
4. **URL filter regex issues** - Test without filters first
5. **Using reserved field names** - Always prefix custom fields

## Reserved Field Names (NEVER USE)

```yaml
# ❌ NEVER use these as field_name:
- id
- title          # Use: article_title, custom_title
- body           # Use: article_body, custom_content
- body_content   # Use: main_content
- url            # Automatic
- links          # Automatic
- headings       # Automatic
- meta_description  # Automatic
- meta_keywords     # Automatic
- last_crawled_at   # Automatic
- domains           # Automatic
- url_host, url_path, url_port, url_scheme  # Automatic

# ✅ ALWAYS use prefixed names:
- article_title
- blog_content
- product_price
- custom_field
```

## Field Naming Conventions (IMPORTANT)

The crawler controller uses **convention-based field mapping** based on field name suffixes. Use these suffixes to control how your extracted fields are indexed in Elasticsearch:

| Suffix | Elasticsearch Mapping | Use Case |
|--------|----------------------|----------|
| `_semantic` | text + keyword + ELSER + Jina embeddings | **Semantic search** - questions, concepts |
| `_text` | text + keyword | **Full-text search** - regular searchable content |
| `_keyword` | keyword only | **Exact match** - categories, IDs, tags for filtering |
| `_date` | date | **Timestamps** - publish dates, etc. |
| `_num`, `_count`, `_price`, `_score` | float | **Numeric values** - prices, ratings, counts |
| (no suffix) | text + keyword | **Default** - standard text behavior |

### When to Use Each Suffix

**Use `_semantic` for fields you want to search by meaning:**
```yaml
- action: extract
  field_name: product_description_semantic  # Semantic search enabled
  selector: ".description"
  source: html
  join_as: string
```
- Product descriptions users might search with questions
- Article content for "find similar" features
- FAQ answers

**Use `_text` for regular searchable content:**
```yaml
- action: extract
  field_name: author_name_text  # Searchable, no embeddings
  selector: ".author"
  source: html
  join_as: string
```
- Author names, bylines
- Short descriptive text
- Content that doesn't need semantic understanding

**Use `_keyword` for filtering and exact match:**
```yaml
- action: extract
  field_name: category_keyword  # Exact match only
  selector: ".category"
  source: html
  join_as: string
```
- Categories, tags
- Product SKUs, IDs
- Status values (in-stock, published)

**Use `_date` for timestamps:**
```yaml
- action: extract
  field_name: published_date  # Parsed as date
  selector: "time[datetime]"
  source: html
  join_as: string
```

**Use numeric suffixes for numbers:**
```yaml
- action: extract
  field_name: product_price  # Indexed as float
  selector: ".price"
  source: html
  join_as: string

- action: extract
  field_name: review_count  # Indexed as float
  selector: ".reviews"
  source: html
  join_as: string
```

### Default Crawler Fields

These fields are **automatically mapped with semantic search** (no suffix needed):
- `title` - Page title
- `body` - Main content
- `headings` - Page headings

### Cost Consideration

Semantic fields (`_semantic` suffix) generate embeddings during indexing which:
- Takes longer to index
- Uses more storage
- Costs inference compute

**Only use `_semantic` for fields that truly benefit from semantic search.**

## Extraction from URL

```yaml
# Extract year from URL path
- action: extract
  field_name: year
  selector: "/blog/([0-9]{4})/"
  source: url
  join_as: string

# Extract category from URL
- action: extract
  field_name: category
  selector: "/products/([^/]+)/"
  source: url
  join_as: string
```

## Testing Workflow

### Step 1: Start Simple

```yaml
# Single field, no URL filters
extraction_rulesets:
  - rules:
      - action: extract
        field_name: test_title
        selector: "h1"
        source: html
        join_as: string
```

### Step 2: Test Selector in Browser

```javascript
// Browser console
document.querySelectorAll('h1')
document.querySelector('.author')?.textContent
```

### Step 3: Run with File Output

```bash
docker compose run --rm crawler bin/crawler crawl /config/test.yml
cat results/test/*.json | jq '.test_title'
```

### Step 4: Add More Fields

```yaml
extraction_rulesets:
  - rules:
      - action: extract
        field_name: test_title
        selector: "h1"
        source: html
        join_as: string
      
      - action: extract
        field_name: test_author
        selector: ".author"
        source: html
        join_as: string
```

### Step 5: Add URL Filters

```yaml
extraction_rulesets:
  - url_filters:
      - type: begins
        pattern: /blog/
    rules:
      - action: extract
        field_name: blog_title
        selector: "h1"
        source: html
        join_as: string
```

## Validation

Always validate before running:

```bash
docker compose run --rm crawler bin/crawler validate /config/your-config.yml
```

## Related Documents

- [Extraction Patterns Library](./extraction-patterns.md)
- [Common Selectors](./common-selectors.md)
- [Base Configuration](../config-structure/base-config.md)
