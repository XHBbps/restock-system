// ESLint 9 flat config
import js from '@eslint/js'
import tsParser from '@typescript-eslint/parser'
import tsPlugin from '@typescript-eslint/eslint-plugin'
import vuePlugin from 'eslint-plugin-vue'
import vueParser from 'vue-eslint-parser'
import prettierConfig from 'eslint-config-prettier'

export default [
  {
    ignores: ['dist/**', 'node_modules/**', '*.config.js', '*.config.ts']
  },
  js.configs.recommended,
  {
    files: ['**/*.{ts,tsx,vue}'],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: tsParser,
        ecmaVersion: 2022,
        sourceType: 'module',
        extraFileExtensions: ['.vue']
      },
      globals: {
        // 浏览器全局
        window: 'readonly',
        document: 'readonly',
        console: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        fetch: 'readonly',
        localStorage: 'readonly',
        sessionStorage: 'readonly'
      }
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      vue: vuePlugin
    },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      ...vuePlugin.configs['vue3-recommended'].rules,
      ...prettierConfig.rules,
      // 宪法：禁止 console.log 进生产
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      // 禁止 any 滥用
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'vue/multi-word-component-names': 'off'
    }
  }
]
