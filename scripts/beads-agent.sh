#!/bin/bash
# Beads-Agent v2: Run cursor-agent with clean context on Beads tasks
#
# Integrates with the Beads (bd) task tracker to:
# - Pick the next best task from ready tasks
# - Provide full task context + acceptance criteria + OpenSpec
# - Run with clean context each iteration (Ralph-style)
# - Mark tasks in_progress while working
# - Set status to review or closed when complete
# - Run tests if defined
#
# Usage:
#   ./scripts/beads-agent.sh                    # Auto-pick next ready task
#   ./scripts/beads-agent.sh <issue-id>         # Work on specific task
#   ./scripts/beads-agent.sh --loop             # Loop through tasks (Ralph-style)
#   ./scripts/beads-agent.sh --list             # List ready tasks and exit
#   ./scripts/beads-agent.sh --status           # Show current status
#
# Requirements:
#   - bd (Beads CLI) installed and configured
#   - cursor-agent CLI installed
#   - Git repository

set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT_DIR="$WORKSPACE/.beads-agent"
OUTPUT_LOG="$AGENT_DIR/output.log"
STATUS_FILE="$AGENT_DIR/status.json"
STREAM_LOG="$AGENT_DIR/stream.jsonl"
HISTORY_LOG="$AGENT_DIR/history.log"
GUARDRAILS_FILE="$AGENT_DIR/guardrails.md"
TASK_RESULTS_DIR="$AGENT_DIR/results"

# Defaults
MODEL="${BEADS_MODEL:-opus-4.5-thinking}"
LOOP_MODE=false
LIST_ONLY=false
STATUS_ONLY=false
SPECIFIC_TASK=""
MAX_ITERATIONS="${MAX_ITERATIONS:-10}"
RUN_TESTS="${RUN_TESTS:-true}"
MARK_REVIEW="${MARK_REVIEW:-true}"
LABEL_FILTER=""
PARENT_FILTER=""

# =============================================================================
# HELPERS
# =============================================================================

log() {
  local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
  echo "[$timestamp] $*" | tee -a "$HISTORY_LOG"
}

show_help() {
  cat << 'EOF'
Beads-Agent v2: Cursor Agent with Beads Task Integration

Runs cursor-agent with clean context on tasks from your Beads issue tracker.
Each iteration starts fresh (Ralph-style) to avoid context pollution.

Usage:
  ./scripts/beads-agent.sh [options] [issue-id]

Options:
  -m, --model MODEL      Model to use (default: opus-4.5-thinking)
  -l, --loop             Run in loop mode (Ralph-style continuous work)
  -n, --max-iterations N Maximum iterations in loop mode (default: 10)
  --label LABEL          Filter tasks by label (e.g., --label agno-migration)
  --epic EPIC-ID         Filter tasks by parent epic ID
  --no-tests             Skip running tests after completion
  --no-review            Don't mark tasks for review (just leave open)
  --close                Auto-close tasks when complete (instead of review)
  --list                 List ready tasks and exit
  --status               Show agent status and exit
  -h, --help             Show this help

Examples:
  ./scripts/beads-agent.sh                              # Auto-pick next ready task
  ./scripts/beads-agent.sh open-crawler-config-generator-9l3   # Work on specific task
  ./scripts/beads-agent.sh --loop                       # Continuous loop mode
  ./scripts/beads-agent.sh --list                       # See available tasks
  ./scripts/beads-agent.sh --label agno-migration --loop # Work on all agno-migration tasks
  ./scripts/beads-agent.sh --epic j0s --loop            # Work on all tasks under epic j0s

Monitor progress:
  tail -f .beads-agent/output.log      # Watch agent output
  cat .beads-agent/status.json         # Check current status
  bd ready                             # See remaining tasks
EOF
}

init_agent_dir() {
  mkdir -p "$AGENT_DIR"
  mkdir -p "$TASK_RESULTS_DIR"
  
  # Initialize guardrails if doesn't exist
  if [[ ! -f "$GUARDRAILS_FILE" ]]; then
    cat > "$GUARDRAILS_FILE" << 'EOF'
# Beads-Agent Guardrails

> Lessons learned from past iterations. READ THESE BEFORE ACTING.

## Core Principles

### Read Before Writing
- **Trigger**: Before modifying any file
- **Instruction**: Always read the existing file first to understand context

### Commit Checkpoints
- **Trigger**: After completing significant work
- **Instruction**: Commit changes with descriptive message before moving on

### Test After Changes
- **Trigger**: After any code change
- **Instruction**: Run relevant tests to verify nothing broke

### Check Acceptance Criteria
- **Trigger**: Before marking task complete
- **Instruction**: Verify ALL acceptance criteria are met, not just "it works"

---

## Learned Lessons

EOF
  fi
  
  # Initialize history if doesn't exist
  if [[ ! -f "$HISTORY_LOG" ]]; then
    echo "# Beads-Agent History" > "$HISTORY_LOG"
    echo "" >> "$HISTORY_LOG"
  fi
}

# Get list of ready tasks (no blockers), optionally filtered by label or parent
get_ready_tasks() {
  local filter_args=""
  
  if [[ -n "$LABEL_FILTER" ]]; then
    filter_args="--label $LABEL_FILTER"
  fi
  
  if [[ -n "$PARENT_FILTER" ]]; then
    # For parent filter, we list children and check which are ready
    # First get all child task IDs
    local children
    children=$(bd list --status open $filter_args 2>/dev/null | grep -oE 'open-crawler-config-generator-[a-z0-9.]+' || echo "")
    
    if [[ -n "$children" ]]; then
      # Filter to only those that are ready (have no blockers)
      local ready_ids
      ready_ids=$(bd ready 2>/dev/null | grep -oE 'open-crawler-config-generator-[a-z0-9.]+' || echo "")
      
      # Find intersection
      for child in $children; do
        # Escape dots for grep regex
        local escaped_child="${child//./\\.}"
        if echo "$ready_ids" | grep -q "^${escaped_child}$"; then
          # Get the title line (skip empty first line)
          bd show "$child" 2>/dev/null | grep -m1 "^open-crawler-config-generator"
        fi
      done
      return
    fi
  fi
  
  if [[ -n "$filter_args" ]]; then
    # Get ready tasks filtered by label
    local label_tasks
    label_tasks=$(bd list --status open $filter_args 2>/dev/null | grep -oE 'open-crawler-config-generator-[a-z0-9.]+' || echo "")
    
    local ready_ids
    ready_ids=$(bd ready 2>/dev/null | grep -oE 'open-crawler-config-generator-[a-z0-9.]+' || echo "")
    
    # Find intersection - tasks that have the label AND are ready
    for task in $label_tasks; do
      # Escape dots for grep regex
      local escaped_task="${task//./\\.}"
      if echo "$ready_ids" | grep -q "^${escaped_task}$"; then
        # Get the title line (skip empty first line)
        bd show "$task" 2>/dev/null | grep -m1 "^open-crawler-config-generator"
      fi
    done
  else
    bd ready 2>/dev/null | grep -E '^\s*[0-9]+\.' | sed 's/^[[:space:]]*[0-9]*\.[[:space:]]*//'
  fi
}

# Get first ready task ID, optionally filtered by label or parent
get_next_task_id() {
  if [[ -n "$LABEL_FILTER" ]] || [[ -n "$PARENT_FILTER" ]]; then
    # Get filtered ready tasks and return first one
    local filter_args=""
    [[ -n "$LABEL_FILTER" ]] && filter_args="--label $LABEL_FILTER"
    
    local label_tasks
    label_tasks=$(bd list --status open $filter_args 2>/dev/null | grep -oE 'open-crawler-config-generator-[a-z0-9.]+' || echo "")
    
    local ready_ids
    ready_ids=$(bd ready 2>/dev/null | grep -oE 'open-crawler-config-generator-[a-z0-9.]+' || echo "")
    
    # Find first task that has the label AND is ready (skip epics - type epic)
    for task in $label_tasks; do
      # Escape dots for grep regex
      local escaped_task="${task//./\\.}"
      if echo "$ready_ids" | grep -q "^${escaped_task}$"; then
        # Check if it's not an epic (epics have no . in their ID typically, or check type)
        local task_type
        task_type=$(bd show "$task" 2>/dev/null | grep -i "Type:" | head -1 || echo "")
        if [[ ! "$task_type" =~ epic ]]; then
          echo "$task"
          return
        fi
      fi
    done
    echo ""
  else
    bd ready 2>/dev/null | grep -E '^\s*1\.' | grep -oE 'open-crawler-config-generator-[a-z0-9.]+' | head -1
  fi
}

# Get task details as structured text
get_task_context() {
  local task_id="$1"
  bd show "$task_id" 2>/dev/null
}

# Get acceptance criteria from task (bd edit --acceptance outputs them)
get_acceptance_criteria() {
  local task_id="$1"
  # Check if task has acceptance criteria field
  local criteria
  criteria=$(bd show "$task_id" 2>/dev/null | grep -A100 "Acceptance:" | head -50) || criteria=""
  echo "$criteria"
}

# Try to find matching OpenSpec for a task
get_openspec() {
  local task_id="$1"
  local task_title
  task_title=$(bd show "$task_id" 2>/dev/null | head -1 | sed 's/.*: //')
  
  # Map task titles to specs (heuristic)
  local spec_file=""
  case "$task_title" in
    *"Site Investigation"*)
      spec_file="$WORKSPACE/openspec/specs/site-investigation/spec.md"
      ;;
    *"Config Generation"*)
      spec_file="$WORKSPACE/openspec/specs/config-generation/spec.md"
      ;;
    *"Config Validation"*)
      spec_file="$WORKSPACE/openspec/specs/config-validation/spec.md"
      ;;
    *"Config Preview"*)
      spec_file="$WORKSPACE/openspec/specs/ui-config-preview/spec.md"
      ;;
    *"Chat Interface"*)
      spec_file="$WORKSPACE/openspec/specs/ui-chat/spec.md"
      ;;
    *"Config Testing"*)
      spec_file="$WORKSPACE/openspec/specs/config-testing/spec.md"
      ;;
    *"Orchestrator"*)
      spec_file="$WORKSPACE/openspec/specs/orchestration/spec.md"
      ;;
  esac
  
  if [[ -n "$spec_file" ]] && [[ -f "$spec_file" ]]; then
    echo "$spec_file"
  fi
}

# Build the agent prompt with full context
build_agent_prompt() {
  local task_id="$1"
  local task_context
  task_context=$(get_task_context "$task_id")
  
  local acceptance_criteria
  acceptance_criteria=$(get_acceptance_criteria "$task_id")
  
  local spec_file
  spec_file=$(get_openspec "$task_id")
  
  local spec_content=""
  if [[ -n "$spec_file" ]]; then
    spec_content="## OpenSpec (Detailed Requirements)

Read the full specification at: $spec_file

Key scenarios to implement:
$(head -100 "$spec_file" | grep -A3 "#### Scenario:" || echo "See spec file for details")"
  fi
  
  local ready_tasks
  ready_tasks=$(bd ready 2>/dev/null || echo "No tasks available")
  
  cat << EOF
# Beads Task Agent

You are an autonomous development agent working on a task from the Beads issue tracker.

## YOUR CURRENT TASK

$task_context

## ACCEPTANCE CRITERIA

${acceptance_criteria:-"No explicit acceptance criteria defined. Verify your work meets the task description."}

$spec_content

## INSTRUCTIONS

1. **Read the guardrails first**: Check \`.beads-agent/guardrails.md\` for lessons from past iterations
2. **Read the relevant OpenSpec**: If referenced above, read the full spec file
3. **Check existing code**: Look at what's already implemented in the codebase
4. **Plan your approach**: Think through the steps needed before coding
5. **Implement incrementally**: Make small, testable changes
6. **Write tests**: Create or update tests for your changes
7. **Commit frequently**: Use descriptive commit messages like \`beads[$task_id]: implement X\`
8. **Verify acceptance criteria**: Check each criterion before declaring complete

## COMPLETION PROTOCOL

When you finish, you MUST:

1. **Run any existing tests**: 
   - Python: \`cd elastic-crawler-control/crawler-service && python -m pytest app/ -v\`
   - Or check if tests exist in the relevant directory

2. **Create a completion report** at \`.beads-agent/results/$task_id.md\` containing:
   - Summary of what you implemented
   - Files created/modified
   - Tests run and their results
   - Acceptance criteria checklist (mark each [x] or [ ])
   - Any issues or follow-up work needed

3. **Signal completion** with one of these tags:
   - \`<beads>COMPLETE: $task_id</beads>\` - All acceptance criteria met, tests pass
   - \`<beads>REVIEW: $task_id - summary of what needs review</beads>\` - Needs human review
   - \`<beads>BLOCKED: $task_id - what's blocking</beads>\` - Can't proceed
   - \`<beads>PARTIAL: $task_id - what was done, what remains</beads>\` - Made progress but not done

## WORKSPACE CONTEXT

Working directory: $WORKSPACE
Task ID: $task_id
Key directories:
- \`elastic-crawler-control/crawler-service/app/\` - Main backend code
- \`knowledge/\` - Open Crawler knowledge base
- \`openspec/specs/\` - Detailed specifications

## OTHER READY TASKS (for context)

$ready_tasks

Begin by reading the guardrails and any referenced spec file, then explore the codebase.
EOF
}

# Parse agent output for completion signals
parse_completion_signal() {
  local output_file="$1"
  local stream_file="$2"
  
  # Check output log first
  if grep -q '<beads>COMPLETE:' "$output_file" 2>/dev/null; then
    echo "COMPLETE"
    return
  elif grep -q '<beads>REVIEW:' "$output_file" 2>/dev/null; then
    echo "REVIEW"
    return
  elif grep -q '<beads>BLOCKED:' "$output_file" 2>/dev/null; then
    echo "BLOCKED"
    return
  elif grep -q '<beads>PARTIAL:' "$output_file" 2>/dev/null; then
    echo "PARTIAL"
    return
  fi
  
  # Check stream log for signals in assistant messages
  if [[ -f "$stream_file" ]]; then
    if grep -q 'COMPLETE.*</beads>' "$stream_file" 2>/dev/null; then
      echo "COMPLETE"
      return
    elif grep -q 'REVIEW.*</beads>' "$stream_file" 2>/dev/null; then
      echo "REVIEW"
      return
    fi
  fi
  
  echo "UNKNOWN"
}

# Extract summary from completion report
get_completion_summary() {
  local task_id="$1"
  local report_file="$TASK_RESULTS_DIR/$task_id.md"
  
  if [[ -f "$report_file" ]]; then
    head -20 "$report_file"
  else
    echo "No completion report found"
  fi
}

# Run tests if available
run_tests() {
  local workspace="$1"
  
  log "Running tests..."
  
  # Check for Python tests
  if [[ -d "$workspace/elastic-crawler-control/crawler-service" ]]; then
    cd "$workspace/elastic-crawler-control/crawler-service"
    if [[ -f "requirements.txt" ]]; then
      # Activate venv if exists
      if [[ -d "$workspace/venv" ]]; then
        source "$workspace/venv/bin/activate" 2>/dev/null || true
      fi
      
      # Run pytest
      python -m pytest app/ -v --tb=short 2>&1 | tee -a "$OUTPUT_LOG" || true
    fi
  fi
  
  # Add other test runners as needed
  cd "$workspace"
}

# Update task status in Beads
update_task_status() {
  local task_id="$1"
  local status="$2"  # close, comment
  local message="${3:-}"
  
  case "$status" in
    "close")
      log "Closing task: $task_id"
      bd close "$task_id" 2>/dev/null || echo "Could not close task"
      ;;
    "comment")
      if [[ -n "$message" ]]; then
        log "Adding comment to task: $task_id"
        bd comment "$task_id" "$message" 2>/dev/null || echo "Could not add comment"
      fi
      ;;
  esac
}

# Run a single agent iteration
run_iteration() {
  local task_id="$1"
  local iteration="$2"
  
  local prompt
  prompt=$(build_agent_prompt "$task_id")
  
  # Setup output files for this iteration
  local iter_output="$AGENT_DIR/output_${task_id}_${iteration}.log"
  echo "# Iteration $iteration - Task: $task_id" > "$iter_output"
  echo "# Started: $(date -Iseconds)" >> "$iter_output"
  echo "" >> "$iter_output"
  
  # Also update main output log
  cp "$iter_output" "$OUTPUT_LOG"
  
  : > "$STREAM_LOG"
  
  # Write status
  cat > "$STATUS_FILE" << EOF
{
  "status": "running",
  "task_id": "$task_id",
  "iteration": $iteration,
  "started_at": "$(date -Iseconds)",
  "model": "$MODEL",
  "workspace": "$WORKSPACE"
}
EOF

  log "Starting iteration $iteration on task: $task_id"
  
  # Add comment to Beads that we're working on it
  update_task_status "$task_id" "comment" "🤖 Agent started iteration $iteration (model: $MODEL)"
  
  echo ""
  echo "═══════════════════════════════════════════════════════════════════"
  echo "🚀 Beads-Agent Iteration $iteration"
  echo "═══════════════════════════════════════════════════════════════════"
  echo ""
  echo "Task:      $task_id"
  echo "Model:     $MODEL"
  echo "Monitor:   tail -f $OUTPUT_LOG"
  echo ""
  
  cd "$WORKSPACE"
  
  # Run cursor-agent and capture output properly
  local exit_code=0
  
  # Use process substitution to capture output while also displaying it
  cursor-agent -p --force --approve-mcps \
    --output-format stream-json \
    --model "$MODEL" \
    --workspace "$WORKSPACE" \
    "$prompt" 2>&1 > >(tee "$STREAM_LOG") | while IFS= read -r line; do
      echo "$line"
    done || exit_code=$?
  
  # Parse the stream log for readable content and write to output log
  if [[ -f "$STREAM_LOG" ]]; then
    while IFS= read -r line; do
      if echo "$line" | jq -e '.type == "assistant"' > /dev/null 2>&1; then
        content=$(echo "$line" | jq -r '.message.content[]? | select(.type == "text") | .text // empty' 2>/dev/null)
        if [[ -n "$content" ]]; then
          echo "$content" >> "$iter_output"
          echo "$content" >> "$OUTPUT_LOG"
        fi
      fi
    done < "$STREAM_LOG"
  fi
  
  # Check completion signal
  local signal
  signal=$(parse_completion_signal "$OUTPUT_LOG" "$STREAM_LOG")
  
  # Get summary if completion report exists
  local summary=""
  if [[ -f "$TASK_RESULTS_DIR/$task_id.md" ]]; then
    summary=$(get_completion_summary "$task_id")
  fi
  
  # Update status file
  cat > "$STATUS_FILE" << EOF
{
  "status": "completed",
  "task_id": "$task_id",
  "iteration": $iteration,
  "started_at": "$(jq -r '.started_at' "$STATUS_FILE" 2>/dev/null || echo "unknown")",
  "completed_at": "$(date -Iseconds)",
  "exit_code": $exit_code,
  "signal": "$signal",
  "model": "$MODEL",
  "workspace": "$WORKSPACE",
  "has_report": $([ -f "$TASK_RESULTS_DIR/$task_id.md" ] && echo "true" || echo "false")
}
EOF

  log "Iteration $iteration completed with signal: $signal"
  
  # Handle completion based on signal
  case "$signal" in
    "COMPLETE")
      update_task_status "$task_id" "comment" "✅ Agent completed task. Report: .beads-agent/results/$task_id.md"
      if [[ "$MARK_REVIEW" == "close" ]]; then
        update_task_status "$task_id" "close"
      fi
      ;;
    "REVIEW")
      update_task_status "$task_id" "comment" "👀 Agent requests review. Report: .beads-agent/results/$task_id.md"
      ;;
    "BLOCKED")
      update_task_status "$task_id" "comment" "🚧 Agent blocked. Check report for details."
      ;;
    "PARTIAL")
      update_task_status "$task_id" "comment" "📝 Agent made partial progress. See report for details."
      ;;
    *)
      update_task_status "$task_id" "comment" "❓ Agent finished without clear signal. Manual review needed."
      ;;
  esac
  
  echo "$signal"
}

# Show current status
show_status() {
  echo "═══════════════════════════════════════════════════════════════════"
  echo "📊 Beads-Agent Status"
  echo "═══════════════════════════════════════════════════════════════════"
  echo ""
  
  if [[ -f "$STATUS_FILE" ]]; then
    echo "Last Run:"
    cat "$STATUS_FILE" | jq '.'
    echo ""
  else
    echo "No runs yet."
    echo ""
  fi
  
  echo "Task Results:"
  if [[ -d "$TASK_RESULTS_DIR" ]] && ls "$TASK_RESULTS_DIR"/*.md &>/dev/null; then
    for f in "$TASK_RESULTS_DIR"/*.md; do
      local task_id=$(basename "$f" .md)
      echo "  - $task_id"
    done
  else
    echo "  (none)"
  fi
  echo ""
  
  echo "Ready Tasks:"
  bd ready 2>/dev/null | head -10
}

# =============================================================================
# MAIN
# =============================================================================

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--model)
      MODEL="$2"
      shift 2
      ;;
    -l|--loop)
      LOOP_MODE=true
      shift
      ;;
    -n|--max-iterations)
      MAX_ITERATIONS="$2"
      shift 2
      ;;
    --label)
      LABEL_FILTER="$2"
      shift 2
      ;;
    --epic)
      PARENT_FILTER="$2"
      # If just the suffix is provided, expand to full ID
      if [[ ! "$PARENT_FILTER" =~ ^open-crawler-config-generator- ]]; then
        PARENT_FILTER="open-crawler-config-generator-$PARENT_FILTER"
      fi
      # Also set label filter based on epic's labels (optional enhancement)
      shift 2
      ;;
    --no-tests)
      RUN_TESTS=false
      shift
      ;;
    --no-review)
      MARK_REVIEW=false
      shift
      ;;
    --close)
      MARK_REVIEW="close"
      shift
      ;;
    --list)
      LIST_ONLY=true
      shift
      ;;
    --status)
      STATUS_ONLY=true
      shift
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    -*)
      echo "Unknown option: $1"
      show_help
      exit 1
      ;;
    *)
      SPECIFIC_TASK="$1"
      shift
      ;;
  esac
done

# Initialize
init_agent_dir

# Status mode
if [[ "$STATUS_ONLY" == "true" ]]; then
  show_status
  exit 0
fi

# List mode
if [[ "$LIST_ONLY" == "true" ]]; then
  if [[ -n "$LABEL_FILTER" ]]; then
    echo "📋 Ready tasks with label '$LABEL_FILTER':"
    echo ""
    get_ready_tasks
  elif [[ -n "$PARENT_FILTER" ]]; then
    echo "📋 Ready tasks under epic '$PARENT_FILTER':"
    echo ""
    get_ready_tasks
  else
    echo "📋 Ready tasks (no blockers):"
    echo ""
    bd ready
  fi
  exit 0
fi

# Check prerequisites
if ! command -v bd &> /dev/null; then
  echo "❌ Beads CLI (bd) not found"
  echo "   Install from: https://steveyegge.github.io/beads/"
  exit 1
fi

if ! command -v cursor-agent &> /dev/null; then
  echo "❌ cursor-agent CLI not found"
  exit 1
fi

# Determine task to work on
if [[ -n "$SPECIFIC_TASK" ]]; then
  TASK_ID="$SPECIFIC_TASK"
else
  TASK_ID=$(get_next_task_id)
  if [[ -z "$TASK_ID" ]]; then
    echo "✅ No ready tasks! All tasks either complete or blocked."
    echo ""
    echo "Check status with: bd status"
    echo "List all tasks with: bd list"
    exit 0
  fi
fi

# Verify task exists
if ! bd show "$TASK_ID" &>/dev/null; then
  echo "❌ Task not found: $TASK_ID"
  echo ""
  echo "Available ready tasks:"
  bd ready
  exit 1
fi

# Show banner
echo "═══════════════════════════════════════════════════════════════════"
echo "🐛 Beads-Agent v2: Autonomous Task Runner"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "  Each iteration runs with fresh context (Ralph-style)."
echo "  Progress persists in git and Beads, not LLM memory."
if [[ -n "$LABEL_FILTER" ]]; then
  echo ""
  echo "  🏷️  Filtering by label: $LABEL_FILTER"
fi
if [[ -n "$PARENT_FILTER" ]]; then
  echo ""
  echo "  📦 Filtering by epic: $PARENT_FILTER"
fi
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Show task info
echo "📋 Selected Task:"
echo "───────────────────────────────────────────────────────────────────"
bd show "$TASK_ID"
echo "───────────────────────────────────────────────────────────────────"

# Check for linked OpenSpec
SPEC_FILE=$(get_openspec "$TASK_ID")
if [[ -n "$SPEC_FILE" ]]; then
  echo ""
  echo "📖 OpenSpec: $SPEC_FILE"
fi
echo ""

if [[ "$LOOP_MODE" == "true" ]]; then
  # Loop mode - run multiple iterations
  echo "🔄 Running in LOOP mode (max $MAX_ITERATIONS iterations)"
  echo ""
  
  iteration=1
  while [[ $iteration -le $MAX_ITERATIONS ]]; do
    # Check if there are still ready tasks
    TASK_ID=$(get_next_task_id)
    if [[ -z "$TASK_ID" ]]; then
      echo ""
      echo "═══════════════════════════════════════════════════════════════════"
      echo "🎉 All ready tasks complete!"
      echo "═══════════════════════════════════════════════════════════════════"
      exit 0
    fi
    
    signal=$(run_iteration "$TASK_ID" "$iteration")
    
    echo ""
    echo "───────────────────────────────────────────────────────────────────"
    echo "Iteration $iteration result: $signal"
    echo "───────────────────────────────────────────────────────────────────"
    
    # Run tests if enabled and task completed
    if [[ "$RUN_TESTS" == "true" ]] && [[ "$signal" == "COMPLETE" || "$signal" == "REVIEW" ]]; then
      run_tests "$WORKSPACE"
    fi
    
    case "$signal" in
      "COMPLETE")
        echo "✅ Task $TASK_ID completed!"
        ;;
      "REVIEW")
        echo "👀 Task $TASK_ID needs review"
        ;;
      "BLOCKED")
        echo "🚧 Task $TASK_ID is blocked. Moving to next ready task..."
        ;;
      *)
        echo "📝 Progress made on $TASK_ID"
        ;;
    esac
    
    iteration=$((iteration + 1))
    
    # Brief pause between iterations
    sleep 2
  done
  
  echo ""
  echo "⚠️  Max iterations ($MAX_ITERATIONS) reached."
  echo "   Run again to continue working on tasks."
  
else
  # Single iteration mode
  echo "Running single iteration..."
  echo ""
  
  signal=$(run_iteration "$TASK_ID" "1")
  
  # Run tests if enabled
  if [[ "$RUN_TESTS" == "true" ]] && [[ "$signal" == "COMPLETE" || "$signal" == "REVIEW" ]]; then
    run_tests "$WORKSPACE"
  fi
  
  echo ""
  echo "═══════════════════════════════════════════════════════════════════"
  echo "📋 Iteration Complete"
  echo "═══════════════════════════════════════════════════════════════════"
  echo ""
  echo "Result: $signal"
  
  # Show completion report if exists
  if [[ -f "$TASK_RESULTS_DIR/$TASK_ID.md" ]]; then
    echo ""
    echo "📄 Completion Report:"
    echo "───────────────────────────────────────────────────────────────────"
    head -30 "$TASK_RESULTS_DIR/$TASK_ID.md"
    echo "───────────────────────────────────────────────────────────────────"
  fi
  
  echo ""
  echo "Next steps:"
  echo "  • Review report: cat $TASK_RESULTS_DIR/$TASK_ID.md"
  echo "  • Review changes: git log --oneline -5"
  echo "  • Check output: cat $OUTPUT_LOG"
  echo "  • Run again: ./scripts/beads-agent.sh"
  echo "  • Loop mode: ./scripts/beads-agent.sh --loop"
  echo ""
fi
