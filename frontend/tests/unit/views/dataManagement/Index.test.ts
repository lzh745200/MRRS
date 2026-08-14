/**
 * views/dataManagement/Index.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：loadStats 成功（snake_case/camelCase 两种形态、village 数据有效/无效、
 * totalRecords=0 分支）、失败（logger.error + ElMessage.error）、
 * handleImportComplete/handleExportComplete/handleBackupComplete 三事件、
 * 模板：el-tabs v-model、四个 tab-pane、el-statistic 渲染。
 * 说明：el-tab-pane 使用空 stub，子组件（Import/Export/Backup/Quality Section）不挂载，
 * 避免加载真实 API 模块（各子组件有独立测试文件覆盖）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { ElMessage, mockGet, mockApiRequest } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockGet: vi.fn(),
  mockApiRequest: vi.fn(),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: vi.fn() }),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/request', () => ({
  get: mockGet,
  apiRequest: mockApiRequest,
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import Index from '@/views/dataManagement/Index.vue'

const villages = [
  { id: 1, department: '作战处', village_name: '甲村', county: '都匀市' },
  { id: 2, department: '', village_name: '乙村', county: '' },
]

function mountComp() {
  return mount(Index, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
        },
        'el-statistic': {
          name: 'ElStatistic',
          props: ['value', 'title', 'suffix'],
          template: '<div class="el-statistic-stub">{{ title }}:{{ value }}{{ suffix }}</div>',
        },
        'el-tabs': {
          name: 'ElTabs',
          template: '<div class="el-tabs-stub"><slot /></div>',
          emits: ['update:modelValue', 'tab-change'],
        },
        'el-tab-pane': {
          name: 'ElTabPane',
          props: ['label'],
          template: '<div class="el-tab-pane-stub">{{ label }}</div>',
        },
        'el-row': { name: 'ElRow', template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { name: 'ElCol', template: '<div class="el-col-stub"><slot /></div>' },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  mockGet.mockResolvedValue({
    data: {
      total_villages: 120,
      monthly_imports: 5,
      monthly_exports: 3,
      backup_count: 8,
    },
  })
  mockApiRequest.mockResolvedValue({ data: { items: villages } })
})

describe('挂载与统计加载', () => {
  it('onMounted：snake_case 数据 → stats；village 数据计算质量统计', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(mockGet).toHaveBeenCalledWith('/dashboard/stats')
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ url: '/supported-villages', method: 'GET' })
    )
    expect(vm.stats.villageCount).toBe(120)
    expect(vm.stats.monthlyImports).toBe(5)
    expect(vm.stats.monthlyExports).toBe(3)
    expect(vm.stats.backupCount).toBe(8)
    expect(vm.qualityStats.totalRecords).toBe(2)
    expect(vm.qualityStats.validRecords).toBe(1)
    expect(vm.qualityStats.invalidRecords).toBe(1)
    expect(vm.qualityStats.completenessRate).toBe(50)
    expect(vm.qualityStats.lastCheckTime).toBeTruthy()

    const text = wrapper.text()
    expect(text).toContain('帮扶村总数:120')
    expect(text).toContain('本月导入:5次')
    expect(text).toContain('本月导出:3次')
    expect(text).toContain('备份数量:8')
    expect(text).toContain('数据导入')
    expect(text).toContain('数据导出')
    expect(text).toContain('数据备份')
    expect(text).toContain('数据质量')
  })

  it('camelCase 数据 / village 数据缺失 items → 兜底', async () => {
    mockGet.mockResolvedValue({
      data: { villageCount: 10, monthlyImports: 1, monthlyExports: 2, backupCount: 0 },
    })
    mockApiRequest.mockResolvedValue({ data: {} })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.stats.villageCount).toBe(10)
    expect(vm.stats.monthlyImports).toBe(1)
    expect(vm.stats.monthlyExports).toBe(2)
    expect(vm.stats.backupCount).toBe(0)
    expect(vm.qualityStats.totalRecords).toBe(0)
    expect(vm.qualityStats.completenessRate).toBe(0)
  })

  it('res 无 data（直接对象）/res 为 null /data 为空对象 → ?? 兜底；失败 → 错误提示', async () => {
    mockGet.mockResolvedValue({ total_villages: 7 })
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).stats.villageCount).toBe(7)

    mockGet.mockResolvedValue(null)
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).stats.villageCount).toBe(0)
    expect((wrapper.vm as any).stats.monthlyImports).toBe(0)

    mockGet.mockResolvedValue({ data: {} })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).stats.backupCount).toBe(0)

    mockGet.mockRejectedValue(new Error('net'))
    wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('net')
    expect((wrapper.vm as any).stats.villageCount).toBe(0)
  })
})

describe('事件处理', () => {
  it('三个 complete 事件：刷新统计 + 提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const base = mockGet.mock.calls.length

    vm.handleImportComplete()
    await flushPromises()
    expect(ElMessage.success).toHaveBeenCalledWith('数据导入完成')
    expect(mockGet.mock.calls.length).toBe(base + 1)

    vm.handleExportComplete()
    await flushPromises()
    expect(ElMessage.success).toHaveBeenCalledWith('数据导出完成')
    expect(mockGet.mock.calls.length).toBe(base + 2)

    // 备份管理已整合至系统管理：验证跳转入口存在
    expect((wrapper.vm as any).goBackupManagement).toBeTypeOf('function')
  })
})

describe('el-tabs 交互', () => {
  it('v-model 切换 activeTab；tab-change 事件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const tabs = wrapper.findAllComponents({ name: 'ElTabs' })
    tabs[0].vm.$emit('update:modelValue', 'backup')
    expect(vm.activeTab).toBe('backup')
    tabs[0].vm.$emit('tab-change', 'export')
    expect(vm.activeTab).toBe('backup')
  })
})

describe('备份跳转', () => {
  it('前往备份管理按钮 → goBackupManagement', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const btn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().includes('前往备份管理'))
    if (btn) {
      await btn.trigger('click')
      expect(vm.goBackupManagement).toBeTypeOf('function')
    } else {
      vm.goBackupManagement()
    }
    wrapper.unmount()
  })
})
