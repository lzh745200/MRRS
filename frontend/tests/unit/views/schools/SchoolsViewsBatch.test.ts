/**
 * Schools Views 批量组件测试
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

enableAutoUnmount(afterEach)

const mockPush = vi.fn(() => Promise.resolve())
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, resolve: vi.fn(() => ({ name: 'x', matched: [{ path: '/x' }] })) }),
  useRoute: () => ({ params: { id: '1' }, query: {}, path: '/schools/1' }),
  onBeforeRouteLeave: vi.fn(),
  RouterLink: { template: '<a><slot/></a>' },
}))
const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDel = vi.fn()
const mockDownloadBlobAsFile = vi.fn(() => Promise.resolve())
// 回收站（schoolsRecycle）与 ElMessageBox 交互：提升为具名 mock 以便断言/覆写返回值
const mockRestoreSchool = vi.fn(() => Promise.resolve({ success: true }))
const mockPreviewPurgeSchool = vi.fn(() => Promise.resolve({ data: { total_references: 2 } }))
const mockPurgeSchool = vi.fn(() => Promise.resolve({ data: { message: '已清理', deleted_records: 3 } }))
const mockConfirm = vi.fn(() => Promise.resolve('confirm'))
const mockPrompt = vi.fn(() => Promise.resolve({ value: 'pwd-123' }))
vi.mock('@/api/helpers/blobDownload', () => ({
  downloadBlobAsFile: (...a: any[]) => mockDownloadBlobAsFile(...a),
  parseFileName: vi.fn(),
  getFileNameFromResponse: vi.fn(),
}))
vi.mock('@/api/request', () => ({
  // schoolsRecycle.ts / List.vue 均 import 默认导出（AGENTS 前端测试约定 #1：
  // mock 必须覆盖源模块 import 的全部具名导出 + default）
  default: { get: (...a: any[]) => mockGet(...a), post: (...a: any[]) => mockPost(...a) },
  get: (...a: any[]) => mockGet(...a),
  post: (...a: any[]) => mockPost(...a),
  put: (...a: any[]) => mockPut(...a),
  del: (...a: any[]) => mockDel(...a),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))
vi.mock('@/api/schoolsRecycle', () => ({
  restoreSchool: (...a: any[]) => mockRestoreSchool(...a),
  previewPurgeSchool: (...a: any[]) => mockPreviewPurgeSchool(...a),
  purgeSchool: (...a: any[]) => mockPurgeSchool(...a),
  request: { get: (...a: any[]) => mockGet(...a) },
}))
vi.mock('@/utils/logger', () => ({ logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() } }))
vi.mock('@/composables/useRouterSafe', () => ({ useRouterSafe: () => ({ push: mockPush, pushSafe: mockPush }), pushSafe: vi.fn(() => Promise.resolve()), safeRouteParam: (v: unknown, fallback = 0) => { const n = Number(Array.isArray(v) ? v[0] : v); return Number.isFinite(n) ? n : fallback } }))
vi.mock('@/utils/notify', () => ({ notify: Object.assign(() => vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn(), closeAll: vi.fn() }), default: vi.fn() }))
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  ElMessageBox: {
    confirm: (...a: any[]) => mockConfirm(...a),
    alert: vi.fn(),
    prompt: (...a: any[]) => mockPrompt(...a),
  },
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn(), closeAll: vi.fn() },
  ElForm: { template: '<form><slot/></form>' },
  ElFormItem: { template: '<div><slot/></div>' },
  ElTable: { template: '<table><slot/></table>' },
  ElTableColumn: { template: '<td><slot/></td>' },
  ElPagination: { template: '<div/>' },
  ElDialog: { template: '<div><slot/></div>' },
  ElSelect: { template: '<select><slot/></select>' },
  ElOption: { template: '<option/>' },
  ElInput: { template: '<input/>' },
  ElButton: { template: '<button><slot/></button>' },
  ElCard: { template: '<div><slot/></div>' },
  ElTag: { template: '<span><slot/></span>' },
  ElTabs: { template: '<div><slot/></div>' },
  ElTabPane: { template: '<div><slot/></div>' },
}))

const schoolData = { items: [{ id: 1, name: '测试小学', level: '小学', student_count: 100, status: 'active' }], total: 1 }

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  mockGet.mockResolvedValue({ ...schoolData, data: schoolData, success: true })
  mockPost.mockResolvedValue({ data: { id: 1 }, success: true })
  mockPut.mockResolvedValue({ data: { id: 1 }, success: true })
  mockDel.mockResolvedValue({ data: null, success: true })
})

describe('schools/Analysis.vue', () => {
  it('渲染', async () => {
    const { default: C } = await import('@/views/schools/Analysis.vue')
    const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true)
  })
})
describe('schools/Detail.vue', () => {
  it('渲染', async () => {
    const { default: C } = await import('@/views/schools/Detail.vue')
    const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true)
  })

  // W10-030：帮扶成效卡数值来自 GET /schools/{id}/statistics（非本地聚合）
  it('帮扶成效卡展示 statistics 接口返回值', async () => {
    const stats = {
      scholarship_count: 7,
      scholarship_total_amount: 1234,
      project_count: 3,
      project_total_budget: 56.5,
    }
    mockGet.mockImplementation((url: string) =>
      String(url).includes('/statistics')
        ? Promise.resolve({ data: stats, success: true })
        : Promise.resolve({ ...schoolData, data: schoolData, success: true }),
    )
    const { default: C } = await import('@/views/schools/Detail.vue')
    const w = mount(C)
    await flushPromises()
    const values = w.findAll('.effect-value').map((n) => n.text())
    expect(values).toEqual(['7', '1234元', '3', '56.5万元'])
    expect(mockGet).toHaveBeenCalledWith('/schools/1/statistics')
    w.unmount()
  })
})
describe('schools/Edit.vue', () => {
  it('渲染', async () => {
    const { default: C } = await import('@/views/schools/Edit.vue')
    const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true)
  })
})
describe('schools/List.vue', () => {
  it('渲染并加载列表', async () => {
    const { default: C } = await import('@/views/schools/List.vue')
    const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true)
    expect(mockGet).toHaveBeenCalled()
  })
  it('新增学校', async () => {
    const { default: C } = await import('@/views/schools/List.vue')
    const w = mount(C); await flushPromises()
    const vm = w.vm as any
    if (vm.handleCreate) vm.handleCreate()
  })

  // W10-030：地区列渲染（优先后端 region，回退分字段拼接，缺省 '-'）
  it('formatRegion 三分支（region / 分字段 / 空值）', async () => {
    const { default: C } = await import('@/views/schools/List.vue')
    const w = mount(C); await flushPromises()
    const vm = w.vm as any
    expect(vm.formatRegion({ region: '贵州省 贵阳市 南明区' })).toBe('贵州省 贵阳市 南明区')
    expect(vm.formatRegion({ province: '贵州省', city: '贵阳市', district: '南明区' })).toBe('贵州省 / 贵阳市 / 南明区')
    expect(vm.formatRegion({})).toBe('-')
    expect(vm.formatRegion(null)).toBe('-')
  })
  it('导出', async () => {
    const { default: C } = await import('@/views/schools/List.vue')
    const w = mount(C); await flushPromises()
    const vm = w.vm as any
    mockDownloadBlobAsFile.mockClear()
    if (vm.handleExport) await vm.handleExport()
    // L3: handleExport 收敛到统一的 downloadBlobAsFile（解析 Content-Disposition 真实文件名）
    expect(mockDownloadBlobAsFile).toHaveBeenCalledTimes(1)
    const [, options] = mockDownloadBlobAsFile.mock.calls[0]
    expect(options).toEqual({ fallbackFileName: 'schools.xlsx' })
    if (vm.handleDownloadTemplate) await vm.handleDownloadTemplate()
  })

  // AGENTS.md 前端 BUG 模式 #3：列表处理器必须在 fetchData 前重置分页
  it('handleRestore 刷新前把 currentPage 重置为 1', async () => {
    const { default: C } = await import('@/views/schools/List.vue')
    const w = mount(C); await flushPromises()
    const vm = w.vm as any
    expect(typeof vm.handleRestore).toBe('function')
    vm.currentPage = 3

    await vm.handleRestore({ id: 7, name: '测试小学' })
    await flushPromises()

    expect(mockRestoreSchool).toHaveBeenCalledWith(7)
    // 恢复会改变结果集长度；停留第 3 页会刷出空页，看似"恢复没生效"
    expect(vm.currentPage).toBe(1)
  })

  it('handlePurge 刷新前把 currentPage 重置为 1', async () => {
    const { default: C } = await import('@/views/schools/List.vue')
    const w = mount(C); await flushPromises()
    const vm = w.vm as any
    expect(typeof vm.handlePurge).toBe('function')
    vm.currentPage = 3

    await vm.handlePurge({ id: 8, name: '测试小学' })
    await flushPromises()

    expect(mockPreviewPurgeSchool).toHaveBeenCalledWith(8)
    expect(mockPurgeSchool).toHaveBeenCalledWith(8, 'pwd-123')
    expect(vm.currentPage).toBe(1)
  })
})
describe('schools/Projects.vue', () => {
  it('渲染', async () => {
    const { default: C } = await import('@/views/schools/Projects.vue')
    const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true)
  })
})
