module.exports = {
  darkMode: "media",
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx,astro}"],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#f9fafb",
          dark: "#0f172a",
        },
        text: {
          DEFAULT: "#1f2937",
          dark: "#e5e7eb",
        },
        muted: {
          DEFAULT: "#6b7280",
          dark: "#9ca3af",
        },
        card: {
          DEFAULT: "#ffffff",
          dark: "#020617",
        },
        border: {
          DEFAULT: "#e5e7eb",
          dark: "#1f2937",
        },
        accent: {
          DEFAULT: "#2563eb",
          dark: "#60a5fa",
        },
      },
    },
  },
  plugins: [],
};
