/**
 * AdminDashboard.vue 组件测试
 *
 * 覆盖目标：src/views/admin/AdminDashboard.vue 100% statements
 * 场景：
 * 1. 权限分支 - isAdmin true/false
 * 2. 数据加载 - 成功（完整数据/空数据/envelope 嵌套）/失败
 * 3. 模板渲染 - v-if 空态 / v-for 列表 / 各区块
 * 4. 交互 - 4 个横幅按钮 / 查看全部 / 快捷操作点击
 * 5. 工具函数 - formatSize 各量级分支 / storagePercent
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

// ==================== Mocks ====================

const mockPush = vi.fn(() => Promise.resolve())
const mockResolve = vi.fn(() => ({ name: 'SomeRoute', matched: [{ path: '/x' }] }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, resolve: mockResolve }),
  useRoute: () => ({ params: {}, query: {} }),
}))

const mockGet = vi.fn()
vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

const mockLoggerError = vi.fn()
vi.mock('@/utils/logger', () => ({
  logger: {
    error: (...args: any[]) => mockLoggerError(...args),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
    log: vi.fn(),
  },
}))

import AdminDashboard from '@/views/admin/AdminDashboard.vue'
import { useUserStore } from '@/stores/user'

// ==================== Helpers ====================

/** 完整的管理端统计数据（覆盖所有 v-for / 非空分支） */
const fullStats = {
  total_users: 42,
  total_population: 7,
  total_villages: 100,
  total_projects: 400,
  total_funds: 500,
  total_schools: 24,
  system_status: [
    { name: 'API服务', status: 'online', statusText: '正常' },
    { name: '数据库', status: 'offline', statusText: '异常' },
  ],
  recent_logins: [
    { id: 1, name: '张三', time: '2024-01-01 10:00', ip: '10.0.0.1' },
    { id: 2, name: '', time: '2024-01-01 11:00', ip: '10.0.0.2' },
  ],
  audit_logs: [
    { id: 1, type: 'info', action: '登录系统', user: 'admin', target: '系统', time: '10:00' },
    { id: 2, type: 'danger', action: '删除数据', user: 'admin', target: '项目', time: '11:00' },
  ],
  pending_items: [
    { id: 1, priority: 'high', type: '审批', description: '项目审批待处理', time: '1小时前' },
    { id: 2, priority: 'low', type: '告警', description: '存储空间告警', time: '2小时前' },
  ],
  storage: {
    used: 600 * 1024 * 1024,
    total: 1024 * 1024 * 1024,
    db: 100 * 1024 * 1024,
    backup: 300 * 1024 * 1024,
    log: 200 * 1024 * 1024,
  },
}

function setupPinia(role: string | null = 'admin') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const userStore = useUserStore(pinia)
  userStore.currentUser = role ? ({ id: 1, username: 'u', role } as any) : null
  return pinia
}

function mountDashboard(role: string | null = 'admin') {
  const pinia = setupPinia(role)
  return mount(AdminDashboard, {
    global: {
      plugins: [pinia],
      stubs: {
        // 让 el-icon 渲染插槽内的真实图标组件，覆盖 <component :is> 语句
        'el-icon': { template: '<i><slot/></i>' },
      },
    },
  })
}

// ==================== 测试 ====================

beforeEach(() => {
  vi.clearAllMocks()
  mockGet.mockResolvedValue({ data: fullStats })
})

describe('权限分支', () => {
  it('admin 角色渲染管理控制台', async () => {
    const wrapper = mountDashboard('admin')
    await flushPromises()

    expect(wrapper.find('.admin-dashboard').exists()).toBe(true)
    expect(wrapper.text()).toContain('管理控制台')
  })

  it('super_admin 角色同样有权限', async () => {
    const wrapper = mountDashboard('super_admin')
    await flushPromises()

    expect(wrapper.find('.admin-dashboard').exists()).toBe(true)
  })

  it('普通角色渲染无权限提示', async () => {
    const wrapper = mountDashboard('viewer')
    await flushPromises()

    expect(wrapper.find('.admin-dashboard').exists()).toBe(false)
  })

  it('未登录用户渲染无权限提示', async () => {
    const wrapper = mountDashboard(null)
    await flushPromises()

    expect(wrapper.find('.admin-dashboard').exists()).toBe(false)
  })
})

describe('数据加载', () => {
  it('加载成功：完整数据填充所有区块', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(mockGet).toHaveBeenCalledWith('/dashboard/stats')
    expect(vm.adminStats[0].value).toBe(42)
    expect(vm.adminStats[1].value).toBe(7)
    // 数据记录 = 帮扶村100 + 项目400 + 经费500 + 学校24
    expect(vm.adminStats[2].value).toBe(1024)
    expect(vm.adminStats[3].value).toBe('100 村 / 400 项目')
    expect(vm.systemStatus).toHaveLength(2)
    expect(vm.recentLogins).toHaveLength(2)
    expect(vm.auditLogs).toHaveLength(2)
    expect(vm.pendingItems).toHaveLength(2)
    expect(vm.storageUsed).toBe(600 * 1024 * 1024)

    // v-for 渲染内容
    expect(wrapper.text()).toContain('API服务')
    expect(wrapper.text()).toContain('张三')
    expect(wrapper.text()).toContain('登录系统')
    expect(wrapper.text()).toContain('项目审批待处理')
    // 待处理计数
    expect(wrapper.find('.pending-count').text()).toBe('2')
  })

  it('空数据：使用默认值并展示空态提示', async () => {
    mockGet.mockResolvedValue({ data: {} })
    const wrapper = mountDashboard()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.adminStats[0].value).toBe(0)
    expect(vm.adminStats[3].value).toBe('--')
    expect(vm.systemStatus).toHaveLength(0)
    expect(wrapper.text()).toContain('加载中...')
    expect(wrapper.text()).toContain('暂无登录记录')
    expect(wrapper.text()).toContain('暂无审计记录')
    expect(wrapper.text()).toContain('暂无待处理事项')
  })

  it('envelope 格式（拦截器展开后）也能解析', async () => {
    // get() 返回的是拦截器展开后的信封：code/message 保留，payload 字段提升到顶层
    mockGet.mockResolvedValue({ code: 200, data: { total_users: 88 }, message: '成功' })
    const wrapper = mountDashboard()
    await flushPromises()

    expect((wrapper.vm as any).adminStats[0].value).toBe(88)
  })

  it('裸 payload（无信封包装）也能解析', async () => {
    mockGet.mockResolvedValue({ total_users: 66, total_villages: 3, total_projects: 4 })
    const wrapper = mountDashboard()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.adminStats[0].value).toBe(66)
    expect(vm.adminStats[3].value).toBe('3 村 / 4 项目')
  })

  it('加载失败：记录日志且页面保持默认态', async () => {
    mockGet.mockRejectedValue(new Error('network error'))
    const wrapper = mountDashboard()
    await flushPromises()

    expect(mockLoggerError).toHaveBeenCalled()
    expect((wrapper.vm as any).systemStatus).toHaveLength(0)
  })

  it('登录记录 name 为空时头像回退为 U', async () => {
    mockGet.mockResolvedValue({
      data: { recent_logins: [{ id: 9, name: '', time: 't', ip: '1.1.1.1' }] },
    })
    const wrapper = mountDashboard()
    await flushPromises()

    expect(wrapper.find('.login-avatar').text()).toBe('U')
  })
})

describe('交互', () => {
  it('横幅四个操作按钮均触发 pushSafe', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    const buttons = wrapper.findAll('.admin-actions .action-btn')
    expect(buttons).toHaveLength(4)
    for (const btn of buttons) {
      await btn.trigger('click')
    }

    expect(mockPush).toHaveBeenCalledWith('/system/users-orgs')
    expect(mockPush).toHaveBeenCalledWith('/system/backup')
    expect(mockPush).toHaveBeenCalledWith('/system/audit')
    expect(mockPush).toHaveBeenCalledWith('/system/config')
  })

  it('审计日志"查看全部"按钮跳转', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    await wrapper.find('.text-btn').trigger('click')
    expect(mockPush).toHaveBeenCalledWith('/system/audit')
  })

  it('快捷操作点击跳转对应路径', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    const actions = wrapper.findAll('.quick-action')
    expect(actions).toHaveLength(6)
    for (const action of actions) {
      await action.trigger('click')
    }
    expect(mockPush).toHaveBeenCalledWith('/system/roles')
    expect(mockPush).toHaveBeenCalledWith('/data-management/overview')
  })
})

describe('工具函数', () => {
  it('formatSize 覆盖 B/KB/MB/GB 各分支', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.formatSize(512)).toBe('512 B')
    expect(vm.formatSize(2048)).toBe('2.0 KB')
    expect(vm.formatSize(5 * 1024 * 1024)).toBe('5.0 MB')
    expect(vm.formatSize(3 * 1024 * 1024 * 1024)).toBe('3.0 GB')
  })

  it('storagePercent 按 used/total 计算并渲染到宽度', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    const vm = wrapper.vm as any
    // 600MB / 1024MB ≈ 59%
    expect(vm.storagePercent).toBe(Math.round((600 / 1024) * 100))

    vm.storageUsed = 1
    vm.storageTotal = 4
    await nextTick()
    expect(vm.storagePercent).toBe(25)
  })
})

describe('loadAdminData 兜底分支补全', () => {
  it('storage 字段缺失 → used/total/db/backup/log 各级默认值', async () => {
    mockGet.mockResolvedValue({ data: { data: { storage: {} } } })
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.storageUsed).toBe(0)
    expect(vm.storageTotal).toBe(1) // || 1 防除零
    expect(vm.dbSize).toBe(0)
    expect(vm.backupSize).toBe(0)
    expect(vm.logSize).toBe(0)
  })

  it('total_projects 缺失 → ?? 0；storage 空对象 → || 兜底', async () => {
    mockGet.mockResolvedValue({ data: { total_villages: 5, storage: {} } })
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.adminStats[3].value).toBe('5 村 / 0 项目')
    expect(vm.storageUsed).toBe(0)
    expect(vm.storageTotal).toBe(1)
    expect(vm.dbSize).toBe(0)
    expect(vm.backupSize).toBe(0)
    expect(vm.logSize).toBe(0)
  })

  it('res.data 为 null → ?? res 兜底，统计归零', async () => {
    mockGet.mockResolvedValue({ data: null })
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.adminStats[0].value).toBe(0)
    expect(vm.adminStats[1].value).toBe(0)
    expect(vm.adminStats[2].value).toBe(0)
  })

  it('res 为 null（后端无数据返回 None）→ ?? {} 兜底，统计归零', async () => {
    mockGet.mockResolvedValue(null)
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.adminStats[0].value).toBe(0)
    expect(vm.adminStats[1].value).toBe(0)
    expect(vm.adminStats[2].value).toBe(0)
    expect(vm.adminStats[3].value).toBe('--')
  })
})
