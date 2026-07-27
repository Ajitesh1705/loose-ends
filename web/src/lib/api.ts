// Server components reach the API over the compose network (API_BASE_INTERNAL).
// Browser code uses NEXT_PUBLIC_API_BASE. Keep the two separate.

export const SERVER_API_BASE =
  process.env.API_BASE_INTERNAL ?? "http://localhost:8000";

export const BROWSER_API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type Source = {
  id: string;
  kind: "call_transcript" | "email_thread" | "whatsapp_export" | "session_note";
  title: string;
  channel_ts: string | null;
  contact_hint: string | null;
  created_at: string;
};

export async function fetchSources(): Promise<Source[]> {
  const res = await fetch(`${SERVER_API_BASE}/sources`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET /sources failed: ${res.status}`);
  return res.json();
}
