"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";
import {
  LayoutDashboard,
  Briefcase,
  MessageSquare,
  Newspaper,
  Swords,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/format";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const NAV: NavItem[] = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/jobs", label: "Jobs", icon: Briefcase },
  { href: "/social", label: "Social", icon: MessageSquare },
  { href: "/blog", label: "Blog", icon: Newspaper },
  { href: "/competitor", label: "Competitor", icon: Swords },
];

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col gap-1 px-3 py-2" aria-label="Primary">
      {NAV.map((item) => {
        const active =
          item.href === "/"
            ? pathname === "/"
            : pathname.startsWith(item.href);
        const ItemIcon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-indigo-50 text-accent"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
            )}
          >
            <ItemIcon
              aria-hidden="true"
              strokeWidth={active ? 2.2 : 1.8}
              className={cn(
                "h-[18px] w-[18px] shrink-0",
                active ? "text-accent" : "text-slate-400",
              )}
            />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
