# Workflow Review Prompt

Copy and paste this prompt to an AI agent to review the config generation workflow for improvements.

---

## Prompt

```
I need you to review our Open Crawler Config Generator workflow and assess it for improvements.

## Context

This is an AI-powered tool that generates Open Crawler YAML configurations for web crawling. Users provide a target URL and content type, and the system:
1. Validates the site is crawlable
2. Investigates site structure (robots.txt, sitemaps, sample pages)
3. Generates a crawler configuration with crawl rules and extraction rules
4. Validates the config works (tests selectors against real pages)
5. Returns the final YAML config

## Documentation to Review

Please read these files to understand the current implementation:

1. **Workflow Documentation**: `docs/CONFIG_GENERATION_WORKFLOW.md`
   - Complete logical flow from URL to validated config
   - 6 phases with timing and error handling
   - Technical details and configuration parameters

2. **Agent Handoff**: `AGENT_HANDOFF.md`
   - Current implementation status
   - Recent fixes and known issues
   - File locations

3. **Key Implementation Files**:
   - `elastic-crawler-control/crawler-service/app/routes/workflow.py` - SSE endpoint
   - `elastic-crawler-control/crawler-service/app/agents/orchestration_workflow.py` - Agno workflow
   - `elastic-crawler-control/crawler-service/app/agents/site_investigation.py` - Site analysis
   - `elastic-crawler-control/crawler-service/app/agents/config_generation.py` - Config creation
   - `elastic-crawler-control/crawler-service/app/agents/config_validation.py` - Validation

## Assessment Criteria

Please evaluate the workflow against these dimensions:

### 1. Efficiency
- Are there unnecessary steps that could be removed?
- Are there steps that could run in parallel instead of sequentially?
- Is the ~60-90 second total time acceptable, or should we target faster?
- Are the sitemap/page limits (10 sitemaps, 500 URLs, 10 pages) appropriate?

### 2. Robustness
- Are there edge cases not being handled?
- Is error handling comprehensive?
- Are the timeout values (120s investigation, 30s HTTP) appropriate?
- Should we add retry logic anywhere?

### 3. Quality of Output
- Are the generated configs high quality?
- Are extraction selectors diverse enough (fallback patterns)?
- Are crawl rules appropriate (not too broad, not too narrow)?
- Is the field naming convention (_semantic, _text, _keyword) clear?

### 4. User Experience
- Is the SSE streaming providing useful feedback?
- Are error messages actionable?
- Should there be more checkpoints for user confirmation (HITL)?
- Is the ~60-90 second wait acceptable for users?

### 5. Architecture
- Is the Agno workflow pattern the right choice?
- Should any components be split or combined?
- Is the separation of concerns appropriate?
- Are there any anti-patterns in the code?

### 6. Missing Features
- What capabilities would make this more useful?
- Are there common crawling patterns not being detected?
- Should we support more content types?
- Would caching help (avoid re-investigating same site)?

## Deliverables

Please provide:

1. **Executive Summary**: 2-3 sentence overall assessment

2. **Strengths**: What's working well (bullet points)

3. **Recommended Improvements**: Prioritized list with:
   - Priority (P0 = critical, P1 = important, P2 = nice-to-have)
   - Description of the improvement
   - Expected impact
   - Estimated effort (small/medium/large)

4. **Questions**: Any clarifying questions about requirements or constraints

5. **Optional**: If you see quick wins (< 30 min to implement), feel free to implement them directly.
```

---

## Usage

1. Start a new conversation with an AI coding agent
2. Paste the prompt above
3. The agent will read the documentation and provide assessment
4. Review recommendations and decide which to implement

## Notes

- The workflow was recently fixed and validated (2026-02-03)
- 11 sites tested successfully
- Main pain point is ~60-90 second generation time
- LLM calls are the biggest time sink
