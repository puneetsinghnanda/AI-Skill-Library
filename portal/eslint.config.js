import js from '@eslint/js';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    ignores: [
      'dist',
      'dist-demo',
      'node_modules',
      'test-results',
      'playwright-report',
      'coverage',
      'src/api/schema.d.ts',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: { globals: { ...globals.browser } },
    plugins: { 'react-hooks': reactHooks, 'jsx-a11y': jsxA11y },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.flatConfigs.strict.rules,
      // Scrollable table regions and tab panels must be keyboard-focusable (axe scrollable-region-focusable).
      'jsx-a11y/no-noninteractive-tabindex': ['error', { roles: ['tabpanel', 'region'], tags: [] }],
      'no-restricted-syntax': [
        'error',
        {
          selector:
            'Literal[value=/#[0-9a-fA-F]{3,8}\\b/][parent.type="Property"][parent.key.name=/color|background|fill|stroke/i]',
          message: 'Use a var(--tm-*) token from src/theme/tokens.css, not a hex colour.',
        },
      ],
    },
  },
  {
    files: ['src/screens/**', 'src/app/**', 'src/components/**', 'src/auth/**', 'src/lib/**'],
    ignores: ['**/*.test.ts', '**/*.test.tsx'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['**/mocks/**', '**/demo/**', 'msw', 'msw/*'],
              message: 'Mocks and demo code are only for tests and `npm run demo` (SDD-09 §1.3).',
            },
          ],
        },
      ],
    },
  },
  {
    files: ['scripts/**/*.mjs', '*.config.{js,ts}', 'e2e/**/*.ts'],
    languageOptions: { globals: { ...globals.node } },
  },
);
