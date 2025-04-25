const colors = require('tailwindcss/colors')

module.exports = {
  content: ["templates/**/*.html"],
  darkMode: 'class',
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      white: colors.white,
      offwhite: '#E6E6E6',
      emerald: colors.emerald,
      gray: colors.gray,
      indigo: colors.indigo,
      yellow: colors.yellow,
      red: colors.red,
      sky: colors.sky,
      blue: colors.blue,
      charcoal: '#172A34',
      orange: '#FF9F00',
      green: '#5AD599',
      black: '#051A26',
      slate: '#314A57',
      steel: '#B5C9D3',
      stone: '#DDE7EC',
      'stone-white': '#DDE7EC',
      gold: '#F4CA1F',
      bronze: '#BB8A56',
      silver: '#B5C9D3',
    },
    extend: {
      colors: {
        slate: {
          100: '#C2D8E2',
          200: '#A1C2D0',
          300: '#7FACBE',
          400: '#5F96AC',
          500: '#314A57',
          600: '#2A404F',
          700: '#233847',
          800: '#1C2C3F',
          900: '#151E37',
        }
      },
      // fontFamily: {
      //   'sans': [
      //     '"Noto Sans"',
      //     process.env.ENVIRONMENT_NAME == 'Development Environment' ?
      //       'serif'
      //     :
      //       'sans-serif',
      //   ],
      // }
    },
  },
  variants: {
    extend: {},
  },
  plugins: [require("@tailwindcss/forms")],
};
