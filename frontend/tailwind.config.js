/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: {
          400: "#8b9dfd",
          500: "#7487f7",
          600: "#6071e8",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Cascadia Code", "SFMono-Regular", "Consolas", "monospace"],
      },
      boxShadow: {
        panel: "0 18px 55px rgba(15, 23, 42, 0.08)",
        "panel-dark": "0 18px 55px rgba(0, 0, 0, 0.24)",
      },
    },
  },
  plugins: [],
};
