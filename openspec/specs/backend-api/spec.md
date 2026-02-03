# Backend API Specification

## Purpose
Define FastAPI endpoints for the Open Crawler Config Generator backend.

## Requirements

### Requirement: Chat Endpoint
The system SHALL provide an SSE streaming chat endpoint for agent workflows.

#### Scenario: Chat Stream Endpoint
- GIVEN user sends chat message
- WHEN POST `/api/chat` is called
- THEN:
  - Accept message body with domain(s) and demo scenario
  - Initialize orchestration workflow
  - Stream agent progress via SSE
  - Return final config when complete
- AND follow A2A Coordinator Pattern from hive-mind

#### Scenario: SSE Message Format
- GIVEN SSE stream is active
- WHEN streaming updates
- THEN send messages in format:
  - `event`: Message type (progress, result, error, confirmation)
  - `data`: JSON payload with content
- AND include timestamps and step information

### Requirement: Config Test Endpoint
The system SHALL provide endpoint for standalone config testing.

#### Scenario: Test Config Endpoint
- GIVEN user provides config for testing
- WHEN POST `/api/config/test` is called
- THEN:
  - Accept config YAML in request body
  - Validate config format
  - Execute test against Open Crawler
  - Return test results (extracted documents, statistics)
- AND return results quickly (< 30 seconds for initial)

#### Scenario: Test Results Format
- GIVEN test has executed
- WHEN returning results
- THEN include:
  - Extracted documents (sample)
  - Success rate per extraction rule
  - Fields extracted per page
  - Crawl rule match results
  - Errors and warnings
- AND format as JSON

### Requirement: Health Check Endpoint
The system SHALL provide health check endpoint.

#### Scenario: Health Check
- GIVEN service is running
- WHEN GET `/health` is called
- THEN return status:
  - Service status (healthy/unhealthy)
  - Dependencies status (LLM Proxy, Open Crawler, ES)
  - Version information
- AND return 200 if healthy, 503 if unhealthy

### Requirement: Config Export Endpoint
The system SHALL provide endpoint for config export.

#### Scenario: Config Download
- GIVEN config has been generated
- WHEN GET `/api/config/{config_id}/download` is called
- THEN return config as YAML file
- AND set appropriate headers for download

## Technical Details

### Endpoints

#### POST `/api/chat`
- **Purpose**: Main agent workflow endpoint
- **Input**: `{ "domain": string, "demo_scenario": string, "seed_urls": string[] (optional) }`
- **Output**: SSE stream
- **Pattern**: Follows A2A Coordinator Pattern

#### POST `/api/config/test`
- **Purpose**: Test config against live pages
- **Input**: `{ "config": string (YAML), "test_options": object (optional) }`
- **Output**: `{ "results": object, "statistics": object, "errors": array }`
- **Response Time**: < 30 seconds initial

#### GET `/health`
- **Purpose**: Health check
- **Output**: `{ "status": string, "dependencies": object, "version": string }`

#### GET `/api/config/{config_id}/download`
- **Purpose**: Download config as YAML
- **Output**: YAML file download

### Dependencies
- FastAPI framework
- SSE streaming support
- Open Crawler API client
- LLM Proxy client
- Elasticsearch client (if needed)

### Error Handling
- Invalid input: Return 400 with error details
- Service errors: Return 500 with error message
- Dependency failures: Return 503 with dependency status
- SSE errors: Close stream with error message

### Authentication
- Handled by IAP (Identity-Aware Proxy)
- Backend assumes authenticated requests
- No auth logic in backend code
