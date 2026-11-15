import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        channel: {
          darkest: "#070913",
          dark: "#0d1124",
          surface: "#141a36",
          border: "#202852",
          borderHover: "#2f3a75",
          purple: "#7c3aed",
          purpleHover: "#6d28d9",
          yellow: "#f59e0b",
          yellowHover: "#d97706",
          accent: "#fbbf24",
        },
      },
    },
  },
  plugins: [],
};

export default config;
