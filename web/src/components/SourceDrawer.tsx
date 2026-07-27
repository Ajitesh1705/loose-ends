"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { getSource } from "@/lib/api";
import { bandColor, directionLabel, dueLabel, fmtDate } from "@/lib/format";
import { KIND_LABEL, type LedgerItem, type SourceDetail } from "@/lib/types";
import { DecayMark } from "./DecayMark";

function Highlighted({ text, start, end }: { text: string; start: number; end: number }) {
  const markRef = useRef<HTMLElement>(null);
  useEffect(() => {
    markRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [start, end]);
  return (
    <pre className="whitespace-pre-wrap font-[inherit] text-[14px] leading-relaxed">
      {text.slice(0, start)}
      <mark className="evidence" ref={markRef as never}>
        {text.slice(start, end)}
      </mark>
      {text.slice(end)}
    </pre>
  );
}

export function SourceDrawer({
  item,
  onClose,
  onDraft,
}: {
  item: LedgerItem | null;
  onClose: () => void;
  onDraft: (item: LedgerItem) => void;
}) {
  const [sources, setSources] = useState<Record<string, SourceDetail>>({});
  const [active, setActive] = useState(0);

  useEffect(() => {
    setActive(0);
    if (!item) return;
    const ids = Array.from(new Set(item.evidence.map((e) => e.source_id)));
    Promise.all(ids.map(getSource)).then((list) => {
      const map: Record<string, SourceDetail> = {};
      list.forEach((s) => (map[s.id] = s));
      setSources(map);
    });
  }, [item]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const activeEvidence = item?.evidence[active];
  const activeSource = activeEvidence ? sources[activeEvidence.source_id] : undefined;

  if (!item) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div
        className="absolute inset-0 bg-black/20"
        onClick={onClose}
        aria-hidden
      />
      <aside
        className="relative flex h-full w-full max-w-xl flex-col border-l shadow-2xl"
        style={{ background: "var(--surface)", borderColor: "var(--line-strong)" }}
        role="dialog"
        aria-label="Source and provenance"
      >
        <header className="border-b px-6 py-5" style={{ borderColor: "var(--line)" }}>
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="eyebrow mb-1">
                {directionLabel(item.direction)} · {item.contact_name ?? "unknown"}
              </div>
              <h2 className="serif text-xl leading-snug">{item.what}</h2>
              <div className="mono mt-2 text-xs" style={{ color: "var(--muted)" }}>
                due {dueLabel(item.due_at, item.due_precision)} · {item.due_precision}
              </div>
            </div>
            <button
              onClick={onClose}
              className="eyebrow shrink-0 rounded px-2 py-1"
              style={{ color: "var(--muted)" }}
            >
              Close ✕
            </button>
          </div>
          <div className="mt-3">
            <DecayMark decay={item.decay} />
          </div>
          {item.merges.length > 0 && (
            <div
              className="mono mt-3 rounded-md px-3 py-2 text-[12px]"
              style={{ background: "var(--paper)", color: "var(--muted)" }}
            >
              ⑃ merged from {item.evidence.length} sources ·{" "}
              {item.merges[0].reason}
              {item.merges[0].similarity != null &&
                ` · sim ${item.merges[0].similarity.toFixed(2)}`}
            </div>
          )}
        </header>

        {/* evidence tabs */}
        <div
          className="flex gap-1 overflow-x-auto border-b px-6 py-2"
          style={{ borderColor: "var(--line)" }}
        >
          {item.evidence.map((e, i) => {
            const s = sources[e.source_id];
            const label = s
              ? `${KIND_LABEL[s.kind] ?? s.kind} · ${fmtDate(s.channel_ts, {
                  month: "short",
                  day: "numeric",
                })}`
              : "…";
            return (
              <button
                key={e.id}
                onClick={() => setActive(i)}
                className="mono whitespace-nowrap rounded px-3 py-1 text-xs"
                style={{
                  background: i === active ? "var(--ink)" : "transparent",
                  color: i === active ? "var(--surface)" : "var(--muted)",
                }}
              >
                {label}
              </button>
            );
          })}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {activeSource && activeEvidence ? (
            <Highlighted
              text={activeSource.raw_text}
              start={activeEvidence.start_char}
              end={activeEvidence.end_char}
            />
          ) : (
            <p className="mono text-sm" style={{ color: "var(--faint)" }}>
              loading source…
            </p>
          )}
        </div>

        <footer className="border-t px-6 py-4" style={{ borderColor: "var(--line)" }}>
          <button
            onClick={() => onDraft(item)}
            className="w-full rounded-md py-2.5 text-sm font-medium"
            style={{ background: "var(--accent)", color: "var(--accent-ink)" }}
          >
            Draft a follow-up
          </button>
        </footer>
      </aside>
    </div>
  );
}
