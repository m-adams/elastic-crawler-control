# Beads-Agent Pattern (DRAFT)

> **Status**: Draft - Learning from open-crawler-config-generator project
> **Last Updated**: 2026-02-02
> **Author**: Matthew Adams / AI Collaboration

## Overview

The Beads-Agent pattern combines the **Beads issue tracker** with **autonomous AI agents** running via CLI, enabling supervised AI development with clean context management.

### The Problem

When using AI coding agents for extended work:

1. **Context pollution** - Agents degrade after 40-60 minutes as failures accumulate
2. **No verification** - Hard to know if agent actually completed the task correctly
3. **Lost progress** - If agent gets stuck, work may be lost
4. **Manual handoff** - Switching between tasks requires manual context management

### The Solution

Run agents in a loop with:
- **Fresh context each iteration** (Ralph Wiggum technique)
- **Beads for task management** with acceptance criteria
- **Git for state persistence** (not LLM memory)
- **Structured completion reports** for verification

## Pattern Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        Supervisor (You/Cursor)                   │
│  - Picks tasks from Beads                                       │
│  - Reviews completion reports                                    │
│  - Verifies acceptance criteria                                  │
│  - Closes tasks / requests changes                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     beads-agent.sh Script                        │
│  - Reads task from Beads (bd ready / bd show)                   │
│  - Builds prompt with context + acceptance criteria             │
│  - Invokes cursor-agent CLI with fresh context                  │
│  - Monitors output, captures completion signals                 │
│  - Updates Beads with comments/status                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      cursor-agent CLI                            │
│  - Runs with -p (print mode) for non-interactive use            │
│  - Works on single task with full context                       │
│  - Commits to git frequently                                    │
│  - Creates completion report                                    │
│  - Signals completion via <beads>COMPLETE</beads> tags          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Persistent State                            │
│  - Git: Code changes, commits                                   │
│  - Beads: Task status, comments, acceptance criteria            │
│  - Files: Completion reports, guardrails, progress logs         │
└─────────────────────────────────────────────────────────────────┘
```

## Key Concepts

### 1. Clean Context (Ralph Wiggum Technique)

Each agent invocation starts fresh:
- No memory of previous iterations
- Reads state from files/git/Beads
- Avoids context pollution and circular reasoning

**What persists**: Git commits, Beads tasks, completion reports, guardrails
**What resets**: LLM conversation history, accumulated failures

### 2. Acceptance Criteria

Every task needs checkable criteria:

```bash
bd update task-123 --acceptance "- [ ] Feature implemented
- [ ] Unit tests pass
- [ ] Integration test works
- [ ] Documentation updated"
```

Agents check these before declaring completion.

### 3. Completion Signals

Agents output structured signals:

```
<beads>COMPLETE: task-123</beads>     # All criteria met
<beads>REVIEW: task-123 - summary</beads>   # Needs human review
<beads>BLOCKED: task-123 - reason</beads>   # Can't proceed
<beads>PARTIAL: task-123 - progress</beads> # Made progress, not done
```

### 4. Completion Reports

Agents create structured reports at `.beads-agent/results/<task-id>.md`:

```markdown
# Completion Report: task-123

## Summary
Implemented the feature as specified.

## Acceptance Criteria
- [x] Feature implemented
- [x] Unit tests pass
- [x] Integration test works
- [ ] Documentation updated (deferred to separate task)

## Files Changed
- src/feature.py (new)
- tests/test_feature.py (new)

## Tests Run
- 5 tests, all passing

## Notes
- Decided to use X approach because Y
- Follow-up needed for documentation
```

### 5. Guardrails

Accumulated lessons in `.beads-agent/guardrails.md`:

```markdown
### Sign: Check Existing Code First
- **Trigger**: Before implementing new feature
- **Instruction**: Read existing related code to understand patterns
- **Added after**: Agent duplicated existing utility function
```

## Implementation

### Directory Structure

```
project/
├── .beads-agent/
│   ├── guardrails.md        # Learned lessons
│   ├── history.log          # Activity log
│   ├── status.json          # Current run status
│   ├── output.log           # Agent output
│   ├── stream.jsonl         # Raw stream output
│   ├── results/             # Completion reports per task
│   │   ├── task-123.md
│   │   └── task-456.md
│   └── MANAGEMENT.md        # Supervisor dashboard
├── .beads/
│   └── issues.jsonl         # Beads task database
└── scripts/
    └── beads-agent.sh       # Agent runner script
```

### Script Options

```bash
# Basic usage
./scripts/beads-agent.sh                    # Auto-pick next ready task
./scripts/beads-agent.sh task-123           # Specific task
./scripts/beads-agent.sh --loop             # Continuous mode
./scripts/beads-agent.sh --list             # List ready tasks
./scripts/beads-agent.sh --status           # Show agent status

# Options
-m, --model MODEL      # Model to use (default: sonnet-4.5)
-l, --loop            # Run multiple iterations
-n, --max-iterations  # Max iterations in loop mode
--no-tests            # Skip test running
--close               # Auto-close tasks on completion
```

### Prompt Structure

The script builds prompts with:

1. **Task context** - From `bd show <task-id>`
2. **Acceptance criteria** - Checkable completion conditions
3. **OpenSpec link** - Detailed specifications if available
4. **Guardrails** - Lessons from past iterations
5. **Workspace context** - Key directories and files
6. **Completion protocol** - How to signal done

## Workflow

### For the Supervisor (Human/Cursor Agent)

```bash
# 1. Check what's ready
bd ready

# 2. Review task has acceptance criteria
bd show task-123

# 3. Delegate to agent (run in terminal)
./scripts/beads-agent.sh task-123

# 4. Monitor progress
tail -f .beads-agent/output.log
cat .beads-agent/status.json

# 5. Review completion
cat .beads-agent/results/task-123.md
git log --oneline -5

# 6. Verify and close
bd close task-123 -r "Verified - all criteria met"
```

### For the Agent (cursor-agent)

1. Read guardrails and task context
2. Explore codebase, understand requirements
3. Implement incrementally with frequent commits
4. Run tests after changes
5. Create completion report
6. Signal completion with `<beads>COMPLETE</beads>`

## Lessons Learned

> This section will be updated as we learn from using the pattern.

### Lesson 1: TTY Requirements
**Problem**: `cursor-agent -p` doesn't work from within Cursor's shell (no TTY)
**Solution**: Run the script from a real terminal (iTerm, Terminal.app)
**Workaround**: Supervisor monitors output files, can't invoke directly

### Lesson 2: Stream Parsing Complexity
**Problem**: `--output-format stream-json` output is hard to parse in bash
**Solution**: Write to file and parse, or use simpler text format
**Trade-off**: Stream-json gives more detail but text is easier to work with

### Lesson 3: Acceptance Criteria Are Essential
**Problem**: Without clear criteria, agents declare "done" prematurely
**Solution**: Always add `--acceptance` when creating/updating tasks
**Pattern**: Use checkbox format `- [ ]` for each criterion

### Lesson 4: [Placeholder for next lesson]

### Lesson 5: [Placeholder for next lesson]

## Integration with Other Patterns

### OpenSpec
Tasks can link to detailed specifications:
- Agent reads spec for GIVEN/WHEN/THEN scenarios
- More detail than fits in Beads description

### Ralph Wiggum Technique
This pattern is inspired by the Ralph Wiggum approach:
- Fresh context each iteration
- State in files, not LLM memory
- Guardrails for learning
- Token monitoring (optional)

Reference: https://github.com/agrimsingh/ralph-wiggum-cursor

### A2A Coordinator Pattern
For multi-agent workflows:
- Orchestrator coordinates multiple agents
- Each agent uses beads-agent pattern
- SSE streaming for progress updates

## Limitations

1. **Can't run from Cursor** - Requires real terminal for TTY
2. **Single task focus** - Agent works on one task per invocation
3. **Manual verification** - Supervisor must review completion reports
4. **No parallel execution** - Sequential task processing only

## Future Improvements

- [ ] Add token monitoring (Ralph-style rotation)
- [ ] Parallel task execution
- [ ] Auto-verification of acceptance criteria
- [ ] Integration with CI/CD
- [ ] Web dashboard for monitoring
- [ ] Support for non-Cursor agents (Claude CLI, etc.)

## Quick Start

```bash
# 1. Ensure beads is set up
bd ready

# 2. Add acceptance criteria to a task
bd update task-123 --acceptance "- [ ] Feature works
- [ ] Tests pass"

# 3. Run agent (in your terminal, not Cursor)
./scripts/beads-agent.sh task-123

# 4. Monitor and review
cat .beads-agent/results/task-123.md
bd close task-123 -r "Verified complete"
```

---

## Appendix: Related Documents

- [Beads Issue Tracker Guide](hive-mind/meta/workflows/BEADS_ISSUE_TRACKER.md)
- [Ralph Wiggum Technique](https://deepwiki.com/agrimsingh/ralph-wiggum-cursor)
- [Cursor Agent CLI Docs](https://cursor.com/docs/cli/using)

## Changelog

| Date | Change |
|------|--------|
| 2026-02-02 | Initial draft created |
| | |
