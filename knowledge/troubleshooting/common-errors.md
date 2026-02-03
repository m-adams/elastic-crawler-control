# Common Errors and Solutions

> Extracted from hive-mind open-crawler guides
> Last Updated: 2026-02-02
> Version: Open Crawler 0.4.2

## Quick Diagnostics

```bash
# Validate configuration
docker compose run --rm crawler bin/crawler validate /config/configs/test.yml

# Test single URL (fastest debugging)
docker compose run --rm crawler bin/crawler urltest /config/configs/test.yml https://example.com

# Run with debug logging
docker compose run --rm crawler bin/crawler crawl /config/configs/test.yml --log-level debug
```

## Configuration Errors

### "Unexpected configuration options: [:http]"

**Cause**: Using v0.1 config format with v0.4 crawler

**Fix**: Settings are top-level, not nested under `http:`

```yaml
# ❌ WRONG (v0.1 format)
http:
  user_agent: "MyCrawler"
  request_timeout: 30

# ✅ CORRECT (v0.4 format)
user_agent: "MyCrawler"
request_timeout: 30
max_crawl_depth: 2
```

### "Domain cannot have a path"

**Cause**: Trailing slash or path in domain URL

**Fix**: Remove path from domain, use seed_urls instead

```yaml
# ❌ WRONG
domains:
  - url: https://example.com/
  - url: https://example.com/blog

# ✅ CORRECT
domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/
      - https://example.com/blog
```

### "Extraction rule join_as is invalid"

**Cause**: Missing required `join_as` field

**Fix**: Add `join_as` to every extraction rule

```yaml
# ❌ WRONG
- action: extract
  field_name: author
  selector: ".author"
  source: html

# ✅ CORRECT
- action: extract
  field_name: author
  selector: ".author"
  source: html
  join_as: string  # or 'array'
```

### "Extraction ruleset url_filter `equals` is invalid"

**Cause**: Using `equals` filter type in extraction rules (only valid in crawl_rules)

**Fix**: Use `regex` with `^pattern$` for exact matching

```yaml
# ❌ WRONG
extraction_rulesets:
  - url_filters:
      - type: equals
        pattern: /about

# ✅ CORRECT
extraction_rulesets:
  - url_filters:
      - type: regex
        pattern: "^/about$"
```

**Valid extraction URL filter types**: `begins`, `ends`, `contains`, `regex`

### "bad URI(is not URI?): \"${ES_HOST}\""

**Cause**: Open Crawler doesn't support `${VAR}` substitution in configs

**Fix**: Use shell expansion when creating config

```bash
# Set env vars
export ES_HOST="https://your-host.com"
export ES_API_KEY="your-key"

# Create config with shell expansion
cat > configs/crawler.yml << EOF
elasticsearch:
  host: $ES_HOST
  api_key: $ES_API_KEY
EOF
```

## Connection Errors

### Cannot connect to Elasticsearch

**Symptoms**: Connection refused, timeout, or authentication errors

**Checklist**:
- [ ] ES_HOST includes protocol (`https://`)
- [ ] ES_PORT correct (443 for cloud, 9200 for local)
- [ ] API key valid and not expired
- [ ] For local ES from Docker: use `host.docker.internal` not `localhost`

```yaml
# ✅ Correct format
elasticsearch:
  host: "https://your-deployment.es.region.cloud.es.io"
  port: 443
  api_key: "your_base64_encoded_api_key"
  ssl:
    enabled: true
```

### Timeout errors (status 599)

**Symptoms**: `java.net.SocketTimeoutException: Read timed out`

**Fix**: Increase timeout settings

```yaml
request_timeout: 60   # Overall request timeout (increase this)
connect_timeout: 10   # Connection establishment
socket_timeout: 10    # Socket read timeout
```

### Index not found

**Symptoms**: `index_not_found_exception`

**Fix**: Create index before crawling

```bash
curl -X PUT "https://your-es-host/your-index" \
  -H "Authorization: ApiKey YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d @your-mapping.json
```

## Crawl Issues

### Pages not being crawled

**Symptoms**: `pages_visited: 0` or very low count

**Checklist**:
- [ ] Check robots.txt isn't blocking (`log_level: debug` shows this)
- [ ] Verify `crawl_rules` allow the URL pattern
- [ ] Ensure `max_crawl_depth` is sufficient (must be ≥1)
- [ ] Check if URL is external to the domain
- [ ] Verify site is accessible (not behind CAPTCHA/auth)

### No files created (file output)

**Symptoms**: Crawler reports success but results directory is empty

**Common Causes**:

1. **max_crawl_depth: 0** (MOST COMMON)
   ```yaml
   # ❌ WRONG - no files created
   max_crawl_depth: 0
   
   # ✅ CORRECT
   max_crawl_depth: 1  # Minimum for file output
   ```

2. **Wrong Docker setup**
   - Not using docker-compose
   - Configs and results not mounted separately
   - See [Docker Setup](../patterns/docker-setup.md)

3. **Wrong output path**
   ```yaml
   # ❌ WRONG - host path
   output_dir: ./results
   
   # ✅ CORRECT - container path
   output_dir: /config/results/test
   ```

See: [File Output Troubleshooting](./file-output-issues.md)

### Extracted fields not appearing

**Problem**: You're using console output - it shows raw HTML, not structured fields

**Fix**: Use file output to see extracted fields

```yaml
output_sink: file
output_dir: /config/results/test
```

Then inspect JSON:
```bash
cat results/test/*.json | python3 -m json.tool
cat results/test/*.json | jq '.your_custom_field'
```

### Content missing from documents

**Possible causes**:

1. **JavaScript-rendered content**
   - Open Crawler doesn't execute JS
   - Check: `curl -s URL | grep "expected content"`
   - If not found, content is JS-rendered

2. **Content behind authentication**
   - Only basic auth supported
   - Most login forms won't work

3. **Extraction selectors don't match**
   - Test selectors in browser console
   - Use file output to debug
   - Start with simple selectors

### Empty or minimal body content

**Symptoms**: Body field empty or only contains navigation

**Cause**: Site uses JavaScript to render content

**How to tell**:
```bash
# View raw HTML without JS
curl -s 'https://example.com' | grep -i "your expected content"
# If content not found, it's JS-rendered
```

**Solutions**:
1. Find server-rendered versions (mobile site, AMP pages, RSS feeds)
2. Check for site APIs
3. Use headless browser (Playwright, Puppeteer)
4. Use pre-rendering service

See: [JavaScript Rendering Issues](./javascript-rendering.md)

## Bot Protection Issues

### All requests return 403 Forbidden

**Symptoms**:
- Status code 403 on all pages
- Response contains "Checking your browser..." or CAPTCHA
- First request works, subsequent blocked

**Quick check**:
```bash
curl -sI -A "Mozilla/5.0" 'https://target-site.com' | head -5
```

**Workarounds** (in order):

1. **Check for unprotected alternatives**:
   ```bash
   # Sitemaps often accessible
   curl -s "https://example.com/sitemap.xml"
   
   # RSS feeds
   curl -s "https://example.com" | grep -i "rss\|feed"
   ```

2. **Python cloudscraper** (Cloudflare only):
   ```python
   import cloudscraper
   scraper = cloudscraper.create_scraper()
   response = scraper.get('https://cloudflare-site.com')
   ```

3. **Contact site owner** - request API access or crawler whitelist

**Note**: Cloudflare headers don't always mean blocking. Test actual response.

## Extraction Issues

### Selectors not matching

**Debug steps**:

1. **Test in browser console**:
   ```javascript
   document.querySelectorAll('h1')
   document.querySelector('.author')?.textContent
   ```

2. **Start simple**:
   ```yaml
   # Single field, no URL filters
   extraction_rulesets:
     - rules:
         - action: extract
           field_name: test_h1
           selector: "h1"
           source: html
           join_as: string
   ```

3. **Check file output** (not console):
   ```bash
   cat results/test/*.json | jq '.test_h1'
   ```

4. **Add complexity gradually**:
   - First: basic selector
   - Then: more specific selector
   - Finally: URL filters

### URL filters not matching

**Debug approach**:

1. Remove `url_filters` entirely
2. Verify extraction works on all pages
3. Add filters back one at a time

```yaml
# Start without filters
extraction_rulesets:
  - rules:  # No url_filters
      - action: extract
        field_name: test
        selector: "h1"
        source: html
        join_as: string

# Then add filters
extraction_rulesets:
  - url_filters:
      - type: begins
        pattern: /blog/
    rules:
      - action: extract
        field_name: test
        selector: "h1"
        source: html
        join_as: string
```

## Docker Issues

### "env file not found"

**Fix**: Create `.env` file (even if empty)

```bash
touch .env
# or
cp .env.example .env
```

### Volume permissions

**Fix**: Ensure directories exist and are writable

```bash
mkdir -p results configs
chmod -R 755 results configs
```

### Cannot connect to Docker daemon

**Fix**: Start Docker Desktop or service

```bash
# macOS
open -a Docker

# Linux
sudo systemctl start docker
```

## Performance Issues

### Crawl is very slow

**Checklist**:
- [ ] Network latency to target site
- [ ] Large binary files being downloaded
- [ ] Timeout values too high
- [ ] Site has rate limiting

**Fix**: Adjust timeouts

```yaml
request_timeout: 30  # Reduce if needed
max_response_size: 10485760  # Limit response size
```

### Bulk Index Timeout (Elasticsearch)

**Symptoms**: `Net::ReadTimeout` or `Faraday::TimeoutError` during indexing

**Causes**:
1. ELSER inference slow for large text
2. Local model needs warm-up
3. Document body too large for semantic processing

**Solutions**:

1. **Use Elastic Inference Service** (`.elser-2-elastic` - no cold start)
2. **Only copy small fields to semantic_text**:
   ```json
   "title": {
     "type": "text",
     "copy_to": "semantic_content"  // ✅ Small
   },
   "body": {
     "type": "text"  // ❌ Don't copy - too large
   }
   ```
3. **Test inference before indexing**:
   ```bash
   curl -X POST "https://your-es/_inference/sparse_embedding/.elser-2-elastic" \
     -H "Authorization: ApiKey YOUR_KEY" \
     -d '{"input": "test query"}'
   ```

## Debug Logging

Enable detailed logging for troubleshooting:

```yaml
log_level: debug
```

Debug output shows:
- Full config dump at startup
- Each URL added to queue
- Crawl rules evaluation
- HTTP execution progress
- Connection pool stats
- Extraction attempts

## Status Code Reference

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | ✅ Normal |
| 301/302 | Redirect | ✅ Followed automatically |
| 403 | Forbidden | ⚠️ Check bot protection |
| 404 | Not found | ⚠️ Logged, crawl continues |
| 429 | Rate limited | ⚠️ Slow down requests |
| 500 | Server error | ⚠️ Temporary, retry |
| 599 | Timeout | ⚠️ Increase `request_timeout` |

## Crawl Stats Interpretation

```text
urls_denied={:rule_engine_denied=>199, :already_seen=>92, :link_too_deep=>136}
```

| Stat | Meaning | Action |
|------|---------|--------|
| `pages_visited` | Successfully crawled | ✅ Good |
| `rule_engine_denied` | Blocked by crawl rules | Check rules if unexpected |
| `already_seen` | Deduplicated URLs | Normal |
| `link_too_deep` | Exceeded `max_crawl_depth` | Increase depth if needed |
| `domain_filter` | Different domain | Expected for external links |

## Quick Fixes Reference

| Error | Fix |
|-------|-----|
| `Unexpected configuration options: [:http]` | Use v0.4 flat format |
| `Domain cannot have a path` | Remove trailing slash |
| `join_as is invalid` | Add `join_as: array` or `string` |
| `url_filter equals is invalid` | Use `regex` instead |
| `bad URI: "${ES_HOST}"` | Use shell expansion |
| Extraction fields not appearing | Use file output, not console |
| Empty body content | Site is JS-rendered |
| Timeout (599) | Increase `request_timeout` |
| 403 Forbidden | Check bot protection |
| No files created | Check `max_crawl_depth` ≥ 1 |

## Getting Help

1. Check [Open Crawler GitHub Issues](https://github.com/elastic/crawler/issues)
2. Review [Official Documentation](https://github.com/elastic/crawler)
3. Enable debug logging and check output
4. Validate config with `bin/crawler validate`

## Related Documents

- [File Output Troubleshooting](./file-output-issues.md)
- [Validation Checklist](../validation-rules/validation-checklist.md)
- [Docker Setup](../patterns/docker-setup.md)
- [Testing Workflow](../patterns/testing-workflow.md)
