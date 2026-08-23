/**
 * views/schools/Analysis.vue 覆盖率攻坚
 * 覆盖：统计卡片渲染、状态/地区分布聚合、接口异常处理。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('@/components/common/BaseChart.vue', () => ({
  default: {
    name: 'BaseChart',
    template: '<div class="base-chart-stub" />',
    props: ['option', 'height'],
  },
}))

vi.mock('@/components/common/StatsCard.vue', () => ({
  default: {
    name: 'StatsCard',
    template: '<div class="stats-card-stub" />',
    props: ['title', 'value', 'type'],
  },
}))

vi.mock('@/api/schools', () => ({
  schoolsApi: {
    getStatistics: vi.fn(),
    list: vi.fn(),
  },
}))

import Analysis from '@/views/schools/Analysis.vue'
import { schoolsApi } from '@/api/schools'

const statsData = {
  data: {
    total_schools: 12,
    active: 8,
    completed: 3,
    total_students: 1200,
    total_teachers: 60,
    project_count: 5,
    project_total_budget: 100000,
    scholarship_count: 20,
    scholarship_total_amount: 50000,
  },
}

const listData = {
  data: {
    items: [
      { support_status: 'active', district: '都匀市' },
      { support_status: 'active', district: '都匀市' },
      { support_status: 'completed', district: '福泉市' },
      { support_status: 'pending', district: '福泉市' },
      { support_status: 'pending' },
    ],
  },
}

function mountAnalysis() {
  return mount(Analysis, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
        'el-row': { template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { template: '<div class="el-col-stub"><slot /></div>' },
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('schools/Analysis.vue', () => {
  it('渲染统计卡片与图表', async () => {
    vi.mocked(schoolsApi.getStatistics).mockResolvedValue(statsData as never)
    vi.mocked(schoolsApi.list).mockResolvedValue(listData as never)

    const wrapper = mountAnalysis()
    await flushPromises()

    expect(wrapper.text()).toContain('学校分析')
    expect(wrapper.findAll('.stats-card-stub')).toHaveLength(8)
    expect(wrapper.findAll('.base-chart-stub')).toHaveLength(2)
    expect(schoolsApi.getStatistics).toHaveBeenCalled()
    expect(schoolsApi.list).toHaveBeenCalled()
  })

  it('聚合状态与地区分布', async () => {
    vi.mocked(schoolsApi.getStatistics).mockResolvedValue(statsData as never)
    vi.mocked(schoolsApi.list).mockResolvedValue(listData as never)

    const wrapper = mountAnalysis()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.statusDist).toEqual({ active: 2, completed: 1, pending: 2 })
    expect(vm.regionDist['都匀市']).toBe(2)
    expect(vm.regionDist['福泉市']).toBe(2)
    expect(vm.regionDist['未知']).toBe(1)

    const pieData = vm.statusOption.series[0].data
    expect(pieData).toContainEqual({ name: '帮扶中', value: 2 })
    const barData = vm.regionOption.series[0].data
    expect(barData).toContain(2)
  })

  it('统计卡片格式化(预算万元/金额千分位)', async () => {
    vi.mocked(schoolsApi.getStatistics).mockResolvedValue(statsData as never)
    vi.mocked(schoolsApi.list).mockResolvedValue(listData as never)

    const wrapper = mountAnalysis()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.budget).toBe('10')
    expect(vm.scholarshipAmount).toContain('50,000')
  })

  it('接口失败时给出错误提示且不崩溃', async () => {
    vi.mocked(schoolsApi.getStatistics).mockRejectedValue(new Error('network') as never)

    const wrapper = mountAnalysis()
    await flushPromises()

    expect(wrapper.text()).toContain('学校分析')
    const vm = wrapper.vm as any
    expect(vm.stats.total_schools).toBe(0)
  })

  it('无数据时分布为空', async () => {
    vi.mocked(schoolsApi.getStatistics).mockResolvedValue({ data: {} } as never)
    vi.mocked(schoolsApi.list).mockResolvedValue({ data: { items: [] } } as never)

    const wrapper = mountAnalysis()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.statusOption.series[0].data).toEqual([])
    expect(vm.regionOption.series[0].data).toEqual([])
  })


  it('分支补齐: 未知状态/地区兜底与多形态响应', async () => {
    vi.mocked(schoolsApi.getStatistics).mockResolvedValue({} as never)
    vi.mocked(schoolsApi.list).mockResolvedValue({
      data: { items: [{ support_status: 'custom_x', district: '荔波县' }, { status: 'active', county: '三都县' }, {}] },
    } as never)

    const wrapper = mountAnalysis()
    await flushPromises()

    const vm = wrapper.vm as any
    // 未知状态 → 原样 key; 未知地区 → '未知'
    expect(vm.statusDist['custom_x']).toBe(1)
    expect(vm.statusDist['active']).toBe(1)
    expect(vm.regionDist['荔波县']).toBe(1)
    expect(vm.regionDist['三都县']).toBe(1)
    expect(vm.regionDist['未知']).toBe(1)
    // 无 data 时兜底
    const pie = vm.statusOption.series[0].data
    expect(Array.isArray(pie)).toBe(true)
    wrapper.unmount()
  })


  it('响应多形态: 全空/直接 items/无 data', async () => {
    vi.mocked(schoolsApi.getStatistics).mockResolvedValue(undefined as never)
    vi.mocked(schoolsApi.list).mockResolvedValue({
      items: [{ support_status: 'active' }],
    } as never)

    const wrapper = mountAnalysis()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.stats.total_schools).toBe(0)
    expect(vm.statusDist['active']).toBe(1)
    // list 全空形态 → 空分布且不崩溃
    vi.mocked(schoolsApi.list).mockResolvedValue(undefined as never)
    await vm.loadData()
    expect(vm.statusDist).toEqual({})
    expect(vm.statusOption.series[0].data).toEqual([])
    wrapper.unmount()
  })
})
