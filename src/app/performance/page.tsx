import { SectionHeading } from "@/components/ui/misc";

export const dynamic = "force-static";

/**
 * Performance pipeline page — stub. Will surface the segment funnel and
 * anomaly feed from the existing pmis_ tables in a later dispatch
 * (docs/dashboard-vision.md §3).
 */
export default function PerformancePage() {
  return (
    <div className="space-y-6">
      <SectionHeading
        title="Performance"
        description="Segment funnel, anomaly surface, CPQL trends."
      />
      <div className="flex min-h-64 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-surface p-8 text-center">
        <span className="rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-medium text-accent">
          Coming soon
        </span>
        <p className="max-w-md text-sm text-muted">
          This page will read the existing pmis_ performance tables (segment funnel,
          anomalies, CPQL) in a future dispatch. Nothing here is wired up yet — no fake
          numbers.
        </p>
      </div>
    </div>
  );
}
