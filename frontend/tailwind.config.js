/** @type {import('tailwindcss').Config} */

// Colours resolve through CSS custom properties so the palette can be swapped
// at runtime without rebuilding. Each variable holds space-separated RGB
// channels, which is what Tailwind's <alpha-value> placeholder needs in order
// to keep tinted utilities like `bg-accent/20` correct in every theme.
// The theme values themselves live in src/index.css.
const token = (name) => `rgb(var(${name}) / <alpha-value>)`;

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          bg: token('--c-dark-bg'),
          card: token('--c-dark-card'),
          'card-hover': token('--c-dark-card-hover'),
          input: token('--c-dark-input'),
        },
        accent: {
          DEFAULT: token('--c-accent'),
          dim: token('--c-accent-dim'),
          light: token('--c-accent-light'),
        },
        theme: {
          text: token('--c-theme-text'),
          dim: token('--c-theme-dim'),
          border: token('--c-theme-border'),
        },
        success: {
          DEFAULT: token('--c-success'),
          dark: token('--c-success-dark'),
        },
        danger: {
          DEFAULT: token('--c-danger'),
          dark: token('--c-danger-dark'),
        },
        warning: {
          DEFAULT: token('--c-warning'),
          dark: token('--c-warning-dark'),
        },
        // Demand levels on the time-preference heat map. Kept as tokens so the
        // grid and the guide's legend cannot drift apart.
        heat: {
          low: token('--c-heat-low'),
          mid: token('--c-heat-mid'),
          high: token('--c-heat-high'),
        },
        // SVS battle planner: group accents (main / counter / extra) and troop-ratio segments. Aliases of the
        // theme tokens above, so every theme keeps its tested contrast.
        team: {
          main: token('--c-heat-low'),
          counter: token('--c-heat-high'),
          extra: token('--c-success'),
        },
        troop: {
          inf: token('--c-heat-mid'),
          lan: token('--c-heat-low'),
          mks: token('--c-success'),
        },
      },
    },
  },
  plugins: [],
}
