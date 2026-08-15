/**
 * 经费管理 E2E 测试
 *
 * 重点覆盖：
 * - 列表页面加载
 * - 统计卡片
 * - 搜索筛选
 * - 新增经费
 * - 批量选择
 * - 导出
 */
import { test, expect } from '@playwright/test'
import { login, navigateTo } from '../helpers'

test.describe('经费管理', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('列表页面正确加载', async ({ page }) => {
    await navigateTo(page, '/funds')
    // 页面标题
    await expect(page.locator('.page-title')).toContainText('经费管理')
    // 数据表格
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 10000 })
  })

  test('统计卡片展示', async ({ page }) => {
    await navigateTo(page, '/funds')
    const statItems = page.locator('.stat-item')
    await expect(statItems.first()).toBeVisible({ timeout: 10000 })
    // 应有5个统计卡片
    const count = await statItems.count()
    expect(count).toBe(5)
  })

  test('搜索筛选功能', async ({ page }) => {
    await navigateTo(page, '/funds')
    await expect(page.locator('.filter-card')).toBeVisible()

    // 搜索框输入
    const searchInput = page.locator('.filter-card input').first()
    await searchInput.fill('测试')
    await page.locator('button:has-text("搜索")').click()
    await page.waitForLoadState('networkidle').catch(() => {})
    await expect(page.locator('.el-table')).toBeVisible()
  })

  test('重置筛选', async ({ page }) => {
    await navigateTo(page, '/funds')
    const searchInput = page.locator('.filter-card input').first()
    await searchInput.fill('测试')
    await page.locator('button:has-text("重置")').click()
    await expect(searchInput).toHaveValue('')
  })

  test('新增经费按钮导航', async ({ page }) => {
    await navigateTo(page, '/funds')
    const createBtn = page.locator('button:has-text("新增经费")')
    await expect(createBtn).toBeVisible()
    await createBtn.click()
    await expect(page).toHaveURL(/\/funds\/create/, { timeout: 5000 })
  })

  test('预算管理按钮导航', async ({ page }) => {
    await navigateTo(page, '/funds')
    const budgetBtn = page.locator('button:has-text("预算管理")')
    await expect(budgetBtn).toBeVisible()
    await budgetBtn.click()
    await expect(page).toHaveURL(/\/funds\/budget/, { timeout: 5000 })
  })

  test('分页组件展示', async ({ page }) => {
    await navigateTo(page, '/funds')
    await expect(page.locator('.el-pagination')).toBeVisible({ timeout: 10000 })
  })

  test('批量选择功能', async ({ page }) => {
    await navigateTo(page, '/funds')
    await page.waitForLoadState('networkidle').catch(() => {})

    const selectAll = page.locator('.el-table__header .el-checkbox')
    if (await selectAll.isVisible()) {
      // el-checkbox 的可见框体由 ::after 伪元素渲染，原生可点击区可能持续"不稳定"，
      // force 跳过稳定性检查（语义仍是用户点击表头全选）
      await selectAll.click({ force: true })
      const hasRows = await page.locator('.el-table__row').count()
      if (hasRows > 0) {
        await expect(page.locator('.batch-toolbar')).toBeVisible({ timeout: 3000 })
        await expect(page.locator('.batch-info')).toContainText('已选择')

        // 取消选择
        await page.locator('button:has-text("取消选择")').click()
        await expect(page.locator('.batch-toolbar')).not.toBeVisible()
      }
    }
  })

  test('按状态点击统计卡片筛选', async ({ page }) => {
    await navigateTo(page, '/funds')
    // 点击"待审批"卡片
    const pendingCard = page.locator('.stat-item:nth-child(3)')
    if (await pendingCard.isVisible()) {
      await pendingCard.click()
      await page.waitForLoadState('networkidle').catch(() => {})
      await expect(page.locator('.el-table')).toBeVisible()
    }
  })
})
