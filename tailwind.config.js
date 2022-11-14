module.exports = {
  content: ["templates/**/*.html"],
  darkMode: 'media',
  theme: {
    colors: {
      'charcoal': '#172A34',
      'orange': '#FF9F00',
      'green': '#5AD599',
      'black': '#051A26',
      'slate': '#314A57',
      'steel': '#B5C9D3',
      'stone-white': '#DDE7EC',
      'gold': '#F4CA1F',
      'bronze': '#BB8A56',
      'silver': '#B5C9D3',
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
  plugins: [require("@tailwindcss/forms")],
};
