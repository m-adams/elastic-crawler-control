# Orchestration Specification

## Purpose
Coordinate agent workflows, manage conversation state, and stream progress to the UI via Server-Sent Events using the **Agno AI Framework**.

## Detailed Workflow Documentation

**See**: [`docs/CONFIG_GENERATION_WORKFLOW.md`](/docs/CONFIG_GENERATION_WORKFLOW.md) for the complete logical flow with timing, error handling, and examples.

## Implementation

**File**: `elastic-crawler-control/crawler-service/app/agents/orchestration_workflow.py`

The orchestration is implemented using Agno's `Workflow` class, NOT custom wrapper classes.

```python
# CORRECT: Direct Workflow instantiation with Loop for validation retries
workflow = Workflow(
    name="Config Generation Pipeline",
    steps=[
        investigate_site_step,
        generate_config_step,
        Loop(
            steps=[validate_config_step, regenerate_config_step],
            max_iterations=3,
            end_condition=check_validation_passed,
        ),
    ],
    stream=True,
    stream_events=True,
)
```

## Requirements

### Requirement: Agent Coordination
The system SHALL coordinate multiple agents through Agno Workflow.

#### Scenario: Full Generation Workflow
- GIVEN user provides domain(s) and demo scenario
- WHEN orchestrating workflow
- THEN execute using Agno Workflow:
  1. **Site Investigation Step** - `investigate_site_step()`
  2. **Config Generation Step** - `generate_config_step()`
  3. **Validation Loop** - `Loop([validate_config_step, regenerate_config_step])`
- AND use Agno's `StepInput`/`StepOutput` for data passing between steps
- AND use `previous_step_content` to access prior results

#### Scenario: Test-Fail-Iterate Loop
- GIVEN validation finds non-critical issues
- WHEN iterating
- THEN automatically (via Agno Loop):
  - Pass validation feedback via `StepOutput.content`
  - Regenerate config with feedback in `generate_config_step`
  - Re-validate via `validate_config_step`
- AND continue until `check_validation_passed()` returns True
- AND stop after max iterations (default: 3)
- AND set `valid: True` in content when validation passes

### Requirement: Conversation State Management
The system SHALL maintain conversation state via Agno session_state.

#### Scenario: State Persistence
- GIVEN a workflow is in progress
- WHEN agents interact
- THEN pass state via `StepOutput.content` dict containing:
  - `phase`: Current workflow phase
  - `investigation_result`: Site analysis data
  - `config_result`: Generated config
  - `validation_result`: Validation report
  - `params`: User inputs (domain, options)
  - `iteration_count`: Retry counter
- AND access in subsequent steps via `step_input.previous_step_content`

#### Scenario: State Recovery
- GIVEN a workflow uses session_id
- WHEN user returns
- THEN use `session_id` parameter in `workflow.arun()` for session tracking
- AND store workflow state in `_workflow_sessions` dict (or database)

### Requirement: Progress Streaming
The system SHALL stream agent progress via Agno's built-in SSE.

#### Scenario: Real-time Updates (Agno Streaming)
- GIVEN a workflow is executing with `stream=True`
- WHEN agents perform actions
- THEN Agno automatically streams `WorkflowRunOutputEvent` objects
- AND use `event.model_dump_json()` for SSE data lines
- NO custom SSE formatting code required

```python
# FastAPI endpoint using Agno streaming
@router.post("/generate")
async def generate(request: GenerateRequest):
    async def stream():
        async for event in workflow.arun(input=request.domain, stream=True):
            yield f"data: {event.model_dump_json()}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")
```

#### Scenario: Error Streaming
- GIVEN an error occurs during workflow
- WHEN error is encountered
- THEN set `StepOutput(success=False, error=str(e))`
- AND set `content["phase"] = WorkflowPhase.ERROR.value`
- AND yield error event via try/except in stream generator

### Requirement: User Interaction Points (HITL)
The system SHALL support human-in-the-loop at Agent level ONLY.

**IMPORTANT**: Agno HITL is only supported at Agent level, NOT Workflow level.

#### Scenario: Tool Confirmation
- GIVEN an agent tool requires user approval
- WHEN tool has `@tool(requires_confirmation=True)`
- THEN agent response has `is_paused=True`
- AND check `response.active_requirements` for pending confirmations
- AND use `req.confirm()` or `req.reject()` to respond
- AND call `agent.continue_run(run_response=response)` to resume

#### Scenario: Workflow-Level Confirmation (Not Supported)
- NOTE: Agno Workflow does NOT support native pausing for HITL
- WORKAROUND: Implement confirmation via custom step functions
  - Step returns special content indicating "needs confirmation"
  - FastAPI endpoint checks and pauses streaming
  - Separate `/confirm` endpoint to resume

### Requirement: Agent Tools (Not LLM Function Calling)
The system SHALL use Agno tools for agent capabilities.

#### Scenario: Tool Definitions
- GIVEN agents need capabilities
- WHEN defining tools
- THEN use Agno `@tool()` decorator:

```python
from agno.tools import tool

@tool
def fetch_robots_txt(domain: str) -> str:
    """Fetch and parse robots.txt for the given domain."""
    # Implementation...
```

- AND assign tools to Agent: `Agent(tools=[fetch_robots_txt, ...])`

#### Scenario: Tool Execution
- GIVEN agent decides to use a tool
- WHEN Agno calls the tool
- THEN tool function executes and returns result
- AND Agno passes result back to agent for reasoning

## Technical Details

### Input
- `WorkflowInput` Pydantic model via `workflow.arun(input=...)`
- Domain URL (required)
- Optional: seed_urls, output_sink, content_type, max_crawl_depth

### Output
- SSE stream of `WorkflowRunOutputEvent` objects
- Final `WorkflowOutput` Pydantic model with:
  - `success`: Boolean
  - `phase`: Workflow phase enum
  - `config`: Dict of generated config
  - `yaml_content`: YAML string
  - `validation_summary`: Validation report

### Dependencies
- Agno Framework (`agno>=0.x.x` in requirements.txt)
- Site Investigation Agent (`agents/site_investigation.py`)
- Config Generation Agent (`agents/config_generation.py`)
- Config Validation Agent (`agents/config_validation.py`)
- LLM Proxy (configured via `LLM_PROXY_BASE_URL` env var)

### Workflow Phases (WorkflowPhase enum)
1. **INITIAL**: Workflow starting
2. **INVESTIGATING**: Site investigation in progress
3. **GENERATING**: Config generation in progress
4. **VALIDATING**: Config validation in progress
5. **ITERATING**: Validation loop retry
6. **COMPLETE**: Final config ready (`valid: True`)
7. **ERROR**: Critical failure

### Error Handling
- Step errors: Set `StepOutput(success=False, error=...)` and `phase=ERROR`
- Loop termination: `check_validation_passed()` returns True on error phase
- Network issues: Caught in step try/except, returned as error content
- Agent failures: Propagated via StepOutput error field
