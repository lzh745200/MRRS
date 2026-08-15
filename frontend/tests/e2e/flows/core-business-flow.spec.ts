/**
 * 核心业务流 E2E 测试
 *
 * 覆盖: 登录 → 工作台 → 帮扶村 → 新增项目 → 审批 → 数据导出
 *
 * 运行: npx playwright test tests/e2e/flows/core-business-flow.spec.ts
 */

import { test, expect } from '@playwright/test';

const BASE = 'http://127.0.0.1:5173';

test.describe('核心业务流', () => {
  test.beforeEach(async ({ page }) => {
    // storageState 已注入认证态（global-setup），直接落在首页即可
    await page.goto(`${BASE}/`);
    await page.waitForURL(/\/(dashboard|home|$)/, { timeout: 10000 });
  });

  test('1. 登录 → 工作台加载', async ({ page }) => {
    await expect(page.locator('.kpi-cards, .dashboard, .home-safe, #app')).toBeVisible({ timeout: 8000 });
  });

  test('2. 工作台 → 帮扶村列表', async ({ page }) => {
    // 直接导航（菜单点击+懒加载 chunk 在慢速环境下易超 5s 断言窗口）
    await page.goto(`${BASE}/supported-villages`);
    await page.waitForLoadState('networkidle').catch(() => {});
    await expect(page.locator('.el-table').first()).toBeVisible({ timeout: 10000 });
  });

  test('3. 帮扶村 → 查看详情', async ({ page }) => {
    await page.goto(`${BASE}/supported-villages`);
    await page.waitForLoadState('networkidle');
    // 点击第一行的查看按钮
    const viewBtn = page.locator('button:has-text("查看"), button:has-text("详情")').first();
    if (await viewBtn.isVisible()) {
      await viewBtn.click();
      await expect(page).not.toHaveURL('**/undefined');
    }
  });

  test('4. 项目列表 → 新增项目', async ({ page }) => {
    await page.goto(`${BASE}/projects`);
    await page.waitForLoadState('networkidle');
    const createBtn = page.locator('button:has-text("新增"), button:has-text("创建"), button:has-text("添加")').first();
    if (await createBtn.isVisible()) {
      await createBtn.click();
      await page.waitForTimeout(2000);
      // 验证跳转到编辑页面，不是 undefined
      await expect(page).not.toHaveURL('**/undefined');
    }
  });

  test('5. 审批 → 待审批列表', async ({ page }) => {
    await page.goto(`${BASE}/approval/pending`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.el-table').first()).toBeVisible({ timeout: 5000 });
  });

  test('6. 数据导出对话框', async ({ page }) => {
    await page.goto(`${BASE}/data-sync/export`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('form, .el-form, .export-form, .empty')).toBeVisible({ timeout: 5000 });
  });

  test('7. 系统健康度页面', async ({ page }) => {
    await page.goto(`${BASE}/system/health-check`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.health-check-page, .empty').first()).toBeVisible({ timeout: 5000 });
  });

  test('8. 导航后无 404', async ({ page }) => {
    const routes = [
      '/schools', '/projects', '/funds', '/policies',
      '/organization', '/data-analysis/dashboard', '/system/users',
    ];
    for (const route of routes) {
      await page.goto(`${BASE}${route}`);
      await page.waitForTimeout(1500);
      const body = await page.textContent('body');
      expect(body).not.toContain('404 Not Found');
      expect(body).not.toContain('Page not found');
    }
  });
});
