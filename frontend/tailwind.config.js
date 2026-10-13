/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      /*
       * Design tokens.
       *
       * The existing UI is written against Tailwind's `slate` scale (`dark:bg-slate-900`, `text-slate-500`, ...).
       * Re-tinting the DARK end of that scale to deep navy re-skins every screen consistently without touching
       * each component, and gives the layered surfaces the design calls for:
       *   950 page background  <  900 cards  <  800 raised surfaces / borders  <  700 strong borders
       * The LIGHT end (50-400) keeps the neutral slate values, so light mode is unchanged.
       */
      colors: {
        slate: {
          50: "#f8fafc",
          100: "#f1f5f9",
          200: "#e2e8f0",
          300: "#cbd5e1",
          400: "#94a3b8",
          500: "#64748b",
          600: "#475569",
          700: "#25324a",
          800: "#172033",
          900: "#0e1524",
          950: "#080d18",
        },
        // Semantic aliases so new code says what it means. Positive/negative are the only red/green in the UI.
        // Brand accents for the "crypto terminal" look: electric blue, violet and cyan.
        brand: { 400: "#7aa2ff", 500: "#5b8cff", 600: "#3f6fe6", violet: "#8b5cf6", cyan: "#22d3ee" },
        gain: { DEFAULT: "#10b981", soft: "#d1fae5", ink: "#047857" },
        loss: { DEFAULT: "#ef4444", soft: "#fee2e2", ink: "#b91c1c" },
      },
      fontFamily: {
        sans: ['"Inter"', "ui-sans-serif", "system-ui", "-apple-system", '"Segoe UI"', "Roboto", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)",
        pop: "0 10px 30px -10px rgb(2 6 23 / 0.35)",
        glow: "0 0 0 1px rgb(91 140 255 / 0.25), 0 8px 30px -12px rgb(91 140 255 / 0.45)",
        "glow-violet": "0 0 22px -2px rgb(139 92 246 / 0.55)",
      },
      borderRadius: { card: "0.875rem" },
      // Wide desktops: lets the five statistic cards sit in one row beside the insights column.
      screens: { "3xl": "1800px" },
      keyframes: {
        "toast-in": { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        glow: { "0%, 100%": { opacity: "0.55" }, "50%": { opacity: "1" } },
        float: { "0%, 100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-6px)" } },
      },
      animation: {
        "toast-in": "toast-in 160ms ease-out",
        "fade-in": "fade-in 160ms ease-out",
        glow: "glow 5s ease-in-out infinite",
        float: "float 6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
