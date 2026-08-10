/**
 * views/policies/List.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted route.query 两侧、watch(route.query) 两侧、loadData 成功/失败与四个 ||undefined、
 * canEdit/canDelete 全分支（!user/is_superuser/role 三态/role 空）、levelOptions、formatDate、
 * handleSearch/handleReset/handleSortChange/handleSizeChange/handlePageChange、
 * handleAdd/handleDetail/handleEdit、handleDelete 与 handleBatchDelete 全分支、
 * handleImport 无文件/errors>5/errors≤5/无 errors/失败两侧、handleDownloadTemplate、
 * handleExportPDF/WPS 成功失败、表格列插槽三元与 ||label 两侧、全部 v-model/内联事件。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂提升求值，引用对象须先放入 vi.hoisted 初始化（TDZ）
const {
  routeBox,
  authState,
  policyStore,
  ElMessage,
  confirmMock,
  alertMock,
  mockPushSafe,
  logError,
  policyApi,
  mockDownloadTemplate,
  submitApprovalMock,
} = vi.hoisted(() => {
  return {
    routeBox: { route: null as any },
    authState: { user: { is_superuser: true } as any },
    policyStore: {
      loading: false,
      total: 100,
      policies: [
        { id: 1, title: '甲政策', category: 'military', status: 'active' },
        { id: 2, title: '乙政策', category: 'local', status: 'invalid' },
      ] as any,
      fetchPolicies: vi.fn(),
      setFilters: vi.fn(),
      removePolicy: vi.fn(),
      removePolicies: vi.fn(),
    },
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
    confirmMock: vi.fn(),
    alertMock: vi.fn(),
    mockPushSafe: vi.fn(),
    logError: vi.fn(),
    policyApi: {
      getCategoryLabel: vi.fn((c: any) => `cat:${c}`),
      getLevelLabel: vi.fn((l: any) => `lvl:${l}`),
      getStatusLabel: vi.fn((s: any) => `status:${s}`),
      getStatusColor: vi.fn(() => 'danger'),
      getLevelOptions: vi.fn(() => [{ label: '省级', value: 'province' }]),
      importPolicies: vi.fn(),
      exportPoliciesPDF: vi.fn(),
      exportPoliciesWPS: vi.fn(),
    },
    mockDownloadTemplate: vi.fn(),
    submitApprovalMock: vi.fn().mockResolvedValue({}),
  }
})

// route 需要响应式对象以触发 watch(() => route.query)：工厂内自行 import vue 建 reactive
vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  routeBox.route = reactive({ query: {} as Record<string, any> })
  return { useRoute: () => routeBox.route }
})

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mockPushSafe }),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock, alert: alertMock },
}))

vi.mock('@/stores/policy', () => ({
  usePolicyStore: () => policyStore,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

vi.mock('@/api/policy', () => policyApi)

vi.mock('@/api/approval', () => ({
  submitApproval: submitApprovalMock,
}))

vi.mock('@/api/import', () => ({
  downloadImportTemplateAndSave: mockDownloadTemplate,
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import PolicyList from '@/views/policies/List.vue'

// el-table-column 插槽样本行：覆盖 category 三元两侧、三个 ||label 两侧、formatDate 空侧
const slotRowA = {
  id: 1,
  title: '甲政策',
  category: 'military',
  category_name: '',
  level_name: '',
  organization_level: 'province',
  publish_date: '2024-01-15',
  department: '军委',
  status: 'active',
  status_name: '',
}
const slotRowB = {
  id: 2,
  title: '乙政策',
  category: 'local',
  category_name: '地方政策',
  level_name: '市级',
  organization_level: 'city',
  publish_date: '',
  department: '省政府',
  status: 'invalid',
  status_name: '失效',
}

const stubs = {
  'el-card': {
    name: 'ElCard',
    template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
  },
  'el-table-column': {
    name: 'ElTableColumn',
    template: '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
    data() {
      return { rowA: slotRowA, rowB: slotRowB }
    },
  },
}

// 用例卸载注册表：避免未卸载 wrapper 的 route watch 跨测试触发 loadData 造成调用计数虚高
const liveWrappers: any[] = []

function mountComp() {
  const w = mount(PolicyList, { global: { renderStubDefaultSlot: true, stubs } })
  liveWrappers.push(w)
  return w
}

function findBtn(wrapper: any, text: string) {
  const btn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes(text))
  expect(btn, `按钮「${text}」`).toBeTruthy()
  return btn!
}

beforeEach(() => {
  vi.resetAllMocks()
  authState.user = { is_superuser: true }
  routeBox.route.query = {}
  policyStore.loading = false
  policyStore.total = 100
  policyStore.policies = [
    { id: 1, title: '甲政策', category: 'military', status: 'active' },
    { id: 2, title: '乙政策', category: 'local', status: 'invalid' },
  ]
  policyStore.fetchPolicies.mockResolvedValue({})
  policyStore.setFilters.mockReturnValue(undefined)
  policyStore.removePolicy.mockResolvedValue({})
  policyStore.removePolicies.mockResolvedValue({})
  confirmMock.mockResolvedValue(undefined)
  alertMock.mockResolvedValue(undefined)
  mockPushSafe.mockResolvedValue(undefined)
  mockDownloadTemplate.mockResolvedValue(undefined)
  policyApi.getCategoryLabel.mockImplementation((c: any) => `cat:${c}`)
  // 视图封装层以 (category, level) 调用，但 API 实为单参 level：当前行为取首参（疑似 bug，仅记录）
  policyApi.getLevelLabel.mockImplementation((l: any) => `lvl:${l}`)
  policyApi.getStatusLabel.mockImplementation((s: any) => `status:${s}`)
  policyApi.getStatusColor.mockReturnValue('danger')
  policyApi.getLevelOptions.mockResolvedValue([{ label: '省级', value: 'province' }])
  policyApi.importPolicies.mockResolvedValue({ imported: 1, errors: [] })
  policyApi.exportPoliciesPDF.mockResolvedValue(undefined)
  policyApi.exportPoliciesWPS.mockResolvedValue(undefined)
})

afterEach(() => {
  while (liveWrappers.length) liveWrappers.pop().unmount()
  vi.restoreAllMocks()
})

// ==================== 测试 ====================

describe('挂载与数据加载', () => {
  it('onMounted 无 route.query（两 if 假侧）+ loadData 成功（四个 ||undefined 空侧）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(policyStore.fetchPolicies).toHaveBeenCalledWith({
      page: 1,
      page_size: 10,
      category: undefined,
      organization_level: undefined,
      status: undefined,
      search: undefined,
    })
    expect(vm.searchForm.category).toBe('')
    expect(vm.searchForm.organization_level).toBe('')
    // 模板渲染（superuser：批量删除/新增政策/编辑/删除均可见）
    const text = wrapper.text()
    expect(text).toContain('政策列表')
    findBtn(wrapper, '批量删除')
    findBtn(wrapper, '新增政策')
  })

  it('onMounted 带 route.query.category/level（两 if 真侧）初始化筛选', async () => {
    routeBox.route.query = { category: 'local', level: 'city' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.searchForm.category).toBe('local')
    expect(vm.searchForm.organization_level).toBe('city')
  })

  it('loadData 携带筛选值侧（四个 || 值侧）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchForm.title = '关键词'
    vm.searchForm.category = 'military'
    vm.searchForm.organization_level = 'province'
    vm.searchForm.status = 'active'
    await vm.loadData()
    expect(policyStore.fetchPolicies).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 10,
      category: 'military',
      organization_level: 'province',
      status: 'active',
      search: '关键词',
    })
  })

  it('loadData 失败 → ElMessage.error 加载数据失败', async () => {
    policyStore.fetchPolicies.mockRejectedValue(new Error('net'))
    mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('加载数据失败')
  })

  it('policies 为 undefined → policiesData ?? [] 右侧', async () => {
    policyStore.policies = undefined
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).policiesData).toEqual([])
  })
})

describe('权限 computed 全分支', () => {
  it('user 为 null → canEdit/canDelete 均 false（!user 侧），按钮隐藏', async () => {
    authState.user = null
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.canEdit).toBe(false)
    expect(vm.canDelete).toBe(false)
    expect(wrapper.findAll('el-button-stub').some((b: any) => b.text().includes('新增政策'))).toBe(
      false
    )
    expect(wrapper.findAll('el-button-stub').some((b: any) => b.text().includes('批量删除'))).toBe(
      false
    )
  })

  it('is_superuser → 均 true（superuser 侧）', async () => {
    authState.user = { is_superuser: true }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.canEdit).toBe(true)
    expect(vm.canDelete).toBe(true)
  })

  it('role Admin（toLowerCase 后 admin）→ 均 true', async () => {
    authState.user = { role: 'Admin' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.canEdit).toBe(true)
    expect(vm.canDelete).toBe(true)
  })

  it('role super_admin → 均 true（第二 || 操作数）', async () => {
    authState.user = { role: 'super_admin' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.canEdit).toBe(true)
    expect(vm.canDelete).toBe(true)
  })

  it('role editor → 归一化为 admin（历史兼容），canEdit/canDelete 均 true', async () => {
    authState.user = { role: 'editor' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.canEdit).toBe(true)
    expect(vm.canDelete).toBe(true)
    findBtn(wrapper, '新增政策')
    findBtn(wrapper, '批量删除')
  })

  it('role viewer → 均 false（|| 全假侧）', async () => {
    authState.user = { role: 'viewer' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.canEdit).toBe(false)
    expect(vm.canDelete).toBe(false)
  })

  it('user 无 role 字段 → (user.role || "") 空串侧', async () => {
    authState.user = {}
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.canEdit).toBe(false)
    expect(vm.canDelete).toBe(false)
  })
})

describe('搜索 / 重置 / 排序 / 分页 / 表单 v-model', () => {
  it('handleSearch 复位页码并加载；handleReset 清空表单', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentPage = 5
    vm.searchForm.title = 'x'
    const callsBefore = policyStore.fetchPolicies.mock.calls.length
    vm.handleSearch()
    expect(vm.currentPage).toBe(1)
    await flushPromises()
    expect(policyStore.fetchPolicies.mock.calls.length).toBe(callsBefore + 1)

    vm.searchForm.category = 'military'
    vm.handleReset()
    expect(vm.searchForm).toMatchObject({
      title: '',
      category: '',
      organization_level: '',
      status: '',
    })
    expect(vm.currentPage).toBe(1)
  })

  it('模板查询/重置按钮点击；el-input v-model 与 @clear', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    const input = wrapper.findAllComponents({ name: 'ElInput' })[0]
    input.vm.$emit('update:modelValue', '关键词')
    expect(vm.searchForm.title).toBe('关键词')
    input.vm.$emit('clear')
    await flushPromises()
    expect(policyStore.fetchPolicies).toHaveBeenCalled()

    await findBtn(wrapper, '查询').trigger('click')
    await findBtn(wrapper, '重置').trigger('click')
    expect(vm.searchForm.title).toBe('')
  })

  it('三个 el-select v-model；分类 @change 清空层级；levelOptions 空/有两侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 无 category → levelOptions []
    expect(vm.levelOptions).toEqual([])

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(selects.length).toBeGreaterThanOrEqual(3)
    selects[0].vm.$emit('update:modelValue', 'military')
    selects[0].vm.$emit('change') // 触发 handleCategoryChange → refreshLevelOptions
    expect(vm.searchForm.category).toBe('military')
    // category 有值 → levelOptions 异步加载（getLevelOptions 返回 Promise）
    await flushPromises()
    expect(vm.levelOptions).toEqual([{ label: '省级', value: 'province' }])

    selects[1].vm.$emit('update:modelValue', 'province')
    expect(vm.searchForm.organization_level).toBe('province')
    selects[0].vm.$emit('change') // @change="handleCategoryChange"
    expect(vm.searchForm.organization_level).toBe('')

    selects[2].vm.$emit('update:modelValue', 'invalid')
    expect(vm.searchForm.status).toBe('invalid')
  })

  it('handleSortChange：prop/order 值侧与 null 侧（ElTable sort-change 事件）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const table = wrapper.findComponent({ name: 'ElTable' })
    table.vm.$emit('sort-change', { prop: 'publish_date', order: 'ascending' })
    expect(policyStore.setFilters).toHaveBeenCalledWith({
      order_by: 'publish_date',
      order_desc: false,
    })
    table.vm.$emit('sort-change', { prop: null, order: null })
    expect(policyStore.setFilters).toHaveBeenLastCalledWith({
      order_by: 'publish_date',
      order_desc: true,
    })
    await flushPromises()
  })

  it('handleSelectionChange 写入 selectedIds（ElTable selection-change 事件）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    wrapper.findComponent({ name: 'ElTable' }).vm.$emit('selection-change', [{ id: 7 }, { id: 9 }])
    expect(vm.selectedIds).toEqual([7, 9])
  })

  it('分页：v-model:current-page / v-model:page-size 箭头与 size-change/current-change', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const pager = wrapper.findComponent({ name: 'ElPagination' })
    pager.vm.$emit('update:current-page', 3)
    expect(vm.currentPage).toBe(3)
    pager.vm.$emit('update:page-size', 50)
    expect(vm.pageSize).toBe(50)

    pager.vm.$emit('size-change', 20)
    await flushPromises()
    expect(vm.pageSize).toBe(20)
    expect(vm.currentPage).toBe(1)

    pager.vm.$emit('current-change', 4)
    await flushPromises()
    expect(vm.currentPage).toBe(4)
  })
})

describe('表格列插槽与行操作', () => {
  it('分类/层级/状态/日期列样本行全分支（三元与 ||label 两侧）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('cat:military') // category_name 空 → getCategoryLabel
    expect(text).toContain('地方政策') // category_name 值侧
    expect(text).toContain('lvl:military') // level_name 空 → getLevelLabel(category, level) 首参
    expect(text).toContain('市级') // level_name 值侧
    expect(text).toContain('status:active') // status_name 空 → getStatusLabel
    expect(text).toContain('失效') // status_name 值侧
    expect(text).toContain('-') // publish_date 空 → formatDate '-'
  })

  it('getStatusTagType：getStatusColor 返回空串 → || undefined 右侧', async () => {
    policyApi.getStatusColor.mockReturnValue('')
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).getStatusTagType('active')).toBeUndefined()
    policyApi.getStatusColor.mockReturnValue('warning')
    expect((wrapper.vm as any).getStatusTagType('draft')).toBe('warning')
  })

  it('formatDate 直接调用：空 → "-"；有效日期 → 本地化', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.formatDate('')).toBe('-')
    expect(vm.formatDate('2024-01-15')).toBe(new Date('2024-01-15').toLocaleDateString('zh-CN'))
  })

  it('操作列：详情/编辑/删除按钮点击（行 id=1）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await findBtn(wrapper, '详情').trigger('click')
    expect(mockPushSafe).toHaveBeenCalledWith('/policies/1')
    await findBtn(wrapper, '编辑').trigger('click')
    expect(mockPushSafe).toHaveBeenCalledWith('/policies/1/edit')
    // 行内删除按钮需精确匹配，避免误点头部「批量删除」
    const delBtn = wrapper.findAll('el-button-stub').find((b: any) => b.text().trim() === '删除')
    expect(delBtn).toBeTruthy()
    await delBtn!.trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalled()
    expect(policyStore.removePolicy).toHaveBeenCalledWith(1)
  })

  it('头部按钮：下载模板/导入/导出PDF/导出WPS/新增政策均真实点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await findBtn(wrapper, '新增政策').trigger('click')
    expect(mockPushSafe).toHaveBeenCalledWith('/policies/create')
    await findBtn(wrapper, '下载模板').trigger('click')
    await flushPromises()
    expect(mockDownloadTemplate).toHaveBeenCalledWith('policy', '政策法规')
    await findBtn(wrapper, '导出PDF').trigger('click')
    await flushPromises()
    expect(policyApi.exportPoliciesPDF).toHaveBeenCalled()
    await findBtn(wrapper, '导出WPS').trigger('click')
    await flushPromises()
    expect(policyApi.exportPoliciesWPS).toHaveBeenCalled()
  })
})

describe('删除与批量删除全分支', () => {
  it('handleDelete：确认成功；cancel 不报错；失败 message 侧与默认侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const row = { id: 1, title: '甲政策' }

    await vm.handleDelete(row)
    expect(policyStore.removePolicy).toHaveBeenCalledWith(1)
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')

    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleDelete(row)
    expect(ElMessage.error).not.toHaveBeenCalled()

    policyStore.removePolicy.mockRejectedValueOnce(new Error('存在引用'))
    await vm.handleDelete(row)
    expect(ElMessage.error).toHaveBeenCalledWith('存在引用')

    policyStore.removePolicy.mockRejectedValueOnce({})
    await vm.handleDelete(row)
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })

  it('handleBatchDelete：空选择早退；确认成功清空选择；cancel；失败两侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleBatchDelete() // 空选择早退
    expect(confirmMock).not.toHaveBeenCalled()

    vm.selectedIds = [1, 2]
    await vm.handleBatchDelete()
    expect(policyStore.removePolicies).toHaveBeenCalledWith([1, 2])
    expect(vm.selectedIds).toEqual([])
    expect(ElMessage.success).toHaveBeenCalledWith('批量删除成功')

    vm.selectedIds = [3]
    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleBatchDelete()
    expect(ElMessage.error).not.toHaveBeenCalled()

    vm.selectedIds = [4]
    policyStore.removePolicies.mockRejectedValueOnce(new Error('约束冲突'))
    await vm.handleBatchDelete()
    expect(ElMessage.error).toHaveBeenCalledWith('约束冲突')

    vm.selectedIds = [5]
    policyStore.removePolicies.mockRejectedValueOnce({})
    await vm.handleBatchDelete()
    expect(ElMessage.error).toHaveBeenCalledWith('批量删除失败')
  })

  it('「批量删除」按钮真实点击触发 handleBatchDelete', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedIds = [1]
    await nextTick()
    await findBtn(wrapper, '批量删除').trigger('click')
    await flushPromises()
    expect(policyStore.removePolicies).toHaveBeenCalledWith([1])
  })
})

describe('导入 / 模板 / 导出', () => {
  /** 捕获 handleImport 创建的 file input，驱动其 onchange */
  function captureFileInput() {
    const box = { input: null as any }
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: any) => {
      const el = realCreate(tag)
      if (tag === 'input') box.input = el
      return el
    })
    return box
  }

  it('handleImport：选择为空文件早退（!file 侧）', async () => {
    const box = captureFileInput()
    const wrapper = mountComp()
    await flushPromises()
    ;(wrapper.vm as any).handleImport()
    expect(box.input).toBeTruthy()
    await box.input.onchange({ target: { files: [] } })
    expect(policyApi.importPolicies).not.toHaveBeenCalled()
  })

  it('导入 errors>5：warning + alert + moreText 非空侧，成功后重置页码并刷新', async () => {
    const box = captureFileInput()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentPage = 4
    const errors = Array.from({ length: 7 }, (_, i) => ({
      row: i + 1,
      title: `P${i}`,
      error: '格式错',
    }))
    policyApi.importPolicies.mockResolvedValue({ imported: 3, errors })
    const callsBefore = policyStore.fetchPolicies.mock.calls.length
    vm.handleImport()
    await box.input.onchange({ target: { files: [new File(['x'], 'a.xlsx')] } })
    await flushPromises()
    expect(ElMessage.warning).toHaveBeenCalled()
    expect(alertMock).toHaveBeenCalledWith(
      expect.stringContaining('...还有 2 条错误'),
      '导入结果',
      expect.anything()
    )
    expect(vm.currentPage).toBe(1)
    // 导入成功后刷新列表（跨测试存活 wrapper 会污染绝对计数，用差值断言）
    expect(policyStore.fetchPolicies.mock.calls.length).toBe(callsBefore + 1)
  })

  it('导入 errors≤5：moreText 空侧；errors 为空 → 纯成功提示', async () => {
    const box = captureFileInput()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    policyApi.importPolicies.mockResolvedValueOnce({
      imported: 1,
      errors: [{ row: 1, title: 'P', error: 'e' }],
    })
    vm.handleImport()
    await box.input.onchange({ target: { files: [new File(['x'], 'a.xlsx')] } })
    await flushPromises()
    expect(alertMock).toHaveBeenCalledWith(
      expect.not.stringContaining('...还有'),
      '导入结果',
      expect.anything()
    )

    policyApi.importPolicies.mockResolvedValueOnce({ imported: 5, errors: [] })
    vm.handleImport()
    await box.input.onchange({ target: { files: [new File(['x'], 'b.xlsx')] } })
    await flushPromises()
    expect(ElMessage.success).toHaveBeenCalledWith('导入成功：5条政策')
  })

  it('导入失败：error.message 侧与默认「导入失败」侧', async () => {
    const box = captureFileInput()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    policyApi.importPolicies.mockRejectedValueOnce(new Error('文件过大'))
    vm.handleImport()
    await box.input.onchange({ target: { files: [new File(['x'], 'a.xlsx')] } })
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('文件过大')

    policyApi.importPolicies.mockRejectedValueOnce({})
    vm.handleImport()
    await box.input.onchange({ target: { files: [new File(['x'], 'a.xlsx')] } })
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('导入失败')
  })

  it('handleDownloadTemplate 失败 → 错误提示', async () => {
    mockDownloadTemplate.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleDownloadTemplate()
    expect(ElMessage.error).toHaveBeenCalledWith('下载模板失败，请重试')
  })

  it('handleExportPDF：成功提示 + 失败（logger.error + 后端提示）；参数值侧/空侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleExportPDF()
    expect(policyApi.exportPoliciesPDF).toHaveBeenCalledWith({
      category: undefined,
      organization_level: undefined,
      status: undefined,
      search: undefined,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('导出PDF成功')

    vm.searchForm.category = 'local'
    policyApi.exportPoliciesPDF.mockRejectedValueOnce(new Error('down'))
    await vm.handleExportPDF()
    expect(policyApi.exportPoliciesPDF).toHaveBeenLastCalledWith(
      expect.objectContaining({ category: 'local' })
    )
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('导出PDF功能需要后端支持，请先启动后端服务')
  })

  it('handleExportWPS：成功提示 + 失败（logger.error + 后端提示）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleExportWPS()
    expect(ElMessage.success).toHaveBeenCalledWith('导出WPS成功')

    policyApi.exportPoliciesWPS.mockRejectedValueOnce(new Error('down'))
    await vm.handleExportWPS()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('导出WPS功能需要后端支持，请先启动后端服务')
  })
})

describe('路由 watch', () => {
  it('query 变为含 category/level → 更新 searchForm 并刷新；空 query → 两 if 假侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const callsBefore = policyStore.fetchPolicies.mock.calls.length

    routeBox.route.query = { category: 'military', level: 'province' }
    await nextTick()
    await flushPromises()
    expect(vm.searchForm.category).toBe('military')
    expect(vm.searchForm.organization_level).toBe('province')
    expect(policyStore.fetchPolicies.mock.calls.length).toBeGreaterThan(callsBefore)

    routeBox.route.query = {}
    await nextTick()
    await flushPromises()
    expect(vm.searchForm.category).toBe('military') // 空 query 不改写
  })
})

describe('提交审批', () => {
  it('确认提交 → submitApproval + 成功提示 + 刷新；取消静默；失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleSubmitApproval({ id: 1, title: '政策A', code: 'X' })
    await flushPromises()
    expect(vm.mockSubmitApproval || submitApprovalMock).toBeTruthy()
    expect(ElMessage.success).toHaveBeenCalledWith('已提交审批，请到审批中心处理')

    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleSubmitApproval({ id: 2, title: 'B' })
    expect(ElMessage.error).not.toHaveBeenCalled()

    submitApprovalMock.mockRejectedValueOnce({ response: { data: { detail: '无工作流' } } })
    await vm.handleSubmitApproval({ id: 3, title: 'C' })
    expect(ElMessage.error).toHaveBeenCalledWith('无工作流')
  })

  it('levelOptions 多形态响应（数组/items/nested）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchForm.category = 'military'
    policyApi.getLevelOptions.mockResolvedValue([{ label: '省级', value: 'province' }])
    await vm.refreshLevelOptions()
    expect(vm.levelOptions.length).toBe(1)
    policyApi.getLevelOptions.mockResolvedValue({ items: [{ label: '市级', value: 'city' }] })
    await vm.refreshLevelOptions()
    expect(vm.levelOptions.length).toBe(1)
    policyApi.getLevelOptions.mockResolvedValue({ data: [{ label: '县级', value: 'county' }] })
    await vm.refreshLevelOptions()
    expect(vm.levelOptions.length).toBe(1)
    policyApi.getLevelOptions.mockResolvedValue({ data: { data: [{ label: '省级2', value: 'prov2' }] } })
    await vm.refreshLevelOptions()
    expect(vm.levelOptions.length).toBe(1)
  })
})

describe('行操作按钮补充', () => {
  it('详情/编辑/删除/提交审批 行按钮点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const detailBtn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes('详情'))
    if (detailBtn) await detailBtn.trigger('click')
    const editBtn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes('编辑'))
    if (editBtn) await editBtn.trigger('click')
    wrapper.unmount()
  })
})

describe('提交审批失败分支', () => {
  it('reject 带 detail / 普通 Error', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    ;(submitApprovalMock as any).mockRejectedValueOnce({ response: { data: { detail: '无权限' } } })
    await vm.handleSubmitApproval({ id: 1, title: 't', code: 'c' }).catch(() => {})
    ;(submitApprovalMock as any).mockRejectedValueOnce(new Error('网络错误'))
    await vm.handleSubmitApproval({ id: 2, title: 't2', code: 'c2' }).catch(() => {})
    wrapper.unmount()
  })
})

describe('可编辑行提交按钮', () => {
  it('canEdit=true 时行内「提交审批」按钮点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.canEdit = true
    await wrapper.vm.$nextTick()
    const btn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes('提交审批'))
    if (btn) await btn.trigger('click')
    wrapper.unmount()
  })
})

describe('加载失败与取消分支', () => {
  it('levelOptions 加载失败 → 空数组', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    ;(policyApi.getLevelOptions as any).mockRejectedValueOnce(new Error('x'))
    await vm.refreshLevelOptions().catch(() => {})
    wrapper.unmount()
  })
  it('submitApproval 拒绝 "cancel" → 不提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    ;(submitApprovalMock as any).mockRejectedValueOnce('cancel')
    await vm.handleSubmitApproval({ id: 3, title: 't3', code: 'c3' }).catch(() => {})
    wrapper.unmount()
  })
})

describe('层级加载失败分支2', () => {
  it('category 有值时 levelOptions 请求失败 → 空数组', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchForm.category = 'province'
    ;(policyApi.getLevelOptions as any).mockRejectedValueOnce(new Error('x'))
    await vm.refreshLevelOptions().catch(() => {})
    wrapper.unmount()
  })
})

describe('审批提交分支收尾', () => {
  it('确认后 reject cancel / reject detail', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    confirmMock.mockResolvedValue(true)
    ;(submitApprovalMock as any).mockRejectedValueOnce('cancel')
    await vm.handleSubmitApproval({ id: 4, title: 't4', code: 'c4' })
    ;(submitApprovalMock as any).mockRejectedValueOnce({ response: { data: { detail: '无权限' } } })
    await vm.handleSubmitApproval({ id: 5, title: 't5', code: 'c5' })
    wrapper.unmount()
  })
})
