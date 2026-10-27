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
import requests

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


# ---------------------------------------------------------------------------
# partial / degraded live runs (2026-10-27): a run where most queries failed
# used to DELETE+APPEND the month with a fraction of the data and exit 0.
# ---------------------------------------------------------------------------
def _fixture_items():
    files = sorted(f for g in RM.DRYRUN_RAW_GLOBS for f in glob.glob(g))
    assert files, "tracked ai-hiring-trends-test/raw LinkedIn fixtures are missing"
    return json.load(open(files[0], encoding="utf-8"))


class _FakeGov:
    def __init__(self, soft=None):
        self.session_spent, self.last = 0.0, 1.0
        self._soft = list(soft or [])

    def soft_ok(self):
        return self._soft.pop(0) if self._soft else True


def _fake_harness(results, soft=None):
    """A stand-in `harness` module: run_actor plays `results` in order, one per
    launched query (an Exception instance is raised)."""
    import types
    H = types.ModuleType("harness")

    class BudgetExceeded(Exception):
        pass
    H.BudgetExceeded = BudgetExceeded
    H.BudgetGovernor = lambda: _FakeGov(soft)
    H.redact = str
    plays = list(results)

    def run_actor(actor, run_input, gov, label, timeout_s=None):
        r = plays.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    H.run_actor = run_actor
    return H


def _abort_at(H, query, run_actor):
    """Wrap run_actor so the governor raises BudgetExceeded at `query`."""
    def wrapped(actor, run_input, gov, label, timeout_s=None):
        if label.endswith(":" + query):
            raise H.BudgetExceeded("absolute usage $4.51 >= abort $4.5")
        return run_actor(actor, run_input, gov, label, timeout_s=timeout_s)
    return wrapped


def _ok(items, status="SUCCEEDED"):
    return items, 0.01, {"run_id": "r", "status": status, "n_items": len(items),
                         "cost_usd": 0.01, "session_spent": 0.01}


def test_fetch_live_counts_every_kind_of_failed_query(monkeypatch, sandbox_out):
    os.makedirs(RM.RAW, exist_ok=True)
    monkeypatch.setattr(RM, "SOURCE", "linkedin")
    items = _fixture_items()[:3]
    H = _fake_harness([
        _ok(items),                                             # q0 OK
        RuntimeError("503 Server Error"),                       # q2 [ERR]   (q1 GUARD-SKIP)
        ([], 0.0, {"error": "launch HTTP 402: payment required"}),   # q3 [LAUNCH-ERR]
        _ok([], status="FAILED"),                               # q4 [RUN-ERR] (was "[OK] raw=0")
        _ok(items, status="TIMED-OUT"),                         # q5 partial data: kept, counts OK
    ], soft=[True, False])
    H.run_actor = _abort_at(H, C.LINKEDIN_QUERIES[6], H.run_actor)   # q6 [ABORT]; q7 never runs
    monkeypatch.setitem(sys.modules, "harness", H)

    by_query, meta = RM.fetch_live(limit_queries=8)
    qs = C.LINKEDIN_QUERIES[:8]
    assert set(by_query) == {qs[0], qs[5]}
    assert meta["queries_planned"] == 8
    assert meta["queries_failed"] == [qs[1], qs[2], qs[3], qs[4], qs[6], qs[7]]
    kinds = {m["query"]: (set(m) - {"query"}) for m in meta["manifest"]}
    assert kinds[qs[1]] == {"skipped"} and kinds[qs[2]] == {"error"}
    assert kinds[qs[3]] == {"launch_error"} and kinds[qs[4]] == {"run_error"}
    assert {m["query"]: m.get("skipped") for m in meta["manifest"]}[qs[7]] == "aborted"
    assert RM.coverage_verdict(meta)[0] == 4


@pytest.mark.parametrize("planned, n_failed, code", [
    (14, 0, 0), (14, 2, 5), (14, 3, 4), (14, 13, 4), (1, 1, 4)])
def test_coverage_verdict_gate(planned, n_failed, code):
    meta = {"queries_planned": planned, "queries_failed": [f"q{i}" for i in range(n_failed)]}
    assert RM.coverage_verdict(meta)[0] == code


def test_coverage_verdict_dry_run_meta_is_ok():
    assert RM.coverage_verdict({"mode": "dry-run", "apify_cost_usd": 0.0}) == (0, "")


def _setup_live(monkeypatch, n_ok, n_failed):
    """Live main() with BQ + Apify faked: n_ok queries returned the fixture
    items, n_failed hit a launch error. Returns the write_snapshot call log."""
    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_B64", FAKE_SA_B64)
    monkeypatch.setattr(BW, "_client", lambda: FakeBQClient())
    items = _fixture_items()
    qs = C.LINKEDIN_QUERIES[:n_ok + n_failed]
    by_query = {q: items for q in qs[:n_ok]}
    manifest = ([{"query": q, "raw": len(items), "cost_usd": 0.05} for q in qs[:n_ok]]
                + [{"query": q, "launch_error": "launch HTTP 402"} for q in qs[n_ok:]])
    meta = {"mode": "live", "apify_cost_usd": 0.05, "manifest": manifest,
            "queries_planned": len(qs), "queries_failed": list(qs[n_ok:])}
    monkeypatch.setattr(RM, "fetch_live", lambda limit=None: (by_query, meta))
    writes = []
    monkeypatch.setattr(BW, "write_snapshot", lambda rows, rid, dry_run=False: (
        writes.append((len(rows), rid)) or {"loaded": len(rows), "table": C.BQ_FQTN,
                                            "table_total_rows": len(rows), "run_id": rid}))
    monkeypatch.setattr(BW, "query_summary", lambda rid: [])
    return writes


def test_main_partial_run_exits_4_and_keeps_the_previous_snapshot(monkeypatch, capsys, sandbox_out):
    writes = _setup_live(monkeypatch, n_ok=1, n_failed=13)
    with pytest.raises(SystemExit) as e:
        _run_main(monkeypatch, "--source", "linkedin")
    assert e.value.code == 4
    assert writes == []           # no DELETE run_id + APPEND of 1/14 of the month
    out = capsys.readouterr().out
    assert "[FATAL] partial run, BigQuery not written: 13/14 queries failed" in out
    manifest = json.load(open(sandbox_out / "output" / "run_manifest.json", encoding="utf-8"))
    assert manifest["coverage"]["exit_code"] == 4 and manifest["bq"] is None


def test_main_degraded_run_writes_but_exits_5(monkeypatch, capsys, sandbox_out):
    writes = _setup_live(monkeypatch, n_ok=13, n_failed=1)
    with pytest.raises(SystemExit) as e:
        _run_main(monkeypatch, "--source", "linkedin")
    assert e.value.code == 5
    assert len(writes) == 1 and writes[0][1] == f"linkedin-{C.REPORT_DATE:%Y-%m}"
    assert "[DEGRADED] snapshot written, but 1/14 queries failed" in capsys.readouterr().out


def test_main_full_live_run_writes_and_exits_0(monkeypatch, sandbox_out):
    writes = _setup_live(monkeypatch, n_ok=14, n_failed=0)
    assert _run_main(monkeypatch, "--source", "linkedin") is None
    assert len(writes) == 1


# ---------------------------------------------------------------------------
# harness: the Apify token travels in a header, never in a URL (2026-10-27).
# With `?token=`, requests' own error text ("503 ... for url: ...?token=X")
# printed the token into Fly logs and the run manifest.
# ---------------------------------------------------------------------------
TOKEN = "apify_api_FAKE0123456789fake"


class _FakeAdapter(requests.adapters.BaseAdapter):
    """Records every prepared request; answers from `route(request)`."""

    def __init__(self, route):
        super().__init__()
        self.route, self.sent = route, []

    def send(self, request, **kw):
        self.sent.append(request)
        status, body = self.route(request)
        resp = requests.Response()
        resp.status_code, resp.url, resp.request = status, request.url, request
        resp._content = json.dumps(body).encode()
        resp.headers["Content-Type"] = "application/json"
        return resp

    def close(self):
        pass


@pytest.fixture
def real_harness(monkeypatch):
    """Import the real harness under a fake token; dropped again afterwards."""
    monkeypatch.setenv("APIFY_TOKEN", TOKEN)
    monkeypatch.delitem(sys.modules, "harness", raising=False)
    H = importlib.import_module("harness")
    monkeypatch.setitem(sys.modules, "harness", H)
    monkeypatch.setattr(H.time, "sleep", lambda s: None)
    return H


def _limits(usage=1.0):
    return 200, {"data": {"current": {"monthlyUsageUsd": usage}}}


def test_harness_http_error_never_carries_the_token(real_harness):
    H = real_harness
    fake = _FakeAdapter(lambda req: (503, {"error": "unavailable"}))
    H.S.mount("https://", fake)
    with pytest.raises(requests.HTTPError) as e:
        H.BudgetGovernor()
    assert TOKEN not in str(e.value)
    (req,) = fake.sent
    assert TOKEN not in req.url
    assert req.headers["Authorization"] == f"Bearer {TOKEN}"


def test_harness_run_actor_sends_the_token_only_as_a_header(real_harness):
    H = real_harness

    def route(req):
        if req.url.split("?")[0].endswith("/users/me/limits"):
            return _limits()
        if "/acts/" in req.url:
            return 201, {"data": {"id": "run1", "status": "SUCCEEDED", "defaultDatasetId": "ds1"}}
        return 200, [{"title": "ML Engineer"}]
    fake = _FakeAdapter(route)
    H.S.mount("https://", fake)
    items, _, meta = H.run_actor("a/b", {"q": 1}, H.BudgetGovernor(), "label")
    assert items == [{"title": "ML Engineer"}] and meta["status"] == "SUCCEEDED"
    assert len(fake.sent) >= 4    # limits x3 (init/pre/post), launch, dataset
    for req in fake.sent:
        assert TOKEN not in req.url, req.url
        assert req.headers["Authorization"] == f"Bearer {TOKEN}"


def test_harness_redact_masks_the_token(real_harness):
    assert real_harness.redact(f"boom url=...?token={TOKEN}") == "boom url=...?token=***"


def test_fetch_live_err_line_and_manifest_are_redacted(monkeypatch, capsys, sandbox_out, real_harness):
    os.makedirs(RM.RAW, exist_ok=True)
    monkeypatch.setattr(RM, "SOURCE", "linkedin")
    H = real_harness
    monkeypatch.setattr(H, "BudgetGovernor", lambda: _FakeGov())

    def run_actor(*a, **k):
        raise RuntimeError(f"Max retries exceeded with url: /v2/x?token={TOKEN}")
    monkeypatch.setattr(H, "run_actor", run_actor)
    _, meta = RM.fetch_live(limit_queries=1)
    assert TOKEN not in capsys.readouterr().out
    assert TOKEN not in json.dumps(meta)
