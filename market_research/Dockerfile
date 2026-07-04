# Weekly Market Research pipeline image (Social + Blog + Competitor + Exec Summary).
# Needs BOTH Python (pipeline) AND the Claude Code CLI (LLM calls via `claude -p`).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 NODE_VERSION=20

# Node + Claude Code CLI (for `claude -p`, Max-plan auth via CLAUDE_CODE_OAUTH_TOKEN)
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && npm install -g @anthropic-ai/claude-code \
 && apt-get purge -y gnupg && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/ ./agents/
COPY exec_summary.py run_weekly.py ./

# Runs once and exits -> Fly scheduled Machine (--schedule weekly).
CMD ["python", "run_weekly.py"]
