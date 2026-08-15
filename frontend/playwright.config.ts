import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E 测试配置
 *
 * 运行方式：
 *   npx playwright test              # 运行所有 E2E 测试
 *   npx playwright test --ui         # 打开 UI 模式
 *   npx playwright test --headed     # 有头模式运行
 */
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/*.spec.ts',

  /* 全局超时 */
  timeout: 30_000,
  expect: { timeout: 5_000 },

  /* 并行与重试 */
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,

  /* 报告器 */
  reporter: process.env.CI ? 'github' : 'html',

  /* 全局前置：API 登录一次生成 storageState，避免 UI 登录触发限流 */
  globalSetup: './tests/e2e/global-setup.ts',

  /* 全局配置 */
  use: {
    baseURL: 'http://127.0.0.1:5173',
    storageState: './tests/e2e/.auth/admin.json',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    locale: 'zh-CN',
  },

  /* 浏览器 */
  projects: [
    {
      name: 'chromium',
      // 使用系统 Edge 内核（避免下载 Playwright chromium 浏览器包）
      use: { ...devices['Desktop Chrome'], channel: 'msedge' },
    },
  ],

  /* 自动启动 dev server + 后端 */
  webServer: [
    {
      command: 'python -m uvicorn app.main:app --port 8000',
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/api/v1/health',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: {
        ...process.env,
        // E2E 使用独立测试数据库，避免污染生产数据（备份自 rural_revitalization.db）
        // 注意：必须用相对路径（由后端 config.py 解析到动态数据目录）。
        // 绝对路径中的空格若写成 %20，SQLAlchemy 不会解码，会在 C:\ 下创建
        // 名为 "military-Rural%20Revitalization-system" 的幻影目录并新建空库。
        DATABASE_URL: 'sqlite:///./data/e2e_test.db',
      },
    },
    {
      command: 'npm run dev',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
})
