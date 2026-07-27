"use client";

import { useState } from "react";
import { confirmCommitment, rejectCommitment } from "@/lib/api";
import { directionLabel } from "@/lib/format";
import type { ReviewItem } from "@/lib/types";

function Card({ item, onDone }: { item: ReviewItem; onDone: () => void }) {
  const [what, setWhat] = useState(item.what);
  const [who, setWho] = useState(item.contact_name ?? "");
  const [due, setDue] = useState(item.due_at ? item.due_at.slice(0, 10) : "");
  const [busy, setBusy] = useState(false);

  async function confirm() {
    setBusy(true);
    await confirmCommitment(item.id, {
      what,
      who,
      due_at: due ? new Date(due + "T17:00:00Z").toISOString() : null,
    });
    onDone();
  }
  async function reject() {
    setBusy(true);
    await rejectCommitment(item.id);
    onDone();
  }

  return (
    <div
      className="mx-auto max-w-xl rounded-lg border p-6 shadow-sm"
      style={{ background: "var(--surface)", borderColor: "var(--line-strong)" }}
    >
      <div className="eyebrow mb-3">
        {directionLabel(item.direction)} · needs a human
      </div>

      {/* the ambiguity note — the point of this screen */}
      <div
        className="mb-5 rounded-md border-l-2 p-3 text-sm leading-relaxed"
        style={{ borderColor: "var(--cooling)", background: "var(--paper)" }}
      >
        {item.ambiguity_note}
      </div>

      {/* duplicate side-by-side */}
      {item.duplicate_of && (
        <div className="mb-5">
          <div className="eyebrow mb-2">Possible duplicate</div>
          <div className="grid grid-cols-2 gap-3 text-[13px]">
            <blockquote
              className="border-l-2 pl-2"
              style={{ borderColor: "var(--line-strong)", color: "var(--muted)" }}
            >
              <div className="mono mb-1 text-[10px] uppercase">This</div>
              {item.evidence[0]?.quote}
            </blockquote>
            <blockquote
              className="border-l-2 pl-2"
              style={{ borderColor: "var(--accent)", color: "var(--muted)" }}
            >
              <div className="mono mb-1 text-[10px] uppercase">Existing</div>
              {item.duplicate_of.quote}
            </blockquote>
          </div>
        </div>
      )}

      <div className="space-y-3">
        <Field label="What">
          <input
            className="w-full rounded border px-3 py-2 text-sm"
            style={{ borderColor: "var(--line)" }}
            value={what}
            onChange={(e) => setWhat(e.target.value)}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Who">
            <input
              className="w-full rounded border px-3 py-2 text-sm"
              style={{ borderColor: "var(--line)" }}
              value={who}
              onChange={(e) => setWho(e.target.value)}
            />
          </Field>
          <Field label="Due">
            <input
              type="date"
              className="mono w-full rounded border px-3 py-2 text-sm"
              style={{ borderColor: "var(--line)" }}
              value={due}
              onChange={(e) => setDue(e.target.value)}
            />
          </Field>
        </div>
      </div>

      <div className="mt-6 flex gap-2">
        <button
          disabled={busy}
          onClick={confirm}
          className="flex-1 rounded-md py-2.5 text-sm font-medium disabled:opacity-50"
          style={{ background: "var(--accent)", color: "var(--accent-ink)" }}
        >
          Confirm to ledger
        </button>
        <button
          disabled={busy}
          onClick={reject}
          className="rounded-md border px-4 py-2.5 text-sm font-medium disabled:opacity-50"
          style={{ borderColor: "var(--line-strong)", color: "var(--muted)" }}
        >
          Reject
        </button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="eyebrow mb-1 block">{label}</span>
      {children}
    </label>
  );
}

export function ReviewView({
  items,
  onChanged,
}: {
  items: ReviewItem[];
  onChanged: () => void;
}) {
  if (items.length === 0) {
    return (
      <p className="mono py-16 text-center text-sm" style={{ color: "var(--faint)" }}>
        Review queue is clear. Everything confident is in the ledger.
      </p>
    );
  }
  const item = items[0];
  return (
    <div>
      <p className="mono mb-4 text-center text-xs" style={{ color: "var(--faint)" }}>
        {items.length} awaiting review · one at a time
      </p>
      <Card key={item.id} item={item} onDone={onChanged} />
    </div>
  );
}
