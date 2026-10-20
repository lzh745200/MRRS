/**
 * views/households/Detail.vue 单元测试（四指标 100%）
 *
 * 单执行者：Detail.vue 全仓仅本文件执行（挂载）。
 * 覆盖：加载成功/失败/重试、档案头、监测指标、预警提示、风险记录时间线（登记/关闭）、
 * 家庭成员增删改、走访记录、返回列表与全部展示映射函数。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const mocks = vi.hoisted(() => ({
  getHousehold: vi.fn(),
  getHouseholdMembers: vi.fn(),
  createHouseholdMember: vi.fn(),
  updateHouseholdMember: vi.fn(),
  deleteHouseholdMember: vi.fn(),
  createHouseholdRiskRecord: vi.fn(),
  closeHouseholdRiskRecord: vi.fn(),
  pushSafe: vi.fn(),
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  confirm: vi.fn(),
  prompt: vi.fn(),
}))

vi.mock('@/api/households', () => ({
  getHousehold: mocks.getHousehold,
  getHouseholdMembers: mocks.getHouseholdMembers,
  createHouseholdMember: mocks.createHouseholdMember,
  updateHouseholdMember: mocks.updateHouseholdMember,
  deleteHouseholdMember: mocks.deleteHouseholdMember,
  createHouseholdRiskRecord: mocks.createHouseholdRiskRecord,
  closeHouseholdRiskRecord: mocks.closeHouseholdRiskRecord,
}))

vi.mock('element-plus', () => ({
  ElMessage: mocks.ElMessage,
  ElMessageBox: { confirm: mocks.confirm, prompt: mocks.prompt },
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mocks.pushSafe }),
}))

vi.mock('@/composables/useDesensitize', () => ({
  useDesensitize: () => ({ ds: (value: any, type: string) => `${type}:${value}` }),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '7' } }),
  // PageHeader（共享页头标准件）在 setup 阶段调用 useRouter()
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}))

import Detail from '@/views/households/Detail.vue'

const MEMBER_A = {
  id: 1,
  household_id: 7,
  name: '张三',
  relation: '户主',
  id_card: '110101199001011234',
  gender: '男',
  birth_year: 1990,
  education: '高中',
  health_status: '健康',
  employment_status: '务工',
  income: 8000,
  is_special_support: false,
}

const MEMBER_B = {
  id: 2,
  household_id: 7,
  name: '李四',
  relation: null,
  id_card: null,
  gender: null,
  birth_year: null,
  education: null,
  health_status: null,
  employment_status: null,
  income: null,
  is_special_support: true,
}

const OPEN_RECORD = {
  id: 10,
  household_id: 7,
  risk_type: 'income_drop',
  risk_level: 'high',
  reason: '收入骤减',
  detected_at: '2026-03-01',
  status: 'open',
  closed_at: null,
  closed_note: null,
}

const CLOSED_RECORD = {
  id: 11,
  household_id: 7,
  risk_type: 'illness',
  risk_level: 'medium',
  reason: null,
  detected_at: null,
  status: 'closed',
  closed_at: '2026-02-01',
  closed_note: '已落实医疗救助',
}

const VISIT = {
  id: 21,
  pairing_id: 3,
  visit_date: '2026-01-01',
  visitors: '王五',
  purpose: '走访慰问',
  content: null,
  materials: null,
}

const HOUSEHOLD = {
  id: 7,
  supported_village_id: 3,
  village_name: '甲村',
  household_code: 'H-7',
  household_name: '张三',
  address: '甲村7号',
  household_type: 'poverty',
  risk_type: 'illness',
  risk_level: 'high',
  helper_name: '赵六',
  helper_phone: '13800000000',
  annual_income: 12000.5,
  migrant_workers: 2,
  has_serious_illness: true,
  housing_safe: false,
  last_visit_date: '2026-01-01',
  monitoring_note: '需持续跟踪',
  member_count: 2,
  risk_alerts: ['连续未走访', '大病'],
  risk_records: [OPEN_RECORD, CLOSED_RECORD],
  visits: [VISIT],
  members: [MEMBER_A],
}

const MEMBER_ROWS = [MEMBER_A, MEMBER_B]

const elementStubs = {
  'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
  'el-button': {
    props: ['disabled', 'loading', 'type', 'size', 'link', 'plain'],
    emits: ['click'],
    template:
      '<button type="button" class="el-button-stub" :data-loading="String(loading)"' +
      ' @click="$emit(\'click\')"><slot /></button>',
  },
  'el-descriptions': {
    props: ['column', 'border'],
    template: '<div class="el-descriptions-stub"><slot /></div>',
  },
  'el-descriptions-item': {
    props: ['label', 'span'],
    template:
      '<div class="el-descriptions-item-stub" :data-label="label">{{ label }}<slot /></div>',
  },
  'el-tag': {
    props: ['type', 'size'],
    template: '<span class="el-tag-stub" :data-type="type"><slot /></span>',
  },
  'el-alert': {
    props: ['title', 'type', 'closable', 'showIcon'],
    template: '<div class="el-alert-stub" :data-title="title">warning alert</div>',
  },
  'el-timeline': { template: '<div class="el-timeline-stub"><slot /></div>' },
  'el-timeline-item': {
    props: ['timestamp', 'placement'],
    template: '<div class="el-timeline-item-stub" :data-ts="timestamp"><slot /></div>',
  },
  'el-table': { template: '<div class="el-table-stub"><slot /></div>' },
  'el-table-column': {
    props: ['label', 'prop', 'width', 'minWidth', 'fixed'],
    data() {
      return { rows: MEMBER_ROWS }
    },
    template:
      '<div class="el-table-column-stub" :data-label="label">' +
      '<div class="col-cell" v-for="(row, index) in rows" :key="index">{{ prop ? row[prop] : "-" }}<slot :row="row" /></div></div>',
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
    props: ['label', 'required'],
    template: '<div class="el-form-item-stub" :data-label="label"><slot /></div>',
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
  'el-select': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<div class="el-select-stub">' +
      '<button type="button" class="select-emit" @click="$emit(\'update:modelValue\', \'男\')">x</button>' +
      '<slot /></div>',
  },
  'el-option': {
    props: ['label', 'value'],
    template: '<span class="el-option-stub" :data-value="String(value)">{{ label }}</span>',
  },
}

function mountComp() {
  return mount(Detail, { global: { stubs: { ...elementStubs } } })
}

function vmOf(wrapper: ReturnType<typeof mountComp>) {
  return wrapper.vm as any
}

describe('households/Detail.vue（一户一档详情）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getHousehold.mockResolvedValue(HOUSEHOLD)
    mocks.getHouseholdMembers.mockResolvedValue(MEMBER_ROWS)
    mocks.createHouseholdMember.mockResolvedValue({ id: 3 })
    mocks.updateHouseholdMember.mockResolvedValue({ id: 1 })
    mocks.deleteHouseholdMember.mockResolvedValue({ id: 1 })
    mocks.createHouseholdRiskRecord.mockResolvedValue({ id: 12 })
    mocks.closeHouseholdRiskRecord.mockResolvedValue({ id: 10 })
    mocks.confirm.mockResolvedValue(undefined)
    mocks.prompt.mockResolvedValue({ value: '已走访并落实帮扶' })
  })

  it('加载：初始 loading → 详情 + 成员端点，渲染档案头/指标/预警/风险/成员/走访', async () => {
    const wrapper = mountComp()
    await flushPromises()

    expect(mocks.getHousehold).toHaveBeenCalledWith(7)
    expect(mocks.getHouseholdMembers).toHaveBeenCalledWith(7)
    const vm = vmOf(wrapper)
    expect(vm.household.id).toBe(7)
    expect(vm.members).toEqual(MEMBER_ROWS)
    expect(vm.riskRecords).toHaveLength(2)
    expect(vm.visits).toHaveLength(1)

    expect(wrapper.text()).toContain('张三')
    expect(wrapper.text()).toContain('H-7')
    expect(wrapper.text()).toContain('甲村')
    expect(wrapper.text()).toContain('脱贫户')
    expect(wrapper.text()).toContain('高')
    expect(wrapper.text()).toContain('12000.50')
    expect(wrapper.text()).toContain('是')
    expect(wrapper.text()).toContain('否')
    expect(wrapper.text()).toContain('需持续跟踪')
    expect(wrapper.findAll('.el-alert-stub').map((el) => el.attributes('data-title'))).toEqual([
      '连续未走访',
      '大病',
    ])
    expect(wrapper.text()).toContain('已落实医疗救助')
    expect(vm.visits[0].purpose).toBe('走访慰问')
    expect(wrapper.findAll('.visit-table .col-cell').length).toBeGreaterThan(0)
    // 成员表两行
    expect(wrapper.findAll('.el-table-column-stub[data-label="姓名"] .col-cell')).toHaveLength(2)

    // W2 UI v2：list-page + 左主右辅布局 + 卡片/统计卡/数字列
    expect(wrapper.find('.household-detail-page').classes()).toContain('list-page')
    expect(wrapper.find('.detail-layout').exists()).toBe(true)
    expect(wrapper.find('.detail-main').exists()).toBe(true)
    expect(wrapper.find('.detail-side').exists()).toBe(true)
    expect(wrapper.findAll('.app-card')).toHaveLength(5)
    expect(wrapper.findAll('.app-stat-card')).toHaveLength(4)
    expect(wrapper.findAll('.stat-value').map((el) => el.text())).toEqual([
      '12000.50',
      '2',
      '是',
      '否',
    ])
    expect(wrapper.findAll('.stat-trend').map((el) => el.text())).toEqual([
      '年度',
      '当前',
      '需关注',
      '需改造',
    ])
    expect(wrapper.findAll('.num-cell')).toHaveLength(8)
    expect(wrapper.findAll('.app-empty')).toHaveLength(0)
    wrapper.unmount()
  })

  it('详情缺字段：数组缺省为空，页面显示三件套空态与占位符', async () => {
    mocks.getHousehold.mockResolvedValue({
      ...HOUSEHOLD,
      household_code: null,
      village_name: null,
      helper_name: null,
      address: null,
      monitoring_note: null,
      migrant_workers: null,
      has_serious_illness: false,
      housing_safe: true,
      risk_alerts: undefined,
      risk_records: undefined,
      visits: undefined,
      members: undefined,
    })
    mocks.getHouseholdMembers.mockResolvedValue([])
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)
    expect(vm.riskAlerts).toEqual([])
    expect(vm.riskRecords).toEqual([])
    expect(vm.visits).toEqual([])
    expect(vm.members).toEqual([])
    expect(wrapper.text()).toContain('暂无预警命中')
    expect(wrapper.text()).toContain('暂无风险记录')
    expect(wrapper.text()).toContain('暂无家庭成员')
    expect(wrapper.text()).toContain('暂无走访记录')
    expect(wrapper.findAll('.app-empty')).toHaveLength(4)
    // 空值占位符与务工人数 0 兜底
    expect(wrapper.text()).toContain('—')
    expect(wrapper.text()).toContain('务工人数')
    // 统计卡另一侧分支：无大病 / 住房安全
    expect(wrapper.findAll('.stat-value').map((el) => el.text())).toEqual([
      '12000.50',
      '0',
      '否',
      '是',
    ])
    expect(wrapper.findAll('.stat-trend').map((el) => el.text())).toEqual([
      '年度',
      '当前',
      '无',
      '安全',
    ])

    // 加载中骨架分支
    vm.household = null
    vm.loading = true
    await nextTick()
    expect(wrapper.find('.app-loading').text()).toContain('档案加载中')
    // household 为空时统计卡兜底（?. 空分支）
    expect(vm.statCards.map((card: any) => card.value)).toEqual(['—', 0, '否', '否'])
    wrapper.unmount()
  })

  it('成员接口异常 / 非数组响应：保留详情内成员或置空，不阻断页面', async () => {
    mocks.getHouseholdMembers.mockRejectedValueOnce(new Error('net'))
    let wrapper = mountComp()
    await flushPromises()
    expect(vmOf(wrapper).members).toEqual([MEMBER_A])
    wrapper.unmount()

    mocks.getHouseholdMembers.mockResolvedValueOnce(null)
    wrapper = mountComp()
    await flushPromises()
    expect(vmOf(wrapper).members).toEqual([])
    wrapper.unmount()

    // ok_list envelope → items
    mocks.getHouseholdMembers.mockResolvedValueOnce({ items: [MEMBER_B] })
    wrapper = mountComp()
    await flushPromises()
    expect(vmOf(wrapper).members).toEqual([MEMBER_B])
    wrapper.unmount()
  })

  it('加载失败 → 错误态三件套，重试成功后恢复', async () => {
    mocks.getHousehold.mockRejectedValueOnce(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.find('.app-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('档案加载失败，请稍后重试')
    expect(vmOf(wrapper).household).toBeNull()

    await wrapper.find('.btn-retry').trigger('click')
    await flushPromises()
    expect(vmOf(wrapper).household.id).toBe(7)
    expect(wrapper.find('.app-error').exists()).toBe(false)
    wrapper.unmount()
  })

  it('返回列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const back = wrapper.find('.back-btn')
    expect(back.exists()).toBe(true)
    await back.trigger('click')
    expect(mocks.pushSafe).toHaveBeenCalledWith('/households')
    wrapper.unmount()
  })

  it('家庭成员：新增校验/成功/失败/删除（确认、取消、失败）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    await wrapper.find('.btn-add-member').trigger('click')
    expect(vm.memberVisible).toBe(true)
    expect(vm.editingMemberId).toBeNull()
    await wrapper.find('.btn-member-save').trigger('click')
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('请输入成员姓名')

    vm.memberForm.name = '王五'
    await wrapper.find('.btn-member-save').trigger('click')
    await flushPromises()
    expect(mocks.createHouseholdMember).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ name: '王五' })
    )
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('成员已新增')
    expect(vm.memberVisible).toBe(false)

    // 新增失败
    mocks.createHouseholdMember.mockRejectedValueOnce(new Error('x'))
    vm.memberForm.name = '王五'
    await vm.saveMember()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('新增成员失败')

    // 编辑：空值兜底回填（通过行内「编辑」按钮触发内联处理器）
    await wrapper.find('.btn-member-edit').trigger('click')
    expect(vm.memberForm.name).toBe('张三')
    vm.openEditMember(MEMBER_B)
    expect(vm.memberForm).toMatchObject({
      name: '李四',
      relation: '',
      id_card: '',
      gender: '',
      birth_year: undefined,
      income: undefined,
      is_special_support: true,
    })
    await vm.saveMember()
    expect(mocks.updateHouseholdMember).toHaveBeenCalledWith(7, 2, expect.any(Object))
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('成员已更新')

    // 更新失败
    mocks.updateHouseholdMember.mockRejectedValueOnce(new Error('x'))
    vm.openEditMember(MEMBER_A)
    await vm.saveMember()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('更新成员失败')

    // 删除：成功 / 取消 / 失败
    vm.openEditMember(MEMBER_A)
    await wrapper.find('.btn-member-delete').trigger('click')
    await flushPromises()
    expect(mocks.deleteHouseholdMember).toHaveBeenCalledWith(7, 1)
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('成员已删除')

    mocks.confirm.mockRejectedValueOnce('cancel')
    mocks.deleteHouseholdMember.mockClear()
    await wrapper.find('.btn-member-delete').trigger('click')
    await flushPromises()
    expect(mocks.deleteHouseholdMember).not.toHaveBeenCalled()

    mocks.deleteHouseholdMember.mockRejectedValueOnce(new Error('x'))
    await wrapper.find('.btn-member-delete').trigger('click')
    await flushPromises()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('删除成员失败')
    wrapper.unmount()
  })

  it('风险记录：登记成功/失败，关闭（成功/取消/失败），关闭说明为空', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    await wrapper.find('.btn-add-risk').trigger('click')
    expect(vm.riskVisible).toBe(true)
    vm.riskForm.risk_type = 'sudden'
    vm.riskForm.risk_level = 'high'
    vm.riskForm.reason = '突发困难'
    await wrapper.find('.btn-risk-save').trigger('click')
    await flushPromises()
    expect(mocks.createHouseholdRiskRecord).toHaveBeenCalledWith(7, {
      risk_type: 'sudden',
      risk_level: 'high',
      reason: '突发困难',
    })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('风险记录已登记')
    expect(vm.riskVisible).toBe(false)
    // 登记后刷新详情
    expect(mocks.getHousehold).toHaveBeenCalledTimes(2)

    // 登记失败 + 空原因分支
    mocks.createHouseholdRiskRecord.mockRejectedValueOnce(new Error('x'))
    vm.riskForm.reason = ''
    await vm.saveRiskRecord()
    expect(mocks.createHouseholdRiskRecord).toHaveBeenLastCalledWith(7, {
      risk_type: 'sudden',
      risk_level: 'high',
      reason: undefined,
    })
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('登记风险记录失败')

    // 关闭成功（行内「关闭处理」按钮触发内联处理器）
    await wrapper.find('.btn-close-risk').trigger('click')
    await flushPromises()
    expect(mocks.prompt).toHaveBeenCalled()
    expect(mocks.closeHouseholdRiskRecord).toHaveBeenCalledWith(10, {
      closed_note: '已走访并落实帮扶',
    })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('风险记录已关闭')

    // 关闭说明为空 → undefined
    mocks.prompt.mockResolvedValueOnce({ value: '' })
    await vm.closeRisk(OPEN_RECORD)
    expect(mocks.closeHouseholdRiskRecord).toHaveBeenLastCalledWith(10, { closed_note: undefined })

    // 取消关闭
    mocks.prompt.mockRejectedValueOnce('cancel')
    mocks.closeHouseholdRiskRecord.mockClear()
    await vm.closeRisk(OPEN_RECORD)
    expect(mocks.closeHouseholdRiskRecord).not.toHaveBeenCalled()

    // 关闭接口失败
    mocks.closeHouseholdRiskRecord.mockRejectedValueOnce(new Error('x'))
    await vm.closeRisk(OPEN_RECORD)
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('关闭风险记录失败')
    wrapper.unmount()
  })

  it('对话框 v-model 处理器全量可达', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    vm.openAddMember()
    await nextTick()
    await wrapper.find('.el-dialog-stub .member-name').setValue('赵六')
    await wrapper.find('.member-relation').setValue('配偶')
    await wrapper.find('.member-id-card').setValue('110101199001011234')
    await wrapper.find('.member-gender .select-emit').trigger('click')
    await wrapper.find('.member-birth').setValue('1992')
    await wrapper.find('.member-education').setValue('本科')
    await wrapper.find('.member-health .select-emit').trigger('click')
    await wrapper.find('.member-employment .select-emit').trigger('click')
    await wrapper.find('.member-income').setValue('5000')
    await wrapper.find('.member-support').trigger('click')
    expect(vm.memberForm).toMatchObject({
      name: '赵六',
      relation: '配偶',
      birth_year: 1992,
      income: 5000,
      is_special_support: true,
    })

    // 关闭成员对话框 / 取消按钮
    await wrapper.find('.el-dialog-stub .dialog-close').trigger('click')
    expect(vm.memberVisible).toBe(false)
    await wrapper.find('.btn-member-cancel').trigger('click')

    // 风险对话框字段
    vm.openRiskDialog()
    await nextTick()
    await wrapper.find('.risk-form-type .select-emit').trigger('click')
    await wrapper.find('.risk-form-level .select-emit').trigger('click')
    await wrapper.find('.risk-form-reason').setValue('原因')
    expect(vm.riskForm.reason).toBe('原因')
    await wrapper.find('[data-title="登记风险记录"] .dialog-close').trigger('click')
    expect(vm.riskVisible).toBe(false)
    await wrapper.find('.btn-risk-cancel').trigger('click')
    wrapper.unmount()
  })

  it('展示映射函数：类型/风险类型/等级/日期/金额/布尔/脱敏电话', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    expect(vm.householdTypeLabel('general')).toBe('一般户')
    expect(vm.householdTypeLabel('poverty')).toBe('脱贫户')
    expect(vm.householdTypeLabel('monitor')).toBe('监测户')
    expect(vm.householdTypeLabel('unknown')).toBe('unknown')
    expect(vm.householdTypeLabel(null)).toBe('—')
    expect(vm.typeTagType('poverty')).toBe('warning')
    expect(vm.typeTagType('monitor')).toBe('danger')
    expect(vm.typeTagType('general')).toBe('success')

    expect(vm.riskLevelLabel('low')).toBe('低')
    expect(vm.riskLevelLabel('medium')).toBe('中')
    expect(vm.riskLevelLabel('high')).toBe('高')
    expect(vm.riskLevelLabel('unknown')).toBe('unknown')
    expect(vm.riskLevelLabel(null)).toBe('—')
    expect(vm.riskTagType('high')).toBe('danger')
    expect(vm.riskTagType('medium')).toBe('warning')
    expect(vm.riskTagType('low')).toBe('info')

    expect(vm.riskTypeLabel('income_drop')).toBe('收入骤减')
    expect(vm.riskTypeLabel('sudden')).toBe('突发困难')
    expect(vm.riskTypeLabel('unknown')).toBe('unknown')
    expect(vm.riskTypeLabel(null)).toBe('—')

    expect(vm.formatDate('2026-01-01')).toBe('2026-01-01')
    expect(vm.formatDate(null)).toBe('—')
    expect(vm.formatMoney(12.5)).toBe('12.50')
    expect(vm.formatMoney(null)).toBe('—')
    expect(vm.formatMoney(undefined)).toBe('—')
    expect(vm.yesNo(true)).toBe('是')
    expect(vm.yesNo(false)).toBe('否')
    expect(vm.yesNo(undefined)).toBe('否')

    expect(vm.maskedPhone()).toBe('phone:13800000000')
    vm.household.helper_phone = null
    expect(vm.maskedPhone()).toBe('—')
    wrapper.unmount()
  })
})
