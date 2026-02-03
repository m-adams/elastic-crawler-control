# Docker Setup for Open Crawler

> Extracted from hive-mind open-crawler guides
> Last Updated: 2026-02-02
> Version: Open Crawler 0.4.2

## Overview

Open Crawler runs as a Docker container. Proper setup is critical, especially for file output.

## Critical: Docker Compose Required for File Output

**Simple `docker run` commands often fail for file output.** Use docker-compose with separate volume mounts.

## Docker Compose Setup (Recommended)

### Complete docker-compose.yml

```yaml
# docker-compose.yml
version: '3.8'

services:
  crawler:
    image: docker.elastic.co/integrations/crawler:0.4.2
    volumes:
      # CRITICAL: Mount configs and results SEPARATELY
      - ./configs:/config/configs:ro
      - ./results:/config/results
    entrypoint: ["jruby"]
    command: ["bin/crawler", "--help"]
```

### Directory Structure

```
project/
├── docker-compose.yml    # Docker setup
├── .env                  # ES credentials (optional)
├── configs/              # Crawler configs (separate folder!)
│   ├── test.yml
│   ├── production.yml
│   └── extraction-test.yml
├── results/              # Output directory (separate folder!)
│   └── (JSON files appear here)
└── scripts/
    └── crawl.sh          # Helper scripts
```

### Why Separate Mounts?

- The crawler may have issues writing to subdirectories of mounted volumes
- Separate mounts ensure proper write permissions
- Read-only mount for configs prevents accidental modification

## Running Commands

### Validate Configuration

```bash
docker compose run --rm crawler bin/crawler validate /config/configs/test.yml
```

### Test Single URL

```bash
docker compose run --rm crawler bin/crawler urltest /config/configs/test.yml https://example.com
```

### Run Crawl

```bash
docker compose run --rm crawler bin/crawler crawl /config/configs/test.yml
```

### Debug Mode

```bash
docker compose run --rm crawler bin/crawler crawl /config/configs/test.yml --log-level debug
```

## File Output Configuration

### Correct Paths

```yaml
# ✅ CORRECT - Use container paths
output_sink: file
output_dir: /config/results/test  # Container path!

# ❌ WRONG - Don't use host paths
output_dir: ./results/test
output_dir: /Users/me/project/results
```

### Create Output Directory

```bash
mkdir -p results/test
```

### Check Output

```bash
ls -la results/test/
cat results/test/*.json | python3 -m json.tool
```

## Environment Variables

### Option 1: .env File (Recommended)

```bash
# .env
ES_HOST=https://your-cluster.es.cloud.com
ES_PORT=443
ES_API_KEY=your-api-key-here
```

```yaml
# docker-compose.yml
services:
  crawler:
    image: docker.elastic.co/integrations/crawler:0.4.2
    env_file:
      - .env
    volumes:
      - ./configs:/config/configs:ro
      - ./results:/config/results
    entrypoint: ["jruby"]
```

**Note**: Open Crawler doesn't support `${VAR}` substitution in configs. Use shell expansion instead.

### Option 2: Shell Expansion

```bash
# Set env vars
export ES_HOST="https://your-host.com"
export ES_API_KEY="your-key"

# Create config with shell expansion
cat > configs/crawler.yml << EOF
output_sink: elasticsearch
output_index: my-index

elasticsearch:
  host: $ES_HOST
  api_key: $ES_API_KEY

domains:
  - url: https://example.com
    seed_urls:
      - https://example.com/
EOF
```

## Permissions Issues

### Problem: Permission Denied

```bash
# Check permissions
ls -la results/

# Fix permissions
chmod -R 755 results/
```

### macOS Specific

- Check Docker Desktop > Settings > Resources > File Sharing
- Ensure project directory is in allowed paths

### Linux Specific

- SELinux may block volume mounts
- Try with `:z` flag: `./results:/config/results:z`

### Windows Specific

- WSL2 recommended over Hyper-V
- Use Linux-style paths in configs

## Alternative: Simple docker run

**Not recommended for file output**, but works for console/ES:

```bash
# Console output
docker run --rm \
  -v "$(pwd)/configs:/config:ro" \
  docker.elastic.co/integrations/crawler:0.4.2 \
  jruby bin/crawler crawl /config/test.yml

# With environment variables
docker run --rm \
  -v "$(pwd)/configs:/config:ro" \
  -e ES_HOST="https://your-host" \
  -e ES_API_KEY="your-key" \
  docker.elastic.co/integrations/crawler:0.4.2 \
  jruby bin/crawler crawl /config/test.yml
```

## Helper Scripts

### Simple Wrapper

```bash
#!/bin/bash
# crawl.sh - Helper script for common operations

COMPOSE="docker compose run --rm crawler"
CONFIG_DIR="/config/configs"

case "$1" in
  validate)
    $COMPOSE bin/crawler validate $CONFIG_DIR/"$2"
    ;;
  test-url)
    $COMPOSE bin/crawler urltest $CONFIG_DIR/"$2" "$3"
    ;;
  crawl)
    $COMPOSE bin/crawler crawl $CONFIG_DIR/"$2"
    ;;
  check-output)
    ls -la results/"$2"/*.json 2>/dev/null || echo "No files found"
    ;;
  *)
    echo "Usage: $0 {validate|test-url|crawl|check-output} config-name [url]"
    echo "Examples:"
    echo "  $0 validate test.yml"
    echo "  $0 test-url test.yml https://example.com"
    echo "  $0 crawl test.yml"
    echo "  $0 check-output test-results"
    ;;
esac
```

Usage:
```bash
chmod +x crawl.sh
./crawl.sh validate test.yml
./crawl.sh crawl production.yml
./crawl.sh check-output my-crawl
```

## Image Management

### Pull Latest Image

```bash
docker pull docker.elastic.co/integrations/crawler:0.4.2
```

### Check Current Version

```bash
docker compose run --rm crawler bin/crawler --version
```

### Clean Up

```bash
# Remove stopped containers
docker compose down

# Remove volumes
docker compose down -v
```

## Troubleshooting

### Problem: "env file not found"

```bash
# Create empty .env if not using environment variables
touch .env
```

### Problem: File Output Not Working

Checklist:
- [ ] Using docker-compose (not plain docker run)
- [ ] Configs and results mounted as separate volumes
- [ ] output_dir uses container path (/config/...)
- [ ] Results directory exists and is writable
- [ ] max_crawl_depth ≥ 1 (NOT 0)

See: [File Output Troubleshooting](../troubleshooting/file-output-issues.md)

### Problem: "Cannot connect to Docker daemon"

```bash
# Start Docker Desktop
open -a Docker  # macOS

# Or start Docker service
sudo systemctl start docker  # Linux
```

### Problem: Volume Mount Issues

```yaml
# Try absolute paths
services:
  crawler:
    volumes:
      - /absolute/path/to/configs:/config/configs:ro
      - /absolute/path/to/results:/config/results
```

## Production Considerations

### Resource Limits

```yaml
# docker-compose.yml
services:
  crawler:
    image: docker.elastic.co/integrations/crawler:0.4.2
    volumes:
      - ./configs:/config/configs:ro
      - ./results:/config/results
    entrypoint: ["jruby"]
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

### Logging

```yaml
services:
  crawler:
    image: docker.elastic.co/integrations/crawler:0.4.2
    volumes:
      - ./configs:/config/configs:ro
      - ./results:/config/results
      - ./logs:/logs
    entrypoint: ["jruby"]
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Restart Policy

```yaml
services:
  crawler:
    image: docker.elastic.co/integrations/crawler:0.4.2
    restart: unless-stopped
    volumes:
      - ./configs:/config/configs:ro
      - ./results:/config/results
    entrypoint: ["jruby"]
```

## Scheduling Crawls

### Using cron (Linux/macOS)

```bash
# crontab -e
# Run daily at 2 AM
0 2 * * * cd /path/to/project && docker compose run --rm crawler bin/crawler crawl /config/configs/daily.yml >> logs/crawl.log 2>&1
```

### Using systemd Timer (Linux)

```ini
# /etc/systemd/system/crawler.service
[Unit]
Description=Open Crawler Service
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=/path/to/project
ExecStart=/usr/local/bin/docker compose run --rm crawler bin/crawler crawl /config/configs/production.yml

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/crawler.timer
[Unit]
Description=Open Crawler Timer
Requires=crawler.service

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
# Enable and start timer
sudo systemctl enable crawler.timer
sudo systemctl start crawler.timer
sudo systemctl status crawler.timer
```

## Related Documents

- [Base Configuration](../config-structure/base-config.md)
- [Testing Workflow](./testing-workflow.md)
- [File Output Troubleshooting](../troubleshooting/file-output-issues.md)
- [Common Errors](../troubleshooting/common-errors.md)
