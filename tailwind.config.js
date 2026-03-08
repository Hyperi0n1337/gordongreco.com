/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './js/*.js'],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: '#1a365d', dark: '#0f2440', light: '#2a4a7f' },
        slate: '#2d3748',
        green: { DEFAULT: '#276749', light: '#38a169' },
      }
    }
  },
  plugins: [],
}
