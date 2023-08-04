const colors = require('tailwindcss/colors')

module.exports = {
  content: ["templates/includes/_header.html", "templates/includes/_footer.html"],
  darkMode: 'class',
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      white: colors.white,
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
      fontFamily: {
        cairo: "'Cairo', sans-serif",
      },
    },
  },
  variants: {
    extend: {},
  },
  // plugins: [require("@tailwindcss/forms")],
};
