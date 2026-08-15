/**
 * Dashboard（工作台）E2E 测试
 *
 * 重点覆盖：
 * - 页面正确加载
 * - 核心统计指标展示
 * - 快捷导航可用
 * - 项目进度图表
 * - 经费概况
 */
import { test, expect } from '@playwright/test'
import { login, navigateTo } from '../helpers'

test.describe('工作台 Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('页面正确加载 - 展示欢迎横幅', async ({ page }) => {
    await navigateTo(page, '/dashboard')
    // 页面根容器（真实类名为 dashboard-home dashboard-modern）
    await expect(page.locator('.dashboard-home')).toBeVisible({ timeout: 10000 })
    // 欢迎标题是唯一的 h1（PageHeader.vue：欢迎回来，xxx）
    await expect(page.getByRole('heading', { level: 1 })).toContainText('欢迎回来')
  })

  test('核心统计指标展示', async ({ page }) => {
    await navigateTo(page, '/dashboard')
    // 统计卡片区域
    const statsGrid = page.locator('.stats-grid, .stat-card').first()
    await expect(statsGrid).toBeVisible({ timeout: 10000 })
    // 至少有3个统计卡片
    const cardCount = await page.locator('.stat-card').count()
    expect(cardCount).toBeGreaterThanOrEqual(3)
  })

  test('快捷导航功能可用', async ({ page }) => {
    await navigateTo(page, '/dashboard')
    // 快捷入口面板（quick-panel 内嵌 QuickActions 折叠分组）
    const quickPanel = page.locator('.quick-panel')
    await expect(quickPanel).toBeVisible({ timeout: 10000 })

    // 点击"新建项目"快捷按钮
    // 限定在快捷面板内定位，避开页头与常用操作条上的同名按钮
    const createBtn = quickPanel.locator('.action-btn', { hasText: '新建项目' })
    await expect(createBtn).toBeVisible({ timeout: 10000 })
    await createBtn.click()
    await expect(page).toHaveURL(/\/projects\/create/, { timeout: 5000 })
  })

  test('项目进度表格展示', async ({ page }) => {
    await navigateTo(page, '/dashboard')
    // 项目进度区块（ChartRow.vue 图表卡片，真实标题为"项目进度跟踪"）
    const projectCard = page.locator('.chart-card').filter({ hasText: '项目进度跟踪' })
    await expect(projectCard).toBeVisible({ timeout: 10000 })

    // 图表数据异步加载：ECharts 画布 / 空或错误状态 / 加载骨架，任一可见即区块正常渲染
    await expect(projectCard.locator('.chart-body, .chart-state, .chart-skeleton')).toBeVisible({
      timeout: 10000,
    })
  })

  test('经费概况展示', async ({ page }) => {
    await navigateTo(page, '/dashboard')
    // 经费区块（ChartRow.vue 图表卡片，真实标题为"经费使用概览"）
    const fundCard = page.locator('.chart-card').filter({ hasText: '经费使用概览' })
    await expect(fundCard).toBeVisible({ timeout: 10000 })

    // 经费统计数值：KPI 横条中的"帮扶经费"统计卡片（KpiCards.vue）
    const fundKpiValue = page
      .locator('.stat-card')
      .filter({ hasText: '帮扶经费' })
      .locator('.stat-value')
    await expect(fundKpiValue).toBeVisible({ timeout: 10000 })
  })

  test('近期动态展示', async ({ page }) => {
    await navigateTo(page, '/dashboard')
    // 近期动态区块
    const activitySection = page.locator('text=近期动态').first()
    await expect(activitySection).toBeVisible({ timeout: 10000 })
  })

  test('待办事项功能', async ({ page }) => {
    await navigateTo(page, '/dashboard')
    // 工作台页内没有待办输入框；待办事项入口在侧边栏菜单（跳转 /todos）
    await page.getByRole('menuitem', { name: '待办事项' }).click()
    await expect(page).toHaveURL(/\/todos/, { timeout: 5000 })

    // 待办页面标题与新增待办输入框
    await expect(page.locator('.todos-page .page-title')).toContainText('待办事项', {
      timeout: 10000,
    })
    await expect(page.getByPlaceholder(/输入待办事项/)).toBeVisible({ timeout: 10000 })
  })
})
