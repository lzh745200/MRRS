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
  // 本地与 CI 一致地串行执行：E2E 共享同一 SQLite 测试库，
  // 多 worker 并行会互相修改数据导致断言随机漂移（failures 每次运行都不同）
  workers: 1,

  /* 报告器 */
  reporter: process.env.CI ? 'github' : 'html',

  /* 全局前置：API 登录一次生成 storageState，避免 UI 登录触发限流 */
  globalSetup: './tests/e2e/global-setup.ts',

  /* 全局配置 */
  use: {
    baseURL: 'http://127.0.0.1:15173',
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
  /* 注意端口隔离：E2E 固定使用 18000/15173，避免与本机已安装运行的
     生产实例（默认占用 8000）或本地 dev server（5173）冲突——否则
     global-setup 的登录请求会打到生产库，出现 401/空页面等诡异失败。 */
  webServer: [
    {
      // 使用项目 venv 的 Python（系统 PATH 可能指向无依赖的全局 Python）
      command: '.venv\\Scripts\\python -m uvicorn app.main:app --port 18000',
      cwd: '../backend',
      url: 'http://127.0.0.1:18000/api/v1/health',
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
      command: 'npm run dev -- --port 15173 --strictPort',
      url: 'http://127.0.0.1:15173',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: {
        ...process.env,
        // 让 Vite 代理指向 E2E 后端（18000）而非默认 8000
        E2E_BACKEND_URL: 'http://127.0.0.1:18000',
      },
    },
  ],
})
