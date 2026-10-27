"""Apify budget governor + governed actor runner (Reddit, weekly).

Same proven design as the job-market agent's harness: reads real account spend
before/after each run, hard-aborts under the $5 cap. Imported lazily by the
social agent only when Reddit is enabled, so the rest of the pipeline never
requires APIFY_TOKEN.
"""
from __future__ import annotations
import os, time
import requests
import config as C

API = "https://api.apify.com/v2"
_S = requests.Session()


class BudgetExceeded(Exception):
    pass


def redact(text) -> str:
    """str(text) with APIFY_TOKEN masked (backstop for printed errors)."""
    s, t = str(text), os.environ.get("APIFY_TOKEN")
    return s.replace(t, "***") if t else s


def _token() -> str:
    t = os.environ.get("APIFY_TOKEN")
    if not t:
        raise RuntimeError("APIFY_TOKEN not set (Reddit needs Apify acct #2)")
    return t


class BudgetGovernor:
    def __init__(self):
        self.token = _token()
        # Header, never `?token=` in the URL (2026-10-27): requests errors quote
        # the URL, which put the token into Fly logs via "[reddit] skipped: ...".
        self.auth = {"Authorization": f"Bearer {self.token}"}
        self.baseline = self._usage()
        self.last = self.baseline

    def _usage(self):
        r = _S.get(f"{API}/users/me/limits", headers=self.auth, timeout=30)
        r.raise_for_status()
        return float(r.json()["data"]["current"]["monthlyUsageUsd"])

    @property
    def session_spent(self):
        return self.last - self.baseline

    def refresh(self):
        self.last = self._usage()
        return self.last

    def check_can_launch(self, label):
        self.refresh()
        if self.last >= C.APIFY_ACCOUNT_ABS_ABORT_USD:
            raise BudgetExceeded(f"abs usage ${self.last:.4f} >= {C.APIFY_ACCOUNT_ABS_ABORT_USD}")
        if self.session_spent >= C.APIFY_HARD_ABORT_USD:
            raise BudgetExceeded(f"session ${self.session_spent:.4f} >= {C.APIFY_HARD_ABORT_USD}")
        return True

    def soft_ok(self):
        return self.session_spent < C.APIFY_SOFT_CEILING_USD


def run_actor(actor, run_input, gov: BudgetGovernor, label,
              timeout_s=C.APIFY_DEFAULT_TIMEOUT_S):
    gov.check_can_launch(label)
    aid = actor.replace("/", "~")
    before = gov.last
    t0 = time.time()
    r = _S.post(f"{API}/acts/{aid}/runs",
                params={"timeout": timeout_s}, headers=gov.auth, json=run_input, timeout=60)
    if r.status_code not in (200, 201):
        return [], 0.0, {"error": redact(f"launch HTTP {r.status_code}: {r.text[:200]}")}
    run = r.json()["data"]
    run_id, ds_id, status = run["id"], run.get("defaultDatasetId"), run["status"]
    while status in ("READY", "RUNNING"):
        if time.time() - t0 > timeout_s + 60:
            _S.post(f"{API}/actor-runs/{run_id}/abort", headers=gov.auth, timeout=30)
            status = "TIMED-OUT"; break
        time.sleep(C.APIFY_POLL_INTERVAL_S)
        d = _S.get(f"{API}/actor-runs/{run_id}", headers=gov.auth, timeout=30).json()["data"]
        status, ds_id = d["status"], d.get("defaultDatasetId", ds_id)
    items = []
    if ds_id:
        ir = _S.get(f"{API}/datasets/{ds_id}/items",
                    params={"clean": "true", "format": "json"}, headers=gov.auth,
                    timeout=120)
        if ir.status_code == 200:
            try: items = ir.json()
            except Exception: items = []
    time.sleep(2)
    after = gov.refresh()
    return items, after - before, {"run_id": run_id, "status": status,
                                   "n_items": len(items), "cost_usd": round(after - before, 5)}
