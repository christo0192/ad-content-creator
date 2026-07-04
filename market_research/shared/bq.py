"""Generic BigQuery writer for all market-research tabs.

Same auth precedence as the job-market agent (env base64/json/file -> ADC), so it
works locally and on Fly. One partitioned table per tab; monthly snapshots are
idempotent (delete-by-run_id then append)."""
from __future__ import annotations
import os, io, json, base64
from google.cloud import bigquery
from google.oauth2 import service_account

import config as C
from schemas import REGISTRY

_SCOPES = ["https://www.googleapis.com/auth/bigquery",
           "https://www.googleapis.com/auth/cloud-platform"]
_CLUSTER = {
    "social": ["category", "source"],
    "blog": ["curriculum_match", "audience"],
    "competitor": ["competitor"],
    "exec": ["urgency"],
}


def _load_sa_info():
    b64 = os.getenv("MARKET_RESEARCH_BQ_SA_B64") or os.getenv("IK_BQ_SERVICE_ACCOUNT_B64")
    if b64:
        return json.loads(base64.b64decode(b64).decode("utf-8"))
    raw = os.getenv("MARKET_RESEARCH_BQ_SA_JSON") or os.getenv("IK_BQ_SERVICE_ACCOUNT")
    if raw:
        raw = raw.strip()
        if raw.startswith("{"):
            return json.loads(raw)
        if os.path.isfile(raw):
            return json.load(open(raw, encoding="utf-8"))
    if C.BQ_SA_KEY and os.path.isfile(C.BQ_SA_KEY):
        return json.load(open(C.BQ_SA_KEY, encoding="utf-8"))
    return None


def client() -> bigquery.Client:
    info = _load_sa_info()
    if info is None:
        return bigquery.Client(project=C.BQ_PROJECT)
    creds = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    return bigquery.Client(credentials=creds, project=C.BQ_PROJECT)


def _schema(tab_key):
    _, bq = REGISTRY[tab_key]
    return [bigquery.SchemaField(n, t, mode=m) for n, t, m in bq]


def ensure_table(cl: bigquery.Client, tab_key: str) -> bigquery.Table:
    tbl = bigquery.Table(C.fqtn(tab_key), schema=_schema(tab_key))
    tbl.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.MONTH, field="run_date")
    cluster = [c for c in _CLUSTER.get(tab_key, []) ]
    if cluster:
        tbl.clustering_fields = cluster
    return cl.create_table(tbl, exists_ok=True)


def write_snapshot(tab_key: str, rows: list[dict], run_id: str) -> dict:
    """rows = list of model.to_bq() dicts. Idempotent on run_id."""
    cl = client()
    ensure_table(cl, tab_key)
    fqtn = C.fqtn(tab_key)
    cl.query(f"DELETE FROM `{fqtn}` WHERE run_id=@rid",
             job_config=bigquery.QueryJobConfig(query_parameters=[
                 bigquery.ScalarQueryParameter("rid", "STRING", run_id)])).result()
    if rows:
        cfg = bigquery.LoadJobConfig(
            schema=_schema(tab_key),
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON)
        data = "\n".join(json.dumps(r) for r in rows).encode("utf-8")
        cl.load_table_from_file(io.BytesIO(data), fqtn, job_config=cfg).result()
    n = cl.get_table(fqtn).num_rows
    return {"tab": tab_key, "table": fqtn, "loaded": len(rows), "table_total_rows": n}
