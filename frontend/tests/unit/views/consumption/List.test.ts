/**
 * views/consumption/List.vue 专属测试（契约 W22 §2/§3/§5，四指标 100%）
 *
 * 单执行者规程：本文件是全仓唯一真实执行 consumption/List.vue 的测试。
 * 覆盖：统计卡（含 amount/total_amount 双字段与村 id 双字段兜底）、筛选/年度联动/分页、
 * 表格模板列、新建/编辑校验与载荷、软删确认三态、xlsx/csv 导出。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const CURRENT_YEAR = new Date().getFullYear()

const mocks = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirm: vi.fn(),
  getConsumptionRecords: vi.fn(),
  getConsumptionStatistics: vi.fn(),
  createConsumptionRecord: vi.fn(),
  updateConsumptionRecord: vi.fn(),
  deleteConsumptionRecord: vi.fn(),
  exportConsumption: vi.fn(),
  getSupportedVillages: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage: mocks.ElMessage,
  ElMessageBox: { confirm: mocks.confirm },
}))

vi.mock('@/api/consumption', () => ({
  CONSUMPTION_CATEGORY_LABELS: {
    agriculture: '农产品',
    livestock: '畜禽',
    handicraft: '手工',
    other: '其他',
  },
  CONSUMPTION_SELLER_TYPE_LABELS: {
    farmer: '农户',
    cooperative: '合作社',
    enterprise: '企业',
  },
  getConsumptionRecords: (...a: any[]) => mocks.getConsumptionRecords(...a),
  getConsumptionStatistics: (...a: any[]) => mocks.getConsumptionStatistics(...a),
  createConsumptionRecord: (...a: any[]) => mocks.createConsumptionRecord(...a),
  updateConsumptionRecord: (...a: any[]) => mocks.updateConsumptionRecord(...a),
  deleteConsumptionRecord: (...a: any[]) => mocks.deleteConsumptionRecord(...a),
  exportConsumption: (...a: any[]) => mocks.exportConsumption(...a),
}))

vi.mock('@/api/supportedVillage', () => ({
  getSupportedVillages: (...a: any[]) => mocks.getSupportedVillages(...a),
}))

import ConsumptionList from '@/views/consumption/List.vue'

// ── 桩组件 ──
const ElButtonStub = {
  name: 'ElButtonStub',
  props: ['disabled', 'loading', 'type', 'text'],
  emits: ['click'],
  template:
    '<button class="stub-btn" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
}
const ElSelectStub = {
  name: 'ElSelectStub',
  props: ['modelValue', 'placeholder', 'clearable'],
  emits: ['update:modelValue', 'change'],
  template: '<div class="select-stub"><slot /></div>',
}
const ElOptionStub = {
  name: 'ElOptionStub',
  props: ['label', 'value'],
  template: '<span class="option-stub">{{ label }}</span>',
}
const ElInputStub = {
  name: 'ElInputStub',
  props: ['modelValue', 'placeholder', 'clearable', 'type', 'rows'],
  emits: ['update:modelValue'],
  template: '<input class="input-stub" :value="modelValue" />',
}
const ElInputNumberStub = {
  name: 'ElInputNumberStub',
  props: ['modelValue', 'min', 'precision'],
  emits: ['update:modelValue'],
  template: '<input class="number-stub" type="number" :value="modelValue" />',
}
const ElDatePickerStub = {
  name: 'ElDatePickerStub',
  props: ['modelValue', 'type', 'valueFormat', 'placeholder'],
  emits: ['update:modelValue'],
  template: '<div class="date-stub"></div>',
}
const ElTagStub = {
  name: 'ElTagStub',
  props: ['type'],
  template: '<span class="tag-stub"><slot /></span>',
}
const ElTableStub = {
  name: 'ElTableStub',
  props: ['data', 'border', 'stripe'],
  template: '<div class="table-stub"><slot /></div>',
}
const ElTableColumnStub = {
  name: 'ElTableColumnStub',
  props: ['prop', 'label', 'width', 'align', 'minWidth', 'fixed', 'showOverflowTooltip'],
  template:
    '<div class="column-stub">' +
    '<slot :row="rowA" :scope="{ row: rowA }" />' +
    '<slot :row="rowB" :scope="{ row: rowB }" />' +
    '<slot :row="rowC" :scope="{ row: rowC }" />' +
    '</div>',
  data() {
    return { rowA: ROWS[0], rowB: ROWS[1], rowC: ROWS[2] }
  },
}
const ElPaginationStub = {
  name: 'ElPaginationStub',
  props: ['currentPage', 'pageSize', 'pageSizes', 'total', 'layout'],
  emits: ['current-change', 'size-change'],
  template: '<div class="pagination-stub">{{ total }}</div>',
}
const ElDialogStub = {
  name: 'ElDialogStub',
  props: ['modelValue', 'title', 'width'],
  emits: ['update:modelValue'],
  template:
    '<div v-if="modelValue" class="dialog-stub" :data-title="title">' +
    '<slot /><slot name="footer" /></div>',
}
const ElFormStub = {
  name: 'ElFormStub',
  props: ['labelWidth'],
  template: '<div class="form-stub"><slot /></div>',
}
const ElFormItemStub = {
  name: 'ElFormItemStub',
  props: ['label', 'required'],
  template: '<div class="form-item-stub"><span class="label-stub">{{ label }}</span><slot /></div>',
}
const ElCardStub = {
  name: 'ElCardStub',
  template: '<div class="card-stub"><slot name="header" /><slot /></div>',
}

const stubs = {
  'el-button': ElButtonStub,
  'el-select': ElSelectStub,
  'el-option': ElOptionStub,
  'el-input': ElInputStub,
  'el-input-number': ElInputNumberStub,
  'el-date-picker': ElDatePickerStub,
  'el-tag': ElTagStub,
  'el-table': ElTableStub,
  'el-table-column': ElTableColumnStub,
  'el-pagination': ElPaginationStub,
  'el-dialog': ElDialogStub,
  'el-form': ElFormStub,
  'el-form-item': ElFormItemStub,
  'el-card': ElCardStub,
}

// ── 夹具（rowB/rowC 用于覆盖模板列的空值/未知值兜底分支）──
const ROWS = [
  {
    id: 1,
    year: 2025,
    category: 'agriculture',
    item_name: '土蜂蜜',
    quantity: 10,
    unit: '斤',
    amount: 1200,
    supported_village_id: 1,
    village_name: '村一',
    buyer: '单位A',
    seller: '农户甲',
    seller_type: 'farmer',
    record_date: '2025-03-01',
    remarks: '首单',
  },
  {
    id: 2,
    year: 2025,
    category: 'unknown-cat',
    item_name: '手工篮',
    quantity: null,
    unit: null,
    amount: 300,
    village_name: '',
    buyer: null,
    seller: null,
    seller_type: null,
    record_date: null,
  },
  {
    id: 3,
    year: 2024,
    category: 'other',
    item_name: '鸡蛋',
    amount: 50,
    supported_village_id: 2,
    buyer: '单位B',
    seller: '合作社乙',
    seller_type: 'unknown-type',
  },
]

const STATS = {
  total_amount: 1550,
  record_count: 3,
  by_category: [
    { category: 'agriculture', amount: 1200, count: 2 },
    { category: 'livestock', total_amount: 350 },
    { category: 'other' },
  ],
  by_village: [
    { village_name: '村一', amount: 1200, count: 2 },
    { supported_village_id: 2, total_amount: 350 },
    { village_id: 3, amount: 0 },
    { village_name: '村无金额' },
  ],
}

function mountComp() {
  return mount(ConsumptionList, {
    global: { renderStubDefaultSlot: true, stubs },
  })
}

const findBtn = (wrapper: any, testId: string) => wrapper.find(`[data-testid="${testId}"]`)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getConsumptionRecords.mockResolvedValue({ items: ROWS, total: 3 })
  mocks.getConsumptionStatistics.mockResolvedValue(STATS)
  mocks.getSupportedVillages.mockResolvedValue({
    items: [{ id: 1, village_name: '村一' }, { id: 2 }],
    total: 2,
  })
  mocks.createConsumptionRecord.mockResolvedValue({ id: 9 })
  mocks.updateConsumptionRecord.mockResolvedValue({ id: 1 })
  mocks.deleteConsumptionRecord.mockResolvedValue(true)
  mocks.exportConsumption.mockResolvedValue(undefined)
  mocks.confirm.mockResolvedValue('confirm')
})

describe('挂载与统计卡', () => {
  it('加载村选项/台账/统计，统计卡与表格模板全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()

    expect(mocks.getSupportedVillages).toHaveBeenCalledWith({ page: 1, page_size: 500 })
    expect(mocks.getConsumptionRecords).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
      year: CURRENT_YEAR,
    })
    expect(mocks.getConsumptionStatistics).toHaveBeenCalledWith(CURRENT_YEAR)
    expect((wrapper.vm as any).villageOptions).toEqual([
      { value: 1, label: '村一' },
      { value: 2, label: '#2' },
    ])

    // 统计卡：总额/笔数/品类（amount 与 total_amount 双字段）/村（village_name 与两种 id）
    expect(wrapper.find('[data-testid="stat-total"]').text()).toBe('1,550元')
    expect(wrapper.find('[data-testid="stat-count"]').text()).toBe('3')
    const categoryTags = wrapper.findAll('[data-testid="category-stat"]')
    expect(categoryTags).toHaveLength(3)
    expect(categoryTags[0].text()).toContain('农产品')
    expect(categoryTags[0].text()).toContain('1,200元')
    expect(categoryTags[1].text()).toContain('畜禽')
    expect(categoryTags[1].text()).toContain('350元')
    expect(categoryTags[1].text()).toContain('0') // count 缺省 → 0
    expect(categoryTags[2].text()).toContain('0元') // amount/total_amount 均缺省 → 0
    const villageTags = wrapper.findAll('[data-testid="village-stat"]')
    expect(villageTags).toHaveLength(4)
    expect(villageTags[0].text()).toContain('村一')
    expect(villageTags[1].text()).toContain('#2')
    expect(villageTags[2].text()).toContain('#3')
    expect(villageTags[3].text()).toContain('村无金额')
    expect(villageTags[3].text()).toContain('0元')

    // 表格模板：品类标签（已知/未知）、数量单位、日期、村/采购方/供货方空值兜底
    const text = wrapper.text()
    expect(text).toContain('农产品')
    expect(text).toContain('unknown-cat')
    expect(text).toContain('其他')
    expect(text).toContain('10斤')
    expect(text).toContain('2025-03-01')
    expect(text).toContain('农户甲')
    expect(text).toContain('农户')
    expect(text).toContain('unknown-type')
    expect(text).toContain('合作社')
    expect(wrapper.find('[data-testid="record-pagination"]').exists()).toBe(true)

    // 工具函数兜底分支（空供货方类型 / 数量单位缺省 / 未知品类 / 空日期）
    const vm = wrapper.vm as any
    expect(vm.sellerTypeLabel(null)).toBe('-')
    expect(vm.sellerTypeLabel('farmer')).toBe('农户')
    expect(vm.sellerTypeLabel('x')).toBe('x')
    expect(vm.quantityText({ quantity: 5, unit: null })).toBe('5')
    expect(vm.quantityText({ quantity: undefined })).toBe('-')
    expect(vm.categoryLabel('x')).toBe('x')
    expect(vm.categoryTagType('agriculture')).toBe('success')
    expect(vm.categoryTagType('x')).toBe('info')
    expect(vm.formatDateText(null)).toBe('-')
  })

  it('空台账与空统计：额度显示 -、笔数 0、无分页', async () => {
    mocks.getConsumptionRecords.mockResolvedValue({ items: [], total: 0 })
    mocks.getConsumptionStatistics.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.find('[data-testid="stat-total"]').text()).toBe('-')
    expect(wrapper.find('[data-testid="stat-count"]').text()).toBe('0')
    expect(wrapper.findAll('[data-testid="category-stat"]')).toHaveLength(0)
    expect(wrapper.findAll('[data-testid="village-stat"]')).toHaveLength(0)
    expect(wrapper.find('[data-testid="record-pagination"]').exists()).toBe(false)
  })

  it('加载失败：列表与统计各自提示；村选项失败静默', async () => {
    mocks.getConsumptionRecords.mockRejectedValue({ userMessage: '台账服务不可用' })
    mocks.getConsumptionStatistics.mockRejectedValue({ userMessage: '统计服务不可用' })
    mocks.getSupportedVillages.mockRejectedValue(new Error('options down'))
    const wrapper = mountComp()
    await flushPromises()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('台账服务不可用')
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('统计服务不可用')
    const vm = wrapper.vm as any
    expect(vm.records).toEqual([])
    expect(vm.stats).toEqual({})
    expect(vm.statsLoading).toBe(false)
    expect(vm.loading).toBe(false)
  })
})

describe('筛选/年度联动/分页', () => {
  it('查询携带筛选参数；重置回默认；年度 change 同步刷新列表与统计；分页事件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.categoryFilter = 'agriculture'
    vm.villageFilter = 1
    vm.keyword = ' 蜂蜜 '
    await findBtn(wrapper, 'search-btn').trigger('click')
    await flushPromises()
    expect(mocks.getConsumptionRecords).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 20,
      year: CURRENT_YEAR,
      category: 'agriculture',
      village_id: 1,
      keyword: '蜂蜜',
    })

    await findBtn(wrapper, 'reset-btn').trigger('click')
    await flushPromises()
    expect(vm.categoryFilter).toBe('')
    expect(vm.villageFilter).toBeNull()
    expect(vm.keyword).toBe('')
    expect(vm.yearFilter).toBe(CURRENT_YEAR)
    expect(mocks.getConsumptionStatistics).toHaveBeenLastCalledWith(CURRENT_YEAR)

    // 年度 select change 内联处理器
    const yearSelect = wrapper.findAllComponents({ name: 'ElSelectStub' })[0]
    yearSelect.vm.$emit('update:modelValue', 2024)
    yearSelect.vm.$emit('change', 2024)
    await flushPromises()
    expect(vm.yearFilter).toBe(2024)
    expect(vm.page).toBe(1)
    expect(mocks.getConsumptionRecords).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 20,
      year: 2024,
    })
    expect(mocks.getConsumptionStatistics).toHaveBeenLastCalledWith(2024)

    // 分页事件
    const pagination = wrapper.findComponent({ name: 'ElPaginationStub' })
    pagination.vm.$emit('current-change', 2)
    await flushPromises()
    expect(vm.page).toBe(2)
    pagination.vm.$emit('size-change', 50)
    await flushPromises()
    expect(vm.pageSize).toBe(50)
    expect(vm.page).toBe(1)
  })

  it('筛选下拉与关键词输入 v-model 内联处理器', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const selects = wrapper.findAllComponents({ name: 'ElSelectStub' })
    // 筛选：年度/品类/村
    selects[1].vm.$emit('update:modelValue', 'livestock')
    selects[2].vm.$emit('update:modelValue', 2)
    wrapper.findComponent({ name: 'ElInputStub' }).vm.$emit('update:modelValue', '鸡蛋')
    expect(vm.categoryFilter).toBe('livestock')
    expect(vm.villageFilter).toBe(2)
    expect(vm.keyword).toBe('鸡蛋')
  })
})

describe('新建/编辑', () => {
  it('新建：重置表单 → 校验（品名/金额）→ 成功创建并刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await findBtn(wrapper, 'create-btn').trigger('click')
    await nextTick()
    expect(vm.dialogVisible).toBe(true)
    expect(vm.editingId).toBeNull()
    expect(vm.form).toMatchObject({
      year: CURRENT_YEAR,
      category: 'agriculture',
      item_name: '',
      amount: null,
    })

    // 品名为空
    await findBtn(wrapper, 'record-save').trigger('click')
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('请输入品名')
    expect(mocks.createConsumptionRecord).not.toHaveBeenCalled()

    // 金额缺失
    vm.form.item_name = ' 土蜂蜜 '
    await findBtn(wrapper, 'record-save').trigger('click')
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('请输入正确的金额')

    // 金额 <= 0
    vm.form.amount = 0
    await findBtn(wrapper, 'record-save').trigger('click')
    expect(mocks.ElMessage.error).toHaveBeenCalledTimes(3)

    // 正常创建
    vm.form.amount = 1200
    vm.form.supported_village_id = 1
    vm.form.quantity = 10
    vm.form.unit = '斤'
    vm.form.buyer = '单位A'
    vm.form.seller = '农户甲'
    vm.form.seller_type = 'farmer'
    vm.form.record_date = '2025-03-01'
    vm.form.remarks = '首单'
    await findBtn(wrapper, 'record-save').trigger('click')
    await flushPromises()
    expect(mocks.createConsumptionRecord).toHaveBeenCalledWith({
      supported_village_id: 1,
      category: 'agriculture',
      item_name: '土蜂蜜',
      quantity: 10,
      unit: '斤',
      amount: 1200,
      buyer: '单位A',
      seller: '农户甲',
      seller_type: 'farmer',
      year: CURRENT_YEAR,
      record_date: '2025-03-01',
      remarks: '首单',
    })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('消费帮扶记录已创建')
    expect(vm.dialogVisible).toBe(false)
    expect(mocks.getConsumptionRecords).toHaveBeenCalled()
    expect(mocks.getConsumptionStatistics).toHaveBeenCalled()

    // 对话框 v-model 内联处理器 + 取消按钮
    vm.dialogVisible = true
    await nextTick()
    const dialog = wrapper.findComponent({ name: 'ElDialogStub' })
    dialog.vm.$emit('update:modelValue', false)
    expect(vm.dialogVisible).toBe(false)
    vm.dialogVisible = true
    await nextTick()
    const cancelBtn = wrapper.findAll('.stub-btn').find((b: any) => b.text().trim() === '取消')
    await cancelBtn!.trigger('click')
    expect(vm.dialogVisible).toBe(false)
  })

  it('编辑：回填（空值兜底）→ 更新载荷空串转 null；表单内联 v-model；保存失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 表格模板「编辑」按钮
    await findBtn(wrapper, 'record-edit').trigger('click')
    await nextTick()
    expect(vm.editingId).toBe(1)
    expect(vm.form).toMatchObject({ item_name: '土蜂蜜', supported_village_id: 1 })
    // 编辑行的空值兜底分支（含 amount 缺省）
    vm.openEdit({ id: 5, item_name: '无金额记录', category: 'other', year: 2025 })
    expect(vm.form.amount).toBeNull()
    vm.openEdit(ROWS[1])
    expect(vm.form).toMatchObject({
      supported_village_id: null,
      quantity: null,
      unit: '',
      buyer: '',
      seller: '',
      seller_type: '',
      record_date: null,
      remarks: '',
    })

    // 对话框内 v-model 内联处理器：selects（年度/品类/村/供货方类型）+ input(s)
    vm.openEdit(ROWS[0])
    await nextTick()
    const dialog = wrapper.findComponent({ name: 'ElDialogStub' })
    const selects = dialog.findAllComponents({ name: 'ElSelectStub' })
    selects[0].vm.$emit('update:modelValue', 2024)
    selects[1].vm.$emit('update:modelValue', 'livestock')
    selects[2].vm.$emit('update:modelValue', 2)
    selects[3].vm.$emit('update:modelValue', 'cooperative')
    const inputs = dialog.findAllComponents({ name: 'ElInputStub' })
    inputs[0].vm.$emit('update:modelValue', '鸡蛋')
    inputs[1].vm.$emit('update:modelValue', '箱')
    inputs[2].vm.$emit('update:modelValue', '单位B')
    inputs[3].vm.$emit('update:modelValue', '合作社乙')
    inputs[4].vm.$emit('update:modelValue', '备注')
    const numbers = dialog.findAllComponents({ name: 'ElInputNumberStub' })
    numbers[0].vm.$emit('update:modelValue', 5)
    numbers[1].vm.$emit('update:modelValue', 350)
    dialog.findComponent({ name: 'ElDatePickerStub' }).vm.$emit('update:modelValue', '2025-06-01')

    // 清空可选文本 → null 分支
    vm.form.unit = ''
    vm.form.record_date = null
    await findBtn(wrapper, 'record-save').trigger('click')
    await flushPromises()
    expect(mocks.updateConsumptionRecord).toHaveBeenCalledWith(1, {
      supported_village_id: 2,
      category: 'livestock',
      item_name: '鸡蛋',
      quantity: 5,
      unit: null,
      amount: 350,
      buyer: '单位B',
      seller: '合作社乙',
      seller_type: 'cooperative',
      year: 2024,
      record_date: null,
      remarks: '备注',
    })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('消费帮扶记录已更新')

    // 保存失败（同时覆盖 buildPayload 可选文本空串 → null 分支）
    mocks.updateConsumptionRecord.mockRejectedValueOnce({ userMessage: '无权限' })
    vm.openEdit(ROWS[0])
    vm.form.item_name = '土蜂蜜'
    vm.form.amount = 10
    vm.form.buyer = ''
    vm.form.seller = ''
    vm.form.seller_type = ''
    vm.form.remarks = ''
    await vm.saveRecord()
    expect(mocks.updateConsumptionRecord).toHaveBeenLastCalledWith(
      1,
      expect.objectContaining({ buyer: null, seller: null, seller_type: null, remarks: null })
    )
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('无权限')
    expect(vm.saving).toBe(false)
  })
})

describe('删除与导出', () => {
  it('删除：确认成功/取消/失败三态', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await findBtn(wrapper, 'record-delete').trigger('click')
    await flushPromises()
    expect(mocks.confirm).toHaveBeenCalled()
    expect(mocks.deleteConsumptionRecord).toHaveBeenCalledWith(1)
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('消费帮扶记录已删除')
    expect(vm.page).toBe(1)

    mocks.confirm.mockRejectedValueOnce('cancel')
    const calls = mocks.deleteConsumptionRecord.mock.calls.length
    await vm.handleDelete(ROWS[1])
    expect(mocks.deleteConsumptionRecord.mock.calls.length).toBe(calls)

    mocks.deleteConsumptionRecord.mockRejectedValueOnce({ userMessage: '记录不存在' })
    await vm.handleDelete(ROWS[2])
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('记录不存在')
  })

  it('导出 xlsx / csv：成功提示与失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.categoryFilter = 'agriculture'
    vm.villageFilter = 1
    vm.keyword = ' 蜂蜜 '

    await findBtn(wrapper, 'export-xlsx-btn').trigger('click')
    await flushPromises()
    expect(mocks.exportConsumption).toHaveBeenLastCalledWith({
      format: 'xlsx',
      year: CURRENT_YEAR,
      category: 'agriculture',
      village_id: 1,
      keyword: '蜂蜜',
    })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('导出任务已开始')

    await findBtn(wrapper, 'export-csv-btn').trigger('click')
    await flushPromises()
    expect(mocks.exportConsumption).toHaveBeenLastCalledWith(
      expect.objectContaining({ format: 'csv' })
    )

    mocks.exportConsumption.mockRejectedValueOnce({ userMessage: '导出失败A' })
    await vm.exportData('csv')
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('导出失败A')
    expect(vm.exporting).toBe(false)
  })
})
