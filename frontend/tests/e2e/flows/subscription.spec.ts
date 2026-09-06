/**
 * 报表订阅 E2E（工单 003 订阅闭环）
 *
 * 覆盖：订阅管理卡片渲染 → 新建订阅对话框（四要素表单）→ 列表出现 →
 * 立即生成（站内消息语义的 UI 反馈）→ 启停开关 → 删除确认三态。
 * 运行于真实 element-plus（无桩），后端为隔离实例。
 */
import { test, expect } from '@playwright/test'

// 每用例唯一名称：删除用例断言行数归零，残留行（上一用例未删）会干扰计数
const SUB_NAME = () => `E2E订阅测试-${Date.now()}`

async function openSubscriptionSection(page: import('@playwright/test').Page) {
  await page.goto('/export/report')
  await expect(page.getByRole('heading', { name: '订阅管理' })).toBeVisible({
    timeout: 15000,
  })
  // 作用域限定在订阅卡片（页面另有导出历史卡片的「刷新」按钮）
  return page.locator('.subscription-management')
}

test.describe('报表订阅', () => {
  test.beforeEach(async ({ page }) => {
    // 认证态由 global-setup storageState 注入，确认落在首页即可
    await page.goto('/')
    await expect(page).not.toHaveURL(/\/login/, { timeout: 10000 })
  })

  test('订阅管理卡片渲染（表格与新建入口）', async ({ page }) => {
    const card = await openSubscriptionSection(page)
    await expect(card.getByRole('button', { name: '新建订阅' })).toBeVisible()
    await expect(card.getByRole('button', { name: '刷新' })).toBeVisible()
    await expect(card.locator('.el-table')).toBeVisible()
  })

  test('新建订阅：对话框表单 → 创建成功 → 列表出现', async ({ page }) => {
    const SUB_NAME_LOCAL = SUB_NAME()
    const card = await openSubscriptionSection(page)
    await card.getByRole('button', { name: '新建订阅' }).click()

    const dialog = page.locator('.el-dialog', { hasText: '新建报表订阅' })
    await expect(dialog).toBeVisible()

    // 订阅名称
    await dialog.locator('input[placeholder*="每月帮扶村汇总"]').fill(SUB_NAME_LOCAL)

    // 频率 select（第 2 个）：默认每月，切到每周以覆盖 v-model 交互
    const freqSelect = dialog.locator('.el-select').nth(1)
    await freqSelect.click()
    await page
      .locator('.el-select-dropdown:visible .el-select-dropdown__item', {
        hasText: '每周',
      })
      .click()
    // weekly 下「星期」select 出现
    await expect(dialog.getByText('星期', { exact: true })).toBeVisible()

    await dialog.getByRole('button', { name: '创建订阅' }).click()
    await expect(page.locator('.el-message', { hasText: '订阅创建成功' })).toBeVisible({
      timeout: 10000,
    })
    await expect(dialog).toBeHidden()

    // 列表出现新订阅（该行含 启用开关 与 立即生成）
    const row = card.locator('.el-table__row', { hasText: SUB_NAME_LOCAL })
    await expect(row).toBeVisible({ timeout: 10000 })
    await expect(row.getByRole('button', { name: '立即生成' })).toBeVisible()
  })

  test('立即生成：成功反馈且刷新列表', async ({ page }) => {
    const SUB_NAME_LOCAL = SUB_NAME()
    const card = await openSubscriptionSection(page)

    // 前置：确保存在一条订阅（幂等创建，失败则跳过断言行级操作）
    await card.getByRole('button', { name: '新建订阅' }).click()
    const dialog = page.locator('.el-dialog', { hasText: '新建报表订阅' })
    await dialog.locator('input[placeholder*="每月帮扶村汇总"]').fill(SUB_NAME_LOCAL)
    await dialog.getByRole('button', { name: '创建订阅' }).click()
    await expect(page.locator('.el-message', { hasText: '订阅创建成功' })).toBeVisible({
      timeout: 10000,
    })

    const row = card.locator('.el-table__row', { hasText: SUB_NAME_LOCAL }).first()
    await expect(row).toBeVisible({ timeout: 10000 })
    await row.getByRole('button', { name: '立即生成' }).click()
    // 后端生成 xlsx 并落盘，站内消息送达；UI 提示「已生成」
    await expect(page.locator('.el-message', { hasText: '已生成' })).toBeVisible({ timeout: 15000 })
  })

  test('启停开关与删除确认', async ({ page }) => {
    const SUB_NAME_LOCAL = SUB_NAME()
    const card = await openSubscriptionSection(page)

    // 幂等创建
    await card.getByRole('button', { name: '新建订阅' }).click()
    const dialog = page.locator('.el-dialog', { hasText: '新建报表订阅' })
    await dialog.locator('input[placeholder*="每月帮扶村汇总"]').fill(SUB_NAME_LOCAL)
    await dialog.getByRole('button', { name: '创建订阅' }).click()
    await expect(page.locator('.el-message', { hasText: '订阅创建成功' })).toBeVisible({
      timeout: 10000,
    })
    const row = card.locator('.el-table__row', { hasText: SUB_NAME_LOCAL }).first()
    await expect(row).toBeVisible({ timeout: 10000 })

    // 启停开关：启用 → 禁用
    await row.locator('.el-switch').click()
    await expect(page.locator('.el-message', { hasText: '订阅已禁用' })).toBeVisible({
      timeout: 10000,
    })

    // 删除：确认框 → 确定 → 成功提示 → 行消失
    await row.getByRole('button', { name: '删除' }).click()
    const box = page.locator('.el-message-box', { hasText: '删除确认' })
    await expect(box).toBeVisible()
    await box.getByRole('button', { name: '删除' }).click()
    await expect(page.locator('.el-message', { hasText: '订阅已删除' })).toBeVisible({
      timeout: 10000,
    })
    await expect(card.locator('.el-table__row', { hasText: SUB_NAME_LOCAL })).toHaveCount(0)
  })
})
