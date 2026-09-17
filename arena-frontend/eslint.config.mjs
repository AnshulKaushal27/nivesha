import js from "@eslint/js";

/** @type {import('eslint').Linter.FlatConfig[]} */
const config = [
  js.configs.recommended,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": "off",
    },
  },
];

export default config;
