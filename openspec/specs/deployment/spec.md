# Deployment Specification

## Purpose
Define deployment requirements for local development and GCP Cloud Run production environments.

## Requirements

### Requirement: Docker Container
The system SHALL be containerized for deployment.

#### Scenario: Dockerfile Creation
- GIVEN application needs deployment
- WHEN creating Dockerfile
- THEN include:
  - Python base image
  - Application code
  - Dependencies installation
  - Environment variable configuration
  - Health check endpoint
- AND optimize for size and build speed

#### Scenario: Multi-stage Build
- GIVEN Dockerfile is created
- WHEN building image
- THEN use multi-stage build:
  - Build stage: Install dependencies
  - Runtime stage: Copy only necessary files
- AND minimize final image size

### Requirement: Local Development
The system SHALL support local development workflow.

#### Scenario: Local Setup
- GIVEN developer wants to run locally
- WHEN setting up environment
- THEN provide:
  - Python venv in project root
  - `.env` file for configuration
  - Docker Compose for dependencies (Open Crawler, ES if needed)
  - Development server with hot reload
- AND document setup process

#### Scenario: Development Dependencies
- GIVEN local development
- WHEN running locally
- THEN support:
  - Hot reload for code changes
  - Debugging capabilities
  - Local LLM Proxy connection
  - Local Open Crawler instance
- AND make development efficient

### Requirement: GCP Cloud Run Deployment
The system SHALL deploy to GCP Cloud Run.

#### Scenario: Cloud Run Configuration
- GIVEN application is containerized
- WHEN deploying to Cloud Run
- THEN configure:
  - Container image registry (GCR or Artifact Registry)
  - Cloud Run service settings
  - Environment variables (from secrets or config)
  - Health check endpoint
  - IAP integration (handled externally)
- AND ensure proper scaling configuration

#### Scenario: Environment Variables
- GIVEN Cloud Run deployment
- WHEN configuring environment
- THEN manage via:
  - Cloud Run environment variables (non-sensitive)
  - Secret Manager (for API keys, etc.)
  - `.env` file for local development
- AND document all required variables

### Requirement: Health Checks
The system SHALL provide health check endpoints.

#### Scenario: Health Check Endpoint
- GIVEN service is deployed
- WHEN health check is called
- THEN return:
  - Service status
  - Dependency status (LLM Proxy, Open Crawler, ES)
  - Version information
- AND return appropriate HTTP status codes

#### Scenario: Readiness Probe
- GIVEN service is starting
- WHEN readiness is checked
- THEN verify:
  - Application is initialized
  - Dependencies are reachable
  - Service is ready to accept requests
- AND return 200 when ready, 503 when not

### Requirement: Logging
The system SHALL provide structured logging.

#### Scenario: Application Logs
- GIVEN application is running
- WHEN logging events
- THEN log:
  - Agent workflow steps
  - API requests/responses
  - Errors with stack traces
  - Performance metrics
- AND use structured logging (JSON format)

#### Scenario: Cloud Logging Integration
- GIVEN Cloud Run deployment
- WHEN logging
- THEN integrate with Cloud Logging:
  - Use appropriate log levels
  - Include request IDs for tracing
  - Format logs for Cloud Logging
- AND make logs searchable and filterable

## Technical Details

### Dockerfile Structure
```dockerfile
# Multi-stage build
FROM python:3.11-slim as builder
# Install dependencies
...

FROM python:3.11-slim
# Copy application
# Set up runtime
# Health check
...
```

### Environment Variables
- `LLM_PROXY_URL`: LLM Proxy endpoint
- `LLM_PROXY_API_KEY`: API key (from Secret Manager in Cloud Run)
- `OPEN_CRAWLER_URL`: Open Crawler instance URL
- `ELASTICSEARCH_HOST`: ES connection (if needed)
- `ENVIRONMENT`: `development` or `production`

### Health Check
- Endpoint: `GET /health`
- Response: `{ "status": "healthy", "dependencies": {...}, "version": "..." }`
- Status codes: 200 (healthy), 503 (unhealthy)

### Cloud Run Settings
- CPU: 1-2 vCPU
- Memory: 2-4 GB
- Min instances: 0 (scale to zero)
- Max instances: 10
- Timeout: 300 seconds (for long-running agent workflows)
- Concurrency: 10 requests per instance

### Dependencies
- Docker
- Google Cloud SDK (for Cloud Run deployment)
- Docker Compose (for local development)

### Error Handling
- Container startup failures: Log and exit with error code
- Health check failures: Return 503, Cloud Run will restart
- Dependency failures: Log and return in health check status
