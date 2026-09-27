"use client";

import { useState } from "react";

// Small "i" icon that shows a plain-language explanation on hover, focus or tap.
export default function InfoTip({ text, align = "left" }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex align-middle" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button type="button" onClick={() => setOpen(!open)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} aria-label="What does this mean?"
        className="w-4 h-4 rounded-full border border-ink-600 text-paper-500 text-[10px] font-semibold leading-none flex items-center justify-center hover:border-accent hover:text-accent">
        i
      </button>
      {open ? (
        <span role="tooltip" className={`absolute z-30 top-6 ${align === "right" ? "right-0" : "left-0"} w-72 rounded-lg bg-ink-800 border border-ink-600 p-3 text-xs leading-relaxed text-paper-300 normal-case tracking-normal font-normal shadow-xl`}>
          {text}
        </span>
      ) : null}
    </span>
  );
}
