/** @type { import('@storybook/react-webpack5').StorybookConfig } */
const config = {
  stories: ["../storybook/**/*.stories.@(js|jsx)"],
  addons: ["@storybook/addon-essentials", "@storybook/addon-webpack5-compiler-swc"],
  framework: {
    name: "@storybook/react-webpack5",
    options: {},
  },
  webpackFinal: (config) => {
    config.module.rules = config.module.rules.concat([
      {
        test: /\.html$/,
        type: "asset/source",
      },
    ]);
    return config;
  },
};

module.exports = config;
