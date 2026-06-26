import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

import { SidebarNav } from "@/components/sidebar-nav";
import { getLatestRunDate } from "@/lib/queries";
import { formatDate } from "@/lib/format";

const inter = Inter({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "AI/ML India — Market Research",
  description:
    "Read-only market intelligence on AI/ML hiring demand, social signals, content trends, and competitor positioning in India.",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Fetch the latest snapshot date for the header. Tolerate BQ errors so the
  // shell always renders even if the data layer is briefly unavailable.
  let latestRunDate: string | null = null;
  try {
    latestRunDate = await getLatestRunDate();
  } catch {
    latestRunDate = null;
  }

  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-background text-foreground">
        <div className="flex min-h-screen">
          {/* Sidebar */}
          <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-surface md:flex">
            <div className="flex h-16 items-center gap-2.5 border-b border-border px-5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-sm font-bold text-white">
                IK
              </span>
              <div className="leading-tight">
                <p className="text-sm font-semibold text-foreground">
                  Market Research
                </p>
                <p className="text-[11px] text-muted">AI/ML · India</p>
              </div>
            </div>
            <SidebarNav />
            <div className="mt-auto border-t border-border px-5 py-4">
              <p className="text-[11px] text-muted">
                Latest snapshot
                <br />
                <span className="font-medium text-slate-700">
                  {latestRunDate ? formatDate(latestRunDate) : "—"}
                </span>
              </p>
            </div>
          </aside>

          {/* Main column */}
          <div className="flex min-w-0 flex-1 flex-col">
            <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-border bg-surface/80 px-6 backdrop-blur">
              <div>
                <h1 className="text-base font-semibold tracking-tight text-foreground">
                  AI/ML India — Market Research
                </h1>
                <p className="text-xs text-muted">
                  Hiring demand · Social signals · Content trends · Competitor intel
                </p>
              </div>
              <div className="hidden items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 sm:flex">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
                </span>
                Live from BigQuery
              </div>
            </header>

            <main className="flex-1 px-6 py-6 md:px-8">{children}</main>

            <footer className="border-t border-border px-6 py-4 md:px-8">
              <p className="text-xs text-muted">
                AI/ML India Market Research{" "}
                <span className="text-slate-300">·</span> updated{" "}
                {latestRunDate ? formatDate(latestRunDate) : "—"}
              </p>
            </footer>
          </div>
        </div>
      </body>
    </html>
  );
}
