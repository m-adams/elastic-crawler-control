# Config Generation Specification

## Purpose
Generate Open Crawler YAML configuration files based on site investigation results and user demo goals.

## Requirements

### Requirement: Config Structure Generation
The system SHALL generate valid Open Crawler YAML configs with all required sections.

#### Scenario: Basic Config Generation
- GIVEN site analysis report and user demo scenario
- WHEN generating config
- THEN create YAML config with:
  - `domains`: List of target domains
  - `seed_urls`: Initial URLs to crawl
  - `crawl_rules`: Allow/deny patterns
  - `extraction_rules`: CSS selectors and content fields
  - `output`: Elasticsearch output settings
- AND ensure all required fields are present

#### Scenario: Hive-mind Pattern Reference
- GIVEN config generation is in progress
- WHEN creating extraction rules and crawl rules
- THEN reference patterns from hive-mind knowledge base
- AND apply best practices for:
  - CSS selector specificity
  - Content field naming
  - Crawl rule patterns
  - Error handling

### Requirement: LLM-Powered Generation
The system SHALL use LLM to generate configs with captured reasoning.

#### Scenario: Config Generation with Reasoning
- GIVEN site analysis report is available
- WHEN generating config
- THEN provide site analysis to LLM
- AND request config generation with:
  - Explanation of crawl rule choices
  - Rationale for extraction selectors
  - Content field decisions
- AND capture LLM reasoning for user review

#### Scenario: Intermediate Confirmation
- GIVEN draft config has been generated
- WHEN config is ready
- THEN show user intermediate result:
  - "Your end document will look like..." preview
  - Sample extracted fields
  - Explanation of choices
- AND wait for user confirmation before validation

### Requirement: Multi-Domain Support
The system SHALL handle multiple domains in a single config.

#### Scenario: Multiple Domains
- GIVEN multiple domains are provided
- WHEN generating config
- THEN create config that handles all domains
- AND ensure crawl rules account for domain differences
- AND merge or separate extraction rules as appropriate

### Requirement: Demo Scenario Integration
The system SHALL incorporate user's demo goals into config generation.

#### Scenario: Demo Goal Application
- GIVEN user provides demo scenario (e.g., "index product pages for search demo")
- WHEN generating config
- THEN prioritize content extraction relevant to demo goal
- AND adjust crawl rules to focus on relevant sections
- AND ensure output format supports demo use case

## Technical Details

### Input
- Site analysis report
- User demo scenario
- User confirmation of investigation recommendations

### Output
- Draft Open Crawler YAML config
- LLM reasoning and explanations
- Sample document preview

### Dependencies
- Site investigation agent
- Hive-mind knowledge base
- LLM Proxy
- YAML generation library

### Validation
- Schema validation happens in config validation agent
- This agent focuses on generation, not validation

### Error Handling
- Invalid site analysis: Return to site investigation
- LLM generation failure: Retry with clearer prompts
- YAML syntax errors: Fix automatically or return to user
