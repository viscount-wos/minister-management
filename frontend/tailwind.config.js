/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          bg: '#0f1923',
          card: '#1a2733',
          'card-hover': '#1f3040',
          input: '#14202c',
        },
        accent: {
          DEFAULT: '#e8a639',
          dim: '#c98b2e',
          light: '#f0c060',
        },
        theme: {
          text: '#e0e6ed',
          dim: '#8899a6',
          border: '#2d3e4f',
        },
        success: {
          DEFAULT: '#2ecc71',
          dark: '#27ae60',
        },
        danger: {
          DEFAULT: '#e74c3c',
          dark: '#c0392b',
        },
      },
    },
  },
  plugins: [],
}
