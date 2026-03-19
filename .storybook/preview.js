/** @type { import('@storybook/react').Preview } */
const preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
  },
  decorators: [
    (Story) => {
      // Add v3 class to both html and body for v3 component styles
      document.documentElement.classList.add("v3");
      document.body.classList.add("v3");
      return Story();
    },
  ],
};

export default preview;
