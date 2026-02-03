# File Output Issues

> Common problems when using `output_sink: file` in Open Crawler

## Critical Requirements

### 1. max_crawl_depth Must Be ≥ 1

```yaml
# ❌ WRONG - No files will be created
output_sink: file
max_crawl_depth: 0

# ✅ CORRECT
output_sink: file
max_crawl_depth: 1
```

**Why**: With `max_crawl_depth: 0`, the crawler only processes seed URLs but doesn't follow links or create output files.

### 2. output_dir Must Be Container Path

```yaml
# ❌ WRONG - Host path doesn't work inside container
output_dir: ./results

# ✅ CORRECT - Use container path
output_dir: /config/results/test
```

### 3. Docker Volume Must Be Mounted Separately

```yaml
# docker-compose.yml
services:
  crawler:
    volumes:
      # ❌ WRONG - Single mount for everything
      - .:/config
      
      # ✅ CORRECT - Separate mounts
      - ./configs:/config/configs:ro
      - ./results:/config/results
```

**Why**: Config files should be read-only, results need write access.

## Common Problems

### No Files Created

**Symptoms**: Crawl completes but no JSON files in output directory

**Checklist**:
1. [ ] `max_crawl_depth` is ≥ 1
2. [ ] `output_dir` uses container path (e.g., `/config/results/`)
3. [ ] Docker volume is mounted correctly
4. [ ] Directory exists and is writable

**Debug**:
```bash
# Check if crawler can write
docker compose run --rm crawler ls -la /config/results/

# Run with debug logging
docker compose run --rm crawler bin/crawler crawl /config/config.yml --log-level debug
```

### Permission Denied

**Symptoms**: Error writing to output directory

**Fix**:
```bash
# Ensure host directory exists and is writable
mkdir -p ./results
chmod 755 ./results
```

### Files Created But Empty

**Symptoms**: JSON files exist but are 0 bytes

**Causes**:
1. Extraction rules failed (check for `join_as` requirement)
2. Selectors didn't match any content
3. URL filters excluded all pages

**Debug**:
```bash
# Test extraction on single URL first
docker compose run --rm crawler bin/crawler urltest /config/config.yml https://example.com/page
```

### Wrong Output Location

**Symptoms**: Can't find output files

**Check**:
```bash
# See where files actually went
docker compose run --rm crawler find /config -name "*.json" 2>/dev/null

# Output path in config
grep output_dir /path/to/config.yml
```

## Recommended Setup

### Directory Structure

```
project/
├── docker-compose.yml
├── configs/
│   └── site-config.yml
└── results/
    └── (output files appear here)
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  crawler:
    image: docker.elastic.co/integrations/crawler:0.4.2
    volumes:
      - ./configs:/config/configs:ro
      - ./results:/config/results
    entrypoint: ["jruby"]
```

### config.yml

```yaml
output_sink: file
output_dir: /config/results/test
max_crawl_depth: 1

domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/page
    extraction_rulesets:
      - rules:
          - action: extract
            field_name: page_title
            selector: "h1"
            source: html
            join_as: string
```

### Run Command

```bash
docker compose run --rm crawler bin/crawler crawl /config/configs/site-config.yml
```

## Testing File Output

### Step-by-Step

1. **Verify config**:
   ```bash
   docker compose run --rm crawler bin/crawler validate /config/configs/test.yml
   ```

2. **Test single URL**:
   ```bash
   docker compose run --rm crawler bin/crawler urltest /config/configs/test.yml https://example.com
   ```

3. **Run crawl**:
   ```bash
   docker compose run --rm crawler bin/crawler crawl /config/configs/test.yml
   ```

4. **Check output**:
   ```bash
   ls -la ./results/
   cat ./results/*.json | jq '.'
   ```

## Related Documents

- [Docker Setup](../patterns/docker-setup.md)
- [Testing Workflow](../patterns/testing-workflow.md)
- [Common Errors](./common-errors.md)
