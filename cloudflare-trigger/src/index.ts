// Cloudflare Worker — monthly trigger for the Intelligence department's two
// Fly batch machines (added 2026-10-27). The Fly-native `--schedule monthly`
// on both machines never fired, so this Worker is the ONLY scheduler.
//
// One cron (wrangler.toml, "30 3 1,2 * *" = 03:30 UTC / 09:00 IST on the 1st
// and 2nd — a single trigger to stay under the per-account cron quota), then
// dispatch on the UTC day of the scheduled time:
//   day 1 -> jobs   (ik-market-research-jobs,   job_market_agent/run_monthly.py)
//   day 2 -> weekly (ik-market-research-weekly, market_research/run_weekly.py,
//            which reads the jobs snapshot written the day before)
// It only POSTs the Fly Machines API `start`; each machine runs its job and
// stops on exit. Shape cloned from MIS cloudflare-trigger/src/index.ts.

export interface Env {
  FLY_TOKEN_JOBS: string; // secret — Fly deploy token scoped to ik-market-research-jobs
  FLY_TOKEN_WEEKLY: string; // secret — Fly deploy token scoped to ik-market-research-weekly
  JOBS_APP: string; // var
  JOBS_MACHINE_ID: string; // var
  WEEKLY_APP: string; // var
  WEEKLY_MACHINE_ID: string; // var
}

/** Must equal wrangler.toml [triggers].crons[0] — test/index.test.ts guards it. */
export const CRON = "30 3 1,2 * *";
export const JOBS_DAY = 1;
export const WEEKLY_DAY = 2;

export interface Target {
  label: "jobs" | "weekly";
  app: string;
  machineId: string;
  token: string;
}

/** Which machine to start on this UTC day of the month (null = none). */
export function targetForDay(dayOfMonthUtc: number, env: Env): Target | null {
  switch (dayOfMonthUtc) {
    case JOBS_DAY:
      return { label: "jobs", app: env.JOBS_APP, machineId: env.JOBS_MACHINE_ID, token: env.FLY_TOKEN_JOBS };
    case WEEKLY_DAY:
      return { label: "weekly", app: env.WEEKLY_APP, machineId: env.WEEKLY_MACHINE_ID, token: env.FLY_TOKEN_WEEKLY };
    default:
      return null;
  }
}

/** Fly deploy tokens (`fly tokens create deploy`) print as "FlyV1 fm2_…" and are
 *  sent as-is, the way flyctl sends macaroons; anything else (a Personal Access
 *  Token, like the MIS workers use) goes as Bearer. Trimmed because a token
 *  piped into `wrangler secret put` can carry a trailing newline. */
export function authHeader(token: string): string {
  const t = (token ?? "").trim();
  return t.startsWith("FlyV1 ") ? t : `Bearer ${t}`;
}

export function startUrl(t: Target): string {
  return `https://api.machines.dev/v1/apps/${encodeURIComponent(t.app)}/machines/${encodeURIComponent(t.machineId)}/start`;
}

export async function startMachine(
  t: Target,
  fetchImpl: typeof fetch = fetch,
): Promise<{ ok: boolean; status: number; body: string }> {
  const res = await fetchImpl(startUrl(t), {
    method: "POST",
    headers: { Authorization: authHeader(t.token), "Content-Type": "application/json" },
  });
  return { ok: res.ok, status: res.status, body: (await res.text()).slice(0, 500) };
}

function iso(ms: number): string {
  return Number.isFinite(ms) ? new Date(ms).toISOString() : String(ms);
}

export default {
  async scheduled(event: ScheduledController, env: Env, _ctx: ExecutionContext): Promise<void> {
    const when = iso(event.scheduledTime);
    let label = "trigger";
    // Never throw: Cloudflare retries a scheduled event whose handler throws,
    // which would double-start a paid batch run (same rule as the MIS Worker).
    // Every failure is logged and accepted; the token is never logged.
    try {
      const day = new Date(event.scheduledTime).getUTCDate();
      const t = targetForDay(day, env);
      if (!t) {
        console.warn(
          `[${when}] cron '${event.cron}' on UTC day ${day}: no target (jobs = day ${JOBS_DAY}, weekly = day ${WEEKLY_DAY}) — nothing started`,
        );
        return;
      }
      label = t.label;
      if (!t.app || !t.machineId || !(t.token ?? "").trim()) {
        console.error(`[${when}] ${t.label}: missing app/machine/token config — not started`);
        return;
      }
      const r = await startMachine(t);
      if (r.ok) {
        console.log(`[${when}] ${t.label} start OK (${r.status}) ${t.app}/${t.machineId}`);
      } else {
        console.error(`[${when}] ${t.label} start FAILED (${r.status}) ${t.app}/${t.machineId}: ${r.body}`);
      }
    } catch (err) {
      console.error(`[${when}] ${label} fetch error:`, err);
    }
  },

  async fetch(_request: Request, _env: Env): Promise<Response> {
    return new Response("Scheduled-only Worker (ik-intelligence-trigger).", { status: 405 });
  },
} satisfies ExportedHandler<Env>;
