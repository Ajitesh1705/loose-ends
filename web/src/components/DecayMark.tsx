"use client";

import { useState } from "react";
import type { Decay } from "@/lib/types";
import { bandColor } from "@/lib/format";

// The signature element: a heat rule + mono score, with the deterministic
// explanation one hover away. Color lives here and (almost) nowhere else.
export function DecayMark({ decay }: { decay: Decay }) {
  const [open, setOpen] = useState(false);
  const color = bandColor[decay.band];
  return (
    <div
      className="relative flex items-center gap-2"
      tabIndex={0}
      aria-label={`Decay ${decay.band}, score ${Math.round(decay.score)}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span
        className="inline-block h-6 w-[3px] rounded-full"
        style={{ background: color }}
        aria-hidden
      />
      <span className="mono text-sm tabular-nums" style={{ color }}>
        {Math.round(decay.score)}
      </span>
      <span className="eyebrow">{decay.band}</span>
      {open && (
        <div
          role="tooltip"
          className="absolute left-0 top-8 z-30 w-72 rounded-md border p-3 text-sm shadow-lg"
          style={{ background: "var(--surface)", borderColor: "var(--line-strong)" }}
        >
          <div className="eyebrow mb-2" style={{ color }}>
            {decay.band} · {Math.round(decay.score)}/100
          </div>
          <ul className="space-y-1">
            {decay.explanation.map((line, i) => (
              <li key={i} className="flex gap-2 text-[13px] leading-snug">
                <span style={{ color: "var(--faint)" }}>·</span>
                <span>{line}</span>
              </li>
            ))}
          </ul>
          <div className="mono mt-2 text-[11px]" style={{ color: "var(--faint)" }}>
            computed in Python — not by the model
          </div>
        </div>
      )}
    </div>
  );
}
