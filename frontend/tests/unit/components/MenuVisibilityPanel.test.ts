/**
 * MenuVisibilityPanel.vue 测试
 * 覆盖：菜单树加载、用户菜单配置加载、勾选回调、恢复默认、保存配置、错误回退
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import MenuVisibilityPanel from '@/components/permission/MenuVisibilityPanel.vue'

enableAutoUnmount(afterEach)

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  put: vi.fn(),
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

const mockGet = mocks.get
const mockPut = mocks.put
const mockMessage = mocks.message

vi.mock('@/api/request', () => ({
  get: (...a: any[]) => mocks.get(...a),
  put: (...a: any[]) => mocks.put(...a),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('element-plus', () => ({ ElMessage: mocks.message }))

vi.mock('@/config/menu-config', () => ({
  MENU_CONFIG: [{ key: 'fallback', label: '回退菜单' }],
}))

const menuTree = [
  { key: 'dashboard', label: '仪表盘' },
  { key: 'management', label: '业务管理', children: [{ key: 'village', label: '帮扶村' }] },
]

const ElButtonStub = {
  props: {
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    type: String,
    size: String,
  },
  emits: ['click'],
  template: '<button class="stub-btn" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
}

const ElTreeStub = {
  name: 'ElTreeStub',
  props: ['data', 'defaultCheckedKeys', 'showCheckbox'],
  emits: ['check'],
  methods: {
    onCheck() {
      this.$emit('check', null, this.payload)
    },
  },
  template:
    '<div class="stub-tree"><button class="tree-check" @click="onCheck">check</button></div>',
}

function treeStubWith(payload: any) {
  return {
    name: 'ElTreeStub',
    props: ['data', 'defaultCheckedKeys', 'showCheckbox'],
    emits: ['check'],
    data: () => ({ payload }),
    methods: {
      onCheck() {
        this.$emit('check', null, this.payload)
      },
    },
    template:
      '<div class="stub-tree"><button class="tree-check" @click="onCheck">check</button></div>',
  }
}

function mountPanel(props: Record<string, unknown> = {}, treeStub = ElTreeStub) {
  return mount(MenuVisibilityPanel, {
    props,
    global: {
      stubs: {
        'el-tree': treeStub,
        'el-button': ElButtonStub,
        'el-alert': { template: '<div class="stub-alert"><slot /></div>' },
        'el-space': { template: '<div class="stub-space"><slot /></div>' },
        'el-tag': { template: '<span class="stub-tag"><slot /></span>' },
      },
    },
  })
}

describe('MenuVisibilityPanel.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGet.mockImplementation((url: string) => {
      if (url === '/menus/all') return Promise.resolve({ data: menuTree })
      if (url.includes('/menus/user-menus/')) {
        return Promise.resolve({ data: { menu_keys: ['dashboard'], is_customized: true } })
      }
      return Promise.resolve({})
    })
    mockPut.mockResolvedValue({})
  })

  it('加载菜单树与自定义配置，渲染角色默认标签与提示', async () => {
    const wrapper = mountPanel({
      userId: 7,
      username: '张三',
      role: 'admin',
      roleDefaultKeys: ['dashboard', 'village'],
      isCustomized: true,
    })
    await flushPromises()

    expect(mockGet).toHaveBeenCalledWith('/menus/all')
    expect(mockGet).toHaveBeenCalledWith('/menus/user-menus/7')
    expect(wrapper.text()).toContain('张三')
    expect(wrapper.text()).toContain('当前为自定义配置。角色默认包含 2 个菜单。')

    const tags = wrapper.findAll('span.stub-tag')
    expect(tags).toHaveLength(2)
    expect(tags[0].text()).toBe('仪表盘')
    expect(tags[1].text()).toBe('帮扶村')

    // 自定义配置 → defaultCheckedKeys 为用户配置
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual(['dashboard'])
  })

  it('无自定义配置（menu_keys 为 null）时使用角色默认菜单', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/menus/all') return Promise.resolve({ data: menuTree })
      return Promise.resolve({ data: { menu_keys: null } })
    })
    const wrapper = mountPanel({
      userId: 7,
      username: '张三',
      roleDefaultKeys: ['village'],
      isCustomized: false,
    })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual(['village'])
    // 未自定义 → 恢复按钮禁用
    expect(wrapper.findAll('button.stub-btn')[0].attributes('disabled')).toBeDefined()
    // 无自定义提示（roleDefaultKeys.length || 0 的 0 分支）
    expect(wrapper.text()).not.toContain('当前为自定义配置')
  })

  it('loadUserMenuConfig 失败时回退 currentMenuKeys', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/menus/all') return Promise.resolve({ data: menuTree })
      return Promise.reject(new Error('net'))
    })
    const wrapper = mountPanel({ userId: 7, username: 'x', currentMenuKeys: ['management'] })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual(['management'])
  })

  it('loadMenuTree 失败时回退前端 MENU_CONFIG', async () => {
    mockGet.mockRejectedValue(new Error('boom'))
    const wrapper = mountPanel({ userId: 7, username: 'x' })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('data')).toEqual([
      { key: 'fallback', label: '回退菜单' },
    ])
  })

  it('loadMenuTree 与 MENU_CONFIG 均失败时为空列表', async () => {
    mockGet.mockRejectedValue(new Error('boom'))
    vi.doMock('@/config/menu-config', () => {
      throw new Error('config load failed')
    })
    const wrapper = mountPanel({ userId: 7, username: 'x' })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('data')).toEqual([])
    vi.doUnmock('@/config/menu-config')
  })

  it('loadMenuTree 返回无 data 结构时安全处理', async () => {
    mockGet.mockResolvedValueOnce([{ key: 'direct', label: '直接数组' }])
    const wrapper = mountPanel({ userId: 7, username: 'x' })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('data')).toEqual([
      { key: 'direct', label: '直接数组' },
    ])

    mockGet.mockResolvedValueOnce(0)
    const wrapper2 = mountPanel({ userId: 7, username: 'x' })
    await flushPromises()
    expect(wrapper2.findComponent({ name: 'ElTreeStub' }).props('data')).toEqual([])
  })

  it('无 userId 时 loadUserMenuConfig 提前返回', async () => {
    const wrapper = mountPanel({ username: 'x' })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([])
  })

  it('树勾选回调（checkedKeys 对象 / 原始数组）', async () => {
    const wrapper = mountPanel(
      { userId: 7, username: 'x', roleDefaultKeys: [] },
      treeStubWith({ checkedKeys: ['dashboard', 'village'] })
    )
    await flushPromises()
    await wrapper.find('button.tree-check').trigger('click')
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'dashboard',
      'village',
    ])

    const wrapper2 = mountPanel({ userId: 7, username: 'x' }, treeStubWith(['management']))
    await flushPromises()
    await wrapper2.find('button.tree-check').trigger('click')
    expect(wrapper2.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'management',
    ])
  })

  // ── 2026-09-30 深审修复：半选父键丢失 ──

  it('勾选子菜单（父节点半选）→ 父键一并保存（后端 _filter_menu_tree 要求父键在白名单内）', async () => {
    const wrapper = mountPanel(
      { userId: 7, username: 'x', isCustomized: true, roleDefaultKeys: [] },
      treeStubWith({ checkedKeys: ['village'], halfCheckedKeys: ['management'] })
    )
    await flushPromises()
    await wrapper.find('button.tree-check').trigger('click')
    await flushPromises()
    await wrapper.findAll('button.stub-btn')[1].trigger('click')
    await flushPromises()

    expect(mockPut).toHaveBeenCalledWith('/menus/user-menus/7', {
      menu_keys: expect.arrayContaining(['village', 'management']),
    })
    const saved = (mockPut.mock.calls.at(-1)![1] as any).menu_keys as string[]
    expect(saved).toHaveLength(2)
  })

  it('展示前沿键：含选中后代的祖先键不交给 el-tree（避免级联勾选兄弟节点）', async () => {
    const wrapper = mountPanel(
      { userId: 7, username: 'x' },
      treeStubWith({ checkedKeys: ['village'], halfCheckedKeys: ['management'] })
    )
    await flushPromises()
    await wrapper.find('button.tree-check').trigger('click')
    await flushPromises()
    // management 因"有选中后代"被剔除，由 el-tree 自行推导半选
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'village',
    ])
  })

  it('父键缺失的历史配置 → 载入时保留原值（不静默改写），勾选动作再补齐祖先', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/menus/all') return Promise.resolve({ data: menuTree })
      return Promise.resolve({ data: { menu_keys: ['village'], is_customized: true } })
    })
    const wrapper = mountPanel({ userId: 7, username: 'x' })
    await flushPromises()
    // 展示：village（前沿），父键不在集合内
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual(['village'])
  })

  it('畸形 menu_keys 载荷（字符串/对象）→ 不当作选中集合', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/menus/all') return Promise.resolve({ data: menuTree })
      return Promise.resolve({ data: { menu_keys: 'dashboard' } })
    })
    const wrapper = mountPanel({ userId: 7, username: 'x', roleDefaultKeys: ['dashboard'] })
    await flushPromises()
    // 'dashboard' 为字符串（非数组）→ 视为异常载荷，回退空选而非把字符串当键集合
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([])

    // 对象载荷同理
    const wrapper2 = mountPanel({ userId: 8, username: 'y' })
    mockGet.mockImplementation((url: string) => {
      if (url === '/menus/all') return Promise.resolve({ data: menuTree })
      return Promise.resolve({ data: { menu_keys: { a: 1 } } })
    })
    await flushPromises()
    expect(wrapper2.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([])
  })

  it('watch currentMenuKeys：非数组载荷被忽略（不污染选中集合）', async () => {
    const wrapper = mountPanel({ userId: 7, username: 'x', currentMenuKeys: ['dashboard'] })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'dashboard',
    ])
    await wrapper.setProps({ currentMenuKeys: 'village' as any })
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'dashboard',
    ])
  })

  it('恢复角色默认 → 保存 null；保存成功 emit saved', async () => {
    const wrapper = mountPanel({ userId: 7, username: 'x', isCustomized: true, roleDefaultKeys: ['dashboard'] })
    await flushPromises()

    await wrapper.findAll('button.stub-btn')[0].trigger('click')
    await wrapper.findAll('button.stub-btn')[1].trigger('click')
    await flushPromises()

    expect(mockPut).toHaveBeenCalledWith('/menus/user-menus/7', { menu_keys: null })
    expect(wrapper.emitted('saved')).toHaveLength(1)
    expect(mockMessage.success).toHaveBeenCalledWith('菜单配置保存成功')
  })

  it('保存失败：detail 与默认错误文案', async () => {
    mockPut.mockRejectedValueOnce({ response: { data: { detail: '保存失败A' } } })
    const wrapper = mountPanel({ userId: 7, username: 'x', isCustomized: true })
    await flushPromises()
    await wrapper.findAll('button.stub-btn')[1].trigger('click')
    await flushPromises()
    expect(mockMessage.error).toHaveBeenCalledWith('保存失败A')

    mockPut.mockRejectedValueOnce(new Error('x'))
    await wrapper.findAll('button.stub-btn')[1].trigger('click')
    await flushPromises()
    expect(mockMessage.error).toHaveBeenCalledWith('保存失败')
  })

  it('watch currentMenuKeys 变化时同步选中项', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/menus/all') return Promise.resolve({ data: menuTree })
      return Promise.resolve({ data: null })
    })
    const wrapper = mountPanel({ userId: 7, username: 'x', currentMenuKeys: ['a'] })
    await flushPromises()
    await wrapper.setProps({ currentMenuKeys: null })
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([])
    await wrapper.setProps({ currentMenuKeys: ['b'] })
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual(['b'])
  })

  it('getMenuLabel 对未知 key 回退为 key 本身', async () => {
    const wrapper = mountPanel({ userId: 7, username: 'x', roleDefaultKeys: ['unknown-key'] })
    await flushPromises()
    expect(wrapper.text()).toContain('unknown-key')
  })

  it('暴露 loadUserMenuConfig', async () => {
    const wrapper = mountPanel({ userId: 7, username: 'x' })
    await flushPromises()
    expect(typeof (wrapper.vm as any).loadUserMenuConfig).toBe('function')
  })
})
