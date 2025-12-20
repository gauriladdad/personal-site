/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#f9fafb",
        text: "#1f2937",
        muted: "#6b7280",
        card: "#ffffff",
        border: "#e5e7eb",
        accent: "#2563eb",
      },
    },
  },
  plugins: [],
};
