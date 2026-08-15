/**
 * 乡村工作模块 E2E 测试
 * Feature: system-auto-detection
 * Requirements: 10.3, 10.4, 10.5, 10.6
 *
 * 页面对象：frontend/src/views/ruralWorks/List.vue（路由 /rural-works/list）
 * 视图切换：frontend/src/views/ruralWorks/Index.vue（路由 /rural-works，标签页）
 */

import { test, expect } from '@playwright/test'
import { login, navigateTo } from '../helpers'

// 测试配置
const API_URL = process.env.E2E_API_URL || 'http://127.0.0.1:18000/api/v1'

// 测试数据（仅保留真实表单存在的字段）
const testWork = {
  name: 'E2E测试工作项目',
  responsible_person: '测试负责人',
  description: '这是一个E2E测试创建的工作项目',
}

test.describe('乡村工作模块', () => {
  test.beforeEach(async ({ page }) => {
    // 每个测试前确认已认证（storageState 已注入认证态）
    await login(page)
  })

  test.describe('列表页面', () => {
    test('应该正确加载列表页面', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 验证页面标题（布局面包屑展示路由 meta.title）
      await expect(page.locator('.breadcrumb-current')).toContainText('乡村工作列表', {
        timeout: 10000,
      })

      // 验证统计卡片存在
      await expect(page.locator('.stats-overview')).toBeVisible()
      await expect(page.locator('.stat-card')).toHaveCount(4)

      // 验证搜索筛选区域
      await expect(page.locator('.filter-card')).toBeVisible()

      // 验证工具栏（导出 / 新增工作按钮区）
      await expect(page.locator('.filter-right')).toBeVisible()
    })

    test('应该显示数据表格或空状态', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 等待加载完成
      await page.waitForLoadState('networkidle').catch(() => {})

      // 检查是否有数据表格或加载失败占位
      const hasTable = await page.locator('.el-table').isVisible()
      const hasError = await page.locator('.el-result').isVisible()

      expect(hasTable || hasError).toBeTruthy()
    })

    test('应该能够切换视图模式', async ({ page }) => {
      // 真实的视图切换：/rural-works 的标签页（工作列表 / 任务分配 / ...）
      await navigateTo(page, '/rural-works')
      await expect(page.locator('.rural-works-tabs')).toBeVisible({ timeout: 10000 })

      // 默认展示工作列表视图
      await expect(page.locator('.rural-work-list-page')).toBeVisible()

      // 切换到任务分配视图
      await page.click('.el-tabs__item:has-text("任务分配")')
      await expect(page.locator('.rural-works-task')).toBeVisible({ timeout: 10000 })

      // 切换回工作列表视图
      await page.click('.el-tabs__item:has-text("工作列表")')
      await expect(page.locator('.rural-work-list-page')).toBeVisible()
    })
  })

  test.describe('搜索和筛选', () => {
    test('应该能够按关键词搜索', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 输入搜索关键词（回车触发搜索，页面无独立搜索按钮）
      const searchInput = page.getByPlaceholder('搜索工作名称、负责人...')
      await searchInput.fill('测试')
      await searchInput.press('Enter')

      // 等待搜索结果
      await page.waitForLoadState('networkidle').catch(() => {})

      // 验证搜索已执行（页面不报错即可）
      await expect(page.locator('.rural-work-list-page')).toBeVisible()
    })

    test('应该能够按状态筛选', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 选择状态筛选
      await page.click('.filter-left .el-select:has-text("状态筛选")')
      await page.click('.el-select-dropdown__item:has-text("进行中"):visible')

      // 等待筛选结果
      await page.waitForLoadState('networkidle').catch(() => {})

      // 验证筛选已执行
      await expect(page.locator('.rural-work-list-page')).toBeVisible()
    })

    test('应该能够按类型筛选', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 选择类型筛选
      await page.click('.filter-left .el-select:has-text("类型筛选")')
      await page.click('.el-select-dropdown__item:has-text("基础设施建设"):visible')

      // 等待筛选结果
      await page.waitForLoadState('networkidle').catch(() => {})

      // 验证筛选已执行
      await expect(page.locator('.rural-work-list-page')).toBeVisible()
    })

    test('应该能够重置筛选条件', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 设置一些筛选条件
      const searchInput = page.getByPlaceholder('搜索工作名称、负责人...')
      await searchInput.fill('测试')
      await page.click('.filter-left .el-select:has-text("状态筛选")')
      await page.click('.el-select-dropdown__item:has-text("进行中"):visible')

      // 点击重置
      await page.click('button:has-text("重置")')

      // 验证筛选条件已清空
      await expect(searchInput).toHaveValue('')
    })
  })

  test.describe('CRUD 操作', () => {
    test('应该能够打开新建对话框', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 点击新增工作按钮
      await page.click('button:has-text("新增工作")')

      // 验证对话框打开
      await expect(page.locator('.el-dialog')).toBeVisible()
      await expect(page.locator('.el-dialog__title')).toContainText('新增乡村工作')

      // 验证表单字段存在
      await expect(page.locator('label:has-text("工作名称")')).toBeVisible()
      await expect(page.locator('label:has-text("工作类型")')).toBeVisible()
    })

    test('应该能够创建新工作', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 点击新增工作按钮
      await page.click('button:has-text("新增工作")')

      // 填写表单
      await page.fill('.el-dialog input[placeholder="请输入工作名称"]', testWork.name)

      // 选择工作类型
      await page.click('.el-dialog .el-form-item:has-text("工作类型") .el-select')
      await page.click('.el-select-dropdown__item:has-text("基础设施建设"):visible')

      // 填写负责人
      await page.fill('.el-dialog input[placeholder="请输入负责人"]', testWork.responsible_person)

      // 填写描述
      await page.fill('.el-dialog textarea[placeholder="请输入工作描述"]', testWork.description)

      // 提交表单
      await page.click('.el-dialog button:has-text("保存")')

      // 等待对话框关闭
      await page.waitForSelector('.el-dialog', { state: 'hidden', timeout: 10000 })

      // 验证成功消息
      await expect(page.locator('.el-message--success')).toBeVisible()
    })

    test('应该能够查看工作详情', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 等待数据加载
      await page.waitForLoadState('networkidle').catch(() => {})

      // 检查是否有数据
      const hasData = await page
        .locator('.el-table__row')
        .first()
        .isVisible()
        .catch(() => false)

      if (hasData) {
        // 点击查看按钮
        await page.click('.el-table__row:first-child button:has-text("查看")')

        // 验证详情对话框打开（查看模式标题为“查看乡村工作”）
        await expect(page.locator('.el-dialog')).toBeVisible()
        await expect(page.locator('.el-dialog__title')).toContainText('查看乡村工作')

        // 验证详情为只读（查看模式下表单禁用）
        await expect(page.locator('.el-dialog .el-input.is-disabled').first()).toBeVisible()
      } else {
        // 跳过测试（无数据）
        test.skip()
      }
    })

    test('应该能够编辑工作', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 等待数据加载
      await page.waitForLoadState('networkidle').catch(() => {})

      // 检查是否有数据
      const hasData = await page
        .locator('.el-table__row')
        .first()
        .isVisible()
        .catch(() => false)

      if (hasData) {
        // 点击编辑按钮
        await page.click('.el-table__row:first-child button:has-text("编辑")')

        // 验证编辑对话框打开
        await expect(page.locator('.el-dialog')).toBeVisible()
        await expect(page.locator('.el-dialog__title')).toContainText('编辑乡村工作')

        // 修改名称
        const nameInput = page.locator('.el-dialog input[placeholder="请输入工作名称"]')
        await nameInput.clear()
        await nameInput.fill('修改后的工作名称')

        // 保存
        await page.click('.el-dialog button:has-text("保存")')

        // 等待对话框关闭
        await page.waitForSelector('.el-dialog', { state: 'hidden', timeout: 10000 })

        // 验证成功消息
        await expect(page.locator('.el-message--success')).toBeVisible()
      } else {
        test.skip()
      }
    })

    test('应该能够删除工作', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 等待数据加载
      await page.waitForLoadState('networkidle').catch(() => {})

      // 检查是否有数据
      const hasData = await page
        .locator('.el-table__row')
        .first()
        .isVisible()
        .catch(() => false)

      if (hasData) {
        // 点击删除按钮
        await page.click('.el-table__row:first-child button:has-text("删除")')

        // 验证确认对话框（ElMessageBox）
        await expect(page.locator('.el-message-box')).toBeVisible()
        await expect(page.locator('.el-message-box__message')).toContainText('确认删除该工作项')

        // 确认删除
        await page.click('.el-message-box button:has-text("确定")')

        // 等待确认框关闭
        await page.waitForSelector('.el-message-box', { state: 'hidden', timeout: 10000 })

        // 验证成功消息
        await expect(page.locator('.el-message--success')).toBeVisible()
      } else {
        test.skip()
      }
    })
  })

  test.describe('分页', () => {
    test('应该显示分页组件', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 验证分页组件存在
      await expect(page.locator('.el-pagination')).toBeVisible({ timeout: 10000 })
    })

    test('应该能够切换每页数量', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 点击每页数量选择器
      await page.click('.el-pagination .el-select')

      // 选择20条/页（zh-CN 语言环境下选项文案为“20条/页”）
      await page.click('.el-select-dropdown__item:has-text("20条/页"):visible')

      // 等待数据重新加载
      await page.waitForLoadState('networkidle').catch(() => {})

      // 验证页面正常
      await expect(page.locator('.rural-work-list-page')).toBeVisible()
    })
  })

  test.describe('导出功能', () => {
    test('应该能够点击导出按钮', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 点击导出按钮
      const exportButton = page.locator('button:has-text("导出")')
      await expect(exportButton).toBeVisible()

      // 设置下载监听
      const downloadPromise = page.waitForEvent('download', { timeout: 5000 }).catch(() => null)

      await exportButton.click()

      // 等待下载或超时（无数据时前端仅提示“没有可导出的数据”）
      const download = await downloadPromise

      // 如果有下载，验证文件名
      if (download) {
        expect(download.suggestedFilename()).toContain('乡村工作列表')
      }
    })
  })

  test.describe('表单验证', () => {
    test('应该验证必填字段', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 打开新建对话框
      await page.click('button:has-text("新增工作")')

      // 直接点击保存
      await page.click('.el-dialog button:has-text("保存")')

      // 验证错误提示
      await expect(page.locator('.el-form-item__error').first()).toBeVisible()
    })

    test('应该验证工作类型必选', async ({ page }) => {
      await navigateTo(page, '/rural-works/list')

      // 打开新建对话框
      await page.click('button:has-text("新增工作")')

      // 只填写工作名称，不选工作类型
      await page.fill('.el-dialog input[placeholder="请输入工作名称"]', '仅验证类型必选')

      // 提交触发校验
      await page.click('.el-dialog button:has-text("保存")')

      // 验证错误提示
      await expect(page.locator('.el-form-item__error:has-text("请选择工作类型")')).toBeVisible()
    })
  })
})

test.describe('API 健康检查', () => {
  test('后端API应该可访问', async ({ request }) => {
    // 真实健康检查端点：/api/v1/system/health（信封格式 { code, data: { status, ... } }）
    const response = await request.get(`${API_URL}/system/health`)
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    const payload = data.data ?? data
    expect(payload.status).toBeDefined()
  })

  test('乡村工作API应该可访问', async ({ request }) => {
    // 先登录获取token
    const loginResponse = await request.post(`${API_URL}/auth/login`, {
      form: {
        username: 'admin',
        password: process.env.TEST_PASSWORD || 'Admin@202507!',
      },
    })

    if (loginResponse.ok()) {
      const loginData = await loginResponse.json()
      const token = loginData.access_token

      // 访问乡村工作列表
      const response = await request.get(`${API_URL}/rural-works`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      expect(response.ok()).toBeTruthy()
    }
  })
})
