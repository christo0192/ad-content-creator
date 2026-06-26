import * as React from "react";

import { cn } from "@/lib/format";

type BadgeVariant =
  | "default"
  | "outline"
  | "critical"
  | "high"
  | "medium"
  | "low"
  | "success"
  | "info";

const VARIANTS: Record<BadgeVariant, string> = {
  default: "bg-slate-100 text-slate-700 border-slate-200",
  outline: "bg-transparent text-slate-600 border-slate-300",
  critical: "bg-rose-50 text-rose-700 border-rose-200",
  high: "bg-amber-50 text-amber-700 border-amber-200",
  medium: "bg-slate-50 text-slate-600 border-slate-200",
  low: "bg-slate-50 text-slate-500 border-slate-200",
  success: "bg-emerald-50 text-emerald-700 border-emerald-200",
  info: "bg-indigo-50 text-indigo-700 border-indigo-200",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}

/** Map an urgency string to a badge variant (CRITICAL=red, HIGH=amber, else slate). */
export function urgencyVariant(urgency: string | null | undefined): BadgeVariant {
  switch ((urgency ?? "").toUpperCase()) {
    case "CRITICAL":
      return "critical";
    case "HIGH":
      return "high";
    case "MEDIUM":
      return "medium";
    default:
      return "low";
  }
}
