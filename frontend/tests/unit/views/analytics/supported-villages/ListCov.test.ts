/**
 * views/analytics/supported-villages/List.vue 覆盖率攻坚（筛选 / KPI / 分页 / 操作列 / 对话框）
 *
 * 与同目录 RecycleBin.test.ts 互补：后者聚焦软删恢复、彻底删除、批量删除与导入导出，
 * 且使用全局默认桩（el-card / el-row / el-col / el-table 均为 true 桩，不渲染插槽），
 * 因此筛选表单、KPI 卡片、表格作用域插槽内的模板产物都没有被执行过。
 * 本文件提供"渲染插槽 + 可主动 emit"的局部桩，覆盖：
 *   - handleSearch / handleReset / handleSortChange / handleSizeChange / handlePageChange
 *   - handleCreate / handleView / handleViewDetail / handleEdit / handleYearlyData / handleDelete
 *   - 所有 v-model 编译产物（el-input / el-select ×6 / el-switch / el-pagination / el-dialog ×2）
 *   - kpiStats 后端 summary 缺失时的回退口径
 *   - loadData 响应形态兜底与异常、loadFilterOptions 异常
 *   - 彻底删除 / 批量删除的 inputValidator、预览形态兜底、导出参数分支、导入错误明细
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const {
  ElMessage,
  confirmMock,
  promptMock,
  alertMock,
  pushSafe,
  authBox,
  clearSelectionSpy,
  logError,
  logInfo,
  listMock,
  deleteMock,
  batchDeleteMock,
  createMock,
  updateMock,
  fundingMock,
  importMock,
  exportMock,
  tplMock,
  filterOptionsMock,
  restoreMock,
  previewPurgeMock,
  purgeMock,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  promptMock: vi.fn(),
  alertMock: vi.fn(),
  pushSafe: vi.fn(),
  // 可变权限盒子：非管理员分支需在 mount 前翻转（computed 首次求值后会被缓存）
  authBox: { canViewDeleted: true },
  clearSelectionSpy: vi.fn(),
  logError: vi.fn(),
  logInfo: vi.fn(),
  listMock: vi.fn(),
  deleteMock: vi.fn(),
  batchDeleteMock: vi.fn(),
  createMock: vi.fn(),
  updateMock: vi.fn(),
  fundingMock: vi.fn(),
  importMock: vi.fn(),
  exportMock: vi.fn(),
  tplMock: vi.fn(),
  filterOptionsMock: vi.fn(),
  restoreMock: vi.fn(),
  previewPurgeMock: vi.fn(),
  purgeMock: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock, prompt: promptMock, alert: alertMock },
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: logInfo, debug: vi.fn(), log: vi.fn() },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authBox,
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe }),
}))

vi.mock('@/api/supportedVillage', () => ({
  getSupportedVillages: listMock,
  deleteSupportedVillage: deleteMock,
  batchDeleteSupportedVillages: batchDeleteMock,
  createSupportedVillage: createMock,
  updateSupportedVillage: updateMock,
  saveTransitionFunding: fundingMock,
  importSupportedVillages: importMock,
  exportSupportedVillages: exportMock,
  downloadImportTemplate: tplMock,
  getFilterOptions: filterOptionsMock,
  restoreSupportedVillage: restoreMock,
  previewPurgeSupportedVillage: previewPurgeMock,
  purgeSupportedVillage: purgeMock,
  // 子组件（SupportedVillageForm / YearlyDataForm）静态 import 的其余导出，
  // 本文件不渲染它们，但保留占位避免任何访问报错
  getTransitionFunding: vi.fn(),
  getYearlyData: vi.fn(),
  copyYearData: vi.fn(),
  savePopulationData: vi.fn(),
  saveIncomeData: vi.fn(),
  saveIndustryData: vi.fn(),
  saveInfrastructureData: vi.fn(),
  saveEducationData: vi.fn(),
  saveForceInvestmentData: vi.fn(),
  savePartyBuildingData: vi.fn(),
  saveMedicalData: vi.fn(),
  saveConsumptionData: vi.fn(),
  saveEmploymentData: vi.fn(),
}))

import SupportedVillageList from '@/views/analytics/supported-villages/List.vue'

// 两行样本：地域/振兴标签的 v-if 真假两侧各覆盖一次
const rowA = {
  id: 11,
  villageName: '甲村',
  department: 'D1',
  supportUnit: 'U1',
  regionScope: 'C1',
  county: 'C1',
  totalInvestment: 10,
  industryInvestment: 1,
  infrastructureInvestment: 2,
  educationInvestment: 3,
  isThreeRegions: true,
  isBorderArea: false,
  isEthnicArea: true,
  isRevolutionaryArea: false,
  isKeyCounty: true,
  isRevitalizationTier: true,
  isProvincialDemo: false,
  isHundredVillageDemo: true,
}
const rowB = {
  id: 12,
  villageName: '乙村',
  department: 'D2',
  supportUnit: 'U2',
  regionScope: 'C2',
  totalInvestment: 0,
  isThreeRegions: false,
  isBorderArea: true,
  isEthnicArea: false,
  isRevolutionaryArea: true,
  isKeyCounty: false,
  isRevitalizationTier: false,
  isProvincialDemo: true,
  isHundredVillageDemo: false,
}

const summary = { total: 2, total_investment: 16, county_count: 2, department_count: 2 }

/**
 * 全局默认桩（'el-xxx': true）既不渲染插槽、也不会 emit update:modelValue / change，
 * 因此模板里的 v-model 产物、@click 内联箭头、作用域插槽内的操作列全部不可达。
 * 下面这套局部桩显式渲染 <slot /> 并提供可点击按钮主动 emit。
 */
const stubs: Record<string, any> = {
  'el-card': { template: '<div class="el-card-stub"><slot /><slot name="header" /></div>' },
  'el-row': { template: '<div class="el-row-stub"><slot /></div>' },
  'el-col': { template: '<div class="el-col-stub"><slot /></div>' },
  // @submit.prevent 挂在 el-form 上：不声明 emits，让 onSubmit 透传到真实 <form> 根元素
  'el-form': { template: '<form class="el-form-stub"><slot /></form>' },
  'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
  'el-input': {
    props: ['modelValue', 'placeholder'],
    emits: ['update:modelValue'],
    template:
      '<input class="el-input-stub" :value="modelValue" ' +
      '@input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  'el-select': {
    props: ['modelValue', 'placeholder'],
    emits: ['update:modelValue', 'change'],
    template:
      '<div class="el-select-stub" :data-ph="placeholder">' +
      '<button type="button" class="sel-emit" @click="$emit(\'update:modelValue\', \'SEL\')">s</button>' +
      '<slot /></div>',
  },
  'el-option': { props: ['label', 'value'], template: '<div class="el-option-stub" />' },
  'el-switch': {
    props: ['modelValue'],
    emits: ['update:modelValue', 'change'],
    template:
      '<div class="el-switch-stub">' +
      '<button type="button" class="sw-model" @click="$emit(\'update:modelValue\', true)">m</button>' +
      '<button type="button" class="sw-change" @click="$emit(\'change\', true)">c</button>' +
      '</div>',
  },
  'el-button': {
    props: ['type', 'loading', 'disabled'],
    emits: ['click'],
    template: '<button type="button" class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
  },
  'el-icon': { template: '<i class="el-icon-stub"><slot /></i>' },
  'el-tooltip': { template: '<div class="el-tooltip-stub"><slot /></div>' },
  'el-tag': { props: ['type', 'size'], template: '<span class="el-tag-stub"><slot /></span>' },
  'el-link': {
    props: ['type'],
    emits: ['click'],
    template: '<a class="el-link-stub" @click="$emit(\'click\')"><slot /></a>',
  },
  'el-popconfirm': {
    props: ['title'],
    emits: ['confirm'],
    template:
      '<div class="el-popconfirm-stub" :data-title="title">' +
      '<button type="button" class="pc-confirm" @click="$emit(\'confirm\')">ok</button>' +
      '<slot /><slot name="reference" /></div>',
  },
  'el-table': {
    emits: ['sort-change', 'selection-change'],
    // tableRef.value.clearSelection() 在批量删除成功后被调用（branch@705 真侧）
    methods: { clearSelection: () => clearSelectionSpy() },
    template:
      '<div class="el-table-stub">' +
      '<button type="button" class="tb-sort-asc" @click="$emit(\'sort-change\', { prop: \'department\', order: \'ascending\' })">a</button>' +
      '<button type="button" class="tb-sort-desc" @click="$emit(\'sort-change\', { prop: \'department\', order: \'descending\' })">d</button>' +
      '<button type="button" class="tb-sort-none" @click="$emit(\'sort-change\', { prop: null, order: null })">n</button>' +
      '<button type="button" class="tb-sel" @click="$emit(\'selection-change\', [rowA, rowB])">s</button>' +
      '<slot /></div>',
    data() {
      return { rowA, rowB }
    },
  },
  'el-table-column': {
    props: ['prop', 'label', 'type'],
    template:
      '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
    data() {
      return { rowA, rowB }
    },
  },
  'el-pagination': {
    props: ['currentPage', 'pageSize', 'total'],
    emits: ['update:currentPage', 'update:pageSize', 'size-change', 'current-change'],
    template:
      '<div class="el-pagination-stub" :data-total="total">' +
      '<button type="button" class="pg-model-cur" @click="$emit(\'update:currentPage\', 3)">mc</button>' +
      '<button type="button" class="pg-model-size" @click="$emit(\'update:pageSize\', 50)">ms</button>' +
      '<button type="button" class="pg-cur-change" @click="$emit(\'current-change\', 4)">cc</button>' +
      '<button type="button" class="pg-size-change" @click="$emit(\'size-change\', 100)">sc</button>' +
      '</div>',
  },
  'el-dialog': {
    props: ['modelValue', 'title'],
    emits: ['update:modelValue'],
    template:
      '<div class="el-dialog-stub" :data-title="title">' +
      '<button type="button" class="dlg-close" @click="$emit(\'update:modelValue\', false)">x</button>' +
      '<slot /></div>',
  },
  // 子表单用轻量桩替代：既能 emit submit/cancel/close 覆盖父级内联产物，
  // 又避免真的挂载 650/894 行的重组件
  SupportedVillageForm: {
    props: ['village', 'mode'],
    emits: ['submit', 'cancel'],
    template:
      '<div class="sv-form-stub" :data-mode="mode">' +
      '<button type="button" class="sv-submit" @click="$emit(\'submit\', payload)">s</button>' +
      '<button type="button" class="sv-cancel" @click="$emit(\'cancel\')">c</button>' +
      '</div>',
    data() {
      return { payload: { villageName: '新村庄', _transitionFundingItems: [{ year: 2026 }] } }
    },
  },
  YearlyDataForm: {
    props: ['villageId', 'villageName'],
    emits: ['close'],
    template:
      '<div class="yd-form-stub" :data-vid="villageId">' +
      '<button type="button" class="yd-close" @click="$emit(\'close\')">x</button>' +
      '</div>',
  },
}

function mountList(extraStubs: Record<string, any> = {}) {
  return mount(SupportedVillageList, {
    global: { stubs: { ...stubs, ...extraStubs } },
  })
}

/** 按文本定位操作栏/操作列按钮 */
function btns(wrapper: any, text: string) {
  return wrapper.findAll('.el-button-stub').filter((b: any) => b.text().replace(/\s/g, '').includes(text))
}

/** 按 title 定位 el-popconfirm 的确认按钮 */
function popconfirm(wrapper: any, title: string) {
  const box = wrapper
    .findAll('.el-popconfirm-stub')
    .find((n: any) => n.attributes('data-title') === title)
  expect(box, `popconfirm「${title}」`).toBeTruthy()
  return box.find('.pc-confirm')
}

/** 按 title 定位对话框 */
function dialog(wrapper: any, title: string) {
  const d = wrapper.findAll('.el-dialog-stub').find((n: any) => n.attributes('data-title') === title)
  expect(d, `对话框「${title}」`).toBeTruthy()
  return d
}

beforeEach(() => {
  vi.clearAllMocks()
  authBox.canViewDeleted = true
  filterOptionsMock.mockResolvedValue({
    departments: ['D1', 'D2'],
    supportUnits: ['U1'],
    counties: ['C1', 'C2'],
    regionScopes: [],
    tieredLevels: [],
    years: [2025, 2026],
  })
  listMock.mockResolvedValue({ data: { items: [rowA, rowB], total: 2, summary } })
  createMock.mockResolvedValue({ data: { id: 99 } })
  updateMock.mockResolvedValue({})
  fundingMock.mockResolvedValue({})
  deleteMock.mockResolvedValue({})
  batchDeleteMock.mockResolvedValue({ message: '已删除 2 条记录' })
  exportMock.mockResolvedValue(undefined)
  tplMock.mockResolvedValue(undefined)
  importMock.mockResolvedValue({ imported: 1, failed: 0 })
  confirmMock.mockResolvedValue('confirm')
  promptMock.mockResolvedValue({ value: 'pw' })
  alertMock.mockResolvedValue(undefined)
})

describe('筛选表单与操作栏模板产物', () => {
  it('渲染筛选区/KPI/操作列（默认桩不渲染插槽，本用例用可渲染桩）', async () => {
    const wrapper = mountList()
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('帮扶村总数')
    expect(text).toContain('甲村')
    expect(text).toContain('乙村')
    // 地域属性/振兴属性标签的 v-if 真假两侧
    expect(text).toContain('三区三州')
    expect(text).toContain('边疆地区')
    expect(text).toContain('民族地区')
    expect(text).toContain('革命地区')
    expect(text).toContain('重点帮扶县')
    expect(text).toContain('振兴梯队')
    expect(text).toContain('省级示范')
    expect(text).toContain('百村示范')
    // 非回收站模式：操作列为 查看/编辑/年度数据/删除
    expect(text).toContain('年度数据')
    expect(text).not.toContain('彻底删除')
    wrapper.unmount()
  })

  it('el-form @submit.prevent 与 搜索/重置 按钮', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.pagination.page = 5

    // @submit.prevent 的内联空处理器产物
    await wrapper.find('.el-form-stub').trigger('submit')

    vm.filters.keyword = '甲'
    listMock.mockClear()
    await btns(wrapper, '搜索')[0].trigger('click')
    await flushPromises()
    expect(vm.pagination.page).toBe(1)
    expect(listMock.mock.calls.at(-1)?.[0]).toMatchObject({ page: 1, keyword: '甲' })

    // 重置：清空全部筛选条件并重新加载
    vm.filters.department = 'D1'
    vm.filters.county = 'C1'
    vm.filters.isRevitalizationTier = true
    vm.filters.isThreeRegions = 1
    vm.filters.isEthnicArea = 1
    vm.filters.isKeyCounty = 1
    // 任务#28 缺陷2修复：yearStart 此前被 handleReset 漏掉（模板 v-model="filters.yearStart"、
    // loadData 的 year_start 都在用它），导致点「重置」后年份筛选仍然生效。
    // 显式赋一个真值，下面两条断言在旧实现下会失败。
    vm.filters.yearStart = 2024
    vm.pagination.page = 7
    listMock.mockClear()
    await btns(wrapper, '重置')[0].trigger('click')
    await flushPromises()
    expect(vm.filters).toEqual({
      keyword: '',
      department: undefined,
      county: undefined,
      isRevitalizationTier: undefined,
      isThreeRegions: undefined,
      isEthnicArea: undefined,
      isKeyCounty: undefined,
      yearStart: undefined,
    })
    // toEqual 忽略值为 undefined 的属性，故再显式断言：yearStart 确已被清空，
    // 且重置后的请求不再携带 year_start（旧实现下这两条均为 2024）
    expect(vm.filters.yearStart).toBeUndefined()
    expect(listMock.mock.calls.at(-1)?.[0].year_start).toBeUndefined()
    expect(vm.pagination.page).toBe(1)
    wrapper.unmount()
  })

  it('el-input v-model 写回 filters.keyword；keyup.enter 触发搜索', async () => {
    const wrapper = mountList()
    await flushPromises()
    const input = wrapper.find('.el-input-stub')
    await input.setValue('乙村')
    expect((wrapper.vm as any).filters.keyword).toBe('乙村')

    listMock.mockClear()
    await input.trigger('keyup.enter')
    await flushPromises()
    expect(listMock.mock.calls.at(-1)?.[0]).toMatchObject({ page: 1, keyword: '乙村' })
    wrapper.unmount()
  })

  it('6 个 el-select 的 v-model 产物分别写回对应筛选项', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    const sels = wrapper.findAll('.el-select-stub')
    expect(sels.length).toBe(6)
    for (const s of sels) {
      await s.find('.sel-emit').trigger('click')
    }
    await nextTick()
    expect(vm.filters.department).toBe('SEL')
    expect(vm.filters.county).toBe('SEL')
    expect(vm.filters.isThreeRegions).toBe('SEL')
    expect(vm.filters.isEthnicArea).toBe('SEL')
    expect(vm.filters.isKeyCounty).toBe('SEL')
    expect(vm.filters.yearStart).toBe('SEL')

    // 筛选值参与 loadData 查询参数
    listMock.mockClear()
    vm.handleSearch()
    await flushPromises()
    expect(listMock.mock.calls.at(-1)?.[0]).toMatchObject({
      department: 'SEL',
      county: 'SEL',
      year_start: 'SEL',
      is_three_regions: 'SEL',
      is_ethnic_area: 'SEL',
      is_key_county: 'SEL',
    })
    wrapper.unmount()
  })

  it('el-switch（振兴梯队）v-model 写回；is_revitalization_tier 参与查询', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    // 管理员可见回收站开关 → 页面共 2 个 el-switch，索引 0 为筛选项
    const switches = wrapper.findAll('.el-switch-stub')
    expect(switches.length).toBe(2)
    await switches[0].find('.sw-model').trigger('click')
    await nextTick()
    expect(vm.filters.isRevitalizationTier).toBe(true)

    listMock.mockClear()
    vm.handleSearch()
    await flushPromises()
    expect(listMock.mock.calls.at(-1)?.[0]).toMatchObject({ is_revitalization_tier: true })
    wrapper.unmount()
  })

  it('操作栏：新增 / 导入 / 导出 / 下载模板 四个按钮', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any

    await btns(wrapper, '新增帮扶村')[0].trigger('click')
    await nextTick()
    expect(vm.dialogVisible).toBe(true)
    expect(vm.dialogMode).toBe('create')
    expect(vm.currentVillage).toBeNull()
    expect(logInfo).toHaveBeenCalled()
    vm.dialogVisible = false

    await btns(wrapper, '导出数据')[0].trigger('click')
    await flushPromises()
    expect(exportMock).toHaveBeenCalledTimes(1)
    expect(vm.exporting).toBe(false)

    await btns(wrapper, '下载模板')[0].trigger('click')
    await flushPromises()
    expect(tplMock).toHaveBeenCalledTimes(1)

    // 注意：spy 必须在 mount 之后再装。el-input 局部桩渲染真实 <input>，
    // Vue 的 runtime-dom 会走 document.createElement，先装 spy 会把筛选框当成文件输入框。
    const inputs: HTMLInputElement[] = []
    const orig = document.createElement.bind(document)
    const spy = vi.spyOn(document, 'createElement').mockImplementation((tag: any) => {
      const el = orig(tag)
      if (String(tag).toLowerCase() === 'input') inputs.push(el as HTMLInputElement)
      return el
    })
    await btns(wrapper, '导入数据')[0].trigger('click')
    expect(inputs.length).toBe(1)
    expect(inputs[0].accept).toBe('.xlsx,.xls')
    expect(inputs[0].type).toBe('file')

    spy.mockRestore()
    wrapper.unmount()
  })

  it('回收站开关：管理员 change → 重新加载；非管理员 → 警告并复位', async () => {
    const wrapper = mountList()
    await flushPromises()
    const switches = wrapper.findAll('.el-switch-stub')
    listMock.mockClear()
    await switches[1].find('.sw-change').trigger('click')
    await flushPromises()
    expect(listMock.mock.calls.at(-1)?.[0]).toMatchObject({ include_deleted: undefined, page: 1 })

    // 打开回收站后 include_deleted=true
    const vm = wrapper.vm as any
    await switches[1].find('.sw-model').trigger('click')
    await nextTick()
    expect(vm.showDeletedOnly).toBe(true)
    listMock.mockClear()
    vm.handleToggleDeleted(true)
    await flushPromises()
    expect(listMock.mock.calls.at(-1)?.[0]).toMatchObject({ include_deleted: true })
    // 回收站模式下操作列切换为 恢复/彻底删除
    await nextTick()
    expect(wrapper.text()).toContain('彻底删除')
    wrapper.unmount()

    // 非管理员：开关被隐藏（v-if=canViewDeleted 假侧），直接调用 handleToggleDeleted 走警告分支
    authBox.canViewDeleted = false
    const w2 = mountList()
    await flushPromises()
    expect(w2.findAll('.el-switch-stub').length).toBe(1) // 仅剩筛选梯队开关
    const vm2 = w2.vm as any
    vm2.handleToggleDeleted(true)
    await flushPromises()
    expect(ElMessage.warning).toHaveBeenCalledWith('仅管理员可查看已删除记录')
    expect(vm2.showDeletedOnly).toBe(false)
    authBox.canViewDeleted = true
    w2.unmount()
  })
})

describe('表格事件与操作列', () => {
  it('sort-change：ascending / descending / 空 → sort_order 三态', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any

    await wrapper.find('.tb-sort-asc').trigger('click')
    await flushPromises()
    expect(vm.sortParams).toEqual({ prop: 'department', order: 'ascending' })
    expect(listMock.mock.calls.at(-1)?.[0]).toMatchObject({ sort_by: 'department', sort_order: 'asc' })

    await wrapper.find('.tb-sort-desc').trigger('click')
    await flushPromises()
    expect(listMock.mock.calls.at(-1)?.[0]).toMatchObject({ sort_order: 'desc' })

    await wrapper.find('.tb-sort-none').trigger('click')
    await flushPromises()
    expect(vm.sortParams).toEqual({ prop: '', order: '' })
    expect(listMock.mock.calls.at(-1)?.[0]).toMatchObject({ sort_by: undefined, sort_order: undefined })
    wrapper.unmount()
  })

  it('selection-change → 批量删除区可见，popconfirm 触发批量删除', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(wrapper.find('.action-bar-right').exists()).toBe(false)

    await wrapper.find('.tb-sel').trigger('click')
    await nextTick()
    expect(vm.selectedRows).toHaveLength(2)
    expect(wrapper.text()).toContain('已选择 2 条')

    batchDeleteMock.mockClear()
    listMock.mockClear()
    await popconfirm(wrapper, '确定批量删除这 2 条记录吗？').trigger('click')
    await flushPromises()
    await flushPromises()
    expect(batchDeleteMock).toHaveBeenCalledWith([11, 12], 'pw')
    expect(ElMessage.success).toHaveBeenCalledWith('已删除 2 条记录')
    expect(clearSelectionSpy).toHaveBeenCalledTimes(1)
    expect(vm.selectedRows).toHaveLength(0)
    expect(vm.batchDeleting).toBe(false)
    wrapper.unmount()
  })

  it('el-link 村名 → handleViewDetail 跳转详情页', async () => {
    const wrapper = mountList()
    await flushPromises()
    const links = wrapper.findAll('.el-link-stub')
    expect(links.length).toBe(2)
    await links[0].trigger('click')
    expect(pushSafe).toHaveBeenCalledWith('/supported-villages/11')
    await links[1].trigger('click')
    expect(pushSafe).toHaveBeenCalledWith('/supported-villages/12')
    wrapper.unmount()
  })

  it('操作列：查看 / 编辑 / 年度数据 三个内联产物', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any

    await btns(wrapper, '查看')[0].trigger('click')
    await nextTick()
    expect(vm.dialogMode).toBe('view')
    expect(vm.currentVillage.id).toBe(11)
    expect(vm.dialogVisible).toBe(true)
    vm.dialogVisible = false

    await btns(wrapper, '编辑')[1].trigger('click')
    await nextTick()
    expect(vm.dialogMode).toBe('edit')
    expect(vm.currentVillage.id).toBe(12)
    expect(vm.dialogVisible).toBe(true)
    vm.dialogVisible = false

    await btns(wrapper, '年度数据')[0].trigger('click')
    expect(pushSafe).toHaveBeenCalledWith('/supported-villages/11/yearly')
    wrapper.unmount()
  })

  it('操作列删除 popconfirm → 乐观移除并刷新；失败 → 错误提示', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.pagination.total = 2
    listMock.mockClear()

    await popconfirm(wrapper, '确定删除该帮扶村记录吗？').trigger('click')
    await flushPromises()
    expect(deleteMock).toHaveBeenCalledWith(11)
    // 乐观更新后立即被 loadData 覆盖回 2 行
    expect(listMock.mock.calls.length).toBeGreaterThan(0)
    expect(vm.pagination.page).toBe(1)

    // 失败分支：挂起刷新以观察乐观移除后的中间态
    deleteMock.mockRejectedValueOnce(new Error('down'))
    await popconfirm(wrapper, '确定删除该帮扶村记录吗？').trigger('click')
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
    wrapper.unmount()
  })

  it('回收站模式操作列：恢复 / 彻底删除 内联产物', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.showDeletedOnly = true
    await nextTick()

    restoreMock.mockResolvedValue({})
    await btns(wrapper, '恢复')[0].trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalled()
    expect(restoreMock).toHaveBeenCalledWith(11)

    previewPurgeMock.mockResolvedValue({ data: { total_references: 0, details: {} } })
    purgeMock.mockResolvedValue({ data: { deleted_records: 0 } })
    await btns(wrapper, '彻底删除')[0].trigger('click')
    await flushPromises()
    expect(purgeMock).toHaveBeenCalledWith(11, 'pw')
    wrapper.unmount()
  })
})

describe('分页 v-model 与事件', () => {
  it('current-page / page-size 的 v-model 产物 + current-change / size-change 处理器', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any

    await wrapper.find('.pg-model-cur').trigger('click')
    await nextTick()
    expect(vm.pagination.page).toBe(3)

    await wrapper.find('.pg-model-size').trigger('click')
    await nextTick()
    expect(vm.pagination.pageSize).toBe(50)

    listMock.mockClear()
    await wrapper.find('.pg-cur-change').trigger('click')
    await flushPromises()
    expect(vm.pagination.page).toBe(4)
    expect(listMock.mock.calls.at(-1)?.[0]).toMatchObject({ page: 4 })

    listMock.mockClear()
    await wrapper.find('.pg-size-change').trigger('click')
    await flushPromises()
    expect(vm.pagination.pageSize).toBe(100)
    expect(vm.pagination.page).toBe(1)
    expect(listMock.mock.calls.at(-1)?.[0]).toMatchObject({ page: 1, page_size: 100 })

    // :total 直接绑定 pagination.total。任务#28 死代码4：原 `(pagination as any)?.data?.total ||
    // (pagination as any)?.total` 的左侧永为 undefined、`?.` 的 nullish 侧亦不可达，已删除；
    // 下面断言 pagination 恒只有 page/pageSize/total 三键，作为该不可达结论的回归守卫。
    expect(wrapper.find('.el-pagination-stub').attributes('data-total')).toBe('2')
    expect(Object.keys(vm.pagination).sort()).toEqual(['page', 'pageSize', 'total'])
    wrapper.unmount()
  })
})

describe('对话框 v-model 与子表单事件', () => {
  it('新增对话框：v-model 关闭 + SupportedVillageForm @cancel', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleCreate()
    await nextTick()
    const dlg = dialog(wrapper, '新增帮扶村')
    expect(dlg.find('.sv-form-stub').attributes('data-mode')).toBe('create')

    await dlg.find('.sv-cancel').trigger('click')
    await nextTick()
    expect(vm.dialogVisible).toBe(false)

    // v-model 产物：对话框自身 emit update:modelValue(false)
    vm.dialogVisible = true
    await nextTick()
    await dialog(wrapper, '新增帮扶村').find('.dlg-close').trigger('click')
    await nextTick()
    expect(vm.dialogVisible).toBe(false)
    wrapper.unmount()
  })

  it('编辑对话框标题随 dialogMode 变化；提交走更新接口', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleEdit(rowB as any)
    await nextTick()
    const dlg = dialog(wrapper, '编辑帮扶村')
    expect(dlg.find('.sv-form-stub').attributes('data-mode')).toBe('edit')

    updateMock.mockClear()
    listMock.mockClear()
    await dlg.find('.sv-submit').trigger('click')
    await flushPromises()
    await flushPromises()
    // 任务#28 缺陷3修复：私有过渡字段 _transitionFundingItems 现在入口处统一摘除，
    // edit 分支不再把内部状态透传给 updateSupportedVillage（与 Detail.vue 写法一致）。
    expect(updateMock).toHaveBeenCalledWith(12, { villageName: '新村庄' })
    expect(updateMock.mock.calls[0][1]._transitionFundingItems).toBeUndefined()
    expect(vm.dialogVisible).toBe(false)
    expect(vm.pagination.page).toBe(1)
    wrapper.unmount()
  })

  it('创建提交：含过渡资金 → createSupportedVillage + saveTransitionFunding', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleCreate()
    await nextTick()
    createMock.mockClear()
    fundingMock.mockClear()
    await dialog(wrapper, '新增帮扶村').find('.sv-submit').trigger('click')
    await flushPromises()
    await flushPromises()
    expect(createMock).toHaveBeenCalledWith({ villageName: '新村庄' })
    expect(fundingMock).toHaveBeenCalledWith(99, { items: [{ year: 2026 }] })
    expect(vm.dialogVisible).toBe(false)
    wrapper.unmount()
  })

  it('创建提交：过渡资金保存失败仅记日志，创建仍成功', async () => {
    fundingMock.mockRejectedValueOnce(new Error('tf down'))
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleCreate()
    await nextTick()
    await dialog(wrapper, '新增帮扶村').find('.sv-submit').trigger('click')
    await flushPromises()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(vm.dialogVisible).toBe(false)
    expect(ElMessage.error).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('创建提交：接口失败 → 「创建失败」；查看模式提交不落库', async () => {
    createMock.mockRejectedValueOnce(new Error('dup'))
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleCreate()
    await nextTick()
    await dialog(wrapper, '新增帮扶村').find('.sv-submit').trigger('click')
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('创建失败')
    expect(logError).toHaveBeenCalled()

    // view 模式：既非 create 也非 edit → 直接关闭刷新
    vm.dialogMode = 'view'
    vm.dialogVisible = true
    await nextTick()
    createMock.mockClear()
    updateMock.mockClear()
    await dialog(wrapper, '查看帮扶村').find('.sv-submit').trigger('click')
    await flushPromises()
    expect(createMock).not.toHaveBeenCalled()
    expect(updateMock).not.toHaveBeenCalled()
    expect(vm.dialogVisible).toBe(false)
    wrapper.unmount()
  })

  it('年度数据对话框：v-model 关闭 + YearlyDataForm @close', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentVillage = rowA as any
    vm.yearlyDialogVisible = true
    await nextTick()
    const dlg = dialog(wrapper, '年度数据管理')
    expect(dlg.find('.yd-form-stub').attributes('data-vid')).toBe('11')

    await dlg.find('.yd-close').trigger('click')
    await nextTick()
    expect(vm.yearlyDialogVisible).toBe(false)

    vm.yearlyDialogVisible = true
    await nextTick()
    await dialog(wrapper, '年度数据管理').find('.dlg-close').trigger('click')
    await nextTick()
    expect(vm.yearlyDialogVisible).toBe(false)

    // currentVillage 为空 → v-if="yearlyDialogVisible && currentVillage" 假侧
    vm.currentVillage = null
    vm.yearlyDialogVisible = true
    await nextTick()
    expect(dialog(wrapper, '年度数据管理').find('.yd-form-stub').exists()).toBe(false)
    wrapper.unmount()
  })
})

describe('kpiStats 与 loadData 响应形态', () => {
  it('后端 summary 存在 → 使用全量聚合口径', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.kpiStats.totalVillages).toBe(2)
    expect(vm.kpiStats.countyCount).toBe(2)
    expect(vm.kpiStats.departmentCount).toBe(2)
    const kpis = wrapper.findAll('.kpi-value').map((n: any) => n.text())
    expect(kpis[0]).toBe('2')
    wrapper.unmount()
  })

  it('summary 各字段缺省 → ?? / || 兜底为 0', async () => {
    listMock.mockResolvedValue({ data: { items: [rowA], total: 1, summary: {} } })
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.kpiStats).toEqual({
      totalVillages: 0,
      totalInvestment: vm.kpiStats.totalInvestment,
      countyCount: 0,
      departmentCount: 0,
    })
    wrapper.unmount()
  })

  it('裸分页（items/total 无信封）且无 summary → 回退口径基于当前页现算', async () => {
    listMock.mockResolvedValue({ items: [rowA, rowB], total: 5 })
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.tableData).toHaveLength(2)
    expect(vm.pagination.total).toBe(5)
    expect(vm.serverSummary).toBeNull()
    // totalInvestment = (10+1+2+3) + 0 = 16
    expect(vm.kpiStats.totalVillages).toBe(5)
    expect(vm.kpiStats.countyCount).toBe(2) // C1 / C2（rowB 走 regionScope 兜底）
    expect(vm.kpiStats.departmentCount).toBe(2)
    wrapper.unmount()
  })

  it('空响应 → tableData 为空，total 回退 data.length，计数回退 filterOptions', async () => {
    listMock.mockResolvedValue({})
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.tableData).toEqual([])
    expect(vm.pagination.total).toBe(0)
    // pagination.total 为 0 → totalVillages 回退 data.length = 0
    expect(vm.kpiStats.totalVillages).toBe(0)
    // 无行数据 → counties.size / departments.size 为 0 → 回退 filterOptions 长度
    expect(vm.kpiStats.countyCount).toBe(2)
    expect(vm.kpiStats.departmentCount).toBe(2)
    wrapper.unmount()
  })

  // 纯防御分支：tableData 声明为 ref<SupportedVillage[]>([])，UI 路径下恒为数组；
  // 此处直接置 null 以覆盖 `const data = tableData.value || []` 的右侧兜底。
  it('tableData 为 null（纯防御）→ data 回退空数组，kpiStats 不抛错', async () => {
    listMock.mockResolvedValue({})
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.serverSummary).toBeNull()
    vm.tableData = null
    expect(vm.kpiStats.totalVillages).toBe(0)
    expect(vm.kpiStats.countyCount).toBe(2)
    expect(vm.kpiStats.departmentCount).toBe(2)
    wrapper.unmount()
  })

  it('loadData 异常 → 清空表格 + 错误提示 + loading 复位', async () => {
    listMock.mockRejectedValue(new Error('net'))
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.tableData).toEqual([])
    expect(vm.pagination.total).toBe(0)
    expect(ElMessage.error).toHaveBeenCalledWith('加载数据失败')
    expect(vm.loading).toBe(false)
    wrapper.unmount()
  })

  it('loadFilterOptions 异常 → 记日志且不阻塞页面', async () => {
    filterOptionsMock.mockRejectedValue(new Error('opts down'))
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(logError).toHaveBeenCalled()
    expect(vm.filterOptions.departments).toEqual([])
    expect(vm.tableData).toHaveLength(2) // 列表仍正常加载
    wrapper.unmount()
  })
})

describe('彻底删除 / 批量删除的密码校验器与预览形态', () => {
  it('purge：inputValidator 两态 + 预览裸返回（无 data 信封）', async () => {
    previewPurgeMock.mockResolvedValue({ total_references: 5, details: { projects: 3, funds: 2, x: 1 } })
    promptMock.mockImplementation((_m: any, _t: any, opts: any) => {
      expect(opts.inputValidator('')).toBe('密码不能为空')
      expect(opts.inputValidator('abc')).toBe(true)
      expect(opts.inputType).toBe('password')
      return Promise.resolve({ value: 'pw' })
    })
    purgeMock.mockResolvedValue({ data: { deleted_records: 7 } })
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handlePurge({ id: 11, villageName: '甲村' })
    await flushPromises()
    expect(confirmMock.mock.calls[0][0]).toContain('5 条数据')
    expect(confirmMock.mock.calls[0][0]).toContain('projects 3条')
    expect(purgeMock).toHaveBeenCalledWith(11, 'pw')
    expect(ElMessage.success).toHaveBeenCalledWith('已彻底删除及清理 7 条关联数据')
    wrapper.unmount()
  })

  it('purge：预览为 null / details 缺省 → totalRefs=0 且无级联提示；密码为空串', async () => {
    previewPurgeMock.mockResolvedValue(null)
    promptMock.mockResolvedValue({ value: undefined })
    purgeMock.mockResolvedValue(null)
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handlePurge({ id: 12, villageName: '乙村' })
    await flushPromises()
    expect(confirmMock.mock.calls[0][0]).toContain('关联的 0 条数据')
    expect(confirmMock.mock.calls[0][0]).not.toContain('（含')
    expect(purgeMock).toHaveBeenCalledWith(12, '')
    // result 为 null → deleted_records ?? 0
    expect(ElMessage.success).toHaveBeenCalledWith('已彻底删除及清理 0 条关联数据')
    wrapper.unmount()
  })

  it('批量删除：未选中直接返回；密码为空串兜底', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleBatchDelete()
    expect(promptMock).not.toHaveBeenCalled()
    expect(batchDeleteMock).not.toHaveBeenCalled()

    promptMock.mockImplementation((_m: any, _t: any, opts: any) => {
      expect(opts.inputValidator('')).toBe('密码不能为空')
      expect(opts.inputValidator('x')).toBe(true)
      return Promise.resolve({ value: undefined })
    })
    vm.handleSelectionChange([rowA] as any)
    await vm.handleBatchDelete()
    await flushPromises()
    expect(batchDeleteMock).toHaveBeenCalledWith([11], '')
    wrapper.unmount()
  })

  it('批量删除：tableRef 为空时跳过 clearSelection（branch 假侧）', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleSelectionChange([rowA] as any)
    vm.tableRef = null
    clearSelectionSpy.mockClear()
    await vm.handleBatchDelete()
    await flushPromises()
    expect(clearSelectionSpy).not.toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalled()
    wrapper.unmount()
  })
})

describe('导出参数分支', () => {
  it('无勾选 → 携带当前年份；有勾选 → 携带 village_ids 且清空选择', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.handleExport()
    await flushPromises()
    expect(exportMock.mock.calls[0][0]).toMatchObject({ year: new Date().getFullYear() })
    expect(exportMock.mock.calls[0][0]).not.toHaveProperty('village_ids')

    vm.handleSelectionChange([rowA, rowB] as any)
    await vm.handleExport()
    await flushPromises()
    expect(exportMock.mock.calls[1][0]).toMatchObject({ village_ids: [11, 12], year: undefined })
    expect(vm.selectedRows).toHaveLength(0)
    wrapper.unmount()
  })

  it('isRevitalizationTier 为 null/undefined → 不传；为 false → 原样传 false', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.filters.keyword = 'kw'
    vm.filters.department = 'D1'
    vm.filters.county = 'C1'

    vm.handleExport()
    await flushPromises()
    expect(exportMock.mock.calls[0][0]).toMatchObject({
      keyword: 'kw',
      department: 'D1',
      county: 'C1',
      is_revitalization_tier: undefined,
    })

    vm.filters.isRevitalizationTier = false
    await vm.handleExport()
    expect(exportMock.mock.calls[1][0]).toMatchObject({ is_revitalization_tier: false })
    wrapper.unmount()
  })

  it('导出失败 → 日志 + 提示 + exporting 复位', async () => {
    exportMock.mockRejectedValueOnce(new Error('offline'))
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleExport()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('导出功能需要后端支持，请先启动后端服务')
    expect(vm.exporting).toBe(false)
    wrapper.unmount()
  })
})

describe('导入错误明细', () => {
  function withFileInputs(cb: (inputs: HTMLInputElement[]) => void) {
    const inputs: HTMLInputElement[] = []
    const orig = document.createElement.bind(document)
    const spy = vi.spyOn(document, 'createElement').mockImplementation((tag: any) => {
      const el = orig(tag)
      if (String(tag).toLowerCase() === 'input') inputs.push(el as HTMLInputElement)
      return el
    })
    cb(inputs)
    spy.mockRestore()
  }

  it('未选择文件（files 为空）→ 直接返回，不调用导入接口', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    withFileInputs((inputs) => {
      vm.handleImport()
      ;(inputs[0] as any).onchange({ target: { files: [] } })
    })
    await flushPromises()
    expect(importMock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('错误明细：row/error 缺省走 row_index/message 兜底，未知形态走 JSON.stringify', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    importMock.mockResolvedValueOnce({
      imported: 0,
      failed: 3,
      errors: [{ row: 2, error: 'bad' }, { row_index: 3, message: 'worse' }, { odd: true }],
    })
    withFileInputs((inputs) => {
      vm.handleImport()
      ;(inputs[0] as any).onchange({ target: { files: [new File(['x'], 'a.xlsx')] } })
    })
    await flushPromises()
    expect(alertMock).toHaveBeenCalledTimes(1)
    const detail = alertMock.mock.calls[0][0] as string
    expect(detail).toContain('1. 第 2 行：bad')
    expect(detail).toContain('2. 第 3 行：worse')
    expect(detail).toContain('3. 第 3 行：{"odd":true}')
    // 3 条 ≤ 10 → 无"共 N 条失败"尾注
    expect(alertMock.mock.calls[0][0]).not.toContain('共 3 条失败')
    expect(ElMessage.warning).toHaveBeenCalledWith('有3条数据导入失败，请检查数据格式')
    wrapper.unmount()
  })

  it('错误超过 10 条 → 截断并追加总数尾注', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    const errors = Array.from({ length: 12 }, (_x, i) => ({ row: i + 1, error: `e${i}` }))
    importMock.mockResolvedValueOnce({ imported: 0, failed: 12, errors })
    withFileInputs((inputs) => {
      vm.handleImport()
      ;(inputs[0] as any).onchange({ target: { files: [new File(['x'], 'b.xlsx')] } })
    })
    await flushPromises()
    const detail = alertMock.mock.calls[0][0] as string
    expect(detail).toContain('… 共 12 条失败')
    expect(detail).toContain('10. 第 10 行：e9')
    expect(detail).not.toContain('11. 第 11 行')
    wrapper.unmount()
  })

  it('导入接口失败 → 日志 + 提示', async () => {
    const wrapper = mountList()
    await flushPromises()
    const vm = wrapper.vm as any
    importMock.mockRejectedValueOnce(new Error('down'))
    withFileInputs((inputs) => {
      vm.handleImport()
      ;(inputs[0] as any).onchange({ target: { files: [new File(['x'], 'c.xlsx')] } })
    })
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('导入功能需要后端支持，请先启动后端服务')
    wrapper.unmount()
  })
})

