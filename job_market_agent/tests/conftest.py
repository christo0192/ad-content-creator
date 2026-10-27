"""pytest setup for job_market_agent (added 2026-10-27).

The package is a flat set of top-level modules (`import config as C`), so put the
package dir on sys.path. market_research also has a top-level `config` module —
run each package's tests in its OWN pytest process (see .github/workflows/ci.yml).
"""
import os
import sys

import pytest

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PKG not in sys.path:
    sys.path.insert(0, PKG)

# Every env var that can point a test at a real secret / service.
SECRET_ENV = (
    "APIFY_TOKEN",
    "MARKET_RESEARCH_BQ_SA_B64", "IK_BQ_SERVICE_ACCOUNT_B64",
    "MARKET_RESEARCH_BQ_SA_JSON", "IK_BQ_SERVICE_ACCOUNT",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "JOBMKT_WINDOW_DAYS", "JOBMKT_WINDOW_START",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """Every test starts with no credentials at all (and the local key-file
    fallback pointed at a path that does not exist), so nothing can reach Apify
    or BigQuery even if a guard regresses. Tests set only what they need."""
    for k in SECRET_ENV:
        monkeypatch.delenv(k, raising=False)
    missing_key = str(tmp_path / "no-such-sa.json")
    monkeypatch.setenv("JOBMKT_BQ_KEY", missing_key)
    import config as C
    monkeypatch.setattr(C, "BQ_SA_KEY", missing_key)
    return monkeypatch
