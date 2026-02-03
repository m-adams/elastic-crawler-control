# Detailed Workflow Specification

## Purpose
Define the complete agentic workflow for generating Open Crawler configurations, following hive-mind patterns and best practices.

## Requirements

### Requirement: Workflow Phases
The system SHALL execute a multi-phase workflow with clear checkpoints.

#### Phase 1: Initial Validation & Setup
- GIVEN user submits form
- WHEN workflow starts
- THEN:
  1. Validate all input (URLs, required fields)
  2. Perform basic connectivity checks (curl/HTTP requests)
  3. Fetch robots.txt for each domain
  4. Detect bot protection or blocking
  5. If critical issues found, return to user immediately
- AND stream progress updates via SSE

#### Phase 2: Site Investigation
- GIVEN initial validation passed
- WHEN investigating sites
- THEN for each domain:
  1. Parse robots.txt and extract crawl rules
  2. Fetch and parse sitemap(s) if available
  3. Fetch 10+ sample pages from different sections
  4. Analyze page structure (HTML, headings, content areas)
  5. Identify content patterns and URL structures
  6. Detect content types (products, articles, etc.)
  7. Identify potential extraction opportunities
- AND use LLM to analyze patterns and make recommendations
- AND stream investigation progress

#### Phase 3: User Confirmation - Investigation Results
- GIVEN site investigation complete
- WHEN showing recommendations
- THEN present to user:
  - Robots.txt findings (allowed/disallowed paths)
  - Sitemap information (if found)
  - Page structure patterns identified
  - Content extraction opportunities
  - Recommended crawl strategy
  - Identified challenges (bot protection, dynamic content, etc.)
- AND wait for user confirmation before proceeding
- AND allow user to modify recommendations

#### Phase 4: Config Generation
- GIVEN user confirmed investigation results
- WHEN generating config
- THEN:
  1. Generate domains from form input
  2. Generate seed_urls:
     - If example_urls provided: use those as seed URLs
     - If path_pattern provided: use domain root or discover initial URLs matching pattern
     - If both provided: use example_urls as seeds, pattern for crawl rules
  3. Create crawl_rules based on:
     - Robots.txt disallowed paths
     - User's path_pattern (if provided)
     - Site structure analysis
  3. Generate extraction_rulesets:
     - Identify content fields based on content_focus
     - Create CSS selectors for each field
     - Use hive-mind extraction patterns
     - Apply best practices (fallback selectors, etc.)
  4. Configure output settings:
     - Start with file output for testing (hive-mind pattern)
     - Include ES settings if output_index provided
  5. Set appropriate crawl depth (start shallow for testing)
- AND use LLM to generate config with reasoning
- AND stream generation progress

#### Phase 5: User Confirmation - Config Preview
- GIVEN draft config generated
- WHEN showing config preview
- THEN present:
  - "Your end document will look like..." preview
  - Sample extracted document structure
  - Field mappings and selectors
  - Config YAML (syntax-highlighted)
  - Explanation of choices made
- AND wait for user confirmation before validation
- AND allow user to edit config before validation

#### Phase 6: Config Validation
- GIVEN user confirmed config (or edited it)
- WHEN validating config
- THEN:
  1. Schema validation (YAML syntax, required fields)
  2. Test extraction rules:
     - Fetch 10+ sample pages
     - Apply extraction selectors
     - Verify fields extract correctly
     - Check for empty/missing fields
  3. Test crawl rules:
     - Verify seed URLs are allowed
     - Test URL pattern matching
     - Check for contradictions
  4. Generate validation report
- AND stream validation progress
- AND report issues found

#### Phase 7: Iteration Loop
- GIVEN validation found issues
- WHEN issues are non-critical
- THEN automatically:
  1. Provide validation report to generation agent
  2. Request config fixes
  3. Re-generate config
  4. Re-validate
- AND continue until pass or max iterations (3)
- AND stream iteration progress

#### Phase 8: Final Output
- GIVEN config passes validation (or max iterations reached)
- WHEN workflow completes
- THEN:
  1. Output final validated config as YAML
  2. Provide download/copy options
  3. Show validation summary
  4. Provide next steps (testing, deployment)
- AND allow user to test config immediately

### Requirement: Hive-Mind Pattern Application
The system SHALL follow hive-mind best practices throughout.

#### Scenario: Fast Iteration Pattern
- GIVEN generating config
- WHEN configuring output
- THEN default to file output for initial testing
- AND recommend console output for urltest commands
- AND only suggest ES output after validation

#### Scenario: Extraction Pattern Library
- GIVEN generating extraction rules
- WHEN creating selectors
- THEN reference hive-mind extraction patterns:
  - Use semantic HTML5 elements first (time[datetime], etc.)
  - Include meta tag fallbacks
  - Add CSS class fallbacks
  - Follow pattern library for common fields (price, author, date, etc.)

#### Scenario: Crawl Rule Best Practices
- GIVEN generating crawl rules
- WHEN creating rules
- THEN:
  - Respect robots.txt disallowed paths
  - Use appropriate filter types (begins, ends, contains, regex)
  - Remember: equals NOT supported in extraction URL filters
  - Start with shallow depth (1-2) for testing

### Requirement: Error Handling
The system SHALL handle errors gracefully at each phase.

#### Scenario: Critical Failure
- GIVEN critical error occurs (bot protection, site unreachable)
- WHEN error detected
- THEN:
  - Stop workflow immediately
  - Return to user with clear explanation
  - Provide recommendations for resolution
  - Allow user to retry or modify input

#### Scenario: Non-Critical Failure
- GIVEN non-critical error (some pages fail, extraction issues)
- WHEN error detected
- THEN:
  - Continue workflow
  - Log issues in validation report
  - Attempt automatic fixes
  - Report issues to user for review

## Workflow State Machine

```
[Initial] → [Validation] → [Investigation] → [User Confirm 1] → [Generation]
                                                                    ↓
[Final Output] ← [User Confirm 2] ← [Validation] ← [Iteration] ←──┘
     ↑                                                              │
     └────────────────── [Critical Error] ─────────────────────────┘
```

## Technical Details

### Input
- Structured form data (see workflow-input spec)
- User confirmations at checkpoints

### Output
- Validated Open Crawler YAML config
- Validation report
- Sample extracted documents

### Dependencies
- Site Investigation Agent
- Config Generation Agent
- Config Validation Agent
- LLM Proxy (for analysis and generation)
- HTTP client (for page fetching)
- Open Crawler API (for validation)

### Performance Targets
- Initial validation: < 5 seconds
- Site investigation: 30-60 seconds per domain
- Config generation: 10-20 seconds
- Config validation: 30-60 seconds (10+ pages)
- Total workflow: 2-5 minutes (depending on domains)

### User Interaction Points
1. Form submission (initial input)
2. Investigation results confirmation
3. Config preview confirmation
4. Final output (with optional immediate testing)
