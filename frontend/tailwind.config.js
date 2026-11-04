/** @type {import('tailwindcss').Config} */

/* Colores como canales del sistema de diseño (tokens.css es la fuente
 * única): cada utilidad resuelve a rgb(var(--token-rgb) / <alpha-value>),
 * así `text-slate-600` y `bg-emerald-500` consumen los mismos tokens que
 * el CSS BEM y soportan el modificador `/alpha` de Tailwind. */
const tok = (nombre) => `rgb(var(${nombre}) / <alpha-value>)`

export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['Roboto', 'system-ui', 'sans-serif'] },
      colors: {
        brand: {
          50: tok('--brand-50-rgb'),
          100: tok('--brand-100-rgb'),
          400: tok('--brand-light-rgb'),
          500: tok('--brand-rgb'),
          600: tok('--brand-deep-rgb'),
          700: tok('--brand-press-rgb'),
          800: tok('--brand-ink-rgb'),
          900: tok('--navy-rgb'),
        },
        /* Financiera aliada (Inversiones Pacífico): solo para su sello. */
        aliado: {
          500: tok('--aliado-rgb'),
          900: tok('--aliado-navy-rgb'),
        },
        /* slate/emerald/red/amber se remapean a las rampas semánticas:
         * no existen como paleta propia en este producto. */
        slate: {
          50: tok('--surface-neutral-rgb'),
          100: tok('--border-soft-rgb'),
          200: tok('--border-rgb'),
          300: tok('--border-rgb'),
          400: tok('--slate-faint-rgb'),
          500: tok('--slate-soft-rgb'),
          600: tok('--slate-rgb'),
          700: tok('--slate-strong-rgb'),
          800: tok('--ink-rgb'),
          900: tok('--ink-rgb'),
        },
        emerald: {
          50: tok('--success-bg-rgb'),
          100: tok('--success-border-rgb'),
          200: tok('--success-border-rgb'),
          300: tok('--success-border-rgb'),
          400: tok('--success-bright-rgb'),
          500: tok('--success-rgb'),
          600: tok('--success-rgb'),
          700: tok('--success-ink-rgb'),
          800: tok('--success-ink-rgb'),
          900: tok('--success-ink-rgb'),
        },
        red: {
          50: tok('--error-bg-rgb'),
          100: tok('--error-border-rgb'),
          200: tok('--error-border-rgb'),
          300: tok('--error-border-rgb'),
          400: tok('--error-rgb'),
          500: tok('--error-rgb'),
          600: tok('--error-strong-rgb'),
          700: tok('--error-ink-rgb'),
          800: tok('--error-ink-rgb'),
          900: tok('--error-ink-rgb'),
        },
        amber: {
          50: tok('--warning-bg-rgb'),
          100: tok('--warning-bg-deep-rgb'),
          200: tok('--warning-bg-deep-rgb'),
          300: tok('--warning-rgb'),
          400: tok('--warning-rgb'),
          500: tok('--warning-rgb'),
          600: tok('--warning-ink-rgb'),
          700: tok('--warning-ink-rgb'),
          800: tok('--warning-ink-rgb'),
          900: tok('--warning-ink-rgb'),
        },
      },
      boxShadow: {
        card: '0 1px 3px rgba(15,23,42,0.04), 0 1px 2px rgba(15,23,42,0.06)',
      },
    },
  },
  plugins: [],
}
