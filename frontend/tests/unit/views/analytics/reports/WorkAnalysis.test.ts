/**
 * WorkAnalysis.vue (工作分析报告) 组件测试
 *
 * 覆盖目标：src/views/analytics/reports/WorkAnalysis.vue 100% 语句覆盖
 *
 * 测试场景：
 *  1. 挂载加载 — onMounted → loadData → updateCharts（chart.js 全 mock）
 *  2. 统计卡片 — statsCards 计算（有/无数据、延期/无延期分支）
 *  3. 表格过滤 — searchText / filterType / filterStatus 三个 if 分支 + watch
 *  4. filterTable — keyup.enter / clear / select change / 分页事件触发
 *  5. 刷新 — refreshData（按钮 + 日期范围 change）
 *  6. 导出 — 空数据 warning 分支 / CSV 生成下载分支
 *  7. 图表 — updateCharts 三图构建、月度趋势过滤（有/无日期、完成状态）、
 *     destroyCharts 空与非空、onBeforeUnmount
 *  8. 辅助函数 — getTypeTagType / getStatusTagType / ds 调用（表格列模板渲染）
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia } from 'pinia'

// ==================== Mocks ====================

vi.mock('chart.js/auto', () => {
  class MockChart {
    static instances: MockChart[] = []
    config: any
    destroyed = false
    constructor(_ctx: any, config: any) {
      this.config = config
      MockChart.instances.push(this)
    }
    destroy() {
      this.destroyed = true
    }
  }
  return { Chart: MockChart }
})

vi.mock('@/api/ruralWork', () => ({
  getRuralWorks: vi.fn(),
}))

vi.mock('@/composables/useDesensitize', () => ({
  useDesensitize: () => ({
    ds: (value: any) => String(value ?? ''),
  }),
}))

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal<any>()
  return {
    ...actual,
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
    },
  }
})

import WorkAnalysis from '@/views/analytics/reports/WorkAnalysis.vue'
import { getRuralWorks } from '@/api/ruralWork'
import { ElMessage } from 'element-plus'
import { Chart } from 'chart.js/auto'

// MockChart 静态实例记录（每个用例前重置）
const chartInstances = () => (Chart as any).instances as any[]

// ==================== Helpers ====================

const now = new Date()
const pad = (n: number) => String(n).padStart(2, '0')
const thisMonthDate = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-15`

/** 覆盖各映射/过滤分支的样本数据 */
const makeItems = (): any[] => [
  {
    id: 1,
    name: '道路修建',
    type: 'infrastructure',
    village_name: '幸福村',
    responsible_person: '张三',
    status: 'completed',
    progress: 100,
    start_date: thisMonthDate,
    end_date: thisMonthDate,
  },
  {
    id: 2,
    name: '产业扶持',
    type: 'industry',
    village_name: '团结村',
    responsible_person: '李四',
    status: 'in_progress',
    progress: 65,
    start_date: thisMonthDate,
  },
  {
    id: 3,
    name: '医疗帮扶',
    type: 'healthcare',
    village_name: '和平村',
    responsible_person: '王五',
    status: 'delayed',
    progress: 30,
    // 无日期字段 → 月度过滤 if (!created) 分支
  },
  {
    id: 4,
    name: '环保项目',
    type: 'environment',
    village_name: '青山村',
    responsible_person: '赵六',
    status: 'planned',
    progress: 0,
    created_at: '2000-01-01', // 非当前年度 → 月份不匹配分支
  },
  {
    id: 5,
    name: '其他工作',
    type: 'unknown_type', // 映射兜底 || item.type
    status: 'weird_status', // statusCounts[d.status] === undefined 分支
    progress: undefined, // export 中 ?? 0
  },
]

const stubs = {
  'el-date-picker': {
    name: 'ElDatePickerStub',
    props: ['modelValue'],
    emits: ['update:modelValue', 'change'],
    template:
      '<button class="dp-trigger" @click="$emit(\'update:modelValue\', [\'2024-01-01\', \'2024-12-31\']); $emit(\'change\')"></button>',
  },
  'el-button': {
    name: 'ElButtonStub',
    emits: ['click'],
    template: '<button @click="$emit(\'click\')"><slot /></button>',
  },
  'el-input': {
    name: 'ElInputStub',
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
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
  // el-table / el-table-column：渲染默认插槽并注入样本行，覆盖列模板语句
  'el-table': {
    name: 'ElTableStub',
    props: ['data'],
    template: '<div class="el-table-stub"><slot /></div>',
  },
  'el-table-column': {
    name: 'ElTableColumnStub',
    data() {
      return {
        row: {
          type: 'industry',
          typeName: '产业发展',
          responsible_person: '张三',
          status: 'completed',
          statusName: '已完成',
          progress: 100,
        },
      }
    },
    template: '<div class="el-table-column-stub"><slot :row="row" /></div>',
  },
  'el-pagination': {
    name: 'ElPaginationStub',
    props: ['currentPage', 'pageSize', 'total'],
    emits: ['size-change', 'current-change', 'update:currentPage', 'update:pageSize'],
    template:
      '<div class="el-pagination-stub"><button class="size-change" @click="$emit(\'size-change\', 20)"></button><button class="current-change" @click="$emit(\'current-change\', 2)"></button></div>',
  },
  'el-tag': {
    name: 'ElTagStub',
    props: ['type'],
    template: '<span class="el-tag-stub"><slot /></span>',
  },
  'el-progress': {
    name: 'ElProgressStub',
    props: ['percentage', 'status'],
    template: '<div class="el-progress-stub"></div>',
  },
}

const mountPage = () =>
  mount(WorkAnalysis, {
    global: {
      plugins: [createPinia()],
      stubs,
      renderStubDefaultSlot: true,
    },
  })

const findPagination = (wrapper: any) =>
  wrapper.findComponent({ name: 'ElPaginationStub' })

// ==================== Tests ====================

describe('WorkAnalysis.vue (analytics/reports)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    chartInstances().length = 0
    vi.mocked(getRuralWorks).mockResolvedValue({ items: makeItems() } as any)
  })

  it('挂载后加载数据、渲染统计卡片并创建三个图表', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(getRuralWorks).toHaveBeenCalledWith({ limit: 100 })

    const text = wrapper.text()
    expect(text).toContain('工作总数')
    expect(text).toContain('进行中')
    expect(text).toContain('已完成')
    expect(text).toContain('平均进度')
    // delayed=1 → '1项延期' 分支
    expect(text).toContain('1项延期')
    // 占比/完成率（total>0 分支）
    expect(text).toContain('占比 20%')
    expect(text).toContain('完成率 20%')

    // 三个 Chart.js 图表已创建
    expect(chartInstances().length).toBe(3)

    // 分页总数经 watch 同步
    expect(findPagination(wrapper).props('total')).toBe(5)
    wrapper.unmount()
  })

  it('空数据时统计卡片走 total=0 兜底分支', async () => {
    vi.mocked(getRuralWorks).mockResolvedValue({ items: [] } as any)
    const wrapper = mountPage()
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('占比 0%')
    expect(text).toContain('完成率 0%')
    expect(text).toContain('无延期')
    expect(findPagination(wrapper).props('total')).toBe(0)
    wrapper.unmount()
  })

  it('接口返回结构异常时 allData 置空', async () => {
    vi.mocked(getRuralWorks).mockResolvedValue(null as any)
    const wrapper = mountPage()
    await flushPromises()

    expect(findPagination(wrapper).props('total')).toBe(0)
    wrapper.unmount()
  })

  it('加载失败时提示错误', async () => {
    vi.mocked(getRuralWorks).mockRejectedValue(new Error('接口异常'))
    const wrapper = mountPage()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('接口异常')
    wrapper.unmount()
  })

  it('点击刷新按钮重新加载并提示成功', async () => {
    const wrapper = mountPage()
    await flushPromises()
    vi.mocked(getRuralWorks).mockClear()

    const refreshBtn = wrapper.findAll('button').find((b) => b.text().includes('刷新'))!
    await refreshBtn.trigger('click')
    await flushPromises()

    expect(getRuralWorks).toHaveBeenCalledTimes(1)
    expect(ElMessage.success).toHaveBeenCalledWith('数据已刷新')
    wrapper.unmount()
  })

  it('日期范围变化触发刷新', async () => {
    const wrapper = mountPage()
    await flushPromises()
    vi.mocked(getRuralWorks).mockClear()

    await wrapper.find('.dp-trigger').trigger('click')
    await flushPromises()

    expect(getRuralWorks).toHaveBeenCalledTimes(1)
    expect(ElMessage.success).toHaveBeenCalledWith('数据已刷新')
    wrapper.unmount()
  })

  it('搜索文本过滤表格数据', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const input = wrapper.find('input')
    await input.setValue('道路')
    await nextTick()

    expect(findPagination(wrapper).props('total')).toBe(1)
    wrapper.unmount()
  })

  it('按负责人姓名搜索（responsible_person 匹配分支）', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('input').setValue('李四')
    await nextTick()

    expect(findPagination(wrapper).props('total')).toBe(1)
    wrapper.unmount()
  })

  it('工作类型与状态筛选', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const selects = wrapper.findAll('select')
    await selects[0].setValue('industry')
    await nextTick()
    expect(findPagination(wrapper).props('total')).toBe(1)

    // filterType 命中后再叠加 filterStatus（无匹配）
    await selects[1].setValue('completed')
    await nextTick()
    expect(findPagination(wrapper).props('total')).toBe(0)

    // 清空类型 → 仅剩状态过滤
    await selects[0].setValue('')
    await nextTick()
    expect(findPagination(wrapper).props('total')).toBe(1)
    wrapper.unmount()
  })

  it('输入框 keyup.enter 与 clear 事件触发 filterTable', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const input = wrapper.find('input')
    await input.setValue('道路')
    await input.trigger('keyup', { key: 'Enter' })
    await input.trigger('clear')
    // 不抛错即覆盖 filterTable 两条事件路径
    expect(wrapper.exists()).toBe(true)
    wrapper.unmount()
  })

  it('分页 size-change / current-change 触发 filterTable', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('.size-change').trigger('click')
    await wrapper.find('.current-change').trigger('click')
    expect(wrapper.exists()).toBe(true)
    wrapper.unmount()
  })

  it('无数据时导出提示警告', async () => {
    vi.mocked(getRuralWorks).mockResolvedValue({ items: [] } as any)
    const wrapper = mountPage()
    await flushPromises()

    const exportBtn = wrapper.findAll('button').find((b) => b.text().includes('导出报告'))!
    await exportBtn.trigger('click')

    expect(ElMessage.warning).toHaveBeenCalledWith('没有可导出的数据')
    wrapper.unmount()
  })

  it('有数据时导出生成 CSV 下载', async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountPage()
    await flushPromises()

    const exportBtn = wrapper.findAll('button').find((b) => b.text().includes('导出报告'))!
    await exportBtn.trigger('click')

    expect(clickSpy).toHaveBeenCalledTimes(1)
    expect(ElMessage.warning).not.toHaveBeenCalled()
    clickSpy.mockRestore()
    wrapper.unmount()
  })

  it('再次刷新时先销毁旧图表实例', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const instances = chartInstances()
    const firstBatch = instances.slice(0, 3)

    await wrapper.find('.dp-trigger').trigger('click')
    await flushPromises()

    expect(firstBatch.every((c) => c.destroyed)).toBe(true)
    expect(instances.length).toBe(6)
    wrapper.unmount()
  })

  it('卸载时销毁全部图表', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const instances = chartInstances()

    wrapper.unmount()

    expect(instances.every((c) => c.destroyed)).toBe(true)
  })
})

describe('分支补全：进度三元/映射兜底/分页 v-model/导出稀疏行', () => {
  it('进度列三种状态色 + 类型/状态标签映射兜底（模板三元与 || 回退）', async () => {
    // 列样本行：progress 100/65/30 覆盖三元三侧；未知 type/status 覆盖 map || 回退
    const wrapper = mount(WorkAnalysis, {
      global: {
        plugins: [createPinia()],
        stubs: {
          ...stubs,
          'el-table-column': {
            name: 'ElTableColumnStub',
            data() {
              return {
                rows: [
                  { type: 'unknown_t', typeName: 'X', status: 'unknown_s', statusName: 'Y', progress: 100, responsible_person: 'p' },
                  { type: 'industry', typeName: 'X', status: 'completed', statusName: 'Y', progress: 65, responsible_person: 'p' },
                  { type: 'industry', typeName: 'X', status: 'planned', statusName: 'Y', progress: 30, responsible_person: 'p' },
                ],
              }
            },
            template: '<div class="el-table-column-stub"><slot v-for="r in rows" :key="r.progress" :row="r" /></div>',
          },
        },
        renderStubDefaultSlot: true,
      },
    })
    await flushPromises()
    expect(wrapper.find('.el-table-column-stub').exists()).toBe(true)
    wrapper.unmount()
  })

  it('getTypeTagType / getStatusTagType 未知值 → info 兜底', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getTypeTagType('nope')).toBe('info')
    expect(vm.getStatusTagType('nope')).toBe('info')
    wrapper.unmount()
  })

  it('updateCharts 类型为空字符串 → 其他 兜底', async () => {
    vi.mocked(getRuralWorks).mockResolvedValue({
      items: [{ id: 1, name: 'X', type: '', status: 'completed', progress: 50, start_date: thisMonthDate }],
    } as any)
    const wrapper = mountPage()
    await flushPromises()
    // updateCharts 会被 watch 多次触发，取首个饼图实例校验（type '' → '其他' 计入）
    expect(chartInstances().length).toBeGreaterThanOrEqual(3)
    // 全量跑时其他用例的滞后异步链可能向 instances 追加旧图表，按类型+标签断言而非下标
    const pies = chartInstances().filter((c: any) => c.config.type === 'doughnut')
    const hit = pies.some((p: any) => (p.config.data.labels || []).includes('其他'))
    expect(hit).toBe(true)
    wrapper.unmount()
  })

  it('分页 v-model 双向绑定处理器', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    const pager = findPagination(wrapper)
    pager.vm.$emit('update:currentPage', 2)
    pager.vm.$emit('update:pageSize', 20)
    expect(vm.currentPage).toBe(2)
    expect(vm.pageSize).toBe(20)
    wrapper.unmount()
  })

  it('导出稀疏行：name/type/village_name 等全字段 || 兜底', async () => {
    vi.mocked(getRuralWorks).mockResolvedValue({ items: [{ id: 1 }] } as any)
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountPage()
    await flushPromises()
    const exportBtn = wrapper.findAll('button').find((b) => b.text().includes('导出报告'))!
    await exportBtn.trigger('click')
    expect(clickSpy).toHaveBeenCalledTimes(1)
    expect(ElMessage.warning).not.toHaveBeenCalled()
    clickSpy.mockRestore()
    wrapper.unmount()
  })
})
