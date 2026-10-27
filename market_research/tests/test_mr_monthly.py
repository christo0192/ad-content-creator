"""Offline tests for the market-research pipeline's monthly run (added 2026-10-27).

No network, no secrets, no LLM: BigQuery (bq.client) and `claude -p`
(llm.claude) are replaced with fakes, and conftest.clean_env strips every
credential env var and points CLAUDE_BIN at a missing binary.

  python -m pytest -q market_research/tests     # its own process (see conftest)
"""
import base64
import importlib
import json

import pytest

import config as C
import bq as BQ
import llm as L
import run_weekly as RW
from google.cloud import bigquery

FAKE_SA_B64 = base64.b64encode(json.dumps({"type": "service_account"}).encode()).decode()


# ---------------------------------------------------------------------------
# helpers / fakes
# ---------------------------------------------------------------------------
@pytest.fixture
def reload_config(monkeypatch):
    """Reload config under the test's env, then restore the defaults afterwards
    (reload mutates the module object that bq/llm/run_weekly imported as C)."""
    yield lambda: importlib.reload(C)
    monkeypatch.delenv("MR_CADENCE", raising=False)
    monkeypatch.delenv("MR_RUN_ID", raising=False)
    importlib.reload(C)


class _Job:
    def __init__(self, exc=None):
        self._exc = exc

    def result(self):
        if self._exc:
            raise self._exc
        return []


class FakeBQClient:
    def __init__(self, query_exc=None):
        self.calls = []
        self.query_exc = query_exc

    def create_table(self, table, exists_ok=False):
        self.calls.append(("create_table", table.table_id, exists_ok))
        return table

    def query(self, sql, job_config=None):
        self.calls.append(("query", sql, job_config))
        return _Job(self.query_exc)

    def load_table_from_file(self, fileobj, dest, job_config=None):
        self.calls.append(("load", fileobj.read(), dest, job_config))
        return _Job()

    def get_table(self, fqtn):
        self.calls.append(("get_table", fqtn))
        return type("T", (), {"num_rows": 7})()


def _summary(**tabs):
    return {"run_id": "monthly-2026-11", "tabs": tabs}


HEALTHY = dict(social={"rows": 40}, blog={"rows": 25}, competitor={"rows": 6}, exec={"rows": 6})


# ---------------------------------------------------------------------------
# run_id grain (the idempotency key)
# ---------------------------------------------------------------------------
def test_run_id_defaults_to_weekly_per_day(reload_config):
    reload_config()
    assert C.CADENCE == "weekly"
    assert C.RUN_ID == f"weekly-{C.REPORT_DATE:%Y-%m-%d}"


def test_run_id_is_monthly_with_mr_cadence_monthly(monkeypatch, reload_config):
    monkeypatch.setenv("MR_CADENCE", "monthly")
    reload_config()
    assert C.CADENCE == "monthly"
    assert C.RUN_ID == f"monthly-{C.REPORT_DATE:%Y-%m}"


def test_unknown_cadence_falls_back_to_weekly(monkeypatch, reload_config):
    monkeypatch.setenv("MR_CADENCE", "daily")
    reload_config()
    assert C.RUN_ID == f"weekly-{C.REPORT_DATE:%Y-%m-%d}"


def test_mr_run_id_override_wins(monkeypatch, reload_config):
    monkeypatch.setenv("MR_CADENCE", "monthly")
    monkeypatch.setenv("MR_RUN_ID", "backfill-2026-10")
    reload_config()
    assert C.RUN_ID == "backfill-2026-10"


def test_fly_toml_sets_monthly_cadence_and_never_restart():
    import os
    import tomllib
    with open(os.path.join(RW.HERE, "fly.toml"), "rb") as f:
        cfg = tomllib.load(f)
    assert cfg["env"]["MR_CADENCE"] == "monthly"
    assert cfg["restart"] == [{"policy": "never"}]


# ---------------------------------------------------------------------------
# run_ok(): the exit-code verdict
# ---------------------------------------------------------------------------
def test_run_ok_true_for_a_healthy_full_run():
    assert RW.run_ok(_summary(**HEALTHY), None, False)
    assert RW.run_problems(_summary(**HEALTHY)) == []


@pytest.mark.parametrize("tab", ["social", "blog", "competitor"])
def test_run_ok_false_when_a_tab_errored(tab):
    tabs = dict(HEALTHY, **{tab: {"error": "boom"}})
    assert not RW.run_ok(_summary(**tabs), None, False)
    assert RW.run_problems(_summary(**tabs)) == [f"{tab}: error boom"]


@pytest.mark.parametrize("tab", ["blog", "competitor", "exec", "social"])
def test_run_ok_false_when_a_tab_has_zero_rows(tab):
    # blog/competitor/exec all 0 is exactly the expired-Claude-token signature.
    tabs = dict(HEALTHY, **{tab: {"rows": 0}})
    assert not RW.run_ok(_summary(**tabs), None, False)
    assert RW.run_problems(_summary(**tabs)) == [f"{tab}: 0 rows"]


def test_run_ok_false_when_full_run_has_no_exec_tab():
    tabs = {k: v for k, v in HEALTHY.items() if k != "exec"}
    assert not RW.run_ok(_summary(**tabs), None, False)


def test_run_ok_true_without_exec_when_exec_was_not_requested():
    tabs = {k: v for k, v in HEALTHY.items() if k != "exec"}
    assert RW.run_ok(_summary(**tabs), None, True)                      # --no-exec
    assert RW.run_ok(_summary(social={"rows": 40}), "social", False)    # --only social


def test_run_ok_false_for_only_blog_with_zero_rows():
    assert not RW.run_ok(_summary(blog={"rows": 0}), "blog", False)


# ---------------------------------------------------------------------------
# preflight()
# ---------------------------------------------------------------------------
def test_preflight_flags_llm_token_on_fly(monkeypatch):
    monkeypatch.setenv("FLY_APP_NAME", "ik-market-research-weekly")
    assert RW.preflight(no_bq=True) == [RW.PREFLIGHT_LLM]


@pytest.mark.parametrize("var", ["CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"])
def test_preflight_either_llm_token_satisfies_fly(monkeypatch, var):
    monkeypatch.setenv("FLY_APP_NAME", "ik-market-research-weekly")
    monkeypatch.setenv(var, "dummy")
    assert RW.preflight(no_bq=True) == []


def test_preflight_local_run_does_not_demand_llm_token():
    assert RW.preflight(no_bq=True) == []     # local claude uses its own login


def test_preflight_mr_require_llm_token_forces_the_check(monkeypatch):
    monkeypatch.setenv("MR_REQUIRE_LLM_TOKEN", "1")
    assert RW.preflight(no_bq=True) == [RW.PREFLIGHT_LLM]


def test_preflight_only_social_needs_no_llm_token(monkeypatch):
    monkeypatch.setenv("FLY_APP_NAME", "ik-market-research-weekly")
    assert RW.preflight(no_bq=True, only="social") == []


def test_preflight_flags_missing_bq_creds_and_accepts_b64(monkeypatch):
    assert RW.preflight(no_bq=False) == [RW.PREFLIGHT_BQ]
    monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_B64", FAKE_SA_B64)
    assert RW.preflight(no_bq=False) == []


def test_preflight_malformed_bq_secret_counts_as_missing(monkeypatch):
    monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_B64", "bm90LWpzb24")
    assert RW.preflight(no_bq=False) == [RW.PREFLIGHT_BQ]


def test_preflight_on_fly_with_nothing_lists_both(monkeypatch):
    monkeypatch.setenv("FLY_APP_NAME", "ik-market-research-weekly")
    assert RW.preflight(no_bq=False) == [RW.PREFLIGHT_BQ, RW.PREFLIGHT_LLM]


# ---------------------------------------------------------------------------
# main(): exit codes
# ---------------------------------------------------------------------------
@pytest.fixture
def no_run(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("run() must not be called")
    monkeypatch.setattr(RW, "run", boom)


def test_main_exits_2_on_missing_preflight_and_never_runs(monkeypatch, capsys, no_run):
    monkeypatch.setenv("FLY_APP_NAME", "ik-market-research-weekly")
    assert RW.main([]) == 2
    out = capsys.readouterr().out
    assert "FATAL preflight: missing" in out and "CLAUDE_CODE_OAUTH_TOKEN" in out


def test_main_exits_1_on_a_degraded_run(monkeypatch, capsys):
    monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_B64", FAKE_SA_B64)
    seen = {}

    def fake_run(only=None, no_bq=False, no_exec=False):
        seen.update(only=only, no_bq=no_bq, no_exec=no_exec)
        return _summary(social={"rows": 40}, blog={"rows": 0}, competitor={"rows": 0},
                        exec={"rows": 0})
    monkeypatch.setattr(RW, "run", fake_run)
    assert RW.main([]) == 1
    assert seen == {"only": None, "no_bq": False, "no_exec": False}
    assert "[FATAL] run degraded: blog: 0 rows; competitor: 0 rows; exec: 0 rows" in capsys.readouterr().out


def test_main_exits_0_on_a_healthy_run(monkeypatch):
    monkeypatch.setattr(RW, "run", lambda only=None, no_bq=False, no_exec=False: _summary(**HEALTHY))
    assert RW.main(["--no-bq"]) == 0


def test_main_preflight_ok_probes_bq_and_claude_once(monkeypatch, capsys, no_run):
    monkeypatch.setenv("FLY_APP_NAME", "ik-market-research-weekly")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "dummy")
    monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_B64", FAKE_SA_B64)
    fake = FakeBQClient()
    monkeypatch.setattr(BQ, "client", lambda: fake)
    prompts = []
    monkeypatch.setattr(L, "claude", lambda p, model=None, timeout=None, effort=None: (
        prompts.append((p, timeout)) or "OK"))
    assert RW.main(["--preflight"]) == 0
    assert [c[:2] for c in fake.calls] == [("query", "SELECT 1")]
    assert prompts == [("Reply with OK", 120)]
    assert "preflight OK" in capsys.readouterr().out


def test_main_preflight_fails_2_when_claude_fails(monkeypatch, capsys, no_run):
    # Real llm.claude against the missing CLAUDE_BIN from conftest -> raises.
    monkeypatch.setattr(BQ, "client", lambda: FakeBQClient())
    monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_B64", FAKE_SA_B64)
    assert RW.main(["--preflight"]) == 2
    out = capsys.readouterr().out
    assert "FATAL preflight: claude -p failed" in out and "preflight OK" not in out


def test_main_preflight_fails_2_when_bq_auth_fails(monkeypatch, capsys, no_run):
    monkeypatch.setenv("MARKET_RESEARCH_BQ_SA_B64", FAKE_SA_B64)
    monkeypatch.setattr(BQ, "client", lambda: FakeBQClient(query_exc=RuntimeError("invalid_grant")))
    monkeypatch.setattr(L, "claude", lambda *a, **k: pytest.fail("claude must not run after a BQ failure"))
    assert RW.main(["--preflight"]) == 2
    assert "BigQuery auth/query failed: RuntimeError" in capsys.readouterr().out


def test_main_preflight_only_social_skips_claude(monkeypatch, no_run):
    monkeypatch.setattr(L, "claude", lambda *a, **k: pytest.fail("social needs no LLM"))
    assert RW.main(["--preflight", "--no-bq", "--only", "social"]) == 0


# ---------------------------------------------------------------------------
# run(): the summary it builds is what run_problems() reads
# ---------------------------------------------------------------------------
class _Row:
    def __init__(self, i):
        self.i = i

    def to_bq(self):
        return {"i": self.i}


def _agent(rows=None, exc=None):
    def collect(rid):
        if exc:
            raise exc
        return [_Row(i) for i in range(rows or 0)]
    return type("Agent", (), {"collect": staticmethod(collect)})


def test_run_summary_feeds_the_verdict(monkeypatch, tmp_path):
    monkeypatch.setattr(RW, "OUT", str(tmp_path))
    monkeypatch.setattr(RW, "AGENTS", {"social": _agent(3), "blog": _agent(0),
                                       "competitor": _agent(exc=RuntimeError("jina down"))})
    monkeypatch.setattr(RW.exec_summary, "synthesize", lambda *a: [])
    s = RW.run(no_bq=True)
    assert s["tabs"]["social"]["rows"] == 3
    assert RW.run_problems(s) == ["blog: 0 rows", "competitor: error jina down", "exec: 0 rows"]


# ---------------------------------------------------------------------------
# bq.write_snapshot: idempotent on run_id (DELETE, then APPEND)
# ---------------------------------------------------------------------------
def test_write_snapshot_deletes_run_id_before_append(monkeypatch):
    fake = FakeBQClient()
    monkeypatch.setattr(BQ, "client", lambda: fake)
    rows = [{"run_id": "monthly-2026-11", "rank": 1}, {"run_id": "monthly-2026-11", "rank": 2}]
    res = BQ.write_snapshot("exec", rows, "monthly-2026-11")

    assert [c[0] for c in fake.calls] == ["create_table", "query", "load", "get_table"]
    _, sql, qcfg = fake.calls[1]
    assert sql == f"DELETE FROM `{C.fqtn('exec')}` WHERE run_id=@rid"
    (param,) = qcfg.query_parameters
    assert (param.name, param.type_, param.value) == ("rid", "STRING", "monthly-2026-11")
    _, payload, dest, lcfg = fake.calls[2]
    assert dest == C.fqtn("exec")
    assert lcfg.write_disposition == bigquery.WriteDisposition.WRITE_APPEND
    assert [json.loads(x) for x in payload.decode("utf-8").splitlines()] == rows
    assert res == {"tab": "exec", "table": C.fqtn("exec"), "loaded": 2, "table_total_rows": 7}


def test_write_snapshot_with_no_rows_still_clears_the_run_id(monkeypatch):
    fake = FakeBQClient()
    monkeypatch.setattr(BQ, "client", lambda: fake)
    BQ.write_snapshot("social", [], "monthly-2026-11")
    assert [c[0] for c in fake.calls] == ["create_table", "query", "get_table"]
