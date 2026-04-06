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
        'bg-primary': '#0a0a0f',
        'bg-secondary': '#12121a',
        'bg-card': '#1a1a28',
        player: {
          DEFAULT: '#3b82f6',
          dark: '#1e40af',
        },
        banker: {
          DEFAULT: '#ef4444',
          dark: '#991b1b',
        },
        accent: '#8b5cf6',
      },
    },
  },
  plugins: [],
} satisfies Config;
