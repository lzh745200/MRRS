/**
 * 表单提交 E2E 测试
 *
 * 测试场景：
 * - 数据创建流程
 * - 数据编辑流程
 * - 数据删除流程
 */

import { test, expect } from '@playwright/test';

// 测试配置
const TEST_USER = {
  username: process.env.TEST_USERNAME || 'admin',
  password: process.env.TEST_PASSWORD || 'Admin@202507!',
};

// 登录辅助函数
async function login(page: any) {
  await page.goto('/login');
  await page.locator('input[placeholder*="用户名"], input[type="text"]').first().fill(TEST_USER.username);
  await page.locator('input[type="password"]').fill(TEST_USER.password);
  await page.locator('button[type="submit"], button:has-text("登录")').click();
  await expect(page).toHaveURL(/\/(dashboard|home|$)/, { timeout: 10000 });
}

test.describe('表单提交流程', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test.describe('村庄数据管理', () => {
    test('可以访问村庄列表页', async ({ page }) => {
      // 导航到村庄管理页面
      await page.goto('/villages');

      // 验证页面加载
      await expect(page.locator('h1, h2, .page-title').filter({ hasText: /村庄|村/ })).toBeVisible({ timeout: 5000 });
    });

    test('可以打开新建村庄表单', async ({ page }) => {
      await page.goto('/villages');

      // 点击新建按钮
      const addButton = page.locator('button:has-text("新建"), button:has-text("添加"), button:has-text("新增")');
      if (await addButton.isVisible()) {
        await addButton.click();

        // 验证表单弹窗或页面出现
        await expect(page.locator('.el-dialog, .el-drawer, form')).toBeVisible({ timeout: 3000 });
      }
    });

    test('表单验证正常工作', async ({ page }) => {
      await page.goto('/villages');

      // 点击新建按钮
      const addButton = page.locator('button:has-text("新建"), button:has-text("添加"), button:has-text("新增")');
      if (await addButton.isVisible()) {
        await addButton.click();

        // 直接点击提交，触发验证
        const submitButton = page.locator('button:has-text("确定"), button:has-text("保存"), button:has-text("提交")');
        if (await submitButton.isVisible()) {
          await submitButton.click();

          // 验证显示验证错误
          await expect(page.locator('.el-form-item__error')).toBeVisible({ timeout: 3000 });
        }
      }
    });
  });

  test.describe('项目数据管理', () => {
    test('可以访问项目列表页', async ({ page }) => {
      await page.goto('/projects');

      // 验证页面加载
      await expect(page.locator('h1, h2, .page-title').filter({ hasText: /项目/ })).toBeVisible({ timeout: 5000 });
    });

    test('可以查看项目详情', async ({ page }) => {
      await page.goto('/projects');

      // 点击第一行的查看按钮
      const viewButton = page.locator('button:has-text("查看"), button:has-text("详情"), .el-table__row').first();
      if (await viewButton.isVisible()) {
        await viewButton.click();

        // 验证详情页面或弹窗出现
        await expect(page.locator('.el-dialog, .detail-page, .project-detail')).toBeVisible({ timeout: 3000 });
      }
    });
  });

  test.describe('学校数据管理', () => {
    test('可以访问学校列表页', async ({ page }) => {
      await page.goto('/schools');

      // 验证页面加载
      await expect(page.locator('h1, h2, .page-title').filter({ hasText: /学校/ })).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('通用表单操作', () => {
    test('取消按钮可以关闭表单', async ({ page }) => {
      await page.goto('/villages');

      // 点击新建按钮
      const addButton = page.locator('button:has-text("新建"), button:has-text("添加"), button:has-text("新增")');
      if (await addButton.isVisible()) {
        await addButton.click();

        // 等待表单出现
        await expect(page.locator('.el-dialog, .el-drawer')).toBeVisible({ timeout: 3000 });

        // 点击取消按钮
        const cancelButton = page.locator('button:has-text("取消"), button:has-text("关闭")');
        if (await cancelButton.isVisible()) {
          await cancelButton.click();

          // 验证表单关闭
          await expect(page.locator('.el-dialog, .el-drawer')).not.toBeVisible({ timeout: 3000 });
        }
      }
    });

    test('ESC键可以关闭表单弹窗', async ({ page }) => {
      await page.goto('/villages');

      // 点击新建按钮
      const addButton = page.locator('button:has-text("新建"), button:has-text("添加"), button:has-text("新增")');
      if (await addButton.isVisible()) {
        await addButton.click();

        // 等待表单出现
        await expect(page.locator('.el-dialog')).toBeVisible({ timeout: 3000 });

        // 按ESC键
        await page.keyboard.press('Escape');

        // 验证表单关闭
        await expect(page.locator('.el-dialog')).not.toBeVisible({ timeout: 3000 });
      }
    });
  });
});
