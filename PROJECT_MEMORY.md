# Project Memory

This file contains important project context and tooling information that should be remembered across sessions.

## Task Planning: Beads (bd)

This project uses **Beads** (`bd`) for task planning and issue tracking. Beads is a git-backed issue tracker designed for AI-supervised coding workflows.

### Initialization

The project has been initialized with beads:
- **Database**: `.beads/beads.db`
- **Issue prefix**: `open-crawler-config-generator`
- **Issues format**: `open-crawler-config-generator-{hash}` (e.g., `open-crawler-config-generator-g6t`)

### Common Commands

```bash
# Check status and see ready work
bd status
bd ready

# List all issues
bd list

# Create a new task
bd create "Task title" --description "Task description"

# Close a task
bd close <issue-id>

# Add dependencies (B depends on A means A blocks B)
bd dep add <depends-on-id> <issue-id> -t blocks

# View a specific issue
bd show <issue-id>
```

### Current Workflow

1. **Check ready work**: `bd ready` - Shows tasks with no blockers
2. **Start working**: Mark task as in-progress (if needed) or just work on it
3. **Update dependencies**: As you discover new dependencies, add them with `bd dep add`
4. **Close tasks**: When complete, use `bd close <issue-id>`

### Project-Specific Notes

- All tasks follow the naming pattern: `Phase X.Y: Description`
- Dependencies are set up to reflect the implementation phases
- Tasks are stored in `.beads/issues.jsonl` (git-backed, version controlled)

### Reference

- Beads documentation: https://steveyegge.github.io/beads/
- Hive-mind Beads guide: `hive-mind/meta/workflows/BEADS_ISSUE_TRACKER.md`

## Other Project Context

### Tech Stack
- **Backend**: Python FastAPI (integrated into elastic-crawler-control)
- **AI Framework**: **Agno** - Multi-agent orchestration (https://docs.agno.com/)
- **LLM**: Claude Sonnet 4 via Elastic LLM Proxy
- **Task Planning**: Beads (bd)
- **Spec Management**: OpenSpec (in `openspec/` directory)

### Key Directories
- `elastic-crawler-control/` - **Main project directory** (forked from ugosan/elastic-crawler-control)
  - `crawler-service/app/` - FastAPI backend
    - `routes/` - Modular route handlers (crawl.py, health.py, workflow.py)
    - `utils/` - Shared utilities (config.py, llm_client.py, agno_model.py)
    - `agents/` - **Agno-powered agents and workflow**
      - `site_investigation.py` / `site_investigation_tools.py` - Site analysis agent
      - `config_generation.py` / `config_generation_tools.py` - Config creation agent
      - `config_validation.py` / `config_validation_tools.py` - Validation agent
      - `orchestration_workflow.py` - Main Agno Workflow
      - `workflow_state.py` - Pydantic state models
    - `server.py` - FastAPI application entry point
    - `models.py` - Pydantic models (both crawl execution and config generation)
    - `tests/` - Test suite for agents and workflow
  - `frontend/` - React + Elastic UI frontend
- `knowledge/` - Open Crawler patterns + **Agno framework guide**
  - `agno/workflow-guide.md` - **CRITICAL**: Read before modifying agent code
- `openspec/` - OpenSpec specifications
- `.beads/` - Beads issue tracker database and JSONL files
- `hive-mind/` - Submodule with Elastic patterns

### Agno Architecture (IMPORTANT)

This project uses the **Agno AI Framework** for multi-agent orchestration:

1. **Agents**: Site Investigation, Config Generation, Config Validation
2. **Tools**: Each agent has specialized tools (decorated with `@tool()`)
3. **Workflow**: Uses `Workflow(steps=[...])` - NOT custom wrapper classes
4. **Streaming**: Uses Agno's built-in `stream=True` - NO custom SSE code
5. **Loops**: Validation retry via `Loop(steps=[...], end_condition=...)`
6. **HITL**: Human-in-the-loop at Agent level only via `requires_confirmation=True`

**See**: `knowledge/agno/workflow-guide.md` for patterns and anti-patterns.

### Architecture Note (Contribution Alignment)

The backend code is integrated into `elastic-crawler-control/crawler-service/` to maintain
alignment with the upstream repository (ugosan/elastic-crawler-control) for potential
contribution back. The modular structure allows:

1. **Original Crawl Features**: `routes/crawl.py` - unchanged from upstream
2. **New Config Generation**: `routes/workflow.py` - Agno-powered SSE endpoint
3. **Shared Utilities**: `utils/` - configuration, LLM client, Agno model setup
4. **Agents**: `agents/` - Agno agents with tools and orchestration workflow

LLM features are optional - the service works without `LLM_PROXY_API_KEY` set.
