import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  test: {
    globals: true,
    environment: 'jsdom',
    pool: 'threads',
    singleThread: true,
    setupFiles: ['./src/test/setup.ts'],
    // 排除E2E测试（由Playwright运行）
    exclude: [
      '**/node_modules/**',
      '**/node_modules_old/**',
      '**/node_modules_corrupted/**',
      '**/dist/**',
      '**/tests/e2e/**',
      '**/*.e2e.ts',
    ],
    include: [
      '**/tests/unit/**/*.test.ts',
      '**/src/**/__tests__/**/*.spec.ts'
    ],
    coverage: {
      // v8 provider 在本机 Windows 存在 coverage/.tmp 写入竞态（ENOENT，偶发且随文件数放大），
      // 切换 istanbul provider：合并机制不依赖 .tmp 临时文件，Windows 下稳定
      provider: 'istanbul',
      reporter: ['text', 'json', 'html'],
      include: [
        'src/**/*.{ts,vue}',
      ],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/.eslintrc.*',
        '**/mockData',
        'dist/',
        'tests/e2e/',
        'e2e/**',
        'scripts/**',
        '**/__tests__/**',
        'src/App.vue',
        'src/App.test.vue',
        'src/main.ts',
        'src/vite-env.d.ts',
        'src/auto-imports.d.ts',
        'src/components.d.ts',
        'src/env.d.ts',
        // 纯类型定义文件（仅 interface/type，无可执行语句，v8 计数为测量噪音）
        'src/types/analytics.ts',
        'src/types/api.ts',
        'src/types/components.ts',
        'src/types/entities.ts',
        'src/types/helpProject.ts',
        'src/types/index.ts',
        'src/types/models.ts',
        'src/types/organization.ts',
        'src/types/policy.ts',
        'src/components/business/ChartCard/types.ts',
        'src/components/business/DataTable/types.ts',
        'src/components/business/FormBuilder/types.ts',
      ],
      thresholds: {
        'src/utils/**/*.ts': { statements: 100, branches: 100, functions: 100, lines: 100 },
        'src/stores/**/*.ts': { statements: 100, branches: 100, functions: 100, lines: 100 },
        'src/composables/**/*.ts': { statements: 100, branches: 100, functions: 100, lines: 100 },
        'src/api/**/*.ts': { statements: 100, branches: 100, functions: 100, lines: 100 },
        'src/views/**/*.vue': { statements: 100, branches: 100, functions: 100, lines: 100 },
        'src/components/**/*.vue': { statements: 100, branches: 100, functions: 100, lines: 100 },
        'src/router/**/*.ts': { statements: 100, branches: 100, functions: 100, lines: 100 },
        'src/config/**/*.ts': { statements: 100, branches: 100, functions: 100, lines: 100 },
        'src/directives/**/*.ts': { statements: 100, branches: 100, functions: 100, lines: 100 },
      },
    },
    testTimeout: 60000,
    hookTimeout: 60000,
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      // charts/ 下三个图表组件的相对导入指向不存在的 ./BaseChart.vue（实际位于 common/），
      // 测试环境下将其重定向到 common/BaseChart.vue
      './BaseChart.vue': fileURLToPath(
        new URL('./src/components/common/BaseChart.vue', import.meta.url)
      ),
    },
  },
})
