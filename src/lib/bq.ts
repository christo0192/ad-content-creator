import "server-only";

import { existsSync } from "node:fs";
import { BigQuery } from "@google-cloud/bigquery";

/**
 * SERVER-ONLY BigQuery data layer.
 *
 * This module MUST NEVER be imported by a client component. The `server-only`
 * import above turns any accidental client import into a build-time error.
 *
 * Credential precedence (server-side only):
 *   1. env `MARKET_RESEARCH_BQ_SA_B64` -> base64-decode -> JSON.parse -> `credentials`
 *   2. else local key file at LOCAL_KEY_FILE via `keyFilename`
 *
 * Never log, print, or echo the SA key contents.
 */

export const PROJECT_ID = "ik-marketing-data";
export const DATASET = "Market_Research";

/** Local service-account key file used for local development. */
const LOCAL_KEY_FILE = "C:\\Users\\Admin\\.gcp-keys\\market-research-bq.json";

/**
 * Fully-qualified table names: `ik-marketing-data.Market_Research.<table>`.
 */
export const TABLES = {
  jobs: `${PROJECT_ID}.${DATASET}.job_market_demand`,
  social: `${PROJECT_ID}.${DATASET}.social_trends`,
  blog: `${PROJECT_ID}.${DATASET}.blog_publications`,
  competitor: `${PROJECT_ID}.${DATASET}.competitor_intel`,
  exec: `${PROJECT_ID}.${DATASET}.executive_summary`,
} as const;

export type TableKey = keyof typeof TABLES;

/**
 * Builds BigQuery client options based on the credential precedence.
 * Does not expose or log any secret material.
 */
function buildClientOptions(): ConstructorParameters<typeof BigQuery>[0] {
  const base = { projectId: PROJECT_ID } as const;

  const b64 = process.env.MARKET_RESEARCH_BQ_SA_B64;
  if (b64 && b64.trim().length > 0) {
    let credentials: Record<string, unknown>;
    try {
      const json = Buffer.from(b64, "base64").toString("utf8");
      credentials = JSON.parse(json);
    } catch {
      // Do not include the decoded contents in the error — avoid leaking secrets.
      throw new Error(
        "MARKET_RESEARCH_BQ_SA_B64 is set but is not valid base64-encoded JSON.",
      );
    }
    return { ...base, credentials };
  }

  if (existsSync(LOCAL_KEY_FILE)) {
    return { ...base, keyFilename: LOCAL_KEY_FILE };
  }

  throw new Error(
    "No BigQuery credentials found. Set MARKET_RESEARCH_BQ_SA_B64 (base64 of the " +
      "service-account JSON) or provide the local key file.",
  );
}

/**
 * Singleton BigQuery client. Cached across hot reloads in development via
 * globalThis so we don't create a new client per request.
 */
const globalForBq = globalThis as unknown as { __bqClient?: BigQuery };

export const bq: BigQuery =
  globalForBq.__bqClient ?? new BigQuery(buildClientOptions());

if (process.env.NODE_ENV !== "production") {
  globalForBq.__bqClient = bq;
}

/**
 * Generic, parameterized query helper.
 *
 * @param sql    Standard SQL. Use `@name` placeholders with the `params` map.
 * @param params Named query parameters.
 * @returns      Array of typed rows.
 */
export async function query<T = Record<string, unknown>>(
  sql: string,
  params?: Record<string, unknown>,
): Promise<T[]> {
  const [rows] = await bq.query({
    query: sql,
    params,
    // Standard SQL is the default; set explicitly for clarity/safety.
    useLegacySql: false,
  });
  return rows as T[];
}
