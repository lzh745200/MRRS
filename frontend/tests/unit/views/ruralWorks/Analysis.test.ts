/**
 * views/ruralWorks/Analysis.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 加载数据与图表初始化、筛选（村庄/类型）、数据排序、
 * 指标计算、refreshData、exportAnalysis、视图切换、图表数据函数、字典函数全分支、
 * ECharts 各图 option 构造（饼/柱/环形/折线/横向 bar/雷达）、resize/dispose 生命周期。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { ElMessage, generateWorkReportMock, logError, echartsInit, mockInstances } = vi.hoisted(() => {
  const instances: any[] = []
  const init = vi.fn((_el: any) => {
    const inst: any = {
      option: null,
      setOption: vi.fn((opt: any) => {
        inst.option = opt
      }),
      dispose: vi.fn(),
      resize: vi.fn(),
      on: vi.fn(),
    }
    instances.push(inst)
    return inst
  })
  return {
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
    generateWorkReportMock: vi.fn(),
    logError: vi.fn(),
    echartsInit: init,
    mockInstances: instances,
  }
})

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/ruralWork', () => ({ generateWorkReport: generateWorkReportMock }))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/utils/echarts', () => ({
  default: { init: echartsInit },
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

/** 取最近一次某 series 类型的 option */
function lastOptionBySeriesType(type: string) {
  const list = mockInstances.filter((i) => i.option?.series?.[0]?.type === type)
  return list.length ? list[list.length - 1].option : undefined
}

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
              rowA: { workName: '道路建设', village: '村A', type: '基础设施建设', status: '已完成', completionRate: 100 },
              rowB: { workName: '产业帮扶', village: '村A', type: '产业发展', status: '进行中', completionRate: 60 },
              rowC: { workName: '教育资助', village: '村B', type: '教育培训', status: '已延期', completionRate: 20 },
            }
          },
        },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-progress': { template: '<div class="el-progress-stub" />' },
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  mockInstances.length = 0
  generateWorkReportMock.mockResolvedValue({ items })
})

describe('挂载与数据加载', () => {
  it('onMounted 加载数据并初始化图表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(generateWorkReportMock).toHaveBeenCalledWith()
    expect(vm.analysisData).toHaveLength(4)
    expect(vm.analysisData[0]).toEqual({
      workName: '道路建设',
      village: '村A',
      type: '基础设施建设',
      status: '已完成',
      completionRate: 100,
      startDate: '2024-01-10',
      endDate: '2024-03-01',
    })
    // 后端 RuralWork 无金额/质量评分类字段，页面不得再用常量伪造
    expect(vm.analysisData[0]).not.toHaveProperty('investment')
    expect(vm.analysisData[0]).not.toHaveProperty('qualityScore')
    expect(vm.villages).toEqual(['村A', '村B'])
    expect(echartsInit).toHaveBeenCalled()
    expect(vm.loading).toBe(false)
    wrapper.unmount()
  })

  it('报表返回 120 条明细 → 分析数据不再被列表首页 100 条截断', async () => {
    const many = Array.from({ length: 120 }, (_, i) => ({
      ...items[0],
      id: i + 1,
      name: `工作${i + 1}`,
    }))
    generateWorkReportMock.mockResolvedValue({ items: many })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).analysisData).toHaveLength(120)
    wrapper.unmount()
  })

  it('后端直接返回数组（非 {items} 信封）→ 直接采用', async () => {
    generateWorkReportMock.mockResolvedValue(items)
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.analysisData).toHaveLength(4)
    wrapper.unmount()
  })

  it('加载失败 → logger + 提示', async () => {
    generateWorkReportMock.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('net')
    expect((wrapper.vm as any).analysisData).toEqual([])
    wrapper.unmount()
  })

  it('首屏加载未完成即卸载 → 不再初始化图表或注册 resize', async () => {
    let resolveRequest!: (value: unknown) => void
    generateWorkReportMock.mockReturnValue(new Promise((resolve) => (resolveRequest = resolve)))
    const addSpy = vi.spyOn(window, 'addEventListener')

    const wrapper = mountComp()
    await nextTick()
    wrapper.unmount()
    resolveRequest({ items })
    await flushPromises()

    expect(echartsInit).not.toHaveBeenCalled()
    expect(addSpy).not.toHaveBeenCalledWith('resize', expect.any(Function))
    addSpy.mockRestore()
  })

  it('响应无 items → 空数组', async () => {
    generateWorkReportMock.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).analysisData).toEqual([])
    expect((wrapper.vm as any).villages).toEqual([])
    wrapper.unmount()
  })

  it('未知类型/状态与缺失字段走兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const row = vm.analysisData[3]
    expect(row.type).toBe('unknown_type')
    expect(row.status).toBe('计划中')
    expect(row.completionRate).toBe(0)
    expect(row).not.toHaveProperty('qualityScore')
    expect(row.startDate).toBe('')
    wrapper.unmount()
  })

  it('item 无 type/status/name 字段 → || 兜底', async () => {
    generateWorkReportMock.mockResolvedValue({
      items: [{ progress: 10 }],
    })
    const wrapper = mountComp()
    await flushPromises()
    const row = (wrapper.vm as any).analysisData[0]
    expect(row.type).toBe('')
    expect(row.status).toBe('')
    expect(row.workName).toBe('')
    wrapper.unmount()
  })
})

describe('筛选与排序', () => {
  it('时间范围筛选真正生效（无日期/超窗记录被排除）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const today = new Date()
    const recent = today.toISOString().slice(0, 10)
    const old = '2000-01-01'

    // timeRange 的 watch 会重新拉取数据，先等它落定再注入边界样本
    vm.timeRange = '30'
    await flushPromises()
    vm.analysisData = [
      { startDate: recent },
      { startDate: old },
      { startDate: '' },
      { startDate: 'not-a-date' },
    ]
    await nextTick()
    expect(vm.filteredData).toHaveLength(1)
    expect(vm.filteredData[0].startDate).toBe(recent)

    vm.timeRange = 'all'
    await flushPromises()
    vm.analysisData = [
      { startDate: recent },
      { startDate: old },
      { startDate: '' },
      { startDate: 'not-a-date' },
    ]
    await nextTick()
    expect(vm.filteredData).toHaveLength(4)
    wrapper.unmount()
  })

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
    wrapper.unmount()
  })

  it('类型筛选全映射', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedType = 'industry'
    await nextTick()
    expect(vm.filteredData).toHaveLength(1)
    expect(vm.filteredData[0].type).toBe('产业发展')
    wrapper.unmount()
  })

  it('按开始日期排序：空日期不得占首位（旧实现 new Date("") → NaN 比较器静默失效）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.analysisData = [
      { startDate: '', completionRate: 0 },
      { startDate: '2024-01-10', completionRate: 10 },
    ]
    vm.dataTableSort = 'startDate'
    await nextTick()
    expect(vm.sortedAnalysisData[0].startDate).toBe('2024-01-10')
    wrapper.unmount()
  })

  it('排序两种真实字段', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.dataTableSort = 'completion'
    await nextTick()
    expect(vm.sortedAnalysisData[0].completionRate).toBe(100)

    vm.dataTableSort = 'startDate'
    await nextTick()
    expect(vm.sortedAnalysisData[0].startDate).toBe('2024-02-05')
    wrapper.unmount()
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
    expect(vm.coveredVillageCount).toBe(2)
    expect(vm).not.toHaveProperty('totalInvestment')
    wrapper.unmount()

    generateWorkReportMock.mockResolvedValue({ items: [] })
    const w2 = mountComp()
    await flushPromises()
    expect((w2.vm as any).averageCompletionRate).toBe(0)
    expect((w2.vm as any).averageDelayRate).toBe(0)
    w2.unmount()
  })
})

describe('刷新与导出', () => {
  it('refreshData → 重新加载 + 提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    generateWorkReportMock.mockClear()
    await (wrapper.vm as any).refreshData()
    expect(generateWorkReportMock).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('数据刷新成功')
    wrapper.unmount()
  })

  it('exportAnalysis 空数据 → warning', async () => {
    generateWorkReportMock.mockResolvedValue({ items: [] })
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).exportAnalysis()
    expect(ElMessage.warning).toHaveBeenCalledWith('没有可导出的数据')
    wrapper.unmount()
  })

  it('exportAnalysis 成功 → 生成 CSV', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const clickSpy = vi.spyOn(HTMLElement.prototype, 'click').mockImplementation(() => {})
    await (wrapper.vm as any).exportAnalysis()
    expect(ElMessage.success).toHaveBeenCalledWith('分析报告导出成功')
    clickSpy.mockRestore()
    wrapper.unmount()
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
    wrapper.unmount()
  })

  it('刷新/导出按钮', async () => {
    const clickSpy = vi.spyOn(HTMLElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    const btns = wrapper.findAll('.el-button-stub')
    const refresh = btns.find((b) => b.text().includes('刷新数据'))
    generateWorkReportMock.mockClear()
    await refresh!.trigger('click')
    await flushPromises()
    expect(generateWorkReportMock).toHaveBeenCalled()

    const exportBtn = btns.find((b) => b.text().includes('导出分析报告'))
    await exportBtn!.trigger('click')
    await flushPromises()
    expect(ElMessage.success).toHaveBeenCalledWith('分析报告导出成功')
    clickSpy.mockRestore()
    wrapper.unmount()
  })
})

describe('视图与图表切换', () => {
  it('视图与图表切换（含柱状图/环形图渲染与 tooltip 文案）', async () => {
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

    // 饼/环形图 tooltip 等价文案（标签: 值 (百分比%)）
    const ring = lastOptionBySeriesType('pie')
    expect(ring.tooltip.formatter).toBe('{b}: {c} ({d}%)')
    wrapper.unmount()
  })

  it('updateCharts 全量更新（含空数据路径）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.analysisData = []
    await nextTick()
    await vm.updateCharts()
    await vm.updateCharts()
    wrapper.unmount()
  })

  it('initTrendChart 无数据 → title 提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.trendChart).toBeTruthy()
    vm.analysisData = []
    await nextTick()
    await vm.initTrendChart()
    const tip = mockInstances.map((i) => i.option).find((o) => o?.title?.text)
    expect(tip.title.text).toBe('暂无数据，请先录入乡村工作数据')

    await vm.initVillageRankingChart()
    wrapper.unmount()
  })

  it('initTrendChart 图表引用为空 → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.trendChart = null
    await vm.initTrendChart()
    vm.villageRankingChart = null
    await vm.initVillageRankingChart()
    wrapper.unmount()
  })

  it('initTrendChart count 类型 → 工作数量标签', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.trendType = 'count'
    await vm.initTrendChart()
    const trend = lastOptionBySeriesType('line')
    expect(trend).toBeTruthy()
    expect(trend.series[0].name).toBe('工作数量')
    wrapper.unmount()
  })

  it('initTrendChart completion 类型 → 平均完成率标签', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.trendType = 'completion'
    await vm.initTrendChart()
    const trend = lastOptionBySeriesType('line')
    expect(trend).toBeTruthy()
    expect(trend.series[0].name).toBe('平均完成率(%)')
    wrapper.unmount()
  })

  it('村庄排名（横向 bar）option 构造', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.initVillageRankingChart()

    // 横向柱状图：yAxis category + xAxis value（indexAxis:'y' 的等价翻译）
    const horizontal = mockInstances
      .map((i) => i.option)
      .filter((o) => o?.series?.[0]?.type === 'bar' && o?.yAxis?.type === 'category')
      .pop()
    expect(horizontal).toBeTruthy()
    expect(horizontal.yAxis.inverse).toBe(true)
    // W11-T45：颜色令牌化 —— #0055aa 收敛为共享调色板亮蓝（COLOR_PALETTE[3]）
    expect(horizontal.series[0].itemStyle.color).toBe('#3b82f6')
    expect(mockInstances.some((i) => i.option?.series?.[0]?.type === 'radar')).toBe(false)
    wrapper.unmount()
  })

  it('updateTrendChart / updateDataTable', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.updateTrendChart()
    await vm.updateDataTable()
    wrapper.unmount()
  })

  it('window resize 触发 resizeCharts（含已销毁实例的空值分支）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const current = mockInstances.slice()

    window.dispatchEvent(new Event('resize'))
    expect(current.some((c) => c.resize.mock.calls.length > 0)).toBe(true)

    // 切到柱状视图 → typeBarChartInstance / statusBarChartInstance 建立，
    // 再 resize → 覆盖 resizeCharts 中这两条可选链的**非空**分支
    // （默认饼/环形视图下柱状实例恒为 null，只走到空值分支）
    vm.handleTypeChartView('bar')
    vm.handleStatusChartView('bar')
    await flushPromises()
    const bars = mockInstances.slice(current.length)
    window.dispatchEvent(new Event('resize'))
    expect(bars.filter((c) => c.resize.mock.calls.length > 0).length).toBeGreaterThanOrEqual(2)

    // 主动销毁全部实例后再次 resize → 覆盖 resizeCharts 的空值分支
    vm.disposeAllCharts()
    expect(() => vm.resizeCharts()).not.toThrow()

    // 卸载 → onBeforeUnmount 移除监听并 disposeAllCharts（实例已空 → 假分支）
    wrapper.unmount()
    expect(current.every((c) => c.dispose.mock.calls.length > 0)).toBe(true)
  })

  it('watch 筛选变化 → 重新加载 + 更新图表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    generateWorkReportMock.mockClear()
    ;(wrapper.vm as any).selectedVillage = '村B'
    await nextTick()
    await flushPromises()
    expect(generateWorkReportMock).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('handleTimeRangeChange/handleVillageChange/handleTypeChange 空实现', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleTimeRangeChange()
    vm.handleVillageChange()
    vm.handleTypeChange()
    wrapper.unmount()
  })

  it('dropdown 视图切换', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const dropdowns = wrapper.findAll('.el-dropdown-stub')
    await dropdowns[0].trigger('click')
    expect((wrapper.vm as any).typeChartView).toBe('bar')
    await dropdowns[1].trigger('click')
    expect((wrapper.vm as any).statusChartView).toBe('bar')
    wrapper.unmount()
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
    wrapper.unmount()
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
    wrapper.unmount()
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
      { startDate: '2024-01-10', completionRate: 100 },
      { startDate: '2024-02-05', completionRate: 60 },
    ]
    await nextTick()
    t = vm.getTrendData()
    expect(t.hasData).toBe(true)
    expect(t.labels).toContain('2024-01')

    vm.trendType = 'completion'
    t = vm.getTrendData()
    expect(t.values[0]).toBeGreaterThan(0)
    expect(t.values).toHaveLength(t.labels.length)
    wrapper.unmount()
  })

  it('getTrendData 无 startDate 行跳过', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.analysisData = [{ startDate: '' }, { startDate: '2024-03-01' }]
    await nextTick()
    const t = vm.getTrendData()
    expect(t.labels).toEqual(['2024-03'])
    wrapper.unmount()
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
    wrapper.unmount()
  })

  it('getVillageRankingData 只使用真实村庄工作量', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const v = vm.getVillageRankingData()
    expect(v.labels).toContain('村A')
    expect(vm).not.toHaveProperty('getQualityAnalysisData')
    wrapper.unmount()
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
    wrapper.unmount()
  })

  it('getProgressStatus 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getProgressStatus(100)).toBe('success')
    expect(vm.getProgressStatus(80)).toBe('')
    expect(vm.getProgressStatus(50)).toBe('warning')
    expect(vm.getProgressStatus(10)).toBe('exception')
    expect(vm).not.toHaveProperty('getQualityScoreClass')
    wrapper.unmount()
  })

  it('指标卡不再渲染无数据来源的环比变化', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm).not.toHaveProperty('totalWorksChange')
    expect(vm).not.toHaveProperty('completionRateChange')
    expect(vm).not.toHaveProperty('delayRateChange')
    expect(vm).not.toHaveProperty('investmentChange')
    expect(wrapper.text()).not.toContain('较上期相比')
    wrapper.unmount()
  })
})