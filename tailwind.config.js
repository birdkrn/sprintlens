/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./static/src/**/*.js"],
  safelist: [
    "bg-error/5",
    "bg-error",
    "bg-warning/10",
    "bg-info/5",
    "bg-primary/10",
    "grid-cols-3",
    "grid-cols-4",
    "grid-cols-5",
  ],
  theme: {
    extend: {},
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: ["light"],
  },
};
