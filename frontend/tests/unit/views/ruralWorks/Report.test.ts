/**
 * views/ruralWorks/Report.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 加载、年份/日期范围筛选、statusType 全分支、exportCSV、
 * 加载失败（detail/message/兜底）、空数据提示、模板渲染。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { ElMessage, getMock } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  getMock: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/request', () => ({ get: getMock,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import Report from '@/views/ruralWorks/Report.vue'

const reportData = {
  summary: { total: 10, completed: 5, inProgress: 3, delayed: 2 },
  items: [
    { title: '道路', type: '基建', status: 'completed', village_name: '村A', start_date: '2024-01-01', end_date: '2024-02-01' },
    { title: '教育', type: '教育', status: 'in_progress', village_name: '村B', start_date: '2024-01-15', end_date: '2024-03-01' },
    { title: '医疗', type: '医疗', status: 'delayed', village_name: '村C', start_date: '2024-02-01', end_date: '2024-04-01' },
    { title: '其他', type: '其他', status: 'pending', village_name: '村D', start_date: '2024-02-15', end_date: '2024-05-01' },
  ],
}

function mountComp() {
  return mount(Report, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
        'el-form': { template: '<div class="el-form-stub"><slot /></div>' },
        'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
        'el-select': {
          template:
            '<div class="el-select-stub" @click="$emit(\'update:modelValue\', 2023); $emit(\'change\')"><slot /></div>',
        },
        'el-option': { template: '<div class="el-option-stub" />' },
        'el-date-picker': {
          template:
            '<div class="el-date-picker-stub" @click="$emit(\'update:modelValue\', [\'2024-01-01\', \'2024-06-30\'])" />',
        },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-icon': { template: '<span class="el-icon-stub" />' },
        'el-table': {
          template:
            '<div class="el-table-stub"><slot name="default" /></div>',
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /><slot :row="rowD" /></div>',
          data() {
            return {
              rowA: { title: '道路', type: '基建', status: 'completed', village_name: '村A' },
              rowB: { title: '教育', type: '教育', status: 'in_progress', village_name: '村B' },
              rowC: { title: '医疗', type: '医疗', status: 'delayed', village_name: '村C' },
              rowD: { title: '其他', type: '其他', status: 'pending', village_name: '村D' },
            }
          },
        },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-empty': {
          template: '<div class="el-empty-stub">{{ description }}<slot /></div>',
          props: ['description'],
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  getMock.mockResolvedValue({ data: reportData })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与数据加载', () => {
  it('onMounted 自动生成报告', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(getMock).toHaveBeenCalledWith(
      '/rural-works/report/generate',
      expect.objectContaining({ year: expect.any(Number) })
    )
    expect(vm.reportData.summary.total).toBe(10)
    expect(vm.items).toHaveLength(4)
    expect(vm.loading).toBe(false)
  })

  it('res 无 data 直返格式', async () => {
    getMock.mockResolvedValue(reportData)
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).reportData.summary.total).toBe(10)
  })

  it('works 字段兜底', async () => {
    getMock.mockResolvedValue({ data: { summary: {}, works: [{ title: 'W' }] } })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).items).toHaveLength(1)
  })

  it('空数据 → info 提示', async () => {
    getMock.mockResolvedValue({ data: { summary: {}, items: [] } })
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.info).toHaveBeenCalledWith('暂无符合条件的报告数据')
  })

  it('加载失败 detail/message/兜底', async () => {
    getMock.mockRejectedValueOnce({ response: { data: { detail: '生成失败' } } })
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('生成失败')

    getMock.mockRejectedValueOnce({ response: { data: { message: '服务错误' } } })
    await (wrapper.vm as any).loadReport()
    expect(ElMessage.error).toHaveBeenCalledWith('服务错误')

    getMock.mockRejectedValueOnce(new Error('网络错误'))
    await (wrapper.vm as any).loadReport()
    expect(ElMessage.error).toHaveBeenCalledWith('网络错误')

    getMock.mockRejectedValueOnce({})
    await (wrapper.vm as any).loadReport()
    expect(ElMessage.error).toHaveBeenCalledWith('报告生成失败')

    getMock.mockRejectedValueOnce({ response: { data: { detail: { x: 1 } } } })
    await (wrapper.vm as any).loadReport()
    expect(ElMessage.error).toHaveBeenCalledWith('报告生成失败，请稍后重试')
  })
})

describe('筛选与导出', () => {
  it('年份/日期范围参数传递', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.filterForm.year = 2022
    vm.filterForm.dateRange = ['2024-01-01', '2024-06-30']
    getMock.mockClear()
    await vm.loadReport()
    expect(getMock).toHaveBeenCalledWith(
      '/rural-works/report/generate',
      expect.objectContaining({ year: 2022, start_date: '2024-01-01', end_date: '2024-06-30' })
    )
  })

  it('年份 select change → loadReport', async () => {
    const wrapper = mountComp()
    await flushPromises()
    getMock.mockClear()
    await wrapper.find('.el-select-stub').trigger('click')
    await flushPromises()
    expect((wrapper.vm as any).filterForm.year).toBe(2023)
    expect(getMock).toHaveBeenCalledWith(
      '/rural-works/report/generate',
      expect.objectContaining({ year: 2023 })
    )
  })

  it('日期选择器 v-model', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.el-date-picker-stub').trigger('click')
    expect((wrapper.vm as any).filterForm.dateRange).toEqual(['2024-01-01', '2024-06-30'])
  })

  it('生成报告按钮 → loadReport', async () => {
    const wrapper = mountComp()
    await flushPromises()
    getMock.mockClear()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('生成报告'))
    await btn!.trigger('click')
    await flushPromises()
    expect(getMock).toHaveBeenCalled()
  })

  it('exportCSV 无数据 → 直接返回', async () => {
    getMock.mockResolvedValue({ data: { summary: {}, items: [] } })
    const wrapper = mountComp()
    await flushPromises()
    const clickSpy = vi.spyOn(HTMLElement.prototype, 'click').mockImplementation(() => {})
    ;(wrapper.vm as any).exportCSV()
    expect(clickSpy).not.toHaveBeenCalled()
    clickSpy.mockRestore()
  })

  it('exportCSV 有数据 → 下载 CSV', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const clickSpy = vi.spyOn(HTMLElement.prototype, 'click').mockImplementation(() => {})
    ;(wrapper.vm as any).exportCSV()
    expect(clickSpy).toHaveBeenCalled()
    clickSpy.mockRestore()
  })

  it('导出 CSV 按钮（有数据时可用）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const clickSpy = vi.spyOn(HTMLElement.prototype, 'click').mockImplementation(() => {})
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('导出 CSV'))
    await btn!.trigger('click')
    expect(clickSpy).toHaveBeenCalled()
    clickSpy.mockRestore()
  })
})

describe('字典与模板', () => {
  it('statusType 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.statusType('completed')).toBe('success')
    expect(vm.statusType('in_progress')).toBe('warning')
    expect(vm.statusType('delayed')).toBe('danger')
    expect(vm.statusType('pending')).toBe('info')
  })

  it('统计卡片与明细渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await nextTick()
    expect(wrapper.text()).toContain('10')
    expect(wrapper.text()).toContain('5')
    expect(wrapper.text()).toContain('3')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('工作明细')
    expect(wrapper.text()).toContain('completed')
  })

  it('空态渲染', async () => {
    getMock.mockResolvedValue(null)
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).reportData).toBeNull()
    expect(wrapper.find('.el-empty-stub').exists()).toBe(true)
  })

  it('yearOptions 生成（滚动窗口：当前年-10 ~ 当前年+10）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const cur = new Date().getFullYear()
    expect(vm.yearOptions).toHaveLength(21)
    expect(vm.yearOptions[0]).toBe(cur + 10)
    expect(vm.yearOptions[vm.yearOptions.length - 1]).toBe(cur - 10)
    expect(vm.yearOptions).toContain(cur)
  })
})
