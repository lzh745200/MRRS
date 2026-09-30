/**
 * PermissionAssignmentDrawer.vue 测试
 * stub 子面板（RoleTagsPanel/PermissionTreePanel/MenuVisibilityPanel）与 EP 组件，
 * 覆盖：加载、保存权限（成功/部分失败/失败/抽屉关闭中断）、遗留角色保存、
 * 用户切换、面板刷新事件、暴露方法
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import PermissionAssignmentDrawer from '@/components/permission/PermissionAssignmentDrawer.vue'

enableAutoUnmount(afterEach)

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

const mockGet = mocks.get
const mockPost = mocks.post
const mockPut = mocks.put
const mockMessage = mocks.message

vi.mock('@/api/request', () => ({
  get: (...a: any[]) => mocks.get(...a),
  post: (...a: any[]) => mocks.post(...a),
  put: (...a: any[]) => mocks.put(...a),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('element-plus', () => ({ ElMessage: mocks.message }))

const user = {
  id: 1,
  username: 'zhangsan',
  role: 'admin',
  data_scope: 'org',
}

const ElDrawerStub = {
  props: ['modelValue', 'title'],
  emits: ['update:modelValue', 'close'],
  template:
    '<div v-if="modelValue" class="stub-drawer"><button class="drawer-close" @click="$emit(\'close\')">x</button><slot /></div>',
}

const ElTabsStub = {
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<div class="stub-tabs"><slot /></div>',
}

const ElTabPaneStub = {
  props: ['label', 'name'],
  template: '<div class="stub-tabpane"><slot /></div>',
}

const ElButtonStub = {
  props: {
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    type: String,
  },
  emits: ['click'],
  template:
    '<button class="stub-btn" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
}

const ElSelectStub = {
  props: ['modelValue', 'placeholder'],
  emits: ['update:modelValue', 'change'],
  methods: {
    onChange(e: Event) {
      const val = (e.target as HTMLSelectElement).value
      this.$emit('update:modelValue', val)
      this.$emit('change', val)
    },
  },
  template: '<select class="stub-select" :value="modelValue" @change="onChange"><slot /></select>',
}

const ElOptionStub = {
  props: ['label', 'value'],
  template: '<option :value="value">{{ label }}</option>',
}

const RoleTagsPanelStub = {
  name: 'RoleTagsPanelStub',
  props: ['userId', 'allRoles'],
  emits: ['assigned', 'removed'],
  methods: { loadAssignedRoles: vi.fn() },
  template:
    '<div class="stub-roles"><button class="emit-assigned" @click="$emit(\'assigned\')">assigned</button><button class="emit-removed" @click="$emit(\'removed\')">removed</button></div>',
}

const PermissionTreePanelStub = {
  name: 'PermissionTreePanelStub',
  props: ['permissions', 'disabled'],
  emits: ['change'],
  template:
    '<div class="stub-perm"><button class="tree-change" @click="$emit(\'change\', [\'user:read\', \'project:read\'])">change</button></div>',
}

const MenuVisibilityPanelStub = {
  name: 'MenuVisibilityPanelStub',
  props: ['userId', 'username', 'role', 'roleDefaultKeys', 'isCustomized', 'currentMenuKeys'],
  emits: ['saved'],
  template:
    '<div class="stub-menu"><button class="menu-saved" @click="$emit(\'saved\')">saved</button></div>',
}

function setupDefaultMocks() {
  mockGet.mockImplementation((url: string) => {
    if (url === '/rbac/roles') return Promise.resolve({ data: [{ id: 'r1', name: '管理员' }] })
    if (url.includes('/rbac/user/1/permissions')) {
      return Promise.resolve({ data: { permissions: ['user:read'] } })
    }
    if (url.includes('/menus/user-menus/1')) {
      return Promise.resolve({
        data: { menu_keys: ['dashboard'], is_customized: true, role_default_keys: ['dashboard'] },
      })
    }
    return Promise.resolve({})
  })
  mockPost.mockResolvedValue({ success: true, granted: [], revoked: [], skipped: [], failed: [] })
  mockPut.mockResolvedValue({})
}

function mountDrawer(props: Record<string, unknown> = {}) {
  return mount(PermissionAssignmentDrawer, {
    props: { modelValue: true, ...props },
    global: {
      stubs: {
        'el-drawer': ElDrawerStub,
        'el-tabs': ElTabsStub,
        'el-tab-pane': ElTabPaneStub,
        'el-button': ElButtonStub,
        'el-select': ElSelectStub,
        'el-option': ElOptionStub,
        'el-alert': { template: '<div class="stub-alert"><slot /></div>' },
        'el-form': { template: '<form class="stub-form"><slot /></form>' },
        'el-form-item': { template: '<div class="stub-form-item"><slot /></div>' },
        RoleTagsPanel: RoleTagsPanelStub,
        PermissionTreePanel: PermissionTreePanelStub,
        MenuVisibilityPanel: MenuVisibilityPanelStub,
      },
    },
  })
}

function btn(wrapper: any, text: string) {
  return wrapper
    .findAll('button.stub-btn')
    .find((b: any) => b.text().trim() === text || (b.text().includes(text) && text !== '保存'))
}

describe('PermissionAssignmentDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupDefaultMocks()
  })

  it('打开抽屉：加载角色/权限/菜单配置并传给子面板', async () => {
    const wrapper = mountDrawer({ user })
    await flushPromises()

    expect(mockGet).toHaveBeenCalledWith('/rbac/roles')
    expect(mockGet).toHaveBeenCalledWith('/rbac/user/1/permissions')
    expect(mockGet).toHaveBeenCalledWith('/menus/user-menus/1')

    const menuProps = wrapper.findComponent({ name: 'MenuVisibilityPanelStub' }).props()
    expect(menuProps.userId).toBe(1)
    expect(menuProps.username).toBe('zhangsan')
    expect(menuProps.role).toBe('admin')
    expect(menuProps.roleDefaultKeys).toEqual(['dashboard'])
    expect(menuProps.isCustomized).toBe(true)
    expect(menuProps.currentMenuKeys).toEqual(['dashboard'])

    expect(wrapper.findComponent({ name: 'PermissionTreePanelStub' }).props('permissions')).toEqual(
      ['user:read']
    )
    expect(wrapper.findComponent({ name: 'RoleTagsPanelStub' }).props('allRoles')).toEqual([
      { id: 'r1', name: '管理员' },
    ])
  })

  it('无 user 时不发起加载请求；保存函数提前返回', async () => {
    const wrapper = mountDrawer({ user: null })
    await flushPromises()
    expect(mockGet).not.toHaveBeenCalled()

    const state = (wrapper.vm as any).$.setupState
    await state.savePermissions()
    expect(mockPost).not.toHaveBeenCalled()
    await state.saveLegacyRole()
    expect(mockPut).not.toHaveBeenCalled()
  })

  it('权限加载失败：显示告警、禁用保存、savePermissions 提前返回', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/permissions')) return Promise.reject(new Error('boom'))
      if (url === '/rbac/roles') return Promise.resolve({ data: [{ id: 'r1', name: '管理员' }] })
      return Promise.resolve({ data: null })
    })
    const wrapper = mountDrawer({ user })
    await flushPromises()

    expect(wrapper.text()).toContain('权限数据加载失败')
    const saveBtn = btn(wrapper, '保存权限')!
    expect(saveBtn.attributes('disabled')).toBeDefined()

    await (wrapper.vm as any).$.setupState.savePermissions()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('loadAllRoles 返回无 data 结构时安全处理', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles') return Promise.resolve([{ id: 'r1', name: '管理员' }])
      return Promise.resolve({})
    })
    const wrapper = mountDrawer({ user })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'RoleTagsPanelStub' }).props('allRoles')).toEqual([
      { id: 'r1', name: '管理员' },
    ])

    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles') return Promise.resolve(0)
      return Promise.resolve({})
    })
    const wrapper2 = mountDrawer({ user })
    await flushPromises()
    expect(wrapper2.findComponent({ name: 'RoleTagsPanelStub' }).props('allRoles')).toEqual([])
  })

  it('loadCurrentPermissions 兼容数组/非数组/无数据', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/permissions')) return Promise.resolve({ data: ['a:read', 'b:write'] })
      return Promise.resolve({})
    })
    const wrapper = mountDrawer({ user })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'PermissionTreePanelStub' }).props('permissions')).toEqual(
      ['a:read', 'b:write']
    )

    mockGet.mockImplementation((url: string) => {
      if (url.includes('/permissions'))
        return Promise.resolve({ data: { permissions: 'not-array' } })
      return Promise.resolve({})
    })
    const wrapper2 = mountDrawer({ user })
    await flushPromises()
    expect(
      wrapper2.findComponent({ name: 'PermissionTreePanelStub' }).props('permissions')
    ).toEqual([])
  })

  it('loadMenuConfig 无数据或失败时回退', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/user-menus')) return Promise.resolve({ data: null })
      return Promise.resolve({})
    })
    const wrapper = mountDrawer({ user })
    await flushPromises()
    const p = wrapper.findComponent({ name: 'MenuVisibilityPanelStub' }).props()
    expect(p.currentMenuKeys).toEqual([])

    mockGet.mockImplementation((url: string) => {
      if (url.includes('/user-menus')) return Promise.reject(new Error('net'))
      return Promise.resolve({})
    })
    const wrapper2 = mountDrawer({ user })
    await flushPromises()
    expect(
      wrapper2.findComponent({ name: 'MenuVisibilityPanelStub' }).props('currentMenuKeys')
    ).toEqual([])
  })

  it('用户切换：重新加载并重置遗留表单', async () => {
    const wrapper = mountDrawer({ user })
    await flushPromises()
    const user2 = { id: 2, username: 'lisi', role: 'user', data_scope: 'self' }
    await wrapper.setProps({ user: user2 })
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/rbac/user/2/permissions')
    expect(mockGet).toHaveBeenCalledWith('/menus/user-menus/2')
    expect(wrapper.findComponent({ name: 'MenuVisibilityPanelStub' }).props('userId')).toBe(2)
  })

  it('挂载后 200ms 调用 RoleTagsPanel.loadAssignedRoles', async () => {
    vi.useFakeTimers()
    const wrapper = mountDrawer({ user })
    await flushPromises()
    // 断言目标：定时器推进后子面板的 loadAssignedRoles 被调用
    // （实例代理会把方法 bind 成新函数，故直接引用 stub 定义里的 vi.fn）
    vi.advanceTimersByTime(300)
    await flushPromises()
    vi.useRealTimers()
    expect(RoleTagsPanelStub.methods.loadAssignedRoles).toHaveBeenCalled()
    void wrapper
  })

  it('保存权限成功：完整成功消息 + emit saved', async () => {
    mockPost.mockResolvedValue({
      success: true,
      granted: ['a'],
      revoked: ['b'],
      skipped: ['c'],
      failed: [],
    })
    const wrapper = mountDrawer({ user })
    await flushPromises()
    await btn(wrapper, '保存权限')!.trigger('click')
    await flushPromises()

    expect(mockPost).toHaveBeenCalledWith('/rbac/save-permissions', {
      user_id: 1,
      permissions: ['user:read'],
    })
    expect(mockMessage.success).toHaveBeenCalledWith(
      '权限保存成功 (授予 1 项) (撤销 1 项) (1 项已存在，已跳过)'
    )
    expect(wrapper.emitted('saved')).toHaveLength(1)
  })

  it('保存权限成功：granted/revoked/skipped 缺省时默认空数组', async () => {
    mockPost.mockResolvedValue({
      success: true,
      failed: [],
    })
    const wrapper = mountDrawer({ user })
    await flushPromises()
    await btn(wrapper, '保存权限')!.trigger('click')
    await flushPromises()
    expect(mockMessage.success).toHaveBeenCalledWith('权限保存成功')
    expect(wrapper.emitted('saved')).toHaveLength(1)
  })

  it('保存权限部分失败：warning 消息', async () => {
    mockPost.mockResolvedValue({
      success: true,
      granted: [],
      revoked: [],
      skipped: [],
      failed: ['x', 'y'],
    })
    const wrapper = mountDrawer({ user })
    await flushPromises()
    await btn(wrapper, '保存权限')!.trigger('click')
    await flushPromises()
    expect(mockMessage.warning).toHaveBeenCalledWith('权限保存部分失败: x, y')
  })

  it('保存权限 success=false：error 消息（message/detail/默认）', async () => {
    mockPost.mockResolvedValueOnce({ success: false, message: '保存失败msg' })
    const wrapper = mountDrawer({ user })
    await flushPromises()
    await btn(wrapper, '保存权限')!.trigger('click')
    await flushPromises()
    expect(mockMessage.error).toHaveBeenCalledWith('保存失败msg')

    mockPost.mockResolvedValueOnce({ success: false, detail: '保存失败detail' })
    await btn(wrapper, '保存权限')!.trigger('click')
    await flushPromises()
    expect(mockMessage.error).toHaveBeenCalledWith('保存失败detail')

    mockPost.mockResolvedValueOnce({ success: false })
    await btn(wrapper, '保存权限')!.trigger('click')
    await flushPromises()
    expect(mockMessage.error).toHaveBeenCalledWith('权限保存失败')
  })

  it('保存权限请求异常：error 消息（detail/默认）', async () => {
    mockPost.mockRejectedValueOnce({ response: { data: { detail: '请求失败' } } })
    const wrapper = mountDrawer({ user })
    await flushPromises()
    await btn(wrapper, '保存权限')!.trigger('click')
    await flushPromises()
    expect(mockMessage.error).toHaveBeenCalledWith('请求失败')

    mockPost.mockRejectedValueOnce(new Error('x'))
    await btn(wrapper, '保存权限')!.trigger('click')
    await flushPromises()
    expect(mockMessage.error).toHaveBeenCalledWith('权限保存失败')
  })

  it('保存期间抽屉关闭：中止后续操作', async () => {
    let resolvePost!: (v: any) => void
    mockPost.mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolvePost = r
        })
    )
    const wrapper = mountDrawer({ user })
    await flushPromises()

    const p = (wrapper.vm as any).$.setupState.savePermissions()
    await flushPromises()
    await wrapper.setProps({ modelValue: false })
    resolvePost({ success: true, granted: ['a'], failed: [] })
    await p
    await flushPromises()

    expect(mockMessage.success).not.toHaveBeenCalled()
    expect(wrapper.emitted('saved')).toBeUndefined()
  })

  it('遗留角色保存：选择后保存成功 emit saved', async () => {
    const wrapper = mountDrawer({ user })
    await flushPromises()
    const selects = wrapper.findAll('select.stub-select')
    await selects[0].setValue('admin')
    await selects[1].setValue('self')
    await btn(wrapper, '保存')!.trigger('click')
    await flushPromises()

    expect(mockPut).toHaveBeenCalledWith('/users/1/permissions', {
      role: 'admin',
      data_scope: 'self',
    })
    expect(mockMessage.success).toHaveBeenCalledWith('系统角色保存成功')
    expect(wrapper.emitted('saved')).toHaveLength(1)
  })

  it('遗留角色保存失败：error 消息（detail/默认）', async () => {
    mockPut.mockRejectedValueOnce({ response: { data: { detail: '遗留失败' } } })
    const wrapper = mountDrawer({ user })
    await flushPromises()
    await btn(wrapper, '保存')!.trigger('click')
    await flushPromises()
    expect(mockMessage.error).toHaveBeenCalledWith('遗留失败')

    mockPut.mockRejectedValueOnce(new Error('x'))
    await btn(wrapper, '保存')!.trigger('click')
    await flushPromises()
    expect(mockMessage.error).toHaveBeenCalledWith('保存失败')
  })

  it('抽屉关闭：handleClose 触发 update:modelValue=false', async () => {
    const wrapper = mountDrawer({ user })
    await flushPromises()
    await wrapper.find('button.drawer-close').trigger('click')
    expect(wrapper.emitted('update:modelValue')!.at(-1)![0]).toBe(false)
    // 父组件收到 update:modelValue 后回写 prop → 抽屉卸载
    await wrapper.setProps({ modelValue: false })
    expect(wrapper.find('.stub-drawer').exists()).toBe(false)
  })

  it('子面板事件：assigned/removed 刷新权限，saved 刷新菜单', async () => {
    const wrapper = mountDrawer({ user })
    await flushPromises()
    mockGet.mockClear()

    await wrapper.find('button.emit-assigned').trigger('click')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/rbac/user/1/permissions')

    mockGet.mockClear()
    await wrapper.find('button.menu-saved').trigger('click')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/menus/user-menus/1')
  })

  it('权限树 change：更新 currentPermissions 并随保存提交', async () => {
    const wrapper = mountDrawer({ user })
    await flushPromises()
    await wrapper.find('button.tree-change').trigger('click')
    await btn(wrapper, '保存权限')!.trigger('click')
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith('/rbac/save-permissions', {
      user_id: 1,
      permissions: ['user:read', 'project:read'],
    })
  })

  it('暴露 refreshAll 方法', async () => {
    const wrapper = mountDrawer({ user })
    await flushPromises()
    mockGet.mockClear()
    await (wrapper.vm as any).refreshAll()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/rbac/user/1/permissions')
    expect(mockGet).toHaveBeenCalledWith('/menus/user-menus/1')
  })

  it('loadAllRoles 失败 → 空列表兜底', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles') return Promise.reject(new Error('boom'))
      return Promise.resolve({ data: [] })
    })
    const wrapper = mountDrawer({ user })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.allRoles).toEqual([])
  })

  it('user 缺 role/data_scope → 默认 user/org（watch 分支）', async () => {
    vi.useFakeTimers()
    mockGet.mockImplementation(() => Promise.resolve({ data: [] }))
    const wrapper = mountDrawer({ user: { id: 2, username: 'lisi' } })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.legacyForm.role).toBe('user')
    expect(vm.legacyForm.data_scope).toBe('org')
    // 推进 200ms 触发 loadAssignedRoles 回调
    await vi.advanceTimersByTimeAsync(200)
    vi.useRealTimers()
  })

  it('user 无 id → 权限/菜单加载早退', async () => {
    mockGet.mockImplementation(() => Promise.resolve({ data: [] }))
    const wrapper = mountDrawer({ user: { username: 'noid' } })
    await flushPromises()
    expect(mockGet).not.toHaveBeenCalledWith('/rbac/user/undefined/permissions')
    const vm = wrapper.vm as any
    expect(vm.currentPermissions).toEqual([])
    expect(vm.currentMenuKeys).toEqual([])
  })

  it('权限响应无 permissions 字段 → 空数组', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/permissions')) return Promise.resolve({ data: { foo: 1 } })
      if (url.includes('/user-menus')) return Promise.resolve({ data: { menu_keys: ['a'] } })
      return Promise.resolve({ data: [] })
    })
    const wrapper = mountDrawer({ user })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.currentPermissions).toEqual([])
  })

  it('模板 v-model 内联 handler：el-drawer / el-tabs 触发 update:modelValue', async () => {
    const wrapper = mountDrawer({ user })
    await flushPromises()

    await wrapper.findComponent(ElDrawerStub).vm.$emit('update:modelValue', false)
    expect(wrapper.emitted('update:modelValue')!.at(-1)![0]).toBe(false)

    await wrapper.findComponent(ElTabsStub).vm.$emit('update:modelValue', 'menus')
    expect((wrapper.vm as any).activeTab).toBe('menus')
  })

  it('loadCurrentPermissions：权限响应为 0 → payload 两假侧兜底空数组', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/permissions')) return Promise.resolve(0)
      return Promise.resolve({ data: [] })
    })
    const wrapper = mountDrawer({ user })
    await flushPromises()
    expect((wrapper.vm as any).currentPermissions).toEqual([])
  })

  it('保存权限：res 为假值/空对象 → res || {} 兜底 + 默认错误提示', async () => {
    mockPost.mockResolvedValueOnce({})
    const wrapper = mountDrawer({ user })
    await flushPromises()
    await btn(wrapper, '保存权限')!.trigger('click')
    await flushPromises()
    expect(mockMessage.error).toHaveBeenCalledWith('权限保存失败')

    mockPost.mockResolvedValueOnce(null)
    await btn(wrapper, '保存权限')!.trigger('click')
    await flushPromises()
    expect(mockMessage.error).toHaveBeenCalledWith('权限保存失败')
  })

  it('保存权限成功：failed 字段缺失 → data.failed || [] 兜底', async () => {
    mockPost.mockResolvedValueOnce({ success: true, granted: [], revoked: [], skipped: [] })
    const wrapper = mountDrawer({ user })
    await flushPromises()
    await btn(wrapper, '保存权限')!.trigger('click')
    await flushPromises()
    expect(mockMessage.success).toHaveBeenCalledWith('权限保存成功')
  })

  // ── 用户切换竞态（A 的权限不得写到 B / 不得覆盖 B）──

  it('用户切换：A 的慢权限响应被丢弃，不覆盖 B 的数据', async () => {
    let resolveA!: (v: any) => void
    const pendingA = new Promise((r) => {
      resolveA = r
    })
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/user/1/permissions') return pendingA
      if (url.includes('/permissions'))
        return Promise.resolve({ data: { permissions: ['b:read'] } })
      if (url.includes('/user-menus')) return Promise.resolve({ data: { menu_keys: ['b-menu'] } })
      return Promise.resolve({ data: [] })
    })
    const wrapper = mountDrawer({ user })
    await flushPromises()

    // 切到用户 2，B 的响应先到
    await wrapper.setProps({ user: { id: 2, username: 'lisi' } })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.currentPermissions).toEqual(['b:read'])
    expect(vm.currentMenuKeys).toEqual(['b-menu'])
    expect(vm.loadedPermissionsUserId).toBe(2)

    // A 的响应姗姗来迟 → 必须被丢弃
    resolveA({ data: { permissions: ['a:read'] } })
    await flushPromises()
    expect(vm.currentPermissions).toEqual(['b:read'])
    expect(vm.loadedPermissionsUserId).toBe(2)
  })

  it('用户切换：A 的慢菜单配置响应被丢弃；慢角色列表响应也被丢弃', async () => {
    let resolveMenu!: (v: any) => void
    let resolveRoles!: (v: any) => void
    const pendingMenu = new Promise((r) => {
      resolveMenu = r
    })
    const pendingRoles = new Promise((r) => {
      resolveRoles = r
    })
    let rolesCall = 0
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles') {
        rolesCall += 1
        // 第一次（用户 1）挂起不返回；切换后的第二次立即返回 B 的角色
        return rolesCall === 1 ? pendingRoles : Promise.resolve([{ id: 'r-b', name: 'B 角色' }])
      }
      if (url === '/menus/user-menus/1') return pendingMenu
      if (url.includes('/user-menus')) return Promise.resolve({ data: { menu_keys: ['b-menu'] } })
      if (url.includes('/permissions'))
        return Promise.resolve({ data: { permissions: ['b:read'] } })
      return Promise.resolve({ data: [] })
    })
    const wrapper = mountDrawer({ user })
    await flushPromises()

    await wrapper.setProps({ user: { id: 2, username: 'lisi' } })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.currentMenuKeys).toEqual(['b-menu'])
    expect(vm.allRoles).toEqual([{ id: 'r-b', name: 'B 角色' }])

    // A 的过期响应回来 → 一律丢弃
    resolveMenu({ data: { menu_keys: ['a-menu'], is_customized: true } })
    resolveRoles([{ id: 'r-a', name: 'A 角色' }])
    await flushPromises()
    expect(vm.currentMenuKeys).toEqual(['b-menu'])
    expect(vm.isMenuCustomized).toBe(false)
    expect(vm.allRoles).toEqual([{ id: 'r-b', name: 'B 角色' }])
  })

  it('用户切换时立即清空上一个用户的残留状态', async () => {
    const wrapper = mountDrawer({ user })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.currentPermissions).toEqual(['user:read'])
    expect(vm.currentMenuKeys).toEqual(['dashboard'])

    // B 的请求永不返回 → 面板必须保持"空 + 禁止保存"，而不是显示 A 的数据
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/permissions') || url.includes('/user-menus')) return new Promise(() => {})
      return Promise.resolve({ data: [] })
    })
    await wrapper.setProps({ user: { id: 2, username: 'lisi' } })
    await flushPromises()
    expect(vm.currentPermissions).toEqual([])
    expect(vm.currentMenuKeys).toEqual([])
    expect(vm.loadedPermissionsUserId).toBeNull()
  })

  it('保存权限：数据尚未加载完成（属于其他用户）时拒绝保存', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles') return Promise.resolve({ data: [] })
      if (url === '/rbac/user/1/permissions')
        return Promise.resolve({ data: { permissions: ['a:read'] } })
      if (url === '/rbac/user/2/permissions') return new Promise(() => {})
      if (url.includes('/user-menus')) return Promise.resolve({ data: { menu_keys: [] } })
      return Promise.resolve({ data: [] })
    })
    const wrapper = mountDrawer({ user })
    await flushPromises()

    await wrapper.setProps({ user: { id: 2, username: 'lisi' } })
    await flushPromises()
    mockPost.mockClear()
    mockMessage.error.mockClear()

    await (wrapper.vm as any).$.setupState.savePermissions()
    expect(mockPost).not.toHaveBeenCalled()
    expect(mockMessage.error).toHaveBeenCalledWith('权限数据尚未加载完成，请稍后重试')
  })

  it('保存期间用户切换：丢弃结果、不提示成功、不再发 saved', async () => {
    let resolvePost!: (v: any) => void
    mockPost.mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolvePost = r
        })
    )
    const wrapper = mountDrawer({ user })
    await flushPromises()

    const p = (wrapper.vm as any).$.setupState.savePermissions()
    await flushPromises()
    // 请求在途时切到用户 2
    await wrapper.setProps({ user: { id: 2, username: 'lisi' } })
    await flushPromises()
    resolvePost({ success: true, granted: ['a'], failed: [] })
    await p
    await flushPromises()

    expect(mockMessage.success).not.toHaveBeenCalled()
    expect(wrapper.emitted('saved')).toBeUndefined()
  })

  it('遗留角色保存期间用户切换：成功与失败结果都被丢弃', async () => {
    let resolvePut!: (v: any) => void
    mockPut.mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolvePut = r
        })
    )
    const wrapper = mountDrawer({ user })
    await flushPromises()
    const state = (wrapper.vm as any).$.setupState

    const p1 = state.saveLegacyRole()
    await flushPromises()
    await wrapper.setProps({ user: { id: 2, username: 'lisi' } })
    await flushPromises()
    resolvePut({ code: 200 })
    await p1
    await flushPromises()
    expect(mockMessage.success).not.toHaveBeenCalled()
    expect(wrapper.emitted('saved')).toBeUndefined()

    // 失败也必须在用户已切换时静默丢弃（不把上一个用户的错误弹给新用户）
    mockPut.mockClear()
    mockMessage.error.mockClear()
    let rejectPut!: (e: any) => void
    mockPut.mockImplementationOnce(
      () =>
        new Promise((_r, rej) => {
          rejectPut = rej
        })
    )
    const p2 = state.saveLegacyRole()
    await flushPromises()
    await wrapper.setProps({ user: { id: 3, username: 'wangwu' } })
    await flushPromises()
    rejectPut({ response: { data: { detail: '上一个用户的失败' } } })
    await p2
    await flushPromises()
    expect(mockMessage.error).not.toHaveBeenCalled()
  })

  it('用户切换后 B 的权限加载失败：标记失败并清空（不残留 A 的数据）', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/rbac/roles') return Promise.resolve({ data: [] })
      if (url === '/rbac/user/1/permissions')
        return Promise.resolve({ data: { permissions: ['a:read'] } })
      if (url === '/rbac/user/2/permissions') return Promise.reject(new Error('boom'))
      if (url === '/menus/user-menus/2') return Promise.reject(new Error('boom'))
      return Promise.resolve({ data: {} })
    })
    const wrapper = mountDrawer({ user })
    await flushPromises()
    await wrapper.setProps({ user: { id: 2, username: 'lisi' } })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.permissionsLoadFailed).toBe(true)
    expect(vm.currentPermissions).toEqual([])
    expect(vm.loadedPermissionsUserId).toBeNull()
    expect(vm.currentMenuKeys).toEqual([])
  })

  it('refreshPermissions/refreshAll 使用当前用户重新加载（非过期序号）', async () => {
    const wrapper = mountDrawer({ user })
    await flushPromises()
    mockGet.mockClear()
    await wrapper.find('button.emit-assigned').trigger('click')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/rbac/user/1/permissions')
    // 重新加载结果被采纳
    expect((wrapper.vm as any).loadedPermissionsUserId).toBe(1)
  })
})
