/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './static/js/**/*.js'],
  theme: {
    extend: {
      colors: {
        ricotta: '#FAF6F0',
        ink: '#15201A',
        forest: { DEFAULT: '#1F4D36', dark: '#173A2A', soft: '#E2EDE5' },
        tomato: { DEFAULT: '#E8472F', ink: '#B8361F', soft: '#FDE5DF', light: '#FF8A73' },
        line: { DEFAULT: '#ECE4D7', strong: '#E6DDCF', faint: '#F1EADF' },
        sand: '#F4EFE7',
        muted: { DEFAULT: '#55546A', soft: '#6B6879' },
        thumb: '#1A3326',
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        bar: '0 1px 2px rgba(21,32,26,0.05), 0 24px 48px -12px rgba(31,77,54,0.18)',
        cta: 'inset 0 -2px 0 rgba(0,0,0,0.2), 0 8px 20px -6px rgba(31,77,54,0.55)',
        card: '0 1px 2px rgba(21,32,26,0.04), 0 30px 60px -24px rgba(21,32,26,0.18)',
        seg: '0 1px 2px rgba(21,32,26,0.08), 0 4px 12px -4px rgba(21,32,26,0.12)',
      },
      letterSpacing: { tightest: '-0.048em' },
    },
  },
  plugins: [],
};
