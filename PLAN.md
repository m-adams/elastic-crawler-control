# Implementation Plan

## Phase 1: Foundation

### 1.1 Fork & Assess elastic-crawler-control
- Fork `ugosan/elastic-crawler-control`
- Assess the UI codebase — what it provides, what we can reuse
- Determine if it's a viable base or if we should start fresh with its patterns
- **Output**: Decision doc on fork vs. fresh build

### 1.2 Ingest hive-mind Knowledge
- Pull all `open-crawler-*` guides from `elastic/hive-mind` repo
- Extract key patterns: config structure, extraction rules, validation rules
- Create a structured knowledge base the agent can reference
- **Output**: Local knowledge files in `knowledge/` directory

### 1.3 Backend Scaffold
- Python FastAPI project with venv
- `.env` based config (Elastic LLM Proxy URL, API keys, ES connection)
- SSE streaming endpoint following A2A Coordinator Pattern from hive-mind
- Health check + basic project structure
- **Output**: Working FastAPI server with `/api/chat` SSE endpoint

## Phase 2: Agentic Core

### 2.1 Site Investigation Agent
- Given a URL, investigate:
  - robots.txt and sitemap
  - Page structure (headings, content areas, navigation)
  - Content patterns across multiple pages
  - URL structure and depth
- Uses LLM Proxy for analysis
- **Output**: Site analysis report used by downstream agents

### 2.2 Config Generation Agent
- Takes site analysis + user's demo goals
- Generates Open Crawler YAML config:
  - `domains` and `seed_urls`
  - `crawl_rules` (allow/deny patterns)
  - `extraction_rules` (CSS selectors, content fields)
  - `output` settings for Elasticsearch
- References hive-mind patterns for best practices
- **Output**: Draft Open Crawler config

### 2.3 Config Validation Agent
- Validates generated config:
  - Schema validation (valid YAML, required fields)
  - Extraction rule testing against live pages (fetch sample pages, apply selectors)
  - Crawl rule logic checks (no contradictions, seed URLs allowed)
- Reports issues back to generation agent for iteration
- **Output**: Validation report + pass/fail

### 2.4 Orchestrator
- Coordinates the above agents via function calling through LLM Proxy
- Manages conversation state and iteration loops
- Streams progress/feedback to UI via SSE
- Handles the full flow: investigate → generate → validate → iterate → output

## Phase 3: UI Integration

### 3.1 Chat Interface
- Extend crawler-control UI with chat component
- SSE streaming from backend (follow hive-mind STREAMING_CHAT_UI_PATTERNS)
- Show agent progress (which step, what it's doing)
- Display intermediate results (site analysis, draft config)

### 3.2 Config Preview & Export
- Render final config with syntax highlighting
- Download as YAML
- Copy to clipboard
- Optional: direct push to Open Crawler instance

## Phase 4: Polish

### 4.1 Multi-domain Support
- Handle multiple domains in a single session
- Merge configs or generate separate ones

### 4.2 Config Templates
- Pre-built templates for common demo scenarios
- User can start from template and customise

### 4.3 History & Sharing
- Save generated configs
- Share configs between team members

---

## Key Technical Decisions Needed

1. **Fork vs. fresh**: Need to assess `elastic-crawler-control` first
2. **LLM Proxy details**: Need endpoint URL, auth method, available models
3. **Open Crawler access**: Need a running instance for live validation, or mock the API
4. **Deployment**: Local-first or hosted service?

## Next Steps (for the next agent)

1. Fork `ugosan/elastic-crawler-control` via `gh repo fork`
2. Pull and read all `open-crawler-*` files from hive-mind
3. Scaffold the FastAPI backend with venv
4. Get LLM Proxy connection details and test connectivity
