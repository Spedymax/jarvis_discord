/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0e0420", surface: "#190a2c", card: "#21103a", raised: "#2c1648",
        border: "#3a1f5e", text: "#fde7ff", muted: "#b88fd6",
        accent: "#ff49d9", accent2: "#37d6ff", green: "#23a55a", danger: "#ff5470",
      },
      boxShadow: { panel: "0 4px 20px rgba(0,0,0,.35)" },
      borderRadius: { xl2: "16px" },
    },
  },
  plugins: [],
};
