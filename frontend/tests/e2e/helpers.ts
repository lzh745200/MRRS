/**
 * E2E 测试公共辅助函数
 *
 * 认证约定：global-setup.ts 已通过 API 登录并将持久令牌写入 storageState，
 * 各 spec 启动即处于已认证状态（localStorage auth_persist_*）。
 * 因此 login() 不再走 UI 表单（登录接口限流 5 次/分钟/IP，逐用例 UI 登录
 * 会随机触发 429）。UI 登录表单本身的测试见 flows/login.spec.ts
 * （该文件通过 test.use 显式使用空认证态）。
 */
import { type Page, expect } from '@playwright/test'

const TEST_USER = {
  username: process.env.TEST_USERNAME || 'admin',
  password: process.env.TEST_PASSWORD || 'Admin@202507!',
}

/** 供需要直接调 API 的用例使用（如 rural-works 的接口级测试） */
export { TEST_USER }

/**
 * 确认处于已认证状态并落在首页（storageState 已注入令牌）
 */
export async function login(page: Page) {
  await page.goto('/')
  await expect(page).not.toHaveURL(/\/login/, { timeout: 10000 })
}

/**
 * 带重试的导航到指定路由
 */
export async function navigateTo(page: Page, path: string) {
  await page.goto(path)
  await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {})
}
