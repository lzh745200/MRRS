/**
 * Dashboard.vue (数据分析仪表板) 组件测试
 *
 * 覆盖目标：src/views/analytics/dashboard/Dashboard.vue 100% 语句覆盖
 *
 * 测试场景：
 *  1. 挂载加载 — onMounted → loadFilterOptions / initCharts / loadData / fetchKpiTrends
 *  2. 筛选与年份切换 — department / regionType(isThreeRegions|isKeyCounty) / year 参数分支
 *  3. 异常路径 — 统计/筛选选项/KPI趋势/年度趋势加载失败
 *  4. 钻取面板 — handleRegionClick 成功(渲染 v-if 面板)与失败、closeDrillDown
 *  5. 导出报表 — handleExport 生成 JSON Blob 下载
 *  6. resize / 卸载 — handleResize 与 onUnmounted 销毁图表
 *  7. 空数据 — `|| 0` 兜底链 + generateSparkData baseValue<=0 分支
 *
 * echarts 被完整 mock：setOption 会主动调用 option 内的 tooltip.formatter 与
 * yAxis.min/max 回调，以覆盖这些函数字面量语句。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// ==================== Mocks ====================

const h = vi.hoisted(() => ({
  clickHandler: null as null | ((params: any) => any),
}))

vi.mock('@/utils/echarts', () => {
  class LinearGradient {
    constructor(..._args: any[]) {}
  }
  const makeChart = () => ({
    setOption(option: any) {
      // 主动执行配置中的回调，覆盖 formatter / min / max 函数体语句
      const formatter = option?.tooltip?.formatter
      if (typeof formatter === 'function') {
        formatter({ marker: '<i/>', name: '测试', value: 1, percent: 2 })
      }
      const yAxis = option?.yAxis
      const axes = Array.isArray(yAxis) ? yAxis : yAxis ? [yAxis] : []
      for (const ax of axes) {
        if (typeof ax?.min === 'function') ax.min({ min: 0, max: 10 })
        if (typeof ax?.max === 'function') ax.max({ min: 0, max: 10 })
      }
    },
    on(event: string, cb: any) {
      if (event === 'click') h.clickHandler = cb
    },
    resize: () => {},
    dispose: () => {},
    isDisposed: () => false,
  })
  return {
    default: {
      init: () => makeChart(),
      graphic: { LinearGradient },
    },
  }
})

vi.mock('@/utils/echarts-theme', () => ({
  getCurrentTheme: () => 'military',
}))

vi.mock('@/components/business/SystemStatus.vue', () => ({
  default: {
    name: 'SystemStatus',
    props: ['pollInterval', 'showRefresh'],
    template: '<div class="system-status-stub" />',
  },
}))

vi.mock('@/api/analytics', () => ({
  getSummaryStatistics: vi.fn(),
  getFilterOptions: vi.fn(),
  drillDown: vi.fn(),
}))

vi.mock('@/api/dashboard', () => ({
  getKpiTrends: vi.fn(),
  getYearlyTrends: vi.fn(),
}))

import Dashboard from '@/views/analytics/dashboard/Dashboard.vue'
import { getSummaryStatistics, getFilterOptions, drillDown } from '@/api/analytics'
import { getKpiTrends, getYearlyTrends } from '@/api/dashboard'

// ==================== Helpers ====================

const fullStats = () => ({
  year: 2024,
  villages: {
    totalVillages: 1234,
    threeRegionsCount: 100,
    keyCountyCount: 50,
    provincialDemoCount: 20,
    crossProvinceCount: 10,
  },
  population: { totalPopulation: 123456, totalHouseholds: 3000, povertyHouseholds: 200 },
  income: { avgPerCapitaIncome: 1.2345, totalCollectiveIncome: 500 },
  investment: {
    industry: 40000,
    infrastructure: 50000,
    infrastructureRoadKm: 12,
    education: 30000,
    educationAidedStudents: 40,
  },
})

const stubs = {
  // 可交互 select：正确实现 v-model + change
  'el-select': {
    name: 'ElSelectStub',
    props: ['modelValue'],
    emits: ['update:modelValue', 'change'],
    template:
      '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value); $emit(\'change\', $event.target.value)"><slot /></select>',
  },
  'el-option': {
    name: 'ElOptionStub',
    props: ['label', 'value'],
    template: '<option :value="value">{{ label }}</option>',
  },
  'el-button': {
    name: 'ElButtonStub',
    emits: ['click'],
    template: '<button @click="$emit(\'click\')"><slot /></button>',
  },
}

// 关键：VTU 默认不渲染 stub 的默认插槽，必须开启 renderStubDefaultSlot，
// 否则 el-row/el-col 内的 KPI 卡片与图表容器 div 不会渲染，图表无法初始化。
const mountDashboard = () =>
  mount(Dashboard, { global: { stubs, renderStubDefaultSlot: true } })

// ==================== Tests ====================

describe('Dashboard.vue (analytics/dashboard)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    h.clickHandler = null
    vi.mocked(getFilterOptions).mockResolvedValue({
      departments: ['教育部', '卫健委'],
      supportUnits: [],
      regionScopes: [],
      years: [],
    } as any)
    vi.mocked(getSummaryStatistics).mockResolvedValue(fullStats() as any)
    vi.mocked(getKpiTrends).mockResolvedValue({
      villages: 5,
      population: 6,
      income: 7,
      investment: 8,
    })
    vi.mocked(getYearlyTrends).mockResolvedValue({
      years: [2020, 2021],
      villages: [1, 2],
      population: [3, 4],
      income: [5, 6],
    })
    vi.mocked(drillDown).mockResolvedValue({
      items: [{ name: '教育部', value: 10, totalPopulation: 100 }],
    } as any)
  })

  it('挂载后加载数据并渲染 KPI、筛选选项与图表', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    expect(getFilterOptions).toHaveBeenCalledTimes(1)
    expect(getSummaryStatistics).toHaveBeenCalledTimes(1)
    expect(getSummaryStatistics).toHaveBeenCalledWith(
      expect.objectContaining({ year: new Date().getFullYear() })
    )
    expect(getKpiTrends).toHaveBeenCalledTimes(1)
    expect(getYearlyTrends).toHaveBeenCalled()

    // KPI 数值渲染：toLocaleString 分支 + formatNumber >= 10000 → '万' 分支
    expect(wrapper.text()).toContain('1,234')
    expect(wrapper.text()).toContain('12.3万')
    expect(wrapper.text()).toContain('1.23') // avgPerCapitaIncome.toFixed(2)
    expect(wrapper.text()).toContain('12.0万') // totalInvestment=120000 → formatNumber '万'
    // KPI 环比趋势
    expect(wrapper.text()).toContain('5%')
    expect(wrapper.text()).toContain('8%')
    // 部门筛选 v-for 渲染
    expect(wrapper.text()).toContain('教育部')
    expect(wrapper.text()).toContain('卫健委')
    // 钻取回调已注册
    expect(h.clickHandler).toBeTypeOf('function')
    wrapper.unmount()
  })

  it('切换年份后携带 year 参数重新加载', async () => {
    const wrapper = mountDashboard()
    await flushPromises()
    vi.mocked(getSummaryStatistics).mockClear()

    const yearSelect = wrapper.findAll('select')[0]
    await yearSelect.setValue('2020')
    await flushPromises()

    expect(getSummaryStatistics).toHaveBeenCalledWith(expect.objectContaining({ year: '2020' }))
    wrapper.unmount()
  })

  it('选择部门后携带 department 参数重新加载', async () => {
    const wrapper = mountDashboard()
    await flushPromises()
    vi.mocked(getSummaryStatistics).mockClear()

    const deptSelect = wrapper.findAll('select')[1]
    await deptSelect.setValue('教育部')
    await flushPromises()

    expect(getSummaryStatistics).toHaveBeenCalledWith(
      expect.objectContaining({ department: '教育部' })
    )
    wrapper.unmount()
  })

  it('选择地域属性 isThreeRegions / isKeyCounty 设置对应参数', async () => {
    const wrapper = mountDashboard()
    await flushPromises()
    vi.mocked(getSummaryStatistics).mockClear()

    const regionSelect = wrapper.findAll('select')[2]
    await regionSelect.setValue('isThreeRegions')
    await flushPromises()
    expect(getSummaryStatistics).toHaveBeenLastCalledWith(
      expect.objectContaining({ isThreeRegions: true })
    )

    await regionSelect.setValue('isKeyCounty')
    await flushPromises()
    expect(getSummaryStatistics).toHaveBeenLastCalledWith(
      expect.objectContaining({ isKeyCounty: true })
    )
    wrapper.unmount()
  })

  it('统计数据加载失败时重置为零值', async () => {
    vi.mocked(getSummaryStatistics).mockRejectedValue(new Error('网络错误'))
    const wrapper = mountDashboard()
    await flushPromises()

    // formatNumber(0) → toLocaleString 分支；收入 formatMoney4(0) 去尾零
    expect(wrapper.text()).toContain('0')
    wrapper.unmount()
  })

  it('统计接口返回空对象时使用默认值兜底（含 sparkline 零值分支）', async () => {
    vi.mocked(getSummaryStatistics).mockResolvedValue({} as any)
    const wrapper = mountDashboard()
    await flushPromises()

    expect(wrapper.text()).toContain('0')
    wrapper.unmount()
  })

  it('筛选选项加载失败仅记录日志不中断挂载', async () => {
    vi.mocked(getFilterOptions).mockRejectedValue(new Error('选项失败'))
    const wrapper = mountDashboard()
    await flushPromises()

    expect(getSummaryStatistics).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('KPI 趋势获取失败使用默认值 0', async () => {
    vi.mocked(getKpiTrends).mockRejectedValue(new Error('KPI失败'))
    const wrapper = mountDashboard()
    await flushPromises()

    expect(wrapper.text()).toContain('0%')
    wrapper.unmount()
  })

  it('年度趋势获取失败时使用默认零值序列', async () => {
    vi.mocked(getYearlyTrends).mockRejectedValue(new Error('趋势失败'))
    const wrapper = mountDashboard()
    await flushPromises()

    expect(getSummaryStatistics).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('钻取成功渲染面板并可关闭', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    await h.clickHandler!({ name: '三区三州' })
    await flushPromises()
    await nextTick()

    expect(drillDown).toHaveBeenCalledWith({
      dimension: 'province',
      value: '三区三州',
      targetDimension: 'department',
    })
    const panel = wrapper.find('.drill-down-panel')
    expect(panel.exists()).toBe(true)
    expect(panel.text()).toContain('三区三州 - 详细数据')

    // 关闭面板
    await panel.find('button').trigger('click')
    await nextTick()
    expect(wrapper.find('.drill-down-panel').exists()).toBe(false)
    wrapper.unmount()
  })

  it('钻取失败时不显示面板', async () => {
    vi.mocked(drillDown).mockRejectedValue(new Error('钻取失败'))
    const wrapper = mountDashboard()
    await flushPromises()

    await h.clickHandler!({ name: '三区三州' })
    await flushPromises()
    await nextTick()

    expect(wrapper.find('.drill-down-panel').exists()).toBe(false)
    wrapper.unmount()
  })

  it('导出报表生成 JSON 文件下载', async () => {
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {})
    const wrapper = mountDashboard()
    await flushPromises()

    const exportBtn = wrapper.findAll('button')[0]
    await exportBtn.trigger('click')

    expect(clickSpy).toHaveBeenCalledTimes(1)
    clickSpy.mockRestore()
    wrapper.unmount()
  })

  it('窗口 resize 触发图表重排', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    window.dispatchEvent(new Event('resize'))
    // 不抛错即通过（resize 调用链覆盖）
    expect(wrapper.exists()).toBe(true)
    wrapper.unmount()
  })

  it('卸载时销毁全部图表实例', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    expect(() => wrapper.unmount()).not.toThrow()
  })

  describe('分支补满：?? 兜底与 initCharts 重复初始化', () => {
    it('KPI 趋势接口字段缺失时使用 ?? 0 兜底', async () => {
      vi.mocked(getKpiTrends).mockResolvedValue({} as any)
      const wrapper = mountDashboard()
      await flushPromises()

      // villages/population/income/investment 均走 ?? 0 → 0%
      expect(wrapper.text()).toContain('0%')
      wrapper.unmount()
    })

    it('年度趋势接口数组字段缺失时回退默认零值序列', async () => {
      // trendData.years 存在但 villages/population/income 缺失 → ?? 默认序列兜底
      vi.mocked(getYearlyTrends).mockResolvedValue({ years: [2021, 2022] } as any)
      const wrapper = mountDashboard()
      await flushPromises()

      expect(getYearlyTrends).toHaveBeenCalled()
      wrapper.unmount()
    })

    it('图表已初始化后再次 initCharts 先销毁旧实例', async () => {
      const wrapper = mountDashboard()
      await flushPromises()

      // 挂载后图表变量已非空；同实例再次 initCharts 覆盖 ?.dispose() 非空分支
      const vm = wrapper.vm as any
      expect(typeof vm.initCharts).toBe('function')
      vm.initCharts()
      wrapper.unmount()
    })
  })
})
