/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./static/src/**/*.js"],
  safelist: [
    "bg-error/5",
    "bg-error",
    "bg-warning/10",
    "bg-info/5",
  ],
  theme: {
    extend: {},
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: ["light"],
  },
};
