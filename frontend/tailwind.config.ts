import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "media",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          800: "#232b3a",
          900: "#131924",
          950: "#0b0f16",
        },
      },
    },
  },
  plugins: [],
};

export default config;
