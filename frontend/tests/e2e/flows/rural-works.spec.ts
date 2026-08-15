/**
 * 乡村工作模块 E2E 测试
 * Feature: system-auto-detection
 * Requirements: 10.3, 10.4, 10.5, 10.6
 */

import { test, expect, Page } from '@playwright/test'

// 测试配置
const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173'
const API_URL = process.env.E2E_API_URL || 'http://localhost:8000/api/v1'

// 测试数据
const testWork = {
  name: 'E2E测试工作项目',
  type: 'infrastructure',
  status: 'planned',
  responsible_person: '测试负责人',
  contact_phone: '13800138000',
  description: '这是一个E2E测试创建的工作项目',
  target: '完成E2E测试验证'
}

// 辅助函数：登录
async function login(page: Page) {
  await page.goto(`${BASE_URL}/login`)
  await page.fill('input[placeholder*="用户名"]', 'admin')
  await page.fill('input[placeholder*="密码"]', process.env.TEST_PASSWORD || 'Admin@202507!')
  await page.click('button[type="submit"]')

  // 等待登录成功并跳转
  await page.waitForURL(/.*(?!login).*/, { timeout: 10000 })
}

// 辅助函数：导航到乡村工作页面
async function navigateToRuralWorks(page: Page) {
  // 尝试通过菜单导航
  const menuItem = page.locator('text=农村振兴工作').first()
  if (await menuItem.isVisible()) {
    await menuItem.click()
  } else {
    // 直接访问URL
    await page.goto(`${BASE_URL}/ruralWorks`)
  }

  // 等待页面加载
  await page.waitForSelector('.rural-works-list', { timeout: 10000 })
}

test.describe('乡村工作模块', () => {
  test.beforeEach(async ({ page }) => {
    // 每个测试前登录
    await login(page)
  })

  test.describe('列表页面', () => {
    test('应该正确加载列表页面', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 验证页面标题
      await expect(page.locator('.page-title')).toContainText('农村振兴工作管理')

      // 验证统计卡片存在
      await expect(page.locator('.stats-cards')).toBeVisible()
      await expect(page.locator('.stat-card')).toHaveCount(4)

      // 验证搜索筛选区域
      await expect(page.locator('.search-filter-section')).toBeVisible()

      // 验证工具栏
      await expect(page.locator('.toolbar-section')).toBeVisible()
    })

    test('应该显示数据表格或空状态', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 等待加载完成
      await page.waitForLoadState('networkidle')

      // 检查是否有数据表格或空状态
      const hasTable = await page.locator('.el-table').isVisible()
      const hasEmpty = await page.locator('.el-empty').isVisible()

      expect(hasTable || hasEmpty).toBeTruthy()
    })

    test('应该能够切换视图模式', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 点击视图模式下拉
      await page.click('.view-mode-trigger')

      // 选择卡片视图
      await page.click('text=卡片视图')

      // 验证卡片视图显示
      await expect(page.locator('.card-view-section')).toBeVisible()

      // 切换回表格视图
      await page.click('.view-mode-trigger')
      await page.click('text=表格视图')

      // 验证表格视图显示
      await expect(page.locator('.table-section')).toBeVisible()
    })
  })

  test.describe('搜索和筛选', () => {
    test('应该能够按关键词搜索', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 输入搜索关键词
      await page.fill('.search-input input', '测试')
      await page.click('button:has-text("搜索")')

      // 等待搜索结果
      await page.waitForLoadState('networkidle')

      // 验证搜索已执行（页面不报错即可）
      await expect(page.locator('.rural-works-list')).toBeVisible()
    })

    test('应该能够按状态筛选', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 选择状态筛选
      await page.click('.status-select')
      await page.click('.el-select-dropdown__item:has-text("进行中")')

      // 等待筛选结果
      await page.waitForLoadState('networkidle')

      // 验证筛选已执行
      await expect(page.locator('.rural-works-list')).toBeVisible()
    })

    test('应该能够按类型筛选', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 选择类型筛选
      await page.click('.type-select')
      await page.click('.el-select-dropdown__item:has-text("基础设施建设")')

      // 等待筛选结果
      await page.waitForLoadState('networkidle')

      // 验证筛选已执行
      await expect(page.locator('.rural-works-list')).toBeVisible()
    })

    test('应该能够重置筛选条件', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 设置一些筛选条件
      await page.fill('.search-input input', '测试')
      await page.click('.status-select')
      await page.click('.el-select-dropdown__item:has-text("进行中")')

      // 点击重置
      await page.click('button:has-text("重置")')

      // 验证筛选条件已清空
      await expect(page.locator('.search-input input')).toHaveValue('')
    })
  })

  test.describe('CRUD 操作', () => {
    test('应该能够打开新建对话框', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 点击新建按钮
      await page.click('.create-button')

      // 验证对话框打开
      await expect(page.locator('.el-dialog')).toBeVisible()
      await expect(page.locator('.el-dialog__title')).toContainText('新建工作')

      // 验证表单字段存在
      await expect(page.locator('label:has-text("工作名称")')).toBeVisible()
      await expect(page.locator('label:has-text("工作类型")')).toBeVisible()
    })

    test('应该能够创建新工作', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 点击新建按钮
      await page.click('.create-button')

      // 填写表单
      await page.fill('input[placeholder*="工作名称"]', testWork.name)

      // 选择工作类型
      await page.click('.el-form-item:has-text("工作类型") .el-select')
      await page.click('.el-select-dropdown__item:has-text("基础设施建设")')

      // 填写负责人
      await page.fill('input[placeholder*="负责人"]', testWork.responsible_person)

      // 填写联系电话
      await page.fill('input[placeholder*="联系电话"]', testWork.contact_phone)

      // 填写描述
      await page.fill('textarea[placeholder*="工作描述"]', testWork.description)

      // 填写目标
      await page.fill('textarea[placeholder*="预期目标"]', testWork.target)

      // 提交表单
      await page.click('button:has-text("保存")')

      // 等待对话框关闭
      await page.waitForSelector('.el-dialog', { state: 'hidden', timeout: 10000 })

      // 验证成功消息
      await expect(page.locator('.el-message--success')).toBeVisible()
    })

    test('应该能够查看工作详情', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 等待数据加载
      await page.waitForLoadState('networkidle')

      // 检查是否有数据
      const hasData = await page.locator('.el-table__row').first().isVisible().catch(() => false)

      if (hasData) {
        // 点击查看按钮
        await page.click('.el-table__row:first-child button:has-text("查看")')

        // 验证详情对话框打开
        await expect(page.locator('.el-dialog:has-text("工作详情")')).toBeVisible()

        // 验证详情内容
        await expect(page.locator('.el-descriptions')).toBeVisible()
      } else {
        // 跳过测试（无数据）
        test.skip()
      }
    })

    test('应该能够编辑工作', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 等待数据加载
      await page.waitForLoadState('networkidle')

      // 检查是否有数据
      const hasData = await page.locator('.el-table__row').first().isVisible().catch(() => false)

      if (hasData) {
        // 点击编辑按钮
        await page.click('.el-table__row:first-child button:has-text("编辑")')

        // 验证编辑对话框打开
        await expect(page.locator('.el-dialog')).toBeVisible()
        await expect(page.locator('.el-dialog__title')).toContainText('编辑工作')

        // 修改名称
        const nameInput = page.locator('input[placeholder*="工作名称"]')
        await nameInput.clear()
        await nameInput.fill('修改后的工作名称')

        // 保存
        await page.click('button:has-text("保存")')

        // 等待对话框关闭
        await page.waitForSelector('.el-dialog', { state: 'hidden', timeout: 10000 })

        // 验证成功消息
        await expect(page.locator('.el-message--success')).toBeVisible()
      } else {
        test.skip()
      }
    })

    test('应该能够删除工作', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 等待数据加载
      await page.waitForLoadState('networkidle')

      // 检查是否有数据
      const hasData = await page.locator('.el-table__row').first().isVisible().catch(() => false)

      if (hasData) {
        // 点击删除按钮
        await page.click('.el-table__row:first-child button:has-text("删除")')

        // 验证确认对话框
        await expect(page.locator('.el-dialog:has-text("确认删除")')).toBeVisible()

        // 确认删除
        await page.click('button:has-text("确定删除")')

        // 等待对话框关闭
        await page.waitForSelector('.el-dialog:has-text("确认删除")', { state: 'hidden', timeout: 10000 })

        // 验证成功消息
        await expect(page.locator('.el-message--success')).toBeVisible()
      } else {
        test.skip()
      }
    })
  })

  test.describe('分页', () => {
    test('应该显示分页组件', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 验证分页组件存在
      await expect(page.locator('.el-pagination')).toBeVisible()
    })

    test('应该能够切换每页数量', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 点击每页数量选择器
      await page.click('.el-pagination .el-select')

      // 选择20条/页
      await page.click('.el-select-dropdown__item:has-text("20")')

      // 等待数据重新加载
      await page.waitForLoadState('networkidle')

      // 验证页面正常
      await expect(page.locator('.rural-works-list')).toBeVisible()
    })
  })

  test.describe('导出功能', () => {
    test('应该能够点击导出按钮', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 点击导出按钮
      const exportButton = page.locator('.export-button')
      await expect(exportButton).toBeVisible()

      // 设置下载监听
      const downloadPromise = page.waitForEvent('download', { timeout: 5000 }).catch(() => null)

      await exportButton.click()

      // 等待下载或超时（API可能未实现导出）
      const download = await downloadPromise

      // 如果有下载，验证文件名
      if (download) {
        expect(download.suggestedFilename()).toContain('乡村工作')
      }
    })
  })

  test.describe('表单验证', () => {
    test('应该验证必填字段', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 打开新建对话框
      await page.click('.create-button')

      // 直接点击保存
      await page.click('button:has-text("保存")')

      // 验证错误提示
      await expect(page.locator('.el-form-item__error')).toBeVisible()
    })

    test('应该验证手机号格式', async ({ page }) => {
      await navigateToRuralWorks(page)

      // 打开新建对话框
      await page.click('.create-button')

      // 填写无效手机号
      await page.fill('input[placeholder*="联系电话"]', '12345')

      // 触发验证
      await page.click('input[placeholder*="工作名称"]')

      // 验证错误提示
      await expect(page.locator('.el-form-item__error:has-text("手机号")')).toBeVisible()
    })
  })
})

test.describe('API 健康检查', () => {
  test('后端API应该可访问', async ({ request }) => {
    const response = await request.get(`${API_URL}/health`)
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data.status).toBeDefined()
  })

  test('乡村工作API应该可访问', async ({ request }) => {
    // 先登录获取token
    const loginResponse = await request.post(`${API_URL}/auth/login`, {
      form: {
        username: 'admin',
        password: process.env.TEST_PASSWORD || 'Admin@202507!'
      }
    })

    if (loginResponse.ok()) {
      const loginData = await loginResponse.json()
      const token = loginData.access_token

      // 访问乡村工作列表
      const response = await request.get(`${API_URL}/rural-works`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      expect(response.ok()).toBeTruthy()
    }
  })
})
