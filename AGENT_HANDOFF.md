# Agent Handoff: Open Crawler Config Generator

**Date**: 2026-02-03  
**Previous Session**: Workflow optimization - data flow improvements, LLM extraction rules, extraction preview  
**Project**: AI-powered tool to generate Open Crawler configurations for pre-sales demos

---

## Recent Improvements (2026-02-03 Session)

### Data Flow Optimizations
| Change | Before | After | Benefit |
|--------|--------|-------|---------|
| robots.txt | Fetched twice (preflight + investigation) | Reused from preflight | Faster, consistent |
| HTML samples | Fetched twice (investigation + validation) | Reused from investigation | Faster, consistent |
| user_context | Only used in post-hoc LLM review | Guides investigation + config gen | Better extraction rules |

### LLM-Generated Extraction Rules (NEW)
Instead of hardcoded selectors, the LLM now:
1. Receives actual HTML samples from the site
2. Receives the extraction rules guide with naming conventions
3. Generates tailored CSS selectors for that specific site
4. Knows which fields the crawler already extracts (title, body, headings)

### Extraction Preview (NEW)
The completion event now includes actual extracted values:
```json
{
  "extraction_preview": {
    "article_title_text": {"value": "Example Domain", "matched": true, "selector": "h1"},
    "author_name_text": {"value": null, "matched": false, "selector": ".author"}
  },
  "extraction_test_summary": {"total_fields": 6, "fields_matched": 5, "fields_failed": 1}
}
```

### Frontend Updates
- New "Extraction Preview" tab in Config Preview showing actual extracted values
- Badge shows matched/total fields (e.g., "5/6")
- Visual indicators for matched (✓) vs failed (✗) fields

---

## Workflow Documentation

**See**: [`docs/CONFIG_GENERATION_WORKFLOW.md`](docs/CONFIG_GENERATION_WORKFLOW.md) for the complete logical flow from target site to validated config.

**Quick Summary**:
```
[Preflight] → [Deep Check] → [Site Investigation] → [Config Generation] → [Validation Loop] → [Complete]
   0.3s          0.1s            30-60s                 10-20s               30-60s
```

Total time: ~60-90 seconds per config

---

## Quick Start

```bash
# This is a fork of ugosan/elastic-crawler-control
# Working on: feature/config-generator branch

# Check what's ready to work on
bd ready

# Project structure
ls -la                           # Root of fork
ls crawler-service/app/          # Backend (FastAPI + Agno)
ls frontend/src/components/      # Frontend (React)

# Run backend
cd crawler-service && source ../venv/bin/activate
uvicorn app.server:app --reload

# Run frontend
cd frontend && npm run dev
```

---

## Current Implementation Status

### ✅ COMPLETED (Backend)

| Component | File | Description |
|-----------|------|-------------|
| **Domain Preflight API** | `routes/domain.py` | DNS, HTTP, robots.txt checks (~2-3s, no LLM) |
| **Domain Deep-Check API** | `routes/domain.py` | Bot protection, JS detection, Firecrawl rec (~5-10s) |
| Site Investigation Agent | `agents/site_investigation.py` | Agno-powered, analyzes robots.txt, sitemaps, 10+ pages |
| Config Generation Agent | `agents/config_generation.py` | Generates YAML with crawl rules + extraction rules |
| Config Validation Agent | `agents/config_validation.py` | Schema validation + structure checks |
| Orchestration Workflow | `agents/orchestration_workflow.py` | Agno Workflow with Loop for retries |
| SSE Streaming | `routes/workflow.py` | `/api/generate` with pre-checks before LLM |
| Open Crawler Client | `utils/crawler_client.py` | `validate`, `urltest`, `crawl` commands |
| Extraction Testing API | `routes/extraction.py` | `/api/extraction/test`, `/batch`, `/evaluate` |

### ✅ COMPLETED (Frontend)

| Component | File | Description |
|-----------|------|-------------|
| Config Generator | `components/ConfigGenerator.jsx` | **Debounced URL preflight**, SSE streaming, Firecrawl banner |
| Config Preview | `components/ConfigPreview.jsx` | YAML viewer, copy/download, field table |
| Extraction Tester | `components/ExtractionTester.jsx` | Modal for testing extraction on real URLs |
| App with Tabs | `App.jsx` | 3 tabs: Generate \| Preview \| Run |

### ✅ VALIDATED (2026-02-03)

End-to-end testing completed with 11 sites:
- BBC News, Hacker News, Python Docs, Elastic Blog, Go Blog
- example.com (blog, general, ecommerce content types)
- httpbin.org

All configs generated successfully with valid structure, proper field naming, and working crawl rules.

---

## Validation Steps (E2E Testing)

### 1. Start the Services

```bash
# Terminal 1: Start backend
cd elastic-crawler-control/crawler-service
source ../../venv/bin/activate  # If venv exists
pip install -r requirements.txt
python -m uvicorn app.server:app --reload --port 8000

# Terminal 2: Start frontend  
cd elastic-crawler-control/frontend
npm install
npm run dev
```

### 2. Test Backend API Directly

```bash
# Health check
curl http://localhost:8000/api/health

# Check extraction testing is available
curl http://localhost:8000/api/extraction/status

# Test SSE streaming (will stream events)
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"domain": "https://www.bbc.co.uk/news", "content_type": "blog"}'
```

### 3. Test Frontend UI

1. Open http://localhost:5173 (or whatever Vite reports)
2. **Generate Config Tab**:
   - Enter: `https://www.bbc.co.uk/news`
   - Select: "Blog / News"
   - Click "Generate Config"
   - Verify: Phase progress shows (Investigation → Generation → Validation → Complete)
   - Verify: Event log updates in real-time
   - Verify: Sample document appears

3. **Config Preview Tab**:
   - Verify: YAML displays with syntax highlighting
   - Verify: "Copy" button works
   - Verify: "Download YAML" downloads a file
   - Verify: Extraction Fields tab shows field names and selectors

4. **Test Extraction**:
   - Click "Test Extraction" button
   - Enter a BBC News article URL: `https://www.bbc.co.uk/news/uk-12345678`
   - Click "Run Extraction Test"
   - Verify: Field evaluation shows pass/warning/fail per field
   - Verify: Sample values appear

5. **Run Crawler Tab**:
   - Click "Use Generated Config"
   - Verify: JSON config loads in textarea
   - (Optional) Click "Run" if crawler is available

### 4. Test Error Handling

```bash
# Test with invalid URL
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"domain": "not-a-valid-url"}'

# Test extraction with unavailable crawler
# (should return 503 if crawler binary not found)
curl -X POST http://localhost:8000/api/extraction/test \
  -H "Content-Type: application/json" \
  -d '{"config": {}, "url": "https://example.com"}'
```

---

## Domain Pre-Check Feature (NEW)

The system now runs lightweight domain checks BEFORE engaging the LLM workflow:

### Preflight Check (~2-3s, debounced as user types)
- URL format validation
- DNS resolution
- HTTP connectivity
- robots.txt analysis

### Deep Check (~5-10s, before LLM workflow)
- Bot protection detection (Cloudflare, Akamai, Imperva, DataDome, PerimeterX)
- JavaScript rendering requirements
- Open Crawler urltest (if available)

### Firecrawl Recommendation
When bot protection or JS rendering is detected, the system recommends Firecrawl with:
- Link to Firecrawl (https://firecrawl.dev)
- Pricing warning ("Firecrawl is a paid service")
- Reason why it's recommended

### API Endpoints
- `POST /api/domain/preflight` - Fast checks (no LLM required)
- `POST /api/domain/deep-check` - Thorough checks
- `GET /api/domain/firecrawl-info` - Firecrawl details

---

## Known Issues / Potential Problems

1. **LLM Proxy API Key**: Backend needs `LLM_PROXY_API_KEY` in `.env` for Agno agents to work
2. **Crawler Binary**: Extraction testing requires Open Crawler at `/crawler/bin/crawler`
3. **CORS**: Frontend may need VITE_API_URL if running on different ports
4. **Investigation Timeout**: Sites with slow sitemaps may hit 120s timeout (safety feature)
5. **Rate Limiting**: Testing same site repeatedly may trigger rate limits

## Recent Fixes (2026-02-03)

### Earlier Fixes
| Issue | Fix | File |
|-------|-----|------|
| SSE events buffered | Added asyncio.Queue + keepalive messages | `routes/workflow.py` |
| Sitemap parser hanging | Added max_sitemaps=10, max_urls=500 limits | `utils/sitemap_parser.py` |
| Thread hangs forever | Added 120s timeout to `_run_async_in_thread` | `orchestration_workflow.py` |
| Seed URL blocked by `/` | Filter bot-specific robots.txt rules, only use `User-agent: *` | `site_investigation.py` |
| Config missing in SSE | Fixed extraction from Agno workflow events | `routes/workflow.py` |

### Workflow Optimization Session (This Session)
| Change | File | Description |
|--------|------|-------------|
| Robots.txt reuse | `orchestration_workflow.py`, `site_investigation.py` | Pass preflight data to investigation |
| user_context propagation | `workflow_state.py`, `orchestration_workflow.py` | Add to session state, pass to agents |
| LLM extraction rules | `config_generation.py` | New `_generate_extraction_rules_with_llm()` method |
| HTML sample storage | `site_investigation.py` | Store `html_samples` in report |
| HTML sample reuse | `orchestration_workflow.py` | Pass to validation to avoid re-fetch |
| Extraction preview | `routes/workflow.py` | Build and return in completion event |
| Default fields guide | `config_generation.py` | LLM knows not to extract title/body/headings |
| Suffix clarification | `config_generation.py` | Suffix = value type, not array indicator |
| Structured logging | `utils/logging.py` | New logging utility with context |
| Logging migration | Multiple files | Replaced `print()` with `logger.info()` |
| Frontend extraction tab | `ConfigPreview.jsx` | New tab showing actual extracted values |
| Frontend state | `ConfigGenerator.jsx`, `App.jsx` | Handle `extractionPreview` data |

---

## Open Beads Tasks (Priority Order)

### Recently Completed (2026-02-02)
| Task ID | Description | Implementation |
|---------|-------------|----------------|
| `2jk` | **Editable YAML with Validation** | `YamlEditor` component, debounced validation, inline errors |
| `btq` | HITL Config Preview | Replaced by editable YAML validation |
| `mvk` | **Epic: Enhanced Workflow** | All 4 dependencies complete |
| `amf` | User Intent Context Flow | `user_context` wired through full flow to LLM prompt |
| `157` | Direct Open Crawler Validation | `CrawlerClient.validate()` integrated into `ConfigValidationAgent` |
| `rrn` | **Epic: Real Open Crawler Integration** | All 4 dependencies complete |
| `0z9` | Config Validation Agent | Schema, extraction rule testing, crawl rule verification |
| `duw` | LLM Proxy Key UI | Password field, validation, localStorage, setup instructions |
| `mzg` | Final Output Polish | Tabbed interface, YAML highlighting, copy/download, badges |
| `d6s` | Config Testing Workflow | Integrated into validate_config_step |
| `wfd` | Iteration Loop | Agno Loop with MAX_VALIDATION_ITERATIONS=3 |
| `bxw` | Site Crawlability Detection | Bot protection, JS detection in `routes/domain.py` |

### Ready to Work (No Blockers)

| Task ID | Priority | Description | What's Needed |
|---------|----------|-------------|---------------|
| `m8o` | P2 | HITL - Investigation Results | Add pause after investigation for user confirmation |
| `75n` | P2 | Edge Case Testing | Test corpus, error handling, resilience testing |

### No Blocked Tasks

All P1 tasks and epics are now complete!

### New Feature: Editable YAML with Validation

Users can now edit generated YAML configs directly in the Preview tab:
- **YamlEditor**: Editable textarea with line numbers
- **Auto-validation**: Debounced (800ms) calls to `/api/extraction/validate`
- **Inline errors**: Shows validation errors/warnings below editor
- **Reset button**: Revert to original generated config
- **Use & Run**: Disabled when config has errors
- **API update**: `/api/extraction/validate` now accepts `yaml_content` string

---

## File Locations Quick Reference

```
elastic-crawler-control/
├── crawler-service/app/
│   ├── server.py                    # FastAPI app entry point
│   ├── routes/
│   │   ├── workflow.py              # /api/generate SSE endpoint
│   │   ├── extraction.py            # /api/extraction/* endpoints (NEW)
│   │   ├── crawl.py                 # /api/crawl endpoint
│   │   └── health.py                # /api/health endpoint
│   ├── agents/
│   │   ├── orchestration_workflow.py # Agno Workflow with steps
│   │   ├── site_investigation.py     # Investigation agent
│   │   ├── config_generation.py      # Config generation agent
│   │   ├── config_validation.py      # Validation agent
│   │   └── workflow_state.py         # State management
│   └── utils/
│       ├── crawler_client.py         # Open Crawler binary wrapper
│       └── agno_model.py             # Agno/LLM Proxy setup
│
├── frontend/src/
│   ├── App.jsx                       # Main app with tabs (UPDATED)
│   └── components/
│       ├── ConfigGenerator.jsx       # Chat interface (NEW)
│       ├── ConfigPreview.jsx         # YAML preview (NEW)
│       ├── ExtractionTester.jsx      # Extraction testing modal (NEW)
│       ├── CrawlLogs.jsx             # Original crawl logs
│       └── CrawlRuns.jsx             # Original crawl runs

knowledge/
├── extraction-templates/
│   └── content-types.yaml            # Field definitions for blog, ecommerce, etc.

openspec/
└── specs/                            # OpenSpec specifications

.beads/
└── issues.jsonl                      # Beads task database
```

---

## Environment Variables Needed

Create/update `.env` in `elastic-crawler-control/crawler-service/`:

```bash
# Required for LLM-powered agents
LLM_PROXY_API_KEY=your-key-here
LLM_PROXY_BASE_URL=https://litellm-proxy-service-1059491012611.us-central1.run.app/v1

# Optional - path to Open Crawler (default: /crawler)
CRAWLER_PATH=/path/to/crawler

# Optional - environment
ENVIRONMENT=development
```

---

## Recommended Next Steps

1. **Validate E2E** - Run through the validation steps above first
2. **Test YAML editing** - Try editing configs in Preview tab, verify validation works
3. **Task `m8o`** - Optional HITL pause after investigation (P2)
4. **Task `75n`** - Edge case testing with test URL corpus (P2)

---

## BBC News Specific Notes

For the BBC News demo (`https://www.bbc.co.uk/news`):

- Content type: `blog` or `articles`
- Expected extraction fields: `article_title`, `article_author`, `publish_date`, `article_body`, `article_tags`
- BBC uses modern React-based rendering, may need specific selectors
- Test with actual article URLs like: `https://www.bbc.co.uk/news/articles/xxxxx`

---

## Commands Reference

```bash
# Beads task management
bd ready                    # See unblocked tasks
bd show <task-id>          # View task details
bd close <task-id>         # Close a task
bd list --status open      # All open tasks

# Git status
git status
git diff

# Run tests (if they exist)
cd elastic-crawler-control/crawler-service
pytest app/tests/
```

---

**End of Handoff**
