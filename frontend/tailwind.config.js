/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
      colors: {
        brand: {
          50: '#edfaff',
          100: '#d5f3ff',
          500: '#099dd7',
          600: '#087ead',
          700: '#065f83',
          900: '#000033',
        },
      },
      boxShadow: {
        card: '0 1px 3px rgba(15,23,42,0.04), 0 1px 2px rgba(15,23,42,0.06)',
      },
    },
  },
  plugins: [],
}
