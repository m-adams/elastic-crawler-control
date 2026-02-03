# Workflow Input Specification

## Purpose
Define the structured input form that users fill out to initiate the Open Crawler config generation workflow.

## Requirements

### Requirement: Structured Input Form
The system SHALL collect structured input via a form rather than freeform chat.

#### Scenario: Initial Form Submission
- GIVEN user wants to generate a crawler config
- WHEN user accesses the config generator
- THEN present a structured form with required and optional fields
- AND validate input before starting workflow
- AND use form data to initialize the agent workflow

### Requirement: Required Fields
The system SHALL require essential information to start the workflow.

#### Scenario: Domain Information
- GIVEN user is filling out the form
- WHEN providing domain information
- THEN require:
  - Target domain(s) (at least one)
  - At least one seed URL per domain
- AND validate URL format
- AND allow multiple domains

#### Scenario: Demo Context
- GIVEN user is filling out the form
- WHEN providing demo context
- THEN require:
  - Demo scenario description (what are you trying to demonstrate?)
  - Content focus (what content is most important?)
- AND use this to guide extraction rule generation

### Requirement: Optional Fields
The system SHALL allow optional fields to refine the workflow.

#### Scenario: Advanced Options
- GIVEN user is filling out the form
- WHEN providing optional information
- THEN allow:
  - Expected content types (products, articles, documentation, etc.)
  - Known URL patterns (e.g., "/products/", "/blog/")
  - Specific fields to extract (if known)
  - Crawl depth preference
  - Output destination (Elasticsearch index name)
- AND use these to inform agent decisions

### Requirement: Input Validation
The system SHALL validate all input before starting workflow.

#### Scenario: URL Validation
- GIVEN user submits form
- WHEN validating URLs
- THEN check:
  - Valid URL format
  - Seed URLs belong to specified domains
  - URLs are accessible (basic connectivity check)
- AND report validation errors before starting

#### Scenario: Required Field Validation
- GIVEN user submits form
- WHEN validating required fields
- THEN ensure:
  - All required fields are present
  - Domain and seed URLs are provided
  - Demo scenario is not empty
- AND show clear error messages for missing fields

## Input Schema

### Form Fields

```typescript
interface CrawlerConfigRequest {
  // Required
  domains: DomainInput[];  // At least one domain
  demo_scenario: string;    // What are you demonstrating?
  content_focus: string;    // What content is most important?
  
  // Optional
  expected_content_types?: ContentType[];  // products, articles, docs, etc.
  specific_fields?: string[];                // Fields user knows they need
  crawl_depth_preference?: number;          // User's preference (agent may override)
  output_index?: string;                     // ES index name (if known)
  notes?: string;                            // Additional context
}

interface DomainInput {
  url: string;              // Domain URL, e.g., "https://example.com"
  
  // Crawl scope: Either provide example URLs OR a path regex pattern
  // At least one must be provided
  example_urls?: string[];  // Example URLs of pages to crawl (e.g., ["https://example.com/products/item-1"])
  path_pattern?: string;     // Regex pattern for paths to crawl (e.g., "/products/.*")
  
  label?: string;            // Optional label for multi-domain configs
}

enum ContentType {
  PRODUCTS = "products",
  ARTICLES = "articles",
  DOCUMENTATION = "documentation",
  NEWS = "news",
  EVENTS = "events",
  PROFILES = "profiles",
  OTHER = "other"
}
```

### Example Form Submissions

**Example 1: Using Example URLs**
```json
{
  "domains": [
    {
      "url": "https://example.com",
      "example_urls": [
        "https://example.com/products/item-1",
        "https://example.com/products/item-2"
      ],
      "label": "Main Site"
    }
  ],
  "demo_scenario": "Index product pages for search demo. Need to show product search with filters.",
  "content_focus": "Product information: name, description, price, images, categories, SKU",
  "expected_content_types": ["products"],
  "specific_fields": ["price", "sku", "category"],
  "crawl_depth_preference": 3,
  "output_index": "products-demo"
}
```

**Example 2: Using Path Pattern**
```json
{
  "domains": [
    {
      "url": "https://example.com",
      "path_pattern": "/products/.*",
      "label": "Main Site"
    }
  ],
  "demo_scenario": "Index product pages for search demo",
  "content_focus": "Product information: name, description, price, images",
  "expected_content_types": ["products"]
}
```

**Example 3: Mixed Approach (Multiple Domains)**
```json
{
  "domains": [
    {
      "url": "https://example.com",
      "example_urls": ["https://example.com/products/item-1"],
      "label": "Products"
    },
    {
      "url": "https://blog.example.com",
      "path_pattern": "/posts/.*",
      "label": "Blog"
    }
  ],
  "demo_scenario": "Index products and blog posts for unified search",
  "content_focus": "Product data and article content"
}
```

## Technical Details

### Input
- JSON form submission via POST `/api/chat`
- Form data validated before workflow starts

### Output
- Validated request object passed to workflow orchestrator
- Validation errors returned immediately if invalid

### Validation Rules
1. **Domains**: At least one domain required
2. **Crawl Scope**: For each domain, either `example_urls` OR `path_pattern` must be provided (not both required, but at least one)
3. **URL Format**: Domain URL and example URLs must be valid HTTP/HTTPS URLs
4. **Domain Match**: Example URLs must belong to their domain
5. **Path Pattern**: If provided, must be a valid regex pattern (will be validated)
6. **Demo Scenario**: Non-empty string, min 10 characters
7. **Content Focus**: Non-empty string, min 10 characters

### Error Handling
- Return 400 Bad Request with validation errors
- List all validation issues, not just the first
- Provide clear, actionable error messages
