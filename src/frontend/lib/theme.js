"use client";

import { useEffect, useState } from "react";

// Theme = "light" | "dark", stored per browser; the default follows the operating system.
const KEY = "crimefir-theme";

export function getTheme() {
  if (typeof document === "undefined") return "light";
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem(KEY, theme); } catch (_) { /* private mode: the theme still applies for this visit */ }
  window.dispatchEvent(new CustomEvent("themechange", { detail: theme }));
}

// Runs before the first paint (see app/layout.js) so the page never flashes the wrong theme.
export const THEME_BOOT_SCRIPT = `(function(){try{var t=localStorage.getItem("${KEY}");if(t!=="light"&&t!=="dark"){t=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";}document.documentElement.dataset.theme=t;}catch(e){document.documentElement.dataset.theme="light";}})();`;

export function useTheme() {
  const [theme, set] = useState("light");
  useEffect(() => {
    set(getTheme());
    const on = (e) => set(e.detail);
    window.addEventListener("themechange", on);
    return () => window.removeEventListener("themechange", on);
  }, []);
  return theme;
}

// Resolved colours for canvas drawing (a canvas cannot use CSS variables directly).
export function useThemeColors() {
  const theme = useTheme();
  const [colors, setColors] = useState(null);
  useEffect(() => {
    const css = getComputedStyle(document.documentElement);
    const c = (name, a = 1) => `rgba(${css.getPropertyValue(`--${name}`).trim().split(/\s+/).join(",")},${a})`;
    setColors({ theme, c, bg: c("bg"), surface: c("surface"), fg: c("fg"), muted: c("fg-muted"), subtle: c("fg-subtle"),
      border: c("border"), amber: c("amber"), accent: c("accent") });
  }, [theme]);
  return colors;
}
