import type { Config } from "tailwindcss";

/**
 * bafather · Mercury × HUD · tailwind.config.ts
 *
 * Color tokens mirror globals.css CSS variables.
 * Keep names readable in Tailwind classes: bg-surface, text-cyan-1, etc.
 *
 * Two color axes:
 *   - UI semantic:    success / warn / danger / info / admin
 *   - Data domain:    win / lose / banker / player / tie  (PnL ONLY)
 * Don't mix them. Suspending a user is `danger`, NOT `banker`.
 */
export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Surfaces
        // ★2026-09-23: 会員ページ (/me) だけ明るめにするため、面と文字の色は CSS 変数経由にした。
        //   既定値は globals.css の :root (従来と同じ色)。.me-theme の中だけ上書きされる。
        bg:          "rgb(var(--c-bg) / <alpha-value>)",
        "bg-rail":   "rgb(var(--c-bg-rail) / <alpha-value>)",
        surface:     "rgb(var(--c-surface) / <alpha-value>)",
        "surface-2": "rgb(var(--c-surface-2) / <alpha-value>)",
        "surface-3": "rgb(var(--c-surface-3) / <alpha-value>)",

        // Borders (used as border-[color])
        // Prefer border-white/[0.07] for hairlines; keep token for parity.

        // Text
        text:         "rgb(var(--c-text) / <alpha-value>)",
        "text-muted": "rgb(var(--c-text-muted) / <alpha-value>)",
        "text-dim":   "rgb(var(--c-text-dim) / <alpha-value>)",

        // UI semantic
        cyan: {
          DEFAULT: "#5cdfff",
          dim:     "#3a8fa5",
        },
        amber: {
          DEFAULT: "#ffb547",
          dim:     "#a37130",
        },
        win:   "#3fd49a",
        lose:  "#ff6479",
        warn:  "#ffb547",

        // Data domain — for PnL/baccarat displays only
        banker: { DEFAULT: "#ff6479", dark: "#b91c1c" },
        player: { DEFAULT: "#4a9eff", dark: "#1c5fb9" },
        tie:    "#ffcc40",

        // Legacy aliases kept so old code keeps compiling.
        // Migrate over time.
        accent:        "#5cdfff",
        "bg-primary":  "#0a0d12",
        "bg-secondary":"#0c1017",
        "bg-card":     "#10141c",
        "bg-glass":    "#161b25",
      },
      fontFamily: {
        hud:  ["Orbitron", "Noto Sans JP", "Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Share Tech Mono", "ui-monospace", "monospace"],
        body: ["Inter", "Noto Sans JP", "Segoe UI", "system-ui", "sans-serif"],
      },
      fontVariantNumeric: {
        tabular: ["tabular-nums"],
      },
      letterSpacing: {
        kicker: "0.25em",
        label:  "0.15em",
      },
    },
  },
  plugins: [],
} satisfies Config;
