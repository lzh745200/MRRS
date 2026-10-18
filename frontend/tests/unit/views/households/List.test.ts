/**
 * views/households/List.vue 单元测试（四指标 100%）
 *
 * 单执行者：List.vue 全仓仅本文件执行（挂载）。
 * 覆盖：挂载加载（村下拉 + 列表）、筛选/重置/分页、新建/编辑/删除、
 * 台账导出 xlsx/csv、「一键汇总回填」、风险预警抽屉、详情跳转与全部展示映射。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const mocks = vi.hoisted(() => ({
  getHouseholds: vi.fn(),
  createHousehold: vi.fn(),
  updateHousehold: vi.fn(),
  deleteHousehold: vi.fn(),
  exportHouseholds: vi.fn(),
  rollupHouseholds: vi.fn(),
  getHouseholdAlerts: vi.fn(),
  getSupportedVillages: vi.fn(),
  pushSafe: vi.fn(),
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  confirm: vi.fn(),
}))

vi.mock('@/api/households', () => ({
  getHouseholds: mocks.getHouseholds,
  createHousehold: mocks.createHousehold,
  updateHousehold: mocks.updateHousehold,
  deleteHousehold: mocks.deleteHousehold,
  exportHouseholds: mocks.exportHouseholds,
  rollupHouseholds: mocks.rollupHouseholds,
  getHouseholdAlerts: mocks.getHouseholdAlerts,
}))

vi.mock('@/api/supportedVillage', () => ({
  getSupportedVillages: mocks.getSupportedVillages,
}))

vi.mock('element-plus', () => ({
  ElMessage: mocks.ElMessage,
  ElMessageBox: { confirm: mocks.confirm },
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mocks.pushSafe }),
}))

vi.mock('@/composables/useDesensitize', () => ({
  useDesensitize: () => ({ ds: (value: any) => String(value) }),
}))

vi.mock('@/components/business/EmptyState/EmptyState.vue', () => ({
  default: {
    props: ['description', 'text'],
    template: '<div class="empty-stub" :data-description="description" />',
  },
}))

import List from '@/views/households/List.vue'

const ROW_A = {
  id: 1,
  supported_village_id: 11,
  village_name: '甲村',
  household_code: 'A-1',
  household_name: '张三',
  address: '甲村1号',
  household_type: 'poverty',
  risk_type: 'illness',
  risk_level: 'high',
  helper_name: '李四',
  helper_phone: '13800000000',
  annual_income: 12000,
  migrant_workers: 2,
  has_serious_illness: true,
  housing_safe: false,
  last_visit_date: '2026-01-01',
  monitoring_note: '需持续跟踪',
  member_count: 3,
  risk_alerts: ['连续未走访', '大病'],
}

const ROW_B = {
  id: 2,
  supported_village_id: 12,
  village_name: null,
  household_code: null,
  household_name: '王五',
  household_type: 'general',
  risk_type: 'none',
  risk_level: 'low',
  helper_name: null,
  member_count: undefined,
  risk_alerts: [],
}

const TABLE_ROWS = [ROW_A, ROW_B]

const ALERT_A = {
  household_id: 1,
  household_name: '张三',
  village_name: '甲村',
  risk_level: 'high',
  alerts: ['大病', '住房不安全'],
}

const ALERT_B = {
  household_id: 2,
  household_name: null,
  village_name: null,
  risk_level: null,
  reason: '连续 90 天未走访',
}

const elementStubs = {
  'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
  'el-button': {
    props: ['disabled', 'loading', 'type', 'size', 'link', 'plain'],
    emits: ['click'],
    template:
      '<button type="button" class="el-button-stub" :data-loading="String(loading)"' +
      ' @click="$emit(\'click\')"><slot /></button>',
  },
  'el-select': {
    props: ['modelValue'],
    emits: ['update:modelValue', 'change'],
    template:
      '<div class="el-select-stub">' +
      "<button type=\"button\" class=\"select-emit\" @click=\"$emit('update:modelValue', 'high'); $emit('change', 'high')\">x</button>" +
      '<slot /></div>',
  },
  'el-option': {
    props: ['label', 'value'],
    template: '<span class="el-option-stub" :data-value="String(value)">{{ label }}</span>',
  },
  'el-input': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<input class="el-input-stub" :value="modelValue"' +
      ' @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  'el-input-number': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<input class="el-input-number-stub" type="number" :value="modelValue"' +
      ' @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
  },
  'el-switch': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<button type="button" class="el-switch-stub" :data-on="String(modelValue)"' +
      ' @click="$emit(\'update:modelValue\', !modelValue)" />',
  },
  'el-date-picker': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<button type="button" class="el-date-stub" @click="$emit(\'update:modelValue\', \'2026-02-02\')">d</button>',
  },
  'el-drawer': {
    props: ['modelValue', 'title', 'size'],
    emits: ['update:modelValue'],
    template:
      '<div class="el-drawer-stub" :data-title="title" :data-open="String(modelValue)">' +
      '<button type="button" class="dialog-close" @click="$emit(\'update:modelValue\', false)">x</button>' +
      '<slot /><slot name="footer" /></div>',
  },
  'el-dialog': {
    props: ['modelValue', 'title', 'width'],
    emits: ['update:modelValue'],
    template:
      '<div class="el-dialog-stub" :data-title="title" :data-open="String(modelValue)">' +
      '<button type="button" class="dialog-close" @click="$emit(\'update:modelValue\', false)">x</button>' +
      '<slot /><slot name="footer" /></div>',
  },
  'el-form': { template: '<form class="el-form-stub"><slot /></form>' },
  'el-form-item': {
    props: ['label'],
    template: '<div class="el-form-item-stub" :data-label="label"><slot /></div>',
  },
  'el-table': { template: '<div class="el-table-stub"><slot /></div>' },
  'el-table-column': {
    props: ['label', 'prop', 'width', 'minWidth', 'fixed'],
    data() {
      return { rows: TABLE_ROWS }
    },
    template:
      '<div class="el-table-column-stub" :data-label="label">' +
      '<div class="col-cell" v-for="(row, index) in rows" :key="index">{{ prop ? row[prop] : "-" }}<slot :row="row" /></div></div>',
  },
  'el-tag': {
    props: ['type', 'size'],
    template: '<span class="el-tag-stub" :data-type="type"><slot /></span>',
  },
  'el-pagination': {
    props: ['total', 'currentPage', 'pageSize'],
    emits: ['current-change', 'size-change'],
    template:
      '<div class="el-pagination-stub">' +
      '<button type="button" class="page-next" @click="$emit(\'current-change\', 2)">n</button>' +
      '<button type="button" class="size-change" @click="$emit(\'size-change\', 20)">s</button></div>',
  },
}

function mountComp() {
  return mount(List, { global: { stubs: { ...elementStubs } } })
}

function vmOf(wrapper: ReturnType<typeof mountComp>) {
  return wrapper.vm as any
}

describe('households/List.vue（一户一档列表）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getHouseholds.mockResolvedValue({
      items: [ROW_A, ROW_B],
      total: 2,
      page: 1,
      page_size: 10,
    })
    mocks.getSupportedVillages.mockResolvedValue({
      items: [{ id: 11, village_name: '甲村' }, { id: 12, name: '乙村' }, { id: 13 }],
      total: 3,
    })
    mocks.createHousehold.mockResolvedValue({ id: 3 })
    mocks.updateHousehold.mockResolvedValue({ id: 1 })
    mocks.deleteHousehold.mockResolvedValue({ id: 1 })
    mocks.exportHouseholds.mockResolvedValue(undefined)
    mocks.rollupHouseholds.mockResolvedValue({ total_households: 2, total_population: 6 })
    mocks.getHouseholdAlerts.mockResolvedValue([ALERT_A, ALERT_B])
    mocks.confirm.mockResolvedValue(undefined)
  })

  it('挂载：加载村下拉与列表，渲染台账行与预警标记', async () => {
    const wrapper = mountComp()
    await flushPromises()

    expect(mocks.getSupportedVillages).toHaveBeenCalledWith({ page: 1, page_size: 500 })
    expect(mocks.getHouseholds).toHaveBeenCalledWith({
      page: 1,
      page_size: 10,
      village_id: undefined,
      risk_level: '',
      household_type: '',
      keyword: undefined,
    })
    const vm = vmOf(wrapper)
    expect(vm.villageOptions).toEqual([
      { id: 11, name: '甲村' },
      { id: 12, name: '乙村' },
      { id: 13, name: '村13' },
    ])
    expect(wrapper.text()).toContain('张三')
    expect(wrapper.text()).toContain('甲村')
    expect(wrapper.text()).toContain('A-1')
    expect(wrapper.text()).toContain('脱贫户')
    expect(wrapper.text()).toContain('高')
    expect(wrapper.text()).toContain('连续未走访')
    expect(wrapper.text()).toContain('共 2 户')
    // 台账卡内空态不渲染（预警抽屉内的空态不计）
    expect(wrapper.find('.table-card .empty-stub').exists()).toBe(false)
    wrapper.unmount()
  })

  it('空列表 / 缺字段响应：空态渲染且计数归零', async () => {
    mocks.getHouseholds.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)
    expect(vm.items).toEqual([])
    expect(vm.total).toBe(0)
    expect(wrapper.find('.empty-stub').attributes('data-description')).toBe('暂无建档记录')
    wrapper.unmount()
  })

  it('加载失败：列表与村下拉分别降级并提示', async () => {
    mocks.getHouseholds.mockRejectedValue(new Error('net'))
    mocks.getSupportedVillages.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('加载一户一档列表失败')
    expect(vmOf(wrapper).villageOptions).toEqual([])
    expect(vmOf(wrapper).items).toEqual([])
    wrapper.unmount()
  })

  it('村下拉支持数组直返', async () => {
    mocks.getSupportedVillages.mockResolvedValue([{ id: 21, village_name: '丙村' }])
    const wrapper = mountComp()
    await flushPromises()
    expect(vmOf(wrapper).villageOptions).toEqual([{ id: 21, name: '丙村' }])
    wrapper.unmount()
  })

  it('村下拉返回 null → 空选项兜底', async () => {
    mocks.getSupportedVillages.mockResolvedValue(null)
    const wrapper = mountComp()
    await flushPromises()
    expect(vmOf(wrapper).villageOptions).toEqual([])
    wrapper.unmount()
  })

  it('筛选：查询/重置/关键词回车/分页', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)
    mocks.getHouseholds.mockClear()

    vm.query.village_id = 11
    vm.query.risk_level = 'high'
    vm.query.household_type = 'monitor'
    vm.query.keyword = ' 张三 '
    await wrapper.find('.btn-search').trigger('click')
    await flushPromises()
    expect(vm.query.page).toBe(1)
    expect(mocks.getHouseholds).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 1,
        village_id: 11,
        risk_level: 'high',
        household_type: 'monitor',
        keyword: '张三',
      })
    )

    await wrapper.find('.btn-reset').trigger('click')
    await flushPromises()
    expect(vm.query).toMatchObject({
      village_id: undefined,
      risk_level: '',
      household_type: '',
      keyword: '',
      page: 1,
    })

    // 关键词输入（v-model）与回车查询
    await wrapper.find('.f-keyword').setValue('王五')
    await wrapper.find('.f-keyword').trigger('keyup', { key: 'Enter' })
    await flushPromises()
    expect(vm.query.keyword).toBe('王五')

    // 分页
    await wrapper.find('.page-next').trigger('click')
    await flushPromises()
    expect(vm.query.page).toBe(2)
    await wrapper.find('.size-change').trigger('click')
    await flushPromises()
    expect(vm.query.page_size).toBe(20)
    expect(vm.query.page).toBe(1)
    wrapper.unmount()
  })

  it('筛选下拉 v-model 处理器全部可达', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)
    await wrapper.find('.f-village .select-emit').trigger('click')
    await wrapper.find('.f-risk .select-emit').trigger('click')
    await wrapper.find('.f-type .select-emit').trigger('click')
    expect(vm.query.village_id).toBe('high')
    expect(vm.query.risk_level).toBe('high')
    expect(vm.query.household_type).toBe('high')
    wrapper.unmount()
  })

  it('新建：必填校验、成功建档、失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    await wrapper.find('.btn-create').trigger('click')
    expect(vm.drawerVisible).toBe(true)
    expect(vm.editingId).toBeNull()
    expect(wrapper.find('.el-drawer-stub').attributes('data-title')).toBe('新建一户一档')

    await wrapper.find('.btn-drawer-save').trigger('click')
    await flushPromises()
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('请选择帮扶村')

    vm.form.supported_village_id = 11
    await wrapper.find('.btn-drawer-save').trigger('click')
    await flushPromises()
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('请输入户主姓名')

    vm.form.household_name = '赵六'
    await wrapper.find('.btn-drawer-save').trigger('click')
    await flushPromises()
    expect(mocks.createHousehold).toHaveBeenCalled()
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('建档成功')
    expect(vm.drawerVisible).toBe(false)
    expect(vm.query.page).toBe(1)

    // 失败分支
    mocks.createHousehold.mockRejectedValueOnce(new Error('x'))
    vm.form.supported_village_id = 11
    vm.form.household_name = '赵六'
    await vm.handleSave()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('建档失败')
    wrapper.unmount()
  })

  it('编辑：回填（含空值兜底）并更新，失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    await wrapper.find('.btn-edit').trigger('click')
    expect(mocks.pushSafe).not.toHaveBeenCalled()
    vm.openEdit(ROW_A)
    expect(vm.editingId).toBe(1)
    expect(vm.form).toMatchObject({
      supported_village_id: 11,
      household_name: '张三',
      helper_name: '李四',
      has_serious_illness: true,
      housing_safe: false,
    })
    await nextTick()
    expect(wrapper.find('.el-drawer-stub').attributes('data-title')).toBe('编辑一户一档')

    // null / undefined 回填分支
    vm.openEdit(ROW_B)
    expect(vm.form).toMatchObject({
      household_code: '',
      helper_name: '',
      helper_phone: '',
      annual_income: undefined,
      migrant_workers: undefined,
      last_visit_date: '',
      monitoring_note: '',
      has_serious_illness: false,
      housing_safe: true,
    })

    vm.openEdit(ROW_A)
    await vm.handleSave()
    expect(mocks.updateHousehold).toHaveBeenCalledWith(1, expect.any(Object))
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('档案已更新')

    mocks.updateHousehold.mockRejectedValueOnce(new Error('x'))
    vm.openEdit(ROW_A)
    await vm.handleSave()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('更新失败')
    wrapper.unmount()
  })

  it('删除：确认删除、取消、失败、末页回退', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    await wrapper.find('.btn-delete').trigger('click')
    await flushPromises()
    expect(mocks.confirm).toHaveBeenCalled()
    expect(mocks.deleteHousehold).toHaveBeenCalledWith(1)
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('删除成功')

    // 取消删除
    mocks.confirm.mockRejectedValueOnce('cancel')
    mocks.deleteHousehold.mockClear()
    await wrapper.find('.btn-delete').trigger('click')
    await flushPromises()
    expect(mocks.deleteHousehold).not.toHaveBeenCalled()

    // 删除失败
    mocks.deleteHousehold.mockRejectedValueOnce(new Error('x'))
    await wrapper.find('.btn-delete').trigger('click')
    await flushPromises()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('删除失败')

    // 末页最后一条 → page-1
    mocks.getHouseholds.mockResolvedValue({ items: [ROW_A], total: 1, page: 2, page_size: 10 })
    vm.query.page = 2
    await vm.loadData()
    mocks.deleteHousehold.mockResolvedValue({ id: 1 })
    await vm.handleDelete(ROW_A)
    expect(vm.query.page).toBe(1)
    wrapper.unmount()
  })

  it('导出：xlsx / csv 成功与失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)
    vm.query.village_id = 11
    vm.query.risk_level = 'high'

    await wrapper.find('.btn-export-xlsx').trigger('click')
    await flushPromises()
    expect(mocks.exportHouseholds).toHaveBeenCalledWith({
      format: 'xlsx',
      village_id: 11,
      risk_level: 'high',
    })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('台账 Excel 导出已开始')

    await wrapper.find('.btn-export-csv').trigger('click')
    await flushPromises()
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('台账 CSV 导出已开始')

    mocks.exportHouseholds.mockRejectedValueOnce(new Error('x'))
    await wrapper.find('.btn-export-xlsx').trigger('click')
    await flushPromises()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('台账导出失败')
    wrapper.unmount()
  })

  it('汇总回填：必填校验、成功（写回摘要）与失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    vm.query.village_id = 11
    await wrapper.find('.btn-rollup').trigger('click')
    expect(vm.rollupVisible).toBe(true)
    expect(vm.rollupForm.village_id).toBe(11)

    vm.rollupForm.village_id = undefined
    await wrapper.find('.btn-rollup-confirm').trigger('click')
    await flushPromises()
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('请选择帮扶村')

    vm.rollupForm.village_id = 11
    await wrapper.find('.btn-rollup-confirm').trigger('click')
    await flushPromises()
    expect(mocks.rollupHouseholds).toHaveBeenCalledWith({
      village_id: 11,
      year: new Date().getFullYear(),
    })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('已回填：总户数 2、总人口 6')
    expect(vm.rollupVisible).toBe(false)

    mocks.rollupHouseholds.mockRejectedValueOnce(new Error('x'))
    await vm.handleRollup()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('汇总回填失败')

    // 结果摘要四种形态
    expect(vm.formatRollupResult({ message: '后端消息' })).toBe('后端消息')
    expect(vm.formatRollupResult({ written: { total_households: 3, extra: null } })).toBe(
      '已回填：总户数 3、extra —'
    )
    expect(vm.formatRollupResult({ total_households: 3 })).toBe('已回填：总户数 3')
    expect(
      vm.formatRollupResult({
        total_households: 1,
        total_population: 2,
        poverty_households: 3,
        monitor_households: 4,
      })
    ).toBe('已回填：总户数 1、总人口 2、脱贫户数 3、监测户数 4')
    expect(vm.formatRollupResult({})).toBe('汇总回填完成')
    wrapper.unmount()
  })

  it('风险预警抽屉：打开加载、等级切换、空态、失败与跳转', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    await wrapper.find('.btn-alerts').trigger('click')
    await flushPromises()
    expect(vm.alertsVisible).toBe(true)
    expect(mocks.getHouseholdAlerts).toHaveBeenCalledWith({ level: '' })
    expect(wrapper.text()).toContain('连续 90 天未走访')
    expect(wrapper.text()).toContain('大病；住房不安全')

    await wrapper.find('.btn-alert-view').trigger('click')
    expect(mocks.pushSafe).toHaveBeenCalledWith('/households/1')

    // 等级切换触发 @change → 重新加载
    mocks.getHouseholdAlerts.mockClear()
    await wrapper.find('.alert-level .select-emit').trigger('click')
    await flushPromises()
    expect(mocks.getHouseholdAlerts).toHaveBeenCalledWith({ level: 'high' })

    // 空态
    mocks.getHouseholdAlerts.mockResolvedValueOnce([])
    await wrapper.find('.btn-alerts-refresh').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.empty-stub').length).toBeGreaterThan(0)

    // 失败降级
    mocks.getHouseholdAlerts.mockRejectedValueOnce(new Error('x'))
    await wrapper.find('.btn-alerts-refresh').trigger('click')
    await flushPromises()
    expect(vm.alerts).toEqual([])
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('加载风险预警失败')

    // 非数组响应兜底：ok_list envelope → items；null → []
    mocks.getHouseholdAlerts.mockResolvedValueOnce({ items: [ALERT_B] })
    await vm.loadAlerts()
    expect(vm.alerts).toEqual([ALERT_B])
    mocks.getHouseholdAlerts.mockResolvedValueOnce(null)
    await vm.loadAlerts()
    expect(vm.alerts).toEqual([])
    wrapper.unmount()
  })

  it('详情跳转与 Alert 跳转', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)
    await wrapper.find('.btn-view').trigger('click')
    expect(mocks.pushSafe).toHaveBeenCalledWith('/households/1')
    vm.goDetailFromAlert(ALERT_B)
    expect(mocks.pushSafe).toHaveBeenCalledWith('/households/2')
    wrapper.unmount()
  })

  it('展示映射函数：类型/等级/日期/责任人/兜底', () => {
    const wrapper = mountComp()
    const vm = vmOf(wrapper)
    expect(vm.householdTypeLabel('monitor')).toBe('监测户')
    expect(vm.householdTypeLabel('general')).toBe('一般户')
    expect(vm.householdTypeLabel('poverty')).toBe('脱贫户')
    expect(vm.householdTypeLabel('unknown')).toBe('unknown')
    expect(vm.householdTypeLabel(null)).toBe('—')
    expect(vm.typeTagType('poverty')).toBe('warning')
    expect(vm.typeTagType('monitor')).toBe('danger')
    expect(vm.typeTagType('general')).toBe('success')
    expect(vm.riskLevelLabel('high')).toBe('高')
    expect(vm.riskLevelLabel('medium')).toBe('中')
    expect(vm.riskLevelLabel('low')).toBe('低')
    expect(vm.riskLevelLabel('unknown')).toBe('unknown')
    expect(vm.riskLevelLabel(null)).toBe('—')
    expect(vm.riskTagType('high')).toBe('danger')
    expect(vm.riskTagType('medium')).toBe('warning')
    expect(vm.riskTagType('low')).toBe('info')
    expect(vm.formatDate('2026-01-01')).toBe('2026-01-01')
    expect(vm.formatDate(null)).toBe('—')
    expect(vm.formatHelperName('张三')).toBe('张三')
    expect(vm.formatHelperName(null)).toBe('—')
    expect(vm.alertsOf(ROW_A)).toEqual(['连续未走访', '大病'])
    expect(vm.alertsOf({ ...ROW_A, risk_alerts: undefined })).toEqual([])
    expect(vm.alertText(ALERT_A)).toBe('大病；住房不安全')
    expect(vm.alertText(ALERT_B)).toBe('连续 90 天未走访')
    expect(vm.alertText({ household_id: 3 })).toBe('规则命中')
    wrapper.unmount()
  })

  it('抽屉表单单向/双向绑定处理器全量可达', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)
    vm.openEdit(ROW_A)
    await nextTick()

    const inputs = wrapper.findAll('.el-input-stub')
    expect(inputs.length).toBeGreaterThan(0)
    await inputs.forEach((input) => input.setValue('v'))
    await wrapper.find('.form-income').setValue('100')
    await wrapper.find('.form-migrant').setValue('2')
    await wrapper.find('.form-illness').trigger('click')
    await wrapper.find('.form-housing').trigger('click')
    await wrapper.find('.form-visit-date').trigger('click')
    await wrapper.find('.form-village .select-emit').trigger('click')
    await wrapper.find('.form-type .select-emit').trigger('click')
    await wrapper.find('.form-risk-type .select-emit').trigger('click')
    await wrapper.find('.form-risk-level .select-emit').trigger('click')

    expect(vm.form.household_name).toBe('v')
    expect(vm.form.has_serious_illness).toBe(false)
    expect(vm.form.housing_safe).toBe(true)
    expect(vm.form.last_visit_date).toBe('2026-02-02')
    expect(vm.form.household_type).toBe('high')

    await wrapper.find('.btn-drawer-cancel').trigger('click')
    expect(vm.drawerVisible).toBe(false)
    await wrapper.find('.btn-rollup-cancel').trigger('click')
    expect(vm.rollupVisible).toBe(false)
    await wrapper.find('.el-dialog-stub .dialog-close').trigger('click')
    await wrapper.find('.el-drawer-stub .dialog-close').trigger('click')
    vm.openRollup()
    await nextTick()
    await wrapper.find('.rollup-village .select-emit').trigger('click')
    await wrapper.find('.rollup-year').setValue('2027')
    expect(vm.rollupForm.year).toBe(2027)
    await wrapper.find('.el-dialog-stub .dialog-close').trigger('click')
    expect(vm.rollupVisible).toBe(false)
    vm.openAlerts()
    await flushPromises()
    await wrapper.find('.el-drawer-stub[data-title="风险预警"] .dialog-close').trigger('click')
    expect(vm.alertsVisible).toBe(false)
    wrapper.unmount()
  })
})
