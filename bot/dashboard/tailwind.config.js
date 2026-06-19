/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0e0f13", surface: "#16181d", card: "#1e2027", raised: "#262932",
        border: "#2a2d36", text: "#e7e9ee", muted: "#9aa0ad",
        accent: "#5865f2", accent2: "#7c5cff", green: "#23a55a", danger: "#f23f43",
      },
      boxShadow: { panel: "0 4px 20px rgba(0,0,0,.35)" },
      borderRadius: { xl2: "16px" },
    },
  },
  plugins: [],
};
