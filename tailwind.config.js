/** @type {import('tailwindcss').Config} */
// Gordon Greco LLC — site Tailwind config.
// Consumes the brand-system preset (tailwind.preset.js) shipped by the design
// system bundle. Keep tailwind.preset.js in lockstep with the Claude Design
// source of truth; site-specific `content` paths + legacy-class aliases below.
module.exports = {
  presets: [require('./tailwind.preset.js')],
  content: ['./**/*.html', './js/*.js'],
  theme: {
    extend: {
      colors: {
        // Legacy Tailwind aliases the site HTML still uses. The brand-v1
        // preset only ships numeric shades (navy.800, navy.600, etc.); the
        // site HTML predates that change and uses semantic names like
        // "navy-dark". Map the aliases to their brand-v1 equivalents here
        // so HTML stays untouched during the token swap.
        navy: {
          dark:  '#0f2440',   // → navy.800
          light: '#2a4a7f',   // → navy.600
        },
      },
    },
  },
};
