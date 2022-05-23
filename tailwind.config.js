module.exports = {
  purge: ["templates/**/*.html"],
  darkMode: false,
  theme: {
    colors: {
      'charcoal': '#172A34',
      'orange': '#FF9F00',
      'green': '#5AD599',
      'black': '#051A26',
      'slate': '#314A57',
      'steel': '#B5C9D3',
      'stone-white': '#DDE7EC',
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
  plugins: [],
};
