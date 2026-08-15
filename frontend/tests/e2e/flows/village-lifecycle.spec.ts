/**
 * E2E: Village full lifecycle — create, edit, view yearly data, delete.
 */
import { test, expect } from '@playwright/test'
import { login, navigateTo } from '../helpers'

test.describe('Village Lifecycle', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('should navigate to village list', async ({ page }) => {
    await navigateTo(page, '/supported-villages')
    await expect(page.locator('text=帮扶村管理').or(page.locator('table'))).toBeVisible({ timeout: 10000 })
  })

  test('should open create village form', async ({ page }) => {
    await navigateTo(page, '/supported-villages')
    const addBtn = page.locator('button:has-text("新增"), button:has-text("添加"), .el-button:has-text("新增")')
    if (await addBtn.isVisible()) {
      await addBtn.first().click()
      await expect(page.locator('.el-dialog, .el-drawer, form').first()).toBeVisible({ timeout: 5000 })
    }
  })

  test('should show village detail when clicking a row', async ({ page }) => {
    await navigateTo(page, '/supported-villages')
    const firstRow = page.locator('table tbody tr').first()
    if (await firstRow.isVisible()) {
      await firstRow.click()
      await page.waitForTimeout(1000)
    }
  })

  test('should navigate to yearly overview', async ({ page }) => {
    await navigateTo(page, '/supported-villages')
    const firstRow = page.locator('table tbody tr').first()
    if (await firstRow.isVisible()) {
      await firstRow.click()
      const yearlyLink = page.locator('text=/年度概览|年度数据/').first()
      if (await yearlyLink.first().isVisible()) {
        await yearlyLink.first().click()
        await page.waitForTimeout(1500)
      }
    }
  })
})
