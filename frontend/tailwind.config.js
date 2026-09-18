/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ['Urbanist', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        sans: ['"DM Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      borderRadius: {
        '4xl': '2rem',
        '5xl': '2.5rem',
      },
      colors: {
        // Canvas + surfaces (no borders / no shadows — hierarchy by tone only)
        app: {
          bg: '#EDEEF0',        // canvas
          surface: '#FFFFFF',   // primary card
          secondary: '#F5F6F7', // nested well / inactive pill
          border: '#E4E6E9',    // hairline only where a divider is unavoidable
          borderDark: '#D5D8DC',
        },
        ink: {
          DEFAULT: '#141518',   // headings, active pill
          soft: '#3A3D42',      // dark card surface
          muted: '#8B9098',
        },
        // "teal" retained as a token name, remapped to the electric-blue accent
        teal: {
          50: '#EEF3FF',
          100: '#DCE6FF',
          200: '#C2D3FF',
          500: '#1F5EFF',
          600: '#1A50DB',
          700: '#1743B8',
          800: '#123590',
          900: '#0E2A70',
        },
        accent: { DEFAULT: '#1F5EFF', soft: '#EEF3FF', deep: '#1743B8' },
        text: { main: '#141518', secondary: '#5E636B', muted: '#9AA0A8' },
        info: { DEFAULT: '#1F5EFF', light: '#EEF3FF', dark: '#1743B8' },
        success: { DEFAULT: '#1E9E6A', light: '#E8F6EF', dark: '#15704B' },
        warning: { DEFAULT: '#D98A1C', light: '#FDF3E3', dark: '#9A5F10' },
        danger: { DEFAULT: '#E5484D', light: '#FDECEC', dark: '#B4282D' },
      },
      keyframes: {
        'fade-in': { from: { opacity: 0, transform: 'translateY(6px)' }, to: { opacity: 1, transform: 'none' } },
      },
      animation: { 'fade-in': 'fade-in .35s cubic-bezier(.2,.7,.2,1) both' },
    },
  },
  plugins: [],
}
