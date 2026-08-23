/**
 * views/system/UserManagement.vue 补充覆盖（菜单权限配置 L850-928）
 * 覆盖：handleMenuPermission、updateMenuPermAllState、flattenMenuKeys、
 * toggleMenuPermAll、saveMenuPermission 全分支
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

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
} = vi.hoisted(() => {
  return {
    authState: { isAdmin: true },
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
    confirmMock: vi.fn(),
    alertMock: vi.fn(),
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
  }
})

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock, alert: alertMock },
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: mockDel,
  apiRequest: mockApiRequest,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

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

// el-tree stub：提供 setCheckedKeys / getCheckedKeys，受测试控制
const treeState = { checkedKeys: [] as string[] }

const ElTreeStub = {
  name: 'ElTree',
  props: ['data', 'showCheckbox', 'nodeKey'],
  emits: ['update:modelValue'],
  methods: {
    setCheckedKeys(keys: string[]) {
      treeState.checkedKeys = [...keys]
    },
    getCheckedKeys() {
      return [...treeState.checkedKeys]
    },
  },
  template: '<div class="el-tree-stub"><slot /></div>',
}

function mountComp() {
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
          props: ['title', 'modelValue'],
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
        'el-table-column': {
          name: 'ElTableColumn',
          template: '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
          data() {
            return {
              rowA: { id: 1, username: 'admin', full_name: '张三', role: 'admin', is_active: true },
              rowB: { id: 2, username: 'op', full_name: '李四', role: 'user', is_active: false },
            }
          },
        },
        'el-tree': ElTreeStub,
        'el-checkbox': {
          name: 'ElCheckbox',
          template: '<input type="checkbox" class="el-checkbox-stub" />',
          emits: ['update:modelValue', 'change'],
        },
        'el-tabs': { name: 'ElTabs', template: '<div class="el-tabs-stub"><slot /></div>' },
        'el-tab-pane': { name: 'ElTabPane', template: '<div class="el-tab-pane-stub"><slot /></div>' },
        'el-select': { name: 'ElSelect', template: '<div class="el-select-stub"><slot /></div>' },
        'el-option': { name: 'ElOption', template: '<div><slot /></div>' },
        'el-option-group': { name: 'ElOptionGroup', template: '<div><slot /></div>' },
        'el-tree-select': { name: 'ElTreeSelect', template: '<div class="el-tree-select-stub" />' },
        'el-switch': { name: 'ElSwitch', template: '<div class="el-switch-stub" />' },
        'el-divider': { name: 'ElDivider', template: '<div><slot /></div>' },
        'el-empty': { name: 'ElEmpty', template: '<div class="el-empty-stub" />' },
        'el-button': { name: 'ElButton', template: '<button class="el-button-stub"><slot /></button>' },
        'el-table': { name: 'ElTable', template: '<table><slot /></table>' },
        'el-badge': { name: 'ElBadge', template: '<span><slot /></span>' },
        'el-icon': { name: 'ElIcon', template: '<span><slot /></span>' },
        'el-alert': { name: 'ElAlert', template: '<div><slot /></div>' },
        'el-pagination': { name: 'ElPagination', template: '<div />' },
        'el-form': { name: 'ElForm', template: '<form><slot /></form>' },
        'el-form-item': { name: 'ElFormItem', template: '<div><slot /></div>' },
      },
    },
  })
}

const menuTreeData = [
  { key: 'dashboard', label: '首页', children: [{ key: 'dashboard.sub', label: '子页' }] },
  { key: 'funds', label: '资金' },
]

beforeEach(() => {
  vi.resetAllMocks()
  authState.isAdmin = true
  treeState.checkedKeys = []
  mockGet.mockImplementation((url: string) => {
    if (url === '/organizations/tree') return Promise.resolve({ data: [] })
    if (url === '/users/pending/list') return Promise.resolve({ data: [] })
      if (url.includes('/menus/user-menus/')) {
        return Promise.resolve({ data: { menu_keys: ['dashboard', 'dashboard.sub', 'funds'] } })
      }
    if (url === '/menus/all') return Promise.resolve({ data: menuTreeData })
    if (url.includes('/sessions')) return Promise.resolve({ data: { data: [] } })
    return Promise.resolve({ data: {} })
  })
  mockApiRequest.mockResolvedValue({ items: [], total: 0 })
  mockPost.mockResolvedValue({ data: {} })
  mockPut.mockResolvedValue({ data: {} })
  mockDel.mockResolvedValue({ data: {} })
  confirmMock.mockResolvedValue(undefined)
  alertMock.mockResolvedValue(undefined)
  clipWrite.mockResolvedValue(undefined)
  genPwdMock.mockReturnValue('Gen#Pass1')
  normalizeMock.mockImplementation((nodes: any) => nodes)
  dsMock.mockImplementation((v: any) => v)
})

describe('UserManagement.vue 菜单权限配置', () => {
  it('handleMenuPermission：加载用户菜单配置并勾选', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleMenuPermission({ id: 7, username: 'user7' })
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/menus/user-menus/7')
    expect(mockGet).toHaveBeenCalledWith('/menus/all')
    expect(vm.menuPermUser?.username).toBe('user7')
    expect(vm.menuPermDialogVisible).toBe(true)
    expect(vm.menuPermTree.length).toBe(2)
    expect(treeState.checkedKeys).toEqual(['dashboard', 'dashboard.sub', 'funds'])
    expect(vm.menuPermAllChecked).toBe(true)
    expect(vm.menuPermIndeterminate).toBe(false)
    expect(vm.menuPermLoading).toBe(false)
  })

  it('handleMenuPermission：部分勾选 → indeterminate', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/menus/user-menus/')) {
        return Promise.resolve({ data: { menu_keys: ['dashboard'] } })
      }
      if (url === '/menus/all') return Promise.resolve({ data: menuTreeData })
      return Promise.resolve({ data: [] })
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleMenuPermission({ id: 7 })
    expect(treeState.checkedKeys).toEqual(['dashboard'])
    expect(vm.menuPermAllChecked).toBe(false)
    expect(vm.menuPermIndeterminate).toBe(true)
  })

  it('handleMenuPermission：无勾选 → 全不选', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/menus/user-menus/')) return Promise.resolve({ data: {} })
      if (url === '/menus/all') return Promise.resolve({ data: menuTreeData })
      return Promise.resolve({ data: [] })
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleMenuPermission({ id: 7 })
    expect(treeState.checkedKeys).toEqual([])
    expect(vm.menuPermAllChecked).toBe(false)
    expect(vm.menuPermIndeterminate).toBe(false)
  })

  it('handleMenuPermission：接口失败 → 日志 + 错误提示', async () => {
    mockGet.mockRejectedValue({ response: { data: { detail: '权限服务异常' } } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleMenuPermission({ id: 7 })
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('权限服务异常')
    expect(vm.menuPermLoading).toBe(false)
  })

  it('handleMenuPermission：失败无 detail → 默认文案', async () => {
    mockGet.mockRejectedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleMenuPermission({ id: 7 })
    expect(ElMessage.error).toHaveBeenCalledWith('加载菜单权限配置失败')
  })

  it('handleMenuPermission：无树实例 → 跳过勾选', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.menuPermTreeRef = null
    await vm.handleMenuPermission({ id: 7 })
    expect(vm.menuPermTree.length).toBe(2)
  })

  it('handleMenuPermission：配置响应为空 → 空勾选', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/menus/user-menus/')) return Promise.resolve(null)
      if (url === '/menus/all') return Promise.resolve({ data: menuTreeData })
      return Promise.resolve({ data: [] })
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleMenuPermission({ id: 7 })
    expect(treeState.checkedKeys).toEqual([])
    expect(vm.menuPermTree.length).toBe(2)
  })

  it('handleMenuPermission：菜单树响应为空 → 空树', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/menus/user-menus/')) return Promise.resolve({ data: { menu_keys: ['a'] } })
      if (url === '/menus/all') return Promise.resolve(null)
      return Promise.resolve({ data: [] })
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleMenuPermission({ id: 7 })
    expect(vm.menuPermTree).toEqual([])
  })

  it('表格行"菜单权限"按钮点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const btn = wrapper
      .findAll('button')
      .find((b) => b.text().includes('菜单权限'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    await flushPromises()
    expect(vm.menuPermDialogVisible).toBe(true)
    expect(mockGet).toHaveBeenCalledWith('/menus/user-menus/1')
  })

  it('flattenMenuKeys：递归展开', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.flattenMenuKeys(menuTreeData)).toEqual(['dashboard', 'dashboard.sub', 'funds'])
    expect(vm.flattenMenuKeys([])).toEqual([])
  })

  it('toggleMenuPermAll：全选 / 取消全选', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.menuPermTree = menuTreeData
    await vm.handleMenuPermission({ id: 7 })
    vm.toggleMenuPermAll(false)
    expect(treeState.checkedKeys).toEqual([])
    expect(vm.menuPermAllChecked).toBe(false)
    vm.toggleMenuPermAll(true)
    expect(treeState.checkedKeys).toEqual(['dashboard', 'dashboard.sub', 'funds'])
    expect(vm.menuPermAllChecked).toBe(true)
  })

  it('toggleMenuPermAll：无树实例 → 返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.menuPermTreeRef = null
    vm.toggleMenuPermAll(true)
    expect(treeState.checkedKeys).toEqual([])
  })

  it('saveMenuPermission：保存成功', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleMenuPermission({ id: 7, username: 'user7' })
    treeState.checkedKeys = ['dashboard', 'funds']
    await vm.saveMenuPermission()
    expect(mockPut).toHaveBeenCalledWith('/menus/user-menus/7', {
      menu_keys: ['dashboard', 'funds'],
    })
    expect(ElMessage.success).toHaveBeenCalledWith('菜单权限已保存')
    expect(vm.menuPermDialogVisible).toBe(false)
    expect(vm.menuPermSaving).toBe(false)
  })

  it('saveMenuPermission：无用户/无树 → 返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.menuPermUser = null
    await vm.saveMenuPermission()
    expect(mockPut).not.toHaveBeenCalled()
    vm.menuPermUser = { id: 1 }
    vm.menuPermTreeRef = null
    await vm.saveMenuPermission()
    expect(mockPut).not.toHaveBeenCalled()
  })

  it('saveMenuPermission：失败 → 日志 + 错误提示', async () => {
    mockPut.mockRejectedValue({ response: { data: { detail: '保存失败' } } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleMenuPermission({ id: 7 })
    await vm.saveMenuPermission()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
    expect(vm.menuPermSaving).toBe(false)
  })

  it('handleMenuPermission：菜单树响应为对象（非数组）→ Array.isArray 假侧 []', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/menus/user-menus/')) return Promise.resolve({ data: { menu_keys: ['a'] } })
      if (url === '/menus/all') return Promise.resolve({ data: { tree: [{ key: 'x' }] } })
      return Promise.resolve({ data: [] })
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleMenuPermission({ id: 7 })
    expect(vm.menuPermTree).toEqual([])
  })

  it('updateMenuPermAllState：无树实例 → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.menuPermTreeRef = null
    vm.updateMenuPermAllState()
    expect(vm.menuPermAllChecked).toBe(false)
    expect(vm.menuPermIndeterminate).toBe(false)
  })

  it('saveMenuPermission：失败无 detail / 异常为 null → 默认文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleMenuPermission({ id: 7 })
    mockPut.mockRejectedValueOnce({})
    await vm.saveMenuPermission()
    expect(ElMessage.error).toHaveBeenCalledWith('保存菜单权限失败')
    mockPut.mockRejectedValueOnce(null)
    await vm.saveMenuPermission()
    expect(ElMessage.error).toHaveBeenCalledWith('保存菜单权限失败')
    expect(vm.menuPermSaving).toBe(false)
  })

  it('菜单权限对话框：全选复选框点击与关闭', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleMenuPermission({ id: 7 })
    await nextTick()
    // 页面有多个对话框（用户编辑 + 菜单权限），按标题精确定位
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    const dialog = dialogs.find((d) => d.props('title') === '菜单权限配置')!
    dialog.vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.menuPermDialogVisible).toBe(false)
  })
})
