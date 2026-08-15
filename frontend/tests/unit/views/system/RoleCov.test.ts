/**
 * views/system/Role.vue 覆盖率攻坚（statements/branches/functions/lines 四指标 100%）
 * 覆盖：加载（角色列表 bare/envelope 双形态 + 空列表 + 全兜底分支、权限树全兜底分支）、
 * 搜索/重置/分页 v-model、
 * 新增/编辑/提交（validate 三分支 + isEdit 两侧 + 失败）、用户列表对话框
 * （三种响应形态 + 异常 + 空态 v-if 两侧）、删除（有关联/无关联/取消/失败）、
 * 权限配置（checkAll/uncheckAll、savePermissions 四分支）、
 * 模板插槽 el-tag 三元两侧与全部内联 @click / v-model 处理器。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂被提升到模块顶部，引用的对象必须先放入 vi.hoisted（TDZ 坑）
const { ElMessage, confirmMock, mockGet, mockPost, mockPut, mockDel, dsMock } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  confirmMock: vi.fn(),
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPut: vi.fn(),
  mockDel: vi.fn(),
  dsMock: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
  ElTree: { name: 'ElTree' },
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: mockDel,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/composables/useDesensitize', () => ({
  useDesensitize: () => ({ ds: dsMock }),
}))

import Role from '@/views/system/Role.vue'

// roleViewer 缺 name/created_at → 覆盖 loadRoles 中 || '' 兜底；is_active:false → 禁用侧
const roleAdmin = {
  id: 'r1',
  name: '系统管理员',
  description: '最高权限',
  is_active: true,
  created_at: '2024-01-01',
}
const roleViewer = { id: 'r2', name: '', description: '', is_active: false }

const roleUsersR1 = [{ username: 'u1', real_name: '张三', email: 'a@b.c', is_active: true }]

// 权限树：覆盖 categoryNames 命中/回退、空类别 continue、null 类别 continue、
// actionNames 命中、code 缺失回退 p.name、label 三级回退
const permissionsPayload = {
  categories: {
    user: [
      { code: 'user:read', name: '读取' },
      { code: 'user:write', name: '写入', description: '编辑用户' },
    ],
    custom_cat: [{ name: '无编码权限' }],
    empty_cat: [],
    null_cat: null,
  },
}

function defaultGetImpl(url: string) {
  // loadRoles 现读取 res?.data || res?.items || [] —— bare 形态下 res.data 即角色数组
  if (url === '/rbac/roles') return Promise.resolve({ data: [roleAdmin, roleViewer], total: 2 })
  if (url === '/rbac/permissions') return Promise.resolve(permissionsPayload)
  if (url === '/rbac/roles/r1/users') return Promise.resolve({ data: roleUsersR1 })
  if (url === '/rbac/roles/r2/users') return Promise.resolve({ data: [] })
  if (url === '/rbac/roles/r1') {
    return Promise.resolve({ data: { permissions: ['user:read'] } })
  }
  return Promise.resolve({ data: {} })
}

// 主表格列插槽行：status active/inactive 两侧；用户对话框列：is_active true/false 两侧
const rowA = {
  id: 'r1',
  name: '系统管理员',
  code: 'ADMIN',
  description: '最高权限',
  userCount: 3,
  createTime: '2024-01-01',
  status: 'active',
  username: 'u1',
  real_name: '张三',
  email: 'a@b.c',
  is_active: true,
}
const rowB = {
  id: 'r2',
  name: '观察员',
  code: 'VIEWER',
  description: '',
  userCount: 0,
  createTime: '',
  status: 'inactive',
  username: 'u2',
  real_name: '',
  email: '',
  is_active: false,
}

function mountComp() {
  return mount(Role, {
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
        'el-input': {
          name: 'ElInput',
          template: '<div class="el-input-stub"><slot /></div>',
          emits: ['update:modelValue'],
        },
        'el-select': {
          name: 'ElSelect',
          template: '<div class="el-select-stub"><slot /></div>',
          emits: ['update:modelValue'],
        },
        'el-switch': {
          name: 'ElSwitch',
          template: '<div class="el-switch-stub" />',
          emits: ['update:modelValue'],
        },
        'el-pagination': {
          name: 'ElPagination',
          template: '<div class="el-pagination-stub" />',
          emits: ['update:currentPage', 'update:pageSize'],
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
          data() {
            return { rowA, rowB }
          },
        },
      },
    },
  })
}

function findButtons(wrapper: any, text: string) {
  return wrapper.findAll('el-button-stub').filter((b: any) => b.text().includes(text))
}

beforeEach(() => {
  vi.resetAllMocks()
  mockGet.mockImplementation(defaultGetImpl)
  mockPost.mockResolvedValue({ data: {} })
  mockPut.mockResolvedValue({ data: {} })
  mockDel.mockResolvedValue({ data: {} })
  confirmMock.mockResolvedValue(undefined)
  dsMock.mockImplementation((v: any) => v ?? '')
})

describe('挂载与数据加载', () => {
  it('onMounted 并行加载角色列表与权限树（含全部兜底分支）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(mockGet).toHaveBeenCalledWith('/rbac/roles')
    expect(mockGet).toHaveBeenCalledWith('/rbac/permissions')
    expect(vm.tableData).toEqual([
      {
        id: 'r1',
        name: '系统管理员',
        code: '系统管理员',
        description: '最高权限',
        userCount: 1,
        createTime: '2024-01-01',
        status: 'active',
      },
      {
        id: 'r2',
        name: '',
        code: '',
        description: '',
        userCount: 0,
        createTime: '',
        status: 'inactive',
      },
    ])
    expect(vm.pagination.total).toBe(2)
    // 权限树：类别名命中与回退、空/null 类别跳过、action/label 多级回退
    expect(vm.menuTreeData).toEqual([
      {
        id: 'user',
        label: '用户管理',
        children: [
          { id: 'user:read', label: '查看' },
          { id: 'user:write', label: '编辑' },
        ],
      },
      { id: 'custom_cat', label: 'custom_cat', children: [{ id: undefined, label: '无编码权限' }] },
    ])
  })

  it('loadRoles 失败 → 空表并提示', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles') return Promise.reject(new Error('net'))
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.tableData).toEqual([])
    expect(ElMessage.error).toHaveBeenCalledWith('net')
  })

  it('loadRoles：响应缺 data 与 items → 空表兜底（|| [] 末段）', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles') return Promise.resolve({})
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).tableData).toEqual([])
  })

  it('loadRoles：envelope 形态响应 { items } → 取 items 作为角色列表', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles') return Promise.resolve({ items: [roleAdmin] })
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.tableData).toEqual([
      {
        id: 'r1',
        name: '系统管理员',
        code: '系统管理员',
        description: '最高权限',
        userCount: 1,
        createTime: '2024-01-01',
        status: 'active',
      },
    ])
    expect(vm.pagination.total).toBe(1)
  })

  it('loadRoles：bare 空数组 → 空表且不调用用户数接口', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles') return Promise.resolve({ data: [], total: 0 })
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.tableData).toEqual([])
    expect(vm.pagination.total).toBe(0)
    const userCountCalls = mockGet.mock.calls.filter(
      ([url]) =>
        typeof url === 'string' && url.startsWith('/rbac/roles/') && url.endsWith('/users')
    )
    expect(userCountCalls).toHaveLength(0)
  })

  it('角色用户数接口失败 → userCount 兜底 0', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles/r1/users') return Promise.reject(new Error('404'))
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.tableData[0].userCount).toBe(0)
    expect(vm.tableData[1].userCount).toBe(0)
  })

  it('角色用户数接口返回 { users } 形态 → 取 users 长度', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles/r2/users') return Promise.resolve({ users: [{}, {}] })
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).tableData[1].userCount).toBe(2)
  })

  it('角色用户数接口响应缺 data 与 users → userCount 兜底 0（|| [] 末段）', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles/r1/users') return Promise.resolve({})
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).tableData[0].userCount).toBe(0)
  })

  it('loadPermissions 失败 → 空树并提示', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/permissions') return Promise.reject(new Error('net'))
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.menuTreeData).toEqual([])
    expect(ElMessage.error).toHaveBeenCalledWith('net')
  })

  it('loadPermissions：响应缺 categories → 空树兜底（|| {} 分支），不报错', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/permissions') return Promise.resolve({})
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.menuTreeData).toEqual([])
    expect(ElMessage.error).not.toHaveBeenCalled()
  })
})

describe('搜索 / 重置 / 分页', () => {
  it('搜索表单 v-model 绑定全部可写（el-input / el-select 内联处理器）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    expect(inputs).toHaveLength(5)
    inputs[0].vm.$emit('update:modelValue', '管理员')
    inputs[1].vm.$emit('update:modelValue', 'ADMIN')
    inputs[2].vm.$emit('update:modelValue', '新角色')
    inputs[3].vm.$emit('update:modelValue', 'NEW_ROLE')
    inputs[4].vm.$emit('update:modelValue', '描述文本')
    await nextTick()
    expect(vm.searchForm.name).toBe('管理员')
    expect(vm.searchForm.code).toBe('ADMIN')
    expect(vm.formData.name).toBe('新角色')
    expect(vm.formData.code).toBe('NEW_ROLE')
    expect(vm.formData.description).toBe('描述文本')

    const select = wrapper.findComponent({ name: 'ElSelect' })
    select.vm.$emit('update:modelValue', 'active')
    await nextTick()
    expect(vm.searchForm.status).toBe('active')
  })

  it('点击查询 → 重新加载角色', async () => {
    const wrapper = mountComp()
    await flushPromises()
    mockGet.mockClear()
    await findButtons(wrapper, '查询')[0].trigger('click')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/rbac/roles')
  })

  it('点击重置 → 清空条件并重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchForm.name = 'x'
    vm.searchForm.code = 'y'
    vm.searchForm.status = 'active'
    mockGet.mockClear()
    await findButtons(wrapper, '重置')[0].trigger('click')
    await flushPromises()
    expect(vm.searchForm).toEqual({ name: '', code: '', status: '' })
    expect(mockGet).toHaveBeenCalledWith('/rbac/roles')
  })

  it('分页 v-model:current-page / page-size 内联处理器', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const pager = wrapper.findComponent({ name: 'ElPagination' })
    pager.vm.$emit('update:currentPage', 3)
    pager.vm.$emit('update:pageSize', 50)
    await nextTick()
    expect(vm.pagination.page).toBe(3)
    expect(vm.pagination.size).toBe(50)
  })
})

describe('新增 / 编辑 / 取消 / 提交', () => {
  it('点击新增角色 → 重置表单并打开对话框', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.isEdit = true
    vm.formData.name = 'dirty'
    await findButtons(wrapper, '新增角色')[0].trigger('click')
    expect(vm.isEdit).toBe(false)
    expect(vm.dialogTitle).toBe('新增角色')
    expect(vm.dialogVisible).toBe(true)
    expect(vm.formData).toMatchObject({
      id: '',
      name: '',
      code: '',
      description: '',
      status: 'active',
    })
  })

  it('点击行内编辑 → 填充表单', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findButtons(wrapper, '编辑')[0].trigger('click')
    expect(vm.isEdit).toBe(true)
    expect(vm.dialogTitle).toBe('编辑角色')
    expect(vm.dialogVisible).toBe(true)
    expect(vm.formData.name).toBe('系统管理员')
    expect(vm.formData.status).toBe('active')
  })

  it('点击编辑对话框取消 → handleCancel 关闭', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.dialogVisible = true
    await nextTick()
    // 两个“取消”按钮：[0] 编辑对话框（handleCancel），[1] 权限对话框（内联赋值）
    await findButtons(wrapper, '取消')[0].trigger('click')
    expect(vm.dialogVisible).toBe(false)
  })

  it('el-dialog v-model 内联处理器（三个对话框）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    expect(dialogs).toHaveLength(3)
    dialogs[0].vm.$emit('update:modelValue', true)
    dialogs[1].vm.$emit('update:modelValue', true)
    dialogs[2].vm.$emit('update:modelValue', true)
    await nextTick()
    expect(vm.dialogVisible).toBe(true)
    expect(vm.usersDialogVisible).toBe(true)
    expect(vm.permissionDialogVisible).toBe(true)
    dialogs[0].vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.dialogVisible).toBe(false)
  })

  it('el-switch v-model 绑定 formData.status', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    wrapper.findComponent({ name: 'ElSwitch' }).vm.$emit('update:modelValue', 'inactive')
    await nextTick()
    expect(vm.formData.status).toBe('inactive')
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
    expect(mockPut).not.toHaveBeenCalled()
  })

  it('点击确定提交新增 → POST 并提示已创建', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleAdd()
    vm.formData.name = '数据专员'
    vm.formData.description = '负责数据录入'
    // Vue 重渲染会把模板 ref 重同步为 stub 实例，调用提交前必须重新赋值
    vm.formRef = { validate: (cb: any) => cb(true) }
    mockGet.mockClear()
    await findButtons(wrapper, '确定')[0].trigger('click')
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith('/rbac/roles', {
      name: '数据专员',
      description: '负责数据录入',
      permissions: [],
      is_system: false,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('已创建')
    expect(vm.dialogVisible).toBe(false)
    expect(mockGet).toHaveBeenCalledWith('/rbac/roles')
    expect(vm.saving).toBe(false)
  })

  it('提交编辑（status active）→ PUT is_active=true 并提示已保存', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleEdit({ ...rowA })
    vm.formRef = { validate: (cb: any) => cb(true) }
    await vm.handleSubmit()
    await flushPromises()
    expect(mockPut).toHaveBeenCalledWith('/rbac/roles/r1', {
      name: '系统管理员',
      description: '最高权限',
      is_active: true,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('已保存')
  })

  it('提交编辑（status inactive）→ PUT is_active=false', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleEdit({ ...rowB })
    vm.formRef = { validate: (cb: any) => cb(true) }
    await vm.handleSubmit()
    await flushPromises()
    expect(mockPut).toHaveBeenCalledWith(
      '/rbac/roles/r2',
      expect.objectContaining({ is_active: false })
    )
  })

  it('提交失败 → 错误提示且 saving 复位', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleAdd()
    vm.formRef = { validate: (cb: any) => cb(true) }
    mockPost.mockRejectedValueOnce(new Error('net'))
    await vm.handleSubmit()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
    expect(vm.saving).toBe(false)
  })
})

describe('用户列表对话框', () => {
  it('点击用户数 → 加载关联用户并渲染（v-if=false 侧，ds 脱敏调用）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findButtons(wrapper, '人')[0].trigger('click')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/rbac/roles/r1/users')
    expect(vm.roleUsers).toEqual(roleUsersR1)
    expect(vm.usersDialogVisible).toBe(true)
    expect(vm.loadingUsers).toBe(false)
    expect(vm.currentRole.id).toBe('r1')
    await nextTick()
    expect(dsMock).toHaveBeenCalled()
  })

  it('users 接口返回 { users } 形态 → 兜底取 users', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles/r2/users') return Promise.resolve({ users: [{ username: 'x' }] })
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleViewUsers({ ...rowB })
    expect(vm.roleUsers).toEqual([{ username: 'x' }])
  })

  it('users 接口响应缺 data 与 users → 空数组兜底（|| [] 末段）', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles/r2/users') return Promise.resolve({})
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleViewUsers({ ...rowB })
    expect(vm.roleUsers).toEqual([])
    expect(vm.loadingUsers).toBe(false)
  })

  it('users 接口异常 → 空列表且 loading 复位', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles/r2/users') return Promise.reject(new Error('net'))
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleViewUsers({ ...rowB })
    expect(vm.roleUsers).toEqual([])
    expect(vm.loadingUsers).toBe(false)
  })

  it('空用户列表 → 渲染“暂无关联用户”（v-if=true 侧）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleViewUsers({ ...rowB })
    await flushPromises()
    await nextTick()
    expect(vm.roleUsers).toHaveLength(0)
    expect(wrapper.text()).toContain('暂无关联用户')
  })

  it('点击关闭 → usersDialogVisible 内联赋 false', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.usersDialogVisible = true
    await nextTick()
    await findButtons(wrapper, '关闭')[0].trigger('click')
    expect(vm.usersDialogVisible).toBe(false)
  })
})

describe('删除角色', () => {
  it('有关联用户 → 警告文案确认 → 删除成功并刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    mockGet.mockClear()
    await findButtons(wrapper, '删除')[0].trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('该角色下还有 1 个用户'),
      '警告',
      expect.objectContaining({ type: 'warning', confirmButtonText: '确认删除' })
    )
    expect(mockDel).toHaveBeenCalledWith('/rbac/roles/r1')
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    expect(mockGet).toHaveBeenCalledWith('/rbac/roles')
  })

  it('无关联用户 → 普通提示文案确认 → 删除', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await findButtons(wrapper, '删除')[1].trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('确定删除角色 "观察员" 吗？'),
      '提示',
      expect.objectContaining({ type: 'warning' })
    )
    expect(mockDel).toHaveBeenCalledWith('/rbac/roles/r2')
  })

  it('users 接口返回 { users } 形态 → 按 users 计数确认', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles/r2/users') return Promise.resolve({ users: [{}] })
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete({ ...rowB })
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('该角色下还有 1 个用户'),
      '警告',
      expect.anything()
    )
    expect(mockDel).toHaveBeenCalledWith('/rbac/roles/r2')
  })

  it('删除前 users 接口响应缺 data 与 users → 按 0 人走普通确认（|| [] 末段）', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles/r2/users') return Promise.resolve({})
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete({ ...rowB })
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('确定删除角色 "观察员" 吗？'),
      '提示',
      expect.objectContaining({ type: 'warning' })
    )
    expect(mockDel).toHaveBeenCalledWith('/rbac/roles/r2')
  })

  it('用户取消确认 → 不删除也不报错', async () => {
    confirmMock.mockRejectedValue('cancel')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete({ ...rowA })
    expect(mockDel).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('删除接口失败 → 错误提示', async () => {
    mockDel.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete({ ...rowA })
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })
})

describe('权限配置对话框', () => {
  it('点击行内权限 → 加载已有权限并打开对话框', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findButtons(wrapper, '权限')[0].trigger('click')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/rbac/roles/r1')
    expect(vm.defaultCheckedKeys).toEqual(['user:read'])
    expect(vm.permissionDialogVisible).toBe(true)
    expect(vm.currentRole.id).toBe('r1')
  })

  it('handlePermission：响应缺 permissions → 空数组兜底', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles/r2') return Promise.resolve({ data: { data: {} } })
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handlePermission({ ...rowB })
    expect(vm.defaultCheckedKeys).toEqual([])
    expect(vm.permissionDialogVisible).toBe(true)
  })

  it('handlePermission：接口异常 → 空数组兜底', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles/r2') return Promise.reject(new Error('net'))
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handlePermission({ ...rowB })
    expect(vm.defaultCheckedKeys).toEqual([])
  })

  it('点击全选 / 全不选 → 设置所有叶子 key / 清空', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const setCheckedKeys = vi.fn()
    vm.treeRef = { setCheckedKeys }
    await findButtons(wrapper, '全选')[0].trigger('click')
    expect(setCheckedKeys).toHaveBeenCalledWith(['user:read', 'user:write', undefined])
    setCheckedKeys.mockClear()
    await findButtons(wrapper, '全不选')[0].trigger('click')
    expect(setCheckedKeys).toHaveBeenCalledWith([])
  })

  it('checkAll / uncheckAll：treeRef 为空 → 安全跳过', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.treeRef = null
    vm.checkAll()
    vm.uncheckAll()
    // 不抛异常即通过
  })

  it('savePermissions：currentRole 为空 → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentRole = null
    await vm.savePermissions()
    expect(mockPut).not.toHaveBeenCalled()
  })

  it('点击保存权限 → PUT 勾选 keys 并关闭对话框', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentRole = { ...rowA }
    vm.permissionDialogVisible = true
    vm.treeRef = { getCheckedKeys: () => ['user:read', 'user:write'] }
    await findButtons(wrapper, '保存')[0].trigger('click')
    await flushPromises()
    expect(mockPut).toHaveBeenCalledWith('/rbac/roles/r1', {
      permissions: ['user:read', 'user:write'],
    })
    expect(ElMessage.success).toHaveBeenCalledWith('已保存')
    expect(vm.permissionDialogVisible).toBe(false)
    expect(vm.saving).toBe(false)
  })

  it('savePermissions：treeRef 为空 → 按空数组保存', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentRole = { ...rowA }
    vm.treeRef = null
    await vm.savePermissions()
    expect(mockPut).toHaveBeenCalledWith('/rbac/roles/r1', { permissions: [] })
  })

  it('savePermissions 失败 → 错误提示且 saving 复位', async () => {
    mockPut.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentRole = { ...rowA }
    vm.treeRef = { getCheckedKeys: () => [] }
    await vm.savePermissions()
    expect(ElMessage.error).toHaveBeenCalledWith('权限保存失败')
    expect(vm.saving).toBe(false)
  })

  it('点击权限对话框取消 → permissionDialogVisible 内联赋 false', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.permissionDialogVisible = true
    await nextTick()
    await findButtons(wrapper, '取消')[1].trigger('click')
    expect(vm.permissionDialogVisible).toBe(false)
  })
})
