/**
 * Projects + Organization + Policies + Other Views 批量组件测试
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// 自动卸载组件，防止 HomeSafe.vue 等组件的 setInterval 在测试结束后继续运行导致未捕获的 Promise 拒绝
enableAutoUnmount(afterEach)

const mockPush = vi.fn(() => Promise.resolve())
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, resolve: vi.fn(() => ({ name: 'x', matched: [{ path: '/x' }] })) }),
  useRoute: () => ({ params: { id: '1' }, query: {}, path: '/projects/1' }),
  onBeforeRouteLeave: vi.fn(),
  RouterLink: { template: '<a><slot/></a>' },
}))
const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDel = vi.fn()
const mockApiRequest = vi.fn()
const mockPatch = vi.fn()
vi.mock('@/api/request', () => ({
  get: (...a: any[]) => mockGet(...a),
  post: (...a: any[]) => mockPost(...a),
  put: (...a: any[]) => mockPut(...a),
  del: (...a: any[]) => mockDel(...a),
  patch: (...a: any[]) => mockPatch(...a),
  apiRequest: (...a: any[]) => mockApiRequest(...a),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))
vi.mock('@/utils/logger', () => ({ logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() } }))
vi.mock('@/composables/useRouterSafe', () => ({ useRouterSafe: () => ({ push: mockPush, pushSafe: mockPush }), pushSafe: vi.fn(() => Promise.resolve()), safeRouteParam: (v: unknown, fallback = 0) => { const n = Number(Array.isArray(v) ? v[0] : v); return Number.isFinite(n) ? n : fallback } }))
vi.mock('@/utils/notify', () => ({ notify: Object.assign(() => vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn(), closeAll: vi.fn() }), default: vi.fn() }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 1, username: 'admin', role: 'admin' }, token: 'fake-token', isAdmin: true, logout: vi.fn() }) }))
vi.mock('@/stores/menu', () => ({ useMenuStore: () => ({ menuItems: [], filteredMenus: [], generateMenus: vi.fn(), fetchMenus: vi.fn(), loaded: true, canAccessMenu: () => true }) }))
vi.mock('@/composables/useOnboarding', () => ({ useOnboarding: () => ({ startTour: vi.fn() }) }))
vi.mock('@/utils/enhancedStorage', () => ({ enhancedStorage: { get: vi.fn(() => null), set: vi.fn(), remove: vi.fn() }, STORAGE_KEYS: { DASHBOARD_LAYOUT: 'dashboard_layout', DASHBOARD_ORDER: 'dashboard_order' } }))
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  ElMessageBox: { confirm: vi.fn(() => Promise.resolve('confirm')), alert: vi.fn(), prompt: vi.fn() },
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
  ElCollapse: { template: '<div><slot/></div>' },
  ElCollapseItem: { template: '<div><slot/></div>' },
  ElIcon: { template: '<span><slot/></span>' },
  ElRow: { template: '<div><slot/></div>' },
  ElCol: { template: '<div><slot/></div>' },
  ElTooltip: { template: '<span><slot/></span>' },
  ElDropdown: { template: '<div><slot/></div>' },
  ElDropdownItem: { template: '<div><slot/></div>' },
  ElDropdownMenu: { template: '<div><slot/></div>' },
  ElSwitch: { template: '<div/>' },
  ElDatePicker: { template: '<input/>' },
  ElCheckbox: { template: '<input type="checkbox"/>' },
  ElCheckboxGroup: { template: '<div><slot/></div>' },
  ElRadio: { template: '<input type="radio"/>' },
  ElRadioGroup: { template: '<div><slot/></div>' },
  ElUpload: { template: '<div><slot/></div>' },
  ElProgress: { template: '<div/>' },
  ElDescriptions: { template: '<div><slot/></div>' },
  ElDescriptionsItem: { template: '<div><slot/></div>' },
  ElEmpty: { template: '<div/>' },
  ElImage: { template: '<img/>' },
  ElLink: { template: '<a><slot/></a>' },
  ElSkeleton: { template: '<div><slot/></div>' },
  ElTree: { template: '<div><slot/></div>' },
  ElSteps: { template: '<div><slot/></div>' },
  ElStep: { template: '<div/>' },
  ElBadge: { template: '<span><slot/></span>' },
  ElAvatar: { template: '<div/>' },
  ElDivider: { template: '<hr/>' },
  ElPopover: { template: '<div><slot/></div>' },
}))

const listData = { items: [{ id: 1, name: '测试项' }], total: 1 }
const detailData = { id: 1, name: '测试详情' }

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/detail') || url.match(/\/\d+\/?$/)) return Promise.resolve({ ...detailData, data: detailData, success: true })
    return Promise.resolve({ ...listData, data: listData, success: true })
  })
  mockPost.mockResolvedValue({ data: { id: 1 }, success: true })
  mockPut.mockResolvedValue({ data: { id: 1 }, success: true })
  mockDel.mockResolvedValue({ data: null, success: true })
  mockPatch.mockResolvedValue({ data: null, success: true })
  // apiRequest 用于 HomeSafe.vue 的 Promise.allSettled 调用，必须返回带 .data 的对象
  mockApiRequest.mockImplementation((config: any) => {
    const url = config?.url || ''
    if (url.includes('/dashboard/stats')) return Promise.resolve({ data: { total_villages: 1, total_funds: 1, total_projects: 1, total_schools: 1 }, success: true })
    if (url.includes('/projects')) return Promise.resolve({ data: { items: [], total: 0 }, success: true })
    if (url.includes('/dashboard/recent-activities')) return Promise.resolve({ data: { items: [], total: 0 }, success: true })
    if (url.includes('/messages')) return Promise.resolve({ data: { items: [], total: 0 }, success: true })
    return Promise.resolve({ data: {}, success: true })
  })
})

// --- Projects ---
describe('projects/Detail.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/projects/Detail.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('projects/Edit.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/projects/Edit.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('projects/Import.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/projects/Import.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('projects/List.vue', () => {
  it('渲染并加载', async () => { const { default: C } = await import('@/views/projects/List.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true); expect(mockGet).toHaveBeenCalled() })
})
describe('projects/ProgressGallery.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/projects/ProgressGallery.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('organization/Detail.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/organization/Detail.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('organization/Edit.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/organization/Edit.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('organization/List.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/organization/List.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('organization/PassCodeManagement.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/organization/PassCodeManagement.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})

// --- Policies ---
describe('policies/Category.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/policies/Category.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('policies/Detail.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/policies/Detail.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('policies/Edit.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/policies/Edit.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('policies/List.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/policies/List.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('policies/Search.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/policies/Search.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})

// --- DataPackage ---
describe('dataPackage/IncrementalUpdate.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/dataPackage/IncrementalUpdate.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('dataPackage/List.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/dataPackage/List.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('dataPackage/PackageVersion.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/dataPackage/PackageVersion.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('dataPackage/ReceivePackage.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/dataPackage/ReceivePackage.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('dataPackage/ReportPackage.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/dataPackage/ReportPackage.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})

// --- DataSync ---
describe('dataSync/ConflictResolution.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/dataSync/ConflictResolution.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('dataSync/Export.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/dataSync/Export.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('dataSync/Import.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/dataSync/Import.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})

// --- Approval ---
describe('approval/History.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/approval/History.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('approval/MyApplications.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/approval/MyApplications.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('approval/Overview.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/approval/Overview.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('approval/PendingList.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/approval/PendingList.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})

// --- RuralWorks ---
describe('ruralWorks/Analysis.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/ruralWorks/Analysis.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('ruralWorks/Index.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/ruralWorks/Index.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('ruralWorks/List.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/ruralWorks/List.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('ruralWorks/Report.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/ruralWorks/Report.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('ruralWorks/Task.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/ruralWorks/Task.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})

// --- Other views ---
describe('admin/MachineCode.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/admin/MachineCode.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('admin/MachineCodeManagement.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/admin/MachineCodeManagement.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('analytics/Assessment.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/analytics/Assessment.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('batch/Index.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/batch/Index.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('dataAnalysis/Index.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/dataAnalysis/Index.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('dataEntry/ComprehensiveEntry.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/dataEntry/ComprehensiveEntry.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('dataManagement/Index.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/dataManagement/Index.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('dataVerify/RulesManagement.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/dataVerify/RulesManagement.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('effectiveness/Evaluation.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/effectiveness/Evaluation.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('effectiveness/Rankings.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/effectiveness/Rankings.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('errorPage/403.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/errorPage/403.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('errorPage/500.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/errorPage/500.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('export/ReportExport.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/export/ReportExport.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('help/HelpCenter.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/help/HelpCenter.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('import/DataImport.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/import/DataImport.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('message/MessageCenter.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/message/MessageCenter.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('NotFound.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/NotFound.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('reportTemplates/Index.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/reportTemplates/Index.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('sentiment/Index.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/sentiment/Index.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('dashboard/index.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/views/dashboard/index.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
