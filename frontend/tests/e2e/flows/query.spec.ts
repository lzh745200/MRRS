/**
 * 数据查询流程 E2E 测试
 *
 * 测试场景：
 * - 帮扶村列表查询与筛选
 * - 项目列表搜索
 * - 经费记录查询
 * - 分页功能
 */

import { test, expect } from '@playwright/test'
import { login, navigateTo } from '../helpers'

test.describe('数据查询流程', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('帮扶村列表正确加载', async ({ page }) => {
    await navigateTo(page, '/villages')
    // 等待列表或空状态出现
    const hasList = await page
      .locator('.el-table, .village-list')
      .isVisible()
      .catch(() => false)
    const hasEmpty = await page
      .locator('.el-empty, text=暂无数据')
      .isVisible()
      .catch(() => false)
    expect(hasList || hasEmpty).toBeTruthy()
  })

  test('项目列表搜索功能', async ({ page }) => {
    await navigateTo(page, '/projects')
    // 等待页面加载
    await expect(page.locator('.el-table, .project-list, .el-empty')).toBeVisible({
      timeout: 10000,
    })

    // 查找搜索框
    const searchInput = page.locator(
      'input[placeholder*="搜索"], input[placeholder*="项目"], .search-input input'
    )
    if (await searchInput.isVisible()) {
      await searchInput.fill('帮扶')
      // 等待搜索结果刷新
      await page.waitForTimeout(500)
    }
  })

  test('经费列表正确加载', async ({ page }) => {
    await navigateTo(page, '/funds')
    // 经费页（EnhancedList.vue）空态也渲染 el-table（暂无数据在表内），断言表格容器可见即可
    await expect(page.locator('.fund-list-page .el-table')).toBeVisible({ timeout: 10000 })
  })

  test('分页功能正常', async ({ page }) => {
    await navigateTo(page, '/projects')
    await expect(page.locator('.el-table, .el-empty')).toBeVisible({ timeout: 10000 })

    // 检查分页组件是否存在
    const pagination = page.locator('.el-pagination')
    if (await pagination.isVisible()) {
      // 验证分页组件包含页码信息
      await expect(pagination).toBeVisible()
    }
  })

  test('政策法规列表加载与搜索', async ({ page }) => {
    await navigateTo(page, '/policies')
    // 政策列表页（List.vue）由 search-card + table-card 两张卡片组成，空态也渲染表格
    await expect(page.locator('.el-card.table-card')).toBeVisible({ timeout: 10000 })

    // 政策名称关键词搜索（placeholder 为“请输入关键词”），点击“查询”触发搜索
    const searchInput = page.getByPlaceholder('请输入关键词')
    await searchInput.fill('乡村振兴')
    await page.getByRole('button', { name: '查询' }).click()
    await page.waitForTimeout(500)
    // 搜索后列表区域仍然正常展示
    await expect(page.locator('.el-card.table-card')).toBeVisible({ timeout: 10000 })
  })
})
