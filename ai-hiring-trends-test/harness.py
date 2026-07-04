"""Runtime harness: budget governor + governed actor runner.

The budget governor reads ACTUAL account spend (Apify limits API) before and
after every run, enforces self-imposed ceilings, and hard-aborts the pipeline
before the $5 platform cap is ever reached. This is the reliability guarantee.
"""
import os, sys, time, json
import requests
import config as C

TOKEN = os.environ.get("APIFY_TOKEN")
if not TOKEN:
    sys.exit("FATAL: APIFY_TOKEN env var not set")

API = "https://api.apify.com/v2"
S = requests.Session()


class BudgetExceeded(Exception):
    pass


class BudgetGovernor:
    """Tracks spend against self-imposed ceilings layered under the $5 cap."""

    def __init__(self):
        self.baseline = self._usage()
        self.last = self.baseline
        self.events = []  # (label, absolute_usd, session_delta)
        print(f"[GOVERNOR] baseline monthly usage = ${self.baseline:.4f}  "
              f"(account cap $5.00, room ${5.0 - self.baseline:.4f})")

    def _usage(self):
        r = S.get(f"{API}/users/me/limits?token={TOKEN}", timeout=30)
        r.raise_for_status()
        return float(r.json()["data"]["current"]["monthlyUsageUsd"])

    @property
    def session_spent(self):
        return self.last - self.baseline

    def refresh(self, label=""):
        self.last = self._usage()
        self.events.append((label, self.last, self.session_spent))
        return self.last

    def check_can_launch(self, label):
        """Raise/refuse BEFORE launching a new run."""
        self.refresh(f"pre:{label}")
        if self.last >= C.ACCOUNT_ABS_ABORT_USD:
            raise BudgetExceeded(
                f"absolute usage ${self.last:.4f} >= abort ${C.ACCOUNT_ABS_ABORT_USD}")
        if self.session_spent >= C.SESSION_HARD_ABORT_USD:
            raise BudgetExceeded(
                f"session spend ${self.session_spent:.4f} >= hard ${C.SESSION_HARD_ABORT_USD}")
        return True

    def soft_ok(self):
        """False -> stop launching new scaled runs (soft ceiling)."""
        return self.session_spent < C.SESSION_SOFT_CEILING_USD


def run_actor(actor, run_input, governor, label, max_items_hint=None,
              memory_mb=None, timeout_s=C.DEFAULT_TIMEOUT_S):
    """Launch one actor run, poll to completion, return (items, cost_delta, meta).
    Governed: refuses to launch if budget ceiling reached."""
    governor.check_can_launch(label)
    aid = actor.replace("/", "~")
    params = {"token": TOKEN, "timeout": timeout_s}
    if memory_mb:
        params["memory"] = memory_mb
    before = governor.last

    t0 = time.time()
    r = S.post(f"{API}/acts/{aid}/runs", params=params, json=run_input, timeout=60)
    if r.status_code not in (200, 201):
        return [], 0.0, {"error": f"launch HTTP {r.status_code}: {r.text[:300]}"}
    run = r.json()["data"]
    run_id = run["id"]
    ds_id = run.get("defaultDatasetId")

    # Poll
    status = run["status"]
    while status in ("READY", "RUNNING"):
        if time.time() - t0 > timeout_s + 60:
            S.post(f"{API}/actor-runs/{run_id}/abort?token={TOKEN}", timeout=30)
            status = "TIMED-OUT"
            break
        time.sleep(C.POLL_INTERVAL_S)
        rr = S.get(f"{API}/actor-runs/{run_id}?token={TOKEN}", timeout=30)
        d = rr.json()["data"]
        status = d["status"]
        ds_id = d.get("defaultDatasetId", ds_id)

    # Fetch items
    items = []
    if ds_id:
        ir = S.get(f"{API}/datasets/{ds_id}/items",
                   params={"token": TOKEN, "clean": "true", "format": "json"},
                   timeout=120)
        if ir.status_code == 200:
            try:
                items = ir.json()
            except Exception:
                items = []

    # Cost (true, from account)
    time.sleep(2)  # let usage settle
    after = governor.refresh(f"post:{label}")
    cost = after - before
    meta = {"run_id": run_id, "status": status, "elapsed_s": round(time.time() - t0, 1),
            "n_items": len(items), "cost_usd": round(cost, 5),
            "session_spent": round(governor.session_spent, 5)}
    return items, cost, meta
