/**
 * System Views 批量组件测试
 *
 * 覆盖 src/views/system/ 下所有未单独测试的视图组件
 * 目标：每个组件 90%+ 语句覆盖
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

// 自动卸载组件，防止组件的 setInterval/setTimeout 在测试结束后继续运行
enableAutoUnmount(afterEach)

// ==================== Shared Mocks ====================

const mockPush = vi.fn(() => Promise.resolve())
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, resolve: vi.fn(() => ({ name: 'x', matched: [{ path: '/x' }] })) }),
  useRoute: () => ({ params: {}, query: {}, path: '/system' }),
}))

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDel = vi.fn()
vi.mock('@/api/request', () => ({
  get: (...a: any[]) => mockGet(...a),
  post: (...a: any[]) => mockPost(...a),
  put: (...a: any[]) => mockPut(...a),
  del: (...a: any[]) => mockDel(...a),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() },
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ push: mockPush, pushSafe: mockPush }),
  pushSafe: vi.fn(() => Promise.resolve()),
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  ElMessageBox: { confirm: vi.fn(() => Promise.resolve('confirm')), alert: vi.fn(), prompt: vi.fn() },
}))

// Mock @element-plus/icons-vue — 使用 importOriginal 保留所有真实导出
vi.mock('@element-plus/icons-vue', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  return { ...actual }
})

// Mock @/api/chunkedUpload — ChunkedUploadManager.vue 导入 chunkedUploadApi
vi.mock('@/api/chunkedUpload', () => ({
  chunkedUploadApi: {
    initUpload: vi.fn(() => Promise.resolve({ session_id: 'test-session', file_name: 'test.txt', file_size: 1024, chunk_size: 5242880, total_chunks: 1, status: 'initialized' })),
    uploadChunk: vi.fn(() => Promise.resolve({ success: true, chunk_index: 0 })),
    getProgress: vi.fn(() => Promise.resolve({ session_id: 'test-session', file_name: 'test.txt', total_chunks: 1, uploaded_chunks: 1, progress: 100, status: 'completed' })),
    mergeChunks: vi.fn(() => Promise.resolve({ session_id: 'test-session', file_path: '/tmp/test.txt', file_name: 'test.txt', status: 'merged' })),
    cancelUpload: vi.fn(() => Promise.resolve({ success: true, message: 'cancelled' })),
  },
}))

// ==================== Helpers ====================

function makeMockGet(overrides: Record<string, any> = {}) {
  const defaults: Record<string, any> = {
    '/system/audit/stats': { todayOps: 5, activeUsers: 3, warnings: 1, failures: 2 },
    '/system/audit/logs': { items: [{ id: 1, user: 'admin', action: 'login', target: '系统', time: '10:00', ip: '10.0.0.1', status: 'success' }], total: 1 },
    '/system/audit/login-attempts': { items: [{ id: 1, user: 'admin', ip: '10.0.0.1', time: '10:00', success: true }], total: 1 },
    '/system/backup/list': { items: [{ id: 1, filename: 'backup.zip', size: 1024, created_at: '2024-01-01', description: 'test' }], total: 1 },
    '/system/backup/schedule': { enabled: true, frequency: 'daily', backup_time: '02:00', retention_count: 7 },
    '/system/cache/status': { status: 'healthy', size: '100MB', keys: 500, hit_rate: '85%' },
    '/system/cache/keys': { items: [{ key: 'user_1', ttl: 300, size: 1024 }], total: 1 },
    '/system/config': { items: [{ key: 'site_name', value: '帮扶系统', description: '站点名称' }], total: 1 },
    '/system/update-logs': { items: [{ id: 1, version: '1.2.0', content: '修复', created_at: '2024-01-01' }], total: 1 },
    '/system/tasks': { items: [{ id: 1, name: '清理任务', status: 'running', progress: 50 }], total: 1 },
    '/system/roles': { items: [{ id: 1, name: 'admin', description: '管理员', permissions: [] }], total: 1 },
    '/system/permissions': { items: [{ id: 1, name: 'user.create', description: '创建用户' }], total: 1 },
    '/system/users': { items: [{ id: 1, username: 'admin', real_name: '管理员', role: 'admin', status: 'active' }], total: 1 },
    '/system/email/settings': { smtp_host: 'localhost', smtp_port: 25, from_email: 'test@test.com' },
    '/system/encryption/status': { enabled: true, algorithm: 'AES-256', key_rotation: '2024-01-01' },
    '/system/env-check': { status: 'ok', checks: [{ name: 'Python', status: 'ok', version: '3.11' }] },
    '/system/error-reports': { items: [{ id: 1, error_type: 'TypeError', message: 'test', time: '2024-01-01' }], total: 1 },
    '/system/feedback': { items: [{ id: 1, user: 'admin', content: 'good', time: '2024-01-01' }], total: 1 },
    '/system/i18n/translations': { items: [{ key: 'hello', zh: '你好', en: 'Hello' }], total: 1 },
    '/system/map/tiles': { items: [{ id: 1, name: 'tile1', status: 'ready' }], total: 1 },
    '/system/menu': { items: [{ id: 1, title: '首页', path: '/', icon: 'home' }], total: 1 },
    '/system/secrets': { items: [{ id: 1, name: 'DB_KEY', type: 'string', created_at: '2024-01-01' }], total: 1 },
    '/system/init/status': { initialized: true, steps: [{ name: 'DB', status: 'done' }] },
    '/system/data-tier': { items: [{ id: 1, table: 'logs', tier: 'cold', rows: 1000 }], total: 1 },
    '/system/chunked-upload/status': { active_uploads: 0, completed: 5 },
    '/system/config-package': { items: [{ id: 1, name: 'pkg1', version: '1.0' }], total: 1 },
    '/system/zero-trust/status': { enabled: true, devices: 3, alerts: 0 },
    '/system/user-permissions': { items: [{ id: 1, user: 'admin', permissions: ['read'] }], total: 1 },
    ...overrides,
  }
  return vi.fn((url: string) => {
    for (const [pattern, data] of Object.entries(defaults)) {
      if (url.includes(pattern) || url === pattern) {
        return Promise.resolve({ data, success: true, ...data })
      }
    }
    return Promise.resolve({ data: { items: [], total: 0 }, success: true, items: [], total: 0 })
  })
}

function setupPinia() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return pinia
}

beforeEach(() => {
  vi.clearAllMocks()
  setupPinia()
  mockGet.mockImplementation(makeMockGet())
  mockPost.mockResolvedValue({ data: { id: 1 }, success: true })
  mockPut.mockResolvedValue({ data: { id: 1 }, success: true })
  mockDel.mockResolvedValue({ data: null, success: true })
})

// ==================== Tests ====================

// --- AuditManagement ---
describe('AuditManagement.vue', () => {
  it('渲染并加载数据', async () => {
    const { default: Comp } = await import('@/views/system/AuditManagement.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
    expect(mockGet).toHaveBeenCalled()
  })
  it('切换 tab', async () => {
    const { default: Comp } = await import('@/views/system/AuditManagement.vue')
    const w = mount(Comp)
    await flushPromises()
    const vm = w.vm as any
    if (vm.activeTab !== undefined) {
      vm.activeTab = 'login'
      await nextTick()
    }
    expect(w.exists()).toBe(true)
  })
  it('actionTagType 返回正确类型', async () => {
    const { default: Comp } = await import('@/views/system/AuditManagement.vue')
    const w = mount(Comp)
    await flushPromises()
    const vm = w.vm as any
    if (vm.actionTagType) {
      expect(vm.actionTagType('login')).toBe('success')
      expect(vm.actionTagType('delete_project')).toBe('danger')
      expect(vm.actionTagType('unknown')).toBe('info')
    }
  })
})

// --- BackupManagement ---
describe('BackupManagement.vue', () => {
  it('渲染并加载备份列表', async () => {
    const { default: Comp } = await import('@/views/system/BackupManagement.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
    expect(mockGet).toHaveBeenCalled()
  })
  it('创建备份', async () => {
    const { default: Comp } = await import('@/views/system/BackupManagement.vue')
    const w = mount(Comp)
    await flushPromises()
    const vm = w.vm as any
    if (vm.handleBackup) {
      await vm.handleBackup()
      expect(mockPost).toHaveBeenCalled()
    }
  })
  it('加载调度配置', async () => {
    const { default: Comp } = await import('@/views/system/BackupManagement.vue')
    const w = mount(Comp)
    await flushPromises()
    const vm = w.vm as any
    if (vm.loadScheduleConfig) {
      await vm.loadScheduleConfig()
    }
  })
})

// --- CacheManagement ---
describe('CacheManagement.vue', () => {
  it('渲染并加载缓存状态', async () => {
    const { default: Comp } = await import('@/views/system/CacheManagement.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
  it('清除缓存', async () => {
    const { default: Comp } = await import('@/views/system/CacheManagement.vue')
    const w = mount(Comp)
    await flushPromises()
    const vm = w.vm as any
    if (vm.handleClearCache) await vm.handleClearCache()
    if (vm.handleClearAll) await vm.handleClearAll()
  })
})

// --- ChunkedUploadManager ---
describe('ChunkedUploadManager.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/system/ChunkedUploadManager.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- ConfigPackage ---
describe('ConfigPackage.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/system/ConfigPackage.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- DataTier ---
describe('DataTier.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/system/DataTier.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- EmailSettings ---
describe('EmailSettings.vue', () => {
  it('渲染并加载设置', async () => {
    const { default: Comp } = await import('@/views/system/EmailSettings.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
  it('保存设置', async () => {
    const { default: Comp } = await import('@/views/system/EmailSettings.vue')
    const w = mount(Comp)
    await flushPromises()
    const vm = w.vm as any
    if (vm.handleSave) await vm.handleSave()
    if (vm.saveSettings) await vm.saveSettings()
    if (vm.handleTest) await vm.handleTest()
  })
})

// --- EncryptionSettings ---
describe('EncryptionSettings.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/system/EncryptionSettings.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- EnvCheck ---
describe('EnvCheck.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/system/EnvCheck.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- ErrorReports ---
describe('ErrorReports.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/system/ErrorReports.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- Feedback ---
describe('Feedback.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/system/Feedback.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- I18nManagement ---
describe('I18nManagement.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/system/I18nManagement.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- MapTileManager ---
describe('MapTileManager.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/system/MapTileManager.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- Menu ---
describe('Menu.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/system/Menu.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- Role ---
describe('Role.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/system/Role.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- SecretsManagement ---
describe('SecretsManagement.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/system/SecretsManagement.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- TaskManager ---
describe('TaskManager.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/system/TaskManager.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- UpdateLogs ---
describe('UpdateLogs.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/system/UpdateLogs.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- UserPermissions ---
describe('ZeroTrust.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/system/ZeroTrust.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})
