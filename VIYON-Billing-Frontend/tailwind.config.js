/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        viyon: {
          black: "#080808",
          charcoal: "#18181B",
          charcoalLight: "#27272A",
          charcoalMuted: "#3F3F46",
          gold: "#D99B32",
          goldHover: "#C48824",
          goldLight: "#F5D48E",
          goldMuted: "#E9BE6D",
          amber: "#F59E0B",
          amberDark: "#D97706",
          beige: "#F5F2EC",
          beigeDark: "#EBE5DB",
          beigeLight: "#FAF8F5",
          white: "#FFFFFF",
          grayText: "#71717A",
          grayBorder: "#E4E4E7",
        }
      },
      fontFamily: {
        serif: ['"Playfair Display"', 'Georgia', 'serif'],
        display: ['"Cinzel"', '"Playfair Display"', 'serif'],
        sans: ['"Inter"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'Menlo', 'Monaco', 'Courier New', 'monospace'],
      },
    },
  },
  plugins: [],
}
