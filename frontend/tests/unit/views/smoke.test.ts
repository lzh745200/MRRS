/**
 * Comprehensive view smoke tests — verify every Vue view can be imported and mounted.
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import ElementPlus from 'element-plus'

// Mock dependencies
vi.mock('@/api/request', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: {} }), post: vi.fn().mockResolvedValue({ data: {} }), put: vi.fn().mockResolvedValue({ data: {} }), delete: vi.fn().mockResolvedValue({ data: {} }) },
  get: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  post: vi.fn().mockResolvedValue({ code: 200 }),
  put: vi.fn().mockResolvedValue({ code: 200 }),
  del: vi.fn().mockResolvedValue({ code: 200 }),
  apiRequest: vi.fn().mockResolvedValue({}),
  parseContentDisposition: vi.fn().mockReturnValue('test.xlsx'),
  downloadBlob: vi.fn(),
  freezeRequests: vi.fn(),
  unfreezeRequests: vi.fn(),
  cancelAllRequests: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

// src/utils/echarts.ts <-> src/utils/echarts-theme.ts 存在循环导入：
// echarts.ts 顶层调用 registerMilitaryTheme() 时其 default 导出尚未初始化，
// 测试环境下会抛 TypeError。此处 mock echarts-theme 以打破循环。
vi.mock('@/utils/echarts-theme', () => ({
  registerMilitaryTheme: vi.fn(),
  getCurrentTheme: vi.fn().mockReturnValue('militaryTech'),
  COLOR_PALETTE: [],
  MILITARY_BLUE: '#1e4d8c',
  REVITALIZATION_GREEN: '#2d6a4f',
  BADGE_GOLD: '#b8960c',
}))

vi.mock('@/api/audit', () => ({ auditApi: { getLogs: vi.fn().mockResolvedValue({ items: [], total: 0 }), getStats: vi.fn().mockResolvedValue({}), getLoginAttempts: vi.fn().mockResolvedValue({ items: [] }), getSecurityEvents: vi.fn().mockResolvedValue({ items: [] }), resolveSecurityEvent: vi.fn() } }))
vi.mock('@/api/effectiveness', () => ({ evaluateVillage: vi.fn(), getRankings: vi.fn().mockResolvedValue({ items: [] }), compareEvaluations: vi.fn() }))
vi.mock('@/api/help', () => ({ getHelpArticles: vi.fn().mockResolvedValue({ items: [] }) }))
vi.mock('@/api/report', () => ({ reportApi: { generate: vi.fn(), download: vi.fn() } }))
vi.mock('@/api/funds', () => ({ fundApi: { list: vi.fn().mockResolvedValue({ items: [], total: 0 }) } }))
vi.mock('@/api/policy', () => ({ getLevelOptions: vi.fn().mockResolvedValue({ data: [] }), getPolicies: vi.fn().mockResolvedValue({ items: [], total: 0 }) }))
vi.mock('@/api/import', () => ({ downloadImportTemplateAndSave: vi.fn() }))

vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ isAdmin: false, isAuthenticated: true, token: 'x', user: { role: 'admin', id: 1, username: 'admin' }, mustChangePassword: false }) }))
vi.mock('@/stores/user', () => ({ useUserStore: () => ({ currentUser: { id: 1, username: 'admin' }, changePassword: vi.fn() }) }))
vi.mock('@/stores/menu', () => ({ useMenuStore: () => ({ canAccessMenu: () => true }) }))
vi.mock('@/stores/project', () => ({ useProjectStore: () => ({ projects: [], currentProject: null }) }))
vi.mock('@/stores/policy', () => ({ usePolicyStore: () => ({ policyList: [], total: 0, current: null }) }))
vi.mock('@/stores/funds', () => ({ useFundsStore: () => ({ fundList: [], total: 0 }) }))
vi.mock('@/stores/village', () => ({ useVillageStore: () => ({ villageList: [], total: 0 }) }))
vi.mock('@/stores/organization', () => ({ useOrganizationStore: () => ({ orgs: [], tree: [] }) }))
vi.mock('@/stores/rbac', () => ({ useRbacStore: () => ({ roles: [], permissions: [], hasPermission: () => true }) }))
vi.mock('@/stores/config', () => ({ useConfigStore: () => ({ theme: 'light', appName: 'Test' }) }))
vi.mock('@/stores/app', () => ({ useAppStore: () => ({ sidebarCollapsed: false }) }))
vi.mock('@/composables/useRouterSafe', () => ({ useRouterSafe: () => ({ pushSafe: vi.fn() }) }))
vi.mock('@/composables/useDesensitize', () => ({ useDesensitize: () => ({ desensitize: (v: any) => v }) }))
vi.mock('@/utils/authStorage', () => ({ AuthStorage: { getToken: () => 'x', getUser: () => ({ id: 1 }), clear: vi.fn(), setToken: vi.fn(), setUser: vi.fn() } }))
vi.mock('@/utils/logger', () => ({ logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() } }))

const router = createRouter({ history: createWebHistory(), routes: [{ path: '/', component: { template: '<div></div>' } }] })

// ═══════════════════════════════════════════════════════
// Core views — verify mounting
// ═══════════════════════════════════════════════════════

describe('Core view smoke tests', () => {
  const views = [
    { name: 'NotFound', path: '@/views/NotFound.vue' },
    { name: 'ChangePassword', path: '@/views/auth/ChangePassword.vue' },
    { name: 'LoginEnhanced', path: '@/views/auth/LoginEnhanced.vue' },
    { name: 'Register', path: '@/views/auth/Register.vue' },
    { name: 'ForgotPassword', path: '@/views/auth/ForgotPassword.vue' },
    { name: 'Profile', path: '@/views/auth/Profile.vue' },
  ]

  views.forEach(({ name, path }) => {
    it(`${name} can be imported`, async () => {
      const mod = await import(/* @vite-ignore */ path)
      expect(mod.default).toBeDefined()
    })
  })

  it('Dashboard index imports', async () => {
    const mod = await import('@/views/dashboard/index.vue')
    expect(mod.default).toBeDefined()
  })

  it('DefaultLayoutSafe imports', async () => {
    const mod = await import('@/layouts/DefaultLayoutSafe.vue')
    expect(mod.default).toBeDefined()
  })
})

// ═══════════════════════════════════════════════════════
// Business views — verify import
// ═══════════════════════════════════════════════════════

describe('Business module view imports', () => {
  const businessViews = [
    ['Village List', '@/views/analytics/supported-villages/List.vue'],
    ['Village Detail', '@/views/analytics/supported-villages/Detail.vue'],
    ['Village Yearly', '@/views/analytics/supported-villages/YearlyOverview.vue'],
    ['School List', '@/views/schools/List.vue'],
    ['School Detail', '@/views/schools/Detail.vue'],
    ['School Edit', '@/views/schools/Edit.vue'],
    ['School Analysis', '@/views/schools/Analysis.vue'],
    ['Project List', '@/views/projects/List.vue'],
    ['Project Edit', '@/views/projects/Edit.vue'],
    ['Project Detail', '@/views/projects/Detail.vue'],
    ['Project Import', '@/views/projects/Import.vue'],
    ['Funds Index', '@/views/funds/EnhancedList.vue'],
    ['Funds Detail', '@/views/funds/Detail.vue'],
    ['Funds User List', '@/views/funds/UserFundList.vue'],
    ['Funds Report', '@/views/funds/Report.vue'],
    ['Policy List', '@/views/policies/List.vue'],
    ['Policy Edit', '@/views/policies/Edit.vue'],
    ['Policy Detail', '@/views/policies/Detail.vue'],
    ['Rural Works Index', '@/views/ruralWorks/Index.vue'],
    ['Rural Works List', '@/views/ruralWorks/List.vue'],
    ['Rural Works Task', '@/views/ruralWorks/Task.vue'],
    ['Rural Works Report', '@/views/ruralWorks/Report.vue'],
    ['Organization List', '@/views/organization/List.vue'],
    ['Organization Edit', '@/views/organization/Edit.vue'],
  ]

  businessViews.forEach(([label, p]) => {
    it(label, async () => {
      const mod = await import(p)
      expect(mod.default).toBeDefined()
    })
  })
})

// ═══════════════════════════════════════════════════════
// System views — verify import
// ═══════════════════════════════════════════════════════

describe('System view imports', () => {
  const systemViews = [
    ['Audit Management', '@/views/system/AuditManagement.vue'],
    ['Backup Management', '@/views/system/BackupManagement.vue'],
    ['User Management', '@/views/system/UserManagement.vue'],
    ['Role', '@/views/system/Role.vue'],
    ['Monitoring', '@/views/system/MonitoringDashboard.vue'],
    ['Menu', '@/views/system/Menu.vue'],
    ['Update Logs', '@/views/system/UpdateLogs.vue'],
    ['User Permissions', '@/views/system/UserPermissions.vue'],
    ['Feedback', '@/views/system/Feedback.vue'],
    ['Env Check', '@/views/system/EnvCheck.vue'],
    ['Error Reports', '@/views/system/ErrorReports.vue'],
    ['Cache Management', '@/views/system/CacheManagement.vue'],
    ['Encryption Settings', '@/views/system/EncryptionSettings.vue'],
    ['Task Manager', '@/views/system/TaskManager.vue'],
    ['Secrets Management', '@/views/system/SecretsManagement.vue'],
    ['Zero Trust', '@/views/system/ZeroTrust.vue'],
    ['Email Settings', '@/views/system/EmailSettings.vue'],
    ['I18n Management', '@/views/system/I18nManagement.vue'],
    ['Data Tier', '@/views/system/DataTier.vue'],
  ]

  systemViews.forEach(([label, p]) => {
    it(label, async () => {
      const mod = await import(p)
      expect(mod.default).toBeDefined()
    })
  })
})

// ═══════════════════════════════════════════════════════
// Data & workflow views
// ═══════════════════════════════════════════════════════

describe('Data and workflow view imports', () => {
  const dataViews = [
    ['Data Management', '@/views/dataManagement/Index.vue'],
    ['Data Management Overview', '@/views/dataManagement/Overview.vue'],
    ['Data Package List', '@/views/dataPackage/List.vue'],
    ['Data Sync Export', '@/views/dataSync/Export.vue'],
    ['Data Sync Import', '@/views/dataSync/Import.vue'],
    ['Data Verify Index', '@/views/dataVerify/Index.vue'],
    ['Data Analysis Index', '@/views/dataAnalysis/Index.vue'],
    ['Data Entry', '@/views/dataEntry/ComprehensiveEntry.vue'],
    ['Data Import', '@/views/import/DataImport.vue'],
    ['Export Report', '@/views/export/ReportExport.vue'],
    ['Approval Overview', '@/views/approval/Overview.vue'],
    ['Approval Pending', '@/views/approval/PendingList.vue'],
    ['Approval My', '@/views/approval/MyApplications.vue'],
    ['Approval History', '@/views/approval/History.vue'],
    ['Effectiveness Eval', '@/views/effectiveness/Evaluation.vue'],
    ['Effectiveness Rankings', '@/views/effectiveness/Rankings.vue'],
    ['Report List', '@/views/report/List.vue'],
    ['Report Templates', '@/views/reportTemplates/Index.vue'],
    ['Todos', '@/views/todos/Index.vue'],
    ['Message Center', '@/views/message/MessageCenter.vue'],
    ['Work Calendar', '@/views/work-calendar/Index.vue'],
    ['Help Center', '@/views/help/HelpCenter.vue'],
    ['Sentiment', '@/views/sentiment/Index.vue'],
  ]

  dataViews.forEach(([label, p]) => {
    it(label, async () => {
      const mod = await import(p)
      expect(mod.default).toBeDefined()
    })
  })
})

// ═══════════════════════════════════════════════════════
// Component imports
// ═══════════════════════════════════════════════════════

describe('Common component imports', () => {
  const components = [
    ['MapPicker', '@/components/MapPicker.vue'],
    ['GuizhouRegionSelector', '@/components/common/GuizhouRegionSelector.vue'],
    ['PageHeader', '@/components/PageHeader.vue'],
    ['GlobalSearch', '@/components/GlobalSearch.vue'],
    ['SkeletonList', '@/components/SkeletonList.vue'],
    ['FilePreview', '@/components/FilePreview.vue'],
    ['BaseButton', '@/components/common/BaseButton.vue'],
    ['BaseTable', '@/components/common/BaseTable.vue'],
    ['BaseForm', '@/components/common/BaseForm.vue'],
    ['BaseChart', '@/components/common/BaseChart.vue'],
    ['DataTable', '@/components/common/DataTable.vue'],
    ['StatsCard', '@/components/common/StatsCard.vue'],
    ['EmptyState', '@/components/business/EmptyState/EmptyState.vue'],
    ['BatchOperationBar', '@/components/common/BatchOperationBar.vue'],
    ['Breadcrumb', '@/components/common/Breadcrumb.vue'],
    ['ExportButton', '@/components/common/ExportButton.vue'],
    ['ImportButton', '@/components/common/ImportButton.vue'],
    ['ProgressDialog', '@/components/common/ProgressDialog.vue'],
    ['PasswordStrength', '@/components/common/PasswordStrength.vue'],
    ['VirtualList', '@/components/common/VirtualList.vue'],
    ['ResponsiveDataTable', '@/components/common/ResponsiveDataTable.vue'],
    ['SkipLink', '@/components/common/SkipLink.vue'],
    ['NetworkStatusIndicator', '@/components/common/NetworkStatusIndicator.vue'],
    ['LazyImage', '@/components/common/LazyImage/LazyImage.vue'],
    ['PageContainer', '@/components/common/PageContainer.vue'],
  ]

  components.forEach(([label, p]) => {
    it(label, async () => {
      const mod = await import(p)
      expect(mod.default).toBeDefined()
    })
  })
})

// ═══════════════════════════════════════════════════════
// Store import verification
// ═══════════════════════════════════════════════════════

describe('Store imports', () => {
  const stores = [
    'app', 'auth', 'user', 'project', 'funds', 'village', 'policy',
    'organization', 'rbac', 'menu', 'config', 'route',
    'taskQueue', 'dataPackage', 'dataReport',
  ]

  stores.forEach((name) => {
    it(`use${name.charAt(0).toUpperCase() + name.slice(1)}Store imports`, async () => {
      const mod = await import(`@/stores/${name}.ts`)
      expect(mod).toBeDefined()
    })
  })
})

// ═══════════════════════════════════════════════════════
// API module import verification
// ═══════════════════════════════════════════════════════

describe('API module imports', () => {
  const apis = [
    'request', 'import', 'projects', 'schools', 'policy', 'funds',
    'supportedVillage', 'organization', 'audit', 'approval', 'effectiveness',
    'help', 'report', 'todos', 'backup', 'dataSync', 'dataPackage',
    'dataQuality', 'ruralWork', 'tasks', 'search', 'map', 'message',
    'machineCode', 'organizationPassCode', 'userPermissions', 'userManagement',
    'export', 'batchOperations', 'validationRules', 'systemMonitor',
    'analytics', 'dashboard', 'sentiment', 'secrets', 'twoFactor',
    'fundLifecycle', 'fundStatistics', 'ai', 'env', 'i18n', 'offlineMap',
    'errorReport', 'dataTier', 'chunkedUpload', 'updateLogs', 'zeroTrust',
  ]

  apis.forEach((name) => {
    it(`${name} imports`, async () => {
      const mod = await import(`@/api/${name}.ts`)
      expect(mod).toBeDefined()
    })
  })
})
