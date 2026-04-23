/** @type {import('tailwindcss').Config} */
// Gordon Greco LLC — site Tailwind config.
// Consumes the brand-system preset (tailwind.preset.js) shipped by the design
// system bundle. Keep tailwind.preset.js in lockstep with the Claude Design
// source of truth; customize site-specific `content` paths and overrides here.
module.exports = {
  presets: [require('./tailwind.preset.js')],
  content: ['./**/*.html', './js/*.js'],
};
