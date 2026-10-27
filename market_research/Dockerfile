# Market Research pipeline image (Social + Blog + Competitor + Exec Summary).
# Needs BOTH Python (pipeline) AND the Claude Code CLI (LLM calls via `claude -p`).
FROM python:3.12-slim

# NODE_VERSION 20 -> 24 and the CLI pinned (2026-10-27): the CLI was installed
# unpinned, so any rebuild could pull a release with different flags
# (llm.py relies on --model/--effort/--output-format). 2.1.311 was the current
# published version on 2026-10-27; it (like 2.1.240, current at the Aug-2026
# deploy) declares engines.node >=22, which Node 20 (EOL 2026-04) violates.
# Bump the pin deliberately, then re-run the --preflight smoke (DEPLOY_FLY.md §4).
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 NODE_VERSION=24 CLAUDE_CODE_VERSION=2.1.311

# Node + Claude Code CLI (for `claude -p`, Max-plan auth via CLAUDE_CODE_OAUTH_TOKEN)
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} \
 && apt-get purge -y gnupg && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/ ./agents/
COPY exec_summary.py run_weekly.py ./

# Runs once and exits -> a stopped Fly Machine that the Cloudflare Worker
# ik-intelligence-trigger starts monthly (no Fly --schedule). Exit 0 OK /
# 1 degraded run / 2 preflight failed. Smoke: --command "python run_weekly.py --preflight".
CMD ["python", "run_weekly.py"]
