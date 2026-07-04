"""BigQuery writer for the Job Market Demand tab.

- Authenticates with the `claude-code-dev-bq@` service-account key.
- Ensures the target table exists (partitioned by run_date, clustered by
  normalized_role + company_tier) — does NOT create the dataset (the dev SA
  lacks datasets.create; the dataset must already exist).
- Loads a monthly snapshot idempotently: deletes any existing rows for the same
  run_id, then appends. Re-running a month is therefore safe.
"""
from __future__ import annotations
import os, json, base64
from google.cloud import bigquery
from google.oauth2 import service_account

import config as C
from schema import BQ_SCHEMA

_SCOPES = ["https://www.googleapis.com/auth/bigquery",
           "https://www.googleapis.com/auth/cloud-platform"]


def _load_sa_info() -> dict | None:
    """Resolve service-account creds across local + Fly.io deployments.

    Precedence (first hit wins):
      1. MARKET_RESEARCH_BQ_SA_B64 / IK_BQ_SERVICE_ACCOUNT_B64  (base64 JSON — Fly secret)
      2. MARKET_RESEARCH_BQ_SA_JSON / IK_BQ_SERVICE_ACCOUNT     (inline JSON or file path)
      3. config.BQ_SA_KEY                                        (local file path)
      4. None -> caller falls back to Application Default Credentials
    """
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


def _client() -> bigquery.Client:
    info = _load_sa_info()
    if info is None:
        # ADC (Fly workload identity / gcloud) — note: a bare gcloud USER cred
        # cannot run BQ jobs without serviceusage.services.use; prefer an SA.
        return bigquery.Client(project=C.BQ_PROJECT)
    creds = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    return bigquery.Client(credentials=creds, project=C.BQ_PROJECT)


def _bq_schema():
    return [bigquery.SchemaField(n, t, mode=m) for n, t, m in BQ_SCHEMA]


def ensure_table(client: bigquery.Client) -> bigquery.Table:
    table = bigquery.Table(C.BQ_FQTN, schema=_bq_schema())
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.MONTH, field="run_date")
    table.clustering_fields = ["normalized_role", "company_tier"]
    return client.create_table(table, exists_ok=True)


def write_snapshot(rows: list[dict], run_id: str, dry_run: bool = False) -> dict:
    """rows = list of JobDemandRow.to_bq() dicts. Returns a result summary."""
    client = _client()
    ensure_table(client)

    if dry_run:
        # validate-load into a temp disposition without touching the table?
        # We DO write in dry-run too (dry-run here means "no Apify spend", not
        # "no BQ write") so the verification is genuinely end-to-end.
        pass

    # Idempotent: clear this run_id first (safe re-run of a month).
    client.query(
        f"DELETE FROM `{C.BQ_FQTN}` WHERE run_id = @rid",
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("rid", "STRING", run_id)]),
    ).result()

    job_config = bigquery.LoadJobConfig(
        schema=_bq_schema(),
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )
    data = "\n".join(json.dumps(r) for r in rows).encode("utf-8")
    import io
    load = client.load_table_from_file(
        io.BytesIO(data), C.BQ_FQTN, job_config=job_config)
    load.result()

    tbl = client.get_table(C.BQ_FQTN)
    return {"loaded": len(rows), "table": C.BQ_FQTN, "table_total_rows": tbl.num_rows,
            "run_id": run_id}


def query_summary(run_id: str) -> list[dict]:
    """Demand-by-role for one run, for a quick post-write sanity check."""
    client = _client()
    sql = f"""
      SELECT normalized_role, COUNT(*) n,
             COUNTIF(is_emerging) emerging,
             COUNTIF(in_window) in_window
      FROM `{C.BQ_FQTN}` WHERE run_id=@rid
      GROUP BY normalized_role ORDER BY n DESC
    """
    job = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("rid", "STRING", run_id)]))
    return [dict(r) for r in job.result()]
