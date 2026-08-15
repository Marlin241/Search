import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "media",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        "surface-sunken": "var(--surface-sunken)",
        border: "var(--border)",
        "border-strong": "var(--border-strong)",
        ink: "var(--ink)",
        "ink-soft": "var(--ink-soft)",
        "ink-faint": "var(--ink-faint)",
        "ink-on-accent": "var(--ink-on-accent)",
        accent: "var(--accent)",
        "accent-strong": "var(--accent-strong)",
        "accent-soft": "var(--accent-soft)",
        "accent-ink": "var(--accent-ink)",
        accent2: "var(--accent2)",
        "accent2-strong": "var(--accent2-strong)",
        "accent2-soft": "var(--accent2-soft)",
        "accent2-ink": "var(--accent2-ink)",
        success: "var(--success)",
        "success-soft": "var(--success-soft)",
        "success-ink": "var(--success-ink)",
        pending: "var(--pending)",
        "pending-soft": "var(--pending-soft)",
        "pending-ink": "var(--pending-ink)",
        attention: "var(--attention)",
        "attention-soft": "var(--attention-soft)",
        "attention-ink": "var(--attention-ink)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-sora)", "var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        soft: "0 14px 34px -16px var(--shadow-color)",
        lift: "0 16px 32px -14px var(--shadow-color)",
        pop: "0 20px 44px -16px var(--shadow-color)",
      },
    },
  },
  plugins: [],
};

export default config;
