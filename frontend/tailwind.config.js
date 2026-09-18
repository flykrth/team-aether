/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        app: {
          bg: '#F6F8F8',
          surface: '#FFFFFF',
          secondary: '#F1F5F5',
          border: '#DDE5E5',
          borderDark: '#C8D5D5',
        },
        teal: {
          50: '#E6F5F4',
          100: '#CCECE9',
          500: '#008F8C',
          600: '#007A77',
          700: '#006F6D',
          800: '#005453',
        },
        text: {
          main: '#1F2933',
          secondary: '#5B6870',
          muted: '#87939A',
        },
        info: {
          DEFAULT: '#2878B5',
          light: '#EAF4FA',
          dark: '#1C5B8C',
        },
        success: {
          DEFAULT: '#2E8B68',
          light: '#E9F6F0',
          dark: '#22694E',
        },
        warning: {
          DEFAULT: '#C9821A',
          light: '#FFF5E5',
          dark: '#9B6312',
        },
        danger: {
          DEFAULT: '#C94A4A',
          light: '#FCECEC',
          dark: '#9E3737',
        }
      }
    },
  },
  plugins: [],
}

