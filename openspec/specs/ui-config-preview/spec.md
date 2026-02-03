# UI Config Preview & Export Specification

## Purpose
Display final Open Crawler configurations with syntax highlighting and provide export functionality.

## Requirements

### Requirement: Config Display
The system SHALL display configs with syntax highlighting.

#### Scenario: Config Viewer
- GIVEN a config has been generated
- WHEN displaying config
- THEN show:
  - Syntax-highlighted YAML
  - Line numbers
  - Collapsible sections
  - Search/filter functionality
- AND make config easy to read and navigate

#### Scenario: Config Sections
- GIVEN config is displayed
- WHEN showing sections
- THEN organize by:
  - Domains and seed URLs
  - Crawl rules
  - Extraction rules
  - Output settings
- AND allow expanding/collapsing sections

### Requirement: Export Functionality
The system SHALL provide multiple export options.

#### Scenario: Download as YAML
- GIVEN config is displayed
- WHEN user clicks download
- THEN download config as `.yaml` file
- AND use appropriate filename (e.g., `crawler-config-{domain}-{timestamp}.yaml`)

#### Scenario: Copy to Clipboard
- GIVEN config is displayed
- WHEN user clicks copy
- THEN copy config YAML to clipboard
- AND show confirmation message

#### Scenario: Direct Push to Open Crawler
- GIVEN config is displayed
- WHEN user wants to deploy
- THEN provide option to push config directly to Open Crawler instance
- AND show deployment status
- AND handle errors gracefully

### Requirement: Config Editing
The system SHALL allow inline config editing.

#### Scenario: Editable Config
- GIVEN config is displayed
- WHEN user wants to edit
- THEN provide:
  - Editable textarea with syntax highlighting
  - Inline validation (YAML syntax)
  - Save changes button
- AND allow editing before export

#### Scenario: Edit and Test
- GIVEN user has edited config
- WHEN user wants to test edited config
- THEN provide "Test Config" button
- AND execute test workflow with edited config
- AND show results

### Requirement: Config History
The system SHALL show config generation history.

#### Scenario: History Display
- GIVEN multiple configs have been generated
- WHEN showing history
- THEN display:
  - List of previous configs
  - Timestamp and domain for each
  - Quick preview
  - Actions (view, download, delete)
- AND allow user to browse history

## Technical Details

### Components
- Config viewer component (syntax-highlighted)
- Export buttons component
- Config editor component (for inline editing)
- History list component

### Syntax Highlighting
- Use YAML syntax highlighter (e.g., Prism, highlight.js)
- Support YAML-specific highlighting
- Maintain readability

### File Handling
- Generate appropriate filenames
- Handle download in browser
- Support clipboard API

### Open Crawler Integration
- API endpoint for config deployment
- Status polling for deployment
- Error handling and display

### Dependencies
- Syntax highlighting library
- File download utilities
- Clipboard API
- Open Crawler API client

### Error Handling
- Invalid YAML: Show inline errors
- Export failures: Show error message
- Deployment failures: Show detailed error and retry option
