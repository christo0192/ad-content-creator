import Link from "next/link";

import { SectionHeading } from "@/components/ui/misc";
import { cn, formatDate, formatINR } from "@/lib/format";
import {
  getCeFreshness,
  getLatestGenerationRunStatus,
  getLeadQualityHeadline,
  getReviewQueuePressure,
  getUnregisteredCampaigns,
  getValueLedgerHeadline,
} from "@/lib/ce-queries";

export const dynamic = "force-dynamic";

/** Weekly pipeline cadence: fresh within 8 days, stale beyond, unknown when never seen. */
const STALE_AFTER_DAYS = 8;

type Health = "healthy" | "stale" | "failed" | "unknown";

function healthOf(latestDate: string | null): Health {
  if (!latestDate) return "unknown";
  const then = new Date(latestDate).getTime();
  if (Number.isNaN(then)) return "unknown";
  const days = (Date.now() - then) / (1000 * 60 * 60 * 24);
  return days <= STALE_AFTER_DAYS ? "healthy" : "stale";
}

const HEALTH_STYLE: Record<Health, { dot: string; text: string; label: string }> = {
  healthy: { dot: "bg-success", text: "text-success", label: "fresh" },
  stale: { dot: "bg-warning", text: "text-warning", label: "stale" },
  failed: { dot: "bg-danger", text: "text-danger", label: "failed" },
  unknown: { dot: "bg-muted/40", text: "text-muted", label: "no data yet" },
};

function VitalTile({
  label,
  value,
  hint,
  href,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  href: string;
  tone?: "default" | "success" | "warning" | "danger";
}) {
  const valueColor =
    tone === "success"
      ? "text-success"
      : tone === "warning"
        ? "text-warning"
        : tone === "danger"
          ? "text-danger"
          : "text-foreground";
  return (
    <Link
      href={href}
      className="group rounded-xl border border-border bg-surface p-4 transition-colors hover:border-accent/40"
    >
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
        {label}
      </p>
      <p className={cn("mt-1 text-2xl font-semibold tracking-tight tabular-nums", valueColor)}>
        {value}
      </p>
      {hint ? <p className="mt-0.5 text-[11px] text-muted">{hint}</p> : null}
      <p className="mt-2 text-[11px] font-medium text-accent opacity-0 transition-opacity group-hover:opacity-100">
        View →
      </p>
    </Link>
  );
}

export default async function HomePage() {
  const [freshness, lastRunStatus, pressure, ledger, leadQuality, unregistered] =
    await Promise.all([
      getCeFreshness(),
      getLatestGenerationRunStatus(),
      getReviewQueuePressure(),
      getValueLedgerHeadline(),
      getLeadQualityHeadline(),
      getUnregisteredCampaigns(),
    ]);

  const healths = freshness.map((f) => ({
    ...f,
    health:
      f.table === "generation_runs" && lastRunStatus === "failed"
        ? ("failed" as Health)
        : healthOf(f.latest_date),
  }));
  const healthyCount = healths.filter((h) => h.health === "healthy").length;
  const staleCount = healths.filter((h) => h.health === "stale").length;
  const failedCount = healths.filter((h) => h.health === "failed").length;
  const unknownCount = healths.filter((h) => h.health === "unknown").length;

  const ledgerRow = ledger.rows[0] ?? null;
  const lqRow = leadQuality.rows[0] ?? null;

  const anyLiveData = healths.some((h) => h.latest_date !== null);

  return (
    <div className="space-y-8">
      {/* Vital signs — small, calm tiles (vision §2) */}
      <section>
        <SectionHeading
          title="Vital Signs"
          description="The whole MIS at a glance. Every tile links to the rows behind it."
        />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <VitalTile
            label="Pipeline Health"
            href="/runs"
            value={
              anyLiveData ? (
                <span className="flex items-baseline gap-2 text-lg">
                  <span className="text-success">{healthyCount} fresh</span>
                  <span className={staleCount > 0 ? "text-warning" : "text-muted/50"}>
                    {staleCount} stale
                  </span>
                  <span className={failedCount > 0 ? "text-danger" : "text-muted/50"}>
                    {failedCount} failed
                  </span>
                </span>
              ) : (
                <span className="text-lg text-muted">no data yet</span>
              )
            }
            hint={
              unknownCount > 0
                ? `${unknownCount} table${unknownCount === 1 ? "" : "s"} never populated`
                : "all tables reporting"
            }
            tone={failedCount > 0 ? "danger" : staleCount > 0 ? "warning" : "default"}
          />
          <VitalTile
            label="Review Queue"
            href="/generation?status=proposed"
            value={
              pressure.unavailable.length === 3 ? (
                <span className="text-lg text-muted">no data yet</span>
              ) : (
                pressure.total.toLocaleString("en-IN")
              )
            }
            hint={
              pressure.unavailable.length === 3
                ? "pipeline hasn't run live"
                : `${pressure.keywordCandidates} keywords · ${pressure.adCopyDrafts} drafts · ${pressure.audienceAngles} angles${pressure.unavailable.length > 0 ? ` · ${pressure.unavailable.length} table(s) unreachable` : ""}`
            }
            tone={pressure.total > 0 ? "warning" : "default"}
          />
          <VitalTile
            label="Value Ledger"
            href="/runs"
            value={
              ledger.error || !ledgerRow ? (
                <span className="text-lg text-muted">no data yet</span>
              ) : ledgerRow.flaggedInrLatestRun !== null ? (
                formatINR(ledgerRow.flaggedInrLatestRun)
              ) : (
                <span className="text-lg text-muted">—</span>
              )
            }
            hint={
              ledger.error || !ledgerRow
                ? "value_ledger not populated"
                : `flagged waste, latest run (${formatDate(ledgerRow.latestRunDate)})${
                    ledgerRow.realizedInrToDate !== null
                      ? ` · ${formatINR(ledgerRow.realizedInrToDate)} realized`
                      : " · nothing realized yet"
                  }`
            }
            tone={ledgerRow?.flaggedInrLatestRun ? "success" : "default"}
          />
          <VitalTile
            label="Unregistered Campaigns"
            href="/registry?unregistered=1"
            value={
              unregistered.error ? (
                <span className="text-lg text-muted">no data yet</span>
              ) : (
                unregistered.rows.length.toLocaleString("en-IN")
              )
            }
            hint={
              unregistered.error
                ? "registry/content tables unreachable"
                : unregistered.rows.length > 0
                  ? "attribution degraded — warn-first"
                  : "all generated content resolves through the registry"
            }
            tone={unregistered.rows.length > 0 ? "danger" : "default"}
          />
        </div>

        {lqRow || leadQuality.error ? (
          <div className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <VitalTile
              label="Quality Leads"
              href="/performance"
              value={
                lqRow?.totalQualityLeads !== null && lqRow
                  ? lqRow.totalQualityLeads!.toLocaleString("en-IN")
                  : "no data yet"
              }
              hint={
                lqRow
                  ? `of ${lqRow.totalLeads?.toLocaleString("en-IN") ?? "—"} leads · period to ${formatDate(lqRow.periodEnd)}`
                  : "lead_quality_scores not populated"
              }
            />
            <VitalTile
              label="Blended CPQL"
              href="/performance"
              value={lqRow?.blendedCpqlInr !== null && lqRow ? formatINR(lqRow.blendedCpqlInr) : "—"}
              hint="segment-level only — per-campaign CPQL pending registry confirmation"
            />
          </div>
        ) : null}
      </section>

      {/* Graph placeholder zone (vision §2 — built next dispatch) */}
      <section>
        <SectionHeading
          title="System Map"
          description="Force-directed live view of the MIS closed loop — Intelligence → Generation → Review → Export → Performance → back."
        />
        <div className="relative flex min-h-72 flex-col items-center justify-center overflow-hidden rounded-xl border border-dashed border-border bg-surface/60 p-8">
          {/* Static skeleton of the future graph so the zone reads as reserved, not broken */}
          <svg
            aria-hidden="true"
            viewBox="0 0 640 200"
            className="pointer-events-none absolute inset-0 h-full w-full opacity-[0.14]"
          >
            <g stroke="currentColor" strokeWidth="1" className="text-accent">
              <line x1="110" y1="100" x2="270" y2="60" />
              <line x1="270" y1="60" x2="410" y2="110" />
              <line x1="410" y1="110" x2="540" y2="70" />
              <line x1="540" y1="70" x2="410" y2="160" />
              <line x1="410" y1="160" x2="270" y2="60" />
            </g>
            <g fill="currentColor" className="text-accent">
              <circle cx="110" cy="100" r="10" />
              <circle cx="270" cy="60" r="14" />
              <circle cx="410" cy="110" r="10" />
              <circle cx="540" cy="70" r="8" />
              <circle cx="410" cy="160" r="8" />
            </g>
          </svg>
          <span className="relative rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-medium text-accent">
            Graph coming in the next dispatch
          </span>
          <p className="relative mt-2 max-w-md text-center text-sm text-muted">
            This zone is reserved for the animated system graph (nodes = pipelines and
            tables, edges = data flow, color = live health). The health data feeding it is
            already live below.
          </p>
        </div>
      </section>

      {/* Per-table freshness strip — the honest data behind "pipeline health" */}
      <section>
        <SectionHeading
          title="Table Freshness"
          description="MAX(run_date / snapshot_date) per Generation-dept table. Unreachable tables show as “no data yet”, never as zero."
        />
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {healths.map((h) => {
            const style = HEALTH_STYLE[h.health];
            return (
              <div
                key={h.table}
                className="flex items-center gap-2.5 rounded-lg border border-border bg-surface px-3 py-2.5"
              >
                <span className={cn("h-2 w-2 shrink-0 rounded-full", style.dot)} />
                <div className="min-w-0 leading-tight">
                  <p className="truncate font-mono text-[11px] text-foreground/80">
                    {h.table}
                  </p>
                  <p className={cn("text-[11px]", style.text)}>
                    {h.latest_date ? formatDate(h.latest_date) : style.label}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
