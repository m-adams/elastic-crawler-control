# Config Testing Specification

## Purpose
Provide a standalone workflow for testing Open Crawler configurations against live pages and displaying results in the UI.

## Requirements

### Requirement: Config Input
The system SHALL accept configs from multiple sources.

#### Scenario: User-Provided Config
- GIVEN user wants to test a config
- WHEN user provides config
- THEN accept config via:
  - File upload (YAML)
  - Paste/textarea input
  - Previously generated config
- AND validate config format before testing

#### Scenario: Generated Config Testing
- GIVEN a config has been generated
- WHEN user requests test
- THEN use generated config for testing
- AND allow user to edit config before testing

### Requirement: Quick Test Execution
The system SHALL execute tests quickly and show results in UI.

#### Scenario: Test Execution
- GIVEN a valid config is provided
- WHEN user initiates test
- THEN:
  - Submit config to Open Crawler test endpoint
  - Fetch sample pages (or use provided URLs)
  - Apply extraction rules
  - Execute crawl rules
- AND return results quickly (< 30 seconds for initial results)

#### Scenario: Results Display
- GIVEN test has executed
- WHEN results are available
- THEN display in UI:
  - Extracted documents (sample)
  - Extraction success rate
  - Fields extracted per page
  - Crawl rule matches
  - Any errors or warnings
- AND format results for easy review

### Requirement: Edit and Re-test Workflow
The system SHALL support iterative editing and testing.

#### Scenario: Config Editing
- GIVEN test results are displayed
- WHEN user wants to edit config
- THEN provide editable config interface:
  - Syntax-highlighted YAML editor
  - Inline validation
  - Field suggestions
- AND allow user to modify config

#### Scenario: Re-test After Edit
- GIVEN user has edited config
- WHEN user requests re-test
- THEN execute test with modified config
- AND show updated results
- AND highlight changes from previous test

### Requirement: Test Scope Configuration
The system SHALL allow users to configure test scope.

#### Scenario: Page Limit
- GIVEN user wants to test config
- WHEN configuring test
- THEN allow user to specify:
  - Number of pages to test (default: 10)
  - Specific URLs to test
  - Test depth limit
- AND respect these limits during testing

#### Scenario: Field Focus
- GIVEN user wants to focus on specific fields
- WHEN configuring test
- THEN allow user to:
  - Select specific extraction rules to test
  - Focus on particular content types
  - Ignore certain fields
- AND report only on selected fields

### Requirement: Comparison View
The system SHALL allow comparing test results.

#### Scenario: Before/After Comparison
- GIVEN user has tested config multiple times
- WHEN comparing results
- THEN show:
  - Previous vs current extraction results
  - Success rate changes
  - Field coverage changes
- AND highlight improvements or regressions

## Technical Details

### Input
- Open Crawler config (YAML)
- Optional: Test configuration (page limit, URLs, etc.)
- Optional: Previous test results (for comparison)

### Output
- Test results (extracted documents, statistics)
- Success/failure indicators
- Comparison data (if applicable)

### Dependencies
- Open Crawler API (test endpoint)
- UI components (results display, config editor)
- Backend API endpoint for test execution

### Performance
- Initial results: < 30 seconds
- Full test: < 2 minutes (for reasonable page counts)
- Results display: Immediate after test completion

### Error Handling
- Invalid config: Show validation errors before testing
- Test failures: Show detailed error messages
- Network issues: Retry with clear user feedback
