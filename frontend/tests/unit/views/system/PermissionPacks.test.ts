/**
 * views/system/PermissionPacks.vue 测试（四指标 100%）
 *
 * 覆盖：列表渲染全分支（描述/菜单数/状态/创建时间）、loadPacks/loadMenuTree 成败、
 * 新建/编辑对话框（名称校验、树勾选取值回退、创建/更新、失败文案）、删除确认三态、
 * 绑定用户对话框（角色过滤、预勾选、bind/unbind diff 全组合、失败文案）。
 *
 * 方案：mock '@/api/permissionPack'（6 个函数）+ '@/api/request'（/menus/all 与 /users），
 * el-table-column stub 注入样本行覆盖模板作用域插槽分支。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const {
  ElMessage,
  confirmMock,
  mockGet,
  mockApiRequest,
  apiList,
  apiCreate,
  apiUpdate,
  apiDelete,
  apiBind,
  apiUnbind,
  menuConfigState,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  mockGet: vi.fn(),
  mockApiRequest: vi.fn(),
  apiList: vi.fn(),
  apiCreate: vi.fn(),
  apiUpdate: vi.fn(),
  apiDelete: vi.fn(),
  apiBind: vi.fn(),
  apiUnbind: vi.fn(),
  menuConfigState: { throwOnImport: false },
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  apiRequest: mockApiRequest,
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/api/permissionPack', () => ({
  listPermissionPacks: apiList,
  createPermissionPack: apiCreate,
  updatePermissionPack: apiUpdate,
  deletePermissionPack: apiDelete,
  bindPackUsers: apiBind,
  unbindPackUsers: apiUnbind,
}))

// MENU_CONFIG 动态导入：默认返回最小静态配置；特定测试置 throwOnImport 使解构抛错（走内层 catch）
vi.mock('@/config/menu-config', () => ({
  get MENU_CONFIG() {
    if (menuConfigState.throwOnImport) {
      throw new Error('menu-config unavailable')
    }
    return [{ key: 'dashboard', label: '工作台' }]
  },
}))

import PermissionPacks from '@/views/system/PermissionPacks.vue'

// ── 样本数据 ──
const menuTree = [
  { key: 'dashboard', label: '工作台' },
  {
    key: 'system-security',
    label: '系统管理',
    children: [{ key: 'backup', label: '备份管理' }],
  },
]

const packA = {
  id: 1,
  name: '基础包',
  description: '基础菜单',
  menu_keys: ['dashboard', 'backup', 'system-security'],
  is_active: true,
  bound_user_count: 2,
  created_at: '2024-01-01T08:00:00',
}
const packB = {
  id: 2,
  name: '空包',
  description: '',
  menu_keys: [],
  is_active: false,
  bound_user_count: 0,
  created_at: null,
}
const packC = {
  id: 3,
  name: '稀疏包',
  description: undefined,
  menu_keys: undefined,
  is_active: false,
  bound_user_count: 0,
  created_at: undefined,
}

const userRows = [
  { id: 11, username: 'u1', full_name: '张三', role: 'user', permission_pack_id: 1 },
  { id: 12, username: 'u2', full_name: '', role: 'viewer', permission_pack_id: 2 },
  { id: 13, username: 'u3', full_name: '李四', role: 'user', permission_pack_id: null },
  { id: 14, username: 'a1', full_name: '管理员', role: 'admin', permission_pack_id: null },
]

function mountComp(extraStubs: Record<string, any> = {}) {
  return mount(PermissionPacks, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-dialog': {
          name: 'ElDialog',
          props: ['modelValue', 'title'],
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue', 'opened'],
        },
        // 作用域插槽注入样本行：列表三行 + 绑定表四行
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub">' +
            '<slot :row="packA" /><slot :row="packB" /><slot :row="packC" />' +
            '<slot :row="u1" /><slot :row="u2" /><slot :row="u3" />' +
            '</div>',
          data() {
            return {
              packA,
              packB,
              packC,
              u1: userRows[0],
              u2: userRows[1],
              u3: userRows[2],
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
  apiList.mockResolvedValue([packA, packB])
  apiCreate.mockResolvedValue({})
  apiUpdate.mockResolvedValue({})
  apiDelete.mockResolvedValue({})
  apiBind.mockResolvedValue({})
  apiUnbind.mockResolvedValue({})
  mockGet.mockResolvedValue({ data: menuTree })
  mockApiRequest.mockResolvedValue({ items: userRows })
  confirmMock.mockResolvedValue('confirm')
  menuConfigState.throwOnImport = false
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与列表渲染', () => {
  it('onMounted 加载权限包与菜单树；表格列模板全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(apiList).toHaveBeenCalled()
    expect(mockGet).toHaveBeenCalledWith('/menus/all')
    expect(vm.packs).toEqual([packA, packB])
    expect(vm.menuTreeData).toEqual(menuTree)
    // 叶子集合：dashboard + backup（父级 system-security 不在内）
    expect([...vm.leafKeySet].sort()).toEqual(['backup', 'dashboard'])
    // 描述 || '-'、菜单数 ?. ?? 0、状态三元、创建时间 formatDateTime 两侧
    // （name 列为 prop 直出，无作用域插槽，stub 不渲染文本，直接断言 vm 数据）
    const text = wrapper.text()
    expect(text).toContain('基础菜单')
    expect(text).toContain('启用')
    expect(text).toContain('停用')
  })

  it('loadPacks 失败 → 提示并置空', async () => {
    apiList.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(ElMessage.error).toHaveBeenCalledWith('加载权限包列表失败')
    expect(vm.packs).toEqual([])
  })

  it('loadMenuTree：res 直返（无 .data）与失败回退 MENU_CONFIG', async () => {
    mockGet.mockResolvedValue(menuTree)
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).menuTreeData).toEqual(menuTree)

    mockGet.mockRejectedValue(new Error('down'))
    const wrapper2 = mountComp()
    await flushPromises()
    await vi.dynamicImportSettled() // 等动态 import('@/config/menu-config') 落地
    await flushPromises()
    // 回退到前端静态配置（真实模块，包含 dashboard 项）
    const data2 = (wrapper2.vm as any).menuTreeData
    expect(Array.isArray(data2)).toBe(true)
    expect(data2.length).toBeGreaterThan(0)
  })
})

describe('新建/编辑对话框', () => {
  it('openCreate 重置表单；openEdit 回显（仅叶子 key、描述/菜单数兜底）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.openCreate()
    expect(vm.editDialogVisible).toBe(true)
    expect(vm.editingPack).toBeNull()
    expect(vm.editForm).toEqual({ name: '', description: '', is_active: true })
    expect(vm.editDefaultCheckedKeys).toEqual([])

    vm.openEdit(packA)
    expect(vm.editingPack).toEqual(packA)
    expect(vm.editForm.name).toBe('基础包')
    // menu_keys 中父级 system-security 被过滤，仅叶子回显
    expect(vm.editDefaultCheckedKeys).toEqual(['dashboard', 'backup'])

    vm.openEdit(packC)
    expect(vm.editForm.description).toBe('')
    expect(vm.editDefaultCheckedKeys).toEqual([])
  })

  it('savePack：名称为空 → 报错不请求', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openCreate()
    vm.editForm.name = '  '
    await vm.savePack()
    expect(ElMessage.error).toHaveBeenCalledWith('请输入权限包名称')
    expect(apiCreate).not.toHaveBeenCalled()
  })

  it('savePack 新建：树 ref 提供全选+半选 key，成功静默关闭并刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openCreate()
    vm.editForm.name = '新包'
    vm.editForm.description = '描述'
    vm.menuTreeRef = {
      getCheckedKeys: () => ['dashboard', 'backup'],
      getHalfCheckedKeys: () => ['system-security'],
    }
    await vm.savePack()
    expect(apiCreate).toHaveBeenCalledWith({
      name: '新包',
      description: '描述',
      menu_keys: ['dashboard', 'backup', 'system-security'],
      is_active: true,
    })
    expect(vm.editDialogVisible).toBe(false)
    expect(apiList).toHaveBeenCalledTimes(2) // 初始 + 保存后刷新
  })

  it('savePack 编辑：树 ref 缺失方法 → 回显 key 兜底；trim 名称', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openEdit(packA)
    vm.editForm.name = '  改名  '
    vm.menuTreeRef = undefined
    await vm.savePack()
    expect(apiUpdate).toHaveBeenCalledWith(1, {
      name: '改名',
      description: '基础菜单',
      menu_keys: ['dashboard', 'backup'],
      is_active: true,
    })
  })

  it('savePack 失败：detail 文案与兜底文案两侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openCreate()
    vm.editForm.name = '重名包'

    apiCreate.mockRejectedValue({ response: { data: { detail: '权限包名称已存在' } } })
    await vm.savePack()
    expect(ElMessage.error).toHaveBeenCalledWith('权限包名称已存在')
    expect(vm.editDialogVisible).toBe(true) // 失败不关闭

    apiCreate.mockRejectedValue(new Error('boom'))
    await vm.savePack()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
  })
})

describe('删除', () => {
  it('确认删除 → 成功刷新；后端 400 → detail 文案；取消 → 不请求', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleDelete(packA)
    expect(confirmMock).toHaveBeenCalled()
    expect(apiDelete).toHaveBeenCalledWith(1)
    expect(apiList).toHaveBeenCalledTimes(2)

    apiDelete.mockRejectedValue({ response: { data: { detail: '该权限包仍绑定 2 个用户' } } })
    await vm.handleDelete(packA)
    expect(ElMessage.error).toHaveBeenCalledWith('该权限包仍绑定 2 个用户')

    apiDelete.mockRejectedValue(new Error('x'))
    await vm.handleDelete(packA)
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')

    confirmMock.mockRejectedValue('cancel')
    await vm.handleDelete(packB)
    expect(apiDelete).toHaveBeenCalledTimes(3) // 未新增调用
  })
})

describe('绑定用户', () => {
  it('openBind：仅保留 user/viewer 角色；失败 → 提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.openBind(packA)
    expect(vm.bindDialogVisible).toBe(true)
    expect(vm.bindableUsers.map((u: any) => u.id)).toEqual([11, 12, 13]) // admin 被过滤

    mockApiRequest.mockRejectedValue(new Error('net'))
    await vm.openBind(packA)
    expect(ElMessage.error).toHaveBeenCalledWith('加载用户列表失败')
  })

  it('openBind：res.data.items 嵌套形态', async () => {
    mockApiRequest.mockResolvedValue({ data: { items: userRows } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.openBind(packA)
    expect(vm.bindableUsers).toHaveLength(3)
  })

  it('preselectBoundUsers：预勾选已绑定本包用户（el-table stub 提供 toggleRowSelection）', async () => {
    const toggled: number[] = []
    const wrapper = mountComp({
      'el-table': {
        name: 'ElTable',
        template: '<div class="el-table-stub"><slot /></div>',
        emits: ['selection-change'],
        methods: {
          toggleRowSelection(row: any, selected: boolean) {
            if (selected) toggled.push(row.id)
          },
        },
      },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.openBind(packA)
    vm.preselectBoundUsers()
    expect(toggled).toEqual([11]) // 仅 u1 绑定到 pack 1
  })

  it('preselectBoundUsers：无包 / 表格无 toggleRowSelection 方法 → 早退', async () => {
    const wrapper = mountComp() // 自动 stub 无 toggleRowSelection 方法
    await flushPromises()
    const vm = wrapper.vm as any

    vm.bindingPack = null
    expect(() => vm.preselectBoundUsers()).not.toThrow()

    vm.bindingPack = packA
    expect(() => vm.preselectBoundUsers()).not.toThrow()
  })

  it('saveBind：diff 出 bind/unbind 两组分别调用，成功关闭并刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.openBind(packA) // pack id=1；u1 已绑本包，u2 绑了其他包，u3 未绑
    // 勾选 u2 + u3：u2 换绑（bind），u3 新绑（bind），u1 未勾（unbind）
    vm.bindSelection = [userRows[1], userRows[2]]
    await vm.saveBind()
    expect(apiBind).toHaveBeenCalledWith(1, [12, 13])
    expect(apiUnbind).toHaveBeenCalledWith(1, [11])
    expect(vm.bindDialogVisible).toBe(false)
    expect(apiList).toHaveBeenCalledTimes(2)
  })

  it('saveBind：无变化 → 两个接口都不调用；无 bindingPack → 早退', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.bindingPack = null
    await vm.saveBind()
    expect(apiBind).not.toHaveBeenCalled()

    await vm.openBind(packA)
    vm.bindSelection = [userRows[0]] // 仅 u1，已绑定本包 → 无 diff
    await vm.saveBind()
    expect(apiBind).not.toHaveBeenCalled()
    expect(apiUnbind).not.toHaveBeenCalled()
    expect(vm.bindDialogVisible).toBe(false)
  })

  it('saveBind 失败：detail 与兜底文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.openBind(packA)
    vm.bindSelection = [userRows[1], userRows[2]]

    apiBind.mockRejectedValue({ response: { data: { detail: '仅可绑定普通用户' } } })
    await vm.saveBind()
    expect(ElMessage.error).toHaveBeenCalledWith('仅可绑定普通用户')

    apiBind.mockRejectedValue(new Error('x'))
    await vm.saveBind()
    expect(ElMessage.error).toHaveBeenCalledWith('绑定保存失败')
  })

  it('绑定表列模板：姓名兜底/角色标签/当前权限包三态', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.openBind(packA)
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('普通用户')
    expect(text).toContain('访客')
    expect(text).toContain('本包') // u1.permission_pack_id === pack.id
    expect(text).toContain('其他包') // u2 绑了 pack 2
    expect(text).toContain('角色默认') // u3 未绑定
  })
})

describe('工具函数与对话框内联事件', () => {
  it('formatDateTime：有值格式化 / 无值 -', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatDateTime(undefined)).toBe('-')
    expect(vm.formatDateTime('2024-01-01T08:00:00')).not.toBe('-')
  })

  it('编辑对话框 v-model / 绑定表 selection-change 内联处理器', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    dialogs[0].vm.$emit('update:modelValue', true)
    expect(vm.editDialogVisible).toBe(true)
    dialogs[1].vm.$emit('update:modelValue', true)
    expect(vm.bindDialogVisible).toBe(true)

    // 对话框 opened → 预勾选处理器
    dialogs[1].vm.$emit('opened')
    await flushPromises()

    const tables = wrapper.findAllComponents({ name: 'ElTable' })
    await tables[1].vm.$emit('selection-change', [userRows[0]])
    expect(vm.bindSelection).toEqual([userRows[0]])
  })
})

describe('loadMenuTree 兜底与 openBind 数据形态', () => {
  it('loadMenuTree：菜单接口失败且 MENU_CONFIG 解构抛错 → 置空（340-341）', async () => {
    menuConfigState.throwOnImport = true
    mockGet.mockRejectedValue(new Error('down'))
    const wrapper = mountComp()
    await flushPromises()
    await vi.dynamicImportSettled()
    await flushPromises()
    expect((wrapper.vm as any).menuTreeData).toEqual([])
  })

  it('loadMenuTree：接口返回 0（falsy）→ 走 [] 兜底', async () => {
    mockGet.mockResolvedValue(0)
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).menuTreeData).toEqual([])
  })

  it('openBind：res 为裸数组 → 直用；空值 → [] 兜底', async () => {
    mockApiRequest.mockResolvedValue([userRows[0]])
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.openBind(packA)
    expect(vm.bindableUsers).toEqual([userRows[0]])

    mockApiRequest.mockResolvedValue(null)
    await vm.openBind(packA)
    expect(vm.bindableUsers).toEqual([])
  })
})

describe('formatDateTime 与菜单树插槽', () => {
  it('formatDateTime：无效日期 → -', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatDateTime('not-a-date')).toBe('-')
  })

  it('菜单树插槽：data.label 有值/无值两侧', async () => {
    const wrapper = mountComp({
      'el-tree': {
        name: 'ElTree',
        template:
          '<div class="el-tree-stub"><slot :data="{ label: \'工作台\' }" /><slot :data="{}" /></div>',
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('工作台')
  })
})

describe('模板内联处理器（按钮/输入/开关）', () => {
  it('编辑/绑定/删除/保存/取消按钮 + name/desc/switch v-model', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 编辑按钮 → openEdit(row)
    const editBtns = wrapper.findAll('el-button-stub').filter((b: any) => b.text().trim() === '编辑')
    expect(editBtns.length).toBe(6) // 操作列注入 6 行（packA/B/C + u1/u2/u3）
    await editBtns[0].trigger('click')
    await flushPromises()
    expect(vm.editingPack).toEqual(packA)

    // 名称/描述输入 v-model
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    inputs[0].vm.$emit('update:modelValue', '新名称')
    inputs[1].vm.$emit('update:modelValue', '新描述')
    expect(vm.editForm.name).toBe('新名称')
    expect(vm.editForm.description).toBe('新描述')

    // 开关 v-model
    wrapper.findComponent({ name: 'ElSwitch' }).vm.$emit('update:modelValue', false)
    expect(vm.editForm.is_active).toBe(false)

    // 保存按钮 → savePack
    const saveBtn = wrapper.findAll('el-button-stub').find((b: any) => b.text().trim() === '保存')
    await saveBtn!.trigger('click')
    await flushPromises()
    expect(apiUpdate).toHaveBeenCalled()

    // 绑定用户按钮 → openBind(row)
    const bindBtns = wrapper.findAll('el-button-stub').filter((b: any) => b.text().trim() === '绑定用户')
    await bindBtns[0].trigger('click')
    await flushPromises()
    expect(vm.bindingPack).toEqual(packA)

    // 取消按钮：绑定对话框 + 编辑对话框（覆盖 line 79/121 两个 onClick 内联处理器）
    const cancelBtns = wrapper.findAll('el-button-stub').filter((b: any) => b.text().trim() === '取消')
    await cancelBtns[1].trigger('click')
    expect(vm.bindDialogVisible).toBe(false)
    await cancelBtns[0].trigger('click')
    expect(vm.editDialogVisible).toBe(false)

    // 删除按钮 → handleDelete(row)
    const delBtns = wrapper.findAll('el-button-stub').filter((b: any) => b.text().trim() === '删除')
    await delBtns[0].trigger('click')
    await flushPromises()
    expect(apiDelete).toHaveBeenCalledWith(1)
  })
})

