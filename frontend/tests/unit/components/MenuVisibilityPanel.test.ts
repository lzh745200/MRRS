/**
 * components/permission/MenuVisibilityPanel.vue 测试（四指标 100%）
 *
 * 契约 §6：菜单树改为 menuStore.fetchAllMenus()（/menus/all 的 v2 sections）渲染
 * "板块 → 入口 → Tab" 三级 el-tree，勾选/保存协议仍是 key 数组（保存格式不变）。
 * 覆盖：fetchAllMenus 成败、三级树构建（page/group/console/空 children 防御）、
 * 用户自定义/角色默认/畸形载荷、树勾选回调（半选父键、板块键剔除）、
 * 展示前沿键、setCheckedKeys 程序化同步、恢复默认、保存成败、重入守卫。
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'

enableAutoUnmount(afterEach)

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  put: vi.fn(),
  fetchAllMenus: vi.fn(),
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

const mockGet = mocks.get
const mockPut = mocks.put
const mockFetchAllMenus = mocks.fetchAllMenus
const mockMessage = mocks.message

vi.mock('@/api/request', () => ({
  get: (...a: any[]) => mocks.get(...a),
  put: (...a: any[]) => mocks.put(...a),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('element-plus', () => ({ ElMessage: mocks.message }))

// 契约 §6：全量菜单统一由 store 提供；menu-config 已删除，组件不再有静态回退
vi.mock('@/stores/menu', () => ({
  useMenuStore: () => ({ fetchAllMenus: mocks.fetchAllMenus }),
}))

import MenuVisibilityPanel from '@/components/permission/MenuVisibilityPanel.vue'

// ── v2 sections 夹具：覆盖 page / group / console（有/无 tabs）/ 空 children 防御分支 ──
const menuSections = [
  {
    key: 'business',
    label: '帮扶业务',
    order: 10,
    items: [
      { key: 'dashboard', label: '工作台', path: '/dashboard', kind: 'page' },
      {
        key: 'management',
        label: '业务管理',
        kind: 'group',
        children: [{ key: 'village', label: '帮扶村', path: '/supported-villages', kind: 'page' }],
      },
      { key: 'empty-group', label: '空分组', kind: 'group' },
    ],
  },
  {
    key: 'system',
    label: '系统管理',
    order: 90,
    items: [
      {
        key: 'system-console-org',
        label: '组织与权限',
        path: '/system/console/org',
        kind: 'console',
        tabs: [
          { key: 'users-orgs', label: '用户与组织', path: '/system/users' },
          { key: 'roles', label: '角色管理', path: '/system/roles' },
        ],
      },
      {
        key: 'system-console-ops',
        label: '运维与监控',
        path: '/system/console/ops',
        kind: 'console',
      },
    ],
  },
]

/** sections → 期望的三级树（板块 isSection 标记为展示分组） */
const expectedTree = [
  {
    key: 'business',
    label: '帮扶业务',
    isSection: true,
    children: [
      { key: 'dashboard', label: '工作台' },
      {
        key: 'management',
        label: '业务管理',
        children: [{ key: 'village', label: '帮扶村' }],
      },
      { key: 'empty-group', label: '空分组' },
    ],
  },
  {
    key: 'system',
    label: '系统管理',
    isSection: true,
    children: [
      {
        key: 'system-console-org',
        label: '组织与权限',
        children: [
          { key: 'users-orgs', label: '用户与组织' },
          { key: 'roles', label: '角色管理' },
        ],
      },
      { key: 'system-console-ops', label: '运维与监控' },
    ],
  },
]

const ElButtonStub = {
  props: {
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    type: String,
    size: String,
  },
  emits: ['click'],
  template:
    '<button class="stub-btn" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
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

/** 带 setCheckedKeys 的树桩：驱动程序化回填路径 */
const setCheckedKeysCalls: string[][] = []
const ElTreeStubWithSync = {
  name: 'ElTreeStubWithSync',
  props: ['data', 'defaultCheckedKeys', 'showCheckbox'],
  emits: ['check'],
  methods: {
    setCheckedKeys(keys: string[]) {
      setCheckedKeysCalls.push([...keys])
    },
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

beforeEach(() => {
  vi.clearAllMocks()
  setCheckedKeysCalls.length = 0
  mockFetchAllMenus.mockResolvedValue(menuSections)
  mockGet.mockImplementation((url: string) => {
    if (url.includes('/menus/user-menus/')) {
      return Promise.resolve({ data: { menu_keys: ['dashboard'], is_customized: true } })
    }
    return Promise.resolve({})
  })
  mockPut.mockResolvedValue({})
})

describe('加载与三级树渲染', () => {
  it('挂载时 fetchAllMenus 构建"板块→入口→Tab"三级树；自定义配置与角色默认标签', async () => {
    const wrapper = mountPanel({
      userId: 7,
      username: '张三',
      role: 'admin',
      roleDefaultKeys: ['dashboard', 'village'],
      isCustomized: true,
    })
    await flushPromises()

    expect(mockFetchAllMenus).toHaveBeenCalledTimes(1)
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('data')).toEqual(expectedTree)
    expect(mockGet).toHaveBeenCalledWith('/menus/user-menus/7')
    expect(wrapper.text()).toContain('张三')
    expect(wrapper.text()).toContain('当前为自定义配置。角色默认包含 2 个菜单。')

    const tags = wrapper.findAll('span.stub-tag')
    expect(tags).toHaveLength(2)
    expect(tags[0].text()).toBe('工作台')
    expect(tags[1].text()).toBe('帮扶村')

    // 自定义配置优先于角色默认
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'dashboard',
    ])
  })

  it('无自定义配置（menu_keys 为 null）→ 展示角色默认；恢复按钮禁用；无自定义提示', async () => {
    mockGet.mockImplementation(() => Promise.resolve({ data: { menu_keys: null } }))
    const wrapper = mountPanel({
      userId: 7,
      username: '张三',
      roleDefaultKeys: ['village'],
      isCustomized: false,
    })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'village',
    ])
    expect(wrapper.findAll('button.stub-btn')[0].attributes('disabled')).toBeDefined()
    expect(wrapper.text()).not.toContain('当前为自定义配置')
  })

  it('全量菜单加载失败 → 树为空，不读取已删除的静态菜单配置', async () => {
    mockFetchAllMenus.mockRejectedValue(new Error('all menus down'))
    const wrapper = mountPanel({ userId: 7, username: 'x' })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('data')).toEqual([])
  })

  it('sections 为空数组 → 空树', async () => {
    mockFetchAllMenus.mockResolvedValue([])
    const wrapper = mountPanel({ userId: 7, username: 'x' })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('data')).toEqual([])
  })

  it('loadUserMenuConfig 失败时回退 currentMenuKeys', async () => {
    mockGet.mockRejectedValue(new Error('net'))
    const wrapper = mountPanel({ userId: 7, username: 'x', currentMenuKeys: ['management'] })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'management',
    ])
  })

  it('loadUserMenuConfig 失败且无 currentMenuKeys 回退 → 空选', async () => {
    mockGet.mockRejectedValue(new Error('net'))
    const wrapper = mountPanel({ userId: 7, username: 'x' })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([])
  })

  it('用户菜单接口返回裸对象（无 .data）时也能解析', async () => {
    mockGet.mockResolvedValue({ menu_keys: ['village'] })
    const wrapper = mountPanel({ userId: 7, username: 'x' })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'village',
    ])
  })

  it('用户菜单接口返回 null → 解析异常被捕获并回退 currentMenuKeys', async () => {
    mockGet.mockResolvedValue(null)
    const wrapper = mountPanel({ userId: 7, username: 'x', currentMenuKeys: ['dashboard'] })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'dashboard',
    ])
  })

  it('无 userId 时 loadUserMenuConfig 提前返回', async () => {
    const wrapper = mountPanel({ username: 'x' })
    await flushPromises()
    expect(mockGet).not.toHaveBeenCalledWith(expect.stringContaining('/menus/user-menus/'))
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([])
  })

  it('畸形 menu_keys 载荷（字符串/对象）→ 空选，不当选中集合', async () => {
    mockGet.mockImplementation(() => Promise.resolve({ data: { menu_keys: 'dashboard' } }))
    const wrapper = mountPanel({ userId: 7, username: 'x', roleDefaultKeys: ['dashboard'] })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([])

    mockGet.mockImplementation(() => Promise.resolve({ data: { menu_keys: { a: 1 } } }))
    const wrapper2 = mountPanel({ userId: 8, username: 'y' })
    await flushPromises()
    expect(wrapper2.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([])
  })

  it('watch currentMenuKeys：数组同步、非数组载荷忽略', async () => {
    const wrapper = mountPanel({ userId: 7, username: 'x', currentMenuKeys: ['dashboard'] })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'dashboard',
    ])
    await wrapper.setProps({ currentMenuKeys: 'village' as any })
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'dashboard',
    ])
    await wrapper.setProps({ currentMenuKeys: ['village'] })
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'village',
    ])
  })

  it('getMenuLabel 对未知 key 回退为 key 本身；roleDefaultKeys 缺省时 v-for 为空', async () => {
    const wrapper = mountPanel({ userId: 7, username: 'x', roleDefaultKeys: ['unknown-key'] })
    await flushPromises()
    expect(wrapper.text()).toContain('unknown-key')

    const wrapper2 = mountPanel({ userId: 7, username: 'x' })
    await flushPromises()
    expect(wrapper2.findAll('span.stub-tag')).toHaveLength(0)
  })

  it('暴露 loadUserMenuConfig', async () => {
    const wrapper = mountPanel({ userId: 7, username: 'x' })
    await flushPromises()
    expect(typeof (wrapper.vm as any).loadUserMenuConfig).toBe('function')
  })
})

describe('树勾选回调与保存协议（key 数组不变）', () => {
  it('勾选子菜单：补齐半选父键；板块分组 key 不进入保存载荷', async () => {
    const wrapper = mountPanel(
      { userId: 7, username: 'x', isCustomized: true, roleDefaultKeys: [] },
      treeStubWith({ checkedKeys: ['village'], halfCheckedKeys: ['management', 'business'] })
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
    expect(saved).not.toContain('business') // 板块展示分组不落库
  })

  it('halfCheckedKeys 缺失时兜底补齐祖先链（跳过板块节点但继续上溯）', async () => {
    const wrapper = mountPanel(
      { userId: 7, username: 'x' },
      treeStubWith({ checkedKeys: ['village'] })
    )
    await flushPromises()
    await wrapper.find('button.tree-check').trigger('click')
    await flushPromises()
    const keys = (wrapper.vm as any).selectedMenuKeys as string[]
    expect(keys).toContain('village')
    expect(keys).toContain('management')
    expect(keys).not.toContain('business')
  })

  it('checked 为纯数组时直接采用', async () => {
    const wrapper = mountPanel({ userId: 7, username: 'x' }, treeStubWith(['dashboard', 'village']))
    await flushPromises()
    await wrapper.find('button.tree-check').trigger('click')
    await flushPromises()
    const keys = (wrapper.vm as any).selectedMenuKeys as string[]
    expect(keys).toContain('dashboard')
    expect(keys).toContain('village')
  })

  it('checked 为畸形载荷（字符串）→ 空选，不污染选中态', async () => {
    const wrapper = mountPanel({ userId: 7, username: 'x' }, treeStubWith('malformed-payload'))
    await flushPromises()
    await wrapper.find('button.tree-check').trigger('click')
    await flushPromises()
    expect((wrapper.vm as any).selectedMenuKeys).toEqual([])
  })

  it('展示前沿键：含选中后代的祖先键不交给 el-tree（避免级联勾选兄弟节点）', async () => {
    const wrapper = mountPanel(
      { userId: 7, username: 'x' },
      treeStubWith({ checkedKeys: ['village'], halfCheckedKeys: ['management'] })
    )
    await flushPromises()
    await wrapper.find('button.tree-check').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'village',
    ])
  })

  it('父键缺失的历史配置 → 载入时保留原值（不静默改写）', async () => {
    mockGet.mockImplementation(() => Promise.resolve({ data: { menu_keys: ['village'] } }))
    const wrapper = mountPanel({ userId: 7, username: 'x' })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'village',
    ])
  })

  it('恢复角色默认 → 保存 null；保存成功 emit saved', async () => {
    const wrapper = mountPanel({
      userId: 7,
      username: 'x',
      isCustomized: true,
      roleDefaultKeys: ['dashboard'],
    })
    await flushPromises()

    await wrapper.findAll('button.stub-btn')[0].trigger('click')
    await wrapper.findAll('button.stub-btn')[1].trigger('click')
    await flushPromises()

    expect(mockPut).toHaveBeenCalledWith('/menus/user-menus/7', { menu_keys: null })
    expect(wrapper.emitted('saved')).toHaveLength(1)
    expect(mockMessage.success).toHaveBeenCalledWith('菜单配置保存成功')
  })

  it('保存失败：detail 文案与默认错误文案', async () => {
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
})

describe('树勾选态程序化同步（setCheckedKeys）', () => {
  it('加载用户自定义菜单后回填；勾选回调后重新回填（展示态与保存集合对齐）', async () => {
    const wrapper = mountPanel({ userId: 7, username: 'x', isCustomized: true }, ElTreeStubWithSync)
    await flushPromises()
    expect(setCheckedKeysCalls.at(-1)).toEqual(['dashboard'])

    const before = setCheckedKeysCalls.length
    await wrapper.find('button.tree-check').trigger('click')
    await flushPromises()
    expect(setCheckedKeysCalls.length).toBeGreaterThan(before)
  })

  it('无自定义配置时回填角色默认菜单', async () => {
    mockGet.mockImplementation(() => Promise.resolve({ data: { menu_keys: null } }))
    mountPanel(
      { userId: 7, username: 'x', roleDefaultKeys: ['dashboard', 'village'] },
      ElTreeStubWithSync
    )
    await flushPromises()
    expect(setCheckedKeysCalls.at(-1)).toEqual(['dashboard', 'village'])
  })

  it('恢复默认后回填空集合（提交 null 语义）', async () => {
    const wrapper = mountPanel({ userId: 7, username: 'x', isCustomized: true }, ElTreeStubWithSync)
    await flushPromises()
    setCheckedKeysCalls.length = 0
    ;(wrapper.vm as any).resetToDefault()
    await flushPromises()
    expect(setCheckedKeysCalls.at(-1)).toEqual([])
  })

  it('roleDefaultKeys 缺省时回填空数组（?? [] 兜底）', async () => {
    mockGet.mockImplementation(() => Promise.resolve({ data: { menu_keys: null } }))
    mountPanel({ userId: 7, username: 'x' }, ElTreeStubWithSync)
    await flushPromises()
    expect(setCheckedKeysCalls.at(-1)).toEqual([])
  })

  it('setCheckedKeys 期间回传的 check 事件被丢弃（重入守卫）', async () => {
    const ReentrantTreeStub = {
      name: 'ReentrantTreeStub',
      props: ['data', 'defaultCheckedKeys', 'showCheckbox'],
      emits: ['check'],
      mounted() {
        ;(this as any).$emit('check', null, { checkedKeys: ['should-be-ignored'] })
      },
      methods: {
        setCheckedKeys() {
          ;(this as any).$emit('check', null, { checkedKeys: ['should-be-ignored'] })
        },
      },
      template: '<div class="stub-tree"></div>',
    }
    const wrapper = mountPanel({ userId: 7, username: 'x' }, ReentrantTreeStub)
    await flushPromises()
    expect((wrapper.vm as any).selectedMenuKeys).toEqual(['dashboard'])
  })
})
