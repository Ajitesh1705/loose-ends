"use client";

import { useCallback, useEffect, useState } from "react";
import { getLedger, getReview } from "@/lib/api";
import type { LedgerItem, ReviewItem } from "@/lib/types";
import { LedgerView } from "@/components/LedgerView";
import { ReviewView } from "@/components/ReviewView";
import { SourceDrawer } from "@/components/SourceDrawer";
import { DraftPanel } from "@/components/DraftPanel";
import { IngestPanel } from "@/components/IngestPanel";

type View = "ledger" | "review";

export default function App() {
  const [view, setView] = useState<View>("ledger");
  const [ledger, setLedger] = useState<LedgerItem[]>([]);
  const [review, setReview] = useState<ReviewItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [drawer, setDrawer] = useState<LedgerItem | null>(null);
  const [draft, setDraft] = useState<LedgerItem | null>(null);
  const [ingest, setIngest] = useState(false);

  const refresh = useCallback(() => {
    getLedger().then(setLedger).catch((e) => setError(String(e)));
    getReview().then(setReview).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="min-h-screen">
      <header
        className="sticky top-0 z-20 border-b backdrop-blur"
        style={{ background: "color-mix(in srgb, var(--paper) 88%, transparent)", borderColor: "var(--line)" }}
      >
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-3">
          <div className="flex items-baseline gap-3">
            <span className="serif text-lg font-semibold tracking-tight">Loose Ends</span>
            <span className="mono hidden text-[11px] sm:inline" style={{ color: "var(--faint)" }}>
              who owes what · and is it slipping
            </span>
          </div>
          <nav className="flex items-center gap-1">
            <Tab active={view === "ledger"} onClick={() => setView("ledger")}>
              Ledger
            </Tab>
            <Tab active={view === "review"} onClick={() => setView("review")}>
              Review
              {review.length > 0 && (
                <span
                  className="mono ml-1.5 rounded-full px-1.5 text-[10px]"
                  style={{ background: "var(--cooling)", color: "#fff" }}
                >
                  {review.length}
                </span>
              )}
            </Tab>
            <button
              onClick={() => setIngest(true)}
              className="ml-2 rounded-md px-3 py-1.5 text-sm font-medium"
              style={{ background: "var(--accent)", color: "var(--accent-ink)" }}
            >
              Ingest
            </button>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-10">
        {error && (
          <p className="mono mb-6 rounded border px-3 py-2 text-xs" style={{ borderColor: "var(--line)", color: "var(--overdue)" }}>
            {error}
          </p>
        )}
        {view === "ledger" ? (
          <LedgerView items={ledger} onOpen={setDrawer} />
        ) : (
          <ReviewView items={review} onChanged={refresh} />
        )}
      </main>

      <SourceDrawer
        item={drawer}
        onClose={() => setDrawer(null)}
        onDraft={(i) => {
          setDrawer(null);
          setDraft(i);
        }}
      />
      <DraftPanel item={draft} onClose={() => setDraft(null)} />
      {ingest && (
        <IngestPanel
          onClose={() => setIngest(false)}
          onRefresh={refresh}
        />
      )}
    </div>
  );
}

function Tab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className="rounded-md px-3 py-1.5 text-sm font-medium"
      style={{
        background: active ? "var(--ink)" : "transparent",
        color: active ? "var(--surface)" : "var(--muted)",
      }}
    >
      {children}
    </button>
  );
}
