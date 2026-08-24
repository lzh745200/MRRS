/**
 * views/dataManagement/Index.vue 覆盖率攻坚（四指标 100%）
 *
 * 负载契约（mock 对齐实际契约）：
 *   villageCount   ← get('/dashboard/stats') → data.total_villages（兼容 villageCount）
 *   monthlyImports ← get('/import/history', { page:1, page_size:100 })
 *                    → items 按 createdAt/created_at 的 YYYY-MM 前缀客户端过滤
 *   monthlyExports ← get('/audit/exports', { page:1, page_size:100 })
 *                    → items 同上过滤
 *   backupCount    ← get('/system/backup', { page:1, page_size:1000 }) → items.length
 * 质量统计 ← apiRequest({ method:'GET', url:'/supported-villages', params:{page:1,page_size:200} })
 *            （apiRequest 为 raw axios，取 villageRes.data.items）
 *
 * 约定：命名导出 get/apiRequest 自动解包信封，mock 直接 resolve 解包后的 body：
 *   列表端点 → { items, total }；/dashboard/stats → 数据负载本身（total_villages）。
 * 覆盖：成功（snake/camelCase、防御性解包、本月/跨月过滤、totalRecords=0）、
 *   内部端点失败（单项保持 0 且流程继续）、外层失败（logger.error + ElMessage.error）、
 *   handleImportComplete/handleExportComplete 事件、el-tabs v-model、goBackupManagement 跳转、
 *   模板 el-statistic 渲染。
 * 说明：el-tab-pane 使用空 stub（不渲染默认插槽），子组件（Import/Export/Quality Section）
 *   不挂载，避免加载真实 API 模块（各子组件有独立测试文件覆盖）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { ElMessage, mockGet, mockApiRequest, mockPushSafe, mockLoggerError } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockGet: vi.fn(),
  mockApiRequest: vi.fn(),
  mockPushSafe: vi.fn(),
  mockLoggerError: vi.fn(),
}))

vi.mock('@/utils/logger', () => ({ logger: { error: mockLoggerError } }))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mockPushSafe }),
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

/**
 * 按真实端点契约配置 mockGet：
 * - 列表端点 resolve { items, total }（ok_list() 信封解包后的 body）
 * - /dashboard/stats resolve 数据负载本身（success_response 的 data payload）
 * - rejected 中的 URL 以 Error 拒绝（覆盖内部/外层 catch 分支）
 */
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
        { id: 1, file_name: 'a.xlsx', createdAt: `${monthPrefix}-05T10:00:00` },
        { id: 2, file_name: 'b.xlsx', created_at: `${monthPrefix}-20T09:30:00` },
        { id: 3, file_name: 'c.xlsx', createdAt: '2020-01-01T10:00:00' },
        { id: 4, file_name: 'd.xlsx' }, // 无日期 → createdAt/created_at 均空 → '' 兜底被过滤
      ],
      total: 4,
    },
    '/audit/exports': {
      items: [
        { id: 1, export_type: 'village', created_at: `${monthPrefix}-03T10:00:00` },
        { id: 2, export_type: 'fund', created_at: `${monthPrefix}-18T10:00:00` },
        { id: 3, export_type: 'school', created_at: '2020-01-05T10:00:00' },
        { id: 4, export_type: 'school' }, // 无日期 → '' 兜底被过滤
      ],
      total: 4,
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
  mockGet.mockImplementation((url: string) => {
    if (rejected.includes(url)) return Promise.reject(new Error(`${url} 请求失败`))
    // 注意：不要用 ?? {} 兜底 —— 会把 null/undefined mock 值吞掉，导致
    // 视图的 `res?.data ?? res ?? {}` 兜底分支永远无法覆盖
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
  mockEndpoints()
  mockApiRequest.mockResolvedValue({ data: { items: villages } })
})

describe('挂载与统计加载', () => {
  it('onMounted：真实端点 → 四指标（本月过滤 + 跨月排除）；village 数据计算质量统计', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 端点调用契约
    expect(mockGet).toHaveBeenCalledWith('/dashboard/stats')
    expect(mockGet).toHaveBeenCalledWith('/import/history', { page: 1, page_size: 100 })
    expect(mockGet).toHaveBeenCalledWith('/audit/exports', { page: 1, page_size: 100 })
    expect(mockGet).toHaveBeenCalledWith('/system/backup', { page: 1, page_size: 1000 })
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/supported-villages',
      params: { page: 1, page_size: 200 },
    })

    // 四指标：本月 2 条（createdAt/created_at 两种字段），跨月 1 条被过滤
    expect(vm.stats.villageCount).toBe(120)
    expect(vm.stats.monthlyImports).toBe(2)
    expect(vm.stats.monthlyExports).toBe(2)
    expect(vm.stats.backupCount).toBe(3)

    // 质量统计
    expect(vm.qualityStats.totalRecords).toBe(2)
    expect(vm.qualityStats.validRecords).toBe(1)
    expect(vm.qualityStats.invalidRecords).toBe(1)
    expect(vm.qualityStats.completenessRate).toBe(50)
    expect(vm.qualityStats.lastCheckTime).toBeTruthy()

    // 模板渲染
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

  it('camelCase 数据 / 空 body 兜底 / village 数据缺失 items → 兜底为 0', async () => {
    // 列表端点返回空对象（无 items 键）→ 触发 `||  (Array.isArray(...) ? ... : [])` 防御链
    mockEndpoints({
      '/dashboard/stats': { villageCount: 10, monthlyImports: 1, monthlyExports: 2, backupCount: 0 },
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

  it('防御性解包：dashboard 信封 data 负载 / 列表 data.items / data 数组 / backup total 兜底', async () => {
    const now = new Date()
    const monthPrefix = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
    mockEndpoints({
      '/dashboard/stats': { data: { total_villages: 12 } },
      '/import/history': {
        data: { items: [{ id: 1, file_name: 'x.xlsx', createdAt: `${monthPrefix}-09T10:00:00` }] },
      },
      '/audit/exports': {
        data: [{ id: 1, export_type: 'village', created_at: `${monthPrefix}-09T10:00:00` }],
      },
      // data 为数组 → bk.data.items 缺省，走 Array.isArray(bk?.data) ? bk.data 分支
      '/system/backup': {
        data: [
          { backup_id: 1, file_name: 'backup_1.db' },
          { backup_id: 2, file_name: 'backup_2.db' },
        ],
      },
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.stats.villageCount).toBe(12)
    expect(vm.stats.monthlyImports).toBe(1)
    expect(vm.stats.monthlyExports).toBe(1)
    expect(vm.stats.backupCount).toBe(2)

    // 导入历史 data 为数组（hist.items / hist.data.items 均缺省）→ 走
    // Array.isArray(hist?.data) ? hist.data 真分支
    mockEndpoints({
      '/dashboard/stats': { total_villages: 12 },
      '/import/history': {
        data: [{ id: 1, file_name: 'x.xlsx', createdAt: `${monthPrefix}-09T10:00:00` }],
      },
      '/audit/exports': { data: [] },
      '/system/backup': { data: [] },
    })
    const wrapper2 = mountComp()
    await flushPromises()
    expect((wrapper2.vm as any).stats.villageCount).toBe(12)
    expect((wrapper2.vm as any).stats.monthlyImports).toBe(1)
    expect((wrapper2.vm as any).stats.monthlyExports).toBe(0)
    expect((wrapper2.vm as any).stats.backupCount).toBe(0)
  })

  it('列表 items 为非数组 → 空数组兜底；backup total 兜底分支', async () => {
    // items 为 truthy 非数组 → (Array.isArray(items) ? items : []) 的 [] 兜底分支；
    // backup 无 total → Number(bk?.total ?? 0) || 0 的 ?? 0 / || 0 兜底分支
    mockEndpoints({
      '/dashboard/stats': { total_villages: 120 },
      '/import/history': { items: 'not-an-array' },
      '/audit/exports': { items: 'not-an-array' },
      '/system/backup': { items: 'not-an-array' },
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.stats.villageCount).toBe(120)
    expect(vm.stats.monthlyImports).toBe(0)
    expect(vm.stats.monthlyExports).toBe(0)
    expect(vm.stats.backupCount).toBe(0)
  })

  it('res 无 data（直接对象）/ res 为 null / data 为空对象 → ?? 兜底；外层失败 → 错误提示', async () => {
    mockEndpoints({
      '/dashboard/stats': { total_villages: 7 },
      '/import/history': { items: [] },
      '/audit/exports': { items: [] },
      '/system/backup': { items: [] },
    })
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).stats.villageCount).toBe(7)

    mockEndpoints({
      '/dashboard/stats': null,
      '/import/history': { items: [] },
      '/audit/exports': { items: [] },
      '/system/backup': { items: [] },
    })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).stats.villageCount).toBe(0)
    expect((wrapper.vm as any).stats.monthlyImports).toBe(0)

    mockEndpoints({
      '/dashboard/stats': { data: {} },
      '/import/history': { items: [] },
      '/audit/exports': { items: [] },
      '/system/backup': { items: [] },
    })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).stats.backupCount).toBe(0)

    // 外层 catch：/dashboard/stats 拒绝 → logger.error + ElMessage.error（getErrorMessage 提取 message）
    mockGet.mockRejectedValue(new Error('net'))
    wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('net')
    expect(mockLoggerError).toHaveBeenCalled()
    expect((wrapper.vm as any).stats.villageCount).toBe(0)
    expect((wrapper.vm as any).stats.monthlyImports).toBe(0)
    expect((wrapper.vm as any).stats.monthlyExports).toBe(0)
    expect((wrapper.vm as any).stats.backupCount).toBe(0)
  })
})

describe('内部端点失败（单项保持 0，流程继续）', () => {
  it('/import/history 失败 → monthlyImports 0，其余指标正常，无错误提示', async () => {
    mockEndpoints({}, ['/import/history'])
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.stats.villageCount).toBe(120)
    expect(vm.stats.monthlyImports).toBe(0)
    expect(vm.stats.monthlyExports).toBe(2)
    expect(vm.stats.backupCount).toBe(3)
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('/audit/exports 失败 → monthlyExports 0，其余指标正常', async () => {
    mockEndpoints({}, ['/audit/exports'])
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.stats.villageCount).toBe(120)
    expect(vm.stats.monthlyImports).toBe(2)
    expect(vm.stats.monthlyExports).toBe(0)
    expect(vm.stats.backupCount).toBe(3)
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('/system/backup 失败 → backupCount 0，其余指标正常', async () => {
    mockEndpoints({}, ['/system/backup'])
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.stats.villageCount).toBe(120)
    expect(vm.stats.monthlyImports).toBe(2)
    expect(vm.stats.monthlyExports).toBe(2)
    expect(vm.stats.backupCount).toBe(0)
    expect(ElMessage.error).not.toHaveBeenCalled()
  })
})

describe('事件处理', () => {
  it('W8 瘦身后 import/export complete 由子组件自治，父组件不再暴露处理器', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.handleImportComplete).toBeUndefined()
    expect(vm.handleExportComplete).toBeUndefined()
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
  it('goBackupManagement → pushSafe(\'/system/backup\')', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.goBackupManagement()
    expect(mockPushSafe).toHaveBeenCalledWith('/system/backup')
    wrapper.unmount()
  })
})
