# Site Investigation Specification

## Purpose
Investigate target websites to understand their structure, content patterns, and crawlability before generating Open Crawler configurations.

## Requirements

### Requirement: Initial Site Checks
The system SHALL perform upfront checks to fail fast and gather foundational information.

#### Scenario: Robots.txt Collection
- GIVEN a target domain is provided
- WHEN the investigation begins
- THEN fetch and parse `robots.txt` from the domain root
- AND extract crawl rules, sitemap URLs, and disallowed paths
- AND store this information for later stages

#### Scenario: Basic Connectivity Test
- GIVEN a target domain is provided
- WHEN the investigation begins
- THEN perform curl/HTTP requests to verify site accessibility
- AND detect bot protection or blocking mechanisms
- AND if critical blocking is detected, return to user with error

### Requirement: Page Structure Analysis
The system SHALL analyze page structure across multiple sample pages to identify content patterns.

#### Scenario: Sample Page Collection
- GIVEN a target domain is provided
- WHEN analyzing page structure
- THEN fetch at least 10 sample pages from different sections of the site
- AND analyze HTML structure (headings, content areas, navigation)
- AND identify common patterns and variations

#### Scenario: Content Pattern Identification
- GIVEN sample pages have been collected
- WHEN analyzing content patterns
- THEN identify:
  - Main content areas (article body, product descriptions, etc.)
  - Metadata fields (title, author, date, etc.)
  - Navigation structures
  - URL patterns and depth
- AND document patterns for extraction rule generation

### Requirement: Sitemap Analysis
The system SHALL analyze sitemaps when available to understand site structure.

#### Scenario: Sitemap Discovery
- GIVEN robots.txt has been parsed
- WHEN sitemap URLs are found
- THEN fetch and parse sitemap(s)
- AND extract URL patterns, priorities, and change frequencies
- AND use this information to inform crawl rules

### Requirement: LLM-Powered Analysis
The system SHALL use LLM to analyze collected data and make recommendations.

#### Scenario: Structure Analysis
- GIVEN page HTML and structure data has been collected
- WHEN analyzing with LLM
- THEN provide HTML samples and structure data to LLM
- AND request analysis of:
  - Content extraction opportunities
  - Crawl rule strategy recommendations
  - Potential challenges (bot protection, dynamic content, etc.)
- AND capture LLM reasoning for user review

#### Scenario: User Validation
- GIVEN LLM has made initial recommendations
- WHEN recommendations are ready
- THEN present recommendations to user:
  - Proposed crawl rule strategy
  - Suggested content to extract
  - Identified challenges
- AND wait for user confirmation before proceeding to config generation

### Requirement: Site Analysis Report
The system SHALL produce a structured report for downstream agents.

#### Scenario: Report Generation
- GIVEN investigation is complete
- WHEN generating report
- THEN create structured report containing:
  - Domain information
  - Robots.txt findings
  - Sitemap information
  - Page structure patterns
  - Content extraction opportunities
  - Crawl rule recommendations
  - Identified challenges
- AND make report available to config generation agent

## Technical Details

### Input
- Target domain(s)
- Optional: Seed URLs
- Optional: Demo scenario context

### Output
- Site analysis report (structured data)
- LLM recommendations (with reasoning)
- User confirmation status

### Dependencies
- HTTP client for fetching pages
- LLM Proxy for analysis
- robots.txt parser
- Sitemap parser

### Error Handling
- Network failures: Retry with exponential backoff, then return to user
- Bot protection: Detect and return to user immediately
- Parse errors: Log and continue with available data
