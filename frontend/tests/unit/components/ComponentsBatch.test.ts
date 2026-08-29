/**
 * Components 批量组件测试
 * 覆盖 src/components/ 下未单独测试的组件
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

enableAutoUnmount(afterEach)

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(() => Promise.resolve()), resolve: vi.fn(() => ({ name: 'x', matched: [{ path: '/x' }] })) }),
  useRoute: () => ({ params: {}, query: {}, path: '/x' }),
  onBeforeRouteLeave: vi.fn(),
  RouterLink: { template: '<a><slot/></a>' },
}))
const mockGet = vi.fn()
const mockPost = vi.fn()
vi.mock('@/api/request', () => ({
  get: (...a: any[]) => mockGet(...a),
  post: (...a: any[]) => mockPost(...a),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))
vi.mock('@/utils/logger', () => ({ logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() } }))
vi.mock('@/composables/useRouterSafe', () => ({ useRouterSafe: () => ({ push: vi.fn(() => Promise.resolve()), pushSafe: vi.fn(() => Promise.resolve()) }), pushSafe: vi.fn(() => Promise.resolve()), safeRouteParam: (v: unknown, fallback = 0) => { const n = Number(Array.isArray(v) ? v[0] : v); return Number.isFinite(n) ? n : fallback } }))
vi.mock('@/utils/notify', () => ({ notify: Object.assign(() => vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn(), closeAll: vi.fn() }), default: vi.fn() }))
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
  ElRow: { template: '<div><slot/></div>' },
  ElCol: { template: '<div><slot/></div>' },
  ElTooltip: { template: '<span><slot/></span>' },
  ElPopover: { template: '<div><slot/></div>' },
  ElDropdown: { template: '<div><slot/></div>' },
  ElDropdownItem: { template: '<div><slot/></div>' },
  ElDropdownMenu: { template: '<div><slot/></div>' },
  ElSwitch: { template: '<div/>' },
  ElDatePicker: { template: '<input/>' },
  ElTimePicker: { template: '<input/>' },
  ElRadio: { template: '<input type="radio"/>' },
  ElRadioGroup: { template: '<div><slot/></div>' },
  ElCheckbox: { template: '<input type="checkbox"/>' },
  ElCheckboxGroup: { template: '<div><slot/></div>' },
  ElUpload: { template: '<div><slot/></div>' },
  ElProgress: { template: '<div/>' },
  ElCollapse: { template: '<div><slot/></div>' },
  ElCollapseItem: { template: '<div><slot/></div>' },
  ElSteps: { template: '<div><slot/></div>' },
  ElStep: { template: '<div/>' },
  ElBadge: { template: '<span><slot/></span>' },
  ElAvatar: { template: '<div/>' },
  ElDescriptions: { template: '<div><slot/></div>' },
  ElDescriptionsItem: { template: '<div><slot/></div>' },
  ElDivider: { template: '<hr/>' },
  ElEmpty: { template: '<div/>' },
  ElImage: { template: '<img/>' },
  ElLink: { template: '<a><slot/></a>' },
  ElPageHeader: { template: '<div><slot/></div>' },
  ElSkeleton: { template: '<div><slot/></div>' },
  ElSlider: { template: '<input type="range"/>' },
  ElTree: { template: '<div><slot/></div>' },
}))

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  mockGet.mockResolvedValue({ data: { items: [], total: 0 }, success: true, items: [], total: 0 })
  mockPost.mockResolvedValue({ data: {}, success: true })
})

// --- common/ components ---
describe('common/ChangeHistoryDialog.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/ChangeHistoryDialog.vue'); const w = mount(C, { props: { modelValue: false } }); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/ErrorBoundary.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/ErrorBoundary.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/GuizhouRegionSelector.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/GuizhouRegionSelector.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/ImportButton.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/ImportButton.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/StatsCard.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/StatsCard.vue'); const w = mount(C, { props: { title: 'Test', value: 100 } }); expect(w.exists()).toBe(true) })
})
describe('common/BaseChart.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/BaseChart.vue'); const w = mount(C, { props: { option: {} } }); expect(w.exists()).toBe(true) })
})

// --- layout/ components ---

// --- dashboard/ components ---
// --- business/ components ---
// --- Other components ---
describe('permission/PermissionAssignmentDrawer.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/permission/PermissionAssignmentDrawer.vue'); const w = mount(C, { props: { modelValue: false } }); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('permission/PermissionTreePanel.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/permission/PermissionTreePanel.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('dataPackage/ExportDialog.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/dataPackage/ExportDialog.vue'); const w = mount(C, { props: { modelValue: false } }); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('dataPackage/ExportEncryptedDialog.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/dataPackage/ExportEncryptedDialog.vue'); const w = mount(C, { props: { modelValue: false } }); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('dataPackage/ImportDialog.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/dataPackage/ImportDialog.vue'); const w = mount(C, { props: { modelValue: false } }); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('dataPackage/ImportEncryptedDialog.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/dataPackage/ImportEncryptedDialog.vue'); const w = mount(C, { props: { modelValue: false } }); await flushPromises(); expect(w.exists()).toBe(true) }) })