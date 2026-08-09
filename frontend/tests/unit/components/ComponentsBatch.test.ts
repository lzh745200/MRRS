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
describe('common/Breadcrumb.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/Breadcrumb.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/ChangeHistoryDialog.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/ChangeHistoryDialog.vue'); const w = mount(C, { props: { modelValue: false } }); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/DataTable.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/DataTable.vue'); const w = mount(C, { props: { data: [], columns: [] } }); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/ErrorBoundary.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/ErrorBoundary.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/ExportButton.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/ExportButton.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/FormWizard.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/FormWizard.vue'); const w = mount(C, { props: { steps: [{ title: 'Step 1' }] } }); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/FundSummary.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/FundSummary.vue'); const w = mount(C, { props: { data: { total: 100, used: 50 } } }); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/GuizhouRegionSelector.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/GuizhouRegionSelector.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/Header.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/Header.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/ImportButton.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/ImportButton.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/NetworkStatusIndicator.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/NetworkStatusIndicator.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/PageContainer.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/PageContainer.vue'); const w = mount(C, { slots: { default: '<div>test</div>' } }); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/PasswordStrength.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/PasswordStrength.vue'); const w = mount(C, { props: { passwordStrength: 'medium' } }); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/PrintDialog.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/PrintDialog.vue'); const w = mount(C, { props: { modelValue: false } }); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/PrintTable.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/PrintTable.vue'); const w = mount(C, { props: { data: [] } }); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/ProgressChart.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/ProgressChart.vue'); const w = mount(C, { props: { percent: 50 } }); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/ProgressDialog.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/ProgressDialog.vue'); const w = mount(C, { props: { modelValue: false, progress: 0 } }); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/QiannanRegionSelector.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/QiannanRegionSelector.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/ResponsiveDataTable.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/ResponsiveDataTable.vue'); const w = mount(C, { props: { data: [], columns: [] } }); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/Sidebar.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/Sidebar.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) })
})
describe('common/PasswordStrength.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/PasswordStrength.vue'); const w = mount(C, { props: { passwordStrength: 'medium' } }); expect(w.exists()).toBe(true) })
})
describe('common/StatsCard.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/StatsCard.vue'); const w = mount(C, { props: { title: 'Test', value: 100 } }); expect(w.exists()).toBe(true) })
})
describe('common/VirtualList.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/VirtualList.vue'); const w = mount(C, { props: { items: [], itemSize: 40 } }); expect(w.exists()).toBe(true) })
})
describe('common/VirtualTable.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/VirtualTable.vue'); const w = mount(C, { props: { data: [], columns: [] } }); expect(w.exists()).toBe(true) })
})
describe('common/BaseButton.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/BaseButton.vue'); const w = mount(C, { slots: { default: 'Click' } }); expect(w.exists()).toBe(true) })
})
describe('common/BaseChart.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/BaseChart.vue'); const w = mount(C, { props: { option: {} } }); expect(w.exists()).toBe(true) })
})
describe('common/BaseForm.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/BaseForm.vue'); const w = mount(C, { props: { modelValue: {}, fields: [] } }); expect(w.exists()).toBe(true) })
})
describe('common/BaseInput.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/BaseInput.vue'); const w = mount(C, { props: { modelValue: '' } }); expect(w.exists()).toBe(true) })
})
describe('common/BaseTable.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/BaseTable.vue'); const w = mount(C, { props: { data: [], columns: [] } }); expect(w.exists()).toBe(true) })
})
describe('common/BatchOperationBar.vue', () => {
  it('渲染', async () => { const { default: C } = await import('@/components/common/BatchOperationBar.vue'); const w = mount(C, { props: { selectedCount: 0 } }); expect(w.exists()).toBe(true) })
})

// --- layout/ components ---
describe('layout/AppFooter.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/layout/AppFooter.vue'); const w = mount(C); expect(w.exists()).toBe(true) }) })
describe('layout/AppHeader.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/layout/AppHeader.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('layout/AppSidebar.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/layout/AppSidebar.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('layout/EnhancedLayout.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/layout/EnhancedLayout.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('layout/MainLayout.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/layout/MainLayout.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('layout/MobileBottomNav.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/layout/MobileBottomNav.vue'); const w = mount(C); expect(w.exists()).toBe(true) }) })

// --- dashboard/ components ---
describe('dashboard/ActivityFeed.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/dashboard/ActivityFeed.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('dashboard/BackupRestoreModal.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/dashboard/BackupRestoreModal.vue'); const w = mount(C, { props: { modelValue: false } }); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('dashboard/ProjectProgress.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/dashboard/ProjectProgress.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) }) })

// --- business/ components ---
describe('business/DataStatistics.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/business/DataStatistics.vue'); const w = mount(C, { props: { data: [] } }); expect(w.exists()).toBe(true) }) })
describe('business/GalleryView.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/business/GalleryView.vue'); const w = mount(C, { props: { images: [] } }); expect(w.exists()).toBe(true) }) })
describe('business/ImageComparison.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/business/ImageComparison.vue'); const w = mount(C, { props: { before: '', after: '' } }); expect(w.exists()).toBe(true) }) })
describe('business/IndustryCard.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/business/IndustryCard.vue'); const w = mount(C, { props: { data: {} } }); expect(w.exists()).toBe(true) }) })
describe('business/PersonnelList.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/business/PersonnelList.vue'); const w = mount(C, { props: { data: [] } }); expect(w.exists()).toBe(true) }) })
describe('business/ProjectCard.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/business/ProjectCard.vue'); const w = mount(C, { props: { project: {} } }); expect(w.exists()).toBe(true) }) })
describe('business/SystemStatus.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/business/SystemStatus.vue'); const w = mount(C); expect(w.exists()).toBe(true) }) })
describe('business/VillageCard.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/business/VillageCard.vue'); const w = mount(C, { props: { village: {} } }); expect(w.exists()).toBe(true) }) })
describe('business/BeforeAfterSlider.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/business/BeforeAfterSlider.vue'); const w = mount(C, { props: { before: '', after: '' } }); expect(w.exists()).toBe(true) }) })
describe('business/ProgressAlbum.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/business/ProgressAlbum.vue'); const w = mount(C, { props: { items: [] } }); expect(w.exists()).toBe(true) }) })

// --- Other components ---
describe('FilePreview.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/FilePreview.vue'); const w = mount(C, { props: { url: '', name: 'test.pdf' } }); expect(w.exists()).toBe(true) }) })
describe('GlobalSearch.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/GlobalSearch.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('PageHeader.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/PageHeader.vue'); const w = mount(C, { props: { title: 'Test' } }); expect(w.exists()).toBe(true) }) })
describe('MapPicker.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/MapPicker.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('charts/StatisticsCard.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/charts/StatisticsCard.vue'); const w = mount(C, { props: { title: 'Test', value: 100 } }); expect(w.exists()).toBe(true) }) })
describe('ui/SecurityMonitor.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/ui/SecurityMonitor.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('map/OfflineMap.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/map/OfflineMap.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('rbac/PermissionManager.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/rbac/PermissionManager.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('permission/MenuVisibilityPanel.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/permission/MenuVisibilityPanel.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('permission/PermissionAssignmentDrawer.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/permission/PermissionAssignmentDrawer.vue'); const w = mount(C, { props: { modelValue: false } }); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('permission/PermissionTreePanel.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/permission/PermissionTreePanel.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('permission/RoleTagsPanel.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/permission/RoleTagsPanel.vue'); const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('report/ReviewDialog.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/report/ReviewDialog.vue'); const w = mount(C, { props: { modelValue: false } }); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('dataPackage/ExportDialog.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/dataPackage/ExportDialog.vue'); const w = mount(C, { props: { modelValue: false } }); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('dataPackage/ExportEncryptedDialog.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/dataPackage/ExportEncryptedDialog.vue'); const w = mount(C, { props: { modelValue: false } }); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('dataPackage/ImportDialog.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/dataPackage/ImportDialog.vue'); const w = mount(C, { props: { modelValue: false } }); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('dataPackage/ImportEncryptedDialog.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/dataPackage/ImportEncryptedDialog.vue'); const w = mount(C, { props: { modelValue: false } }); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('funds/CategorizedFundForm.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/funds/CategorizedFundForm.vue'); const w = mount(C, { props: { modelValue: {} } }); await flushPromises(); expect(w.exists()).toBe(true) }) })
describe('funds/YearlyComparisonChart.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/funds/YearlyComparisonChart.vue'); const w = mount(C, { props: { data: [] } }); expect(w.exists()).toBe(true) }) })
describe('common/SkipLink.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/common/SkipLink.vue'); const w = mount(C); expect(w.exists()).toBe(true) }) })
describe('common/LazyImage/LazyImage.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/common/LazyImage/LazyImage.vue'); const w = mount(C, { props: { src: '', alt: 'test' } }); expect(w.exists()).toBe(true) }) })
describe('common/Skeleton/Skeleton.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/common/Skeleton/Skeleton.vue'); const w = mount(C); expect(w.exists()).toBe(true) }) })
describe('business/ChartCard/ChartCard.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/business/ChartCard/ChartCard.vue'); const w = mount(C, { props: { title: 'Test' } }); expect(w.exists()).toBe(true) }) })
describe('business/DataTable/DataTable.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/business/DataTable/DataTable.vue'); const w = mount(C, { props: { data: [], columns: [] } }); expect(w.exists()).toBe(true) }) })
describe('business/EmptyState/EmptyState.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/business/EmptyState/EmptyState.vue'); const w = mount(C); expect(w.exists()).toBe(true) }) })
describe('business/FormBuilder/FormBuilder.vue', () => { it('渲染', async () => { const { default: C } = await import('@/components/business/FormBuilder/FormBuilder.vue'); const w = mount(C, { props: { fields: [] } }); expect(w.exists()).toBe(true) }) })
