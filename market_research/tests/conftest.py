"""pytest setup for market_research (added 2026-10-27).

The pipeline imports its modules top-level (`import config as C`, `import bq`,
`import agent_blog`), so put the package dir, shared/ and agents/ on sys.path.
job_market_agent also has a top-level `config` module — run each package's tests
in its OWN pytest process (see .github/workflows/ci.yml).
"""
import os
import sys

import pytest

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("", "shared", "agents"):
    p = os.path.join(PKG, sub) if sub else PKG
    if p not in sys.path:
        sys.path.insert(0, p)

# Every env var that can point a test at a real secret / service, or change
# which run_id / preflight branch a test sees.
SECRET_ENV = (
    "MARKET_RESEARCH_BQ_SA_B64", "IK_BQ_SERVICE_ACCOUNT_B64",
    "MARKET_RESEARCH_BQ_SA_JSON", "IK_BQ_SERVICE_ACCOUNT",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "APIFY_TOKEN",
    "FLY_APP_NAME", "MR_REQUIRE_LLM_TOKEN", "MR_CADENCE", "MR_RUN_ID",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """No credentials, the local key-file fallback pointed at a missing path, and
    the claude CLI pointed at a binary that does not exist — so an accidental
    LLM / BigQuery call fails fast instead of reaching a real service."""
    for k in SECRET_ENV:
        monkeypatch.delenv(k, raising=False)
    missing_key = str(tmp_path / "no-such-sa.json")
    monkeypatch.setenv("MR_BQ_KEY", missing_key)
    import config as C
    monkeypatch.setattr(C, "BQ_SA_KEY", missing_key)
    monkeypatch.setattr(C, "CLAUDE_BIN", str(tmp_path / "no-such-claude"))
    return monkeypatch
