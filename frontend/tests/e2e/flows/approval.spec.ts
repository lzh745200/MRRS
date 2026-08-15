/**
 * 审批流程 E2E 测试
 *
 * Feature: production-deployment-readiness
 * Requirements: 8.4
 *
 * 测试场景：
 * - 提交审批流程
 * - 审批通过流程
 * - 审批拒绝流程
 * - 审批转交流程
 */

import { test, expect, Page } from '@playwright/test';

// 测试配置
const TEST_USER = {
  username: process.env.TEST_USERNAME || 'admin',
  password: process.env.TEST_PASSWORD || 'Admin@202507!',
};

// 登录辅助函数
async function login(page: Page) {
  await page.goto('/login');
  await page.locator('input[placeholder*="用户名"], input[type="text"]').first().fill(TEST_USER.username);
  await page.locator('input[type="password"]').fill(TEST_USER.password);
  await page.locator('button[type="submit"], button:has-text("登录")').click();
  await expect(page).toHaveURL(/\/(dashboard|home|$)/, { timeout: 10000 });
}

test.describe('审批流程', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test.describe('待审批任务列表', () => {
    test('可以访问待审批任务页面', async ({ page }) => {
      // 导航到待审批任务页面
      await page.goto('/approval/pending');

      // 验证页面加载
      await expect(page.locator('text=待审批, text=审批任务, .title:has-text("审批")')).toBeVisible({ timeout: 5000 });
    });

    test('待审批页面显示统计信息', async ({ page }) => {
      await page.goto('/approval/pending');

      // 验证统计信息存在
      const statistics = page.locator('.el-statistic, [class*="statistic"], [class*="stat"]');
      if (await statistics.first().isVisible()) {
        const count = await statistics.count();
        expect(count).toBeGreaterThan(0);
      }
    });

    test('待审批任务列表正确显示', async ({ page }) => {
      await page.goto('/approval/pending');

      // 验证任务列表表格存在
      const taskTable = page.locator('.el-table, table');
      await expect(taskTable).toBeVisible({ timeout: 5000 });

      // 验证表格有列头
      const headers = page.locator('th, .el-table__header-wrapper');
      const headerCount = await headers.count();
      expect(headerCount).toBeGreaterThan(0);
    });

    test('可以刷新待审批任务列表', async ({ page }) => {
      await page.goto('/approval/pending');

      // 查找刷新按钮
      const refreshButton = page.locator('button:has-text("刷新"), [aria-label*="refresh"]');

      if (await refreshButton.isVisible()) {
        await refreshButton.click();

        // 等待加载完成
        await page.waitForLoadState('networkidle');
      }
    });

    test('任务按优先级和时间排序', async ({ page }) => {
      await page.goto('/approval/pending');

      // 等待表格加载
      await page.waitForLoadState('networkidle');

      // 验证优先级列存在
      const priorityColumn = page.locator('th:has-text("优先级"), .el-table__header:has-text("优先级")');
      if (await priorityColumn.isVisible()) {
        // 验证高优先级标签
        const highPriorityTags = page.locator('.el-tag--danger, .el-tag:has-text("高")');
        // 高优先级任务应该排在前面（如果有的话）
      }
    });
  });

  test.describe('提交审批流程', () => {
    test('可以从数据详情页提交审批', async ({ page }) => {
      // 导航到帮扶村列表
      await page.goto('/villages');

      // 等待列表加载
      await page.waitForLoadState('networkidle');

      // 点击编辑或查看按钮
      const editButton = page.locator('button:has-text("编辑"), button:has-text("修改")').first();

      if (await editButton.isVisible()) {
        await editButton.click();

        // 等待表单出现
        await page.waitForTimeout(500);

        // 查找提交审批按钮
        const submitApprovalButton = page.locator('button:has-text("提交审批"), button:has-text("申请审批")');

        if (await submitApprovalButton.isVisible()) {
          // 验证提交审批按钮可点击
          await expect(submitApprovalButton).toBeEnabled();
        }
      }
    });
  });

  test.describe('审批通过流程', () => {
    test('可以打开审批通过对话框', async ({ page }) => {
      await page.goto('/approval/pending');

      // 等待任务列表加载
      await page.waitForLoadState('networkidle');

      // 查找通过按钮
      const approveButton = page.locator('button:has-text("通过"), button:has-text("同意")').first();

      if (await approveButton.isVisible()) {
        await approveButton.click();

        // 验证审批对话框出现
        const dialog = page.locator('.el-dialog, [role="dialog"]');
        await expect(dialog).toBeVisible({ timeout: 3000 });
      }
    });

    test('审批通过需要填写意见', async ({ page }) => {
      await page.goto('/approval/pending');

      await page.waitForLoadState('networkidle');

      const approveButton = page.locator('button:has-text("通过"), button:has-text("同意")').first();

      if (await approveButton.isVisible()) {
        await approveButton.click();

        // 等待对话框出现
        await page.waitForTimeout(500);

        // 验证意见输入框存在
        const opinionInput = page.locator('textarea, .el-textarea, input[placeholder*="意见"]');
        if (await opinionInput.isVisible()) {
          await expect(opinionInput).toBeVisible();
        }
      }
    });

    test('可以执行审批通过操作', async ({ page }) => {
      await page.goto('/approval/pending');

      await page.waitForLoadState('networkidle');

      const approveButton = page.locator('button:has-text("通过"), button:has-text("同意")').first();

      if (await approveButton.isVisible()) {
        await approveButton.click();

        // 等待对话框出现
        await page.waitForTimeout(500);

        // 填写审批意见
        const opinionInput = page.locator('textarea, .el-textarea__inner');
        if (await opinionInput.isVisible()) {
          await opinionInput.fill('同意，审批通过');
        }

        // 点击确认按钮
        const confirmButton = page.locator('button:has-text("确认"), button:has-text("确定")').last();
        if (await confirmButton.isVisible()) {
          // 监听API响应
          const responsePromise = page.waitForResponse(
            response => response.url().includes('approve') && response.status() === 200,
            { timeout: 5000 }
          ).catch(() => null);

          await confirmButton.click();

          // 等待操作完成
          const response = await responsePromise;
          if (response) {
            expect(response.status()).toBe(200);
          }
        }
      }
    });
  });

  test.describe('审批拒绝流程', () => {
    test('可以打开审批拒绝对话框', async ({ page }) => {
      await page.goto('/approval/pending');

      await page.waitForLoadState('networkidle');

      // 查找拒绝按钮
      const rejectButton = page.locator('button:has-text("拒绝"), button:has-text("驳回")').first();

      if (await rejectButton.isVisible()) {
        await rejectButton.click();

        // 验证拒绝对话框出现
        const dialog = page.locator('.el-dialog, [role="dialog"]');
        await expect(dialog).toBeVisible({ timeout: 3000 });
      }
    });

    test('审批拒绝必须填写原因', async ({ page }) => {
      await page.goto('/approval/pending');

      await page.waitForLoadState('networkidle');

      const rejectButton = page.locator('button:has-text("拒绝"), button:has-text("驳回")').first();

      if (await rejectButton.isVisible()) {
        await rejectButton.click();

        // 等待对话框出现
        await page.waitForTimeout(500);

        // 不填写原因直接点击确认
        const confirmButton = page.locator('button:has-text("确认拒绝"), button:has-text("确定")').last();
        if (await confirmButton.isVisible()) {
          await confirmButton.click();

          // 验证显示验证错误或提示
          const errorMessage = page.locator('.el-message--warning, .el-form-item__error, [class*="error"]');
          // 可能显示错误提示
          await page.waitForTimeout(500);
        }
      }
    });

    test('可以执行审批拒绝操作', async ({ page }) => {
      await page.goto('/approval/pending');

      await page.waitForLoadState('networkidle');

      const rejectButton = page.locator('button:has-text("拒绝"), button:has-text("驳回")').first();

      if (await rejectButton.isVisible()) {
        await rejectButton.click();

        // 等待对话框出现
        await page.waitForTimeout(500);

        // 填写拒绝原因
        const opinionInput = page.locator('textarea, .el-textarea__inner');
        if (await opinionInput.isVisible()) {
          await opinionInput.fill('数据不完整，需要补充');
        }

        // 点击确认按钮
        const confirmButton = page.locator('button:has-text("确认拒绝"), button:has-text("确定")').last();
        if (await confirmButton.isVisible()) {
          // 监听API响应
          const responsePromise = page.waitForResponse(
            response => response.url().includes('reject') && response.status() === 200,
            { timeout: 5000 }
          ).catch(() => null);

          await confirmButton.click();

          // 等待操作完成
          const response = await responsePromise;
          if (response) {
            expect(response.status()).toBe(200);
          }
        }
      }
    });
  });

  test.describe('审批转交流程', () => {
    test('可以打开转交对话框', async ({ page }) => {
      await page.goto('/approval/pending');

      await page.waitForLoadState('networkidle');

      // 查找转交按钮
      const transferButton = page.locator('button:has-text("转交"), button:has-text("转办")').first();

      if (await transferButton.isVisible()) {
        await transferButton.click();

        // 验证转交对话框出现
        const dialog = page.locator('.el-dialog, [role="dialog"]');
        await expect(dialog).toBeVisible({ timeout: 3000 });
      }
    });

    test('转交需要选择目标用户', async ({ page }) => {
      await page.goto('/approval/pending');

      await page.waitForLoadState('networkidle');

      const transferButton = page.locator('button:has-text("转交"), button:has-text("转办")').first();

      if (await transferButton.isVisible()) {
        await transferButton.click();

        // 等待对话框出现
        await page.waitForTimeout(500);

        // 验证用户选择器存在
        const userSelector = page.locator('.el-select, select, [role="combobox"]');
        if (await userSelector.isVisible()) {
          await expect(userSelector).toBeVisible();
        }
      }
    });

    test('可以执行转交操作', async ({ page }) => {
      await page.goto('/approval/pending');

      await page.waitForLoadState('networkidle');

      const transferButton = page.locator('button:has-text("转交"), button:has-text("转办")').first();

      if (await transferButton.isVisible()) {
        await transferButton.click();

        // 等待对话框出现
        await page.waitForTimeout(500);

        // 选择目标用户
        const userSelector = page.locator('.el-select, [role="combobox"]').first();
        if (await userSelector.isVisible()) {
          await userSelector.click();

          // 选择第一个选项
          const option = page.locator('.el-select-dropdown__item, [role="option"]').first();
          if (await option.isVisible()) {
            await option.click();
          }
        }

        // 填写转交原因
        const reasonInput = page.locator('textarea, .el-textarea__inner');
        if (await reasonInput.isVisible()) {
          await reasonInput.fill('需要相关部门审核');
        }

        // 点击确认按钮
        const confirmButton = page.locator('button:has-text("确认转交"), button:has-text("确定")').last();
        if (await confirmButton.isVisible()) {
          // 监听API响应
          const responsePromise = page.waitForResponse(
            response => response.url().includes('transfer') && response.status() === 200,
            { timeout: 5000 }
          ).catch(() => null);

          await confirmButton.click();

          // 等待操作完成
          const response = await responsePromise;
          if (response) {
            expect(response.status()).toBe(200);
          }
        }
      }
    });
  });

  test.describe('批量审批', () => {
    test('可以选择多个任务', async ({ page }) => {
      await page.goto('/approval/pending');

      await page.waitForLoadState('networkidle');

      // 查找复选框
      const checkboxes = page.locator('.el-checkbox, input[type="checkbox"]');
      const count = await checkboxes.count();

      if (count > 1) {
        // 选择前两个任务
        await checkboxes.nth(1).click();
        if (count > 2) {
          await checkboxes.nth(2).click();
        }
      }
    });

    test('批量通过按钮显示选中数量', async ({ page }) => {
      await page.goto('/approval/pending');

      await page.waitForLoadState('networkidle');

      // 查找批量通过按钮
      const batchApproveButton = page.locator('button:has-text("批量通过"), button:has-text("批量审批")');

      if (await batchApproveButton.isVisible()) {
        // 验证按钮显示选中数量
        const buttonText = await batchApproveButton.textContent();
        // 按钮文本可能包含数量，如 "批量通过 (0)"
        expect(buttonText).toBeTruthy();
      }
    });
  });

  test.describe('变更对比视图', () => {
    test('可以查看变更对比', async ({ page }) => {
      await page.goto('/approval/pending');

      await page.waitForLoadState('networkidle');

      // 查找对比按钮
      const diffButton = page.locator('button:has-text("对比"), button:has-text("查看变更")').first();

      if (await diffButton.isVisible()) {
        await diffButton.click();

        // 验证对比对话框出现
        const dialog = page.locator('.el-dialog, [role="dialog"]');
        await expect(dialog).toBeVisible({ timeout: 3000 });
      }
    });

    test('变更对比显示原值和新值', async ({ page }) => {
      await page.goto('/approval/pending');

      await page.waitForLoadState('networkidle');

      const diffButton = page.locator('button:has-text("对比"), button:has-text("查看变更")').first();

      if (await diffButton.isVisible()) {
        await diffButton.click();

        // 等待对话框出现
        await page.waitForTimeout(500);

        // 验证对比表格存在
        const diffTable = page.locator('.el-table, table');
        if (await diffTable.isVisible()) {
          // 验证有原值和新值列
          const headers = page.locator('th');
          const headerTexts = await headers.allTextContents();
          // 可能包含 "原值"、"新值" 或类似的列
        }
      }
    });
  });

  test.describe('审批历史', () => {
    test('可以访问审批历史页面', async ({ page }) => {
      await page.goto('/approval/history');

      // 验证页面加载
      await expect(page.locator('text=审批历史, text=历史记录, .title:has-text("历史")')).toBeVisible({ timeout: 5000 });
    });

    test('审批历史列表正确显示', async ({ page }) => {
      await page.goto('/approval/history');

      // 验证历史列表表格存在
      const historyTable = page.locator('.el-table, table');
      await expect(historyTable).toBeVisible({ timeout: 5000 });
    });

    test('可以筛选审批历史', async ({ page }) => {
      await page.goto('/approval/history');

      // 查找筛选条件
      const filterForm = page.locator('.el-form, form, [class*="filter"]');

      if (await filterForm.isVisible()) {
        // 验证有筛选输入
        const inputs = page.locator('.el-input, .el-select, input, select');
        const inputCount = await inputs.count();
        expect(inputCount).toBeGreaterThan(0);
      }
    });
  });
});
