# Beads Workflow Overview

This document provides an overview of the workflow tasks tracked in Beads for the Open Crawler Config Generator project.

## Workflow Phases (Sequential)

The main workflow follows this sequence:

1. **Phase 1: Initial Validation & Setup** (`open-crawler-config-generator-6dn`)
   - Validate form input
   - Perform connectivity checks
   - Fetch robots.txt
   - Detect bot protection
   - **Status**: Ready (no blockers)

2. **Phase 2: Site Investigation** (`open-crawler-config-generator-p5a`)
   - Parse robots.txt and sitemaps
   - Fetch 10+ sample pages
   - Analyze page structure
   - Identify content patterns
   - **Status**: Blocked by Phase 1

3. **Phase 3: User Confirmation - Investigation Results** (`open-crawler-config-generator-m8o`)
   - Present investigation findings
   - Wait for user confirmation
   - **Status**: Blocked by Phase 2

4. **Phase 4: Config Generation** (`open-crawler-config-generator-b0t`)
   - Generate Open Crawler YAML config
   - Create crawl_rules and extraction_rulesets
   - Use hive-mind patterns
   - **Status**: Blocked by Phase 3 (also needs Phase 1.2: hive-mind knowledge)

5. **Phase 5: User Confirmation - Config Preview** (`open-crawler-config-generator-btq`)
   - Show draft config preview
   - "Your end document will look like..."
   - Wait for user confirmation
   - **Status**: Blocked by Phase 4

6. **Phase 6: Config Validation** (`open-crawler-config-generator-0z9`)
   - Schema validation
   - Test extraction rules (10+ pages)
   - Test crawl rules
   - Generate validation report
   - **Status**: Blocked by Phase 5

7. **Phase 7: Iteration Loop** (`open-crawler-config-generator-wfd`)
   - Automatic iteration on validation failures
   - Max 3 iterations
   - **Status**: Blocked by Phase 6

8. **Phase 8: Final Output** (`open-crawler-config-generator-mzg`)
   - Output validated config as YAML
   - Download/copy options
   - Next steps
   - **Status**: Blocked by Phase 7

9. **Orchestrator** (`open-crawler-config-generator-fdj`)
   - Coordinates all workflow phases
   - Manages state and SSE streaming
   - Handles user confirmations
   - **Status**: Blocked by Phase 8

## Supporting Tasks

### Phase 1.2: Ingest hive-mind Knowledge (`open-crawler-config-generator-9l3`)
- Extract Open Crawler patterns from hive-mind
- Create knowledge base
- **Status**: Ready (needed by Phase 4)

### UI Tasks (Can be done in parallel)
- **Phase 3.1: Chat Interface** (`open-crawler-config-generator-8oe`) - Blocked by Orchestrator
- **Phase 3.2: Config Preview & Export** (`open-crawler-config-generator-2u9`) - Ready
- **Phase 3.3: Config Testing Workflow** (`open-crawler-config-generator-d6s`) - Ready

## Quick Commands

```bash
# See what's ready to work on
bd ready

# See what's blocked
bd blocked

# View a specific task
bd show <task-id>

# List all open tasks
bd list --status open

# View workflow chain
bd list --status open | grep "Phase"
```

## Next Steps for Handoff

1. **Start with ready tasks**:
   - Phase 1.2: Ingest hive-mind Knowledge
   - Phase 1: Initial Validation & Setup
   - Phase 3.2 & 3.3: UI components (can be done in parallel)

2. **Then follow the workflow chain**:
   - Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8 → Orchestrator

3. **Reference specs**:
   - Detailed workflow: `openspec/specs/workflow-detailed/spec.md`
   - Input form: `openspec/specs/workflow-input/spec.md`
   - Individual agent specs in `openspec/specs/`

## Current Dependency Issues

⚠️ **NOTE**: There's a dependency issue that needs fixing:
- Phase 1 (6dn) incorrectly depends on Phase 2.1 (p5a) - this is backwards
- Phase 1 should come BEFORE Phase 2.1
- **To fix**: Remove the dependency from Phase 1, then add: `bd dep add open-crawler-config-generator-p5a open-crawler-config-generator-6dn -t blocks`

Also note:
- Phase 3 (m8o) depends on Phase 4 (b0t) - should depend on Phase 2 instead
- Phase 5 (btq) depends on Phase 6 (0z9) - should depend on Phase 4 instead  
- Phase 7 (wfd) depends on Orchestrator (fdj) - should depend on Phase 6 instead
- Phase 8 (mzg) depends on UI (8oe) - should depend on Phase 7 instead

**Correct workflow chain should be**:
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8 → Orchestrator

## Notes

- All workflow phases have detailed descriptions in beads
- Dependencies need to be fixed (see above)
- Use `bd ready` to see what can be worked on immediately
- The orchestrator coordinates all phases but depends on them being implemented first
- Phase 1.2 (hive-mind knowledge) is needed by Phase 4 and can be done in parallel with Phase 1
