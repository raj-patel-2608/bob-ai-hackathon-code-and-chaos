"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "../lib/api";

const ICONS = {
  home: "M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  upload: "M12 16V4m0 0l-4 4m4-4l4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3",
  files: "M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm7 0v5h5",
  group: "M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm8 0a3 3 0 1 0 0-6M3 20a6 6 0 0 1 12 0m2-6a6 6 0 0 1 4 6",
  graph: "M6 6a2 2 0 1 0 0-.01M18 8a2 2 0 1 0 0-.01M12 18a2 2 0 1 0 0-.01M7.5 7.5l3.5 9m1.5-.5l4.5-7M8 6h8",
  station: "M4 21V8l8-5 8 5v13M9 21v-6h6v6M8 10h.01M16 10h.01",
  quality: "M4 19h16M7 16V9m5 7V5m5 11v-4",
};

const NAV = [
  { href: "/", label: "Dashboard", icon: "home" },
  { href: "/upload", label: "Add FIRs", icon: "upload" },
  { href: "/firs", label: "Case files", icon: "files" },
  { href: "/offenders", label: "Repeat offenders", icon: "group" },
  { href: "/graph", label: "Link graph", icon: "graph" },
  { href: "/stations", label: "Station briefs", icon: "station" },
  { href: "/quality", label: "AI accuracy", icon: "quality" },
];

function Icon({ d }) {
  return (
    <svg viewBox="0 0 24 24" className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const [mode, setMode] = useState(null);

  useEffect(() => {
    const load = () => api.ready().then((r) => setMode(r.mode)).catch(() => setMode("offline"));
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  const active = (href) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
  const status = mode === "full" ? ["All AI services running", "text-signal-green"]
    : mode === "offline" ? ["API not reachable", "text-signal-red"]
    : mode ? ["AI service offline: rules only", "text-signal-amber"] : ["Checking…", "text-paper-500"];

  return (
    <aside className="w-56 shrink-0 border-r border-ink-700 bg-ink-900 flex flex-col">
      <div className="px-5 py-6 border-b border-ink-700">
        <div className="font-serif text-xl tracking-tight text-paper-100">CrimeFIR</div>
        <div className="text-[11px] text-paper-500 mt-1 leading-snug">FIR intelligence &amp; crime pattern detector</div>
      </div>
      <nav className="flex-1 py-3">
        {NAV.map((item) => (
          <Link key={item.href} href={item.href}
            className={`flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
              active(item.href) ? "bg-ink-800 text-paper-100 stripe-amber" : "text-paper-500 hover:text-paper-100 hover:bg-ink-800/50"}`}>
            <Icon d={ICONS[item.icon]} />
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>
      <div className="px-5 py-4 border-t border-ink-700 text-[11px] text-paper-500 leading-relaxed space-y-2">
        <div className="flex items-center gap-2"><span className={`w-2 h-2 rounded-full bg-current ${status[1]}`} /><span className={status[1]}>{status[0]}</span></div>
        <div>Every link is an investigation lead that needs human verification.</div>
      </div>
    </aside>
  );
}
