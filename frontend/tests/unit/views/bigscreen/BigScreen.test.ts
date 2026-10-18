/**
 * views/bigscreen/BigScreen.vue 单元测试（四指标 100%）
 *
 * 单执行者规程：BigScreen.vue 全仓只允许本文件执行（挂载 / bare import 均禁止出现在其他测试）。
 *
 * 覆盖：
 * - 挂载：filters + overview 加载、KPI/图表/负责人渲染、轮询只刷新 overview；
 * - 筛选：全部/帮扶村/帮扶学校/帮扶单位四类 scope 切换、对象下拉选择、重置、
 *   单位下拉覆盖统计、filters 失败仅保留「全部」、scope 持久化与恢复校验；
 * - 降级：overview 失败保留上次数据/零值、全部失败仅提示一次、404 回退全部、
 *   过期响应丢弃；
 * - 对象档案 / 帮扶明细渲染、金额脱敏、空数据占位；
 * - 设置抽屉（卡片显隐排序）、刷新频率、全屏、时钟、卸载清理。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const mocks = vi.hoisted(() => ({
  getBigScreenFilters: vi.fn(),
  getBigScreenOverview: vi.fn(),
  pushSafe: vi.fn(),
  ElMessage: { warning: vi.fn(), success: vi.fn(), error: vi.fn() },
}))

vi.mock('@/api/bigscreen', () => ({
  getBigScreenFilters: mocks.getBigScreenFilters,
  getBigScreenOverview: mocks.getBigScreenOverview,
}))

// W22 退出大屏：断言回到工作台
vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mocks.pushSafe }),
}))

vi.mock('element-plus', () => ({
  ElMessage: mocks.ElMessage,
}))

vi.mock('@/components/common/BaseChart.vue', () => ({
  default: { name: 'BaseChart', template: '<div class="chart-stub" />' },
}))

import BigScreen from '@/views/bigscreen/BigScreen.vue'
import {
  BIGSCREEN_CONFIG_KEY,
  defaultBigScreenConfig,
  type BigScreenConfig,
  type BigScreenScopeConfig,
} from '@/views/bigscreen/bigscreenConfig'

// ─────────────────────────────────────────────
// 后端契约样例数据
// ─────────────────────────────────────────────
const FILTERS = {
  villages: [
    { id: 1, name: '甲村', county: '示范县', support_unit: '单位甲' },
    { id: 2, name: '乙村', county: null, support_unit: null },
  ],
  schools: [
    { id: 11, name: '甲校', district: '示范区', support_unit: null },
    { id: 12, name: '乙校', district: null, support_unit: '单位乙' },
  ],
  units: [
    { name: '帮扶单位甲', village_count: 3, school_count: 2, project_count: 5, pairing_count: 4 },
    { name: '帮扶单位乙', village_count: 1, school_count: 0, project_count: 2, pairing_count: 1 },
  ],
}

const ALL_OVERVIEW = {
  scope: { type: 'all', id: null, name: '全部对象', subtitle: '' },
  kpis: [
    { key: 'villages', label: '帮扶村', value: 12, unit: '个' },
    { key: 'projects', label: '帮扶项目', value: 34, unit: '个' },
    { key: 'schools', label: '帮扶学校', value: 5, unit: '所' },
    { key: 'completion', label: '完成率', value: '88.6%', unit: '' },
    { key: 'funds', label: '经费总额', value: 1234000.567, unit: '万元' },
  ],
  fund_trend: [
    { year: 2024, planned: 100.456, actual: 80 },
    // 金额空值：displayMoney 的 null/undefined 兜底分支
    { year: 2025, planned: null, actual: undefined },
  ],
  project_status: [
    { key: 'completed', label: '已完成', value: 10 },
    // 空 label → 回退 key；计数 0 → Number(v) || 0 兜底
    { key: 'active', label: '', value: 0 },
  ],
  yearly: [
    { year: 2024, project_count: 5, fund_count: 5 },
    // project_count 缺失 → 回退 fund_count
    { year: 2025, fund_count: 8 },
  ],
  rankings: [
    { name: '甲村', score: 92 },
    { name: '乙村', score: 85 },
  ],
  leaders: [
    { name: '示范项目甲', person: '张三', unit: '单位甲' },
    // 缺项目名 → '—'；空负责人 → formatLeaderName 占位
    { name: '', person: '', unit: null },
  ],
  profile: null,
  details: null,
}

const SCOPED_OVERVIEW = {
  ...ALL_OVERVIEW,
  scope: { type: 'village', id: 1, name: '甲村', subtitle: '示范县 · 覆盖统计' },
  profile: {
    title: '甲村对象档案',
    sections: [
      {
        title: '基础信息',
        items: [
          { label: '所属县', value: '示范县' },
          // null 值 → 模板 '—' 兜底
          { label: '结对单位', value: null },
        ],
      },
      { title: '人口信息', items: [{ label: '户籍人口', value: '1200 人' }] },
    ],
    tags: [
      { label: '标签', items: ['示范村', '重点村'] },
      { label: '空标签组', items: [] },
    ],
  },
  details: {
    projects: [
      { name: '项目甲', status: 'completed', label: '已完成', amount: 100.456, person: '张三' },
      { name: '项目乙', status: 'active', label: '进行中', amount: 20, person: '李四' },
      { name: '项目丙', status: 'approved', label: '已审批', amount: 3.333, person: '王五' },
      { name: '项目丁', status: 'pending', label: '待审批', amount: 0, person: '赵六' },
      { name: '项目戊', status: 'active', label: '进行中', amount: 1.005, person: '钱七' },
      // 第 6 条用于验证 top5 截断
      { name: '项目己', status: 'completed', label: '已完成', amount: 9, person: '孙八' },
    ],
    funds: [
      { name: '经费甲', year: 2024, status: 'approved', label: '已审批', amount: 50.5 },
      { name: '经费乙', year: 2024, status: 'completed', label: '已完成', amount: 10 },
      { name: '经费丙', year: 2025, status: 'active', label: '进行中', amount: 2.25 },
      { name: '经费丁', year: 2025, status: 'pending', label: '待审批', amount: 1 },
      { name: '经费戊', year: 2026, status: 'active', label: '进行中', amount: 0.5 },
      { name: '经费己', year: 2026, status: 'completed', label: '已完成', amount: 8 },
    ],
    pairing: { total: 12, active: 8, visits: 30 },
  },
}

/** 按请求参数生成 overview 响应（scope 回显与请求一致） */
function overviewFor(params: any) {
  if (params.scope_type === 'all') return ALL_OVERVIEW
  return {
    ...SCOPED_OVERVIEW,
    scope: {
      type: params.scope_type,
      id: params.scope_id ?? null,
      name: params.scope_name ?? '帮扶对象',
      subtitle: '覆盖统计：3 个村 · 2 所学校',
    },
  }
}

// ─────────────────────────────────────────────
// Element Plus 局部桩（渲染插槽并主动 emit，保证内联处理器可达）
// ─────────────────────────────────────────────
const elementStubs = {
  'el-button': {
    props: ['disabled', 'size'],
    emits: ['click'],
    template:
      '<button type="button" class="el-button-stub" :data-disabled="String(disabled)"' +
      ' @click="$emit(\'click\')"><slot /></button>',
  },
  'el-drawer': {
    props: ['modelValue', 'title'],
    emits: ['update:modelValue'],
    template:
      '<div class="el-drawer-stub" :data-open="String(modelValue)" :data-title="title">' +
      '<button type="button" class="drawer-close" @click="$emit(\'update:modelValue\', false)">x</button>' +
      '<slot /></div>',
  },
  'el-switch': {
    props: { modelValue: Boolean },
    emits: ['update:modelValue', 'change'],
    template:
      '<button type="button" class="el-switch-stub" :data-on="String(modelValue)"' +
      " @click=\"$emit('update:modelValue', !modelValue); $emit('change', !modelValue)\" />",
  },
  'el-radio-group': {
    props: { modelValue: [String, Number] },
    emits: ['update:modelValue'],
    template:
      '<div class="el-radio-group-stub" :data-value="String(modelValue)">' +
      '<button type="button" class="radio-all" @click="$emit(\'update:modelValue\', \'all\')">all</button>' +
      '<button type="button" class="radio-village" @click="$emit(\'update:modelValue\', \'village\')">village</button>' +
      '<button type="button" class="radio-school" @click="$emit(\'update:modelValue\', \'school\')">school</button>' +
      '<button type="button" class="radio-unit" @click="$emit(\'update:modelValue\', \'unit\')">unit</button>' +
      '<button type="button" class="radio-60" @click="$emit(\'update:modelValue\', 60)">60</button>' +
      '<button type="button" class="radio-off" @click="$emit(\'update:modelValue\', 0)">off</button>' +
      '<slot /></div>',
  },
  'el-radio-button': {
    props: ['value'],
    template: '<span class="el-radio-button-stub"><slot /></span>',
  },
  'el-select': {
    props: { modelValue: String, filterable: Boolean, placeholder: String },
    emits: ['update:modelValue'],
    template:
      '<div class="el-select-stub" :data-value="String(modelValue)" :data-filterable="String(filterable)">' +
      '<button type="button" class="select-village-1" @click="$emit(\'update:modelValue\', \'village:1\')">v1</button>' +
      '<button type="button" class="select-village-2" @click="$emit(\'update:modelValue\', \'village:2\')">v2</button>' +
      '<button type="button" class="select-school-11" @click="$emit(\'update:modelValue\', \'school:11\')">s11</button>' +
      '<button type="button" class="select-unit" @click="$emit(\'update:modelValue\', \'unit:帮扶单位甲\')">u1</button>' +
      '<button type="button" class="select-unit-2" @click="$emit(\'update:modelValue\', \'unit:帮扶单位乙\')">u2</button>' +
      '<button type="button" class="select-unknown" @click="$emit(\'update:modelValue\', \'unknown:0\')">x</button>' +
      '<slot /></div>',
  },
  'el-option': {
    props: ['label', 'value'],
    template: '<span class="el-option-stub" :data-value="String(value)">{{ label }}</span>',
  },
  'el-tag': {
    props: ['size'],
    template: '<span class="el-tag-stub"><slot /></span>',
  },
}

function mountComp() {
  return mount(BigScreen, {
    attachTo: document.body,
    global: { stubs: { ...elementStubs } },
  })
}

type AnyWrapper = ReturnType<typeof mountComp>

function vmOf(wrapper: AnyWrapper) {
  return wrapper.vm as any
}

function findButton(wrapper: AnyWrapper, text: string) {
  return wrapper.findAll('.el-button-stub').find((button) => button.text().includes(text))
}

function lastOverviewParams() {
  const calls = mocks.getBigScreenOverview.mock.calls
  return calls[calls.length - 1][0]
}

/** 写入此前持久化的配置（用于验证恢复/失效回退） */
function seedScope(scope: BigScreenScopeConfig) {
  const config: BigScreenConfig = { ...defaultBigScreenConfig(), scope }
  localStorage.setItem(BIGSCREEN_CONFIG_KEY, JSON.stringify(config))
}

function savedConfig() {
  return JSON.parse(localStorage.getItem(BIGSCREEN_CONFIG_KEY) as string)
}

function createDeferred<T = any>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: any) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('BigScreen.vue（帮扶成效大屏）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    localStorage.clear()
    mocks.getBigScreenFilters.mockResolvedValue(FILTERS)
    mocks.getBigScreenOverview.mockImplementation((params: any) =>
      Promise.resolve(overviewFor(params))
    )
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  // ─────────────────────────────────────────────
  // 挂载与全局数据
  // ─────────────────────────────────────────────
  it('挂载加载 filters + overview，渲染 KPI/图表/负责人/页脚', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    expect(mocks.getBigScreenFilters).toHaveBeenCalledTimes(1)
    expect(mocks.getBigScreenOverview).toHaveBeenCalledTimes(1)
    expect(lastOverviewParams()).toEqual({ scope_type: 'all', years: 5 })

    expect(wrapper.text()).toContain('帮扶成效总览大屏')
    expect(vm.kpis).toHaveLength(5)
    expect(vm.kpis[1].value).toBe(34)
    expect(vm.kpis[3]).toEqual({ key: 'completion', label: '完成率', unit: '', value: '88.6%' })
    // KPI 直接渲染后端 5 项：labels 含单位，无单位项不出现括号
    expect(wrapper.text()).toContain('帮扶村（个）')
    expect(wrapper.text()).toContain('经费总额（万元）')
    expect(wrapper.text()).toContain('完成率')

    // 全部对象：5 张卡片（4 图表 + 负责人），对象档案/明细不渲染
    expect(wrapper.findAll('.chart-card')).toHaveLength(5)
    expect(wrapper.findAll('.chart-stub')).toHaveLength(4)
    expect(vm.visibleCards.map((card: any) => card.key)).toEqual([
      'fundTrend',
      'rank',
      'projectStatus',
      'yearly',
      'leaders',
    ])
    expect(wrapper.findAll('.leader-item')).toHaveLength(2)
    expect(wrapper.findAll('.leader-person')[0].text()).toBe('张三')
    expect(wrapper.findAll('.leader-person')[1].text()).toBe('—')
    // 无 scope 副标题（后端 subtitle 空）
    expect(wrapper.find('.scope-subtitle').exists()).toBe(false)
    expect(wrapper.text()).toContain('数据每 30 秒自动刷新')
    wrapper.unmount()
  })

  it('图表 computed 使用 overview 数据（含兜底分支）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    expect(vm.fundTrendOption.xAxis.data).toEqual([2024, 2025])
    // 非脱敏保留 2 位小数；null/undefined → 0
    expect(vm.fundTrendOption.series[0].data).toEqual([100.46, 0])
    expect(vm.fundTrendOption.series[1].data).toEqual([80, 0])
    expect(vm.rankOption.yAxis.data).toEqual(['甲村', '乙村'])
    expect(vm.rankOption.series[0].data).toEqual([92, 85])
    // 空 label → 回退 key；value 0 → 0
    expect(vm.projectStatusOption.series[0].data).toEqual([
      { name: '已完成', value: 10 },
      { name: 'active', value: 0 },
    ])
    expect(vm.yearlyOption.xAxis.data).toEqual([2024, 2025])
    // project_count 缺失 → fund_count 兜底
    expect(vm.yearlyOption.series[0].data).toEqual([5, 8])
    wrapper.unmount()
  })

  it('overview 未加载时各 computed 走空结构兜底（零值 KPI）', async () => {
    mocks.getBigScreenOverview.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    expect(vm.kpis.map((kpi: any) => kpi.value)).toEqual([0, 0, 0, '—', 0])
    expect(vm.fundTrendOption.series[0].data).toEqual([])
    expect(vm.rankOption.yAxis.data).toEqual([])
    expect(vm.projectStatusOption.series[0].data).toEqual([])
    expect(vm.yearlyOption.series[0].data).toEqual([])
    expect(vm.leaderRows).toEqual([])
    expect(vm.profileData).toBeNull()
    expect(vm.detailsData).toBeNull()
    expect(vm.scopeSubtitle).toBe('')
    expect(vm.detailsProjects).toEqual([])
    expect(vm.detailsFunds).toEqual([])
    expect(vm.pairingStats).toEqual({ total: 0, active: 0, visits: 0 })
    wrapper.unmount()
  })

  it('overview 返回 null / kpis 为空数组 → KPI 兜底、档案与明细为 null', async () => {
    mocks.getBigScreenOverview.mockResolvedValueOnce(null)
    let wrapper = mountComp()
    await flushPromises()
    let vm = vmOf(wrapper)
    expect(vm.overview).toBeNull()
    expect(vm.kpis).toHaveLength(5)
    expect(vm.profileData).toBeNull()
    expect(vm.detailsData).toBeNull()
    wrapper.unmount()

    // overview 对象存在但 kpis 空数组 + profile/details 字段缺失
    mocks.getBigScreenOverview.mockResolvedValueOnce({
      ...ALL_OVERVIEW,
      kpis: [],
      profile: undefined,
      details: undefined,
    })
    wrapper = mountComp()
    await flushPromises()
    vm = vmOf(wrapper)
    expect(vm.overview).not.toBeNull()
    expect(vm.kpis.map((kpi: any) => kpi.value)).toEqual([0, 0, 0, '—', 0])
    expect(vm.profileData).toBeNull()
    expect(vm.detailsData).toBeNull()
    wrapper.unmount()
  })

  // ─────────────────────────────────────────────
  // scope 切换
  // ─────────────────────────────────────────────
  it('切换到帮扶村：自动选中首个村、按 id 请求、渲染对象档案与帮扶明细', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()
    const vm = vmOf(wrapper)

    // filters 只加载一次
    expect(mocks.getBigScreenFilters).toHaveBeenCalledTimes(1)
    expect(vm.config.scope).toEqual({ type: 'village', id: 1, name: '甲村' })
    expect(lastOverviewParams()).toEqual({ scope_type: 'village', scope_id: 1, years: 5 })
    expect(savedConfig().scope).toEqual({ type: 'village', id: 1, name: '甲村' })

    // 对象下拉：可搜索、选中值、村名（县缺失时只显示村名）
    const select = wrapper.find('.scope-object-select')
    expect(select.exists()).toBe(true)
    expect(select.attributes('data-filterable')).toBe('true')
    expect(select.attributes('data-value')).toBe('village:1')
    const optionTexts = wrapper.findAll('.el-option-stub').map((option) => option.text())
    expect(optionTexts).toContain('甲村（示范县）')
    expect(optionTexts).toContain('乙村')

    // 对象档案卡
    expect(wrapper.findAll('.chart-card')).toHaveLength(7)
    expect(wrapper.find('.profile-title').text()).toBe('甲村对象档案')
    expect(wrapper.findAll('.profile-section')).toHaveLength(2)
    expect(wrapper.text()).toContain('户籍人口')
    expect(wrapper.text()).toContain('1200 人')
    // null 字段值 → '—'
    expect(wrapper.findAll('.profile-item-value')[1].text()).toBe('—')
    expect(wrapper.findAll('.profile-tag').map((tag) => tag.text())).toEqual(['示范村', '重点村'])
    // scope 副标题（后端 scope 回显）
    expect(wrapper.find('.scope-subtitle').text()).toBe('覆盖统计：3 个村 · 2 所学校')

    // 帮扶明细卡：两张 Top5 表 + 结对统计
    expect(wrapper.findAll('.detail-table')).toHaveLength(2)
    expect(wrapper.findAll('.detail-row')).toHaveLength(10)
    expect(wrapper.text()).toContain('项目甲')
    expect(wrapper.text()).not.toContain('项目己') // Top5 截断
    expect(wrapper.text()).toContain('经费甲')
    expect(wrapper.text()).not.toContain('经费己')
    expect(wrapper.findAll('.pairing-value').map((item) => item.text())).toEqual(['12', '8', '30'])
    expect(wrapper.text()).toContain('结对数')
    expect(wrapper.text()).toContain('进行中')
    expect(wrapper.text()).toContain('走访次数')
    wrapper.unmount()
  })

  it('切换到帮扶学校：自动选中首个学校并按 school id 请求', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.scope-type-group .radio-school').trigger('click')
    await flushPromises()
    const vm = vmOf(wrapper)

    expect(vm.config.scope).toEqual({ type: 'school', id: 11, name: '甲校' })
    expect(lastOverviewParams()).toEqual({ scope_type: 'school', scope_id: 11, years: 5 })
    expect(wrapper.find('.scope-object-select').attributes('data-value')).toBe('school:11')
    const optionTexts = wrapper.findAll('.el-option-stub').map((option) => option.text())
    expect(optionTexts).toContain('甲校（示范区）')
    expect(optionTexts).toContain('乙校')
    wrapper.unmount()
  })

  it('切换到帮扶单位：按 name 请求，下拉文案含村/校/项目覆盖统计', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.scope-type-group .radio-unit').trigger('click')
    await flushPromises()
    const vm = vmOf(wrapper)

    expect(vm.config.scope).toEqual({ type: 'unit', id: null, name: '帮扶单位甲' })
    expect(lastOverviewParams()).toEqual({ scope_type: 'unit', scope_name: '帮扶单位甲', years: 5 })
    expect(wrapper.find('.scope-object-select').attributes('data-value')).toBe('unit:帮扶单位甲')
    const optionTexts = wrapper.findAll('.el-option-stub').map((option) => option.text())
    expect(optionTexts[0]).toBe('帮扶单位甲（村3·校2·项目5）')
    expect(optionTexts[1]).toBe('帮扶单位乙（村1·校0·项目2）')
    wrapper.unmount()
  })

  it('对象下拉切换：换村/换单位后重新请求 overview', async () => {
    const wrapper = mountComp()
    await flushPromises()

    await wrapper.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()
    const before = mocks.getBigScreenOverview.mock.calls.length
    await wrapper.find('.scope-object-select .select-village-2').trigger('click')
    await flushPromises()
    expect(mocks.getBigScreenOverview.mock.calls.length).toBe(before + 1)
    expect(vmOf(wrapper).config.scope).toEqual({ type: 'village', id: 2, name: '乙村' })
    expect(lastOverviewParams()).toEqual({ scope_type: 'village', scope_id: 2, years: 5 })
    expect(wrapper.find('.scope-object-select').attributes('data-value')).toBe('village:2')

    await wrapper.find('.scope-type-group .radio-unit').trigger('click')
    await flushPromises()
    await wrapper.find('.scope-object-select .select-unit-2').trigger('click')
    await flushPromises()
    expect(vmOf(wrapper).config.scope).toEqual({ type: 'unit', id: null, name: '帮扶单位乙' })
    expect(lastOverviewParams()).toEqual({ scope_type: 'unit', scope_name: '帮扶单位乙', years: 5 })
    wrapper.unmount()
  })

  it('切回全部：对象下拉隐藏、对象档案/明细卡片隐藏，请求 scope_type=all', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()
    expect(wrapper.find('.scope-object-select').exists()).toBe(true)

    await wrapper.find('.scope-type-group .radio-all').trigger('click')
    await flushPromises()
    const vm = vmOf(wrapper)
    expect(vm.config.scope).toEqual({ type: 'all', id: null, name: null })
    expect(wrapper.find('.scope-object-select').exists()).toBe(false)
    expect(vm.visibleCards.map((card: any) => card.key)).not.toContain('profile')
    expect(vm.visibleCards.map((card: any) => card.key)).not.toContain('details')
    expect(lastOverviewParams()).toEqual({ scope_type: 'all', years: 5 })
    wrapper.unmount()
  })

  it('重置按钮：从具体对象回到全部视图', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)
    // 全部视图下「重置」禁用
    expect(findButton(wrapper, '重置')!.attributes('data-disabled')).toBe('true')

    await wrapper.find('.scope-type-group .radio-school').trigger('click')
    await flushPromises()
    expect(vm.config.scope.type).toBe('school')
    expect(findButton(wrapper, '重置')!.attributes('data-disabled')).toBe('false')

    await findButton(wrapper, '重置')!.trigger('click')
    await flushPromises()
    expect(vm.config.scope).toEqual({ type: 'all', id: null, name: null })
    expect(lastOverviewParams()).toEqual({ scope_type: 'all', years: 5 })
    wrapper.unmount()
  })

  it('切换到的类型无对象 → 回退全部并提示一次', async () => {
    mocks.getBigScreenFilters.mockResolvedValue({ ...FILTERS, villages: [] })
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()
    const vm = vmOf(wrapper)

    expect(vm.config.scope).toEqual({ type: 'all', id: null, name: null })
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('暂无可选对象，已恢复「全部」视图')
    expect(lastOverviewParams()).toEqual({ scope_type: 'all', years: 5 })
    wrapper.unmount()
  })

  it('对象下拉收到未知值 → 忽略，不发请求', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()
    const before = mocks.getBigScreenOverview.mock.calls.length
    await wrapper.find('.scope-object-select .select-unknown').trigger('click')
    await flushPromises()
    expect(mocks.getBigScreenOverview.mock.calls.length).toBe(before)
    expect(vmOf(wrapper).config.scope).toEqual({ type: 'village', id: 1, name: '甲村' })
    wrapper.unmount()
  })

  // ─────────────────────────────────────────────
  // 降级
  // ─────────────────────────────────────────────
  it('filters 加载失败：仅保留「全部」、warning 一次、overview 仍按全部加载', async () => {
    mocks.getBigScreenFilters.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    expect(vm.filtersFailed).toBe(true)
    expect(vm.scopeTypeOptions).toEqual([{ value: 'all', label: '全部' }])
    expect(wrapper.findAll('.scope-type-group .el-radio-button-stub')).toHaveLength(1)
    expect(wrapper.find('.scope-type-group').text()).toContain('全部')
    expect(wrapper.find('.scope-object-select').exists()).toBe(false)
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('筛选对象加载失败，仅保留「全部」视图')
    expect(lastOverviewParams()).toEqual({ scope_type: 'all', years: 5 })

    // 轮询 overview 不再重复提示
    vi.advanceTimersByTime(30000)
    await flushPromises()
    expect(mocks.ElMessage.warning).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('filters 返回畸形载荷 → 各列表按空数组兜底', async () => {
    mocks.getBigScreenFilters.mockResolvedValue({ villages: 'bad', schools: null })
    let wrapper = mountComp()
    await flushPromises()
    let vm = vmOf(wrapper)

    expect(vm.filters).toEqual({ villages: [], schools: [], units: [] })
    // filters 成功但对象为空：切换到帮扶村同样回退全部
    await wrapper.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()
    expect(vm.config.scope.type).toBe('all')
    wrapper.unmount()

    // filters 接口 resolve null（后端异常空体）→ 同样按空数组兜底
    mocks.getBigScreenFilters.mockResolvedValueOnce(null)
    wrapper = mountComp()
    await flushPromises()
    vm = vmOf(wrapper)
    expect(vm.filters).toEqual({ villages: [], schools: [], units: [] })
    expect(vm.filtersFailed).toBe(false)
    wrapper.unmount()
  })

  it('恢复的 scope 校验失败（对象已删除）→ 回退全部并提示', async () => {
    seedScope({ type: 'school', id: 999, name: '已删学校' })
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    expect(vm.config.scope).toEqual({ type: 'all', id: null, name: null })
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('所选对象不存在，已恢复「全部」视图')
    // 校验发生在 filters 之后、overview 之前：唯一一次 overview 就是全部对象
    expect(mocks.getBigScreenOverview).toHaveBeenCalledTimes(1)
    expect(lastOverviewParams()).toEqual({ scope_type: 'all', years: 5 })
    wrapper.unmount()
  })

  it('恢复的 scope 有效（村/校/单位）→ 保留并直接按该对象加载', async () => {
    // 帮扶村
    seedScope({ type: 'village', id: 1, name: '甲村' })
    let wrapper = mountComp()
    await flushPromises()
    expect(vmOf(wrapper).config.scope).toEqual({ type: 'village', id: 1, name: '甲村' })
    expect(lastOverviewParams()).toEqual({ scope_type: 'village', scope_id: 1, years: 5 })
    expect(wrapper.find('.scope-object-select').attributes('data-value')).toBe('village:1')
    wrapper.unmount()

    // 帮扶学校
    seedScope({ type: 'school', id: 12, name: '乙校' })
    wrapper = mountComp()
    await flushPromises()
    expect(vmOf(wrapper).config.scope).toEqual({ type: 'school', id: 12, name: '乙校' })
    expect(lastOverviewParams()).toEqual({ scope_type: 'school', scope_id: 12, years: 5 })
    wrapper.unmount()

    // 帮扶单位
    seedScope({ type: 'unit', id: null, name: '帮扶单位甲' })
    wrapper = mountComp()
    await flushPromises()
    expect(vmOf(wrapper).config.scope).toEqual({ type: 'unit', id: null, name: '帮扶单位甲' })
    expect(lastOverviewParams()).toEqual({ scope_type: 'unit', scope_name: '帮扶单位甲', years: 5 })
    wrapper.unmount()
  })

  it('恢复的 scope 单位名已失效 → 回退全部并提示', async () => {
    seedScope({ type: 'unit', id: null, name: '不存在的单位' })
    const wrapper = mountComp()
    await flushPromises()
    expect(vmOf(wrapper).config.scope).toEqual({ type: 'all', id: null, name: null })
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('所选对象不存在，已恢复「全部」视图')
    wrapper.unmount()
  })

  it('filters 失败且存在恢复的 scope → 无法校验，回退全部并分别提示', async () => {
    seedScope({ type: 'village', id: 1, name: '甲村' })
    mocks.getBigScreenFilters.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    expect(vm.config.scope).toEqual({ type: 'all', id: null, name: null })
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('筛选对象加载失败，仅保留「全部」视图')
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('所选对象不存在，已恢复「全部」视图')
    wrapper.unmount()
  })

  it('overview 全部对象失败：零值降级 + 仅提示一次', async () => {
    mocks.getBigScreenOverview.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    expect(vm.kpis.map((kpi: any) => kpi.value)).toEqual([0, 0, 0, '—', 0])
    expect(wrapper.findAll('.kpi-item')).toHaveLength(5)
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('大屏数据加载失败，请检查服务连接')
    // 轮询再失败不重复提示
    vi.advanceTimersByTime(30000)
    await flushPromises()
    expect(mocks.ElMessage.warning).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('具体对象 overview 失败（非 404）：静默保留上次数据，不提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)
    const allScope = vm.overview.scope

    mocks.getBigScreenOverview.mockRejectedValue(new Error('net'))
    await wrapper.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()

    expect(vm.config.scope.type).toBe('village')
    // 保留上一次（全部）数据，不白屏、不弹出提示
    expect(vm.overview.scope).toEqual(allScope)
    expect(mocks.ElMessage.warning).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('具体对象 overview 404：回退全部并重新加载，仅提示一次', async () => {
    const wrapper = mountComp()
    await flushPromises()
    mocks.getBigScreenOverview.mockImplementation((params: any) => {
      if (params.scope_type === 'village') {
        return Promise.reject({ response: { status: 404 } })
      }
      return Promise.resolve(overviewFor(params))
    })

    await wrapper.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()
    const vm = vmOf(wrapper)
    expect(vm.config.scope).toEqual({ type: 'all', id: null, name: null })
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith(
      '所选对象不存在或无权查看，已恢复「全部」视图'
    )
    expect(lastOverviewParams()).toEqual({ scope_type: 'all', years: 5 })
    expect(wrapper.find('.scope-object-select').exists()).toBe(false)

    // 再次触发 404：warning 已去重，不再提示
    await wrapper.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()
    expect(mocks.ElMessage.warning).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('404 判定：错误 null / 无 response 均按普通失败处理', async () => {
    const wrapper = mountComp()
    await flushPromises()
    // 具体对象 + 错误对象无 response.status → 静默降级（不误判 404）
    mocks.getBigScreenOverview.mockRejectedValueOnce(null)
    await wrapper.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()
    expect(vmOf(wrapper).config.scope.type).toBe('village')
    expect(mocks.ElMessage.warning).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('过期响应丢弃：旧 scope 的成功/失败响应都不覆盖当前数据', async () => {
    // 第一次 overview（全部）挂起，后续立即返回
    const deferredSuccess = createDeferred()
    let callIndex = 0
    mocks.getBigScreenOverview.mockImplementation((params: any) => {
      callIndex += 1
      if (callIndex === 1) return deferredSuccess.promise
      return Promise.resolve(overviewFor(params))
    })
    const wrapper = mountComp()
    await flushPromises()
    expect(mocks.getBigScreenOverview).toHaveBeenCalledTimes(1)

    await wrapper.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()
    expect(vmOf(wrapper).config.scope.type).toBe('village')

    // 旧「全部」响应迟到 → 丢弃
    deferredSuccess.resolve(ALL_OVERVIEW)
    await flushPromises()
    expect(vmOf(wrapper).overview.scope.type).toBe('village')
    wrapper.unmount()

    // 旧响应失败迟到 → 同样丢弃（不触发 404 回退 / 不提示）
    const deferredError = createDeferred()
    callIndex = 0
    mocks.getBigScreenOverview.mockImplementation((params: any) => {
      callIndex += 1
      if (callIndex === 1) return deferredError.promise
      return Promise.resolve(overviewFor(params))
    })
    const wrapper2 = mountComp()
    await flushPromises()
    await wrapper2.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()
    deferredError.reject({ response: { status: 404 } })
    await flushPromises()
    expect(vmOf(wrapper2).config.scope.type).toBe('village')
    expect(mocks.ElMessage.warning).not.toHaveBeenCalled()
    wrapper2.unmount()
  })

  // ─────────────────────────────────────────────
  // 对象档案 / 帮扶明细
  // ─────────────────────────────────────────────
  it('对象档案/明细为空（scoped 但后端返回 null）→ 空态占位', async () => {
    mocks.getBigScreenOverview.mockImplementation((params: any) =>
      Promise.resolve(
        params.scope_type === 'all'
          ? ALL_OVERVIEW
          : { ...ALL_OVERVIEW, scope: { ...SCOPED_OVERVIEW.scope }, profile: null, details: null }
      )
    )
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()

    const emptyTexts = wrapper.findAll('.detail-empty').map((item) => item.text())
    expect(emptyTexts).toEqual(['暂无对象档案数据', '暂无帮扶明细数据'])
    const vm = vmOf(wrapper)
    expect(vm.detailsProjects).toEqual([])
    expect(vm.detailsFunds).toEqual([])
    expect(vm.pairingStats).toEqual({ total: 0, active: 0, visits: 0 })
    wrapper.unmount()
  })

  it('明细字段缺失/空值 → label→status→— 兜底，pairing 零值', async () => {
    mocks.getBigScreenOverview.mockImplementation((params: any) =>
      Promise.resolve({
        ...ALL_OVERVIEW,
        scope: { ...SCOPED_OVERVIEW.scope },
        profile: SCOPED_OVERVIEW.profile,
        details:
          params.scope_type === 'all'
            ? null
            : {
                projects: [
                  { name: '项目X', status: 'approved', label: null, amount: null, person: null },
                  { name: '项目Y', status: null, label: null, amount: undefined, person: '' },
                ],
                funds: [
                  { name: '经费X', year: 2024, status: 'pending', label: undefined, amount: null },
                  // label/status 全缺 → '—' 兜底
                  { name: '经费Y', year: 2025, status: null, label: null, amount: 6 },
                ],
                pairing: null,
              },
      })
    )
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()
    const vm = vmOf(wrapper)

    expect(vm.detailsProjects).toEqual([
      { name: '项目X', statusText: 'approved', amountText: 0, person: '—' },
      { name: '项目Y', statusText: '—', amountText: 0, person: '—' },
    ])
    expect(vm.detailsFunds).toEqual([
      { name: '经费X', year: 2024, statusText: 'pending', amountText: 0 },
      { name: '经费Y', year: 2025, statusText: '—', amountText: 6 },
    ])
    expect(vm.pairingStats).toEqual({ total: 0, active: 0, visits: 0 })
    // 表格照常渲染（无 Top5 数据也不算异常）
    expect(wrapper.findAll('.detail-row')).toHaveLength(4)
    wrapper.unmount()
  })

  it('汇报脱敏：KPI/明细金额隐藏小数精度、负责人姓名打码', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()
    const vm = vmOf(wrapper)

    // 非脱敏：KPI 原样透传；明细金额保留 2 位小数，负责人原样
    expect(vm.kpis[4].value).toBe(1234000.567)
    expect(vm.detailsProjects[0].amountText).toBe(100.46)
    expect(vm.detailsFunds[0].amountText).toBe(50.5)
    expect(vm.detailsProjects[0].person).toBe('张三')
    expect(wrapper.findAll('.leader-person')[0].text()).toBe('张三')

    const switches = wrapper.findAll('.el-switch-stub')
    await switches[switches.length - 1].trigger('click')
    await flushPromises()

    expect(vm.config.desensitized).toBe(true)
    expect(savedConfig().desensitized).toBe(true)
    // 数值型 KPI 隐藏小数精度；字符串型 KPI 原样
    expect(vm.kpis[4].value).toBe(1234001)
    expect(vm.kpis[3].value).toBe('88.6%')
    expect(vm.detailsProjects[0].amountText).toBe(100)
    expect(vm.detailsFunds[0].amountText).toBe(51)
    expect(vm.detailsProjects[0].person).toBe('张*')
    expect(wrapper.findAll('.leader-person')[0].text()).toBe('张*')
    expect(wrapper.text()).toContain('汇报脱敏模式')
    wrapper.unmount()

    // 重新挂载后脱敏配置保持
    const remount = mountComp()
    await flushPromises()
    await remount.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()
    expect(vmOf(remount).config.desensitized).toBe(true)
    expect(remount.findAll('.leader-person')[0].text()).toBe('张*')
    remount.unmount()
  })

  it('明细数组顶层与金额兜底：null/undefined 值 → 0', async () => {
    mocks.getBigScreenOverview.mockImplementation((params: any) =>
      Promise.resolve(
        params.scope_type === 'all'
          ? ALL_OVERVIEW
          : {
              ...ALL_OVERVIEW,
              scope: { ...SCOPED_OVERVIEW.scope },
              profile: null,
              details: { projects: undefined, funds: undefined, pairing: undefined },
            }
      )
    )
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.scope-type-group .radio-village').trigger('click')
    await flushPromises()
    const vm = vmOf(wrapper)

    expect(vm.detailsProjects).toEqual([])
    expect(vm.detailsFunds).toEqual([])
    expect(vm.pairingStats).toEqual({ total: 0, active: 0, visits: 0 })
    wrapper.unmount()
  })

  // ─────────────────────────────────────────────
  // 配置抽屉 / 刷新频率 / 全屏 / 时钟
  // ─────────────────────────────────────────────
  it('设置抽屉：打开关闭、7 张卡片显隐、排序与持久化', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    await findButton(wrapper, '设置')!.trigger('click')
    expect(vm.settingsVisible).toBe(true)
    expect(wrapper.find('.el-drawer-stub').attributes('data-open')).toBe('true')
    expect(wrapper.find('.el-drawer-stub').attributes('data-title')).toBe('大屏设置')

    // 7 张卡片 + 1 个脱敏开关
    expect(wrapper.findAll('.el-switch-stub')).toHaveLength(8)

    // 隐藏「经费执行趋势」→ 图表少一张、配置写回 localStorage
    await wrapper.findAll('.el-switch-stub')[0].trigger('click')
    await flushPromises()
    expect(vm.config.cards[0].visible).toBe(false)
    expect(vm.visibleCards.map((card: any) => card.key)).not.toContain('fundTrend')
    expect(wrapper.findAll('.chart-stub')).toHaveLength(3)
    expect(savedConfig().cards[0].visible).toBe(false)

    // 再次点击恢复显示
    await wrapper.findAll('.el-switch-stub')[0].trigger('click')
    await flushPromises()
    expect(vm.config.cards[0].visible).toBe(true)
    expect(vm.visibleCards.map((card: any) => card.key)).toContain('fundTrend')

    // 下移第一张卡片 → 顺序交换并持久化
    let rows = wrapper.findAll('.settings-card-row')
    await rows[0].findAll('.el-button-stub')[1].trigger('click')
    await flushPromises()
    expect(vm.config.cards.map((card: any) => card.key).slice(0, 2)).toEqual(['rank', 'fundTrend'])
    expect(
      savedConfig()
        .cards.map((card: any) => card.key)
        .slice(0, 2)
    ).toEqual(['rank', 'fundTrend'])

    // 再上移回第一位
    rows = wrapper.findAll('.settings-card-row')
    await rows[1].findAll('.el-button-stub')[0].trigger('click')
    await flushPromises()
    expect(vm.config.cards[0].key).toBe('fundTrend')

    // 首行上移 / 末行下移的越界守卫 + 禁用态
    rows = wrapper.findAll('.settings-card-row')
    await rows[0].findAll('.el-button-stub')[0].trigger('click')
    await rows[rows.length - 1].findAll('.el-button-stub')[1].trigger('click')
    expect(vm.config.cards[0].key).toBe('fundTrend')
    expect(rows[0].findAll('.el-button-stub')[0].attributes('data-disabled')).toBe('true')
    expect(rows[rows.length - 1].findAll('.el-button-stub')[1].attributes('data-disabled')).toBe(
      'true'
    )

    // 关闭抽屉
    await wrapper.find('.drawer-close').trigger('click')
    expect(vm.settingsVisible).toBe(false)
    wrapper.unmount()
  })

  it('刷新频率：默认 30s 只轮询 overview；切 60s / 关闭自动刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const overviewCalls = () => mocks.getBigScreenOverview.mock.calls.length

    expect(document.body.textContent).toContain('数据每 30 秒自动刷新')
    const initial = overviewCalls()
    vi.advanceTimersByTime(30000)
    await flushPromises()
    expect(overviewCalls()).toBe(initial + 1)
    // 自动刷新不重复拉 filters
    expect(mocks.getBigScreenFilters).toHaveBeenCalledTimes(1)

    // 切到 60 秒：重建定时器
    await wrapper.find('.settings-refresh .radio-60').trigger('click')
    await flushPromises()
    expect(vmOf(wrapper).config.refreshInterval).toBe(60)
    expect(savedConfig().refreshInterval).toBe(60)
    const afterSwitch = overviewCalls()
    vi.advanceTimersByTime(30000)
    await flushPromises()
    expect(overviewCalls()).toBe(afterSwitch)
    vi.advanceTimersByTime(30000)
    await flushPromises()
    expect(overviewCalls()).toBe(afterSwitch + 1)

    // 关闭自动刷新：推进 5 分钟也不应产生轮询
    await wrapper.find('.settings-refresh .radio-off').trigger('click')
    await flushPromises()
    expect(vmOf(wrapper).config.refreshInterval).toBe(0)
    expect(wrapper.text()).toContain('自动刷新已关闭')
    const offCount = overviewCalls()
    vi.advanceTimersByTime(300000)
    await flushPromises()
    expect(overviewCalls()).toBe(offCount)
    wrapper.unmount()
  })

  it('恢复默认：卡片全显示、30s、非脱敏、scope 回全部并重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)
    await wrapper.find('.scope-type-group .radio-unit').trigger('click')
    await flushPromises()
    await wrapper.find('.settings-refresh .radio-off').trigger('click')
    await wrapper.findAll('.el-switch-stub')[0].trigger('click')
    const lastSwitch = wrapper.findAll('.el-switch-stub')
    await lastSwitch[lastSwitch.length - 1].trigger('click')
    await flushPromises()
    expect(vm.config.refreshInterval).toBe(0)
    expect(vm.config.desensitized).toBe(true)
    expect(vm.config.scope.type).toBe('unit')

    await findButton(wrapper, '恢复默认')!.trigger('click')
    await flushPromises()
    expect(vm.config.refreshInterval).toBe(30)
    expect(vm.config.desensitized).toBe(false)
    expect(vm.config.cards.every((card: any) => card.visible)).toBe(true)
    expect(vm.config.scope).toEqual({ type: 'all', id: null, name: null })
    expect(lastOverviewParams()).toEqual({ scope_type: 'all', years: 5 })

    // 恢复 30s 轮询
    const before = mocks.getBigScreenOverview.mock.calls.length
    vi.advanceTimersByTime(30000)
    await flushPromises()
    expect(mocks.getBigScreenOverview.mock.calls.length).toBe(before + 1)
    wrapper.unmount()
  })

  it('全屏切换与 fullscreenchange 监听', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)
    const origReq = document.documentElement.requestFullscreen
    const origExit = document.exitFullscreen
    ;(document.documentElement as any).requestFullscreen = vi.fn(() => Promise.resolve())
    ;(document as any).exitFullscreen = vi.fn(() => Promise.resolve())
    Object.defineProperty(document, 'fullscreenElement', {
      value: null,
      configurable: true,
      writable: true,
    })

    vm.toggleFullscreen()
    expect(vm.isFullscreen).toBe(true)
    expect(document.documentElement.requestFullscreen).toHaveBeenCalled()
    ;(document as any).fullscreenElement = document.documentElement
    document.dispatchEvent(new Event('fullscreenchange'))
    await nextTick()
    expect(vm.isFullscreen).toBe(true)

    vm.toggleFullscreen()
    expect(vm.isFullscreen).toBe(false)
    expect((document as any).exitFullscreen).toHaveBeenCalled()
    ;(document as any).fullscreenElement = null
    document.dispatchEvent(new Event('fullscreenchange'))
    await nextTick()
    expect(vm.isFullscreen).toBe(false)
    ;(document.documentElement as any).requestFullscreen = origReq
    ;(document as any).exitFullscreen = origExit
    wrapper.unmount()
  })

  it('时钟每秒更新、卸载时清理定时器', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)
    expect(vm.clock).toMatch(/^\d{4}-\d{2}-\d{2}/)
    vi.advanceTimersByTime(1000)
    expect(vm.clock).toMatch(/^\d{4}-\d{2}-\d{2}/)
    wrapper.unmount()
    // 卸载后推进时钟/轮询不应报错
    vi.advanceTimersByTime(120000)
    expect(vi.getTimerCount()).toBe(0)
  })

  // ─────────────────────────────────────────────
  // 防御分支（归一化保证正常流程不会走到，但保留兜底）
  // ─────────────────────────────────────────────
  it('参数组装/选中值/告警去重的防御分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    // overview 参数：村/校用 id、单位用 name、全部只带类型
    expect(vm.buildOverviewParams({ type: 'village', id: 3, name: '甲村' })).toEqual({
      scope_type: 'village',
      scope_id: 3,
      years: 5,
    })
    expect(vm.buildOverviewParams({ type: 'school', id: 4, name: '甲校' })).toEqual({
      scope_type: 'school',
      scope_id: 4,
      years: 5,
    })
    expect(vm.buildOverviewParams({ type: 'unit', id: null, name: '帮扶单位甲' })).toEqual({
      scope_type: 'unit',
      scope_name: '帮扶单位甲',
      years: 5,
    })
    expect(vm.buildOverviewParams({ type: 'all', id: null, name: null })).toEqual({
      scope_type: 'all',
      years: 5,
    })
    // 缺 id/name 的异常 scope 不传递空参数
    expect(vm.buildOverviewParams({ type: 'village', id: null, name: null })).toEqual({
      scope_type: 'village',
      years: 5,
    })
    expect(vm.buildOverviewParams({ type: 'unit', id: null, name: null })).toEqual({
      scope_type: 'unit',
      years: 5,
    })

    // 下拉选中值：类型/定位字段缺失时回退空串
    vm.config.scope = { type: 'village', id: null, name: null }
    await nextTick()
    expect(vm.scopeSelection).toBe('')
    vm.config.scope = { type: 'unit', id: null, name: null }
    await nextTick()
    expect(vm.scopeSelection).toBe('')
    vm.config.scope = { type: 'all', id: null, name: null }
    await nextTick()
    expect(vm.scopeSelection).toBe('')

    // 全部视图下收到对象选择事件：早退不发请求
    const before = mocks.getBigScreenOverview.mock.calls.length
    vm.onScopeObjectChange('village:1')
    expect(mocks.getBigScreenOverview.mock.calls.length).toBe(before)

    // 非法 scope 类型 → 归一化回全部并刷新
    vm.onScopeTypeChange('bad')
    await flushPromises()
    expect(vm.config.scope.type).toBe('all')

    // 同一类告警只提示一次
    const warnCount = mocks.ElMessage.warning.mock.calls.length
    vm.warnOnce('filters', '重复告警')
    vm.warnOnce('filters', '重复告警')
    expect(mocks.ElMessage.warning).toHaveBeenCalledTimes(warnCount + 1)
    wrapper.unmount()
  })

  it('对象下拉选项 computed：按类型组装，非法类型返回空数组', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)

    vm.config.scope = { type: 'village', id: null, name: null }
    await nextTick()
    expect(vm.scopeObjectOptions.map((option: any) => option.value)).toEqual([
      'village:1',
      'village:2',
    ])
    expect(vm.scopeObjectOptions[1].label).toBe('乙村')

    vm.config.scope = { type: 'school', id: null, name: null }
    await nextTick()
    expect(vm.scopeObjectOptions.map((option: any) => option.value)).toEqual([
      'school:11',
      'school:12',
    ])
    expect(vm.scopeObjectOptions[1].label).toBe('乙校')

    vm.config.scope = { type: 'unit', id: null, name: null }
    await nextTick()
    expect(vm.scopeObjectOptions.map((option: any) => option.value)).toEqual([
      'unit:帮扶单位甲',
      'unit:帮扶单位乙',
    ])

    vm.config.scope = { type: 'all', id: null, name: null }
    await nextTick()
    expect(vm.scopeObjectOptions).toEqual([])
    wrapper.unmount()
  })
})

// ─────────────────────────────────────────────
// W22：退出大屏（退出全屏 + 返回工作台）
// ─────────────────────────────────────────────
describe('W22 退出大屏', () => {
  it('非全屏时直接返回工作台', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      get: () => null,
    })
    const exitSpy = vi.fn(() => Promise.resolve())
    ;(document as any).exitFullscreen = exitSpy

    vm.exitBigScreen()
    expect(mocks.pushSafe).toHaveBeenCalledWith('/dashboard')
    expect(exitSpy).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('全屏时先退出全屏再返回工作台；退出失败静默不阻断跳转', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = vmOf(wrapper)
    vm.isFullscreen = true
    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      get: () => document.documentElement,
    })
    const exitSpy = vi.fn(() => Promise.reject(new Error('exit failed')))
    ;(document as any).exitFullscreen = exitSpy

    vm.exitBigScreen()
    await flushPromises()
    expect(exitSpy).toHaveBeenCalled()
    expect(vm.isFullscreen).toBe(false)
    expect(mocks.pushSafe).toHaveBeenCalledWith('/dashboard')

    Object.defineProperty(document, 'fullscreenElement', {
      configurable: true,
      get: () => null,
    })
    wrapper.unmount()
  })

  it('头部「退出大屏」按钮触发退出逻辑', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper
      .findAll('button.el-button-stub')
      .find((b: any) => b.text().trim() === '退出大屏')
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    expect(mocks.pushSafe).toHaveBeenCalledWith('/dashboard')
    wrapper.unmount()
  })
})
