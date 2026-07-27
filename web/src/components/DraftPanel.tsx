"use client";

import { useEffect, useState } from "react";
import { draftCommitment } from "@/lib/api";
import type { DraftResponse, LedgerItem } from "@/lib/types";

const TONES: DraftResponse["tone"][] = ["warm", "direct", "brief"];

export function DraftPanel({
  item,
  onClose,
}: {
  item: LedgerItem | null;
  onClose: () => void;
}) {
  const [tone, setTone] = useState<DraftResponse["tone"]>("warm");
  const [draft, setDraft] = useState<DraftResponse | null>(null);
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate(t: DraftResponse["tone"]) {
    if (!item) return;
    setLoading(true);
    setError(null);
    try {
      const d = await draftCommitment(item.id, t);
      setDraft(d);
      setBody(d.body);
    } catch (e) {
      setError(e instanceof Error ? e.message : "draft failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (item) {
      setTone("warm");
      setDraft(null);
      setBody("");
      generate("warm");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item]);

  if (!item) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} aria-hidden />
      <div
        className="relative grid w-full max-w-3xl grid-cols-1 overflow-hidden rounded-lg border shadow-2xl md:grid-cols-[1fr_18rem]"
        style={{ background: "var(--surface)", borderColor: "var(--line-strong)" }}
        role="dialog"
        aria-label="Draft follow-up"
      >
        {/* draft */}
        <div className="p-6">
          <div className="mb-1 eyebrow">Follow-up · {item.contact_name ?? "unknown"}</div>
          <h2 className="serif mb-4 text-lg leading-snug">{item.what}</h2>

          <div className="mb-3 flex gap-1">
            {TONES.map((t) => (
              <button
                key={t}
                onClick={() => {
                  setTone(t);
                  generate(t);
                }}
                className="rounded px-3 py-1 text-xs font-medium capitalize"
                style={{
                  background: t === tone ? "var(--ink)" : "var(--paper)",
                  color: t === tone ? "var(--surface)" : "var(--muted)",
                }}
              >
                {t}
              </button>
            ))}
          </div>

          {draft?.subject && (
            <input
              className="mb-2 w-full rounded border px-3 py-2 text-sm"
              style={{ borderColor: "var(--line)" }}
              defaultValue={draft.subject}
            />
          )}

          <textarea
            value={loading ? "" : body}
            onChange={(e) => setBody(e.target.value)}
            placeholder={loading ? "Drafting…" : ""}
            rows={7}
            className="w-full resize-none rounded border p-3 text-sm leading-relaxed"
            style={{ borderColor: "var(--line)" }}
          />

          <div className="mt-2 flex items-center justify-between">
            <span className="mono text-xs" style={{ color: "var(--faint)" }}>
              {body.trim() ? body.trim().split(/\s+/).length : 0} words
            </span>
            <div className="flex gap-2">
              <button
                onClick={onClose}
                className="eyebrow rounded px-3 py-1.5"
                style={{ color: "var(--muted)" }}
              >
                Close
              </button>
              <button
                onClick={() => navigator.clipboard?.writeText(body)}
                className="rounded px-3 py-1.5 text-sm font-medium"
                style={{ background: "var(--accent)", color: "var(--accent-ink)" }}
              >
                Copy
              </button>
            </div>
          </div>

          {error && (
            <p className="mono mt-2 text-xs" style={{ color: "var(--overdue)" }}>
              {error}
            </p>
          )}
          {draft?.flagged && (
            <p
              className="mt-3 rounded px-3 py-2 text-xs"
              style={{ background: "#fdeceb", color: "var(--overdue)" }}
            >
              ⚠ {draft.flag_reason}
            </p>
          )}
        </div>

        {/* grounding */}
        <aside
          className="border-t p-5 md:border-l md:border-t-0"
          style={{ background: "var(--paper)", borderColor: "var(--line)" }}
        >
          <div className="eyebrow mb-3">Built from</div>
          {draft?.grounding.length ? (
            <ul className="space-y-3">
              {draft.grounding.map((g) => (
                <li key={g.evidence_id}>
                  <div className="mono mb-1 text-[10px] uppercase" style={{ color: "var(--faint)" }}>
                    {g.source_kind.replace("_", " ")}
                  </div>
                  <blockquote
                    className="border-l-2 pl-2 text-[13px] leading-snug"
                    style={{ borderColor: "var(--accent)", color: "var(--muted)" }}
                  >
                    {g.quote}
                  </blockquote>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mono text-xs" style={{ color: "var(--faint)" }}>
              {loading ? "…" : "no grounding quotes"}
            </p>
          )}
        </aside>
      </div>
    </div>
  );
}
