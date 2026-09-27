/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0B1012",
          900: "#10161A",
          800: "#171E23",
          700: "#212A30",
          600: "#2C373E",
        },
        paper: {
          100: "#E9ECEC",
          300: "#B7C0C4",
          500: "#8B979E",
        },
        signal: {
          amber: "#D9A441",
          amberDim: "#8A6A2F",
          red: "#C1442E",
          redDim: "#7A3226",
          blue: "#4C7EA8",
          green: "#5C8A6B",
        },
      },
      fontFamily: {
        // System font stacks only — no external font fetch, so the tool
        // builds and runs fully offline on a station network.
        serif: [
          "Iowan Old Style",
          "Palatino Linotype",
          "URW Palladio L",
          "P052",
          "Georgia",
          "serif",
        ],
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "SFMono-Regular",
          "Consolas",
          "Liberation Mono",
          "Menlo",
          "monospace",
        ],
      },
      boxShadow: {
        none: "none",
      },
    },
  },
  plugins: [],
};
