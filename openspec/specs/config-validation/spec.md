# Config Validation Specification

## Purpose
Validate generated Open Crawler configurations through schema checks, live page testing, and crawl rule verification.

## Requirements

### Requirement: Schema Validation
The system SHALL validate config structure and syntax.

#### Scenario: YAML Syntax Check
- GIVEN a config has been generated
- WHEN validating schema
- THEN parse YAML and verify syntax
- AND check all required fields are present
- AND validate field types and formats
- AND report any syntax errors

#### Scenario: Open Crawler Schema Validation
- GIVEN YAML syntax is valid
- WHEN validating schema
- THEN validate against Open Crawler config schema
- AND check:
  - Required sections (domains, seed_urls, etc.)
  - Valid crawl rule patterns
  - Valid extraction rule structure
  - Valid output configuration
- AND report schema violations

### Requirement: Extraction Rule Testing
The system SHALL test extraction rules against live pages.

#### Scenario: Sample Page Testing
- GIVEN config contains extraction rules
- WHEN testing extraction rules
- THEN fetch at least 10 sample pages from target domain
- AND apply extraction selectors to each page
- AND verify:
  - Selectors match expected elements
  - Content is extracted correctly
  - Field mappings work as intended
- AND collect success/failure statistics

#### Scenario: Extraction Result Validation
- GIVEN extraction rules have been tested
- WHEN validating results
- THEN check:
  - Required fields are present
  - Content quality (not empty, meaningful)
  - Field consistency across pages
- AND identify pages where extraction fails
- AND report issues to generation agent for iteration

### Requirement: Crawl Rule Testing
The system SHALL validate crawl rule logic.

#### Scenario: Rule Logic Validation
- GIVEN config contains crawl rules
- WHEN validating crawl rules
- THEN check:
  - No contradictory allow/deny patterns
  - Seed URLs are allowed by rules
  - Domain patterns are correct
  - Rule precedence is logical
- AND report any logical errors

#### Scenario: Rule Pattern Testing
- GIVEN crawl rules are defined
- WHEN testing patterns
- THEN test rule patterns against sample URLs
- AND verify:
  - Allow rules match intended URLs
  - Deny rules exclude intended URLs
  - Pattern matching works correctly
- AND report mismatches

### Requirement: Iterative Improvement
The system SHALL iterate on config when validation fails.

#### Scenario: Automatic Iteration
- GIVEN validation has found issues
- WHEN issues are non-critical
- THEN automatically iterate:
  - Provide validation report to generation agent
  - Request config fixes
  - Re-validate fixed config
- AND continue until config passes or max iterations reached

#### Scenario: Critical Failure Handling
- GIVEN validation finds critical issues (e.g., no pages extractable)
- WHEN critical failure occurs
- THEN return to user with:
  - Clear explanation of issue
  - Validation report
  - Recommendations for resolution
- AND do not proceed automatically

### Requirement: Validation Report
The system SHALL produce detailed validation reports.

#### Scenario: Report Generation
- GIVEN validation is complete
- WHEN generating report
- THEN create report containing:
  - Schema validation results
  - Extraction rule test results (per page)
  - Crawl rule validation results
  - Overall pass/fail status
  - Recommendations for fixes
- AND make report available to user and generation agent

## Technical Details

### Input
- Draft Open Crawler config (YAML)
- Target domain(s)
- Sample pages (from site investigation or fresh fetch)

### Output
- Validation report
- Pass/fail status
- Issue list with recommendations

### Dependencies
- Open Crawler API (for config validation)
- HTTP client (for page fetching)
- HTML parser (for selector testing)
- YAML parser

### Testing Scope
- **Extraction**: Test against at least 10 pages
- **Crawl Rules**: Test against sample URL set
- **Schema**: Full config validation

### Error Handling
- Network failures: Retry, then report as validation failure
- Selector failures: Report specific pages and selectors
- Config errors: Return detailed error messages
