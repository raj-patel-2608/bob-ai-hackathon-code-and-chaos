"use client";

import { setTheme, useTheme } from "../lib/theme";

const SUN = "M12 4V2m0 20v-2m8-8h2M2 12h2m13.66-5.66l1.41-1.41M4.93 19.07l1.41-1.41m0-11.32L4.93 4.93m14.14 14.14l-1.41-1.41M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0z";
const MOON = "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z";

export default function ThemeToggle() {
  const theme = useTheme();
  const next = theme === "dark" ? "light" : "dark";
  return (
    <button type="button" onClick={() => setTheme(next)} aria-label={`Switch to ${next} mode`} title={`Switch to ${next} mode`}
      className="inline-flex items-center gap-2 border border-white/25 px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.06em] text-white/90 hover:bg-white/10">
      <svg viewBox="0 0 24 24" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d={theme === "dark" ? SUN : MOON} />
      </svg>
      {theme === "dark" ? "Day mode" : "Night mode"}
    </button>
  );
}
