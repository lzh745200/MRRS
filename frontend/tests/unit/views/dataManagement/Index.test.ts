/**
 * views/dataManagement/Index.vue 覆盖率（四指标 100%）
 *
 * 页面定位：菜单「数据概览」的真实落地页（/data-management）。
 * 本轮重新设计：删除「数据导入/数据导出/数据备份」三个只会跳转的「前往…」空壳页签，
 * 改为直接呈现四类真实信息 —— 核心指标、最近导入记录、最近导出记录（仅管理员）、数据质量。
 *
 * 负载契约（mock 对齐实际契约）：
 *   villageCount   ← get('/dashboard/stats') → total_villages（兼容 villageCount）
 *   monthlyImports ← get('/import/history', { page:1, page_size:100 }) → items 按本月前缀过滤
 *   monthlyExports ← get('/system/audit/exports', { page:1, page_size:100 }) → 同上（仅管理员请求）
 *   backupCount    ← get('/system/backup', { page:1, page_size:1000 }) → total
 *   质量统计 ← apiRequest({ method:'GET', url:'/supported-villages', params:{page:1,page_size:200} })
 *
 * 约定：命名导出 get/apiRequest 自动解包信封，mock 直接 resolve 解包后的 body：
 *   列表端点 → { items, total }；/dashboard/stats → 数据负载本身。
 *
 * 覆盖：管理员/非管理员两套渲染、四指标与最近记录、空态、内部端点失败（单项归零不打断）、
 *   外层失败（logger + 错误提示）、刷新按钮、全部格式化函数分支（实体/导出类型/状态文案与标签色/时间）。
 *
 * 说明：QualitySection 用 vi.mock 替换为同步桩 —— 该组件有独立测试文件覆盖，
 *   同一 .vue 被两个测试文件真实执行会在全量覆盖率按 id 合并 fnMap 时互相污染。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { ElMessage, mockGet, mockApiRequest, mockLoggerError, mockIsAdmin } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockGet: vi.fn(),
  mockApiRequest: vi.fn(),
  mockLoggerError: vi.fn(),
  mockIsAdmin: vi.fn(() => true),
}))

vi.mock('@/utils/logger', () => ({ logger: { error: mockLoggerError } }))
vi.mock('@/utils/roleAccess', () => ({ isAdminUser: mockIsAdmin }))
vi.mock('element-plus', () => ({ ElMessage }))
vi.mock('@/api/request', () => ({
  get: mockGet,
  apiRequest: mockApiRequest,
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))
// 子组件桩：避免同一 .vue 被第二个测试文件执行。
// __esModule 让 defineAsyncComponent 正确解包 default（否则模块命名空间对象会被
// 当成组件类型，VTU 探测 __isTeleport 时命中 mock 代理并抛未处理异常）。
vi.mock('@/views/dataManagement/components/QualitySection.vue', () => ({
  __esModule: true,
  default: { name: 'QualitySection', props: ['stats'], template: '<div class="quality-stub" />' },
}))

import Index from '@/views/dataManagement/Index.vue'

const villages = [
  { id: 1, department: '作战处', village_name: '甲村', county: '都匀市' },
  { id: 2, department: '', village_name: '乙村', county: '' },
]

/** 按真实端点契约配置 mockGet；rejected 中的 URL 以 Error 拒绝 */
function mockEndpoints(
  overrides: Record<string, unknown> = {},
  rejected: string[] = []
): { monthPrefix: string } {
  const now = new Date()
  const monthPrefix = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  const defaults: Record<string, unknown> = {
    '/dashboard/stats': { total_villages: 120 },
    '/import/history': {
      items: [
        {
          id: 1,
          file_name: 'a.xlsx',
          entity_type: 'village',
          success_rows: 10,
          total_rows: 12,
          status: 'success',
          created_at: `${monthPrefix}-05T10:00:00`,
        },
        {
          id: 2,
          entity_type: undefined,
          success_rows: null,
          total_rows: null,
          status: 'completed',
          createdAt: `${monthPrefix}-20T09:30:00`,
        },
        {
          id: 3,
          file_name: 'c.xlsx',
          entity_type: 'unknown_type',
          success_rows: 0,
          total_rows: 0,
          status: 'failed',
          created_at: '2020-01-01T10:00:00',
        },
        { id: 4, file_name: 'd.xlsx', status: 'partial', created_at: 'not-a-date' },
        { id: 5, file_name: 'e.xlsx', status: 'pending' },
        { id: 6, file_name: 'f.xlsx', status: 'processing' }, // 第 6 条不展示（只取前 5）
      ],
      total: 6,
    },
    '/system/audit/exports': {
      items: [
        {
          id: 1,
          export_type: 'village',
          record_count: 100,
          file_format: 'xlsx',
          status: 'success',
          created_at: `${monthPrefix}-03T10:00:00`,
        },
        {
          id: 2,
          export_type: undefined,
          record_count: null,
          file_format: '',
          status: 'running',
          created_at: `${monthPrefix}-18T10:00:00`,
        },
        {
          id: 3,
          export_type: 'unknown',
          record_count: 0,
          file_format: null,
          status: 'processing',
          created_at: '2020-01-05T10:00:00',
        },
        { id: 4, export_type: 'fund', status: 'weird', created_at: 'not-a-date' },
        { id: 5, export_type: 'school', status: 'failed' },
        { id: 6, export_type: 'project', status: 'success' },
      ],
      total: 6,
    },
    '/system/backup': {
      items: [{ backup_id: 1 }, { backup_id: 2 }, { backup_id: 3 }],
      total: 3,
    },
  }
  const merged = { ...defaults, ...overrides }
  mockGet.mockImplementation((url: string) => {
    if (rejected.includes(url)) return Promise.reject(new Error(`${url} 请求失败`))
    return Promise.resolve(merged[url])
  })
  return { monthPrefix }
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
          template: '<div class="el-statistic-stub">{{ title }}:{{ value }}{{ suffix }}</div>',
        },
        'el-row': { name: 'ElRow', template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': {
          name: 'ElCol',
          props: ['span'],
          template: '<div class="el-col-stub" :data-span="span"><slot /></div>',
        },
        'el-tag': {
          name: 'ElTag',
          props: ['type'],
          template: '<span class="el-tag-stub" :data-type="type"><slot /></span>',
        },
        'el-empty': {
          name: 'ElEmpty',
          props: ['description'],
          template: '<div class="el-empty-stub" :data-description="description" />',
        },
        'el-button': {
          name: 'ElButton',
          emits: ['click'],
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  mockIsAdmin.mockReturnValue(true)
  mockEndpoints()
  mockApiRequest.mockResolvedValue({ data: { items: villages } })
})

describe('管理员视图：指标 + 最近流转 + 数据质量', () => {
  it('拉取四类数据，渲染四张指标卡与最近导入/导出记录', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(mockGet).toHaveBeenCalledWith('/dashboard/stats')
    expect(mockGet).toHaveBeenCalledWith('/import/history', { page: 1, page_size: 100 })
    expect(mockGet).toHaveBeenCalledWith('/system/audit/exports', { page: 1, page_size: 100 })
    expect(mockGet).toHaveBeenCalledWith('/system/backup', { page: 1, page_size: 1000 })
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/supported-villages',
      params: { page: 1, page_size: 200 },
    })

    // 指标：本月导入/导出各 2 条（snake/camelCase 两种时间字段均可识别）
    expect(vm.stats).toEqual({
      villageCount: 120,
      monthlyImports: 2,
      monthlyExports: 2,
      backupCount: 3,
    })
    // 最近记录只取前 5 条
    expect(vm.recentImports).toHaveLength(5)
    expect(vm.recentExports).toHaveLength(5)

    // 质量统计
    expect(vm.qualityStats.totalRecords).toBe(2)
    expect(vm.qualityStats.validRecords).toBe(1)
    expect(vm.qualityStats.invalidRecords).toBe(1)
    expect(vm.qualityStats.completenessRate).toBe(50)
    expect(vm.qualityStats.lastCheckTime).toBeTruthy()

    const text = wrapper.text()
    expect(text).toContain('数据概览')
    expect(text).toContain('帮扶村总数:120')
    expect(text).toContain('本月导入:2次')
    expect(text).toContain('本月导出:2次')
    expect(text).toContain('备份数量:3')
    expect(text).toContain('最近导入')
    expect(text).toContain('最近导出')
    // 重新设计后不得再出现只会跳转的「前往…」提示
    expect(text).not.toContain('前往')
    expect(wrapper.findAll('.el-statistic-stub')).toHaveLength(4)
    expect(vm.loading).toBe(false)
    wrapper.unmount()
  })

  it('最近导入/导出逐行格式化：空文件名占位、记录数兜底、状态文案与标签色、时间兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 文件名：有值原样；缺省用占位符
    expect(vm.recentImports[0].file_name).toBe('a.xlsx')
    expect(vm.recentImports[1].file_name).toBeUndefined()

    // 实体/导出类型：已知映射、未知原样、缺省占位
    expect(vm.entityText('village')).toBe('帮扶村')
    expect(vm.entityText('unknown_type')).toBe('unknown_type')
    expect(vm.entityText(undefined)).toBe('—')
    expect(vm.exportTypeText('fund')).toBe('经费')
    expect(vm.exportTypeText('unknown')).toBe('unknown')
    expect(vm.exportTypeText(undefined)).toBe('综合')

    // 状态文案：已知、未知原样、缺省
    expect(vm.statusText('success')).toBe('成功')
    expect(vm.statusText('weird')).toBe('weird')
    expect(vm.statusText(undefined)).toBe('未知')

    // 标签色：成功/失败/处理中/未知四条分支
    expect(vm.statusTag('success')).toBe('success')
    expect(vm.statusTag('completed')).toBe('success')
    expect(vm.statusTag('failed')).toBe('danger')
    expect(vm.statusTag('partial')).toBe('warning')
    expect(vm.statusTag('pending')).toBe('warning')
    expect(vm.statusTag('running')).toBe('warning')
    expect(vm.statusTag('processing')).toBe('warning')
    expect(vm.statusTag(undefined)).toBe('info')

    // 时间展示统一走 @/utils/datetime（空值/非法值落占位符，不出现 Invalid Date）
    expect(vm.formatTime).toBeUndefined()
    // 仅带 createdAt（camelCase）的记录同样能渲染出时间，而不是占位符
    const secondImportTimeCell = wrapper
      .findAll('table')[0]
      .findAll('tbody tr')[1]
      .findAll('td')[4]
      .text()
    expect(secondImportTimeCell).not.toBe('—')
    expect(secondImportTimeCell).toContain(String(new Date().getFullYear()))

    // 模板中的兜底表达式（缺省字段渲染为 0 / —）
    const text = wrapper.text()
    expect(text).toContain('—')
    expect(text).toContain('0/0')
    expect(text).toContain('100')
    wrapper.unmount()
  })
})

describe('非管理员视图', () => {
  it('不请求导出审计，隐藏导出指标与最近导出区块，三张卡等宽', async () => {
    mockIsAdmin.mockReturnValue(false)
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(mockGet).not.toHaveBeenCalledWith('/system/audit/exports', expect.anything())
    expect(vm.isAdmin).toBe(false)
    expect(vm.kpiSpan).toBe(8)
    expect(vm.stats.monthlyExports).toBe(0)
    expect(vm.recentExports).toEqual([])
    expect(wrapper.findAll('.el-statistic-stub')).toHaveLength(3)
    expect(wrapper.text()).not.toContain('最近导出')
    // 导出区块不渲染 → 不出现「暂无导出记录」空态
    expect(wrapper.find('[data-description="暂无导出记录"]').exists()).toBe(false)
    wrapper.unmount()
  })
})

describe('空数据与防御性解包', () => {
  it('camelCase / 空 body / 缺 items → 全部归零且空态可读', async () => {
    mockEndpoints({
      '/dashboard/stats': { villageCount: 10 },
      '/import/history': {},
      '/system/audit/exports': {},
      '/system/backup': {},
    })
    mockApiRequest.mockResolvedValue({ data: {} })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.stats).toEqual({
      villageCount: 10,
      monthlyImports: 0,
      monthlyExports: 0,
      backupCount: 0,
    })
    expect(vm.qualityStats.totalRecords).toBe(0)
    expect(vm.qualityStats.completenessRate).toBe(0)
    expect(wrapper.find('[data-description="暂无导入记录"]').exists()).toBe(true)
    expect(wrapper.find('[data-description="暂无导出记录"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('信封 data 负载 / data.items / data 数组 / total 兜底均可解析', async () => {
    const now = new Date()
    const monthPrefix = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
    mockEndpoints({
      '/dashboard/stats': { data: { total_villages: 12 } },
      '/import/history': {
        data: {
          items: [{ id: 1, file_name: 'x.xlsx', createdAt: `${monthPrefix}-09T10:00:00` }],
        },
      },
      '/system/audit/exports': {
        data: [{ id: 1, export_type: 'village', created_at: `${monthPrefix}-09T10:00:00` }],
      },
      '/system/backup': { data: [{ backup_id: 1 }, { backup_id: 2 }] },
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.stats.villageCount).toBe(12)
    expect(vm.stats.monthlyImports).toBe(1)
    expect(vm.stats.monthlyExports).toBe(1)
    expect(vm.stats.backupCount).toBe(2)
    wrapper.unmount()
  })

  it('dashboard 返回 null / data 为空对象 → 指标为 0', async () => {
    mockEndpoints({
      '/dashboard/stats': null,
      '/import/history': { items: [] },
      '/system/audit/exports': { items: [] },
      '/system/backup': { items: [] },
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).stats.villageCount).toBe(0)

    mockEndpoints({
      '/dashboard/stats': { data: {} },
      '/import/history': { items: [] },
      '/system/audit/exports': { items: [] },
      '/system/backup': { items: [] },
    })
    const wrapper2 = mountComp()
    await flushPromises()
    expect((wrapper2.vm as any).stats.backupCount).toBe(0)
    wrapper.unmount()
    wrapper2.unmount()
  })
})

describe('内部端点失败（单项归零，流程继续）', () => {
  it('/import/history 失败 → 导入指标 0、最近导入为空，其余正常且无错误提示', async () => {
    mockEndpoints({}, ['/import/history'])
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.stats.villageCount).toBe(120)
    expect(vm.stats.monthlyImports).toBe(0)
    expect(vm.stats.monthlyExports).toBe(2)
    expect(vm.stats.backupCount).toBe(3)
    expect(vm.recentImports).toEqual([])
    expect(ElMessage.error).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('/system/audit/exports 失败 → 导出指标 0、最近导出为空，其余正常', async () => {
    mockEndpoints({}, ['/system/audit/exports'])
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.stats.monthlyImports).toBe(2)
    expect(vm.stats.monthlyExports).toBe(0)
    expect(vm.recentExports).toEqual([])
    expect(vm.stats.backupCount).toBe(3)
    expect(ElMessage.error).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('/system/backup 失败 → 备份指标 0，其余正常', async () => {
    mockEndpoints({}, ['/system/backup'])
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.stats.villageCount).toBe(120)
    expect(vm.stats.backupCount).toBe(0)
    expect(vm.stats.monthlyImports).toBe(2)
    expect(ElMessage.error).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})

describe('外层失败与刷新', () => {
  it('/dashboard/stats 拒绝 → 记录日志并提示，指标保持 0', async () => {
    mockGet.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(mockLoggerError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('net')
    expect(vm.stats.villageCount).toBe(0)
    expect(vm.loading).toBe(false)
    wrapper.unmount()
  })

  it('点击刷新按钮重新拉取全部数据', async () => {
    const wrapper = mountComp()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledTimes(4)

    await wrapper.find('[data-test="refresh-overview"]').trigger('click')
    await flushPromises()

    expect(mockGet).toHaveBeenCalledTimes(8)
    expect(mockGet).toHaveBeenCalledWith('/dashboard/stats')
    wrapper.unmount()
  })
})
