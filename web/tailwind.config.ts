import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: '#0a0a0f',
          secondary: '#12121a',
          card: '#1a1a28',
        },
        player: {
          DEFAULT: '#3b82f6',
          dark: '#1e40af',
          glow: 'rgba(59, 130, 246, 0.3)',
        },
        banker: {
          DEFAULT: '#ef4444',
          dark: '#991b1b',
          glow: 'rgba(239, 68, 68, 0.3)',
        },
        accent: '#8b5cf6',
      },
    },
  },
  plugins: [],
} satisfies Config;
