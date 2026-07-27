export type Band = "fresh" | "warm" | "cooling" | "cold" | "overdue";

export type Evidence = {
  id: string;
  source_id: string;
  start_char: number;
  end_char: number;
  quote: string;
  is_primary: boolean;
};

export type Decay = {
  score: number;
  band: Band;
  explanation: string[];
};

export type Merge = {
  reason: string;
  similarity: number | null;
  created_at: string;
};

export type Commitment = {
  id: string;
  direction: "i_owe" | "they_owe";
  contact_id: string | null;
  contact_name: string | null;
  what: string;
  due_at: string | null;
  due_precision: string;
  status: string;
  confidence: number;
  state: string;
  ambiguity_note: string | null;
  created_at: string;
  updated_at: string;
  last_touch_at: string | null;
  possible_duplicate_of: string | null;
  evidence: Evidence[];
};

export type LedgerItem = Commitment & {
  decay: Decay;
  merges: Merge[];
};

export type DuplicateInfo = { id: string; what: string; quote: string | null };
export type ReviewItem = Commitment & { duplicate_of: DuplicateInfo | null };

export type SourceDetail = {
  id: string;
  kind: string;
  title: string;
  raw_text: string;
  channel_ts: string | null;
  contact_hint: string | null;
  created_at: string;
};

export type Source = Omit<SourceDetail, "raw_text">;

export type GroundingQuote = {
  evidence_id: string;
  quote: string;
  source_kind: string;
};

export type DraftResponse = {
  subject: string | null;
  body: string;
  tone: "warm" | "direct" | "brief";
  word_count: number;
  grounding: GroundingQuote[];
  flagged: boolean;
  flag_reason: string | null;
};

export const BAND_ORDER: Band[] = ["overdue", "cold", "cooling", "warm", "fresh"];

export const BAND_LABEL: Record<Band, string> = {
  overdue: "Overdue",
  cold: "Cold",
  cooling: "Cooling",
  warm: "Warm",
  fresh: "Fresh",
};

export const KIND_LABEL: Record<string, string> = {
  call_transcript: "Call",
  email_thread: "Email",
  whatsapp_export: "WhatsApp",
  session_note: "Session note",
};
