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
        bg:          "#0a0d12",
        "bg-rail":   "#0c1017",
        surface:     "#10141c",
        "surface-2": "#161b25",
        "surface-3": "#1c2230",

        // Borders (used as border-[color])
        // Prefer border-white/[0.07] for hairlines; keep token for parity.

        // Text
        text:         "#e6ecf3",
        "text-muted": "#8b97a9",
        "text-dim":   "#6b7d97",

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
