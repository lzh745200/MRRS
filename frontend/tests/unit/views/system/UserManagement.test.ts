/**
 * views/system/UserManagement.vue 覆盖率攻坚
 * 覆盖：Tab 切换、组织树/角色加载三分支、字典映射函数、密码生成与复制、
 * 用户 CRUD 全路径、待审核用户、会话管理、2FA 重置、权限包导入导出、删除全分支，
 * 以及模板中 v-if/v-else（machine_code、is_active、isAdmin、activeTab、会话空态）两侧渲染。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂会被提升到模块顶部注册，直接引用下方 const 会触发 TDZ；
// 所有被工厂引用的对象放入 vi.hoisted 中先行初始化。
const {
  authState,
  ElMessage,
  confirmMock,
  alertMock,
  mockGet,
  mockPost,
  mockPut,
  mockDel,
  mockApiRequest,
  dsMock,
  logError,
  genPwdMock,
  normalizeMock,
  clipWrite,
  routeQuery,
  listPacksMock,
  promptMock,
  mockDownloadBlobAsFile,
  mockRequestGet,
} = vi.hoisted(() => {
  return {
    authState: { isAdmin: true },
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
    confirmMock: vi.fn(),
    alertMock: vi.fn(),
    promptMock: vi.fn(),
    mockGet: vi.fn(),
    mockPost: vi.fn(),
    mockPut: vi.fn(),
    mockDel: vi.fn(),
    mockApiRequest: vi.fn(),
    dsMock: vi.fn(),
    logError: vi.fn(),
    genPwdMock: vi.fn(),
    normalizeMock: vi.fn(),
    clipWrite: vi.fn(),
    routeQuery: { query: {} as Record<string, any> },
    listPacksMock: vi.fn(),
    // 忠实镜像真实 helper：downloadBlobAsFile 内部会 await requestFn()（blobDownload.ts:108），
    // 故 mock 也调用传入的取数 thunk，覆盖组件里 () => request.get(...) 的下载请求体。
    mockDownloadBlobAsFile: vi.fn(async (requestFn: any) => {
      if (typeof requestFn === 'function') await requestFn()
    }),
    mockRequestGet: vi.fn(),
  }
})

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock, alert: alertMock, prompt: promptMock },
}))

vi.mock('@/api/request', () => ({
  default: { get: mockRequestGet },
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: mockDel,
  apiRequest: mockApiRequest,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/api/permissionPack', () => ({
  listPermissionPacks: listPacksMock,
}))

// 权限包导出改走 downloadBlobAsFile（带 Authorization 拦截器的 axios 实例下载 blob），
// 不再手工创建 <a> 并 click。按 AGENTS.md 测试约定 #5，mock 该 helper 并断言其被调用，
// 而非 spy DOM anchor click（jsdom 下 createObjectURL/click 行为不可靠）。
vi.mock('@/api/helpers/blobDownload', () => ({
  downloadBlobAsFile: mockDownloadBlobAsFile,
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeQuery,
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

vi.mock('@/composables/useDesensitize', () => ({
  useDesensitize: () => ({ ds: dsMock }),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/utils/clipboard', () => ({
  generateRandomPassword: genPwdMock,
}))

vi.mock('@/utils/treeNormalizer', () => ({
  normalizeTreeNodes: normalizeMock,
}))

vi.mock('@/views/system/Role.vue', () => ({
  default: { name: 'RoleManagement', template: '<div class="role-management-mock" />' },
}))

vi.mock('@/components/permission/PermissionAssignmentDrawer.vue', () => ({
  default: {
    name: 'PermissionAssignmentDrawer',
    template: '<div class="perm-drawer-mock" />',
    emits: ['saved', 'update:modelValue'],
  },
}))

import UserManagement from '@/views/system/UserManagement.vue'

const sampleUser = {
  id: 1,
  username: 'admin',
  full_name: '管理员',
  role: 'admin',
  data_scope: 'all',
  department: '信息科',
  phone: '13800000000',
  email: 'a@b.c',
  is_active: true,
  organization_id: 3,
  organization_name: '总部',
}

const menuTreeSample = [
  { key: 'a', label: '菜单A' },
  { key: 'b', label: '菜单B', children: [{ key: 'b1', label: '子B1' }] },
]

function defaultGetImpl(url: string) {
  if (url === '/organizations/tree') {
    return Promise.resolve({ data: [{ id: 1, name: '总部', children: [] }] })
  }
  if (url === '/users/pending/list') {
    return Promise.resolve({ data: [{ id: 9, username: 'pending1' }] })
  }
  if (url === '/rbac/roles') {
    return Promise.resolve({ data: { items: [{ id: 'custom', name: '自定义角色' }] } })
  }
  if (url.includes('/sessions')) {
    return Promise.resolve({
      data: {
        data: [
          { session_id: 's1', ip_address: '1.1.1.1', user_agent: 'Chrome', created_at: '2024-01-01T10:00:00' },
        ],
      },
    })
  }
  return Promise.resolve({ data: {} })
}

function mountComp(extraStubs: Record<string, any> = {}) {
  // setup.ts 的全局 el-* stub 默认不渲染插槽，需 renderStubDefaultSlot；
  // 具名插槽（header/footer/dropdown/append）与作用域插槽（表格行）需自定义 stub。
  return mount(UserManagement, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
        },
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue'],
        },
        'el-dropdown': {
          name: 'ElDropdown',
          template: '<div class="el-dropdown-stub"><slot /><slot name="dropdown" /></div>',
        },
        'el-input': {
          name: 'ElInput',
          template: '<div class="el-input-stub"><slot /><slot name="append" /></div>',
          emits: ['update:modelValue'],
        },
        // 注入两行样本数据，覆盖 machine_code 有/无、is_active 真/假、organization_name 空值等模板两侧分支
        'el-table-column': {
          name: 'ElTableColumn',
          template: '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>',
          data() {
            return {
              rowA: {
                id: 1,
                permission_pack_id: 1,
                username: 'admin',
                full_name: '张三',
                role: 'admin',
                data_scope: 'all',
                organization_name: '总部',
                department: '信息科',
                phone: '13800000000',
                machine_code: 'MC-001',
                last_login: '2024-01-01',
                is_active: true,
                session_id: 's1',
                ip_address: '1.1.1.1',
                user_agent: 'Chrome',
                created_at: '2024-01-01T10:00:00',
              },
              rowB: {
                id: 2,
                permission_pack_id: 999,
                username: 'op',
                full_name: '李四',
                role: 'viewer',
                data_scope: 'self',
                organization_name: '',
                department: '',
                phone: '',
                machine_code: '',
                last_login: '',
                is_active: false,
                session_id: 's2',
                ip_address: '2.2.2.2',
                user_agent: 'Firefox',
                created_at: null,
              },
              rowC: {
                id: 3,
                username: 'u3',
                full_name: '王五',
                role: 'user',
                data_scope: 'self',
                organization_name: '',
                department: '',
                phone: '',
                machine_code: '',
                last_login: '',
                is_active: true,
                session_id: 's3',
                ip_address: '3.3.3.3',
                user_agent: 'Safari',
                created_at: null,
              },
            }
          },
        },
        ...extraStubs,
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  authState.isAdmin = true
  mockGet.mockImplementation(defaultGetImpl)
  listPacksMock.mockResolvedValue([{ id: 1, name: '基础包' }])
  mockApiRequest.mockResolvedValue({ items: [sampleUser], total: 1 })
  mockPost.mockResolvedValue({ data: {} })
  mockPut.mockResolvedValue({ data: {} })
  mockDel.mockResolvedValue({ data: {} })
  confirmMock.mockResolvedValue(undefined)
  alertMock.mockResolvedValue(undefined)
  promptMock.mockResolvedValue({ value: 'pw' })
  clipWrite.mockResolvedValue(undefined)
  genPwdMock.mockReturnValue('Gen#Pass1')
  normalizeMock.mockImplementation((nodes: any) => nodes)
  dsMock.mockImplementation((v: any) => v)
  Object.defineProperty(window.navigator, 'clipboard', {
    value: { writeText: clipWrite },
    configurable: true,
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与初始化', () => {
  it('onMounted 并行加载用户/组织树/待审核数（角色选项固定不请求）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'GET', url: '/users' })
    )
    expect(vm.tableData).toHaveLength(1)
    expect(vm.pagination.total).toBe(1)
    expect(mockGet).toHaveBeenCalledWith('/organizations/tree')
    expect(normalizeMock).toHaveBeenCalled()
    expect(vm.orgTreeOptions).toHaveLength(1)
    expect(mockGet).toHaveBeenCalledWith('/users/pending/list')
    expect(vm.pendingCount).toBe(1) // 数组 → length
    // 角色选项固定为 users.role 体系 4 个角色，不再请求 /rbac/roles
    expect(mockGet).not.toHaveBeenCalledWith('/rbac/roles', expect.anything())
    expect(vm.roleOptions).toEqual([
      { value: 'super_admin', label: '超级管理员' },
      { value: 'admin', label: '系统管理员' },
      { value: 'user', label: '普通用户' },
      { value: 'viewer', label: '访客' },
    ])
  })

  it('loadOrgTree：返回非数组 → 置空', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/organizations/tree') return Promise.resolve({ data: { not: 'array' } })
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).orgTreeOptions).toEqual([])
  })

  it('loadOrgTree：请求异常 → 置空', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/organizations/tree') return Promise.reject(new Error('net'))
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).orgTreeOptions).toEqual([])
  })

  it('loadOrgTree：falsy 原始值（0）→ 走 || [] 兜底', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/organizations/tree') return Promise.resolve(0)
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).orgTreeOptions).toEqual([])
  })

  it('roleOptions：固定 users.role 体系 4 角色，不再请求 /rbac/roles 覆盖', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // fetchRoles 死函数已移除: roleOptions 为静态数组, 角色体系固定
    expect(mockGet).not.toHaveBeenCalledWith('/rbac/roles', expect.anything())
    expect(vm.roleOptions).toEqual([
      { value: 'super_admin', label: '超级管理员' },
      { value: 'admin', label: '系统管理员' },
      { value: 'user', label: '普通用户' },
      { value: 'viewer', label: '访客' },
    ])
  })

  it('loadData：响应缺 total → 以 items 长度兜底', async () => {
    mockApiRequest.mockResolvedValue({ items: [sampleUser, { ...sampleUser, id: 2 }] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.tableData).toHaveLength(2)
    expect(vm.pagination.total).toBe(2)
  })

  it('loadData：请求失败 → 记录日志并提示', async () => {
    mockApiRequest.mockRejectedValue(new Error('boom'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('加载用户数据失败')
    expect(vm.loading).toBe(false)
  })
})

describe('Tab 切换与角色管理面板', () => {
  it('切换到 roles 页签渲染 RoleManagement，users 搜索卡消失', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(wrapper.find('.role-management-mock').exists()).toBe(false)
    vm.handleTabChange('roles')
    vm.activeTab = 'roles'
    await nextTick()
    expect(wrapper.find('.role-management-mock').exists()).toBe(true)
    expect(wrapper.find('.search-card').exists()).toBe(false)
  })
})

describe('待审核用户', () => {
  it('非管理员：loadPendingCount 直接返回，不请求', async () => {
    authState.isAdmin = false
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGet.mock.calls.some((c) => c[0] === '/users/pending/list')).toBe(false)
    expect(vm.pendingCount).toBe(0)
  })

  it('管理员：对象响应 → 取 data.total', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/users/pending/list') return Promise.resolve({ data: { total: 5 } })
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).pendingCount).toBe(5)
  })

  it('请求异常 → pendingCount 归零', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/users/pending/list') return Promise.reject(new Error('net'))
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).pendingCount).toBe(0)
  })

  it('showPendingUsers：数组响应 → 填充列表并打开弹窗', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.showPendingUsers()
    expect(vm.pendingUsers).toHaveLength(1)
    expect(vm.pendingCount).toBe(1)
    expect(vm.pendingDialogVisible).toBe(true)
  })

  it('showPendingUsers：对象响应 → 取 data.items', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/users/pending/list') {
        return Promise.resolve({ data: { items: [{ id: 8 }, { id: 9 }] } })
      }
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.showPendingUsers()
    expect(vm.pendingUsers).toHaveLength(2)
    expect(vm.pendingCount).toBe(2)
  })

  it('showPendingUsers：异常 → 错误提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockImplementation((url: string) => {
      if (url === '/users/pending/list') return Promise.reject(new Error('net'))
      return defaultGetImpl(url)
    })
    await vm.showPendingUsers()
    expect(ElMessage.error).toHaveBeenCalledWith('加载待审核用户失败')
  })
})

describe('搜索 / 重置 / 分页', () => {
  it('handleSearch 携带查询参数并回到第 1 页', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchForm.username = 'u1'
    vm.searchForm.name = 'n1'
    vm.searchForm.role = 'admin'
    vm.searchForm.is_active = true
    vm.pagination.page = 3
    mockApiRequest.mockClear()
    vm.handleSearch()
    await flushPromises()
    expect(vm.pagination.page).toBe(1)
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'GET',
      url: '/users',
      params: { page: 1, page_size: 10, username: 'u1', keyword: 'n1', role: 'admin', is_active: true },
    })
  })

  it('handleReset 清空搜索条件并重新查询', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchForm.username = 'u1'
    vm.searchForm.name = 'n1'
    vm.searchForm.role = 'admin'
    vm.searchForm.is_active = false
    mockApiRequest.mockClear()
    vm.handleReset()
    await flushPromises()
    expect(vm.searchForm).toEqual({ username: '', name: '', role: '', is_active: undefined })
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        params: expect.objectContaining({ username: undefined, keyword: undefined, role: undefined }),
      })
    )
  })

  it('handleSizeChange 回第 1 页并刷新；handlePageChange 刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockApiRequest.mockClear()
    vm.pagination.page = 4
    vm.handleSizeChange()
    await flushPromises()
    expect(vm.pagination.page).toBe(1)
    expect(mockApiRequest).toHaveBeenCalledTimes(1)
    vm.handlePageChange()
    await flushPromises()
    expect(mockApiRequest).toHaveBeenCalledTimes(2)
  })
})

describe('字典映射函数', () => {
  it('getRoleTagType 全映射与未知兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getRoleTagType('super_admin')).toBe('danger')
    expect(vm.getRoleTagType('admin')).toBe('danger')
    expect(vm.getRoleTagType('approval_leader')).toBe('warning')
    expect(vm.getRoleTagType('manager')).toBe('warning')
    expect(vm.getRoleTagType('operator')).toBe('success')
    expect(vm.getRoleTagType('viewer')).toBe('info')
    expect(vm.getRoleTagType('whatever')).toBe('info')
  })

  it('getRoleName 全映射与未知透传', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getRoleName('super_admin')).toBe('超级管理员')
    expect(vm.getRoleName('admin')).toBe('系统管理员')
    expect(vm.getRoleName('approval_leader')).toBe('审批领导')
    expect(vm.getRoleName('manager')).toBe('管理人员')
    expect(vm.getRoleName('operator')).toBe('操作员')
    expect(vm.getRoleName('user')).toBe('普通用户')
    expect(vm.getRoleName('viewer')).toBe('访客')
    expect(vm.getRoleName('custom_role')).toBe('custom_role')
  })

  it('getDataScopeName 全映射、未知透传与空值兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getDataScopeName('all')).toBe('全部')
    expect(vm.getDataScopeName('org_children')).toBe('本组织及下级')
    expect(vm.getDataScopeName('org')).toBe('仅本组织')
    expect(vm.getDataScopeName('self')).toBe('仅自己')
    expect(vm.getDataScopeName('other')).toBe('other')
    expect(vm.getDataScopeName('')).toBe('-')
  })
})

describe('密码生成与复制', () => {
  it('generatePassword / generateResetPassword 调用生成器', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.generatePassword()
    expect(vm.formData.password).toBe('Gen#Pass1')
    vm.generateResetPassword()
    expect(vm.resetPwdForm.newPassword).toBe('Gen#Pass1')
    await nextTick() // 触发“生成的密码”v-if 区块渲染
  })

  it('copyPassword 成功 → 成功提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.resetPwdForm.newPassword = 'abc123'
    await vm.copyPassword()
    expect(clipWrite).toHaveBeenCalledWith('abc123')
    expect(ElMessage.success).toHaveBeenCalledWith('密码已复制到剪贴板')
  })

  it('copyPassword 剪贴板失败 → 错误提示', async () => {
    clipWrite.mockRejectedValue(new Error('denied'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.resetPwdForm.newPassword = 'abc123'
    await vm.copyPassword()
    expect(ElMessage.error).toHaveBeenCalledWith('复制失败，请手动复制')
  })
})

describe('新增 / 编辑 / 提交', () => {
  it('handleAdd 重置表单并打开弹窗', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.isEdit = true
    vm.formData.username = 'dirty'
    vm.handleAdd()
    expect(vm.isEdit).toBe(false)
    expect(vm.dialogTitle).toBe('新增用户')
    expect(vm.dialogVisible).toBe(true)
    expect(vm.formData).toMatchObject({
      id: 0,
      username: '',
      role: 'user',
      data_scope: 'org',
      is_active: true,
      organization_id: null,
      permissions: [],
    })
  })

  it('handleEdit 填充表单并加载会话（organization_id 缺省 → null）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const row = { ...sampleUser }
    delete (row as any).organization_id
    vm.handleEdit(row)
    await flushPromises()
    expect(vm.isEdit).toBe(true)
    expect(vm.dialogTitle).toBe('编辑用户')
    expect(vm.currentUser).toEqual(row)
    expect(vm.formData.username).toBe('admin')
    expect(vm.formData.organization_id).toBeNull()
    expect(mockGet).toHaveBeenCalledWith('/system/admin/users/1/sessions')
    expect(vm.userSessions).toHaveLength(1)
    await nextTick() // 渲染会话表格（userSessions.length > 0 分支）
  })

  it('handleEdit 保留已有 organization_id', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleEdit({ ...sampleUser, organization_id: 42 })
    expect(vm.formData.organization_id).toBe(42)
  })

  it('handleSubmit：formRef 为空 → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formRef = undefined
    await vm.handleSubmit()
    expect(mockPost).not.toHaveBeenCalled()
    expect(mockPut).not.toHaveBeenCalled()
  })

  it('handleSubmit：校验未通过 → 不发请求', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formRef = { validate: (cb: any) => cb(false) }
    await vm.handleSubmit()
    await flushPromises()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('handleSubmit 新建：返回初始密码 → 密码提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleAdd()
    vm.formData.username = 'newbie'
    vm.formData.full_name = '新人'
    vm.formData.permissions = ['data:view', 'data:edit']
    vm.formRef = { validate: (cb: any) => cb(true) }
    mockPost.mockResolvedValueOnce({ data: { data: { password: 'Init!234' } } })
    mockApiRequest.mockClear()
    await vm.handleSubmit()
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith(
      '/users',
      expect.objectContaining({
        username: 'newbie',
        password: undefined,
        permissions: 'data:view,data:edit',
      })
    )
    expect(ElMessage.success).toHaveBeenCalledWith(expect.stringContaining('初始密码: Init!234'))
    expect(vm.dialogVisible).toBe(false)
    expect(mockApiRequest).toHaveBeenCalled() // 提交后刷新列表
    expect(vm.submitting).toBe(false)
  })

  it('handleSubmit 新建：无初始密码 → 普通成功提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleAdd()
    vm.formRef = { validate: (cb: any) => cb(true) }
    mockPost.mockResolvedValueOnce({ data: { data: {} } })
    await vm.handleSubmit()
    await flushPromises()
    expect(ElMessage.success).toHaveBeenCalledWith('用户创建成功')
  })

  it('handleSubmit 编辑：走 PUT 并提示更新成功', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleEdit({ ...sampleUser })
    vm.formRef = { validate: (cb: any) => cb(true) }
    await vm.handleSubmit()
    await flushPromises()
    expect(mockPut).toHaveBeenCalledWith(
      '/users/1',
      expect.objectContaining({ full_name: '管理员', role: 'admin', organization_id: 3 })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('用户更新成功')
  })

  it('handleSubmit 失败：展示后端 detail', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleAdd()
    vm.formRef = { validate: (cb: any) => cb(true) }
    mockPost.mockRejectedValueOnce({ response: { data: { detail: '用户名已存在' } } })
    await vm.handleSubmit()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('用户名已存在')
    expect(vm.submitting).toBe(false)
  })

  it('handleSubmit 失败：无 detail → 兜底文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleAdd()
    vm.formRef = { validate: (cb: any) => cb(true) }
    mockPost.mockRejectedValueOnce(new Error('net'))
    await vm.handleSubmit()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('操作失败')
  })
})

describe('重置密码', () => {
  it('handleResetPassword 打开弹窗并清空密码', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.resetPwdForm.newPassword = 'dirty'
    vm.handleResetPassword(sampleUser)
    expect(vm.currentUser).toEqual(sampleUser)
    expect(vm.resetPwdForm.newPassword).toBe('')
    expect(vm.resetPwdDialogVisible).toBe(true)
  })

  it('confirmResetPassword：空密码 → 警告并返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleResetPassword(sampleUser)
    await vm.confirmResetPassword()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入或生成新密码')
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('confirmResetPassword 成功：复制密码 + 弹窗提示 + 状态复位', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleResetPassword(sampleUser)
    vm.resetPwdForm.newPassword = 'New!2345'
    await vm.confirmResetPassword()
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith('/users/1/admin-reset-password', {
      new_password: 'New!2345',
    })
    expect(clipWrite).toHaveBeenCalledWith('New!2345')
    expect(alertMock).toHaveBeenCalledWith(
      expect.stringContaining('New!2345'),
      expect.stringContaining('admin'),
      expect.objectContaining({ type: 'success' })
    )
    expect(vm.resetPwdDialogVisible).toBe(false)
    expect(vm.resetPwdForm.newPassword).toBe('')
  })

  it('confirmResetPassword：剪贴板失败仍走完整流程（内层 catch）', async () => {
    clipWrite.mockRejectedValue(new Error('denied'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleResetPassword(sampleUser)
    vm.resetPwdForm.newPassword = 'New!2345'
    await vm.confirmResetPassword()
    expect(alertMock).toHaveBeenCalled()
    expect(vm.resetPwdDialogVisible).toBe(false)
  })

  it('confirmResetPassword 失败：detail 与兜底文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleResetPassword(sampleUser)
    vm.resetPwdForm.newPassword = 'New!2345'
    mockPost.mockRejectedValueOnce({ response: { data: { detail: '密码强度不足' } } })
    await vm.confirmResetPassword()
    expect(ElMessage.error).toHaveBeenCalledWith('密码强度不足')
    mockPost.mockRejectedValueOnce(new Error('net'))
    vm.resetPwdForm.newPassword = 'New!2345'
    await vm.confirmResetPassword()
    expect(ElMessage.error).toHaveBeenCalledWith('重置密码失败')
  })
})

describe('角色/权限抽屉', () => {
  it('handleRolePermission 打开抽屉；handlePermSaved 刷新列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleRolePermission(sampleUser)
    expect(vm.permDrawerUser).toEqual(sampleUser)
    expect(vm.permDrawerVisible).toBe(true)
    mockApiRequest.mockClear()
    await vm.handlePermSaved()
    expect(vm.pagination.page).toBe(1)
    expect(mockApiRequest).toHaveBeenCalled()
  })
})

describe('会话管理', () => {
  it('loadUserSessions：res.data 为数组 / data.sessions / 原始数组 三种形态', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockResolvedValueOnce({ data: [{ session_id: 'a' }] })
    await vm.loadUserSessions(1)
    expect(vm.userSessions).toEqual([{ session_id: 'a' }])
    mockGet.mockResolvedValueOnce({ data: { sessions: [{ session_id: 'b' }] } })
    await vm.loadUserSessions(1)
    expect(vm.userSessions).toEqual([{ session_id: 'b' }])
    mockGet.mockResolvedValueOnce([{ session_id: 'c' }])
    await vm.loadUserSessions(1)
    expect(vm.userSessions).toEqual([{ session_id: 'c' }])
  })

  it('loadUserSessions：异常 → 空列表 + 错误提示；空态渲染（el-empty 分支）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/sessions')) return Promise.reject(new Error('404'))
      return defaultGetImpl(url)
    })
    vm.handleEdit({ ...sampleUser })
    await flushPromises()
    expect(vm.userSessions).toEqual([])
    expect(vm.sessionsLoading).toBe(false)
    expect(ElMessage.error).toHaveBeenCalled()
    await nextTick() // 渲染“无活跃会话”空态
  })

  it('loadUserSessions：错误带 detail / 异常为 null → 文案两侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/sessions')) {
        return Promise.reject({ response: { data: { detail: '会话服务异常' } } })
      }
      return defaultGetImpl(url)
    })
    vm.handleEdit({ ...sampleUser })
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('会话服务异常')
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/sessions')) return Promise.reject(null)
      return defaultGetImpl(url)
    })
    ElMessage.error.mockClear()
    vm.handleEdit({ ...sampleUser })
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('会话信息加载失败，请检查后端服务')
    expect(vm.userSessions).toEqual([])
  })

  it('revokeSession：currentUser 为空 → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.revokeSession({ session_id: 'x' })
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('revokeSession 成功 → 列表过滤该会话', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleEdit({ ...sampleUser })
    await flushPromises()
    expect(vm.userSessions).toHaveLength(1)
    await vm.revokeSession({ session_id: 's1' })
    expect(mockPost).toHaveBeenCalledWith('/system/admin/users/1/sessions/s1/revoke')
    expect(ElMessage.success).toHaveBeenCalledWith('已强制登出该会话')
    expect(vm.userSessions).toEqual([])
    expect(vm.revokingSession).toBeNull()
  })

  it('revokeSession 失败：detail 与兜底文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleEdit({ ...sampleUser })
    await flushPromises()
    mockPost.mockRejectedValueOnce({ response: { data: { detail: '会话不存在' } } })
    await vm.revokeSession({ session_id: 's1' })
    expect(ElMessage.error).toHaveBeenCalledWith('会话不存在')
    mockPost.mockRejectedValueOnce(new Error('net'))
    await vm.revokeSession({ session_id: 's1' })
    expect(ElMessage.error).toHaveBeenCalledWith('强制登出失败，接口可能尚未实现')
    expect(vm.revokingSession).toBeNull()
  })

  it('handleReset2fa：currentUser 为空 → 返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleReset2fa()
    expect(confirmMock).not.toHaveBeenCalled()
  })

  it('handleReset2fa：用户取消确认 → 不发请求', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentUser = { ...sampleUser }
    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleReset2fa()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('handleReset2fa 成功与失败两分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentUser = { ...sampleUser }
    await vm.handleReset2fa()
    expect(mockPost).toHaveBeenCalledWith('/system/admin/users/1/two-factor/reset')
    expect(ElMessage.success).toHaveBeenCalledWith('2FA 已重置')
    expect(vm.resetting2fa).toBe(false)
    mockPost.mockRejectedValueOnce({ response: { data: { detail: '未开启2FA' } } })
    await vm.handleReset2fa()
    expect(ElMessage.error).toHaveBeenCalledWith('未开启2FA')
    mockPost.mockRejectedValueOnce(new Error('net'))
    await vm.handleReset2fa()
    expect(ElMessage.error).toHaveBeenCalledWith('重置 2FA 失败，接口可能尚未实现')
  })

  it('formatSessionTime：空值 / 正常时间 / 异常输入', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatSessionTime(null)).toBe('-')
    expect(vm.formatSessionTime('2024-01-01T10:00:00')).not.toBe('-')
    expect(vm.formatSessionTime(Symbol('bad'))).toBe('-')
  })
})

describe('权限包导入导出', () => {
  it('handlePermPackageCommand 分发 export / import / 其他', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handlePermPackageCommand('export')
    await flushPromises()
    // P1：导出先打开角色选择对话框，不再立即发起导出请求
    expect(vm.permExportDialogVisible).toBe(true)
    expect(mockGet).toHaveBeenCalledWith('/rbac/roles', { limit: 200 })
    vm.handlePermPackageCommand('import')
    vm.handlePermPackageCommand('unknown') // 无分支 → 不报错
  })
  it('导出对话框：/rbac/roles 失败 → 不阻断，可全量导出（覆盖 catch 置空分支）', async () => {
    const wrapper3 = mountComp()
    await flushPromises()
    const vm3 = wrapper3.vm as any
    mockGet.mockRejectedValueOnce(new Error('roles down'))
    vm3.handlePermPackageCommand('export')
    await flushPromises()
    expect(vm3.permExportDialogVisible).toBe(true)
    expect(vm3.permExportRoleOptions).toEqual([])
    expect(vm3.permRolesLoading).toBe(false)
  })


  it('导出成功：走 downloadBlobAsFile 触发下载并提示统计', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockResolvedValueOnce({ data: { data: [] } })
    await vm.openPermExportDialog()
    mockPost.mockResolvedValueOnce({
      data: { file_name: 'pkg.zip', role_count: 2, user_count: 3 },
    })
    await vm.doExportPermissionPackage()
    expect(mockDownloadBlobAsFile).toHaveBeenCalledWith(expect.any(Function), {
      fallbackFileName: 'pkg.zip',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('权限包导出成功 (2 个角色, 3 个用户)')
    expect(vm.exportingPermPackage).toBe(false)
    expect(vm.permExportDialogVisible).toBe(false)
  })

  it('导出：勾选角色时携带 role_names；无 file_name 不下载；失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockResolvedValueOnce({
      data: { data: [{ name: 'village_officer' }, { name: 'auditor' }] },
    })
    await vm.openPermExportDialog()
    vm.permExportRoleNames = ['village_officer']
    mockPost.mockResolvedValueOnce({ data: {} }) // 无 file_name → 不下载
    await vm.doExportPermissionPackage()
    expect(mockDownloadBlobAsFile).not.toHaveBeenCalled()

    // 带选择导出：body 应包含 role_names
    mockDownloadBlobAsFile.mockClear()
    mockPost.mockResolvedValueOnce({
      data: { file_name: 'partial.zip', role_count: 1, user_count: 1 },
    })
    await vm.doExportPermissionPackage()
    expect(mockPost).toHaveBeenLastCalledWith('/permission-packages/export', {
      role_names: ['village_officer'],
    })
    expect(mockDownloadBlobAsFile).toHaveBeenCalledWith(expect.any(Function), {
      fallbackFileName: 'partial.zip',
    })

    // 失败 → detail 与兜底
    mockPost.mockRejectedValueOnce({ response: { data: { detail: '无权限' } } })
    await vm.doExportPermissionPackage()
    expect(ElMessage.error).toHaveBeenCalledWith('无权限')
    // 抛出普通 Error 时透出真实 message（不再是笼统“导出失败”）
    mockPost.mockRejectedValueOnce(new Error('net'))
    await vm.doExportPermissionPackage()
    expect(ElMessage.error).toHaveBeenCalledWith('net')
    // 无任何可提取信息时才回退通用文案
    mockPost.mockRejectedValueOnce({})
    await vm.doExportPermissionPackage()
    expect(ElMessage.error).toHaveBeenCalledWith('导出失败')
  })

  /** 捕获组件创建的 file input 元素 */
  function captureInputs() {
    const inputs: HTMLInputElement[] = []
    const orig = document.createElement.bind(document)
    const spy = vi.spyOn(document, 'createElement').mockImplementation((tag: any, opts?: any) => {
      const el = orig(tag, opts)
      if (String(tag).toLowerCase() === 'input') inputs.push(el as HTMLInputElement)
      return el
    })
    return { inputs, spy }
  }

  it('导入：window focus 触发清理（用户取消文件选择）', async () => {
    const { inputs, spy } = captureInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleImportPermissionPackage()
    expect(inputs).toHaveLength(1)
    window.dispatchEvent(new Event('focus'))
    expect(vm.importingPermPackage).toBe(false)
    expect(mockPost.mock.calls.some((c) => c[0] === '/permission-packages/import')).toBe(false)
    spy.mockRestore()
  })

  it('导入：change 事件无文件 → 清理并返回', async () => {
    const { inputs, spy } = captureInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleImportPermissionPackage()
    const input = inputs[0]
    Object.defineProperty(input, 'files', { value: [], configurable: true })
    input.dispatchEvent(new Event('change'))
    await flushPromises()
    expect(mockPost.mock.calls.some((c) => c[0] === '/permission-packages/import')).toBe(false)
    expect(vm.importingPermPackage).toBe(false)
    spy.mockRestore()
  })

  it('导入成功：含警告的预览 → 确认 → confirm 接口 → 刷新列表', async () => {
    const { inputs, spy } = captureInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockPost.mockImplementation((url: string) => {
      if (url === '/permission-packages/import') {
        return Promise.resolve({
          data: {
            success: true,
            preview: { role_count: 2, user_legacy_count: 3, warnings: ['角色X已存在'] },
          },
        })
      }
      if (url.startsWith('/permission-packages/confirm/')) {
        return Promise.resolve({ data: { message: '导入完成，共 2 角色' } })
      }
      return Promise.resolve({ data: {} })
    })
    vm.handleImportPermissionPackage()
    const input = inputs[0]
    const file = new File(['zip'], '我的权限包.zip', { type: 'application/zip' })
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    input.dispatchEvent(new Event('change'))
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('警告: 角色X已存在'),
      '选择导入模式',
      expect.objectContaining({ confirmButtonText: '合并导入' })
    )
    expect(mockPost).toHaveBeenCalledWith(
      `/permission-packages/confirm/${encodeURIComponent('我的权限包.zip')}`,
      { overwrite_existing: false, mode: 'merge' }
    )
    expect(ElMessage.success).toHaveBeenCalledWith('导入完成，共 2 角色')
    expect(vm.importingPermPackage).toBe(false)
    spy.mockRestore()
  })

  it('导入：preview 缺省 + confirm 响应兜底文案', async () => {
    const { inputs, spy } = captureInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockPost.mockImplementation((url: string) => {
      if (url === '/permission-packages/import') {
        return Promise.resolve({ data: { success: true } })
      }
      if (url.startsWith('/permission-packages/confirm/')) return Promise.resolve({})
      return Promise.resolve({ data: {} })
    })
    vm.handleImportPermissionPackage()
    const file = new File(['zip'], 'p.zip')
    Object.defineProperty(inputs[0], 'files', { value: [file], configurable: true })
    inputs[0].dispatchEvent(new Event('change'))
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('将导入 0 个角色, 0 个用户权限'),
      '选择导入模式',
      expect.any(Object)
    )
    expect(ElMessage.success).toHaveBeenCalledWith('导入完成')
    spy.mockRestore()
  })

  it('导入：success=false → 展示失败原因（含 message 兜底）', async () => {
    const { inputs, spy } = captureInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockPost.mockImplementation((url: string) => {
      if (url === '/permission-packages/import') {
        return Promise.resolve({ data: { success: false, message: '文件损坏' } })
      }
      return Promise.resolve({ data: {} })
    })
    vm.handleImportPermissionPackage()
    const file = new File(['zip'], 'bad.zip')
    Object.defineProperty(inputs[0], 'files', { value: [file], configurable: true })
    inputs[0].dispatchEvent(new Event('change'))
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('文件损坏')
    spy.mockRestore()
  })

  it('导入：确认框取消 → 静默返回；导入接口异常 → 错误提示', async () => {
    const { inputs, spy } = captureInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 第一次：confirm 关闭（'close'）→ 放弃导入，静默返回
    mockPost.mockImplementation((url: string) => {
      if (url === '/permission-packages/import') {
        return Promise.resolve({ data: { success: true, preview: {} } })
      }
      return Promise.resolve({ data: {} })
    })
    confirmMock.mockRejectedValueOnce('close')
    vm.handleImportPermissionPackage()
    const file = new File(['zip'], 'p.zip')
    Object.defineProperty(inputs[0], 'files', { value: [file], configurable: true })
    inputs[0].dispatchEvent(new Event('change'))
    await flushPromises()
    expect(ElMessage.error).not.toHaveBeenCalled()
    // 第二次：import 接口抛 detail
    mockPost.mockImplementation((url: string) => {
      if (url === '/permission-packages/import') {
        return Promise.reject({ response: { data: { detail: '格式不支持' } } })
      }
      return Promise.resolve({ data: {} })
    })
    vm.handleImportPermissionPackage()
    Object.defineProperty(inputs[1], 'files', { value: [file], configurable: true })
    inputs[1].dispatchEvent(new Event('change'))
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('格式不支持')
    // 第三次：非 cancel 普通错误 → err.message 兜底
    mockPost.mockImplementation((url: string) => {
      if (url === '/permission-packages/import') return Promise.reject(new Error('网络中断'))
      return Promise.resolve({ data: {} })
    })
    vm.handleImportPermissionPackage()
    Object.defineProperty(inputs[2], 'files', { value: [file], configurable: true })
    inputs[2].dispatchEvent(new Event('change'))
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('网络中断')
    spy.mockRestore()
  })
})

describe('删除用户', () => {
  it('确认删除 → 调用接口并刷新，关闭待审核弹窗', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.pendingDialogVisible = true
    mockApiRequest.mockClear()
    await vm.handleDelete(sampleUser)
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('管理员'),
      '提示',
      expect.objectContaining({ type: 'warning' })
    )
    expect(mockDel).toHaveBeenCalledWith('/users/1')
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    expect(mockApiRequest).toHaveBeenCalled()
    expect(vm.pendingDialogVisible).toBe(false)
  })

  it('取消删除 → 不请求不报错', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleDelete(sampleUser)
    expect(mockDel).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('删除失败：detail 与兜底文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockDel.mockRejectedValueOnce({ response: { data: { detail: '存在关联数据' } } })
    await vm.handleDelete(sampleUser)
    expect(ElMessage.error).toHaveBeenCalledWith('存在关联数据')
    mockDel.mockRejectedValueOnce(new Error('net'))
    await vm.handleDelete({ ...sampleUser, full_name: '' })
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })
})

describe('模板条件渲染（非管理员视角）', () => {
  it('非管理员：不渲染操作列与头部动作区', async () => {
    authState.isAdmin = false
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isAdmin).toBe(false)
    await nextTick()
    // 非管理员分支渲染不崩溃即可（v-if false 路径）
    expect(wrapper.find('.user-management').exists()).toBe(true)
  })
})


describe('模板 v-model 处理器（函数覆盖）', () => {
  it('全部 v-model 组件触发 update 事件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 输入框（搜索区 + 表单 + 重置密码对话框）——逐个触发 v-model 更新
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    expect(inputs.length).toBeGreaterThan(0)
    for (const c of inputs) c.vm.$emit('update:modelValue', 'x')
    expect(vm.searchForm.username).toBe('x')
    expect(vm.formData.username).toBe('x')
    expect(vm.resetPwdForm.newPassword).toBe('x')

    // 下拉选择（搜索角色/状态 + 表单角色/数据范围/权限）
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(selects.length).toBeGreaterThan(0)
    for (const c of selects) c.vm.$emit('update:modelValue', 'admin')

    // 组织树选择 / 开关
    const trees = wrapper.findAllComponents({ name: 'ElTreeSelect' })
    for (const c of trees) c.vm.$emit('update:modelValue', 7)
    expect(vm.formData.organization_id).toBe(7)
    const switches = wrapper.findAllComponents({ name: 'ElSwitch' })
    for (const c of switches) c.vm.$emit('update:modelValue', false)
    expect(vm.formData.is_active).toBe(false)

    // 分页器双 v-model
    const pager = wrapper.findComponent({ name: 'ElPagination' })
    expect(pager.exists()).toBe(true)
    pager.vm.$emit('update:currentPage', 2)
    pager.vm.$emit('update:pageSize', 20)
    expect(vm.pagination.page).toBe(2)
    expect(vm.pagination.size).toBe(20)

    // 四个对话框（用户/重置密码/菜单权限/导出权限包）+ 权限抽屉的 v-model
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    expect(dialogs.length).toBe(4)
    for (const d of dialogs) d.vm.$emit('update:modelValue', false)
    expect(vm.dialogVisible).toBe(false)
    expect(vm.resetPwdDialogVisible).toBe(false)
    expect(vm.menuPermDialogVisible).toBe(false)
    expect(vm.permExportDialogVisible).toBe(false)
    const drawer = wrapper.findComponent({ name: 'PermissionAssignmentDrawer' })
    drawer.vm.$emit('update:modelValue', true)
    expect(vm.permDrawerVisible).toBe(true)

    // Tabs v-model（放最后：切到 roles 会卸载搜索区组件）
    const tabs = wrapper.findComponent({ name: 'ElTabs' })
    expect(tabs.exists()).toBe(true)
    tabs.vm.$emit('update:modelValue', 'roles')
    expect(vm.activeTab).toBe('roles')
    await nextTick()
  })
})

describe('行操作与内联点击处理器（函数覆盖）', () => {
  it('点击编辑/强制登出/重置密码/角色权限/删除/取消按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const findBtn = (text: string) => {
      const btn = wrapper.findAll('el-button-stub').find((b) => b.text().includes(text))
      expect(btn, text).toBeTruthy()
      return btn!
    }

    // 编辑（打开会话区）→ 强制登出
    await findBtn('编辑').trigger('click')
    await flushPromises()
    expect(vm.isEdit).toBe(true)
    await nextTick()
    await findBtn('强制登出').trigger('click')
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith('/system/admin/users/1/sessions/s1/revoke')

    // 行内 重置密码 / 角色权限 / 删除
    await findBtn('重置密码').trigger('click')
    expect(vm.resetPwdDialogVisible).toBe(true)
    await findBtn('角色/权限').trigger('click')
    expect(vm.permDrawerVisible).toBe(true)
    await findBtn('删除').trigger('click')
    await flushPromises()
    expect(mockDel).toHaveBeenCalledWith('/users/1')

    // 三个“取消”按钮分别关闭三个对话框（两条内联赋值箭头 + 新增导出对话框）
    const cancels = wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '取消')
    expect(cancels.length).toBe(4)
    vm.dialogVisible = true
    vm.resetPwdDialogVisible = true
    vm.menuPermDialogVisible = true
    await cancels[0].trigger('click')
    await cancels[1].trigger('click')
    await cancels[2].trigger('click')
    expect(vm.dialogVisible).toBe(false)
    expect(vm.resetPwdDialogVisible).toBe(false)
  })
})

describe('逻辑或 / 空值合并兜底分支', () => {
  it('roleOptions：外部接口数据不影响固定角色选项', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles') return Promise.resolve(null)
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    // roleOptions 为静态数组, 不依赖任何接口数据
    expect((wrapper.vm as any).roleOptions).toHaveLength(4)
  })

  it('loadData：无 items 无 total → 双兜底为 0', async () => {
    mockApiRequest.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.tableData).toEqual([])
    expect(vm.pagination.total).toBe(0)
  })

  it('loadPendingCount：原始数组与 falsy 响应', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/users/pending/list') return Promise.resolve([{ id: 1 }, { id: 2 }])
      return defaultGetImpl(url)
    })
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).pendingCount).toBe(2)
    wrapper.unmount()

    mockGet.mockImplementation((url: string) => {
      if (url === '/users/pending/list') return Promise.resolve(0)
      return defaultGetImpl(url)
    })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).pendingCount).toBe(0)
  })

  it('showPendingUsers：原始数组与空对象响应', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/users/pending/list') return Promise.resolve([{ id: 5 }])
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.showPendingUsers()
    expect(vm.pendingUsers).toEqual([{ id: 5 }])

    mockGet.mockImplementation((url: string) => {
      if (url === '/users/pending/list') return Promise.resolve({ data: {} })
      return defaultGetImpl(url)
    })
    await vm.showPendingUsers()
    expect(vm.pendingUsers).toEqual([])
    expect(vm.pendingCount).toBe(0)

    // res.data 与 res 均 falsy → || [] 兜底
    mockGet.mockImplementation((url: string) => {
      if (url === '/users/pending/list') return Promise.resolve(0)
      return defaultGetImpl(url)
    })
    await vm.showPendingUsers()
    expect(vm.pendingUsers).toEqual([])
  })

  it('loadUserSessions：无 sessions 字段的对象 → ?? [] 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockResolvedValueOnce({ data: { foo: 1 } })
    await vm.loadUserSessions(1)
    expect(vm.userSessions).toEqual([])
  })

  it('导出：响应无 .data 包装 → res 本体兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockPost.mockResolvedValueOnce({ file_name: 'plain.zip', role_count: 1, user_count: 1 })
    if (!vm.permExportDialogVisible) {
      mockGet.mockResolvedValueOnce({ data: { data: [] } })
      await vm.openPermExportDialog()
    }
    await vm.doExportPermissionPackage()
    expect(mockDownloadBlobAsFile).toHaveBeenCalledWith(expect.any(Function), {
      fallbackFileName: 'plain.zip',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('权限包导出成功 (1 个角色, 1 个用户)')
  })

  it('导入：无 .data 包装 / success 无 message / 异常无任何字段', async () => {
    const inputs: HTMLInputElement[] = []
    const orig = document.createElement.bind(document)
    const spy = vi.spyOn(document, 'createElement').mockImplementation((tag: any, opts?: any) => {
      const el = orig(tag, opts)
      if (String(tag).toLowerCase() === 'input') inputs.push(el as HTMLInputElement)
      return el
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const file = new File(['zip'], 'p.zip')
    const fire = async (i: number) => {
      Object.defineProperty(inputs[i], 'files', { value: [file], configurable: true })
      inputs[i].dispatchEvent(new Event('change'))
      await flushPromises()
    }

    // 1) 响应无 .data → res 本体；confirm 走通
    mockPost.mockImplementation((url: string) => {
      if (url === '/permission-packages/import') return Promise.resolve({ success: true })
      if (url.startsWith('/permission-packages/confirm/')) return Promise.resolve({})
      return Promise.resolve({ data: {} })
    })
    vm.handleImportPermissionPackage()
    await fire(0)
    expect(confirmMock).toHaveBeenCalled()

    // 2) success=false 且无 message → '导入失败'
    confirmMock.mockResolvedValue(undefined)
    mockPost.mockImplementation((url: string) => {
      if (url === '/permission-packages/import') return Promise.resolve({ success: false })
      return Promise.resolve({ data: {} })
    })
    vm.handleImportPermissionPackage()
    await fire(1)
    expect(ElMessage.error).toHaveBeenCalledWith('导入失败')

    // 3) 异常无 detail 无 message → '导入失败'
    mockPost.mockImplementation((url: string) => {
      if (url === '/permission-packages/import') return Promise.reject({})
      return Promise.resolve({ data: {} })
    })
    vm.handleImportPermissionPackage()
    await fire(2)
    expect(ElMessage.error).toHaveBeenCalledWith('导入失败')
    spy.mockRestore()
  })
})

describe('组织筛选清除', () => {
  it('orgFilterId 有值时清除按钮触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.orgFilterId = 5
    await wrapper.vm.$nextTick()
    const btn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().includes('清除筛选'))
    if (btn) {
      await btn.trigger('click')
    } else {
      vm.clearOrgFilter()
    }
    expect(vm.orgFilterId).toBeNull()
    wrapper.unmount()
  })
})

describe('org_id 跳转筛选分支', () => {
  it('route.query.org_id>0 → 预筛选组织', async () => {
    routeQuery.query = { org_id: '5' }
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).orgFilterId).toBe(5)
    wrapper.unmount()
    routeQuery.query = {}
  })
})

describe('权限包列 packNameMap', () => {
  it('loadPackNameMap 失败 → 降级为空映射', async () => {
    listPacksMock.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.packNameMap).toEqual({})
    wrapper.unmount()
  })

  it('权限包列模板：命中名称 / 未知包 / 角色默认', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('基础包') // rowA permission_pack_id=1 命中
    expect(text).toContain('未知包') // rowB permission_pack_id=999 未命中
    expect(text).toContain('角色默认') // rowC 无 permission_pack_id
    wrapper.unmount()
  })
})

describe('菜单权限配置', () => {
  it('handleMenuPermission 成功：拉取配置/菜单树并勾选', async () => {
    const setChecked = vi.fn()
    const getChecked = vi.fn(() => ['a', 'b'])
    const wrapper = mountComp({
      'el-tree': {
        name: 'ElTree',
        template: '<div class="el-tree-stub"><slot /></div>',
        methods: {
          setCheckedKeys: (...args: any[]) => setChecked(...args),
          getCheckedKeys: getChecked,
        },
      },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockImplementation((url: string) => {
      if (url === '/menus/user-menus/1') return Promise.resolve({ data: { menu_keys: ['a', 'b'] } })
      if (url === '/menus/all') return Promise.resolve({ data: menuTreeSample })
      return defaultGetImpl(url)
    })
    await vm.handleMenuPermission({ id: 1, username: 'admin' })
    expect(mockGet).toHaveBeenCalledWith('/menus/user-menus/1')
    expect(mockGet).toHaveBeenCalledWith('/menus/all')
    expect(vm.menuPermTree).toEqual(menuTreeSample)
    expect(vm.menuPermLoading).toBe(false)
    expect(setChecked).toHaveBeenCalledWith(['a', 'b'])
    wrapper.unmount()
  })

  it('handleMenuPermission 失败：detail 文案与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/menus/')) return Promise.reject({ response: { data: { detail: '无权限' } } })
      return defaultGetImpl(url)
    })
    await vm.handleMenuPermission({ id: 1 })
    expect(ElMessage.error).toHaveBeenCalledWith('无权限')
    expect(vm.menuPermLoading).toBe(false)

    ElMessage.error.mockClear()
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/menus/')) return Promise.reject(new Error('net'))
      return defaultGetImpl(url)
    })
    await vm.handleMenuPermission({ id: 2 })
    expect(ElMessage.error).toHaveBeenCalledWith('加载菜单权限配置失败')
    expect(logError).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('flattenMenuKeys / updateMenuPermAllState / toggleMenuPermAll 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // flattenMenuKeys
    expect(vm.flattenMenuKeys(menuTreeSample)).toEqual(['a', 'b', 'b1'])
    expect(vm.flattenMenuKeys([])).toEqual([])

    // updateMenuPermAllState：全选 / 半选 / 空选 / 无树
    vm.menuPermTree = menuTreeSample
    vm.menuPermTreeRef = { getCheckedKeys: () => ['a', 'b', 'b1'] }
    vm.updateMenuPermAllState()
    expect(vm.menuPermAllChecked).toBe(true)
    expect(vm.menuPermIndeterminate).toBe(false)

    vm.menuPermTreeRef = { getCheckedKeys: () => ['a'] }
    vm.updateMenuPermAllState()
    expect(vm.menuPermAllChecked).toBe(false)
    expect(vm.menuPermIndeterminate).toBe(true)

    vm.menuPermTreeRef = { getCheckedKeys: () => [] }
    vm.updateMenuPermAllState()
    expect(vm.menuPermAllChecked).toBe(false)
    expect(vm.menuPermIndeterminate).toBe(false)

    vm.menuPermTreeRef = null
    expect(() => vm.updateMenuPermAllState()).not.toThrow()

    // toggleMenuPermAll：全选 / 清空 / 无树
    const setChecked = vi.fn()
    vm.menuPermTreeRef = { setCheckedKeys: setChecked, getCheckedKeys: () => [] }
    vm.toggleMenuPermAll(true)
    expect(setChecked).toHaveBeenCalledWith(['a', 'b', 'b1'])
    vm.toggleMenuPermAll(false)
    expect(setChecked).toHaveBeenCalledWith([])
    vm.menuPermTreeRef = null
    expect(() => vm.toggleMenuPermAll(true)).not.toThrow()
    wrapper.unmount()
  })

  it('saveMenuPermission：早退 / 成功 / 失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 无 menuPermUser → 早退
    await vm.saveMenuPermission()
    expect(mockPut).not.toHaveBeenCalled()

    // 无树 → 早退
    vm.menuPermUser = { id: 1 }
    vm.menuPermTreeRef = null
    await vm.saveMenuPermission()
    expect(mockPut).not.toHaveBeenCalled()

    // 成功
    vm.menuPermTreeRef = { getCheckedKeys: () => ['a', 'b'] }
    await vm.saveMenuPermission()
    expect(mockPut).toHaveBeenCalledWith('/menus/user-menus/1', { menu_keys: ['a', 'b'] })
    expect(ElMessage.success).toHaveBeenCalledWith('菜单权限已保存')
    expect(vm.menuPermDialogVisible).toBe(false)

    // 失败：detail 与兜底（await 后模板 ref 会被重绑，需重新注入 mock 树）
    vm.menuPermTreeRef = { getCheckedKeys: () => ['a', 'b'] }
    mockPut.mockRejectedValueOnce({ response: { data: { detail: '保存失败原因' } } })
    await vm.saveMenuPermission()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败原因')
    vm.menuPermTreeRef = { getCheckedKeys: () => ['a', 'b'] }
    mockPut.mockRejectedValueOnce(new Error('net'))
    await vm.saveMenuPermission()
    expect(ElMessage.error).toHaveBeenCalledWith('保存菜单权限失败')
    expect(vm.menuPermSaving).toBe(false)
    wrapper.unmount()
  })

  it('点击「菜单权限」按钮触发 handleMenuPermission', async () => {
    const setChecked = vi.fn()
    const wrapper = mountComp({
      'el-tree': {
        name: 'ElTree',
        template: '<div class="el-tree-stub"><slot /></div>',
        methods: {
          setCheckedKeys: setChecked,
          getCheckedKeys: () => ['a'],
        },
      },
    })
    await flushPromises()
    mockGet.mockImplementation((url: string) => {
      if (url === '/menus/user-menus/1') return Promise.resolve({ data: { menu_keys: ['a'] } })
      if (url === '/menus/all') return Promise.resolve({ data: menuTreeSample })
      return defaultGetImpl(url)
    })
    const btn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes('菜单权限'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/menus/user-menus/1')
    expect(setChecked).toHaveBeenCalledWith(['a'])
    wrapper.unmount()
  })

  it('handleMenuPermission：cfg/menu 稀疏形态与空值兜底', async () => {
    const setChecked = vi.fn()
    const wrapper = mountComp({
      'el-tree': {
        name: 'ElTree',
        template: '<div class="el-tree-stub"><slot /></div>',
        methods: { setCheckedKeys: setChecked, getCheckedKeys: () => [] },
      },
    })
    await flushPromises()
    const vm = wrapper.vm as any

    // 1) cfgRes 无 data（裸空对象）+ menuRes 裸数组 → cfg/menu_keys/menuData 兜底
    mockGet.mockImplementation((url: string) => {
      if (url === '/menus/user-menus/1') return Promise.resolve({})
      if (url === '/menus/all') return Promise.resolve(menuTreeSample)
      return defaultGetImpl(url)
    })
    await vm.handleMenuPermission({ id: 1, username: 'admin' })
    expect(vm.menuPermTree).toEqual(menuTreeSample)

    // 2) cfgRes 与 menuRes 均为 null → ?? 兜底到 {} / []
    mockGet.mockImplementation((url: string) => {
      if (url === '/menus/user-menus/2') return Promise.resolve(null)
      if (url === '/menus/all') return Promise.resolve(null)
      return defaultGetImpl(url)
    })
    await vm.handleMenuPermission({ id: 2, username: 'u2' })
    expect(vm.menuPermTree).toEqual([])

    // 3) menuRes 为非数组对象 → menuPermTree 三元 false 置空
    mockGet.mockImplementation((url: string) => {
      if (url === '/menus/user-menus/1') return Promise.resolve({ data: {} })
      if (url === '/menus/all') return Promise.resolve({ foo: 1 })
      return defaultGetImpl(url)
    })
    await vm.handleMenuPermission({ id: 1, username: 'admin' })
    expect(vm.menuPermTree).toEqual([])
    wrapper.unmount()
  })
})

// ─────────────────────────────────────────────
// 权限包导出对话框与加密包导入（Phase E）深度分支
// 缺口：funcs inputValidator@1225 / onClick@463 / onUpdate:modelValue@437
//       stmts@1159-1163, 1219-1245
//       branch@439, 1133, 1137×2, 1138×2, 1158, 1161, 1218, 1264, 1278
// ─────────────────────────────────────────────

/** 捕获组件创建的 file input 元素（与上方 captureInputs 同构，供本 describe 内复用） */
function captureFileInputs() {
  const inputs: HTMLInputElement[] = []
  const orig = document.createElement.bind(document)
  const spy = vi.spyOn(document, 'createElement').mockImplementation((tag: any, opts?: any) => {
    const el = orig(tag, opts)
    if (String(tag).toLowerCase() === 'input') inputs.push(el as HTMLInputElement)
    return el
  })
  return { inputs, spy }
}

/**
 * 导出权限包对话框需要真实渲染插槽：
 * - el-dialog 桩带上 title，便于在多个对话框中定位「导出权限包」
 * - el-button 桩可 emit click（覆盖 footer 取消按钮的内联 onClick@463）
 * - el-checkbox-group 桩可 emit update:modelValue（覆盖 v-model 产物 onUpdate:modelValue@437）
 * - el-checkbox 桩渲染默认插槽（覆盖 {{ r.label || r.name }} 两侧）
 */
const permDialogStubs = {
  'el-dialog': {
    props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
    emits: ['update:modelValue'],
    template: '<div class="el-dialog-stub" :data-title="title"><slot /><slot name="footer" /></div>',
  },
  'el-button': {
    template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
    emits: ['click'],
  },
  'el-checkbox-group': {
    props: { modelValue: { type: Array, default: () => [] } },
    emits: ['update:modelValue'],
    template:
      '<div class="el-checkbox-group-stub" @click="$emit(\'update:modelValue\', [\'village_officer\'])"><slot /></div>',
  },
  'el-checkbox': {
    props: { value: { type: [String, Number, Boolean], default: '' } },
    template: '<label class="el-checkbox-stub" :data-value="String(value)"><slot /></label>',
  },
  'el-alert': { template: '<div class="el-alert-stub"><slot /></div>' },
  'el-divider': { template: '<hr class="el-divider-stub" />' },
}

function findPermDialog(wrapper: any) {
  return wrapper
    .findAll('.el-dialog-stub')
    .find((d: any) => d.attributes('data-title') === '导出权限包')
}

describe('权限包导出对话框（模板分支）', () => {
  it('onUpdate:modelValue@437：勾选角色组 emit → permExportRoleNames 回写', async () => {
    const wrapper = mountComp(permDialogStubs)
    await flushPromises()
    const vm = wrapper.vm as any
    vm.permExportDialogVisible = true
    vm.permExportRoleNames = []
    await nextTick()
    const dlg = findPermDialog(wrapper)
    expect(dlg).toBeTruthy()
    const group = dlg!.find('.el-checkbox-group-stub')
    expect(group.exists()).toBe(true)
    await group.trigger('click')
    expect(vm.permExportRoleNames).toEqual(['village_officer'])
  })

  it('onClick@463：footer「取消」按钮 → 关闭导出对话框', async () => {
    const wrapper = mountComp(permDialogStubs)
    await flushPromises()
    const vm = wrapper.vm as any
    vm.permExportDialogVisible = true
    await nextTick()
    const dlg = findPermDialog(wrapper)!
    const cancelBtn = dlg.findAll('.el-button-stub').find((b: any) => b.text() === '取消')
    expect(cancelBtn).toBeTruthy()
    await cancelBtn!.trigger('click')
    expect(vm.permExportDialogVisible).toBe(false)
    // 另一个按钮为「导出」，存在但本用例不触发
    expect(dlg.findAll('.el-button-stub').some((b: any) => b.text() === '导出')).toBe(true)
  })

  it('branch@439：角色有 label → 渲染 label；无 label 也无 name → 回退侧（空文本）', async () => {
    const wrapper = mountComp(permDialogStubs)
    await flushPromises()
    const vm = wrapper.vm as any
    // 第一项有 label；第二项 name/label/description 均缺失 → option.label 为 undefined
    mockGet.mockImplementation((url: string) =>
      url === '/rbac/roles'
        ? Promise.resolve({ data: { items: [{ name: 'a', label: '角色A' }, {}] } })
        : defaultGetImpl(url)
    )
    await vm.openPermExportDialog()
    await nextTick()
    const dlg = findPermDialog(wrapper)!
    const boxes = dlg.findAll('.el-checkbox-stub')
    expect(boxes).toHaveLength(2)
    expect(boxes[0].text()).toBe('角色A')
    expect(boxes[0].attributes('data-value')).toBe('a')
    // r.label 为 undefined → || r.name 也为 undefined → 渲染空
    expect(boxes[1].text()).toBe('')
    // 非空选项 → empty-hint 不渲染
    expect(dlg.find('.empty-hint').exists()).toBe(false)
  })

  it('角色列表为空 → empty-hint 渲染（length === 0 真侧）', async () => {
    const wrapper = mountComp(permDialogStubs)
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockImplementation((url: string) =>
      url === '/rbac/roles' ? Promise.resolve({ data: { items: [] } }) : defaultGetImpl(url)
    )
    await vm.openPermExportDialog()
    await nextTick()
    const dlg = findPermDialog(wrapper)!
    expect(vm.permExportRoleOptions).toEqual([])
    expect(vm.permRolesLoading).toBe(false)
    expect(dlg.find('.empty-hint').exists()).toBe(true)
  })
})

describe('openPermExportDialog 角色响应形态与缓存', () => {
  it('branch@1133 真侧：选项已缓存 → 直接 return，不重复请求，且重置表单', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const rolesCalls = () => mockGet.mock.calls.filter((c) => c[0] === '/rbac/roles').length
    await vm.openPermExportDialog() // defaultGetImpl → {data:{items:[自定义角色]}}
    expect(vm.permExportRoleOptions).toEqual([{ name: '自定义角色', label: '自定义角色' }])
    const afterFirst = rolesCalls()
    expect(afterFirst).toBe(1)

    // 第二次打开：length > 0 → 提前 return
    vm.permExportPassword = 'x'
    vm.permBindMachineCode = true
    vm.permExportRoleNames = ['自定义角色']
    await vm.openPermExportDialog()
    expect(rolesCalls()).toBe(afterFirst) // 未新增请求
    expect(vm.permExportDialogVisible).toBe(true)
    expect(vm.permExportPassword).toBe('')
    expect(vm.permBindMachineCode).toBe(false)
    expect(vm.permExportRoleNames).toEqual([])
    expect(vm.permExportRoleOptions).toEqual([{ name: '自定义角色', label: '自定义角色' }])
  })

  it('branch@1137/@1138：res 为 null / 裸数组 / data.items / data.data / 空对象 五种形态', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const load = async (res: any) => {
      vm.permExportRoleOptions = [] // 清空缓存以绕过 branch@1133 的提前 return
      mockGet.mockImplementation((url: string) =>
        url === '/rbac/roles' ? Promise.resolve(res) : defaultGetImpl(url)
      )
      await vm.openPermExportDialog()
      return vm.permExportRoleOptions
    }

    // res 为 null：res?.data → undefined；|| res → null；|| {} → {} → data.data/items 均缺 → []
    expect(await load(null)).toEqual([])
    // res 为裸数组：res?.data → undefined；|| res → 数组 → Array.isArray 真侧
    expect(await load([{ name: 'x', description: '描述X' }])).toEqual([{ name: 'x', label: '描述X' }])
    // res.data 为数组：res?.data 真侧 + Array.isArray 真侧
    expect(await load({ data: [{ name: 'y', label: 'Y' }] })).toEqual([{ name: 'y', label: 'Y' }])
    // res.data.items
    expect(await load({ data: { items: [{ name: 'z' }] } })).toEqual([{ name: 'z', label: 'z' }])
    // res.data.data 优先于 items
    expect(await load({ data: { data: [{ name: 'd' }], items: [{ name: 'i' }] } })).toEqual([
      { name: 'd', label: 'd' },
    ])
    // res 无 data 且非数组 → || res 真侧；data.data/items 均缺 → []
    expect(await load({ foo: 1 })).toEqual([])
    expect(vm.permRolesLoading).toBe(false)
  })

  it('导出：加密密码 + 机器码绑定 → payload 携带 password/bind_machine_code（branch@1158/@1161 真侧）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.openPermExportDialog()
    vm.permExportRoleNames = []
    vm.permExportPassword = 'secret'
    vm.permBindMachineCode = true
    mockPost.mockResolvedValueOnce({ data: { file_name: 'enc.zip', role_count: 0, user_count: 0 } })
    await vm.doExportPermissionPackage()
    expect(mockPost).toHaveBeenLastCalledWith('/permission-packages/export', {
      password: 'secret',
      bind_machine_code: true,
    })
    expect(mockDownloadBlobAsFile).toHaveBeenCalledWith(expect.any(Function), {
      fallbackFileName: 'enc.zip',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('权限包导出成功 (0 个角色, 0 个用户)')
    expect(vm.exportingPermPackage).toBe(false)
  })
})

describe('加密权限包导入（Phase E）', () => {
  const ENC_MSG = '该权限包已加密，请输入导出时设置的密码'

  /** 构造 import 桩：首次返回加密提示，第二次返回 merged */
  function stubImport(first: any, second: any, confirmRes: any = { data: { message: 'ok' } }) {
    let n = 0
    const seen: FormData[] = []
    mockPost.mockImplementation((url: string, body?: any) => {
      if (url === '/permission-packages/import') {
        if (body instanceof FormData) seen.push(body)
        n += 1
        return Promise.resolve(n === 1 ? first : second)
      }
      if (url.startsWith('/permission-packages/confirm/')) return Promise.resolve(confirmRes)
      return Promise.resolve({ data: {} })
    })
    return { seen, importCalls: () => n }
  }

  async function fireImport(
    vm: any,
    inputs: HTMLInputElement[],
    idx: number,
    fileName = 'enc.zip'
  ) {
    const file = new File(['zip'], fileName, { type: 'application/zip' })
    Object.defineProperty(inputs[idx], 'files', { value: [file], configurable: true })
    inputs[idx].dispatchEvent(new Event('change'))
    await flushPromises()
    return file
  }

  it('branch@1218 真侧：预览失败且含「加密」→ prompt 密码 → 带 password 重传 → 合并结果后继续确认', async () => {
    const { inputs, spy } = captureFileInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const h = stubImport(
      { data: { success: false, message: ENC_MSG } },
      { data: { success: true, preview: { role_count: 1, user_legacy_count: 2 } } }
    )
    vm.handleImportPermissionPackage()
    await fireImport(vm, inputs, 0)

    expect(h.importCalls()).toBe(2)
    expect(promptMock).toHaveBeenCalledWith(
      '该权限包已加密，请输入导出时设置的密码：',
      '解密密码',
      expect.objectContaining({ inputType: 'password' })
    )
    // 第二次上传的 FormData 携带密码
    expect(h.seen).toHaveLength(2)
    expect(h.seen[1].get('password')).toBe('pw')
    expect(h.seen[1].get('file')).toBeInstanceOf(File)
    // Object.assign(result, merged) 后 success 为真 → 进入确认流程
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('将导入 1 个角色, 2 个用户权限'),
      '选择导入模式',
      expect.objectContaining({ confirmButtonText: '合并导入', cancelButtonText: '覆盖导入' })
    )
    expect(mockPost).toHaveBeenCalledWith(
      `/permission-packages/confirm/${encodeURIComponent('enc.zip')}`,
      { overwrite_existing: false, mode: 'merge' }
    )
    expect(ElMessage.success).toHaveBeenCalledWith('ok')
    expect(vm.importingPermPackage).toBe(false) // finally cleanup
    spy.mockRestore()
  })

  it('funcs@1225 inputValidator：空密码 → 「密码不能为空」；非空 → true；value 缺失 → 密码回退空串', async () => {
    const { inputs, spy } = captureFileInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const h = stubImport(
      { data: { success: false, message: ENC_MSG } },
      { data: { success: true } }
    )
    promptMock.mockResolvedValueOnce({ value: undefined }) // → importPassword = ''
    vm.handleImportPermissionPackage()
    await fireImport(vm, inputs, 0)

    const opts = promptMock.mock.calls[0][2]
    expect(typeof opts.inputValidator).toBe('function')
    expect(opts.inputValidator('')).toBe('密码不能为空')
    expect(opts.inputValidator('   ')).toBe(true) // 仅判 falsy，空白串视为已输入
    expect(opts.inputValidator('pw')).toBe(true)
    expect(h.seen[1].get('password')).toBe('')
    spy.mockRestore()
  })

  it('prompt 取消 → cleanup 并 return，不重传也不确认', async () => {
    const { inputs, spy } = captureFileInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const h = stubImport({ data: { success: false, message: ENC_MSG } }, { data: { success: true } })
    promptMock.mockRejectedValueOnce('cancel')
    vm.handleImportPermissionPackage()
    await fireImport(vm, inputs, 0)
    expect(h.importCalls()).toBe(1) // 未重传
    expect(confirmMock).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
    expect(vm.importingPermPackage).toBe(false)
    spy.mockRestore()
  })

  it('重传后仍 success=false → 优先 merged.message，否则回退 result.message', async () => {
    const { inputs, spy } = captureFileInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // a) merged.message 存在 → 取左侧
    stubImport(
      { data: { success: false, message: ENC_MSG } },
      { data: { success: false, message: '密码错误' } }
    )
    vm.handleImportPermissionPackage()
    await fireImport(vm, inputs, 0)
    expect(ElMessage.error).toHaveBeenCalledWith('密码错误')
    expect(confirmMock).not.toHaveBeenCalled()

    // b) merged 无 message 键 → Object.assign 保留了 result.message（即加密提示）
    ElMessage.error.mockClear()
    stubImport({ data: { success: false, message: ENC_MSG } }, { data: { success: false } })
    vm.handleImportPermissionPackage()
    await fireImport(vm, inputs, 1)
    expect(ElMessage.error).toHaveBeenCalledWith(ENC_MSG)
    spy.mockRestore()
  })

  it('branch@1239 右侧：res2 无 data 信封 → merged 即 res2 本体', async () => {
    const { inputs, spy } = captureFileInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 重传响应不带 data 信封（res2.data 为 undefined）→ `res2.data || res2` 取右侧
    stubImport({ data: { success: false, message: ENC_MSG } }, { success: false, message: '包已损坏' })
    vm.handleImportPermissionPackage()
    await fireImport(vm, inputs, 0)
    expect(ElMessage.error).toHaveBeenCalledWith('包已损坏')
    expect(confirmMock).not.toHaveBeenCalled()
    spy.mockRestore()
  })

  it('branch@1242 第三操作数：merged.message 为空串 → 覆盖后回退「导入失败」', async () => {
    const { inputs, spy } = captureFileInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 进入本分支的前提是 /加密/.test(result.message) 为真，但 merged 可以带一个空的
    // message 键：Object.assign(result, merged) 会用 '' 覆盖原有的加密提示，
    // 此时 merged.message 与 result.message 同时为假 → 第三操作数可达。
    stubImport({ data: { success: false, message: ENC_MSG } }, { data: { success: false, message: '' } })
    vm.handleImportPermissionPackage()
    await fireImport(vm, inputs, 0)
    expect(ElMessage.error).toHaveBeenCalledWith('导入失败')
    expect(confirmMock).not.toHaveBeenCalled()
    spy.mockRestore()
  })

  it('branch@1218 假侧：success=false 但 message 不含「加密」→ 不弹密码框，直接报错', async () => {
    const { inputs, spy } = captureFileInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const h = stubImport({ data: { success: false, message: '文件损坏' } }, { data: {} })
    vm.handleImportPermissionPackage()
    await fireImport(vm, inputs, 0)
    expect(promptMock).not.toHaveBeenCalled()
    expect(h.importCalls()).toBe(1)
    expect(ElMessage.error).toHaveBeenCalledWith('文件损坏')
    spy.mockRestore()
  })

  it('branch@1264：confirm 以 cancel 拒绝 → mode=overwrite → overwrite_existing 为真', async () => {
    const { inputs, spy } = captureFileInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    stubImport({ data: { success: true, preview: {} } }, { data: {} }, {})
    confirmMock.mockRejectedValueOnce('cancel')
    vm.handleImportPermissionPackage()
    await fireImport(vm, inputs, 0, 'ow.zip')
    expect(mockPost).toHaveBeenCalledWith(
      `/permission-packages/confirm/${encodeURIComponent('ow.zip')}`,
      { overwrite_existing: true, mode: 'overwrite' }
    )
    expect(ElMessage.success).toHaveBeenCalledWith('导入完成') // cRes 无 data/message → 兑底
    spy.mockRestore()
  })

  it('branch@1278：异常为字符串 cancel → 静默 return，不弹错误', async () => {
    const { inputs, spy } = captureFileInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockPost.mockImplementation((url: string) =>
      url === '/permission-packages/import'
        ? Promise.reject('cancel')
        : Promise.resolve({ data: {} })
    )
    vm.handleImportPermissionPackage()
    await fireImport(vm, inputs, 0)
    expect(ElMessage.error).not.toHaveBeenCalled()
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(vm.importingPermPackage).toBe(false) // finally 仍 cleanup
    spy.mockRestore()
  })
})

