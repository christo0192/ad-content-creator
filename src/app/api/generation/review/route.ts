import { NextResponse } from "next/server";

import { getBq, CE_TABLES } from "@/lib/bq";

/**
 * ============================================================================
 * THE DASHBOARD'S ONLY WRITE SURFACE.
 * ============================================================================
 * Every other route/query in this app is read-only BigQuery access. This is
 * the single exception: a parameterized DML UPDATE, hard-allowlisted below,
 * used by the Generation review queue's Approve/Reject buttons.
 *
 * Allowlist (all three axes are enforced, not just documented):
 *   - table:  ce_keyword_candidates | ce_ad_copy_drafts | ce_audience_angles
 *   - column: status, reviewed_by, reviewed_at  (nothing else is ever SET)
 *   - status value: "approved" | "rejected"
 *
 * The WHERE clause is built from a fixed, per-table set of identifying
 * columns (never arbitrary caller-supplied column names) and every value is
 * bound as a named BigQuery query parameter — no string interpolation of
 * user input into SQL text anywhere in this file.
 * ============================================================================
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ALLOWED_TABLES = {
  keyword_candidates: CE_TABLES.keywordCandidates,
  ad_copy_drafts: CE_TABLES.adCopyDrafts,
  audience_angles: CE_TABLES.audienceAngles,
} as const;

type AllowedTable = keyof typeof ALLOWED_TABLES;

const ALLOWED_STATUSES = new Set(["approved", "rejected"]);

/** Per-table identifying columns allowed in the WHERE clause. Every entry must be present in the request's `where` object. */
const WHERE_KEYS: Record<AllowedTable, readonly string[]> = {
  keyword_candidates: ["run_date", "run_id", "campaign_name", "keyword"],
  ad_copy_drafts: ["run_date", "run_id", "campaign_name", "asset_id"],
  audience_angles: ["run_date", "run_id", "campaign_name", "asset_id"],
};

interface ReviewRequestBody {
  table?: unknown;
  status?: unknown;
  reviewed_by?: unknown;
  where?: unknown;
}

function badRequest(message: string) {
  return NextResponse.json({ ok: false, error: message }, { status: 400 });
}

export async function POST(req: Request) {
  let body: ReviewRequestBody;
  try {
    body = await req.json();
  } catch {
    return badRequest("Request body must be valid JSON.");
  }

  const { table, status, where } = body;

  if (typeof table !== "string" || !(table in ALLOWED_TABLES)) {
    return badRequest(
      `"table" must be one of: ${Object.keys(ALLOWED_TABLES).join(", ")}.`,
    );
  }
  const tableKey = table as AllowedTable;

  if (typeof status !== "string" || !ALLOWED_STATUSES.has(status)) {
    return badRequest(
      `"status" must be one of: ${[...ALLOWED_STATUSES].join(", ")}.`,
    );
  }

  if (where === null || typeof where !== "object" || Array.isArray(where)) {
    return badRequest('"where" must be an object of identifying columns.');
  }
  const whereObj = where as Record<string, unknown>;

  const requiredKeys = WHERE_KEYS[tableKey];
  const params: Record<string, unknown> = {};
  for (const key of requiredKeys) {
    const value = whereObj[key];
    if (typeof value !== "string" || value.length === 0) {
      return badRequest(
        `"where.${key}" is required (string) for table "${tableKey}".`,
      );
    }
    params[key] = value;
  }
  // Reject anything beyond the allowlisted keys — no silent extra columns.
  const extraKeys = Object.keys(whereObj).filter(
    (k) => !requiredKeys.includes(k),
  );
  if (extraKeys.length > 0) {
    return badRequest(
      `Unexpected "where" keys for table "${tableKey}": ${extraKeys.join(", ")}.`,
    );
  }

  const reviewedByRaw = body.reviewed_by;
  const reviewedBy =
    typeof reviewedByRaw === "string" && reviewedByRaw.trim().length > 0
      ? reviewedByRaw.trim().slice(0, 120)
      : "dashboard";

  params.status = status;
  params.reviewedBy = reviewedBy;

  const whereSql = requiredKeys.map((k) => `${k} = @${k}`).join(" AND ");
  const fullyQualifiedTable = ALLOWED_TABLES[tableKey];

  const sql = `
    UPDATE \`${fullyQualifiedTable}\`
       SET status = @status,
           reviewed_by = @reviewedBy,
           reviewed_at = CURRENT_TIMESTAMP()
     WHERE ${whereSql}
  `;

  try {
    const [job] = await getBq().query({
      query: sql,
      params,
      // run_date is a DATE column; the client library would otherwise infer
      // a plain "YYYY-MM-DD" JS string as STRING and BigQuery would reject
      // `DATE = STRING` in the WHERE clause. Every other bound param here is
      // a STRING column, which matches the library's default inference.
      types: requiredKeys.includes("run_date") ? { run_date: "DATE" } : undefined,
      useLegacySql: false,
    });
    // BigQuery's query() for DML returns an empty rows array; row count is on
    // the job metadata (numDmlAffectedRows).
    const metadata = (job as unknown as { metadata?: unknown }).metadata;
    let affected: number | null = null;
    if (
      metadata &&
      typeof metadata === "object" &&
      "statistics" in metadata
    ) {
      const stats = (metadata as Record<string, unknown>).statistics as
        | Record<string, unknown>
        | undefined;
      const dml = stats?.query as Record<string, unknown> | undefined;
      const raw = dml?.dmlStats as Record<string, unknown> | undefined;
      const inserted = raw?.updatedRowCount;
      affected =
        typeof inserted === "string" || typeof inserted === "number"
          ? Number(inserted)
          : null;
    }
    return NextResponse.json({ ok: true, rowsAffected: affected });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    // BQ errors (missing table, permission denied, streaming-buffer conflict)
    // are surfaced honestly to the caller rather than throwing a 500 page.
    return NextResponse.json(
      { ok: false, error: message.slice(0, 500) },
      { status: 502 },
    );
  }
}
