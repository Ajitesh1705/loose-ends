import type { Band } from "./types";

export const bandColor: Record<Band, string> = {
  fresh: "var(--fresh)",
  warm: "var(--warm)",
  cooling: "var(--cooling)",
  cold: "var(--cold)",
  overdue: "var(--overdue)",
};

export function fmtDate(ts: string | null, opts?: Intl.DateTimeFormatOptions): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleDateString(
    undefined,
    opts ?? { month: "short", day: "numeric", year: "numeric" }
  );
}

export function dueLabel(due: string | null, precision: string): string {
  if (!due) return precision === "vague" ? "someday" : "no deadline";
  const d = fmtDate(due, { month: "short", day: "numeric" });
  return precision === "week" || precision === "vague" ? `~${d}` : d;
}

export function directionLabel(direction: string): string {
  return direction === "i_owe" ? "I owe" : "They owe";
}
