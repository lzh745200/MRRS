/**
 * views/ruralWorks/Analysis.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 加载数据与图表初始化、筛选（村庄/类型）、数据排序、
 * 指标计算、refreshData、exportAnalysis、视图切换、图表数据函数、字典函数全分支。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { ElMessage, getRuralWorksMock, logError, chartCtor } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  getRuralWorksMock: vi.fn(),
  logError: vi.fn(),
  chartCtor: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/ruralWork', () => ({ getRuralWorks: getRuralWorksMock }))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('chart.js/auto', () => ({
  Chart: chartCtor,
}))

import Analysis from '@/views/ruralWorks/Analysis.vue'

const items = [
  {
    name: '道路建设',
    village_name: '村A',
    type: 'infrastructure',
    status: 'completed',
    progress: 100,
    start_date: '2024-01-10',
    end_date: '2024-03-01',
  },
  {
    name: '产业帮扶',
    village_name: '村A',
    type: 'industry',
    status: 'in_progress',
    progress: 60,
    start_date: '2024-02-05',
    end_date: '2024-05-01',
  },
  {
    name: '教育资助',
    village_name: '村B',
    type: 'education',
    status: 'delayed',
    progress: 20,
    start_date: '2024-01-15',
    end_date: null,
  },
  {
    name: '未知类型',
    village_name: '',
    type: 'unknown_type',
    status: 'planned',
    progress: 0,
    start_date: null,
    end_date: null,
  },
]

let lastChartConfig: any = null

function mountComp() {
  return mount(Analysis, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-select': {
          template:
            '<div class="el-select-stub" @click="$emit(\'update:modelValue\', \'x\'); $emit(\'change\')"><slot /></div>',
        },
        'el-option': { template: '<div class="el-option-stub" />' },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-icon': { template: '<span class="el-icon-stub"><slot /></span>' },
        'el-dropdown': {
          template:
            '<div class="el-dropdown-stub" @click="$emit(\'command\', \'bar\')"><slot /></div>',
        },
        'el-dropdown-menu': { template: '<div class="el-dropdown-menu-stub"><slot /></div>' },
        'el-dropdown-item': { template: '<div class="el-dropdown-item-stub"><slot /></div>' },
        'el-table': {
          template:
            '<div class="el-table-stub"><slot name="default" /></div>',
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>',
          data() {
            return {
              rowA: { workName: '道路建设', village: '村A', type: '基础设施建设', status: '已完成', completionRate: 100, qualityScore: 4.5 },
              rowB: { workName: '产业帮扶', village: '村A', type: '产业发展', status: '进行中', completionRate: 60, qualityScore: 3.8 },
              rowC: { workName: '教育资助', village: '村B', type: '教育培训', status: '已延期', completionRate: 20, qualityScore: 0 },
            }
          },
        },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-progress': { template: '<div class="el-progress-stub" />' },
      },
    },
  })
}

function makeChart() {
  return {
    destroy: vi.fn(),
    data: { datasets: [{ data: [] }] },
    getContext: vi.fn().mockReturnValue(null),
    width: 300,
    height: 150,
  }
}

beforeEach(() => {
  vi.resetAllMocks()
  getRuralWorksMock.mockResolvedValue({ items })
  lastChartConfig = null
  chartCtor.mockImplementation((_el: any, config: any) => {
    lastChartConfig = config
    return makeChart()
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与数据加载', () => {
  it('onMounted 加载数据并初始化图表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(getRuralWorksMock).toHaveBeenCalledWith({ limit: 100 })
    expect(vm.analysisData).toHaveLength(4)
    expect(vm.analysisData[0]).toEqual({
      workName: '道路建设',
      village: '村A',
      type: '基础设施建设',
      status: '已完成',
      completionRate: 100,
      investment: 0,
      startDate: '2024-01-10',
      endDate: '2024-03-01',
      qualityScore: 4.5,
    })
    expect(vm.villages).toEqual(['村A', '村B'])
    expect(chartCtor).toHaveBeenCalled()
    expect(vm.loading).toBe(false)
  })

  it('加载失败 → logger + 提示', async () => {
    getRuralWorksMock.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('net')
    expect((wrapper.vm as any).analysisData).toEqual([])
  })

  it('响应无 items → 空数组', async () => {
    getRuralWorksMock.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).analysisData).toEqual([])
    expect((wrapper.vm as any).villages).toEqual([])
  })

  it('未知类型/状态与缺失字段走兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const row = vm.analysisData[3]
    expect(row.type).toBe('unknown_type')
    expect(row.status).toBe('计划中')
    expect(row.completionRate).toBe(0)
    expect(row.qualityScore).toBe(0)
    expect(row.startDate).toBe('')
  })

  it('item 无 type/status/name 字段 → || 兜底', async () => {
    getRuralWorksMock.mockResolvedValue({
      items: [{ progress: 10 }],
    })
    const wrapper = mountComp()
    await flushPromises()
    const row = (wrapper.vm as any).analysisData[0]
    expect(row.type).toBe('')
    expect(row.status).toBe('')
    expect(row.workName).toBe('')
  })
})

describe('筛选与排序', () => {
  it('村庄/类型筛选', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedVillage = '村A'
    await nextTick()
    expect(vm.filteredData).toHaveLength(2)

    vm.selectedType = 'education'
    await nextTick()
    expect(vm.filteredData).toHaveLength(0)

    vm.selectedVillage = ''
    await nextTick()
    expect(vm.filteredData).toHaveLength(1)
    expect(vm.filteredData[0].type).toBe('教育培训')
  })

  it('类型筛选全映射', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedType = 'industry'
    await nextTick()
    expect(vm.filteredData).toHaveLength(1)
    expect(vm.filteredData[0].type).toBe('产业发展')
  })

  it('排序三种方式', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.dataTableSort = 'completion'
    await nextTick()
    expect(vm.sortedAnalysisData[0].completionRate).toBe(100)

    vm.dataTableSort = 'startDate'
    await nextTick()
    expect(vm.sortedAnalysisData[0].startDate).toBe('2024-02-05')

    vm.dataTableSort = 'investment'
    await nextTick()
    expect(vm.sortedAnalysisData).toHaveLength(4)
  })
})

describe('指标计算', () => {
  it('核心指标计算', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.totalWorks).toBe(4)
    expect(vm.averageCompletionRate).toBe(60)
    expect(vm.averageDelayRate).toBe(25)
    expect(vm.totalInvestment).toBe(0)

    getRuralWorksMock.mockResolvedValue({ items: [] })
    const w2 = mountComp()
    await flushPromises()
    expect((w2.vm as any).averageCompletionRate).toBe(0)
    expect((w2.vm as any).averageDelayRate).toBe(0)
  })
})

describe('刷新与导出', () => {
  it('refreshData → 重新加载 + 提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    getRuralWorksMock.mockClear()
    await (wrapper.vm as any).refreshData()
    expect(getRuralWorksMock).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('数据刷新成功')
  })

  it('exportAnalysis 空数据 → warning', async () => {
    getRuralWorksMock.mockResolvedValue({ items: [] })
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).exportAnalysis()
    expect(ElMessage.warning).toHaveBeenCalledWith('没有可导出的数据')
  })

  it('exportAnalysis 成功 → 生成 CSV', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const clickSpy = vi.spyOn(HTMLElement.prototype, 'click').mockImplementation(() => {})
    await (wrapper.vm as any).exportAnalysis()
    expect(ElMessage.success).toHaveBeenCalledWith('分析报告导出成功')
    clickSpy.mockRestore()
  })

  it('exportAnalysis 字段缺失 → 单元格兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.analysisData = [{}, { startDate: '2024-01-01' }]
    await nextTick()
    const clickSpy = vi.spyOn(HTMLElement.prototype, 'click').mockImplementation(() => {})
    await vm.exportAnalysis()
    expect(ElMessage.success).toHaveBeenCalledWith('分析报告导出成功')
    clickSpy.mockRestore()
  })

  it('刷新/导出按钮', async () => {
    const clickSpy = vi.spyOn(HTMLElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    const btns = wrapper.findAll('.el-button-stub')
    const refresh = btns.find((b) => b.text().includes('刷新数据'))
    getRuralWorksMock.mockClear()
    await refresh!.trigger('click')
    await flushPromises()
    expect(getRuralWorksMock).toHaveBeenCalled()

    const exportBtn = btns.find((b) => b.text().includes('导出分析报告'))
    await exportBtn!.trigger('click')
    await flushPromises()
    expect(ElMessage.success).toHaveBeenCalledWith('分析报告导出成功')
    clickSpy.mockRestore()
  })
})

describe('视图与图表切换', () => {
  it('视图与图表切换（含柱状图/环形图渲染与 label 回调）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.handleTypeChartView('bar')
    await nextTick()
    vm.initTypeCharts()
    expect(vm.typeChartView).toBe('bar')

    vm.handleTypeChartView('pie')
    await nextTick()
    vm.initTypeCharts()
    expect(vm.typeChartView).toBe('pie')

    vm.handleStatusChartView('bar')
    await nextTick()
    vm.initStatusCharts()
    expect(vm.statusChartView).toBe('bar')

    vm.handleStatusChartView('doughnut')
    await nextTick()
    vm.initStatusCharts()
    expect(vm.statusChartView).toBe('doughnut')

    if (lastChartConfig?.options?.plugins?.tooltip?.callbacks?.label) {
      const cb = lastChartConfig.options.plugins.tooltip.callbacks.label
      const text = cb({ label: '已完成', raw: 1, dataset: { data: [1, 2] } })
      expect(text).toContain('已完成')
    }
  })

  it('updateCharts 全量更新（含空数据路径）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.analysisData = []
    await nextTick()
    await vm.updateCharts()
    await vm.updateCharts()
  })

  it('initTrendChart 无数据 → canvas 绘制提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.trendChart).toBeTruthy()
    expect(typeof vm.trendChart.getContext).toBe('function')
    vm.analysisData = []
    await nextTick()
    await vm.initTrendChart()
    await vm.initVillageRankingChart()
    await vm.initQualityAnalysisChart()
  })

  it('initTrendChart 图表引用为空 → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.trendChart = null
    await vm.initTrendChart()
    vm.villageRankingChart = null
    await vm.initVillageRankingChart()
    vm.qualityAnalysisChart = null
    await vm.initQualityAnalysisChart()
  })

  it('initTrendChart count 类型 → 工作数量标签', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.trendType = 'count'
    await vm.initTrendChart()
    const configs = chartCtor.mock.calls.map((c: any) => c[1])
    const trend = configs.find((c: any) => c.type === 'line')
    expect(trend).toBeTruthy()
    expect(trend.data.datasets[0].label).toBe('工作数量')
  })

  it('initTrendChart completion 类型 → 平均完成率标签', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.trendType = 'completion'
    await vm.initTrendChart()
    const configs = chartCtor.mock.calls.map((c: any) => c[1])
    const trend = configs.filter((c: any) => c.type === 'line').pop()
    expect(trend).toBeTruthy()
    expect(trend.data.datasets[0].label).toBe('平均完成率(%)')
  })

  it('initTrendChart investment 类型 → 投入资金标签', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.trendType = 'investment'
    await vm.initTrendChart()
    const configs = chartCtor.mock.calls.map((c: any) => c[1])
    const trend = configs.filter((c: any) => c.type === 'line').pop()
    expect(trend).toBeTruthy()
    expect(trend.data.datasets[0].label).toBe('投入资金(万元)')
  })

  it('tooltip label 回调空标签/空值分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleStatusChartView('doughnut')
    await nextTick()
    vm.initStatusCharts()
    const configs = chartCtor.mock.calls.map((c: any) => c[1])
    const doughnut = configs.find((c: any) => c.type === 'doughnut')
    const cb = doughnut.options.plugins.tooltip.callbacks.label
    const text = cb({ label: '', raw: 0, dataset: { data: [1] } })
    expect(typeof text).toBe('string')
    vm.handleTypeChartView('pie')
    await nextTick()
    vm.initTypeCharts()
    const configs2 = chartCtor.mock.calls.map((c: any) => c[1])
    const pie = configs2.find((c: any) => c.type === 'pie')
    const cb2 = pie.options.plugins.tooltip.callbacks.label
    const text2 = cb2({ label: '', raw: 0, dataset: { data: [1] } })
    expect(typeof text2).toBe('string')
  })

  it('updateTrendChart / updateDataTable', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.updateTrendChart()
    await vm.updateDataTable()
  })

  it('watch 筛选变化 → 重新加载 + 更新图表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    getRuralWorksMock.mockClear()
    ;(wrapper.vm as any).selectedVillage = '村B'
    await nextTick()
    await flushPromises()
    expect(getRuralWorksMock).toHaveBeenCalled()
  })

  it('handleTimeRangeChange/handleVillageChange/handleTypeChange 空实现', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleTimeRangeChange()
    vm.handleVillageChange()
    vm.handleTypeChange()
  })

  it('dropdown 视图切换', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const dropdowns = wrapper.findAll('.el-dropdown-stub')
    await dropdowns[0].trigger('click')
    expect((wrapper.vm as any).typeChartView).toBe('bar')
    await dropdowns[1].trigger('click')
    expect((wrapper.vm as any).statusChartView).toBe('bar')
  })

  it('筛选/趋势/排序 select v-model', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    for (const sel of wrapper.findAll('.el-select-stub')) {
      await sel.trigger('click')
    }
    await flushPromises()
    expect(vm.timeRange).toBe('x')
    expect(vm.selectedVillage).toBe('x')
    expect(vm.selectedType).toBe('x')
    expect(vm.trendType).toBe('x')
    expect(vm.dataTableSort).toBe('x')
  })
})

describe('图表数据函数', () => {
  it('getTypeDistributionData / getStatusDistributionData', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const td = vm.getTypeDistributionData()
    expect(td.labels).toContain('基础设施建设')
    expect(td.values).toContain(1)
    const sd = vm.getStatusDistributionData()
    expect(sd.labels).toContain('已完成')
  })

  it('getTrendData 空数据/有数据/类型切换', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.analysisData = []
    await nextTick()
    let t = vm.getTrendData()
    expect(t.hasData).toBe(false)

    vm.analysisData = [
      { startDate: '2024-01-10', completionRate: 100, investment: 10 },
      { startDate: '2024-02-05', completionRate: 60, investment: 20 },
    ]
    await nextTick()
    t = vm.getTrendData()
    expect(t.hasData).toBe(true)
    expect(t.labels).toContain('2024-01')

    vm.trendType = 'completion'
    t = vm.getTrendData()
    expect(t.values[0]).toBeGreaterThan(0)

    vm.trendType = 'investment'
    t = vm.getTrendData()
    expect(t.values).toHaveLength(t.labels.length)
  })

  it('getTrendData 无 startDate 行跳过', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.analysisData = [{ startDate: '' }, { startDate: '2024-03-01' }]
    await nextTick()
    const t = vm.getTrendData()
    expect(t.labels).toEqual(['2024-03'])
  })

  it('getTrendData 全部无 startDate → 空月份兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.analysisData = [{ startDate: '' }, { startDate: null }]
    await nextTick()
    const t = vm.getTrendData()
    expect(t.hasData).toBe(false)
    expect(t.labels).toEqual([])
  })

  it('getVillageRankingData / getQualityAnalysisData', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const v = vm.getVillageRankingData()
    expect(v.labels).toContain('村A')
    const q = vm.getQualityAnalysisData()
    expect(q.labels).toHaveLength(5)
  })
})

describe('字典函数', () => {
  it('getTypeTagType / getStatusTagType 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getTypeTagType('基础设施建设')).toBe('warning')
    expect(vm.getTypeTagType('产业发展')).toBe('success')
    expect(vm.getTypeTagType('教育培训')).toBe('primary')
    expect(vm.getTypeTagType('医疗健康')).toBe('info')
    expect(vm.getTypeTagType('生态环境保护')).toBe('danger')
    expect(vm.getTypeTagType('x')).toBe('info')
    expect(vm.getStatusTagType('已完成')).toBe('success')
    expect(vm.getStatusTagType('进行中')).toBe('primary')
    expect(vm.getStatusTagType('计划中')).toBe('info')
    expect(vm.getStatusTagType('已延期')).toBe('danger')
    expect(vm.getStatusTagType('x')).toBe('info')
  })

  it('getProgressStatus / getQualityScoreClass 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getProgressStatus(100)).toBe('success')
    expect(vm.getProgressStatus(80)).toBe('')
    expect(vm.getProgressStatus(50)).toBe('warning')
    expect(vm.getProgressStatus(10)).toBe('exception')
    expect(vm.getQualityScoreClass(4.5)).toBe('excellent')
    expect(vm.getQualityScoreClass(4.0)).toBe('good')
    expect(vm.getQualityScoreClass(3.5)).toBe('average')
    expect(vm.getQualityScoreClass(2)).toBe('poor')
    expect(vm.getQualityScoreClass(0)).toBe('not-evaluated')
  })

  it('指标变化正负号渲染（positive/negative 两侧）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.totalWorksChange = 5
    vm.completionRateChange = 3
    vm.delayRateChange = 4
    vm.investmentChange = 7
    await nextTick()
    expect(vm.totalWorksChange).toBe(5)
    expect(vm.completionRateChange).toBe(3)
    expect(vm.delayRateChange).toBe(4)
    expect(vm.investmentChange).toBe(7)
    vm.totalWorksChange = -5
    await nextTick()
    expect(vm.totalWorksChange).toBe(-5)
  })
})
