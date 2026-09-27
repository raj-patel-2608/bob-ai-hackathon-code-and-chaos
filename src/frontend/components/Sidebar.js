"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  ["Overview", [
    { href: "/", label: "Dashboard" },
    { href: "/upload", label: "Add FIRs" },
  ]],
  ["Investigation", [
    { href: "/firs", label: "Case files" },
    { href: "/offenders", label: "Repeat offenders" },
    { href: "/graph", label: "Link graph" },
  ]],
  ["Reports", [
    { href: "/stations", label: "Station briefs" },
    { href: "/quality", label: "AI accuracy" },
  ]],
];

export default function Sidebar() {
  const pathname = usePathname();
  const active = (href) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  return (
    <aside className="w-56 shrink-0 border-r border-ink-700 bg-ink-900 sticky top-[59px] h-[calc(100vh-59px)] flex flex-col">
      <nav className="flex-1 overflow-y-auto py-4">
        {NAV.map(([section, items]) => (
          <div key={section} className="mb-5">
            <div className="px-5 mb-1 label">{section}</div>
            {items.map((item) => (
              <Link key={item.href} href={item.href}
                className={`block border-l-[3px] px-5 py-2 text-sm transition-colors ${
                  active(item.href)
                    ? "border-khaki bg-ink-800 text-paper-100 font-medium"
                    : "border-transparent text-paper-300 hover:bg-ink-800/60 hover:text-paper-100"}`}>
                {item.label}
              </Link>
            ))}
          </div>
        ))}
      </nav>
      <div className="px-5 py-4 border-t border-ink-700 text-[11px] leading-relaxed text-paper-500">
        Links and groups are investigation leads. Verify before action.
      </div>
    </aside>
  );
}
