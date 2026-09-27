"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import ThemeToggle from "./ThemeToggle";

// Header band across the top of every page (records-system style): wordmark, service status, theme switch.
export default function TopBar() {
  const [mode, setMode] = useState(null);

  useEffect(() => {
    const load = () => api.ready().then((r) => setMode(r.mode)).catch(() => setMode("offline"));
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  const status = mode === "full" ? ["Services online", "bg-[#4ade80]"]
    : mode === "offline" ? ["API offline", "bg-[#f87171]"]
    : mode ? ["AI offline · rules only", "bg-[#fbbf24]"] : ["Connecting", "bg-white/40"];

  return (
    <header className="sticky top-0 z-40 bg-navy text-white border-b-[3px] border-khaki">
      <div className="h-14 px-6 flex items-center justify-between gap-6">
        <Link href="/" className="flex items-baseline gap-3 min-w-0">
          <span className="font-mono text-[17px] font-medium tracking-[0.12em]">CRIMEFIR</span>
          <span className="hidden md:inline text-[12px] text-white/70 truncate">FIR Intelligence &amp; Crime Pattern Analysis · Investigation support system</span>
        </Link>
        <div className="flex items-center gap-4 shrink-0">
          <span className="hidden sm:flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.06em] text-white/80">
            <span className={`w-2 h-2 rounded-full ${status[1]}`} />{status[0]}
          </span>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
