"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

const NAV = [
  { href: "/", label: "Dashboard", glyph: "01" },
  { href: "/upload", label: "Ingest FIRs", glyph: "02" },
  { href: "/firs", label: "Case Files", glyph: "03" },
  { href: "/offenders", label: "Repeat Offenders", glyph: "04" },
  { href: "/graph", label: "Investigation Graph", glyph: "05" },
  { href: "/stations", label: "Station Briefs", glyph: "06" },
  { href: "/quality", label: "Model Quality", glyph: "07" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [mode, setMode] = useState(null);

  useEffect(() => {
    const load = () =>
      api
        .ready()
        .then((r) => setMode(r.mode))
        .catch(() => setMode("API offline"));
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  const active = (href) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <aside className="w-60 shrink-0 border-r border-ink-700 bg-ink-900 flex flex-col">
      <div className="px-5 py-6 border-b border-ink-700">
        <div className="font-serif text-xl tracking-tight text-paper-100">CrimeFIR</div>
        <div className="text-[11px] text-paper-500 mt-1 leading-snug">
          FIR intelligence &amp; crime pattern detector
        </div>
      </div>

      <nav className="flex-1 py-3">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
              active(item.href)
                ? "bg-ink-800 text-paper-100 stripe-amber"
                : "text-paper-500 hover:text-paper-100 hover:bg-ink-800/50"
            }`}
          >
            <span className="data-id text-[11px] text-paper-500">{item.glyph}</span>
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>

      <div className="px-5 py-4 border-t border-ink-700 text-[11px] text-paper-500 leading-relaxed space-y-2">
        <div>
          Mode:{" "}
          <span className={mode === "full" ? "text-signal-green" : "text-signal-amber"}>{mode || "…"}</span>
        </div>
        <div>Every link and flag is an investigation lead that requires human verification.</div>
        <div className="text-paper-500/70">Team Code &amp; Chaos · IBM × NFSU</div>
      </div>
    </aside>
  );
}
