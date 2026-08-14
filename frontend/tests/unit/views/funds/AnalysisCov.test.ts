/**
 * views/funds/Analysis.vue 覆盖率攻坚
 * 覆盖：onMounted 四路加载、summary/饼图/柱状图/年度趋势/利用率趋势 computed 全分支、
 * 维度切换、查询（yearlyChartRef 有/无）、导出 CSV、表格样本行（金额可选链、
 * 利用率三档 status）、趋势图 v-if/v-else 两侧渲染。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂会被提升到模块顶部注册，直接引用下方 const 会触发 TDZ；
// 所有被工厂引用的对象放入 vi.hoisted 中先行初始化。
const {
  ElMessage,
  logError,
  fundsState,
  apiMultiDimension,
  apiYearlyComparison,
  exportCsvMock,
  refreshMock,
} = vi.hoisted(() => {
  return {
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
    logError: vi.fn(),
    fundsState: { totalFunds: 1000, usedFunds: 600, fetchFunds: vi.fn() },
    apiMultiDimension: vi.fn(),
    apiYearlyComparison: vi.fn(),
    exportCsvMock: vi.fn(),
    refreshMock: vi.fn(),
  }
})

vi.mock('element-plus', () => ({
  ElMessage,
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/stores/funds', () => ({
  useFundsStore: () => fundsState,
}))

vi.mock('@/api/funds', () => ({
  fundApi: { statisticsMultiDimension: apiMultiDimension },
}))

vi.mock('@/api/fundStatistics', () => ({
  getYearlyFundComparison: apiYearlyComparison,
}))

vi.mock('@/utils/exportUtil', () => ({
  exportUtil: { exportToCSV: exportCsvMock },
}))

vi.mock('@/components/common/BaseChart.vue', () => ({
  default: {
    name: 'BaseChart',
    template: '<div class="base-chart-stub" />',
    props: ['option', 'height'],
  },
}))

vi.mock('@/components/funds/YearlyComparisonChart.vue', () => ({
  default: {
    name: 'YearlyComparisonChart',
    template: '<div class="yearly-chart-stub" />',
    props: ['yearStart', 'yearEnd', 'department'],
    setup: () => ({ refresh: refreshMock }),
  },
}))

import Analysis from '@/views/funds/Analysis.vue'

const dimRows = [
  {
    label: '2023年',
    count: 5,
    total_amount: 1234.5,
    total_allocated: 1000,
    total_used: 800,
    utilization_rate: 95,
  },
  {
    label: '2024年',
    count: 2,
    total_amount: 600,
    total_allocated: 500,
    total_used: 300,
    utilization_rate: 60,
  },
]

const trendRows = [
  { year: 2023, total_actual: 100, utilization_rate: 80 },
  {
    year: 2024,
    total_actual: null,
    total_military: 30,
    total_local: 20,
    utilization_rate: undefined,
  },
]

function mountComp() {
  // setup.ts 的全局 el-* stub 默认不渲染插槽，需 renderStubDefaultSlot；
  // 具名插槽（header）与作用域插槽（表格行）需自定义 stub。
  return mount(Analysis, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
        },
        // 注入三行样本数据，覆盖金额可选链两侧与利用率 success/warning/exception 三档
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>',
          data() {
            return {
              rowA: {
                label: '2023年',
                count: 5,
                total_amount: 1234.5,
                total_allocated: 1000.25,
                total_used: 800.5,
                utilization_rate: 95,
              },
              rowB: {
                label: '2024年',
                count: 2,
                total_allocated: 500,
                total_used: 100,
                utilization_rate: 65,
              },
              rowC: {
                label: '2025年',
                count: 1,
                total_amount: 200,
                total_allocated: 150,
                total_used: 50,
                utilization_rate: 40,
              },
            }
          },
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  fundsState.totalFunds = 1000
  fundsState.usedFunds = 600
  apiMultiDimension.mockResolvedValue({ success: true, data: [...dimRows] })
  apiYearlyComparison.mockResolvedValue({ success: true, data: [...trendRows] })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与初始加载', () => {
  it('onMounted：拉取经费列表与两路统计，成功分支写入数据', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(fundsState.fetchFunds).toHaveBeenCalled()
    expect(apiMultiDimension).toHaveBeenCalledWith(
      expect.objectContaining({
        group_by: 'period',
        period_type: 'yearly',
        start_date: `${vm.filterForm.yearStart}-01-01`,
        end_date: `${vm.filterForm.yearEnd}-12-31`,
      })
    )
    expect(vm.dimensionData).toHaveLength(2)
    expect(vm.yearlyTrend).toHaveLength(2)
  })

  it('summary：正常使用率、total 为 0、非数字兜底三分支', async () => {
    // fundsStore 为普通对象（非响应式），computed 不追踪其变化，需重新挂载生效
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.summary).toEqual({ total: 1000, used: 600, remain: 400, rate: 60 })
    fundsState.totalFunds = 0
    fundsState.usedFunds = 0
    const wrapper2 = mountComp()
    await flushPromises()
    expect((wrapper2.vm as any).summary.rate).toBe(0)
    expect((wrapper2.vm as any).summary.remain).toBe(0)
    fundsState.totalFunds = 'abc'
    fundsState.usedFunds = undefined
    const wrapper3 = mountComp()
    await flushPromises()
    expect((wrapper3.vm as any).summary).toEqual({ total: 0, used: 0, remain: 0, rate: 0 })
  })
})

describe('图表 computed', () => {
  it('pieChartOption：数据映射、空数据兜底与 color 函数', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const opt = vm.pieChartOption
    expect(opt.series[0].data).toEqual([
      { value: 1234.5, name: '2023年' },
      { value: 600, name: '2024年' },
    ])
    const colorFn = opt.series[0].itemStyle.color
    expect(colorFn({ dataIndex: 0 })).toBe('#40916c')
    expect(colorFn({ dataIndex: 8 })).toBe('#40916c')
    // 空数据与字段兜底
    vm.dimensionData = [{ count: 1 }]
    const opt2 = vm.pieChartOption
    expect(opt2.series[0].data).toEqual([{ value: 0, name: '未知' }])
    vm.dimensionData = []
    const opt3 = vm.pieChartOption
    expect(opt3.series[0].data).toEqual([{ value: 0, name: '无数据' }])
    // dimensionData 为 null → || [] 兜底
    vm.dimensionData = null
    expect(vm.pieChartOption.series[0].data).toEqual([{ value: 0, name: '无数据' }])
  })

  it('barChartOption：数据映射、空数据兜底与 color 三档', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const opt = vm.barChartOption
    expect(opt.yAxis.data).toEqual(['2023年', '2024年'])
    expect(opt.series[0].data).toEqual([95, 60])
    const colorFn = opt.series[0].itemStyle.color
    expect(colorFn({ value: 95 })).toBe('#67c23a')
    expect(colorFn({ value: 70 })).toBe('#e6a23c')
    expect(colorFn({ value: 30 })).toBe('#f56c6c')
    vm.dimensionData = [{ total_amount: 10 }]
    const opt2 = vm.barChartOption
    expect(opt2.yAxis.data).toEqual(['未知'])
    expect(opt2.series[0].data).toEqual([0])
    vm.dimensionData = []
    const opt3 = vm.barChartOption
    expect(opt3.yAxis.data).toEqual(['无数据'])
    expect(opt3.series[0].data).toEqual([0])
    // dimensionData 为 null → || [] 兜底
    vm.dimensionData = null
    expect(vm.barChartOption.yAxis.data).toEqual(['无数据'])
  })

  it('yearlyTrendAreaOption：null 与 total_actual/军地合计/全缺三形态', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const opt = vm.yearlyTrendAreaOption
    expect(opt.xAxis.data).toEqual(['2023年', '2024年'])
    expect(opt.series[0].data).toEqual([100, 50])
    vm.yearlyTrend = [{ year: 2025 }]
    expect(vm.yearlyTrendAreaOption.series[0].data).toEqual([0])
    vm.yearlyTrend = []
    expect(vm.yearlyTrendAreaOption).toBeNull()
  })

  it('utilizationTrendOption：null 与利用率缺失兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const opt = vm.utilizationTrendOption
    expect(opt.xAxis.data).toEqual(['2023年', '2024年'])
    expect(opt.series[0].data).toEqual([80, 0])
    vm.yearlyTrend = []
    expect(vm.utilizationTrendOption).toBeNull()
  })
})

describe('数据加载分支', () => {
  it('loadDimensionStats：非 period 维度不带 period_type；data 缺省置空；res 为空不变；异常提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 非 period 维度
    vm.dimension = 'type'
    apiMultiDimension.mockClear()
    apiMultiDimension.mockResolvedValueOnce({ success: true, data: null })
    await vm.loadDimensionStats()
    expect(apiMultiDimension).toHaveBeenCalledWith(
      expect.not.objectContaining({ period_type: expect.anything() })
    )
    expect(vm.dimensionData).toEqual([])
    // res 为空 → 不更新
    vm.dimensionData = [{ label: '保留' }]
    apiMultiDimension.mockResolvedValueOnce(null)
    await vm.loadDimensionStats()
    expect(vm.dimensionData).toEqual([{ label: '保留' }])
    // 异常 → 日志 + 内联错误态（不再弹全局提示）
    apiMultiDimension.mockRejectedValueOnce(new Error('net'))
    await vm.loadDimensionStats()
    expect(logError).toHaveBeenCalled()
    expect(vm.loadError.dimension).toBe('net')
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('loadYearlyTrend：data 缺省置空；res 为空不变；异常提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    apiYearlyComparison.mockResolvedValueOnce({ success: true, data: null })
    await vm.loadYearlyTrend()
    expect(vm.yearlyTrend).toEqual([])
    vm.yearlyTrend = [{ year: 2020 }]
    apiYearlyComparison.mockResolvedValueOnce(null)
    await vm.loadYearlyTrend()
    expect(vm.yearlyTrend).toEqual([{ year: 2020 }])
    apiYearlyComparison.mockRejectedValueOnce(new Error('net'))
    await vm.loadYearlyTrend()
    expect(vm.loadError.trend).toBe('net')
    expect(ElMessage.error).not.toHaveBeenCalled()
  })
})

describe('维度切换与查询', () => {
  it('el-radio-group 切换维度：v-model 更新 + 清空旧数据并重载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.dimensionData.length).toBeGreaterThan(0)
    const group = wrapper.findComponent({ name: 'ElRadioGroup' })
    apiMultiDimension.mockClear()
    group.vm.$emit('update:modelValue', 'source')
    expect(vm.dimension).toBe('source')
    group.vm.$emit('change', 'source')
    await flushPromises()
    expect(apiMultiDimension).toHaveBeenCalledWith(expect.objectContaining({ group_by: 'source' }))
    // 时间粒度 select 仅 period 维度显示
    expect(wrapper.findAllComponents({ name: 'ElSelect' })).toHaveLength(2)
    group.vm.$emit('update:modelValue', 'period')
    await nextTick()
    expect(wrapper.findAllComponents({ name: 'ElSelect' })).toHaveLength(3)
  })

  it('handleDimensionChange 直接调用：清空并重载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    apiMultiDimension.mockClear()
    vm.handleDimensionChange()
    expect(vm.dimensionData).toEqual([])
    await flushPromises()
    expect(apiMultiDimension).toHaveBeenCalled()
  })

  it('handleSearch：两路重载 + yearlyChartRef 有/无两侧；查询按钮点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    apiMultiDimension.mockClear()
    apiYearlyComparison.mockClear()
    const btn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('查询'))
    await btn!.trigger('click')
    await flushPromises()
    expect(apiMultiDimension).toHaveBeenCalled()
    expect(apiYearlyComparison).toHaveBeenCalled()
    expect(refreshMock).toHaveBeenCalled()
    // ref 为空 → 可选链跳过
    vm.yearlyChartRef = null
    refreshMock.mockClear()
    vm.handleSearch()
    await flushPromises()
    expect(refreshMock).not.toHaveBeenCalled()
  })

  it('筛选 select 的 v-model 与 change 处理器', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(selects).toHaveLength(3)
    apiMultiDimension.mockClear()
    selects[0].vm.$emit('update:modelValue', 'quarterly')
    expect(vm.filterForm.periodType).toBe('quarterly')
    selects[0].vm.$emit('change', 'quarterly')
    await flushPromises()
    expect(apiMultiDimension).toHaveBeenCalledWith(
      expect.objectContaining({ period_type: 'quarterly' })
    )
    selects[1].vm.$emit('update:modelValue', 2020)
    expect(vm.filterForm.yearStart).toBe(2020)
    selects[2].vm.$emit('update:modelValue', 2024)
    expect(vm.filterForm.yearEnd).toBe(2024)
  })
})

describe('导出统计', () => {
  it('无数据 → 警告；有数据 → exportToCSV 带列映射（按钮点击）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.dimensionData = []
    vm.handleExportStats()
    expect(ElMessage.warning).toHaveBeenCalledWith('没有可导出的数据')
    expect(exportCsvMock).not.toHaveBeenCalled()
    vm.dimensionData = [...dimRows]
    const btn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('导出统计'))
    await btn!.trigger('click')
    expect(exportCsvMock).toHaveBeenCalledWith(dimRows, '经费统计分析', {
      label: '分组',
      count: '记录数',
      total_amount: '总金额(万元)',
      total_allocated: '已拨付(万元)',
      total_used: '已使用(万元)',
      utilization_rate: '利用率(%)',
    })
  })
})

describe('模板渲染', () => {
  it('表格样本行：金额格式化/可选链空值与利用率三档 status', async () => {
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.text()).toContain('1,234.50')
    expect(wrapper.text()).toContain('1,000.25')
    // 利用率 progress：95 success、65 warning、40 exception
    const progresses = wrapper.findAllComponents({ name: 'ElProgress' })
    expect(progresses.length).toBeGreaterThanOrEqual(3)
    const statuses = progresses.map((p) => p.attributes('status'))
    expect(statuses).toContain('success')
    expect(statuses).toContain('warning')
    expect(statuses).toContain('exception')
  })

  it('趋势图 v-if/v-else：有数据渲染 BaseChart，无数据渲染 el-empty', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 默认加载有趋势数据 → 两个趋势 BaseChart + 两个常驻图表
    expect(wrapper.findAll('.base-chart-stub')).toHaveLength(4)
    expect(wrapper.find('.chart-card el-empty-stub').exists()).toBe(false)
    vm.yearlyTrend = []
    await nextTick()
    const empties = wrapper.findAll('el-empty-stub')
    expect(empties.length).toBe(2)
    expect(wrapper.findAll('.base-chart-stub')).toHaveLength(2)
  })

  it('汇总卡与年份选项渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(wrapper.text()).toContain('1000')
    expect(wrapper.text()).toContain('600')
    expect(wrapper.text()).toContain('400')
    expect(wrapper.text()).toContain('60%')
    expect(vm.yearOptions[0]).toBe(2000)
    expect(wrapper.find('.yearly-chart-stub').exists()).toBe(true)
  })
})

describe('内联错误态与防御分支收尾', () => {
  it('统计明细：loadError.dimension 且 !hasDimensionData → el-empty 描述 + 重新加载按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.dimensionData = []
    vm.loadError.dimension = '维度加载失败'
    await nextTick()
    // v-else-if 区域渲染 el-empty（description 透传）
    const empties = wrapper.findAll('el-empty-stub')
    expect(empties.some((e) => e.attributes('description') === '维度加载失败')).toBe(true)
    // header 的「重新加载」按钮（v-if 真侧）→ 点击触发 loadDimensionStats
    const reloadBtn = wrapper
      .findAll('el-button-stub')
      .find((b) => b.text().includes('重新加载'))
    expect(reloadBtn, '重新加载').toBeTruthy()
    apiMultiDimension.mockClear()
    await reloadBtn!.trigger('click')
    await flushPromises()
    expect(apiMultiDimension).toHaveBeenCalled()
  })

  it('loadDimensionStats：success 为假 → message / 兜底文案 / 已有数据不覆盖', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 无数据 + message → 用后端 message
    vm.dimensionData = []
    apiMultiDimension.mockResolvedValueOnce({ success: false, message: '维度统计失败' })
    await vm.loadDimensionStats()
    expect(vm.loadError.dimension).toBe('维度统计失败')
    // dimensionData 为 null（?? [] 侧）+ 无 message → 兜底文案
    vm.dimensionData = null
    apiMultiDimension.mockResolvedValueOnce({ success: false })
    await vm.loadDimensionStats()
    expect(vm.loadError.dimension).toBe('暂无统计数据')
    // 已有数据 + success false → else-if 假侧，不设置错误
    vm.loadError.dimension = ''
    vm.dimensionData = [...dimRows]
    apiMultiDimension.mockResolvedValueOnce({ success: false })
    await vm.loadDimensionStats()
    expect(vm.loadError.dimension).toBe('')
    expect(vm.dimensionData).toEqual(dimRows)
  })

  it('loadYearlyTrend：success 为假 → message / 兜底文案 / 已有数据不覆盖', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.yearlyTrend = []
    apiYearlyComparison.mockResolvedValueOnce({ success: false, message: '趋势加载失败' })
    await vm.loadYearlyTrend()
    expect(vm.loadError.trend).toBe('趋势加载失败')
    // yearlyTrend 为 null（?? [] 侧）+ 无 message → 兜底文案
    vm.yearlyTrend = null
    apiYearlyComparison.mockResolvedValueOnce({ success: false })
    await vm.loadYearlyTrend()
    expect(vm.loadError.trend).toBe('暂无年度趋势数据')
    // 已有数据 → else-if 假侧
    vm.loadError.trend = ''
    vm.yearlyTrend = [{ year: 2024 }]
    apiYearlyComparison.mockResolvedValueOnce({ success: false })
    await vm.loadYearlyTrend()
    expect(vm.loadError.trend).toBe('')
  })

  it('yearlyTrend 为 null → 两个趋势 computed 的 ?? [] 侧 → null', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.yearlyTrend = null
    expect(vm.yearlyTrendAreaOption).toBeNull()
    expect(vm.utilizationTrendOption).toBeNull()
  })

  it('handleExportStats：dimensionData 为 null → ?? [] → 无数据警告', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.dimensionData = null
    vm.handleExportStats()
    expect(ElMessage.warning).toHaveBeenCalledWith('没有可导出的数据')
    expect(exportCsvMock).not.toHaveBeenCalled()
  })
})
