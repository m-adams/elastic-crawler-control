# UI Chat Interface Specification

## Purpose
Extend the forked elastic-crawler-control UI with a chat interface for agent interaction and progress display.

## Requirements

### Requirement: Chat Component
The system SHALL provide a chat interface for user interaction.

#### Scenario: Chat Input
- GIVEN user wants to generate config
- WHEN using chat interface
- THEN provide:
  - Text input for domain(s) and demo scenario
  - Send button
  - Clear conversation button
- AND accept natural language input

#### Scenario: Message Display
- GIVEN messages are sent/received
- WHEN displaying messages
- THEN show:
  - User messages (right-aligned)
  - Agent messages (left-aligned)
  - Timestamps
  - Message formatting (markdown support)
- AND maintain conversation history

### Requirement: SSE Streaming Display
The system SHALL display real-time agent progress via SSE.

#### Scenario: Progress Updates
- GIVEN SSE stream is active
- WHEN receiving progress events
- THEN display:
  - Current step indicator ("Investigating site structure...")
  - Progress bar or spinner
  - Agent reasoning and decisions
  - Intermediate results
- AND update UI in real-time

#### Scenario: Event Types
- GIVEN different event types are received
- WHEN displaying events
- THEN format appropriately:
  - `progress`: Show step and activity
  - `result`: Display formatted results (site analysis, config preview)
  - `error`: Show error message with styling
  - `confirmation`: Show confirmation prompt with actions
- AND use appropriate UI components

### Requirement: Intermediate Results Display
The system SHALL display intermediate agent outputs.

#### Scenario: Site Analysis Display
- GIVEN site investigation is complete
- WHEN showing recommendations
- THEN display:
  - Robots.txt findings
  - Page structure patterns
  - LLM recommendations (crawl strategy, extraction suggestions)
  - Confirmation buttons (Approve/Modify)
- AND format for easy review

#### Scenario: Config Preview Display
- GIVEN draft config is generated
- WHEN showing "end document will look like"
- THEN display:
  - Sample extracted document structure
  - Field mappings
  - Preview of extracted content
  - Config YAML (syntax-highlighted)
  - Confirmation buttons
- AND allow user to review before proceeding

### Requirement: Confirmation Prompts
The system SHALL handle user confirmations at decision points.

#### Scenario: Investigation Confirmation
- GIVEN site investigation recommendations are shown
- WHEN user needs to confirm
- THEN provide:
  - Approve button (proceed with recommendations)
  - Modify button (edit recommendations)
  - Cancel button (abort workflow)
- AND wait for user action before continuing

#### Scenario: Config Confirmation
- GIVEN draft config is shown
- WHEN user needs to confirm
- THEN provide:
  - Approve button (proceed to validation)
  - Edit button (modify config before validation)
  - Cancel button (abort workflow)
- AND wait for user action

### Requirement: Error Display
The system SHALL display errors clearly.

#### Scenario: Error Messages
- GIVEN an error occurs
- WHEN displaying error
- THEN show:
  - Error type and message
  - Step where error occurred
  - Recovery suggestions
  - Retry button (if applicable)
- AND use error styling (red, warning icons)

## Technical Details

### Components
- Chat container component
- Message list component
- Message bubble component
- Progress indicator component
- Results display component (site analysis, config preview)
- Confirmation dialog component

### SSE Integration
- Connect to `/api/chat` endpoint
- Handle SSE events
- Update UI reactively
- Handle connection errors and reconnection

### Styling
- Follow existing elastic-crawler-control styles
- Use consistent spacing and typography
- Responsive design for different screen sizes
- Dark/light mode support (if existing UI has it)

### Dependencies
- React (or framework used by elastic-crawler-control)
- SSE client library
- Markdown renderer (for formatted messages)
- Syntax highlighter (for YAML/config display)

### Error Handling
- SSE connection failures: Show error and retry button
- Message parsing errors: Show raw message with error indicator
- UI errors: Show error boundary with recovery option
