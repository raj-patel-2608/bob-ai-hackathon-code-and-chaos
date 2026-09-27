/** @type {import('tailwindcss').Config} */
// Colours are CSS variables (see app/globals.css), so every class follows the light / dark theme.
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;

module.exports = {
  content: ["./app/**/*.{js,jsx}", "./components/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 950: v("bg"), 900: v("sidebar"), 800: v("surface-2"), 700: v("border"), 600: v("border-strong") },
        paper: { 100: v("fg"), 300: v("fg-muted"), 500: v("fg-subtle") },
        surface: v("surface"),
        accent: v("accent"),
        navy: v("navy"),
        khaki: v("khaki"),
        signal: { amber: v("amber"), red: v("red"), blue: v("blue"), green: v("green") },
      },
      fontFamily: {
        // bundled with the app (@fontsource), so the UI looks the same offline on a station network
        sans: ["IBM Plex Sans", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["Roboto Mono", "Consolas", "Liberation Mono", "Menlo", "monospace"],
      },
      borderRadius: { DEFAULT: "2px", sm: "2px", md: "3px", lg: "3px", xl: "4px" },
    },
  },
  plugins: [],
};
