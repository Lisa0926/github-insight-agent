# GitHub Insight Agent - Docker Image
# Usage:
#   docker build -t github-insight-agent .
#   docker run -it --env-file .env github-insight-agent

FROM python:3.12-slim

LABEL maintainer="Lisa"
LABEL description="Enterprise multi-agent intelligence analysis system for GitHub"

WORKDIR /app

# Install Node.js for MCP server (GitHub MCP requires npm)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip and install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Install MCP GitHub server
RUN npm install -g @modelcontextprotocol/server-github

# Copy application code
COPY . .

# Create persistent directories
RUN mkdir -p /app/data /app/reports /app/traces

# Prevent Python from buffering output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Health check (validates application code and dependencies)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=5s \
    CMD python -c "from src.core.config_manager import ConfigManager; from src.agents.base_agent import GiaAgentBase; exit(0)" || exit 1

# Entry point: interactive CLI
ENTRYPOINT ["python", "run_cli.py"]
CMD []
