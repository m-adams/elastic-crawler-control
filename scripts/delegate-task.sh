#!/bin/bash
# Delegate a task to cursor-agent and log output for monitoring
#
# Usage:
#   ./scripts/delegate-task.sh "Your task prompt here"
#   ./scripts/delegate-task.sh --model sonnet-4.5 "Your task prompt here"
#
# Monitor from Cursor:
#   - Output logged to: .delegate/output.log
#   - Status in: .delegate/status.json

set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DELEGATE_DIR="$WORKSPACE/.delegate"
OUTPUT_LOG="$DELEGATE_DIR/output.log"
STATUS_FILE="$DELEGATE_DIR/status.json"
STREAM_LOG="$DELEGATE_DIR/stream.jsonl"

# Defaults
MODEL="${RALPH_MODEL:-sonnet-4.5}"
OUTPUT_FORMAT="stream-json"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--model)
      MODEL="$2"
      shift 2
      ;;
    --text)
      OUTPUT_FORMAT="text"
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [options] \"prompt\""
      echo ""
      echo "Options:"
      echo "  -m, --model MODEL   Model to use (default: sonnet-4.5)"
      echo "  --text              Use text output format instead of stream-json"
      echo "  -h, --help          Show this help"
      echo ""
      echo "Available models:"
      cursor-agent --list-models 2>/dev/null || echo "  (run 'cursor-agent --list-models' to see)"
      exit 0
      ;;
    *)
      PROMPT="$1"
      shift
      ;;
  esac
done

if [[ -z "${PROMPT:-}" ]]; then
  echo "Error: No prompt provided"
  echo "Usage: $0 \"Your task prompt\""
  exit 1
fi

# Setup delegate directory
mkdir -p "$DELEGATE_DIR"
echo "# Delegate task output" > "$OUTPUT_LOG"
echo "" > "$STREAM_LOG"

# Write initial status
cat > "$STATUS_FILE" << EOF
{
  "status": "running",
  "started_at": "$(date -Iseconds)",
  "model": "$MODEL",
  "prompt": $(echo "$PROMPT" | jq -Rs .),
  "pid": $$,
  "workspace": "$WORKSPACE"
}
EOF

echo "═══════════════════════════════════════════════════════════════════"
echo "🚀 Delegating task to cursor-agent"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Model:     $MODEL"
echo "Workspace: $WORKSPACE"
echo "Output:    $OUTPUT_LOG"
echo "Status:    $STATUS_FILE"
echo ""
echo "Prompt:"
echo "───────────────────────────────────────────────────────────────────"
echo "$PROMPT"
echo "───────────────────────────────────────────────────────────────────"
echo ""

# Run cursor-agent
cd "$WORKSPACE"

if [[ "$OUTPUT_FORMAT" == "stream-json" ]]; then
  # Stream JSON mode - capture both stream and readable output
  cursor-agent -p --force --approve-mcps \
    --output-format stream-json \
    --model "$MODEL" \
    --workspace "$WORKSPACE" \
    "$PROMPT" 2>&1 | tee "$STREAM_LOG" | while IFS= read -r line; do
      # Parse stream-json and extract readable content
      if echo "$line" | jq -e '.type == "assistant-message"' > /dev/null 2>&1; then
        content=$(echo "$line" | jq -r '.content // empty')
        if [[ -n "$content" ]]; then
          echo "$content" >> "$OUTPUT_LOG"
          echo "$content"
        fi
      elif echo "$line" | jq -e '.type == "tool-use"' > /dev/null 2>&1; then
        tool=$(echo "$line" | jq -r '.tool // "unknown"')
        echo "[TOOL: $tool]" >> "$OUTPUT_LOG"
        echo "[TOOL: $tool]"
      elif echo "$line" | jq -e '.type == "error"' > /dev/null 2>&1; then
        error=$(echo "$line" | jq -r '.message // .error // "unknown error"')
        echo "[ERROR: $error]" >> "$OUTPUT_LOG"
        echo "[ERROR: $error]"
      fi
    done
  EXIT_CODE=${PIPESTATUS[0]}
else
  # Text mode - simple capture
  cursor-agent -p --force --approve-mcps \
    --output-format text \
    --model "$MODEL" \
    --workspace "$WORKSPACE" \
    "$PROMPT" 2>&1 | tee "$OUTPUT_LOG"
  EXIT_CODE=$?
fi

# Write final status
cat > "$STATUS_FILE" << EOF
{
  "status": "completed",
  "started_at": "$(jq -r '.started_at' "$STATUS_FILE")",
  "completed_at": "$(date -Iseconds)",
  "exit_code": $EXIT_CODE,
  "model": "$MODEL",
  "prompt": $(echo "$PROMPT" | jq -Rs .),
  "workspace": "$WORKSPACE"
}
EOF

echo ""
echo "═══════════════════════════════════════════════════════════════════"
if [[ $EXIT_CODE -eq 0 ]]; then
  echo "✅ Task completed successfully"
else
  echo "❌ Task failed with exit code: $EXIT_CODE"
fi
echo "═══════════════════════════════════════════════════════════════════"
