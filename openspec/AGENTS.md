# AI Agent Instructions

## Code Style & Structure

- **Modular Files**: Keep files small and focused. Each route should be in a separate file.
- **Documentation**: Code should be well-documented for both humans and LLMs
- **Utility Modules**: Extract reusable logic into utility modules that routes reference
- **Python Venv**: Always use venv in `elastic-crawler-control/crawler-service/`

## Environment & Configuration

- **Secrets**: All configuration in `.env` file, never hardcoded
- **Dotenv**: Use `python-dotenv` with `load_dotenv(override=True)` to ensure local vars take precedence
- **Example File**: Maintain comprehensive `.env.example` with all required variables (including `LLM_PROXY_BASE_URL`)

## Agno Framework (AI Agent Orchestration)

This project uses the **Agno framework** for AI agents. Key patterns:

- **Agents**: Each agent has specialized tools (decorated functions)
- **Workflow**: Use `Workflow(steps=[...])` directly - NOT custom wrapper classes
- **Streaming**: Use Agno's built-in `stream=True` - NO custom SSE code
- **Loops**: Use `Loop(steps=[...], end_condition=...)` for retry logic
- **State**: Use `session_state` dict and `StepOutput.content` for passing data

**CRITICAL**: See `knowledge/agno/workflow-guide.md` for correct patterns.

## Elasticsearch Integration

- **Client**: Use official `elasticsearch-py` Python client
- **Connection**: Via environment variables (host, cloud_id, api_key)
- **Templates**: Save mappings/queries as separate template files

## Extraction Field Naming Conventions (CRITICAL)

When creating extraction rules, use **suffix-based naming** to control Elasticsearch mapping:

| Suffix | Mapping | When to Use |
|--------|---------|-------------|
| `_semantic` | text + ELSER + Jina embeddings | Fields for semantic/conceptual search |
| `_text` | text + keyword | Regular searchable text |
| `_keyword` | keyword only | Exact match, filtering, aggregations |
| `_date` | date type | Timestamps, publish dates |
| `_num`, `_count`, `_price`, `_score` | float | Numeric values |
| (no suffix) | text + keyword | Default text behavior |

### Quick Reference

```yaml
# ✅ CORRECT - Using conventions
- field_name: product_description_semantic  # Gets ELSER + Jina
- field_name: author_name_text              # Searchable text
- field_name: category_keyword              # Exact match
- field_name: published_date                # Date type
- field_name: item_price                    # Float type

# ❌ WRONG - No convention, unclear mapping
- field_name: description    # What mapping?
- field_name: category       # text or keyword?
```

### Decision Guide

- **Will users search this field with questions/concepts?** → Use `_semantic`
- **Will users search this with specific keywords?** → Use `_text`
- **Will users filter/aggregate on exact values?** → Use `_keyword`
- **Is it a date?** → Use `_date`
- **Is it a number?** → Use `_num`, `_price`, `_count`, or `_score`

### Cost Note

`_semantic` fields generate embeddings (ELSER sparse + Jina dense), which costs compute time and storage. Only use for fields that truly benefit from semantic understanding.

## FastAPI Patterns

- **Routes**: Each route in separate file under `elastic-crawler-control/crawler-service/app/routes/`
- **Agents**: Agno agents in `elastic-crawler-control/crawler-service/app/agents/`
- **Dependencies**: Use FastAPI dependency injection for shared resources
- **SSE Streaming**: Use Agno's `workflow.arun(stream=True)` for SSE endpoints
- **Error Handling**: Provide clear error messages for debugging

## LLM Integration

- **Framework**: Agno AI Framework with OpenAI-compatible backend
- **Proxy**: Use Elastic LLM Proxy via `LLM_PROXY_BASE_URL` (ends with `/v1`)
- **Model**: Default to `claude-sonnet-4`
- **Tools**: Implement as Agno tools with `@tool()` decorator
- **Streaming**: Handled automatically by Agno when `stream=True`

## Testing Philosophy

- **No Mocking**: Always use real services (Open Crawler, Elasticsearch)
- **Fail Fast**: Do upfront checks (robots.txt, curl tests) to catch issues early
- **Thorough Validation**: Test extraction rules against 10+ pages, validate crawl rules
- **User Feedback**: Show intermediate results and confirmations

## Linking Specs to Beads Issues

Use labels to link Beads issues to their corresponding OpenSpec specifications.

### Convention

**Label format**: `spec:<spec-name>`

The spec name is the directory name under `openspec/specs/`.

### Available Spec Labels

| Spec Path | Label |
|-----------|-------|
| `openspec/specs/site-investigation/spec.md` | `spec:site-investigation` |
| `openspec/specs/config-generation/spec.md` | `spec:config-generation` |
| `openspec/specs/config-validation/spec.md` | `spec:config-validation` |
| `openspec/specs/orchestration/spec.md` | `spec:orchestration` |
| `openspec/specs/backend-api/spec.md` | `spec:backend-api` |
| `openspec/specs/ui-chat/spec.md` | `spec:ui-chat` |
| `openspec/specs/ui-config-preview/spec.md` | `spec:ui-config-preview` |
| `openspec/specs/config-testing/spec.md` | `spec:config-testing` |
| `openspec/specs/deployment/spec.md` | `spec:deployment` |
| `openspec/specs/workflow-input/spec.md` | `spec:workflow-input` |
| `openspec/specs/workflow-detailed/spec.md` | `spec:workflow-detailed` |
| `openspec/specs/open-crawler-integration/spec.md` | `spec:open-crawler-integration` |

### Usage

**When creating issues:**
```bash
bd create "Implement site investigation" \
  --labels "spec:site-investigation"
```

**When adding to existing issues:**
```bash
bd label add <issue-id> spec:site-investigation
```

**Query all issues for a spec:**
```bash
bd list --label spec:orchestration
```

**Multiple specs per issue** (when work spans multiple specs):
```bash
bd label add <issue-id> spec:orchestration
bd label add <issue-id> spec:backend-api
```

### Benefits

- **Traceability**: See which issues implement each spec
- **Coverage**: Identify specs without implementation issues
- **Context**: When working on an issue, quickly find the relevant spec
- **Review**: Filter issues by spec for focused review

## When Editing This Project

1. **Read `knowledge/agno/workflow-guide.md`** before touching agent code
2. Read relevant specs in `openspec/specs/` before making changes
3. **Link issues to specs** using `spec:<name>` labels
4. Check `openspec/changes/` for active proposals
5. Follow the modular structure - don't create monolithic files
6. Update specs when requirements change
7. Use OpenSpec change proposals for significant modifications
