/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        cream: {
          50:  '#FDFAF6',
          100: '#F8F0E8',
          200: '#F2E8DC',
          300: '#E8D8C8',
          400: '#D4BEA8',
        },
        brown: {
          50:  '#F5EDE3',
          100: '#E8D5C0',
          200: '#C8A882',
          300: '#A67C52',
          400: '#7B5C3A',
          500: '#6B3A2A',
          600: '#5A2E1E',
          700: '#3D1F14',
          800: '#2A1510',
        },
      },
      fontFamily: {
        serif: ['Playfair Display', 'Georgia', 'serif'],
        sans:  ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
