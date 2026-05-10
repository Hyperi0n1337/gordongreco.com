/** @type {import('tailwindcss').Config} */
// Gordon Greco LLC — Tailwind preset.
// Auto-generated from mas/advisory/brand/tokens.json.
// DO NOT EDIT BY HAND. Re-run generators/tailwind_preset.py to refresh.
// Consume with: module.exports = { presets: [require("./tailwind.preset.js")] };

module.exports = {
  theme: {
    extend: {
      colors: {
        navy:  { DEFAULT: "#1a365d", 800: "#0f2440", 600: "#2a4a7f", 300: "#8196b5", 50: "#eaeef5" },
        gold:  { DEFAULT: "#b08a54", 400: "#cbab7b", 100: "#ecdfc7" },
        ink:   { DEFAULT: "#14171c", 2: "#33373e" },
        muted: "#5e6067",
        light: "#8a8c92",
        rule:  { DEFAULT: "#e4e0d6", soft: "#eeeae0" },
        paper: "#fbf8f0",
        cream: "#f3ede0",
        pos:   "#276749",
        neg:   "#9b2335",
        warn:  "#b7791f",
      },
      fontFamily: {
        serif: ["Source Serif 4", "Source Serif Pro", "Georgia", "serif"],
        sans: ["Work Sans", "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["JetBrains Mono", "SF Mono", "Menlo", "monospace"],
      },
      fontSize: {
        xs: ["11px", { lineHeight: "1.4" }],
        sm: ["13px", { lineHeight: "1.5" }],
        base: ["15px", { lineHeight: "1.55" }],
        lg: ["18px", { lineHeight: "1.45" }],
        xl: ["22px", { lineHeight: "1.35" }],
        "2xl": ["28px", { lineHeight: "1.25" }],
        "3xl": ["36px", { lineHeight: "1.15" }],
        "4xl": ["48px", { lineHeight: "1.1" }],
      },
      spacing: {
        1: "4px",
        2: "8px",
        3: "12px",
        4: "16px",
        5: "24px",
        6: "32px",
        7: "48px",
        8: "64px",
      },
      borderRadius: {
        sm: "2px",
        DEFAULT: "4px",
        lg: "8px",
      },
      boxShadow: {
        1: "0 1px 2px rgba(20,23,28,0.04), 0 1px 1px rgba(20,23,28,0.03)",
        2: "0 4px 12px rgba(20,23,28,0.06), 0 2px 4px rgba(20,23,28,0.04)",
        3: "0 12px 32px rgba(20,23,28,0.10), 0 4px 8px rgba(20,23,28,0.05)",
      },
    },
  },
  plugins: [],
};
