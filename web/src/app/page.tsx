import { fetchSources, type Source } from "@/lib/api";

const KIND_LABEL: Record<Source["kind"], string> = {
  call_transcript: "Call",
  email_thread: "Email",
  whatsapp_export: "WhatsApp",
  session_note: "Session note",
};

function fmt(ts: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default async function Home() {
  let sources: Source[] = [];
  let error: string | null = null;
  try {
    sources = await fetchSources();
  } catch (e) {
    error = e instanceof Error ? e.message : "failed to load sources";
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <header className="mb-10">
        <h1 className="text-2xl font-semibold tracking-tight">Loose Ends</h1>
        <p className="mt-1 text-sm text-[color:var(--muted)]">
          Sources ingested — the raw material commitments are extracted from.
        </p>
      </header>

      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Couldn&apos;t reach the API: {error}
        </div>
      ) : sources.length === 0 ? (
        <p className="text-sm text-[color:var(--muted)]">No sources yet.</p>
      ) : (
        <ul className="divide-y divide-[color:var(--line)] border-y border-[color:var(--line)]">
          {sources.map((s) => (
            <li key={s.id} className="flex items-baseline gap-4 py-4">
              <span className="w-24 shrink-0 text-xs uppercase tracking-wide text-[color:var(--muted)]">
                {KIND_LABEL[s.kind] ?? s.kind}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{s.title}</p>
                {s.contact_hint && (
                  <p className="text-sm text-[color:var(--muted)]">
                    {s.contact_hint}
                  </p>
                )}
              </div>
              <span className="shrink-0 text-sm tabular-nums text-[color:var(--muted)]">
                {fmt(s.channel_ts)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
