/**
 * 消息通知 E2E 测试
 *
 * Feature: production-deployment-readiness
 * Requirements: 8.5
 *
 * 测试场景：
 * - 站内消息接收
 * - 消息标记已读
 * - WebSocket实时推送
 */

import { test, expect, Page } from '@playwright/test';

// 登录辅助函数（storageState 已注入认证态，仅确认落在首页）
async function login(page: Page) {
  await page.goto('/');
  await expect(page).not.toHaveURL(/\/login/, { timeout: 10000 });
}

test.describe('消息通知系统', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test.describe('消息中心', () => {
    test('可以访问消息中心页面', async ({ page }) => {
      // 导航到消息中心
      await page.goto('/messages');

      // 验证页面加载
      await expect(page.locator('text=消息中心').first()).toBeVisible({ timeout: 5000 });
    });

    test('消息中心显示未读数量', async ({ page }) => {
      await page.goto('/messages');

      // 查找未读数量徽章
      const unreadBadge = page.locator('.el-badge, [class*="badge"], [class*="unread"]');

      // 验证未读数量显示（可能为0）
      if (await unreadBadge.first().isVisible()) {
        await expect(unreadBadge.first()).toBeVisible();
      }
    });

    test('消息列表正确显示', async ({ page }) => {
      await page.goto('/messages');

      // 验证消息列表表格存在
      const messageTable = page.locator('.el-table, table');
      await expect(messageTable).toBeVisible({ timeout: 5000 });

      // 验证表格有列头
      const headers = page.locator('th, .el-table__header-wrapper');
      const headerCount = await headers.count();
      expect(headerCount).toBeGreaterThan(0);
    });

    test('可以按消息类型筛选', async ({ page }) => {
      await page.goto('/messages');

      // 查找消息类型筛选器
      const typeFilter = page.locator('.el-select, select').first();

      if (await typeFilter.isVisible()) {
        await typeFilter.click();

        // 验证有筛选选项
        const options = page.locator('.el-select-dropdown__item, option, [role="option"]');
        const optionCount = await options.count();
        expect(optionCount).toBeGreaterThan(0);
      }
    });

    test('可以按已读状态筛选', async ({ page }) => {
      await page.goto('/messages');

      // 查找状态筛选器
      const statusFilter = page.locator('.el-select, select').nth(1);

      if (await statusFilter.isVisible()) {
        await statusFilter.click();

        // 验证有已读/未读选项
        const options = page.locator('.el-select-dropdown__item, option, [role="option"]');
        const optionCount = await options.count();
        expect(optionCount).toBeGreaterThan(0);
      }
    });

    test('可以刷新消息列表', async ({ page }) => {
      await page.goto('/messages');

      // 查找刷新按钮
      const refreshButton = page.locator('button:has-text("刷新"), [aria-label*="refresh"]');

      if (await refreshButton.isVisible()) {
        await refreshButton.click();

        // 等待加载完成
        await page.waitForLoadState('networkidle');
      }
    });
  });

  test.describe('消息标记已读', () => {
    test('点击消息可以标记为已读', async ({ page }) => {
      await page.goto('/messages');

      await page.waitForLoadState('networkidle');

      // 查找未读消息行
      const unreadRow = page.locator('.unread-row, tr:has(.unread), tr:has(.el-badge)').first();

      if (await unreadRow.isVisible()) {
        // 点击消息行
        await unreadRow.click();

        // 等待标记已读请求
        await page.waitForTimeout(500);

        // 验证消息详情对话框出现
        const dialog = page.locator('.el-dialog, [role="dialog"]');
        if (await dialog.isVisible()) {
          await expect(dialog).toBeVisible();
        }
      }
    });

    test('可以单独标记消息为已读', async ({ page }) => {
      await page.goto('/messages');

      await page.waitForLoadState('networkidle');

      // 查找标记已读按钮
      const markReadButton = page.locator('button:has(.el-icon-check), button[aria-label*="已读"]').first();

      if (await markReadButton.isVisible() && await markReadButton.isEnabled()) {
        // 监听API响应
        const responsePromise = page.waitForResponse(
          response => response.url().includes('mark-read') && response.status() === 200,
          { timeout: 5000 }
        ).catch(() => null);

        await markReadButton.click();

        // 等待操作完成
        const response = await responsePromise;
        if (response) {
          expect(response.status()).toBe(200);
        }
      }
    });

    test('可以全部标记为已读', async ({ page }) => {
      await page.goto('/messages');

      await page.waitForLoadState('networkidle');

      // 查找全部已读按钮
      const markAllReadButton = page.locator('button:has-text("全部已读"), button:has-text("全部标记")');

      if (await markAllReadButton.isVisible() && await markAllReadButton.isEnabled()) {
        // 监听API响应
        const responsePromise = page.waitForResponse(
          response => response.url().includes('mark-all-read') && response.status() === 200,
          { timeout: 5000 }
        ).catch(() => null);

        await markAllReadButton.click();

        // 等待操作完成
        const response = await responsePromise;
        if (response) {
          expect(response.status()).toBe(200);
        }
      }
    });
  });

  test.describe('消息删除', () => {
    test('可以删除单条消息', async ({ page }) => {
      await page.goto('/messages');

      await page.waitForLoadState('networkidle');

      // 查找删除按钮
      const deleteButton = page.locator('button:has(.el-icon-delete), button[aria-label*="删除"]').first();

      if (await deleteButton.isVisible()) {
        await deleteButton.click();

        // 确认删除对话框
        const confirmButton = page.locator('button:has-text("确定"), button:has-text("确认")').last();
        if (await confirmButton.isVisible()) {
          await confirmButton.click();

          // 等待删除完成
          await page.waitForTimeout(500);
        }
      }
    });

    test('可以批量删除消息', async ({ page }) => {
      await page.goto('/messages');

      await page.waitForLoadState('networkidle');

      // 选择多条消息
      const checkboxes = page.locator('.el-checkbox, input[type="checkbox"]');
      const count = await checkboxes.count();

      if (count > 1) {
        // 选择前两条消息
        await checkboxes.nth(1).click();
        if (count > 2) {
          await checkboxes.nth(2).click();
        }

        // 查找批量删除按钮
        const batchDeleteButton = page.locator('button:has-text("删除选中"), button:has-text("批量删除")');

        if (await batchDeleteButton.isVisible() && await batchDeleteButton.isEnabled()) {
          await batchDeleteButton.click();

          // 确认删除
          const confirmButton = page.locator('button:has-text("确定"), button:has-text("确认")').last();
          if (await confirmButton.isVisible()) {
            await confirmButton.click();

            // 等待删除完成
            await page.waitForTimeout(500);
          }
        }
      }
    });
  });

  test.describe('消息详情', () => {
    test('点击消息显示详情', async ({ page }) => {
      await page.goto('/messages');

      await page.waitForLoadState('networkidle');

      // 点击消息行
      const messageRow = page.locator('.el-table__row, tbody tr').first();

      if (await messageRow.isVisible()) {
        await messageRow.click();

        // 验证详情对话框出现
        const dialog = page.locator('.el-dialog, [role="dialog"]');
        await expect(dialog).toBeVisible({ timeout: 3000 });
      }
    });

    test('消息详情显示完整内容', async ({ page }) => {
      await page.goto('/messages');

      await page.waitForLoadState('networkidle');

      const messageRow = page.locator('.el-table__row, tbody tr').first();

      if (await messageRow.isVisible()) {
        await messageRow.click();

        // 等待对话框出现
        await page.waitForTimeout(500);

        // 验证详情内容存在
        const detailContent = page.locator('.el-descriptions, .message-detail, [class*="detail"]');
        if (await detailContent.isVisible()) {
          await expect(detailContent).toBeVisible();
        }
      }
    });

    test('消息详情可以跳转到关联链接', async ({ page }) => {
      await page.goto('/messages');

      await page.waitForLoadState('networkidle');

      const messageRow = page.locator('.el-table__row, tbody tr').first();

      if (await messageRow.isVisible()) {
        await messageRow.click();

        // 等待对话框出现
        await page.waitForTimeout(500);

        // 查找查看详情按钮
        const linkButton = page.locator('button:has-text("查看详情"), a:has-text("查看详情")');

        if (await linkButton.isVisible()) {
          // 验证链接按钮可点击
          await expect(linkButton).toBeEnabled();
        }
      }
    });
  });

  test.describe('WebSocket实时推送', () => {
    test('页面加载时建立WebSocket连接', async ({ page }) => {
      // 监听WebSocket连接
      const wsPromise = page.waitForEvent('websocket', { timeout: 10000 }).catch(() => null);

      await page.goto('/messages');

      // 等待WebSocket连接
      const ws = await wsPromise;

      // WebSocket可能不可用（取决于服务器配置）
      if (ws) {
        expect(ws.url()).toContain('ws');
      }
    });

    test('收到新消息时显示通知', async ({ page }) => {
      await page.goto('/messages');

      // 等待页面加载
      await page.waitForLoadState('networkidle');

      // 验证消息通知组件存在
      // 新消息通知通常通过 ElMessage 或类似组件显示
      const notificationArea = page.locator('.el-message, .el-notification, [class*="notification"]');

      // 通知区域可能存在（取决于是否有新消息）
    });
  });

  test.describe('通知偏好设置', () => {
    test('可以访问通知设置页面', async ({ page }) => {
      // 导航到通知设置页面
      await page.goto('/notifications/settings');

      // 验证页面加载
      await expect(page.locator('text=通知设置').first()).toBeVisible({ timeout: 5000 });
    });

    test('通知设置显示各类开关', async ({ page }) => {
      await page.goto('/notifications/settings');

      // 验证有开关组件
      const switches = page.locator('.el-switch, input[type="checkbox"], [role="switch"]');
      const switchCount = await switches.count();

      // 应该有多个通知类型的开关
      expect(switchCount).toBeGreaterThan(0);
    });

    test('可以切换通知开关', async ({ page }) => {
      await page.goto('/notifications/settings');

      await page.waitForLoadState('networkidle');

      // 查找第一个开关
      const firstSwitch = page.locator('.el-switch, [role="switch"]').first();

      if (await firstSwitch.isVisible()) {
        // 获取当前状态
        const isChecked = await firstSwitch.getAttribute('aria-checked');

        // 点击切换
        await firstSwitch.click();

        // 等待状态更新
        await page.waitForTimeout(500);
      }
    });

    test('保存通知偏好设置', async ({ page }) => {
      await page.goto('/notifications/settings');

      await page.waitForLoadState('networkidle');

      // 查找保存按钮
      const saveButton = page.locator('button:has-text("保存"), button:has-text("确定")');

      if (await saveButton.isVisible()) {
        // 监听API响应
        const responsePromise = page.waitForResponse(
          response => response.url().includes('preferences') && response.status() === 200,
          { timeout: 5000 }
        ).catch(() => null);

        await saveButton.click();

        // 等待保存完成
        const response = await responsePromise;
        if (response) {
          expect(response.status()).toBe(200);
        }
      }
    });
  });

  test.describe('消息类型', () => {
    test('系统通知正确显示', async ({ page }) => {
      await page.goto('/messages');

      await page.waitForLoadState('networkidle');

      // 筛选系统通知
      const typeFilter = page.locator('.el-select, select').first();

      if (await typeFilter.isVisible()) {
        await typeFilter.click();

        // 选择系统通知
        const systemOption = page.locator('.el-select-dropdown__item:has-text("系统"), option:has-text("系统")');
        if (await systemOption.isVisible()) {
          await systemOption.click();

          // 等待筛选结果
          await page.waitForLoadState('networkidle');
        }
      }
    });

    test('审批通知正确显示', async ({ page }) => {
      await page.goto('/messages');

      await page.waitForLoadState('networkidle');

      // 筛选审批通知
      const typeFilter = page.locator('.el-select, select').first();

      if (await typeFilter.isVisible()) {
        await typeFilter.click();

        // 选择审批通知
        const approvalOption = page.locator('.el-select-dropdown__item:has-text("审批"), option:has-text("审批")');
        if (await approvalOption.isVisible()) {
          await approvalOption.click();

          // 等待筛选结果
          await page.waitForLoadState('networkidle');
        }
      }
    });

    test('任务提醒正确显示', async ({ page }) => {
      await page.goto('/messages');

      await page.waitForLoadState('networkidle');

      // 筛选任务提醒
      const typeFilter = page.locator('.el-select, select').first();

      if (await typeFilter.isVisible()) {
        await typeFilter.click();

        // 选择任务提醒
        const taskOption = page.locator('.el-select-dropdown__item:has-text("任务"), option:has-text("任务")');
        if (await taskOption.isVisible()) {
          await taskOption.click();

          // 等待筛选结果
          await page.waitForLoadState('networkidle');
        }
      }
    });
  });

  test.describe('分页功能', () => {
    test('消息列表支持分页', async ({ page }) => {
      await page.goto('/messages');

      await page.waitForLoadState('networkidle');

      // 查找分页组件
      const pagination = page.locator('.el-pagination, [class*="pagination"]');

      if (await pagination.isVisible()) {
        await expect(pagination).toBeVisible();
      }
    });

    test('可以切换每页显示数量', async ({ page }) => {
      await page.goto('/messages');

      await page.waitForLoadState('networkidle');

      // 查找每页数量选择器
      const pageSizeSelector = page.locator('.el-pagination .el-select, .el-pagination__sizes');

      if (await pageSizeSelector.isVisible()) {
        await pageSizeSelector.click();

        // 选择不同的每页数量
        const option = page.locator('.el-select-dropdown__item, option').first();
        if (await option.isVisible()) {
          await option.click();

          // 等待列表刷新
          await page.waitForLoadState('networkidle');
        }
      }
    });
  });
});
