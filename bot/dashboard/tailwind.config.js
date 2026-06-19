/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        discord: { bg: "#313338", card: "#2b2d31", dark: "#1e1f22", blurple: "#5865f2", green: "#23a55a", text: "#dbdee1", muted: "#949ba4" },
      },
    },
  },
  plugins: [],
};
