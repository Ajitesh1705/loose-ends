// Browser-side API client. All calls run from the client (the app is interactive:
// drawers, polling, drafts), so everything uses the public base.
import type {
  DraftResponse,
  LedgerItem,
  ReviewItem,
  Source,
  SourceDetail,
} from "./types";

export const API =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001";

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${detail}`);
  }
  return res.json();
}

export const getLedger = () =>
  fetch(`${API}/commitments`, { cache: "no-store" }).then(j<LedgerItem[]>);

export const getReview = () =>
  fetch(`${API}/review`, { cache: "no-store" }).then(j<ReviewItem[]>);

export const getSources = () =>
  fetch(`${API}/sources`, { cache: "no-store" }).then(j<Source[]>);

export const getSource = (id: string) =>
  fetch(`${API}/sources/${id}`, { cache: "no-store" }).then(j<SourceDetail>);

export const createSource = (body: {
  kind: string;
  title: string;
  raw_text: string;
  channel_ts?: string | null;
  contact_hint?: string | null;
}) =>
  fetch(`${API}/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(j<{ id: string; job_id: string }>);

export const confirmCommitment = (
  id: string,
  body: { what?: string; who?: string; due_at?: string | null; due_precision?: string }
) =>
  fetch(`${API}/commitments/${id}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(j);

export const rejectCommitment = (id: string) =>
  fetch(`${API}/commitments/${id}/reject`, { method: "POST" }).then(j);

// Deployed serverless there is no always-on worker, so the queue is drained on
// demand. Locally the polling worker usually claims the job first and this returns
// `processed: 0` — harmless either way.
export const drainJobs = () =>
  fetch(`${API}/jobs/drain`, { method: "POST" }).then(
    j<{ processed: number; pending: number }>
  );

export const draftCommitment = (id: string, tone: string) =>
  fetch(`${API}/commitments/${id}/draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tone }),
  }).then(j<DraftResponse>);
