/**
 * views/organization/List.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 并行加载、fetchStats/fetchData 全部数据形状与 ||/?. 兜底、
 * handleSearch/handlePageChange、对话框 CRUD（validate 失败/无 formRef/创建/编辑/异常）、
 * handleDelete 全分支（cancel 两态/detail/message/兜底）、handleExport 成功失败、
 * initSortable 早退链/创建/销毁/onEnd 全分支、formatLevel、collectDescendantIds/parentOrgOptions、
 * 模板 v-if/v-else（isAdmin/org_type/is_active/分页/drag-tip）与全部 v-model/内联点击。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂提升求值，引用对象须先放入 vi.hoisted 初始化（TDZ）
const {
  authState,
  ElMessage,
  confirmMock,
  promptMock,
  mockPost,
  mockPut,
  mockDel,
  mockApiRequest,
  mockBatchSort,
  logError,
  mockPushSafe,
  sortableCreate,
  sortableBox,
} = vi.hoisted(() => {
  return {
    authState: { isAdmin: true },
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
    confirmMock: vi.fn(),
    promptMock: vi.fn(),
    mockPost: vi.fn(),
    mockPut: vi.fn(),
    mockDel: vi.fn(),
    mockApiRequest: vi.fn(),
    mockBatchSort: vi.fn(),
    logError: vi.fn(),
    mockPushSafe: vi.fn(),
    sortableCreate: vi.fn(),
    sortableBox: { opts: null as any, instances: [] as any[] },
  }
})

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock, prompt: promptMock },
}))

vi.mock('@/api/request', () => ({
  post: mockPost,
  put: mockPut,
  del: mockDel,
  apiRequest: mockApiRequest,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/api/organization', () => ({
  batchUpdateSortOrders: mockBatchSort,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mockPushSafe }),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('sortablejs', () => ({
  default: { create: sortableCreate },
}))

import OrgList from '@/views/organization/List.vue'

// ==================== 样本数据 ====================

const orgRow1 = {
  id: 1,
  name: '总部',
  code: 'HQ',
  org_type: 'department',
  level: 'level_1',
  parent_id: null,
  is_active: true,
  contact_person: '张三',
  contact_phone: '13800000000',
  sort_order: 1,
}
const orgRow2 = {
  id: 2,
  name: '分部',
  code: 'FB',
  org_type: 'support_unit',
  level: 2,
  parent_id: 1,
  is_active: false,
  contact_person: '',
  contact_phone: '',
  sort_order: 2,
}

// el-table-column 插槽样本行：覆盖 org_type 三分支 + ||'未设置' 两侧、is_active 两侧、formatLevel 三分支
const slotRowA = {
  id: 1,
  name: '甲组织',
  org_type: 'department',
  level: 'level_2',
  is_active: true,
  parent_id: null,
}
const slotRowB = {
  id: 2,
  name: '乙组织',
  org_type: 'support_unit',
  level: 5,
  is_active: false,
  parent_id: 1,
}
const slotRowC = {
  id: 3,
  name: '丙组织',
  org_type: 'custom_type',
  level: null,
  is_active: true,
  parent_id: 2,
}
const slotRowD = {
  id: 4,
  name: '丁组织',
  org_type: '',
  level: 0,
  is_active: false,
  parent_id: null,
}

const stubs = {
  'el-card': {
    name: 'ElCard',
    template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
  },
  'el-dialog': {
    name: 'ElDialog',
    template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
    props: ['modelValue', 'title'],
    emits: ['update:modelValue', 'close'],
  },
  // 自带 tbody 结构，initSortable 挂载即走 Sortable.create 分支（无需手动赋 tableRef）
  'el-table': {
    name: 'ElTable',
    template: '<div><div class="el-table__body-wrapper"><tbody></tbody></div><slot /></div>',
    props: ['data'],
  },
  'el-table-column': {
    name: 'ElTableColumn',
    template:
      '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /><slot :row="rowD" /></div>',
    data() {
      return { rowA: slotRowA, rowB: slotRowB, rowC: slotRowC, rowD: slotRowD }
    },
  },
}

function mountComp() {
  return mount(OrgList, { global: { renderStubDefaultSlot: true, stubs } })
}

function findBtn(wrapper: any, text: string) {
  const btn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes(text))
  expect(btn, `按钮「${text}」`).toBeTruthy()
  return btn!
}

/** 指定 URL 的默认 apiRequest 实现 */
function defaultApiImpl(config: any): Promise<any> {
  const url = config.url
  if (url === '/organizations/statistics/summary') {
    // res.data.data 嵌套侧（fetchStats 的 || 左侧）
    return Promise.resolve({
      data: { data: { total: 4, active: 3, inactive: 1, total_members: 10, orgs_with_members: 2 } },
    })
  }
  if (url === '/organizations') {
    return Promise.resolve({ data: { items: [orgRow1, orgRow2], total: 2 } })
  }
  if (url === '/organizations/export/list') {
    return Promise.resolve(new Blob(['x']))
  }
  return Promise.resolve({ data: {} })
}

beforeEach(() => {
  vi.resetAllMocks()
  authState.isAdmin = true
  mockApiRequest.mockImplementation(defaultApiImpl)
  mockPost.mockResolvedValue({ data: {} })
  mockPut.mockResolvedValue({ data: {} })
  mockDel.mockResolvedValue({ data: { message: '组织已删除' } })
  confirmMock.mockResolvedValue(undefined)
  promptMock.mockResolvedValue({ value: 'pass123' })
  mockBatchSort.mockResolvedValue({ data: {} })
  mockPushSafe.mockResolvedValue(undefined)
  sortableBox.opts = null
  sortableBox.instances = []
  sortableCreate.mockImplementation((_el: any, opts: any) => {
    sortableBox.opts = opts
    const inst = { destroy: vi.fn() }
    sortableBox.instances.push(inst)
    return inst
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ==================== 测试 ====================

describe('挂载与数据加载', () => {
  it('onMounted 并行加载列表与统计（admin 全量渲染）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'GET',
        url: '/organizations',
        params: expect.objectContaining({ page: 1, page_size: 20, is_active: true }),
      })
    )
    // search/org_type 空 → || undefined 兜底侧
    const listCall = mockApiRequest.mock.calls.find((c: any) => c[0].url === '/organizations')
    expect(listCall[0].params.search).toBeUndefined()
    expect(listCall[0].params.org_type).toBeUndefined()

    expect(vm.tableData).toHaveLength(2)
    expect(vm.total).toBe(2)
    expect(vm.stats).toMatchObject({ total: 4, active: 3, total_members: 10, orgs_with_members: 2 })
    expect(vm.statsLoading).toBe(false)
    expect(vm.loading).toBe(false)

    const text = wrapper.text()
    expect(text).toContain('组织管理')
    expect(text).toContain('10') // total_members 渲染
    expect(text).toContain('拖拽表格行') // drag-tip（isAdmin && !search && !filter 真侧）
    findBtn(wrapper, '导出')
    findBtn(wrapper, '新增组织')
  })

  it('fetchStats：res.data 扁平侧 + 字段缺失全兜底为 0', async () => {
    mockApiRequest.mockImplementation((config: any) => {
      if (config.url === '/organizations/statistics/summary') {
        return Promise.resolve({ data: { total: 7 } }) // res.data?.data 空 → || res.data 侧
      }
      return defaultApiImpl(config)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.stats).toMatchObject({ total: 7, active: 0, total_members: 0, orgs_with_members: 0 })

    // res.data 整体缺失 → data undefined → data?.x || 0 全兜底
    mockApiRequest.mockResolvedValueOnce({})
    await vm.fetchStats()
    expect(vm.stats).toMatchObject({ total: 0, active: 0 })
  })

  it('fetchStats 异常静默失败', async () => {
    mockApiRequest.mockImplementation((config: any) => {
      if (config.url === '/organizations/statistics/summary')
        return Promise.reject(new Error('net'))
      return defaultApiImpl(config)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.statsLoading).toBe(false)
    expect(vm.stats.total).toBe(0)
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('fetchData：items / data.items / 数组 / 空 四种响应形状与 total 三级兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // resData.data.items 侧 + resData.data.total 侧
    mockApiRequest.mockResolvedValueOnce({ data: { data: { items: [orgRow1], total: 5 } } })
    await vm.fetchData()
    expect(vm.tableData).toHaveLength(1)
    expect(vm.total).toBe(5)

    // 裸数组侧 + total 兜底 tableData.length
    mockApiRequest.mockResolvedValueOnce({ data: [orgRow1, orgRow2] })
    await vm.fetchData()
    expect(vm.tableData).toHaveLength(2)
    expect(vm.total).toBe(2)

    // 空响应 → [] 兜底 + length 兜底
    mockApiRequest.mockResolvedValueOnce({ data: null })
    await vm.fetchData()
    expect(vm.tableData).toEqual([])
    expect(vm.total).toBe(0)
  })

  it('fetchData 异常 → logger.error 且 loading 复位', async () => {
    mockApiRequest.mockImplementation((config: any) => {
      if (config.url === '/organizations') return Promise.reject(new Error('boom'))
      return defaultApiImpl(config)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(logError).toHaveBeenCalled()
    expect(vm.loading).toBe(false)
  })
})

describe('搜索 / 筛选 / 分页', () => {
  it('handleSearch 携带 search/org_type 值侧并复位页码；handlePageChange 翻页', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.searchText = '总部'
    vm.filterType = 'department'
    vm.currentPage = 3
    vm.handleSearch()
    await flushPromises()
    expect(vm.currentPage).toBe(1)
    const lastCall = mockApiRequest.mock.calls
      .filter((c: any) => c[0].url === '/organizations')
      .pop()
    expect(lastCall[0].params).toMatchObject({ search: '总部', org_type: 'department', page: 1 })

    vm.handlePageChange(2)
    await flushPromises()
    expect(vm.currentPage).toBe(2)
  })

  it('模板 v-model/事件：搜索框、类型下拉、分页器', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    const searchInput = wrapper.findAllComponents({ name: 'ElInput' })[0]
    searchInput.vm.$emit('update:modelValue', '分部')
    expect(vm.searchText).toBe('分部')
    searchInput.vm.$emit('clear') // @clear="handleSearch"
    await flushPromises()
    expect(vm.currentPage).toBe(1)

    const typeSelect = wrapper.findAllComponents({ name: 'ElSelect' })[0]
    typeSelect.vm.$emit('update:modelValue', 'support_unit')
    expect(vm.filterType).toBe('support_unit')
    typeSelect.vm.$emit('change') // @change="handleSearch"
    await flushPromises()

    // 分页器 v-if 假侧 → 真侧
    expect(wrapper.findAllComponents({ name: 'ElPagination' })).toHaveLength(0)
    vm.total = 30
    await nextTick()
    const pager = wrapper.findAllComponents({ name: 'ElPagination' })[0]
    pager.vm.$emit('current-change', 2)
    await flushPromises()
    expect(vm.currentPage).toBe(2)
  })
})

describe('表格列插槽与行交互', () => {
  it('类型/层级/状态列全分支渲染（department/support_unit/其他/空、level_*、非匹配、空）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('部门单位')
    expect(text).toContain('帮扶单位')
    expect(text).toContain('custom_type') // v-else 且 org_type 真值侧
    expect(text).toContain('未设置') // org_type 空 → ||'未设置'；level null/0 → formatLevel 未设置
    expect(text).toContain('第2级') // level_2 匹配
    expect(text).toContain('正常')
    expect(text).toContain('停用')
  })

  it('点击组织名链接与「详情」按钮 → pushSafe 跳转', async () => {
    const wrapper = mountComp()
    await flushPromises()

    await wrapper.find('.org-name-link').trigger('click')
    expect(mockPushSafe).toHaveBeenCalledWith('/organizations/1')

    const detailBtn = findBtn(wrapper, '详情')
    await detailBtn.trigger('click')
    expect(mockPushSafe).toHaveBeenCalledTimes(2)
  })

  it('点击「编辑」填充表单并打开对话框（dialogTitle 编辑侧）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await findBtn(wrapper, '编辑').trigger('click')
    expect(vm.dialogVisible).toBe(true)
    expect(vm.dialogTitle).toBe('编辑组织')
    expect(vm.formData).toMatchObject({
      id: 1,
      name: '甲组织',
      org_type: 'department',
      parent_id: null,
    })
  })

  it('点击「删除」弹密码确认框并携带 confirm_password', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await findBtn(wrapper, '删除').trigger('click')
    await flushPromises()
    expect(promptMock).toHaveBeenCalled()
    expect(mockDel).toHaveBeenCalledWith('/organizations/1?confirm_password=pass123')
  })

  it('删除时密码前后空白会被 trim 后传递', async () => {
    promptMock.mockResolvedValue({ value: '  pass123  ' })
    const wrapper = mountComp()
    await flushPromises()
    await findBtn(wrapper, '删除').trigger('click')
    await flushPromises()
    expect(mockDel).toHaveBeenCalledWith('/organizations/1?confirm_password=pass123')
  })

  it('非 admin：无导出/新增按钮，操作列仅详情，initSortable 早退（!isAdmin 侧）', async () => {
    authState.isAdmin = false
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(wrapper.findAll('el-button-stub').some((b: any) => b.text().includes('新增组织'))).toBe(
      false
    )
    expect(wrapper.findAll('el-button-stub').some((b: any) => b.text().includes('导出'))).toBe(
      false
    )
    expect(wrapper.text()).not.toContain('拖拽表格行')
    expect(findBtn(wrapper, '详情')).toBeTruthy()
    expect(wrapper.findAll('el-button-stub').some((b: any) => b.text().includes('编辑'))).toBe(
      false
    )
    expect(sortableCreate).not.toHaveBeenCalled()
    expect(vm.isAdmin).toBe(false)

    // v-else 操作列「详情」按钮（L135 onClick）
    await findBtn(wrapper, '详情').trigger('click')
    expect(mockPushSafe).toHaveBeenCalledWith('/organizations/1')
  })
})

describe('对话框与表单提交', () => {
  it('「新增组织」按钮打开对话框；全部 v-model 同步 formData；「取消」内联语句关闭', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await findBtn(wrapper, '新增组织').trigger('click')
    expect(vm.dialogVisible).toBe(true)
    expect(vm.dialogTitle).toBe('新增组织')
    expect(vm.formData.id).toBeNull()

    const dialog = wrapper.findComponent({ name: 'ElDialog' })
    const inputs = dialog.findAllComponents({ name: 'ElInput' })
    // name / contact_person / contact_phone / address / description
    inputs[0].vm.$emit('update:modelValue', '新组织')
    inputs[1].vm.$emit('update:modelValue', '李四')
    inputs[2].vm.$emit('update:modelValue', '139')
    inputs[3].vm.$emit('update:modelValue', '北京市')
    inputs[4].vm.$emit('update:modelValue', '备注说明')
    expect(vm.formData).toMatchObject({
      name: '新组织',
      contact_person: '李四',
      contact_phone: '139',
      address: '北京市',
      description: '备注说明',
    })

    const selects = dialog.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 2) // parent_id
    selects[1].vm.$emit('update:modelValue', 'support_unit') // org_type
    expect(vm.formData.parent_id).toBe(2)
    expect(vm.formData.org_type).toBe('support_unit')

    dialog.findAllComponents({ name: 'ElSwitch' })[0].vm.$emit('update:modelValue', false)
    expect(vm.formData.is_active).toBe(false)

    // el-dialog v-model 内联 onUpdate
    dialog.vm.$emit('update:modelValue', false)
    expect(vm.dialogVisible).toBe(false)

    await findBtn(wrapper, '取消').trigger('click') // @click="dialogVisible = false"
    expect(vm.dialogVisible).toBe(false)
  })

  it('handleSubmit 创建：validate 通过 → post 并刷新列表/统计（payload 剔除 id）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const formRefMock = { validate: vi.fn().mockResolvedValue(true), resetFields: vi.fn() }
    vm.formRef = formRefMock // 每次调用前重新赋值（重渲染会把 ref 同步回 stub 实例）

    vm.handleCreate()
    vm.formData.name = '新组织'
    vm.formRef = formRefMock
    await vm.handleSubmit()
    await flushPromises()

    expect(formRefMock.validate).toHaveBeenCalled()
    const [url, payload] = mockPost.mock.calls[0]
    expect(url).toBe('/organizations')
    expect(payload).toMatchObject({ name: '新组织', org_type: 'department' })
    expect('id' in payload).toBe(false)
    expect(ElMessage.success).toHaveBeenCalledWith('已创建')
    expect(vm.dialogVisible).toBe(false)
    expect(vm.submitting).toBe(false)
    // 提交后重新拉取列表与统计
    expect(
      mockApiRequest.mock.calls.filter((c: any) => c[0].url === '/organizations').length
    ).toBeGreaterThan(1)
  })

  it('handleSubmit 编辑：put 到 /organizations/{id}；「确定」按钮点击触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const formRefMock = { validate: vi.fn().mockResolvedValue(true), resetFields: vi.fn() }

    vm.handleEdit({ id: 2, name: '分部', parent_id: 1, org_type: 'support_unit', is_active: false })
    expect(vm.dialogTitle).toBe('编辑组织')

    vm.formRef = formRefMock
    await findBtn(wrapper, '确定').trigger('click')
    await flushPromises()

    const [url, payload] = mockPut.mock.calls[0]
    expect(url).toBe('/organizations/2')
    expect(payload).toMatchObject({ name: '分部', is_active: false })
    // 成功静默：保存成功不弹提示（v1.8.0 提示策略）
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('handleSubmit：无 formRef 直接返回；validate 失败返回不发请求', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.formRef = undefined
    await vm.handleSubmit()
    expect(mockPost).not.toHaveBeenCalled()

    vm.formRef = { validate: vi.fn().mockRejectedValue(new Error('invalid')), resetFields: vi.fn() }
    await vm.handleSubmit()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('handleSubmit 接口异常：err.message 侧与默认「操作失败」侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const formRefMock = { validate: vi.fn().mockResolvedValue(true), resetFields: vi.fn() }

    mockPost.mockRejectedValueOnce(new Error('名称重复'))
    vm.formRef = formRefMock
    await vm.handleSubmit()
    expect(ElMessage.error).toHaveBeenCalledWith('名称重复')
    expect(vm.submitting).toBe(false)

    mockPost.mockRejectedValueOnce({})
    vm.formRef = formRefMock
    await vm.handleSubmit()
    expect(ElMessage.error).toHaveBeenCalledWith('操作失败')
  })

  it('handleDialogClose：formRef 有/无两侧（resetFields 调用与否）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const resetFields = vi.fn()

    vm.formRef = { resetFields, validate: vi.fn() }
    const dialog = wrapper.findComponent({ name: 'ElDialog' })
    dialog.vm.$emit('close') // 模板 @close="handleDialogClose"
    expect(resetFields).toHaveBeenCalled()

    vm.formRef = undefined
    expect(() => vm.handleDialogClose()).not.toThrow()
  })

  it('handleEdit 兜底链：name/parent_id/org_type/is_active 各 || 侧；parentOrgOptions 排除后代', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.handleEdit({})
    expect(vm.formData).toMatchObject({
      name: '',
      parent_id: null,
      org_type: 'department',
      is_active: true,
    })

    vm.handleEdit({ type: 'support_unit', is_active: false })
    expect(vm.formData.org_type).toBe('support_unit') // row.type 侧
    expect(vm.formData.is_active).toBe(false)

    // parentOrgOptions：无 id → 全量；有 id → 排除自身及后代（含跨级）
    vm.tableData = [
      { id: 1, parent_id: null },
      { id: 2, parent_id: 1 },
      { id: 3, parent_id: 2 },
      { id: 4, parent_id: 9 },
    ]
    vm.handleCreate()
    expect(vm.parentOrgOptions).toHaveLength(4)
    vm.handleEdit({ id: 1 })
    expect(vm.parentOrgOptions.map((o: any) => o.id)).toEqual([4])
  })
})

describe('删除组织全分支', () => {
  it('确认取消（reject "cancel" 字符串）→ 不发请求不报错', async () => {
    promptMock.mockRejectedValue('cancel')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete(orgRow1)
    expect(mockDel).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('确认取消（toString()==="cancel" 对象）→ 第二条件短路不报错', async () => {
    promptMock.mockRejectedValue({ toString: () => 'cancel' })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete(orgRow1)
    expect(mockDel).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('删除成功：后端 message 侧与默认「组织已删除」侧，成功后刷新列表/统计', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // del() 已自动解包（返回 res.data），message 在顶层
    mockDel.mockResolvedValueOnce({ message: '已停用' })
    await vm.handleDelete(orgRow1)
    expect(ElMessage.success).toHaveBeenCalledWith('已停用')
    expect(vm.currentPage).toBe(1)

    mockDel.mockResolvedValueOnce({})
    await vm.handleDelete(orgRow2)
    expect(ElMessage.success).toHaveBeenCalledWith('组织已删除')
  })

  it('删除失败：detail / err.message / 默认 三级兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    mockDel.mockRejectedValueOnce({ response: { data: { detail: '存在子组织' } } })
    await vm.handleDelete(orgRow1)
    expect(ElMessage.error).toHaveBeenCalledWith('存在子组织')

    mockDel.mockRejectedValueOnce(new Error('网络错误'))
    await vm.handleDelete(orgRow1)
    expect(ElMessage.error).toHaveBeenCalledWith('网络错误')

    mockDel.mockRejectedValueOnce({})
    await vm.handleDelete(orgRow1)
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })

  it('删除确认框 inputValidator：空值 / 纯空白 / 合法输入 全分支', async () => {
    let validator: any = null
    promptMock.mockImplementation((_msg: any, _title: any, opts: any) => {
      validator = opts?.inputValidator
      return Promise.resolve({ value: 'pass123' })
    })
    const wrapper = mountComp()
    await flushPromises()
    await findBtn(wrapper, '删除').trigger('click')
    await flushPromises()

    expect(validator).toBeDefined()
    expect(validator('')).toBe('请输入密码') // v 空串 → && 短路
    expect(validator('   ')).toBe('请输入密码') // v 有值但 trim 后为空
    expect(validator('pass')).toBe(true) // 合法输入
    expect(mockDel).toHaveBeenCalledWith('/organizations/1?confirm_password=pass123')
  })

  it('删除时密码 value 为 null → value?.trim() ?? \'\' 兜底空串', async () => {
    promptMock.mockResolvedValueOnce({ value: null })
    const wrapper = mountComp()
    await flushPromises()
    await findBtn(wrapper, '删除').trigger('click')
    await flushPromises()
    expect(mockDel).toHaveBeenCalledWith('/organizations/1?confirm_password=')
  })
})

describe('导出', () => {
  it('导出成功：创建 a 标签下载并提示；filterType 值侧/空侧参数', async () => {
    const link = document.createElement('a')
    link.click = vi.fn()
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: any) =>
      tag === 'a' ? link : realCreate(tag)
    )

    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.filterType = 'department'

    await findBtn(wrapper, '导出').trigger('click')
    await flushPromises()

    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'GET',
        url: '/organizations/export/list',
        responseType: 'blob',
        params: { org_type: 'department' },
      })
    )
    expect(link.download).toBe('组织机构列表.xlsx')
    expect(link.click).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('导出成功')
    expect(vm.exporting).toBe(false)
  })

  it('导出失败：提示「导出失败」并复位 exporting', async () => {
    mockApiRequest.mockImplementation((config: any) => {
      if (config.url === '/organizations/export/list') return Promise.reject(new Error('net'))
      return defaultApiImpl(config)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleExport()
    expect(ElMessage.error).toHaveBeenCalledWith('导出失败')
    expect(vm.exporting).toBe(false)
    // filterType 空 → params.org_type undefined 侧
    const call = mockApiRequest.mock.calls.find(
      (c: any) => c[0].url === '/organizations/export/list'
    )
    expect(call[0].params.org_type).toBeUndefined()
  })
})

describe('拖拽排序 initSortable / onEnd', () => {
  it('searchText / filterType 非空时早退，不再新建实例', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await nextTick()
    const vm = wrapper.vm as any
    expect(sortableCreate).toHaveBeenCalledTimes(1) // 挂载即创建（admin 无筛选）

    vm.searchText = 'x'
    vm.initSortable()
    await nextTick()
    expect(sortableCreate).toHaveBeenCalledTimes(1)

    vm.searchText = ''
    vm.filterType = 'department'
    vm.initSortable()
    await nextTick()
    expect(sortableCreate).toHaveBeenCalledTimes(1)
  })

  it('重复初始化销毁旧实例 + !tbody 早退 + onEnd 全分支（同索引/保存成功/保存失败）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await nextTick()
    const vm = wrapper.vm as any
    expect(sortableCreate).toHaveBeenCalledTimes(1)

    // handleSearch → fetchDataWithSort → 重复初始化销毁旧实例并新建
    vm.handleSearch()
    await flushPromises()
    await nextTick()
    expect(sortableBox.instances[0].destroy).toHaveBeenCalled()
    expect(sortableCreate).toHaveBeenCalledTimes(2)

    // tbody 从 DOM 移除 → nextTick 回调 !tbody 早退
    wrapper.find('.el-table__body-wrapper tbody').element.remove()
    vm.initSortable()
    await nextTick()
    expect(sortableCreate).toHaveBeenCalledTimes(2)

    const onEnd = sortableBox.opts.onEnd

    // oldIndex === newIndex 早退
    vm.tableData = [{ id: 1 }, { id: 2 }]
    await onEnd({ oldIndex: 1, newIndex: 1 })
    expect(mockBatchSort).not.toHaveBeenCalled()

    // 拖拽成功 → 行重排 + 保存排序
    await onEnd({ oldIndex: 0, newIndex: 1 })
    expect(mockBatchSort).toHaveBeenCalledWith([
      { id: 2, sort_order: 1 },
      { id: 1, sort_order: 2 },
    ])
    expect(ElMessage.success).toHaveBeenCalledWith('排序已保存')

    // 保存失败：detail 侧 → 报错并重新拉取
    const callsBefore = mockApiRequest.mock.calls.filter(
      (c: any) => c[0].url === '/organizations'
    ).length
    mockBatchSort.mockRejectedValueOnce({ response: { data: { detail: '排序冲突' } } })
    await onEnd({ oldIndex: 0, newIndex: 1 })
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('排序冲突')
    expect(
      mockApiRequest.mock.calls.filter((c: any) => c[0].url === '/organizations').length
    ).toBeGreaterThan(callsBefore)

    // 保存失败：默认提示侧
    mockBatchSort.mockRejectedValueOnce(new Error('boom'))
    await onEnd({ oldIndex: 0, newIndex: 1 })
    expect(ElMessage.error).toHaveBeenCalledWith('保存排序失败')
  })
})

describe('formatLevel', () => {
  it('空值 / level_N 匹配 / 非匹配透传', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.formatLevel(null)).toBe('未设置')
    expect(vm.formatLevel(0)).toBe('未设置')
    expect(vm.formatLevel('level_3')).toBe('第3级')
    expect(vm.formatLevel(5)).toBe('5')
    expect(vm.formatLevel('abc')).toBe('abc')
  })
})
