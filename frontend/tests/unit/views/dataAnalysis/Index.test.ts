/**
 * views/dataAnalysis/Index.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：loadAnalysisData 成功（overview/各表/yearly_comparison 有值）、完整率小数转百分数
 * （0/0.85/1/1.5 全分支）、缺省响应兜底、失败 logger、刷新按钮、
 * 模板渲染（统计卡/四 Tab/增长率正负/进度条/年度对比）、activeTab 与对比年份 v-model。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const { mockGet, logError } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  logError: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() },
}))

import DataAnalysisIndex from '@/views/dataAnalysis/Index.vue'

const analysisData = {
  overview: { total_villages: 12, total_investment: 350, completeness: 0.85, active_projects: 4 },
  investment_trend: [
    { year: 2024, military: 100, local: 50, total: 150, growth: 5 },
    { year: 2023, military: 80, local: 40, total: 120, growth: -2 },
  ],
  category_stats: [{ category: '产业', count: 3, investment: 60, beneficiaries: 200, ratio: 30 }],
  region_stats: [{ region: '黔南', villages: 5, investment: 100, avgIncome: 8000 }],
  yearly_comparison: {
    years: ['2023', '2024'],
    villages: { '2023': 10, '2024': 12 },
    investment: { '2023': 200, '2024': 300 },
    income: { '2023': 5000, '2024': 6000 },
  },
}

const rows = {
  rowA: { year: 2024, military: 100, local: 50, total: 150, growth: 5, category: '产业', count: 3, investment: 60, beneficiaries: 200, ratio: 30, region: '黔南', villages: 5, avgIncome: 8000 },
  rowB: { year: 2023, military: 80, local: 40, total: 120, growth: -3, category: '教育', count: 2, investment: 40, beneficiaries: 100, ratio: 20, region: '遵义', villages: 3, avgIncome: 6000 },
}

const stubs = {
  'el-button': {
    name: 'ElButton',
    props: ['disabled', 'loading'],
    template: '<button class="el-button-stub" :disabled="disabled"><slot /></button>',
  },
  'el-table-column': {
    name: 'ElTableColumn',
    props: ['prop'],
    template:
      '<div class="el-table-column-stub"><span>{{ rowA[prop] }}</span><span>{{ rowB[prop] }}</span><slot :row="rowA" /><slot :row="rowB" /></div>',
    data() {
      return { rowA: rows.rowA, rowB: rows.rowB }
    },
  },
  'el-select': {
    name: 'ElSelect',
    template: '<div class="el-select-stub"><slot /></div>',
    emits: ['update:modelValue', 'change'],
  },
  'el-tabs': {
    name: 'ElTabs',
    template: '<div class="el-tabs-stub"><slot /></div>',
    emits: ['update:modelValue', 'tab-change'],
  },
  'el-tab-pane': {
    name: 'ElTabPane',
    template: '<div class="el-tab-pane-stub"><slot /></div>',
  },
  'el-progress': {
    name: 'ElProgress',
    props: ['percentage'],
    template: '<div class="el-progress-stub">{{ percentage }}</div>',
  },
  'el-descriptions': {
    name: 'ElDescriptions',
    template: '<dl class="el-descriptions-stub"><slot /></dl>',
  },
  'el-descriptions-item': {
    name: 'ElDescriptionsItem',
    props: ['label'],
    template: '<div class="el-desc-item-stub">{{ label }}<slot /></div>',
  },
  'el-icon': { name: 'ElIcon', template: '<span class="el-icon-stub"><slot /></span>' },
}

function mountComp() {
  return mount(DataAnalysisIndex, {
    global: { renderStubDefaultSlot: true, stubs },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  mockGet.mockResolvedValue({ data: analysisData })
})

describe('挂载与加载', () => {
  it('onMounted 加载成功：统计卡、四个 Tab、增长率正负、年度对比渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGet).toHaveBeenCalledWith('/statistics/analysis')
    expect(vm.loading).toBe(false)
    expect(vm.overview).toMatchObject({ total_villages: 12, total_investment: 350, active_projects: 4 })
    expect(vm.overview.completeness).toBe(85) // 0.85 → 85
    expect(vm.investmentTrend).toHaveLength(2)
    expect(vm.categoryStats).toHaveLength(1)
    expect(vm.regionStats).toHaveLength(1)
    // 新结构：按年份映射取值（compareYearA 默认 currentYear-1=2025，mock 数据仅到 2024 → '-')
    expect(vm.yearlyComparison.years).toEqual(['2023', '2024'])
    expect(vm.comparisonA).toMatchObject({ villages: '-', investment: '-', income: '-' })
    expect(vm.comparisonB).toMatchObject({ villages: '-', investment: '-', income: '-' })
    const text = wrapper.text()
    expect(text).toContain('数据统计分析')
    expect(text).toContain('12')
    expect(text).toContain('350万')
    expect(text).toContain('85%')
    expect(text).toContain('4')
    expect(text).toContain('+5%') // growth 正
    expect(text).toContain('-3%') // growth 负
    expect(text).toContain('30') // 占比 progress
    expect(text).toContain('黔南')
    expect(text).toContain('8000')
    expect(text).toContain('2025年帮扶村总数') // compareYearA 默认
  })

  it('完整率转换全分支：0 跳过 / 0.85→85 / 1→100 / 1.5 跳过', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    mockGet.mockResolvedValueOnce({ data: { overview: { completeness: 0 } } })
    await vm.loadAnalysisData()
    expect(vm.overview.completeness).toBe(0)

    mockGet.mockResolvedValueOnce({ data: { overview: { completeness: 1 } } })
    await vm.loadAnalysisData()
    expect(vm.overview.completeness).toBe(100)

    mockGet.mockResolvedValueOnce({ data: { overview: { completeness: 1.5 } } })
    await vm.loadAnalysisData()
    expect(vm.overview.completeness).toBe(1.5) // >1 视为百分比原值
  })

  it('缺省响应：overview/各表/yearly_comparison 全部兜底', async () => {
    mockGet.mockResolvedValueOnce({ data: {} })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.overview).toMatchObject({ total_villages: 0, total_investment: 0, completeness: 0, active_projects: 0 })
    expect(vm.investmentTrend).toEqual([])
    expect(vm.categoryStats).toEqual([])
    expect(vm.regionStats).toEqual([])
    // 缺省响应：yearly_comparison 空结构兜底
    expect(vm.yearlyComparison.years).toEqual([])
    expect(vm.comparisonA.villages).toBe('-')
  })

  it('加载失败 → logger.error，loading 复位', async () => {
    mockGet.mockRejectedValueOnce(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('「刷新数据」按钮重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const before = mockGet.mock.calls.length
    await wrapper.find('.el-button-stub').trigger('click')
    await flushPromises()
    expect(mockGet.mock.calls.length).toBe(before + 1)
  })
})

describe('交互控件', () => {
  it('activeTab 与对比年份 v-model 同步', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    wrapper.findComponent({ name: 'ElTabs' }).vm.$emit('update:modelValue', 'category')
    expect(vm.activeTab).toBe('category')

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 2023)
    expect(vm.compareYearA).toBe(2023)
    selects[1].vm.$emit('update:modelValue', 2024)
    expect(vm.compareYearB).toBe(2024)
    await nextTick()
    const text = wrapper.text()
    expect(text).toContain('2023年帮扶村总数')
    expect(text).toContain('2024年总投入(万元)')
  })


  it('loadAnalysisData: res 无 data 时不崩溃(空对象兜底)', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockResolvedValue({})
    await vm.loadAnalysisData()
    expect(vm.overview).toBeTruthy()
    wrapper.unmount()
  })
})

describe('裸对象分支补充', () => {
  it('get 返回裸 overview 对象（无 data 包裹）', async () => {
    ;(mockGet as any).mockResolvedValueOnce({ overview: { completeness: 0.85, total_count: 10 } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.overview.total_count).toBe(10)
    expect(vm.overview.completeness).toBe(85)
    wrapper.unmount()
  })
})

describe('空响应分支', () => {
  it('get 返回 null → 空对象兜底', async () => {
    ;(mockGet as any).mockResolvedValueOnce(null)
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).overview).toBeTruthy()
    wrapper.unmount()
  })
})

describe('图表联动（v1.8.0）', () => {
  it('handleChartResize 调用 chart.resize（chart 存在）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const resize = vi.fn()
    vm.compareChart = { resize, dispose: vi.fn() }
    vm.handleChartResize()
    expect(resize).toHaveBeenCalled()
    wrapper.unmount() // 卸载时调用 dispose
  })

  it('年份切换 watch 触发图表渲染（chart 为空时静默不抛错）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.compareChart = null
    vm.compareYearA = 2020
    await nextTick()
    await flushPromises()
    expect(vm.compareYearA).toBe(2020)
  })

  it('renderCompareChart：ref 缺失早退；投资/收入缺年度数据 ?? 0 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 模板 ref 在实例上暴露为解包值：置 null → 早退（不创建新实例）
    vm.compareChartRef = null
    vm.compareChart = null
    vm.yearlyComparison = { years: ['2024', '2025'], villages: {}, investment: { '2024': 100 }, income: {} }
    vm.renderCompareChart()
    expect(vm.compareChart).toBeNull()
    // years 含缺失数据 → ?? 0 兜底（chart 存在时 setOption）
    const dispose = vi.fn()
    const setOption = vi.fn()
    const resize = vi.fn()
    vm.compareChart = { setOption, dispose, resize }
    vm.compareChartRef = {}
    vm.renderCompareChart()
    expect(setOption).toHaveBeenCalled()
  })

  it('yearly_comparison 归一化：years 非数组 → villages keys 兜底', async () => {
    mockGet.mockResolvedValueOnce({
      yearly_comparison: {
        villages: { '2023': 5 },
        investment: { '2023': 10 },
        income: { '2023': 1 },
      },
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.yearlyComparison.years).toEqual(['2023'])
    expect(vm.yearlyComparison.investment).toEqual({ '2023': 10 })
  })

  it('yearly_comparison 空对象 → years/villages/investment/income 全部 || 兜底', async () => {
    mockGet.mockResolvedValueOnce({ yearly_comparison: {} })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.yearlyComparison.years).toEqual([])
    expect(vm.yearlyComparison.villages).toEqual({})
    expect(vm.yearlyComparison.investment).toEqual({})
    expect(vm.yearlyComparison.income).toEqual({})
  })
})
