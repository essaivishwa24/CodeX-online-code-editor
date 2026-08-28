/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: {
          400: "#388bfd",
          500: "#2f81f7",
          600: "#0969da",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Cascadia Code", "SFMono-Regular", "Consolas", "monospace"],
      },
      boxShadow: {
        panel: "0 8px 24px rgba(140, 149, 159, 0.15)",
        "panel-dark": "0 8px 24px rgba(1, 4, 9, 0.22)",
      },
    },
  },
  plugins: [],
};
