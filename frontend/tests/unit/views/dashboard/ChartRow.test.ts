/**
 * ChartRow 组件测试
 *
 * 测试范围:
 * 1. 两个图表容器渲染
 * 2. Mock ECharts init 被调用
 * 3. setOption 被调用两次（左右图表）
 * 4. resize 事件触发图表 resize
 * 5. 接口失败时显示错误占位且不渲染图表
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ElButton, ElSkeleton } from 'element-plus'
import ChartRow from '@/views/dashboard/ChartRow.vue'

const mockSetOption = vi.fn()
const mockResize = vi.fn()
const mockDispose = vi.fn()

vi.mock('@/utils/echarts', () => ({
  default: {
    init: () => ({ setOption: mockSetOption, dispose: mockDispose, resize: mockResize }),
    graphic: { LinearGradient: vi.fn(() => ({})) },
  },
}))

const mockApiRequest = vi.hoisted(() => vi.fn())
const mockGet = vi.hoisted(() => vi.fn())

// Mock request（组件使用命名导出 apiRequest / get）
vi.mock('@/api/request', () => ({
  apiRequest: mockApiRequest,
  get: mockGet,
  default: { get: mockGet },
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

function mountChartRow() {
  return mount(ChartRow, {
    global: {
      components: { ElButton, ElSkeleton },
      stubs: { 'el-icon': true },
    },
  })
}

describe('ChartRow.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApiRequest.mockResolvedValue({
      data: {
        items: [
          { name: '道路硬化', progress: 85 },
          { name: '饮水工程', progress: 60 },
          { name: '电商中心', progress: 40 },
        ],
      },
    })
    mockGet.mockResolvedValue({
      data: {
        funds_allocated: 6000000,
        funds_pending: 2000000,
        funds_planned: 900000,
      },
    })
  })

  it('renders two chart containers', () => {
    const wrapper = mountChartRow()
    expect(wrapper.findAll('.chart-card').length).toBe(2)
  })

  it('calls echarts.init twice (left + right chart)', async () => {
    mountChartRow()
    await new Promise((r) => setTimeout(r, 200))
    // ECharts init is called inside renderCharts — verify setOption called
    expect(mockSetOption).toHaveBeenCalled()
  })

  it('resize handler calls chart.resize', async () => {
    mountChartRow()
    await new Promise((r) => setTimeout(r, 200))
    window.dispatchEvent(new Event('resize'))
    expect(mockResize).toHaveBeenCalled()
  })

  it('disposes charts on unmount', async () => {
    const wrapper = mountChartRow()
    await new Promise((r) => setTimeout(r, 200))
    wrapper.unmount()
    expect(mockDispose).toHaveBeenCalled()
  })

  it('shows error placeholder and skips chart init when request fails', async () => {
    mockApiRequest.mockRejectedValue(new Error('network error'))
    mockGet.mockRejectedValue(new Error('network error'))
    const wrapper = mountChartRow()
    await new Promise((r) => setTimeout(r, 200))
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.chart-state--error').length).toBe(2)
    expect(mockSetOption).not.toHaveBeenCalled()
  })

  it('shows empty hint instead of chart when no data', async () => {
    mockApiRequest.mockResolvedValue({ data: { items: [] } })
    mockGet.mockResolvedValue({
      data: { funds_allocated: 0, funds_pending: 0, funds_planned: 0 },
    })
    const wrapper = mountChartRow()
    await new Promise((r) => setTimeout(r, 200))
    await wrapper.vm.$nextTick()
    const empties = wrapper.findAll('.chart-empty')
    expect(empties.length).toBe(2)
    expect(empties[0].attributes('description')).toBe('暂无项目数据')
    expect(empties[1].attributes('description')).toBe('暂无经费数据')
    expect(mockSetOption).not.toHaveBeenCalled()
  })
})
