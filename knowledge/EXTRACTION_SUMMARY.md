# Knowledge Base Extraction Summary

> Task: Phase 1.2 - Ingest hive-mind Knowledge
> Completed: 2026-02-02
> Issue: open-crawler-config-generator-9l3

## Source Documents Processed

Extracted knowledge from 11 open-crawler guides in elastic/hive-mind:

### Pattern Documents
1. `patterns/elastic/open-crawler-complete-guide.md` - Complete implementation guide
2. `patterns/elastic/open-crawler-configs.md` - Configuration patterns
3. `patterns/elastic/open-crawler-extraction.md` - Extraction rules cookbook
4. `patterns/elastic/open-crawler-extraction-patterns.md` - Reusable selector patterns
5. `patterns/elastic/open-crawler-extraction-testing.md` - Testing guide
6. `patterns/elastic/open-crawler-elasticsearch.md` - ES integration
7. `patterns/elastic/open-crawler-fast-iteration.md` - Fast workflow patterns
8. `patterns/elastic/open-crawler-quickstart.md` - Quick start guide
9. `patterns/elastic/open-crawler-reference.md` - Reference card

### Troubleshooting Documents
10. `troubleshooting/open-crawler-common-issues.md` - Common issues
11. `troubleshooting/open-crawler-file-output-issues.md` - File output problems

## Knowledge Base Structure

Created organized knowledge base in `knowledge/` directory:

```
knowledge/
├── README.md                                    # Index and quick reference
├── config-structure/
│   └── base-config.md                          # Core configuration format
├── extraction-rules/
│   ├── extraction-basics.md                    # Extraction fundamentals
│   └── extraction-patterns.md                  # Reusable selector patterns
├── validation-rules/
│   ├── crawl-rules.md                          # URL crawl control
│   └── validation-checklist.md                 # Config validation rules
├── patterns/
│   ├── testing-workflow.md                     # Fast iteration workflow
│   └── docker-setup.md                         # Docker configuration
└── troubleshooting/
    └── common-errors.md                        # Error reference

Total: 9 documents, 3,565 lines
```

## Key Patterns Extracted

### 1. Configuration Structure
- **Format**: v0.4 flat structure (NOT nested)
- **Critical rules**: Domain URL without path, no env var substitution
- **Output sinks**: console, file, elasticsearch
- **Reserved field names**: List of auto-generated fields to avoid

### 2. Extraction Rules
- **Critical requirement**: `join_as` is REQUIRED on all extraction rules
- **URL filter types**: Different support in crawl_rules vs extraction_rulesets
- **Common patterns**: 60+ reusable selector patterns for:
  - Dates, authors, prices, ratings
  - Categories, tags, content
  - E-commerce, blogs, documentation
  - Real estate, job listings

### 3. Validation Rules
- **Crawl rules**: Pattern types, evaluation order, common patterns
- **Config validation**: Required fields, value constraints, error messages
- **Testing commands**: validate, urltest, crawl workflows

### 4. Workflow Patterns
- **Fast iteration**: urltest → validate → console → file → ES
- **Anti-patterns**: Starting with ES, skipping validation, using console for extraction
- **Docker setup**: Critical docker-compose requirements for file output

### 5. Troubleshooting
- **Common errors**: 15+ error types with causes and fixes
- **Quick diagnostics**: Validation commands, debug logging
- **Issue categories**: Config, connection, crawl, extraction, docker, performance

## Critical Rules Documented

1. **Config format is flat** (v0.4+) - no nested `http:` block
2. **`join_as` is REQUIRED** - every extraction rule must have it
3. **File output requires `max_crawl_depth` ≥ 1** - NOT 0
4. **No environment variable substitution** - use shell expansion
5. **Domain URL must not have path** - use seed_urls instead
6. **URL filter `equals` not supported** in extraction_rulesets - use regex
7. **Reserved field names** - never use auto-generated field names

## Usage for Agents

### Config Generation Agent
- **Primary docs**: base-config.md, extraction-basics.md, extraction-patterns.md
- **Use patterns**: 60+ tested selector patterns
- **Validate against**: validation-checklist.md

### Site Investigation Agent
- **Primary docs**: extraction-patterns.md, testing-workflow.md
- **Test workflow**: urltest → console → file
- **Selector library**: Common patterns by content type

### Config Validation Agent
- **Primary docs**: validation-checklist.md, common-errors.md
- **Check against**: Critical validation rules
- **Error mapping**: Common errors to fixes

## Statistics

- **Source files**: 11 markdown documents
- **Knowledge docs**: 9 structured documents
- **Total lines**: 3,565 lines of documentation
- **Patterns extracted**: 60+ reusable selector patterns
- **Error mappings**: 15+ common errors with solutions
- **Validation rules**: 7 critical rules, 20+ field validations
- **Workflow steps**: 6-step fast iteration workflow

## Integration Points

Knowledge base designed to integrate with:

1. **Config Generation Agent** (Phase 2.2)
   - Provides structure templates
   - Supplies tested selector patterns
   - Defines validation rules

2. **Site Investigation Agent** (Phase 2.1)
   - Selector pattern library
   - Testing workflow
   - Common extraction patterns

3. **Config Validation** (Phase 2.3)
   - Validation checklist
   - Error detection
   - Quick fixes

4. **Testing Workflow** (Phase 3.3)
   - Fast iteration pattern
   - Docker setup
   - Debug procedures

## Next Steps

This knowledge base blocks:
- **open-crawler-config-generator-b0t**: Phase 2.2: Config Generation Agent

The Config Generation Agent can now:
1. Reference structured patterns
2. Use tested selector patterns
3. Validate against rules
4. Generate valid configs following best practices

## Verification

Knowledge base includes:
- ✅ Complete config structure documentation
- ✅ Extraction rule patterns (60+ selectors)
- ✅ Validation rules and constraints
- ✅ Fast iteration workflow
- ✅ Docker setup requirements
- ✅ Common error mappings
- ✅ Quick reference guides
- ✅ Cross-referenced documents
- ✅ Use case examples

All patterns extracted from battle-tested hive-mind guides.
