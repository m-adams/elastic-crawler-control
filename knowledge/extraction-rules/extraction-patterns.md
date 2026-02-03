# Common Extraction Patterns

> Extracted from hive-mind open-crawler guides
> Last Updated: 2026-02-02
> Reusable extraction rule snippets for common data types

## Field Naming Conventions

**Use these suffixes** to control Elasticsearch mapping (see [extraction-basics.md](./extraction-basics.md) for details):

| Suffix | Mapping | Example |
|--------|---------|---------|
| `_semantic` | text + ELSER + Jina | `product_description_semantic` |
| `_text` | text + keyword | `author_name_text` |
| `_keyword` | keyword only | `category_keyword` |
| `_date` | date type | `publish_date` |
| `_num`, `_price`, `_count`, `_score` | float | `product_price`, `review_count` |

## Quick Reference

| Pattern | Primary Selector | Fallback Selectors |
|---------|-----------------|-------------------|
| [Publish Date](#publish-date) | `time[datetime]` | `.date`, `meta[property="article:published_time"]` |
| [Author](#author) | `.author` | `.byline`, `[rel="author"]`, `meta[name="author"]` |
| [Price](#price) | `.price` | `[data-price]`, `.cost`, `[itemprop="price"]` |
| [Rating](#rating) | `.rating` | `[data-rating]`, `.stars`, `[itemprop="ratingValue"]` |
| [Category](#category) | `.breadcrumb li` | `.category`, `nav.taxonomy` |
| [Tags](#tags-and-labels) | `.tags .tag` | `.labels`, `[rel="tag"]` |

---

## Publish Date

### HTML5 Time Element (Best)

```yaml
- action: extract
  field_name: publish_date
  selector: "time[datetime]"
  source: html
  join_as: string
```

### Meta Tags

```yaml
# Schema.org / Open Graph
- action: extract
  field_name: publish_date
  selector: "meta[property='article:published_time'], meta[name='date']"
  source: html
  join_as: string
```

### CSS Classes (Fallback)

```yaml
- action: extract
  field_name: publish_date
  selector: ".date, .published, .post-date, .entry-date, .article-date"
  source: html
  join_as: string
```

### Last Modified Date

```yaml
- action: extract
  field_name: last_updated
  selector: "time[itemprop='dateModified'], meta[property='article:modified_time'], .updated"
  source: html
  join_as: string
```

---

## Author

### Standard Author

```yaml
- action: extract
  field_name: author_name
  selector: ".author, .byline, [rel='author']"
  source: html
  join_as: string
```

### Meta Tag

```yaml
- action: extract
  field_name: author_name
  selector: "meta[name='author']"
  source: html
  join_as: string
```

### Schema.org

```yaml
- action: extract
  field_name: author_name
  selector: "[itemprop='author'], [itemtype*='Person'] [itemprop='name']"
  source: html
  join_as: string
```

### Multiple Authors

```yaml
- action: extract
  field_name: authors
  selector: ".author, .byline .name"
  source: html
  join_as: array
```

---

## Price

### Standard Price

```yaml
- action: extract
  field_name: product_price
  selector: ".price, [data-price], .product-price"
  source: html
  join_as: string
```

### Schema.org Price

```yaml
- action: extract
  field_name: product_price
  selector: "[itemprop='price'], .price_color, .product-price"
  source: html
  join_as: string

# Currency
- action: extract
  field_name: currency
  selector: "[itemprop='priceCurrency'], meta[itemprop='priceCurrency']"
  source: html
  join_as: string
```

### Sale Prices

```yaml
# Current/sale price
- action: extract
  field_name: sale_price
  selector: ".sale-price, .current-price, .price-sale"
  source: html
  join_as: string

# Original price
- action: extract
  field_name: original_price
  selector: ".original-price, .was-price, .price-original, del .price"
  source: html
  join_as: string
```

---

## Rating

### Star Rating

```yaml
- action: extract
  field_name: rating
  selector: ".rating, .stars, [data-rating], [data-score]"
  source: html
  join_as: string
```

### Schema.org Rating

```yaml
- action: extract
  field_name: rating_value
  selector: "[itemprop='ratingValue']"
  source: html
  join_as: string

- action: extract
  field_name: rating_count
  selector: "[itemprop='ratingCount'], [itemprop='reviewCount']"
  source: html
  join_as: string

- action: extract
  field_name: rating_best
  selector: "[itemprop='bestRating']"
  source: html
  join_as: string
```

---

## Category

### Breadcrumb Navigation

```yaml
# Full breadcrumb path as array
- action: extract
  field_name: breadcrumbs
  selector: ".breadcrumb li, nav.breadcrumbs a, .breadcrumb-item"
  source: html
  join_as: array

# Last breadcrumb (current category)
- action: extract
  field_name: category
  selector: ".breadcrumb li:last-child, .breadcrumb-item:last-child"
  source: html
  join_as: string
```

### Schema.org Breadcrumb

```yaml
- action: extract
  field_name: breadcrumbs
  selector: "[itemtype*='BreadcrumbList'] [itemprop='name']"
  source: html
  join_as: array
```

### Simple Category

```yaml
- action: extract
  field_name: category
  selector: ".category, .post-category, .entry-category, [rel='category tag']"
  source: html
  join_as: string
```

---

## Tags and Labels

### Tag List

```yaml
- action: extract
  field_name: tags
  selector: ".tags .tag, .tag-list a, .post-tags a, [rel='tag']"
  source: html
  join_as: array
```

### Meta Keywords

```yaml
- action: extract
  field_name: keywords
  selector: "meta[name='keywords']"
  source: html
  join_as: string
```

---

## Content Extraction

### Article Body

```yaml
- action: extract
  field_name: article_body
  selector: "article, .post-content, .entry-content, .article-body, [itemprop='articleBody']"
  source: html
  join_as: string
```

### Summary / Excerpt

```yaml
- action: extract
  field_name: summary
  selector: ".excerpt, .summary, .lead, meta[name='description'], meta[property='og:description']"
  source: html
  join_as: string
```

### Code Blocks

```yaml
- action: extract
  field_name: code_blocks
  selector: "pre code, .highlight code, .code-block"
  source: html
  join_as: array
```

### Images

```yaml
# Featured image
- action: extract
  field_name: featured_image
  selector: ".featured-image img, article img:first-of-type, meta[property='og:image']"
  source: html
  join_as: string

# All images
- action: extract
  field_name: images
  selector: "article img, .content img"
  source: html
  join_as: array
```

---

## E-commerce / Products

### Product Name

```yaml
# Use _text for searchable product names
- action: extract
  field_name: product_name_text
  selector: ".product-title, h1.product-name, [itemprop='name']"
  source: html
  join_as: string
```

### Product Description (with semantic search)

```yaml
# Use _semantic for product descriptions users might search with questions
- action: extract
  field_name: product_description_semantic
  selector: ".product-description, [itemprop='description']"
  source: html
  join_as: string
```

### SKU / Product ID

```yaml
# Use _keyword for exact match / filtering
- action: extract
  field_name: sku_keyword
  selector: "[itemprop='sku'], .sku, .product-id"
  source: html
  join_as: string
```

### Availability

```yaml
# Use _keyword for status filtering
- action: extract
  field_name: availability_keyword
  selector: ".availability, .stock-status, [itemprop='availability']"
  source: html
  join_as: string
```

### Brand

```yaml
# Use _keyword for brand filtering/faceting
- action: extract
  field_name: brand_keyword
  selector: ".brand, [itemprop='brand'], .manufacturer"
  source: html
  join_as: string
```

---

## Blog / Article Patterns

### Complete Blog Post

```yaml
extraction_rulesets:
  - url_filters:
      - type: begins
        pattern: /blog/
    rules:
      # Searchable text (no semantic needed for short titles)
      - action: extract
        field_name: article_title_text
        selector: "h1, article header h1"
        source: html
        join_as: string
      
      # Author as searchable text
      - action: extract
        field_name: article_author_text
        selector: "a[href*='/author/'], .author-name, .byline"
        source: html
        join_as: string
      
      # Date (use _date suffix for date type)
      - action: extract
        field_name: publish_date
        selector: "time[datetime], .date-published"
        source: html
        join_as: string
      
      # Article body WITH semantic search (for conceptual queries)
      - action: extract
        field_name: article_body_semantic
        selector: "article, .post-content, .entry-content"
        source: html
        join_as: string
      
      # Tags as keywords for filtering/faceting
      - action: extract
        field_name: tags_keyword
        selector: ".tags .tag, .post-tags a"
        source: html
        join_as: array
```

---

## Documentation Patterns

### Documentation Page

```yaml
extraction_rulesets:
  - url_filters:
      - type: begins
        pattern: /docs/
    rules:
      - action: extract
        field_name: doc_title
        selector: "h1"
        source: html
        join_as: string
      
      - action: extract
        field_name: breadcrumbs
        selector: ".related li a, nav.breadcrumb a"
        source: html
        join_as: array
      
      - action: extract
        field_name: section_headings
        selector: "h2, h3"
        source: html
        join_as: array
      
      - action: extract
        field_name: code_examples
        selector: ".highlight pre, pre.literal-block"
        source: html
        join_as: array
```

---

## News / Media Patterns

### News Article

```yaml
extraction_rulesets:
  - rules:
      - action: extract
        field_name: story_titles
        selector: ".titleline > a"
        source: html
        join_as: array
      
      - action: extract
        field_name: story_scores
        selector: ".score"
        source: html
        join_as: array
      
      - action: extract
        field_name: story_authors
        selector: ".hnuser"
        source: html
        join_as: array
      
      - action: extract
        field_name: story_times
        selector: ".age"
        source: html
        join_as: array
```

---

## Real Estate Patterns

### Property Listing

```yaml
extraction_rulesets:
  - url_filters:
      - type: contains
        pattern: /property/
    rules:
      - action: extract
        field_name: property_type
        selector: ".property-type, .listing-type"
        source: html
        join_as: string
      
      - action: extract
        field_name: bedrooms
        selector: ".beds, .bedrooms, [data-beds]"
        source: html
        join_as: string
      
      - action: extract
        field_name: bathrooms
        selector: ".baths, .bathrooms, [data-baths]"
        source: html
        join_as: string
      
      - action: extract
        field_name: square_feet
        selector: ".sqft, .area, [data-sqft]"
        source: html
        join_as: string
```

---

## Best Practices

### 1. Use Multiple Selectors (Fallbacks)

```yaml
# Comma-separated selectors try each until one matches
selector: ".author, .byline, [rel='author'], meta[name='author']"
```

### 2. Be Specific Enough

```yaml
# Too broad
selector: "a"

# Better - scoped to content area
selector: ".article-content a"
```

### 3. Use Data Attributes When Available

```yaml
# More reliable than text content
selector: "[data-price]"  # Instead of .price
```

### 4. Test Without URL Filters First

```yaml
# Start simple
extraction_rulesets:
  - rules:  # No url_filters initially
      - action: extract
        field_name: test_field
        selector: ".target"
        source: html
        join_as: string
```

### 5. Use Array for Multiple Items

```yaml
# Single value
join_as: string

# Multiple values (tags, authors, images)
join_as: array
```

---

## Selector Debugging

### Browser Console Test

```javascript
// Test your selector
document.querySelectorAll('.your-selector')

// Check count
document.querySelectorAll('.your-selector').length

// See content
[...document.querySelectorAll('.your-selector')].map(e => e.textContent)
```

### Common Issues

| Problem | Solution |
|---------|----------|
| No matches | Simplify selector, remove parent context |
| Too many matches | Add parent class or :first-of-type |
| Wrong content | Check if content is in attribute vs text |
| Empty result | Content may be JS-rendered |

---

## Related Documents

- [Extraction Basics](./extraction-basics.md)
- [Base Configuration](../config-structure/base-config.md)
- [Validation Rules](../validation-rules/crawl-rules.md)
