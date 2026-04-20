/** @type { import('@storybook/react').Preview } */
const preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    backgrounds: {
      default: 'light',
      values: [
        {
          name: 'light',
          value: '#FAFAFA',
        },
        {
          name: 'dark',
          value: '#18181B',
        },
      ],
    },
  },
  decorators: [
    (Story, context) => {
      // Add v3 class to both html and body for v3 component styles
      document.documentElement.classList.add("v3");
      document.body.classList.add("v3");

      // Sync Storybook's background selector with project's theme system
      const bgValue = context.globals.backgrounds?.value;
      if (bgValue) {
        const bgConfig = context.parameters.backgrounds?.values?.find((b) => b.value === bgValue);
        const theme = bgConfig?.name === 'dark' ? 'dark' : 'light';
        // Use the project's saveColorMode function if available
        if (typeof window.saveColorMode === 'function') {
          window.saveColorMode(theme);
        } else {
          // Fallback: directly set localStorage and dispatch event
          localStorage.setItem('colorMode', theme);
          window.dispatchEvent(new StorageEvent('storage', {
            key: 'colorMode',
            oldValue: localStorage.getItem('colorMode'),
            newValue: theme,
          }));
        }
      }

      return Story();
    },
  ],
};

export default preview;
