/**
 * views/funds/Report.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 加载、fundApi.list 映射全字段、类型/趋势统计透传、
 * summary/reportPeriod/currentTime computed、图表空数据兜底、
 * generateReport/exportReport（空数据与成功）/printReport、字典函数全分支。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const {
  ElMessage,
  fundApiMock,
  logError,
  exportCSVMock,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  fundApiMock: {
    list: vi.fn(),
    statisticsMultiDimension: vi.fn(),
  },
  logError: vi.fn(),
  exportCSVMock: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/api/funds', () => ({
  fundApi: fundApiMock,
}))

vi.mock('@/api/fundStatistics', () => ({
  FUND_TYPES: { project: '项目经费', operation: '运行经费' },
  FUND_STATUSES: { pending: '待审批', approved: '已审批', in_use: '使用中', rejected: '已驳回' },
}))

vi.mock('@/utils/exportUtil', () => ({
  exportUtil: { exportToCSV: exportCSVMock },
}))

import Report from '@/views/funds/Report.vue'

const fundRow = {
  id: 1,
  name: '测试经费',
  fund_type: 'project',
  amount: 100.5,
  used_amount: 40.25,
  source: '财政拨款',
  applicant: '张三',
  status: 'pending',
  application_date: '2024-01-15',
}

const fundRow2 = {
  id: 2,
  name: '运行经费',
  type: 'operation',
  amount: 200,
  used_amount: 100,
  fund_source: '自筹',
  operator: '李四',
  status: 'approved',
  created_at: '2024-02-01T00:00:00',
}

const typeRes = {
  success: true,
  data: [
    { label: '项目经费', total_amount: 100.5 },
    { label: '运行经费', total_amount: 200 },
  ],
}

const trendRes = {
  success: true,
  data: [
    { label: '2024-01', total_amount: 100.5, total_used: 40.25 },
    { label: '2024-02', total_amount: 200, total_used: 100 },
  ],
}

function mountComp() {
  return mount(Report, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'base-chart': {
          name: 'BaseChart',
          template: '<div class="base-chart-stub" />',
          props: ['option', 'height'],
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template: '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
          data() {
            return { rowA: { ...fundRow }, rowB: { ...fundRow2 } }
          },
        },
        'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
        'el-form': { template: '<div class="el-form-stub"><slot /></div>' },
        'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
        'el-input': { template: '<div class="el-input-stub" />' },
        'el-select': {
          template:
            '<div class="el-select-stub" @click="$emit(\'update:modelValue\', \'x\')"><slot /></div>',
        },
        'el-option': { template: '<div class="el-option-stub" />' },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-date-picker': {
          template:
            '<div class="el-date-picker-stub" @click="$emit(\'update:modelValue\', [\'a\', \'b\'])" />',
        },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-row': { template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { template: '<div class="el-col-stub"><slot /></div>' },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  fundApiMock.list.mockResolvedValue({ items: [fundRow, fundRow2], total: 2 })
  fundApiMock.statisticsMultiDimension.mockImplementation((params: any) =>
    params.group_by === 'type' ? Promise.resolve(typeRes) : Promise.resolve(trendRes)
  )
  exportCSVMock.mockReturnValue(undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与数据加载', () => {
  it('onMounted 加载列表并映射、统计透传', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(fundApiMock.list).toHaveBeenCalledWith({ page: 1, page_size: 200, fund_type: undefined })
    expect(fundApiMock.statisticsMultiDimension).toHaveBeenCalledWith(
      expect.objectContaining({ group_by: 'type' })
    )
    expect(fundApiMock.statisticsMultiDimension).toHaveBeenCalledWith(
      expect.objectContaining({ group_by: 'period', period_type: 'monthly' })
    )
    expect(vm.reportData).toHaveLength(2)
    expect(vm.reportData[0]).toEqual({
      date: '2024-01-15',
      projectName: '测试经费',
      fundType: 'project',
      amount: 100.5,
      used_amount: 40.25,
      balance: 60.25,
      usageRate: 40.05,
      unit: '财政拨款',
      manager: '张三',
      status: 'pending',
    })
    expect(vm.reportData[1].date).toBe('2024-02-01')
    expect(vm.reportData[1].fundType).toBe('operation')
    expect(vm.typeStatsData).toHaveLength(2)
    expect(vm.trendData).toHaveLength(2)
    expect(vm.loading).toBe(false)
  })

  it('list 无 items → 空数组；统计 success=false 不写入', async () => {
    fundApiMock.list.mockResolvedValue({})
    fundApiMock.statisticsMultiDimension.mockResolvedValue({ success: false, data: [] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.reportData).toEqual([])
    expect(vm.typeStatsData).toEqual([])
    expect(vm.trendData).toEqual([])
  })

  it('list 字段缺失走兜底（- / 0）', async () => {
    fundApiMock.list.mockResolvedValue({ items: [{}] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.reportData[0]).toEqual({
      date: '-',
      projectName: '-',
      fundType: '-',
      amount: 0,
      used_amount: 0,
      balance: 0,
      usageRate: 0,
      unit: '-',
      manager: '-',
      status: '-',
    })
  })

  it('amount>0 但 used_amount 缺失 → usageRate 走 || 0 兜底', async () => {
    fundApiMock.list.mockResolvedValue({ items: [{ id: 9, name: 'N', amount: 50 }] })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).reportData[0].usageRate).toBe(0)
  })

  it('统计 success=true 但 data 缺失 → || [] 兜底', async () => {
    fundApiMock.statisticsMultiDimension.mockResolvedValue({ success: true })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.typeStatsData).toEqual([])
    expect(vm.trendData).toEqual([])
  })

  it('loadReportData 异常 → logger.error 且 loading 复位', async () => {
    fundApiMock.list.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('带筛选条件（fundType + dateRange）时 params 传递', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.filterForm.fundType = 'project'
    vm.filterForm.dateRange = ['2024-01-01', '2024-02-01']
    fundApiMock.list.mockClear()
    fundApiMock.statisticsMultiDimension.mockClear()
    await vm.loadReportData()
    expect(fundApiMock.list).toHaveBeenCalledWith({
      page: 1,
      page_size: 200,
      fund_type: 'project',
    })
    expect(fundApiMock.statisticsMultiDimension).toHaveBeenCalledWith(
      expect.objectContaining({
        start_date: '2024-01-01',
        end_date: '2024-02-01',
        // 后端参数名是 fund_type；发 type 会被静默忽略（图形不随筛选变化）
        fund_type: 'project',
      })
    )
    expect(vm.reportPeriod).toBe('2024-01-01 至 2024-02-01')
  })

  it('选了日期区间 → 表格与合计只含区间内记录（表头周期与数据一致）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 2024-03-10 的记录在 [2024-01-01, 2024-02-01] 之外，必须被剔除，
    // 否则表头印「2024-01-01 至 2024-02-01」而合计含区间外数据。
    fundApiMock.list.mockResolvedValue({
      items: [
        fundRow,
        { ...fundRow2, created_at: '2024-03-10T08:00:00' },
      ],
      total: 2,
    })
    vm.filterForm.dateRange = ['2024-01-01', '2024-02-01']
    await vm.loadReportData()
    expect(vm.reportData).toHaveLength(1)
    expect(vm.reportData[0].date).toBe('2024-01-15')
    expect(vm.summary.total).toBe(100.5)
  })

  it('无日期的记录不因选了区间而消失', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fundApiMock.list.mockResolvedValue({
      items: [{ id: 9, name: '无日期经费', amount: 10, used_amount: 0 }],
      total: 1,
    })
    vm.filterForm.dateRange = ['2024-01-01', '2024-02-01']
    await vm.loadReportData()
    expect(vm.reportData).toHaveLength(1)
    expect(vm.reportData[0].date).toBe('-')
  })
})

describe('computed 汇总与周期', () => {
  it('summary 计算总额/已用/余额/平均使用率', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.summary.total).toBeCloseTo(300.5)
    expect(vm.summary.used).toBeCloseTo(140.25)
    expect(vm.summary.balance).toBeCloseTo(160.25)
    expect(vm.summary.avgUsageRate).toBeCloseTo(46.67)
  })

  it('summary 空数据 → 全 0', async () => {
    fundApiMock.list.mockResolvedValue({ items: [] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.summary.total).toBe(0)
    expect(vm.summary.used).toBe(0)
    expect(vm.summary.balance).toBe(0)
    expect(vm.summary.avgUsageRate).toBe(0)
  })

  it('reportPeriod 无日期范围 → 当前年月', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.filterForm.dateRange = []
    const now = new Date()
    expect(vm.reportPeriod).toBe(`${now.getFullYear()}年${now.getMonth() + 1}月`)
  })

  it('currentTime 格式化', async () => {
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).currentTime).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/)
  })
})

describe('图表 option', () => {
  it('fundTypeChart 有数据', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const opt = vm.fundTypeChart
    expect(opt.series[0].data).toEqual([
      { value: 100.5, name: '项目经费' },
      { value: 200, name: '运行经费' },
    ])
    expect(opt.title.text).toBe('经费类型分布')
  })

  it('fundTypeChart 无数据 → 暂无数据占位', async () => {
    fundApiMock.statisticsMultiDimension.mockResolvedValue({ success: true, data: [] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.fundTypeChart.series[0].data).toEqual([{ value: 0, name: '暂无数据' }])
  })

  it('usageTrendChart 有/无数据', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.usageTrendChart.xAxis.data).toEqual(['2024-01', '2024-02'])
    expect(vm.usageTrendChart.series[0].data).toEqual([100.5, 200])
    expect(vm.usageTrendChart.series[1].data).toEqual([40.25, 100])

    fundApiMock.statisticsMultiDimension.mockResolvedValue({ success: true, data: [] })
    const w2 = mountComp()
    await flushPromises()
    expect((w2.vm as any).usageTrendChart.xAxis.data).toEqual(['暂无'])
  })
})

describe('字典函数', () => {
  it('getFundTypeName/getStatusName 映射与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getFundTypeName('project')).toBe('项目经费')
    expect(vm.getFundTypeName('unknown')).toBe('unknown')
    expect(vm.getStatusName('pending')).toBe('待审批')
    expect(vm.getStatusName('unknown')).toBe('unknown')
  })

  it('getStatusType 全映射与 undefined', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getStatusType('pending')).toBe('info')
    expect(vm.getStatusType('approved')).toBe('success')
    expect(vm.getStatusType('allocated')).toBe('success')
    expect(vm.getStatusType('in_use')).toBe('warning')
    expect(vm.getStatusType('completed')).toBe('info')
    expect(vm.getStatusType('audited')).toBe('success')
    expect(vm.getStatusType('rejected')).toBe('danger')
    expect(vm.getStatusType('unknown')).toBeUndefined()
  })
})

describe('操作按钮', () => {
  it('生成报表按钮 → loadReportData 再次调用', async () => {
    const wrapper = mountComp()
    await flushPromises()
    fundApiMock.list.mockClear()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('生成报表'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    await flushPromises()
    expect(fundApiMock.list).toHaveBeenCalled()
  })

  it('筛选控件 v-model 更新（reportType/dateRange/fundType）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    for (const sel of wrapper.findAll('.el-select-stub')) {
      await sel.trigger('click')
    }
    const dp = wrapper.find('.el-date-picker-stub')
    await dp.trigger('click')
    await flushPromises()
    expect(vm.filterForm.reportType).toBe('x')
    expect(vm.filterForm.fundType).toBe('x')
    expect(vm.filterForm.dateRange).toEqual(['a', 'b'])
  })

  it('导出报表：有数据 → exportToCSV + 成功提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.exportReport()
    expect(exportCSVMock).toHaveBeenCalledWith(
      vm.reportData,
      '经费使用报表',
      expect.objectContaining({ date: '日期', status: '状态' })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('报表导出成功')
  })

  it('导出报表：无数据 → warning 不导出', async () => {
    fundApiMock.list.mockResolvedValue({ items: [] })
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).exportReport()
    expect(ElMessage.warning).toHaveBeenCalledWith('没有可导出的数据')
    expect(exportCSVMock).not.toHaveBeenCalled()
  })

  it('打印按钮 → window.print 调用（window.print spy 模拟）', async () => {
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).printReport()
    expect(printSpy).toHaveBeenCalled()
    printSpy.mockRestore()
  })
})
