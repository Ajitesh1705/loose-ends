"use client";

import { useEffect, useState } from "react";
import { createSource, getSource, getSources } from "@/lib/api";
import { KIND_LABEL, type Source } from "@/lib/types";

const KINDS = ["call_transcript", "email_thread", "whatsapp_export", "session_note"];

export function IngestPanel({
  onClose,
  onRefresh,
}: {
  onClose: () => void;
  onRefresh: () => void;
}) {
  const [fixtures, setFixtures] = useState<Source[]>([]);
  const [kind, setKind] = useState(KINDS[0]);
  const [title, setTitle] = useState("");
  const [hint, setHint] = useState("");
  const [text, setText] = useState("");
  const [status, setStatus] = useState<"idle" | "extracting" | "done">("idle");

  useEffect(() => {
    getSources().then(setFixtures).catch(() => {});
  }, []);

  async function pickFixture(id: string) {
    if (!id) return;
    const s = await getSource(id);
    setKind(s.kind);
    setTitle(s.title + " (re-run)");
    setHint(s.contact_hint ?? "");
    setText(s.raw_text);
  }

  async function submit() {
    if (!text.trim() || !title.trim()) return;
    setStatus("extracting");
    await createSource({ kind, title, raw_text: text, contact_hint: hint || null });
    // The worker is a poller; refresh a few times as it lands.
    let n = 0;
    const tick = () => {
      onRefresh();
      if (++n < 5) setTimeout(tick, 1800);
      else setStatus("done");
    };
    setTimeout(tick, 1800);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} aria-hidden />
      <div
        className="relative w-full max-w-2xl rounded-lg border p-6 shadow-2xl"
        style={{ background: "var(--surface)", borderColor: "var(--line-strong)" }}
        role="dialog"
        aria-label="Ingest a conversation"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="serif text-lg">Ingest a conversation</h2>
          <button onClick={onClose} className="eyebrow" style={{ color: "var(--muted)" }}>
            Close ✕
          </button>
        </div>

        <label className="mb-3 block">
          <span className="eyebrow mb-1 block">Start from a fixture</span>
          <select
            className="mono w-full rounded border px-3 py-2 text-sm"
            style={{ borderColor: "var(--line)" }}
            defaultValue=""
            onChange={(e) => pickFixture(e.target.value)}
          >
            <option value="">— paste your own below —</option>
            {fixtures.map((f) => (
              <option key={f.id} value={f.id}>
                {f.title}
              </option>
            ))}
          </select>
        </label>

        <div className="mb-3 grid grid-cols-2 gap-3">
          <label className="block">
            <span className="eyebrow mb-1 block">Channel</span>
            <select
              className="w-full rounded border px-3 py-2 text-sm"
              style={{ borderColor: "var(--line)" }}
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {KIND_LABEL[k]}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="eyebrow mb-1 block">Contact hint</span>
            <input
              className="w-full rounded border px-3 py-2 text-sm"
              style={{ borderColor: "var(--line)" }}
              value={hint}
              onChange={(e) => setHint(e.target.value)}
              placeholder="e.g. Priya Raman"
            />
          </label>
        </div>

        <label className="mb-3 block">
          <span className="eyebrow mb-1 block">Title</span>
          <input
            className="w-full rounded border px-3 py-2 text-sm"
            style={{ borderColor: "var(--line)" }}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Client call — Q3 review"
          />
        </label>

        <label className="block">
          <span className="eyebrow mb-1 block">Transcript / thread</span>
          <textarea
            rows={9}
            className="w-full resize-none rounded border p-3 text-sm leading-relaxed"
            style={{ borderColor: "var(--line)" }}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste a call transcript, email thread, or message export…"
          />
        </label>

        <div className="mt-4 flex items-center justify-between">
          <span className="mono text-xs" style={{ color: "var(--faint)" }}>
            {status === "extracting" && "Extracting commitments…"}
            {status === "done" && "Done — check the ledger."}
          </span>
          <button
            onClick={submit}
            disabled={status === "extracting" || !text.trim() || !title.trim()}
            className="rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50"
            style={{ background: "var(--accent)", color: "var(--accent-ink)" }}
          >
            Extract
          </button>
        </div>
      </div>
    </div>
  );
}
