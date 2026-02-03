# Agno Workflow Guide

> Reference documentation for building workflows with Agno.
> Source: https://docs.agno.com/basics/workflows/building-workflows

## CRITICAL: Workflow vs Agent HITL

**Human-in-the-Loop (HITL) is currently ONLY supported for `Agent`, NOT for `Workflow` or `Team`.**

This means:
- For user confirmation points, use Agent-level `requires_confirmation=True` on tools
- Workflows don't pause for human input - design accordingly
- Use custom step functions to handle confirmation state externally

## Building Blocks

### 1. Workflow Class

The `Workflow` class is the top-level orchestrator. You **instantiate** it, you don't extend it:

```python
from agno.workflow import Workflow, Step, Loop, StepOutput

# CORRECT: Instantiate Workflow with steps
workflow = Workflow(
    name="Config Generation Pipeline",
    steps=[
        investigation_agent,      # Agent
        config_generator,         # Agent  
        validation_function,      # Python function
    ],
    session_state={"domain": None},  # Persisted state
    stream=True,                      # Enable streaming
    stream_events=True,              # Stream intermediate steps
)

# Run workflow
result = workflow.run(input="https://example.com")
# Or async
result = await workflow.arun(input="https://example.com")
```

### 2. Step

Each step encapsulates exactly one executor - Agent, Team, or Python function:

```python
from agno.workflow import Step, StepInput, StepOutput

# Using an Agent as a step
step1 = Step(
    agent=my_agent,
    name="investigation",
    max_retries=2,
    timeout_seconds=60,
)

# Using a custom function as a step
def my_custom_step(step_input: StepInput) -> StepOutput:
    # Access previous step outputs
    previous_output = step_input.previous_step_output
    # Access session state
    state = step_input.session_state
    
    # Do work...
    result = process_data(step_input.input)
    
    return StepOutput(
        content=result,
        # Update session state
        session_state={"processed": True}
    )
```

### 3. Loop

Execute steps multiple times until condition met:

```python
from agno.workflow import Loop

# Loop with max iterations
validation_loop = Loop(
    steps=[validation_agent, fix_agent],
    max_iterations=3,
    end_condition=lambda outputs: outputs[-1].content.get("valid", False)
)

workflow = Workflow(
    name="With Validation Loop",
    steps=[
        generation_agent,
        validation_loop,  # Will retry up to 3 times
    ]
)
```

Loop Parameters:
- `steps`: Steps to execute each iteration
- `max_iterations`: Maximum iterations (default: 3)
- `end_condition`: Callable that returns True to stop loop

### 4. Parallel

Execute steps concurrently:

```python
from agno.workflow import Parallel

parallel_analysis = Parallel(
    steps=[
        seo_analyzer,
        content_analyzer,
        structure_analyzer,
    ]
)
# Outputs are joined together
```

### 5. Condition

Make steps conditional:

```python
from agno.workflow import Condition

conditional_step = Condition(
    condition=lambda input: input.get("needs_review", False),
    steps=[review_agent]
)
```

### 6. Router

Branching logic:

```python
from agno.workflow import Router

def route_by_content_type(step_input):
    content_type = step_input.session_state.get("content_type")
    if content_type == "blog":
        return "blog_handler"
    elif content_type == "ecommerce":
        return "ecommerce_handler"
    return "generic_handler"

router = Router(
    router_function=route_by_content_type,
    routes={
        "blog_handler": blog_agent,
        "ecommerce_handler": ecommerce_agent,
        "generic_handler": generic_agent,
    }
)
```

## Workflow Parameters

Key parameters for Workflow:

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | str | Workflow name |
| `steps` | list | List of steps (agents, functions, loops, etc.) |
| `session_state` | dict | Persisted state across runs |
| `stream` | bool | Stream the response |
| `stream_events` | bool | Stream intermediate step events |
| `stream_executor_events` | bool | Stream agent/team events (default True) |
| `db` | BaseDb | Database for persistence |
| `session_id` | str | Session identifier |

## Streaming (SSE)

Agno provides built-in streaming - no custom SSE needed:

```python
# Streaming workflow execution
for event in workflow.run(input="analyze site", stream=True):
    # event is WorkflowRunOutputEvent
    print(event.content)
    
# Async streaming
async for event in workflow.arun(input="analyze site", stream=True):
    yield event.content  # For SSE endpoint
```

## Session State

State persists across workflow runs:

```python
workflow = Workflow(
    name="Stateful Workflow",
    session_state={"iteration": 0, "history": []},
)

# In a step function
def stateful_step(step_input: StepInput) -> StepOutput:
    current = step_input.session_state.get("iteration", 0)
    return StepOutput(
        content="Done",
        session_state={"iteration": current + 1}
    )
```

## Human-in-the-Loop (Agent Level)

Since HITL is only at Agent level, implement confirmation via tools:

```python
from agno.tools import tool

@tool(requires_confirmation=True)
def apply_config(config: str) -> str:
    """Apply the generated config - requires user approval."""
    return f"Config applied: {config}"

# When agent calls this tool, execution pauses
# User must confirm/reject before continuing
```

Handling in code:

```python
response = agent.run("Generate and apply config")

if response.is_paused:
    for req in response.active_requirements:
        if req.needs_confirmation:
            # Show to user, get approval
            if user_approves:
                req.confirm()
            else:
                req.reject()
    
    # Resume execution
    response = agent.continue_run(run_response=response)
```

## FastAPI Integration Example

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.post("/generate")
async def generate_config(domain: str):
    async def event_stream():
        async for event in workflow.arun(input=domain, stream=True):
            yield f"data: {event.model_dump_json()}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )
```

## Common Patterns

### Config Generation Pipeline

```python
from agno.workflow import Workflow, Loop, StepOutput

def check_validation(outputs: list) -> bool:
    """End loop if validation passes."""
    last = outputs[-1] if outputs else None
    return last and last.content.get("valid", False)

workflow = Workflow(
    name="Config Generation",
    steps=[
        site_investigation_agent,
        config_generation_agent,
        Loop(
            steps=[validation_agent, regeneration_agent],
            max_iterations=3,
            end_condition=check_validation,
        ),
    ],
    stream=True,
    stream_events=True,
)
```

## DO NOT

- **DON'T** create a custom class that "wraps" Workflow - use Workflow directly
- **DON'T** manually manage state with dicts - use `session_state`
- **DON'T** implement custom SSE - use `stream=True`
- **DON'T** expect HITL at Workflow level - it's Agent-only currently
