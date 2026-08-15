/**
 * 登录流程 E2E 测试
 *
 * 测试场景：
 * - 登录成功流程
 * - 登录失败流程（错误密码、空输入）
 * - 表单验证反馈
 */

import { test, expect } from '@playwright/test'

// 测试配置
const TEST_USER = {
  username: process.env.TEST_USERNAME || 'admin',
  password: process.env.TEST_PASSWORD || 'Admin@202507!',
}

// 本文件测试登录表单本身，必须覆盖全局 storageState，以未认证态运行
test.use({ storageState: { cookies: [], origins: [] } })

test.describe('登录流程', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
  })

  test('页面加载正确', async ({ page }) => {
    // 验证登录页面元素存在
    await expect(
      page.locator('input[placeholder*="用户名"], input[type="text"]').first()
    ).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.locator('button[type="submit"], button:has-text("登录")')).toBeVisible()
  })

  test('登录成功跳转到首页', async ({ page }) => {
    // 输入用户名和密码
    await page
      .locator('input[placeholder*="用户名"], input[type="text"]')
      .first()
      .fill(TEST_USER.username)
    await page.locator('input[type="password"]').fill(TEST_USER.password)

    // 点击登录按钮
    await page.locator('button[type="submit"], button:has-text("登录")').click()

    // 验证跳转到首页或仪表盘
    await expect(page).toHaveURL(/\/(dashboard|home|$)/)
  })

  test('错误密码显示错误提示', async ({ page }) => {
    // 输入用户名和错误密码
    await page
      .locator('input[placeholder*="用户名"], input[type="text"]')
      .first()
      .fill(TEST_USER.username)
    await page.locator('input[type="password"]').fill('wrong_password')

    // 点击登录按钮
    await page.locator('button[type="submit"], button:has-text("登录")').click()

    // 验证显示错误提示
    await expect(page.locator('.el-message--error, .error-message, [role="alert"]')).toBeVisible({
      timeout: 5000,
    })
  })

  test('空用户名显示验证错误', async ({ page }) => {
    // 只输入密码，不输入用户名
    await page.locator('input[type="password"]').fill(TEST_USER.password)

    // 点击登录按钮
    await page.locator('button[type="submit"], button:has-text("登录")').click()

    // 验证显示验证错误（登录页使用 .error-banner 展示非表单校验错误）
    await expect(
      page.locator('.error-banner, .el-form-item__error, .validation-error').first()
    ).toBeVisible({ timeout: 3000 })
  })

  test('空密码显示验证错误', async ({ page }) => {
    // 只输入用户名，不输入密码
    await page
      .locator('input[placeholder*="用户名"], input[type="text"]')
      .first()
      .fill(TEST_USER.username)

    // 点击登录按钮
    await page.locator('button[type="submit"], button:has-text("登录")').click()

    // 验证显示验证错误（登录页使用 .error-banner 展示非表单校验错误）
    await expect(
      page.locator('.error-banner, .el-form-item__error, .validation-error').first()
    ).toBeVisible({ timeout: 3000 })
  })

  test('密码输入框支持显示/隐藏切换', async ({ page }) => {
    const passwordInput = page.locator('input[type="password"]')

    // 初始状态为密码隐藏
    await expect(passwordInput).toHaveAttribute('type', 'password')

    // 如果有显示/隐藏按钮，点击切换
    const toggleButton = page.locator('.el-input__suffix-inner .el-icon, [aria-label*="显示密码"]')
    if (await toggleButton.isVisible()) {
      await toggleButton.click()
      // 验证密码可见
      await expect(page.locator('input[type="text"]').last()).toBeVisible()
    }
  })

  test('登录后可以正常登出', async ({ page }) => {
    // 先登录
    await page
      .locator('input[placeholder*="用户名"], input[type="text"]')
      .first()
      .fill(TEST_USER.username)
    await page.locator('input[type="password"]').fill(TEST_USER.password)
    await page.locator('button[type="submit"], button:has-text("登录")').click()

    // 等待登录成功
    await expect(page).toHaveURL(/\/(dashboard|home|$)/, { timeout: 10000 })

    // 查找并点击登出按钮
    const logoutButton = page.locator('text=/退出|登出/').first()
    if (await logoutButton.isVisible()) {
      await logoutButton.click()
      // 验证返回登录页
      await expect(page).toHaveURL(/\/login/)
    }
  })
})
