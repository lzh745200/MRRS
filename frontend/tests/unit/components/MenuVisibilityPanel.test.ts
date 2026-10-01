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
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

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

/**
 * 带 setCheckedKeys 的树桩。
 *
 * 真实 el-tree 暴露 setCheckedKeys（程序化回填勾选态）。默认 ElTreeStub 无此方法，
 * 会命中 syncTreeCheckedKeys 的 `typeof tree?.setCheckedKeys !== 'function'` 守卫提前 return，
 * 使「树同步」这段关键逻辑从未被执行（管理员看到 A、提交 B 的静默不一致正是此处缺测所致）。
 */
const setCheckedKeysCalls: string[][] = []
const ElTreeStubWithSync = {
  name: 'ElTreeStubWithSync',
  props: ['data', 'defaultCheckedKeys', 'showCheckbox'],
  emits: ['check'],
  methods: {
    setCheckedKeys(keys: string[]) {
      // 记录每次回填，供断言"展示态与保存集合一致"
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
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'dashboard',
    ])
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
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'village',
    ])
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
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'management',
    ])
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
    expect(wrapper.findComponent({ name: 'ElTreeStub' }).props('defaultCheckedKeys')).toEqual([
      'village',
    ])
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

  // ── 树勾选态同步（syncTreeCheckedKeys 主体） ──
  // 默认 ElTreeStub 无 setCheckedKeys → 守卫提前 return，同步逻辑零执行。
  // 以下用例挂带 setCheckedKeys 的树桩，真实驱动 setCheckedKeys 路径。
  describe('树勾选态程序化同步（setCheckedKeys）', () => {
    beforeEach(() => {
      setCheckedKeysCalls.length = 0
    })

    it('加载用户自定义菜单后调用 setCheckedKeys 回填', async () => {
      const wrapper = mountPanel(
        { userId: 7, username: 'x', isCustomized: true },
        ElTreeStubWithSync
      )
      await flushPromises()
      // 用户有自定义配置 menu_keys=['dashboard'] → 回填该集合
      expect(setCheckedKeysCalls.length).toBeGreaterThan(0)
      expect(setCheckedKeysCalls.at(-1)).toEqual(['dashboard'])
      expect(wrapper.findComponent({ name: 'ElTreeStubWithSync' }).exists()).toBe(true)
    })

    it('无自定义配置时回填角色默认菜单', async () => {
      mockGet.mockImplementation((url: string) => {
        if (url === '/menus/all') return Promise.resolve({ data: menuTree })
        return Promise.resolve({ data: { menu_keys: null } })
      })
      mountPanel(
        { userId: 7, username: 'x', roleDefaultKeys: ['dashboard', 'village'] },
        ElTreeStubWithSync
      )
      await flushPromises()
      expect(setCheckedKeysCalls.at(-1)).toEqual(['dashboard', 'village'])
    })

    it('勾选回调后重新回填（展示态与保存集合对齐）', async () => {
      const wrapper = mountPanel(
        { userId: 7, username: 'x', isCustomized: true },
        ElTreeStubWithSync
      )
      await flushPromises()
      const before = setCheckedKeysCalls.length
      await wrapper.find('button.tree-check').trigger('click')
      await flushPromises()
      // onMenuCheck 末尾 void syncTreeCheckedKeys() → 再次回填
      expect(setCheckedKeysCalls.length).toBeGreaterThan(before)
    })

    it('恢复默认后回填空集合（提交 null 语义）', async () => {
      const wrapper = mountPanel(
        { userId: 7, username: 'x', isCustomized: true },
        ElTreeStubWithSync
      )
      await flushPromises()
      setCheckedKeysCalls.length = 0
      // 通过组件暴露的 resetToDefault 触发（等价于点击「恢复默认」按钮）
      ;(wrapper.vm as any).resetToDefault()
      await flushPromises()
      expect(setCheckedKeysCalls.at(-1)).toEqual([])
    })

    it('角色默认键未提供（undefined）时回填空数组（displayCheckedKeys 的 ?? [] 兜底）', async () => {
      mockGet.mockImplementation((url: string) => {
        if (url === '/menus/all') return Promise.resolve({ data: menuTree })
        // menu_keys 为 null → selectedMenuKeys = roleDefaultKeys
        return Promise.resolve({ data: { menu_keys: null } })
      })
      // 不传 roleDefaultKeys → props.roleDefaultKeys 为 undefined → 命中 ?? []
      mountPanel({ userId: 7, username: 'x' }, ElTreeStubWithSync)
      await flushPromises()
      expect(setCheckedKeysCalls.at(-1)).toEqual([])
    })
  })

  // ── onMenuCheck 载荷形状兼容 ──
  describe('onMenuCheck 载荷形状兼容', () => {
    it('checked 为纯数组时直接采用', async () => {
      // treeStubWith 通过 payload 控制 emit 的 checked 值
      const w2 = mountPanel({ userId: 7, username: 'x' }, treeStubWith(['dashboard', 'village']))
      await flushPromises()
      await w2.find('button.tree-check').trigger('click')
      await flushPromises()
      expect((w2.vm as any).selectedMenuKeys).toContain('dashboard')
      expect((w2.vm as any).selectedMenuKeys).toContain('village')
    })

    it('checked 既非对象 checkedKeys 也非数组（畸形载荷）→ 落空数组，不污染选中态', async () => {
      // 命中 onMenuCheck 的 `: []` 末级兜底：字符串/数字等畸形载荷不得当选中集合
      const w = mountPanel({ userId: 7, username: 'x' }, treeStubWith('malformed-payload'))
      await flushPromises()
      await w.find('button.tree-check').trigger('click')
      await flushPromises()
      expect((w.vm as any).selectedMenuKeys).toEqual([])
    })

    it('checkedKeys 对象含 halfCheckedKeys 时合并父级键（防父键缺失被后端裁掉）', async () => {
      const payload = { checkedKeys: ['village'], halfCheckedKeys: ['management'] }
      const w = mountPanel({ userId: 7, username: 'x' }, treeStubWith(payload))
      await flushPromises()
      await w.find('button.tree-check').trigger('click')
      await flushPromises()
      const keys = (w.vm as any).selectedMenuKeys
      expect(keys).toContain('village')
      expect(keys).toContain('management')
    })
  })

  // ── syncingTree 重入守卫 ──
  describe('syncingTree 重入守卫', () => {
    it('setCheckedKeys 期间回传的 check 事件被丢弃，不与选中态互相覆盖', async () => {
      // 真实 el-tree：setCheckedKeys 会同步触发 check 事件。
      // 若不丢弃，程序化回填会被当作"用户勾选"再写回 selectedMenuKeys，
      // 造成展示态与保存集合偏移。此桩在 setCheckedKeys 内同步 emit check 复现该重入。
      const ReentrantTreeStub = {
        name: 'ReentrantTreeStub',
        props: ['data', 'defaultCheckedKeys', 'showCheckbox'],
        emits: ['check'],
        mounted() {
          // 模拟 el-tree 初始化后同步回传一次 check
          ;(this as any).$emit('check', null, { checkedKeys: ['should-be-ignored'] })
        },
        methods: {
          setCheckedKeys() {
            ;(this as any).$emit('check', null, { checkedKeys: ['should-be-ignored'] })
          },
        },
        template: '<div class="stub-tree"></div>',
      }
      mockGet.mockImplementation((url: string) => {
        if (url === '/menus/all') return Promise.resolve({ data: menuTree })
        return Promise.resolve({ data: { menu_keys: ['dashboard'] } })
      })
      const w = mountPanel({ userId: 7, username: 'x' }, ReentrantTreeStub)
      await flushPromises()
      // 重入事件被 syncingTree 守卫丢弃 → 选中集合保持加载值，未被 'should-be-ignored' 覆盖
      expect((w.vm as any).selectedMenuKeys).toEqual(['dashboard'])
    })
  })
})
