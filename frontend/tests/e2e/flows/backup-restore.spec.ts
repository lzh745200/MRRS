/**
 * 备份 / 恢复冒烟（W13-T52 第 5 条关键路径）
 *
 * 目标：证明「系统备份管理」页面真实可用，且恢复入口存在覆盖警告、必须二次确认。
 * 安全边界：**绝不真正执行恢复**（会覆盖 E2E 库、导致后续用例全部失败），
 * 只创建一次备份 → 打开恢复确认框 → 取消。
 */
import { test, expect } from '@playwright/test'

test.describe('备份 / 恢复冒烟', () => {
  test('创建备份 → 列表出现记录 → 恢复确认框可见且可取消', async ({ page }) => {
    await page.goto('/system/backup')
    // 诊断上下文：首个用例会触发 Vite 冷编译，放宽等待；失败信息里带 URL 与可见文本
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(1500)
    const diag = `URL=${page.url()} BODY=${(await page.locator('body').innerText()).slice(0, 500)}`
    await expect(page.getByText('系统备份管理'), diag).toBeVisible({ timeout: 45_000 })

    // 1) 打开「创建备份」对话框（表单字段存在）
    await page.getByRole('button', { name: '创建备份' }).click()
    await expect(page.getByText('备份描述')).toBeVisible({ timeout: 10_000 })
    await page.getByPlaceholder('请输入备份描述').fill('E2E 冒烟备份')

    // 2) 确认创建 → 成功提示（后端真实建包）
    await page.getByRole('button', { name: '确定' }).last().click()
    await expect(page.getByText('已创建', { exact: false })).toBeVisible({ timeout: 60_000 })

    // 3) 列表中应出现恢复入口（不执行恢复）
    const restoreBtn = page.getByRole('button', { name: '恢复' }).first()
    await expect(restoreBtn).toBeVisible({ timeout: 20_000 })
    await restoreBtn.click()

    // 4) 恢复确认框：覆盖警告 + 文件信息 + 取消关闭
    await expect(page.getByRole('heading', { name: '恢复备份' })).toBeVisible({ timeout: 10_000 })
    await expect(page.getByText(/覆盖当前所有数据/)).toBeVisible()
    await page.getByRole('button', { name: '取消' }).last().click()
    await expect(page.getByText(/覆盖当前所有数据/)).toBeHidden({ timeout: 10_000 })
  })
})
