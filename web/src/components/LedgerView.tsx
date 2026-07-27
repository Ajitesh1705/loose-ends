"use client";

import { directionLabel, dueLabel } from "@/lib/format";
import { BAND_LABEL, BAND_ORDER, type Band, type LedgerItem } from "@/lib/types";
import { DecayMark } from "./DecayMark";

function Row({ item, onOpen }: { item: LedgerItem; onOpen: (i: LedgerItem) => void }) {
  const snippet = item.evidence[0]?.quote ?? "";
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onOpen(item)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen(item);
        }
      }}
      className="grid w-full cursor-pointer grid-cols-[7rem_1fr] items-start gap-4 border-b py-4 text-left transition-colors hover:bg-black/[0.015]"
      style={{ borderColor: "var(--line)" }}
    >
      <div className="pt-0.5">
        <DecayMark decay={item.decay} />
      </div>
      <div className="min-w-0">
        <div className="flex items-baseline justify-between gap-3">
          <span className="serif truncate text-[15px]">{item.what}</span>
          <span className="mono shrink-0 text-xs" style={{ color: "var(--muted)" }}>
            {dueLabel(item.due_at, item.due_precision)}
          </span>
        </div>
        <div className="mono mt-0.5 text-xs" style={{ color: "var(--faint)" }}>
          {directionLabel(item.direction)} · {item.contact_name ?? "unknown"}
          {item.merges.length > 0 && (
            <span style={{ color: "var(--accent)" }}> · ⑃ {item.evidence.length} sources</span>
          )}
        </div>
        {snippet && (
          <p className="mt-1 truncate text-[13px] italic" style={{ color: "var(--muted)" }}>
            “{snippet}”
          </p>
        )}
      </div>
    </div>
  );
}

export function LedgerView({
  items,
  onOpen,
}: {
  items: LedgerItem[];
  onOpen: (i: LedgerItem) => void;
}) {
  const groups = BAND_ORDER.map(
    (band) => [band, items.filter((i) => i.decay.band === band)] as [Band, LedgerItem[]]
  ).filter(([, g]) => g.length > 0);

  if (items.length === 0) {
    return (
      <p className="mono py-16 text-center text-sm" style={{ color: "var(--faint)" }}>
        Nothing in the ledger yet. Ingest a conversation to begin.
      </p>
    );
  }

  return (
    <div className="space-y-10">
      {groups.map(([band, group]) => (
        <section key={band}>
          <div className="mb-1 flex items-baseline gap-3">
            <h2 className="eyebrow" style={{ color: `var(--${band})` }}>
              {BAND_LABEL[band]}
            </h2>
            <span className="mono text-xs" style={{ color: "var(--faint)" }}>
              {group.length}
            </span>
          </div>
          <div>
            {group.map((item) => (
              <Row key={item.id} item={item} onOpen={onOpen} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
