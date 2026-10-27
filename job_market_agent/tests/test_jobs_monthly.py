"""Offline tests for the monthly job-market agent (added 2026-10-27).

No network, no secrets: Apify (fetch_live) and BigQuery (_client) are replaced
with fakes, and conftest.clean_env strips every credential env var.

  python -m pytest -q job_market_agent/tests     # its own process (see conftest)
"""
import base64
import glob
import importlib
import json
import os
import re
import sys
from datetime import timedelta

import pytest

import config as C
import bigquery_writer as BW
import run_monthly as RM
from google.cloud import bigquery

FAKE_SA_B64 = base64.b64encode(json.dumps({"type": "service_account"}).encode()).decode()


# ---------------------------------------------------------------------------
# helpers / fakes
# ---------------------------------------------------------------------------
@pytest.fixture
def reload_config(monkeypatch):
    """Reload config under the test's env, then restore the defaults afterwards
    (reload mutates the module object every other module imported as C)."""
    yield lambda: importlib.reload(C)
    monkeypatch.delenv("JOBMKT_WINDOW_DAYS", raising=False)
    monkeypatch.delenv("JOBMKT_WINDOW_START", raising=False)
    importlib.reload(C)


class _Job:
    def __init__(self, rows=None, exc=None):
        self._rows, self._exc = rows or [], exc

    def result(self):
        if self._exc:
            raise self._exc
        return self._rows


class FakeBQClient:
    """Records every call in order; never touches the network."""

    def __init__(self, query_exc=None, create_exc=None, events=None):
        self.calls = []
        self.query_exc = query_exc
        self.create_exc = create_exc
        self.events = events if events is not None else []

    def create_table(self, table, exists_ok=False):
        self.calls.append(("create_table", table.table_id, exists_ok))
        self.events.append("bq:create_table")
        if self.create_exc:
            raise self.create_exc
        return table

    def query(self, sql, job_config=None):
        self.calls.append(("query", sql, job_config))
        self.events.append(f"bq:{sql}")
        return _Job(exc=self.query_exc)

    def load_table_from_file(self, fileobj, dest, job_config=None):
        self.calls.append(("load", fileobj.read(), dest, job_config))
        return _Job()

    def get_table(self, fqtn):
        self.calls.append(("get_table", fqtn))
        return type("T", (), {"num_rows": 42})()


def _run_main(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["run_monthly.py", *argv])
    return RM.main()


@pytest.fixture
def sandbox_out(monkeypatch, tmp_path):
    """Keep main()'s output/ and raw/ writes out of the repo."""
    monkeypatch.setattr(RM, "OUT", str(tmp_path / "output"))
    monkeypatch.setattr(RM, "RAW", str(tmp_path / "raw"))
    return tmp_path


@pytest.fixture
def no_fetch(monkeypatch):
    """Fail loudly if anything tries to fetch (= spend money) or write BQ."""
    def boom(*a, **k):
        raise AssertionError("must not be called")
    monkeypatch.setattr(RM, "fetch_live", boom)
    monkeypatch.setattr(RM, "fetch_dryrun", boom)
    monkeypatch.setattr(BW, "write_snapshot", boom)


# ---------------------------------------------------------------------------
# config: rolling 32-day window + Naukri freshness
# ---------------------------------------------------------------------------
def test_config_defaults_rolling_32_day_window(reload_config):
    reload_config()
    assert C.WINDOW_DAYS == 32
    assert C.WINDOW_START == C.REPORT_DATE - timedelta(days=32)
    assert C.NAUKRI_FRESHNESS_DAYS == "30"
    assert C.LINKEDIN_TPR_SECONDS == 32 * 24 * 3600


def test_config_window_start_override(monkeypatch, reload_config):
    start = C.REPORT_DATE - timedelta(days=10)
    monkeypatch.setenv("JOBMKT_WINDOW_START", start.isoformat())
    reload_config()
    assert C.WINDOW_START == start
    assert C.WINDOW_DAYS == 10
    assert C.NAUKRI_FRESHNESS_DAYS == "15"     # <=15-day window -> the 15 enum


def test_config_window_days_override(monkeypatch, reload_config):
    monkeypatch.setenv("JOBMKT_WINDOW_DAYS", "20")
    reload_config()
    assert C.WINDOW_START == C.REPORT_DATE - timedelta(days=20)
    assert C.NAUKRI_FRESHNESS_DAYS == "30"


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------
def test_preflight_live_with_nothing_set_flags_both():
    assert RM.preflight(dry_run=False, no_bq=False) == [RM.PREFLIGHT_APIFY, RM.PREFLIGHT_BQ]


def test_preflight_dry_run_no_bq_needs_nothing():
    assert RM.preflight(dry_run=True, no_bq=True) == []


def test_preflight_live_no_bq_needs_only_apify(monkeypatch):
    assert RM.preflight(dry_run=False, no_bq=True) == [RM.PREFLIGHT_APIFY]
    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    assert RM.preflight(dry_run=False, no_bq=True) == []


def test_preflight_dry_run_with_bq_needs_only_bq_creds():
    assert RM.preflight(dry_run=True, no_bq=False) == [RM.PREFLIGHT_BQ]


@pytest.mark.parametrize("how", ["b64", "json_inline", "key_file", "adc_file"])
def test_preflight_accepts_every_bq_cred_source(monkeypatch, tmp_path, how):
    key = tmp_path / "sa.json"
    key.write_text(json.dumps({"type": "service_account"}), encoding="utf-8")
    if how == "b64":
        monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_B64", FAKE_SA_B64)
    elif how == "json_inline":
        monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_JSON", '{"type": "service_account"}')
    elif how == "key_file":
        monkeypatch.setattr(C, "BQ_SA_KEY", str(key))
    else:
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(key))
    assert RM.preflight(dry_run=True, no_bq=False) == []


def test_preflight_malformed_secret_counts_as_missing_and_is_never_printed(
        monkeypatch, capsys, sandbox_out, no_fetch):
    secret = "c2VjcmV0LXNob3VsZC1uZXZlci1wcmludA"   # not valid base64 JSON
    monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_B64", secret)
    assert RM.preflight(dry_run=True, no_bq=False) == [RM.PREFLIGHT_BQ]
    with pytest.raises(SystemExit) as e:
        _run_main(monkeypatch, "--dry-run", "--source", "linkedin")
    assert e.value.code == 2
    out = capsys.readouterr().out
    assert "FATAL preflight: missing" in out
    assert secret not in out


# ---------------------------------------------------------------------------
# main(): exit codes
# ---------------------------------------------------------------------------
def test_main_missing_creds_exits_2_before_any_fetch(monkeypatch, capsys, sandbox_out, no_fetch):
    with pytest.raises(SystemExit) as e:
        _run_main(monkeypatch, "--source", "naukri")
    assert e.value.code == 2
    out = capsys.readouterr().out
    assert "APIFY_TOKEN" in out and "BigQuery SA creds" in out


def test_main_missing_bq_creds_exits_2_even_with_apify_token(monkeypatch, sandbox_out, no_fetch):
    # The 2026-08 failure mode: token present, BQ secret absent -> used to pay
    # for the whole scrape and only then die on DefaultCredentialsError.
    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    with pytest.raises(SystemExit) as e:
        _run_main(monkeypatch, "--source", "naukri")
    assert e.value.code == 2


def test_main_live_run_with_zero_rows_exits_3(monkeypatch, capsys, sandbox_out):
    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_B64", FAKE_SA_B64)
    events = []
    monkeypatch.setattr(BW, "_client", lambda: FakeBQClient(events=events))
    calls = []
    monkeypatch.setattr(RM, "fetch_live", lambda limit=None: (
        calls.append(limit) or events.append("fetch_live")
        or ({}, {"mode": "live", "apify_cost_usd": 0.12, "manifest": []})))

    def no_write(*a, **k):
        raise AssertionError("0 rows must not reach BigQuery")
    monkeypatch.setattr(BW, "write_snapshot", no_write)
    with pytest.raises(SystemExit) as e:
        _run_main(monkeypatch, "--source", "naukri")
    assert e.value.code == 3
    assert calls == [None]
    # BQ auth + table are proven BEFORE the paid scrape.
    assert events == ["bq:SELECT 1", "bq:create_table", "fetch_live"]
    assert "[FATAL] live run produced 0 rows" in capsys.readouterr().out


@pytest.mark.parametrize("fake_kw, reason", [
    ({"query_exc": RuntimeError("invalid_grant: account disabled")}, "RuntimeError: invalid_grant"),
    ({"create_exc": PermissionError("403 Access Denied: dataset")}, "PermissionError: 403"),
])
def test_main_bad_bq_creds_exit_2_before_the_paid_scrape(monkeypatch, capsys, sandbox_out, no_fetch,
                                                         fake_kw, reason):
    # Secret present and parseable (so preflight() passes) but the key is
    # disabled / the SA lost its grant: used to pay for the scrape, then die
    # uncaught (exit 1) in write_snapshot.
    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_B64", FAKE_SA_B64)
    monkeypatch.setattr(BW, "_client", lambda: FakeBQClient(**fake_kw))
    with pytest.raises(SystemExit) as e:
        _run_main(monkeypatch, "--source", "naukri")
    assert e.value.code == 2
    out = capsys.readouterr().out
    assert "FATAL preflight: BigQuery auth/query failed (nothing spent): " + reason in out
    assert "=== Job Market Demand agent" not in out


def test_main_dry_run_with_bq_also_checks_bq_first(monkeypatch, sandbox_out, no_fetch):
    monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_B64", FAKE_SA_B64)
    monkeypatch.setattr(BW, "_client", lambda: FakeBQClient(query_exc=RuntimeError("invalid_grant")))
    with pytest.raises(SystemExit) as e:
        _run_main(monkeypatch, "--dry-run", "--source", "linkedin")
    assert e.value.code == 2


def test_main_dry_run_no_bq_happy_path_exits_normally(monkeypatch, sandbox_out):
    # Same as the CI smoke: tracked LinkedIn fixtures, no network, no secrets.
    assert _run_main(monkeypatch, "--dry-run", "--no-bq", "--source", "linkedin") is None
    manifest = json.load(open(sandbox_out / "output" / "run_manifest.json", encoding="utf-8"))
    assert manifest["run_id"] == f"linkedin-{C.REPORT_DATE:%Y-%m}"
    assert manifest["stats"]["kept"] > 0 and manifest["bq"] is None


def test_main_preflight_ok_runs_select_1_and_spends_nothing(monkeypatch, capsys, sandbox_out, no_fetch):
    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_B64", FAKE_SA_B64)
    fake = FakeBQClient()
    monkeypatch.setattr(BW, "_client", lambda: fake)
    with pytest.raises(SystemExit) as e:
        _run_main(monkeypatch, "--preflight")
    assert e.value.code == 0
    assert [c[:2] for c in fake.calls] == [("query", "SELECT 1")]
    assert "preflight OK" in capsys.readouterr().out


def test_main_preflight_missing_secret_exits_2(monkeypatch, capsys, sandbox_out, no_fetch):
    monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_B64", FAKE_SA_B64)   # APIFY_TOKEN absent
    with pytest.raises(SystemExit) as e:
        _run_main(monkeypatch, "--preflight")
    assert e.value.code == 2
    out = capsys.readouterr().out
    assert "FATAL preflight: missing APIFY_TOKEN" in out
    assert "preflight OK" not in out


def test_main_preflight_bq_auth_failure_exits_2(monkeypatch, capsys, sandbox_out, no_fetch):
    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_B64", FAKE_SA_B64)
    fake = FakeBQClient(query_exc=RuntimeError("invalid_grant"))
    monkeypatch.setattr(BW, "_client", lambda: fake)
    with pytest.raises(SystemExit) as e:
        _run_main(monkeypatch, "--preflight")
    assert e.value.code == 2
    assert "BigQuery auth/query failed: RuntimeError" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# deploy docs: the no-spend smoke must really run --preflight
# ---------------------------------------------------------------------------
def _smoke_commands(text):
    """Logical lines (backslash continuations joined) that run a Fly machine."""
    joined = re.sub(r"\\\r?\n\s*", " ", text)
    return [ln for ln in joined.splitlines() if "machine run" in ln]


def test_docs_never_pass_the_preflight_smoke_via_fly_command_flag():
    # `fly machine run --command` is read only with --shell (flyctl v0.4.110);
    # otherwise the image CMD runs = a LIVE paid scrape + BQ DELETE/append. The
    # smoke must pass the command positionally after `--`.
    here = RM.HERE
    deploy = os.path.join(here, "DEPLOY_FLY.md")
    paths = [deploy, os.path.join(here, "Dockerfile"), os.path.join(here, "..", "PROJECT_TODO.md")]
    docs = {p: open(p, encoding="utf-8").read() for p in paths if os.path.isfile(p)}
    assert deploy in docs
    for path, text in docs.items():
        assert not re.search(r"--command\s+[\"']?python", text), path
        for cmd in _smoke_commands(text):
            if "--preflight" in cmd:
                assert re.search(r"\s--\s+python\s+run_\w+\.py\s+--preflight\b", cmd), (path, cmd)
    assert [c for c in _smoke_commands(docs[deploy]) if "run_monthly.py --preflight" in c], \
        "DEPLOY_FLY.md §4 lost its preflight smoke command"


# ---------------------------------------------------------------------------
# bigquery_writer: idempotent monthly snapshot (DELETE run_id, then APPEND)
# ---------------------------------------------------------------------------
def test_write_snapshot_deletes_run_id_before_append(monkeypatch):
    fake = FakeBQClient()
    monkeypatch.setattr(BW, "_client", lambda: fake)
    rows = [{"run_id": "naukri-2026-11", "title": "ML Engineer"},
            {"run_id": "naukri-2026-11", "title": "LLM Engineer"}]
    res = BW.write_snapshot(rows, "naukri-2026-11")

    kinds = [c[0] for c in fake.calls]
    assert kinds == ["create_table", "query", "load", "get_table"]
    _, sql, qcfg = fake.calls[1]
    assert sql == f"DELETE FROM `{C.BQ_FQTN}` WHERE run_id = @rid"
    (param,) = qcfg.query_parameters
    assert (param.name, param.type_, param.value) == ("rid", "STRING", "naukri-2026-11")

    _, payload, dest, lcfg = fake.calls[2]
    assert dest == C.BQ_FQTN
    assert lcfg.write_disposition == bigquery.WriteDisposition.WRITE_APPEND
    assert lcfg.source_format == bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
    assert [json.loads(line) for line in payload.decode("utf-8").splitlines()] == rows
    assert res == {"loaded": 2, "table": C.BQ_FQTN, "table_total_rows": 42,
                   "run_id": "naukri-2026-11"}


# ---------------------------------------------------------------------------
# process(): the tracked LinkedIn fixtures still validate end-to-end
# ---------------------------------------------------------------------------
def test_process_tracked_linkedin_fixtures_are_valid(monkeypatch):
    files = [f for g in RM.DRYRUN_RAW_GLOBS for f in glob.glob(g)]
    assert files, "tracked ai-hiring-trends-test/raw LinkedIn fixtures are missing"
    monkeypatch.setattr(RM, "SOURCE", "linkedin")
    monkeypatch.setattr(RM, "RUN_ID", "linkedin-test")
    by_query, meta = RM.fetch_dryrun()
    assert meta["mode"] == "dry-run" and meta["apify_cost_usd"] == 0.0
    rows, stats = RM.process(by_query)
    assert stats["kept"] > 0
    assert stats["validation_errors"] == 0
    assert stats["kept"] == len(rows)
    assert all(r.run_id == "linkedin-test" for r in rows)
    assert all(r.to_bq()["run_id"] == "linkedin-test" for r in rows[:5])
