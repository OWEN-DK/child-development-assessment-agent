module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
    node: true,
  },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    ecmaFeatures: {
      jsx: true,
    },
  },
  plugins: ['@typescript-eslint', 'react-hooks'],
  rules: {
    'no-unused-vars': 'off',
    '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    '@typescript-eslint/no-explicit-any': 'warn',
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'warn',
    'no-restricted-imports': [
      'error',
      {
        patterns: [
          {
            group: ['**/features/**'],
            message: '禁止跨 feature 导入，请使用 shared 层或 entities 层',
          },
          {
            group: ['**/pages/**'],
            message: '禁止从 pages 导入，pages 层只能由路由使用',
          },
          {
            group: ['**/widgets/**'],
            message: '禁止从 widgets 导入，除非当前是 pages 层',
          },
        ],
      },
    ],
  },
};
