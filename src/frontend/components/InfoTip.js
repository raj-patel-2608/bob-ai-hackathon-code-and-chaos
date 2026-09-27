"use client";

import { useState } from "react";

// Small "i" icon that shows a plain-language explanation on hover or tap.
export default function InfoTip({ text, align = "left" }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex align-middle" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" onClick={() => setOpen(!open)} aria-label="What does this mean?"
        className="w-4 h-4 rounded-full border border-paper-500 text-paper-500 text-[10px] leading-none flex items-center justify-center hover:border-signal-amber hover:text-signal-amber">
        i
      </button>
      {open ? (
        <span className={`absolute z-30 top-5 ${align === "right" ? "right-0" : "left-0"} w-72 bg-ink-800 border border-ink-600 p-3 text-[12px] leading-relaxed text-paper-300 normal-case tracking-normal font-normal shadow-lg`}>
          {text}
        </span>
      ) : null}
    </span>
  );
}
