/**
 * 导航正确性 E2E 测试
 *
 * 测试场景：
 * - 侧边栏导航链接正确跳转
 * - 面包屑导航显示正确
 * - 旧路由重定向正常
 * - 404 页面处理
 */

import { test, expect } from '@playwright/test'
import { login, navigateTo } from '../helpers'

test.describe('导航正确性', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('工作台页面正确加载', async ({ page }) => {
    await navigateTo(page, '/dashboard')
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('帮扶项目管理导航正确', async ({ page }) => {
    await navigateTo(page, '/projects')
    await expect(page).toHaveURL(/\/projects/)
    await expect(page.locator('.el-table, .project-list, .el-empty')).toBeVisible({
      timeout: 10000,
    })
  })

  test('帮扶村管理导航正确', async ({ page }) => {
    await navigateTo(page, '/villages')
    // 旧路由 /villages 重定向到 /supported-villages
    await expect(page).toHaveURL(/\/supported-villages/)
  })

  test('经费管理导航正确', async ({ page }) => {
    await navigateTo(page, '/funds')
    await expect(page).toHaveURL(/\/funds/)
  })

  test('政策法规导航正确', async ({ page }) => {
    await navigateTo(page, '/policies')
    await expect(page).toHaveURL(/\/policies/)
  })

  test('旧路由 /statistics 重定向到 /data-analysis', async ({ page }) => {
    await navigateTo(page, '/statistics')
    await expect(page).toHaveURL(/\/data-analysis/)
  })

  test('组织机构页面导航正确', async ({ page }) => {
    // /organizations 是现行有效路由（组织机构列表页），并非旧路由
    await navigateTo(page, '/organizations')
    await expect(page).toHaveURL(/\/organizations/)
  })

  test('旧路由 /system/logs 重定向到 /system/audit', async ({ page }) => {
    await navigateTo(page, '/system/logs')
    await expect(page).toHaveURL(/\/system\/audit/)
  })

  test('不存在的路由显示 404 页面', async ({ page }) => {
    await navigateTo(page, '/this-page-does-not-exist')
    // 应显示 404 页面或 NotFound 组件
    const has404 = await page
      .locator('text=/404|页面不存在|找不到/')
      .first()
      .isVisible()
      .catch(() => false)
    expect(has404).toBeTruthy()
  })

  test('根路径重定向到 /dashboard', async ({ page }) => {
    await navigateTo(page, '/')
    await expect(page).toHaveURL(/\/dashboard/)
  })
})
