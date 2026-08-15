/**
 * views/dataManagement/Index.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：loadStats 四指标来自真实端点（dashboard/stats + import/history +
 * audit/exports + system/backup，本月过滤）、village 数据质量统计、
 * 失败（logger.error + ElMessage.error）、
 * handleImportComplete/handleExportComplete 两事件、
 * 模板：el-tabs v-model、四个 tab-pane、el-statistic 渲染。
 * 说明：el-tab-pane 使用空 stub，子组件（Import/Export/Backup/Quality Section）不挂载，
 * 避免加载真实 API 模块（各子组件有独立测试文件覆盖）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { ElMessage, mockGet, mockApiRequest, mockRequest } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockGet: vi.fn(),
  mockApiRequest: vi.fn(),
  mockRequest: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/request', () => ({
  default: mockRequest,
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

function currentMonthPrefix(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

/** 按真实端点契约配置 mockGet（列表端点 resolve { items, total }，/dashboard/stats resolve data 负载） */
function setupEndpoints(overrides: Record<string, unknown> = {}) {
  const mp = currentMonthPrefix()
  const defaults: Record<string, unknown> = {
    '/dashboard/stats': { total_villages: 120 },
    '/import/history': {
      items: [
        { id: 1, file_name: 'a.xlsx', createdAt: `${mp}-05T10:00:00` },
        { id: 2, file_name: 'b.xlsx', created_at: `${mp}-20T09:30:00` },
        { id: 3, file_name: 'c.xlsx', createdAt: '2020-01-01T10:00:00' },
      ],
      total: 3,
    },
    '/audit/exports': {
      items: [
        { id: 1, export_type: 'village', created_at: `${mp}-03T10:00:00` },
        { id: 2, export_type: 'fund', created_at: `${mp}-18T10:00:00` },
        { id: 3, export_type: 'school', created_at: '2020-01-05T10:00:00' },
      ],
      total: 3,
    },
    '/system/backup': {
      items: [
        { backup_id: 1, file_name: 'backup_1.db' },
        { backup_id: 2, file_name: 'backup_2.db' },
        { backup_id: 3, file_name: 'backup_3.db' },
      ],
      total: 3,
    },
  }
  const merged = { ...defaults, ...overrides }
  mockGet.mockImplementation((url: string) => Promise.resolve(merged[url]))
}

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
          template:
            '<div class="el-statistic-stub">{{ title }}:{{ value }}{{ suffix }}</div>',
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
  setupEndpoints()
  mockApiRequest.mockResolvedValue({ data: { items: villages } })
})

describe('挂载与统计加载', () => {
  it('onMounted：snake_case 数据 → stats；village 数据计算质量统计', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 四指标端点调用契约（注意 import/history 与 audit/exports 上限 100）
    expect(mockGet).toHaveBeenCalledWith('/dashboard/stats')
    expect(mockGet).toHaveBeenCalledWith('/import/history', { page: 1, page_size: 100 })
    expect(mockGet).toHaveBeenCalledWith('/audit/exports', { page: 1, page_size: 100 })
    expect(mockGet).toHaveBeenCalledWith('/system/backup', { page: 1, page_size: 1000 })
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ url: '/supported-villages', method: 'GET' })
    )
    expect(vm.stats.villageCount).toBe(120)
    expect(vm.stats.monthlyImports).toBe(2)
    expect(vm.stats.monthlyExports).toBe(2)
    expect(vm.stats.backupCount).toBe(3)
    expect(vm.qualityStats.totalRecords).toBe(2)
    expect(vm.qualityStats.validRecords).toBe(1)
    expect(vm.qualityStats.invalidRecords).toBe(1)
    expect(vm.qualityStats.completenessRate).toBe(50)
    expect(vm.qualityStats.lastCheckTime).toBeTruthy()

    const text = wrapper.text()
    expect(text).toContain('帮扶村总数:120')
    expect(text).toContain('本月导入:2次')
    expect(text).toContain('本月导出:2次')
    expect(text).toContain('备份数量:3')
    expect(text).toContain('数据导入')
    expect(text).toContain('数据导出')
    expect(text).toContain('数据备份')
    expect(text).toContain('数据质量')
  })

  it('camelCase villageCount / 子端点空 body / village 数据缺失 items → 兜底', async () => {
    setupEndpoints({
      '/dashboard/stats': { villageCount: 10 },
      '/import/history': {},
      '/audit/exports': {},
      '/system/backup': {},
    })
    mockApiRequest.mockResolvedValue({ data: {} })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.stats.villageCount).toBe(10)
    expect(vm.stats.monthlyImports).toBe(0)
    expect(vm.stats.monthlyExports).toBe(0)
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
  it('导入/导出 complete 事件：刷新统计 + 提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const base = mockGet.mock.calls.length

    vm.handleImportComplete()
    await flushPromises()
    expect(ElMessage.success).toHaveBeenCalledWith('数据导入完成')
    expect(mockGet.mock.calls.length).toBe(base + 4)

    vm.handleExportComplete()
    await flushPromises()
    expect(ElMessage.success).toHaveBeenCalledWith('数据导出完成')
    expect(mockGet.mock.calls.length).toBe(base + 8)
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

/**
 * utils/index.ts 统一导出（与上方 Index.vue 视图测试同名文件共存）
 * 覆盖：logger/request/exportUtil/copyToClipboard 四个 re-export + format 工具集全部分支
 */
import { logger, request, exportUtil, copyToClipboard, format } from '@/utils/index'

describe('utils/index.ts 统一导出', () => {
  describe('format.formatDateTime', () => {
    it('默认 fmt YYYY-MM-DD HH:mm:ss（本地时区）', () => {
      const d = new Date(2024, 0, 5, 9, 8, 7)
      expect(format.formatDateTime(d)).toBe('2024-01-05 09:08:07')
    })

    it('字符串日期 + 自定义 fmt', () => {
      expect(format.formatDateTime('2024-05-01T10:30:00', 'YYYY/MM/DD HH:mm')).toBe(
        '2024/05/01 10:30'
      )
    })

    it('非法日期返回原值', () => {
      expect(format.formatDateTime('not-a-date')).toBe('not-a-date')
      const invalid = new Date('invalid')
      expect(format.formatDateTime(invalid)).toBe(String(invalid))
    })
  })

  describe('format.formatDateTimeLocale', () => {
    it('空值/非法日期返回 -', () => {
      expect(format.formatDateTimeLocale('' as any)).toBe('-')
      expect(format.formatDateTimeLocale(null as any)).toBe('-')
      expect(format.formatDateTimeLocale(undefined as any)).toBe('-')
      expect(format.formatDateTimeLocale('bad-date')).toBe('-')
    })

    it('合法日期按 zh-CN locale 格式化', () => {
      const r = format.formatDateTimeLocale(new Date(2024, 0, 5, 9, 8, 7))
      expect(r.length).toBeGreaterThan(0)
      expect(r).toContain('2024')
    })
  })

  describe('format.formatDate / formatDateTimeFull', () => {
    it('空值返回 -', () => {
      expect(format.formatDate(null as any)).toBe('-')
      expect(format.formatDateTimeFull(null as any)).toBe('-')
    })

    it('日期格式化', () => {
      const d = new Date(2024, 0, 5)
      expect(format.formatDate(d)).toBe('2024-01-05')
      expect(format.formatDateTimeFull(d)).toBe('2024-01-05 00:00:00')
    })
  })

  describe('format.formatCurrency', () => {
    it('千分位 + 默认单位元 + 两位小数', () => {
      expect(format.formatCurrency(1234567.891)).toBe('1,234,567.89元')
    })

    it('自定义单位', () => {
      expect(format.formatCurrency(100, '万元')).toBe('100万元')
    })
  })

  describe('re-exports 断言', () => {
    it('logger 是 logger 实例', () => {
      expect(typeof logger.debug).toBe('function')
      expect(typeof logger.info).toBe('function')
      expect(typeof logger.warn).toBe('function')
      expect(typeof logger.error).toBe('function')
    })

    it('request 是函数（@/api/request 默认导出，测试中为 mock）', () => {
      expect(typeof request).toBe('function')
      request('/system/ping')
      expect(mockRequest).toHaveBeenCalledWith('/system/ping')
    })

    it('exportUtil 提供 CSV/Excel/PDF/escapeCSVField', () => {
      expect(typeof exportUtil.exportToCSV).toBe('function')
      expect(typeof exportUtil.exportToExcel).toBe('function')
      expect(typeof exportUtil.exportToPDF).toBe('function')
      expect(typeof exportUtil.escapeCSVField).toBe('function')
    })

    it('copyToClipboard 导出（空文本直接 false）', async () => {
      expect(typeof copyToClipboard).toBe('function')
      expect(await copyToClipboard('')).toBe(false)
    })
  })
})
