/**
 * 帮扶项目管理 E2E 测试
 *
 * 重点覆盖：
 * - 列表页面加载
 * - 搜索筛选
 * - 统计卡片
 * - 新建项目流程
 * - 分页
 * - 批量选择
 */
import { test, expect } from '@playwright/test'
import { login, navigateTo } from '../helpers'

test.describe('帮扶项目管理', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('列表页面正确加载', async ({ page }) => {
    await navigateTo(page, '/projects')
    // 页面标题
    await expect(page.locator('.page-title')).toContainText('帮扶项目管理')
    // 统计行
    await expect(page.locator('.stats-row, .stat-item').first()).toBeVisible({ timeout: 10000 })
    // 数据表格
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 10000 })
  })

  test('统计卡片展示正确', async ({ page }) => {
    await navigateTo(page, '/projects')
    const statItems = page.locator('.stat-item')
    await expect(statItems.first()).toBeVisible({ timeout: 10000 })
    // 应有4个统计卡片
    const count = await statItems.count()
    expect(count).toBe(4)
  })

  test('搜索筛选功能', async ({ page }) => {
    await navigateTo(page, '/projects')
    // 筛选区域存在
    await expect(page.locator('.filter-card')).toBeVisible()

    // 搜索框输入
    const searchInput = page.locator('.filter-card input').first()
    await searchInput.fill('测试')

    // 点击搜索
    await page.locator('button:has-text("搜索")').click()
    await page.waitForLoadState('networkidle').catch(() => {})

    // 页面不崩溃
    await expect(page.locator('.el-table')).toBeVisible()
  })

  test('重置筛选', async ({ page }) => {
    await navigateTo(page, '/projects')
    const searchInput = page.locator('.filter-card input').first()
    await searchInput.fill('测试')

    await page.locator('button:has-text("重置")').click()
    await expect(searchInput).toHaveValue('')
  })

  test('新建项目按钮可点击', async ({ page }) => {
    await navigateTo(page, '/projects')
    const createBtn = page.locator('button:has-text("新建项目")')
    await expect(createBtn).toBeVisible()

    await createBtn.click()
    await expect(page).toHaveURL(/\/projects\/create/, { timeout: 5000 })
  })

  test('分页组件展示', async ({ page }) => {
    await navigateTo(page, '/projects')
    await expect(page.locator('.el-pagination')).toBeVisible({ timeout: 10000 })
  })

  test('批量选择功能', async ({ page }) => {
    await navigateTo(page, '/projects')
    await page.waitForLoadState('networkidle').catch(() => {})

    // 勾选表头全选框（el-checkbox 可见框体为伪元素渲染，原生区域持续"不稳定"，
    // force 跳过稳定性检查）
    const selectAll = page.locator('.el-table__header .el-checkbox')
    if (await selectAll.isVisible()) {
      await selectAll.click({ force: true })
      // 如果有数据，批量操作栏应显示
      const hasRows = await page.locator('.el-table__row').count()
      if (hasRows > 0) {
        await expect(page.locator('.batch-toolbar')).toBeVisible({ timeout: 3000 })
        await expect(page.locator('.batch-info')).toContainText('已选择')
      }
    }
  })

  test('点击统计卡片筛选', async ({ page }) => {
    await navigateTo(page, '/projects')
    // 点击"进行中"卡片
    const inProgressCard = page.locator('.stat-clickable:nth-child(2)')
    if (await inProgressCard.isVisible()) {
      await inProgressCard.click()
      await page.waitForLoadState('networkidle').catch(() => {})
      await expect(page.locator('.el-table')).toBeVisible()
    }
  })
})
