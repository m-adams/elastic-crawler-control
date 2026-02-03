# Open Crawler Config Generator - Project Context

## Purpose
An agentic tool that automates the creation, testing, and validation of Elastic Open Crawler configurations for pre-sales demos. The system uses LLM-powered agents to investigate websites, generate crawl/extraction rules, validate configurations, and provide a user-friendly interface for testing and iteration.

## Tech Stack

### Backend
- **Framework**: Python FastAPI with **Agno AI Framework**
- **Agent Orchestration**: Agno Workflow with Step, Loop, and Parallel primitives
- **Agents**: Site Investigation, Config Generation, Config Validation (Agno Agents with tools)
- **Environment**: Python venv (in elastic-crawler-control/crawler-service/)
- **LLM**: Claude Sonnet 4 via Elastic LLM Proxy
  - Base URL: `https://litellm-proxy-service-1059491012611.us-central1.run.app/v1`
  - Model: `claude-sonnet-4` (bedrock alias)
- **Streaming**: Agno's built-in SSE streaming via `workflow.arun(stream=True)`
- **Knowledge Base**: Patterns from `elastic/hive-mind` repo + `knowledge/agno/` guide

### Frontend
- **Base**: Forked from `ugosan/elastic-crawler-control`
- **Integration**: Extends existing FastAPI backend from forked project
- **Patterns**: Follows A2A Coordinator Pattern and Streaming Chat UI Patterns from hive-mind

### Infrastructure
- **Development**: Local with Docker
- **Deployment**: Docker container for GCP Cloud Run (or Kubernetes)
- **Auth**: Identity-Aware Proxy (IAP) - handled externally
- **Open Crawler**: Running locally via Docker (no mocking)

## Key Constraints

1. **No Mocking**: All integrations must use real services (Open Crawler, Elasticsearch)
2. **Modular Code**: Small, well-documented files for LLM agent editing
3. **Environment Config**: All secrets/config in `.env` file (use `python-dotenv` with `override=True`)
4. **Elasticsearch**: Use official `elasticsearch-py` client, connection via env vars
5. **Templates**: Save mappings/queries as separate template files for easy editing

## Project Structure

```
open-crawler-config-generator/
├── openspec/                      # OpenSpec specifications
├── elastic-crawler-control/       # Forked repo (backend + frontend)
│   └── crawler-service/
│       └── app/
│           ├── server.py          # FastAPI entry point
│           ├── agents/            # Agno agents + workflow
│           │   ├── site_investigation.py      # Site analysis agent
│           │   ├── site_investigation_tools.py
│           │   ├── config_generation.py       # Config creation agent
│           │   ├── config_generation_tools.py
│           │   ├── config_validation.py       # Validation agent
│           │   ├── config_validation_tools.py
│           │   ├── orchestration_workflow.py  # Agno Workflow
│           │   └── workflow_state.py          # Pydantic state models
│           ├── routes/            # Individual route files
│           │   ├── workflow.py    # SSE streaming endpoint
│           │   └── health.py
│           ├── utils/             # Utility modules
│           └── tests/             # Test suite
├── knowledge/                     # Open Crawler patterns + Agno guide
│   └── agno/                      # Agno framework documentation
├── hive-mind/                     # Submodule (private elastic/hive-mind repo)
├── .env.example                   # Example env file
└── README.md
```

## User Workflows

1. **Config Generation**: User provides domain(s) + demo scenario → Agent investigates → Generates config → Validates → Iterates → Outputs final config
2. **Config Testing**: User provides config → Test against Open Crawler → Show results in UI
3. **Edit & Test**: Generate config → Test → Edit → Test again (iterative)

## Success Criteria

- **Ease of Use**: Intuitive interface for pre-sales engineers
- **Thorough Testing**: Configs are validated against real pages (10+ pages for extraction)
- **User Feedback**: Clear progress indicators and intermediate confirmations
- **Quality**: Generated configs work correctly with Open Crawler
