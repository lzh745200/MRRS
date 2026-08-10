/**
 * views/dataManagement/Overview.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：fundsLabel 万/非万、formatTime 四分支、getCompletenessColor 三分支、
 * getModuleIcon 六映射+兜底、getModuleIconColor 两侧、getTrendType 三分支、
 * getActionIcon/getActionColor 六映射+兜底、navigateTo/handleModuleClick（已知/未知）、
 * loadOverview 成功（全字段/缺字段 ?? 兜底/默认填报率）与失败、
 * 模板：六个统计卡点击、刷新、查看更多、快捷操作、模块表行、日志列表（空/非空/状态标签）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { mockGet, pushSafeMock } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  pushSafeMock: vi.fn(),
}))

vi.mock('@/api/request', () => ({ get: mockGet,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
}))

import Overview from '@/views/dataManagement/Overview.vue'

const rowA = { module: '帮扶村', records: 10, lastUpdate: '2024-06-01 10:00:00', trend: 2, healthy: true }
const rowB = { module: '帮扶项目', records: 0, lastUpdate: 'None', trend: -1, healthy: false }
const rowC = { module: '帮扶学校', records: 5, lastUpdate: '', trend: 0, healthy: true }
const rowD = { module: '经费管理', records: 8, lastUpdate: 'invalid-date-str', trend: 3, healthy: false }
const rowE = { module: '用户管理', records: 3, lastUpdate: '2024-01-01', trend: -2, healthy: true }
const rowF = { module: '数据分析', records: 2, lastUpdate: null, trend: 5, healthy: true }
const rowG = { module: '未知模块', records: 1, lastUpdate: '2024-02-02', trend: 0, healthy: false }

const fullOverview = {
  villages: 120,
  projects: 30,
  schools: 15,
  funds_amount: 150000,
  users: 8,
  completeness: 96,
  modules: [],
  filing_rates: [{ module: '帮扶村', rate: 88 }],
  recent_logs: [
    { id: 1, action_type: 'create', action: '创建数据', user: '张三', time: '2024-06-01', status: 'success' },
    { id: 2, action_type: 'update', action: '更新数据', user: '李四', time: 'None', status: 'fail' },
    { id: 3, action_type: 'delete', action: '删除数据', user: '王五', time: '', status: 'success' },
    { id: 4, action_type: 'import', action: '导入数据', user: '赵六', time: 'invalid', status: 'fail' },
    { id: 5, action_type: 'export', action: '导出数据', user: '钱七', time: '2024-06-02', status: 'success' },
    { id: 6, action_type: 'backup', action: '备份数据', user: '孙八', time: '2024-06-03', status: 'fail' },
    { id: 7, action_type: 'weird', action: '其他', user: '周九', time: '2024-06-04', status: undefined },
  ],
}

function mountComp() {
  return mount(Overview, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
        },
        'el-table': { name: 'ElTable', template: '<div class="el-table-stub"><slot /></div>' },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /><slot :row="rowD" /><slot :row="rowE" /><slot :row="rowF" /><slot :row="rowG" /></div>',
          data() {
            return { rowA, rowB, rowC, rowD, rowE, rowF, rowG }
          },
        },
        'el-progress': {
          name: 'ElProgress',
          props: ['percentage'],
          template: '<div class="el-progress-stub"><slot :percentage="percentage" /></div>',
        },
        'el-empty': {
          name: 'ElEmpty',
          template: '<div class="el-empty-stub"><slot /></div>',
        },
        'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
        'el-icon': { name: 'ElIcon', template: '<span class="el-icon-stub"><slot /></span>' },
      },
    },
  })
}

const findBtn = (wrapper: any, text: string) => {
  const btn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes(text))
  expect(btn, text).toBeTruthy()
  return btn!
}

beforeEach(() => {
  vi.resetAllMocks()
  mockGet.mockResolvedValue({ data: fullOverview })
})

describe('挂载与加载', () => {
  it('onMounted 加载成功：统计卡、模块表、日志列表渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGet).toHaveBeenCalledWith('/statistics/overview')
    expect(vm.overview.villages).toBe(120)
    expect(vm.loading).toBe(false)
    const text = wrapper.text()
    expect(text).toContain('120')
    expect(text).toContain('15万') // fundsLabel
    expect(text).toContain('96.0%')
    expect(text).toContain('帮扶村')
    expect(text).toContain('88')
    expect(text).toContain('创建数据')
    expect(text).toContain('成功')
    expect(text).toContain('失败')
  })

  it('缺字段时 ?? 兜底与默认填报率；异常 → 保持默认', async () => {
    mockGet.mockResolvedValue({ data: { funds_amount: 5000 } })
    let wrapper = mountComp()
    await flushPromises()
    let vm = wrapper.vm as any
    expect(vm.overview.villages).toBe(0)
    expect(vm.overview.filing_rates).toHaveLength(4)
    expect(vm.fundsLabel).toBe('5000')

    mockGet.mockResolvedValue({ data: {} })
    wrapper = mountComp()
    await flushPromises()
    vm = wrapper.vm as any
    expect(vm.overview.funds_amount).toBe(0)
    expect(vm.overview.projects).toBe(0)

    mockGet.mockRejectedValue(new Error('net'))
    wrapper = mountComp()
    await flushPromises()
    vm = wrapper.vm as any
    expect(vm.overview.villages).toBe(0)
    expect(vm.loading).toBe(false)
  })
})

describe('计算属性与工具函数', () => {
  it('fundsLabel：>=10000 万元展示', async () => {
    mockGet.mockResolvedValue({ data: { funds_amount: 9999.5 } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.fundsLabel).toBe('9999.5')
    vm.overview.funds_amount = 150000
    expect(vm.fundsLabel).toBe('15万')
  })

  it('formatTime 四分支：空 / None / 非法字符串 / 合法日期', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatTime(null)).toBe('-')
    expect(vm.formatTime('None')).toBe('-')
    expect(vm.formatTime('not-a-date')).toBe('not-a-date')
    expect(vm.formatTime('2024-06-01T10:00:00')).not.toBe('-')
    // catch 分支：new Date(Symbol) 抛 TypeError → 原样返回
    const s = Symbol('sym')
    expect(vm.formatTime(s as any)).toBe(s)
  })

  it('getCompletenessColor 三分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getCompletenessColor(95)).toBe('#67c23a')
    expect(vm.getCompletenessColor(80)).toBe('#e6a23c')
    expect(vm.getCompletenessColor(50)).toBe('#f56c6c')
  })

  it('getModuleIcon 六映射 + 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    for (const m of ['帮扶村', '帮扶项目', '帮扶学校', '经费管理', '用户管理', '数据分析']) {
      expect(vm.getModuleIcon(m)).toBeTruthy()
    }
    expect(vm.getModuleIcon('不存在')).toBeTruthy()
  })

  it('getModuleIconColor：healthy 两侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getModuleIconColor({ healthy: true })).toBe('#67c23a')
    expect(vm.getModuleIconColor({ healthy: false })).toBe('#e6a23c')
  })

  it('getTrendType 三分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getTrendType(1)).toBe('success')
    expect(vm.getTrendType(-1)).toBe('danger')
    expect(vm.getTrendType(0)).toBe('info')
  })

  it('getActionIcon/getActionColor 六映射 + 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    for (const t of ['create', 'update', 'delete', 'import', 'export', 'backup']) {
      expect(vm.getActionIcon(t)).toBeTruthy()
      expect(vm.getActionColor(t)).toBeTruthy()
    }
    expect(vm.getActionIcon('x')).toBeTruthy()
    expect(vm.getActionColor('x')).toBe('#909399')
  })

  it('navigateTo 与 handleModuleClick（已知/未知）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.navigateTo('/villages')
    expect(pushSafeMock).toHaveBeenCalledWith('/villages')

    vm.handleModuleClick({ module: '帮扶村' })
    vm.handleModuleClick({ module: '帮扶项目' })
    vm.handleModuleClick({ module: '帮扶学校' })
    vm.handleModuleClick({ module: '经费管理' })
    vm.handleModuleClick({ module: '用户管理' })
    expect(pushSafeMock.mock.calls.length).toBe(6)
    vm.handleModuleClick({ module: '未知' })
    expect(pushSafeMock.mock.calls.length).toBe(6)
  })
})

describe('模板交互', () => {
  it('统计卡点击跳转（帮扶村/项目/学校/经费/质量）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const cards = wrapper.findAll('.stat-card')
    // 第 6 张卡（系统用户）无点击事件
    expect(cards.length).toBe(6)
    await cards[0].trigger('click')
    await cards[1].trigger('click')
    await cards[2].trigger('click')
    await cards[3].trigger('click')
    await cards[4].trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/villages')
    expect(pushSafeMock).toHaveBeenCalledWith('/projects')
    expect(pushSafeMock).toHaveBeenCalledWith('/schools')
    expect(pushSafeMock).toHaveBeenCalledWith('/funds')
    expect(pushSafeMock).toHaveBeenCalledWith('/data-management/quality')
  })

  it('快捷操作四按钮 + 查看更多', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const quick = wrapper.findAll('.quick-action-btn')
    expect(quick.length).toBe(4)
    for (const q of quick) {
      await q.trigger('click')
    }
    expect(pushSafeMock).toHaveBeenCalledWith('/data-entry/comprehensive')
    expect(pushSafeMock).toHaveBeenCalledWith('/data-import/batch')
    expect(pushSafeMock).toHaveBeenCalledWith('/data-management/backup')
    expect(pushSafeMock).toHaveBeenCalledWith('/data-management/quality')

    await findBtn(wrapper, '查看更多').trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/data-management/logs')
  })

  it('刷新按钮（模块卡头部）重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const base = mockGet.mock.calls.length
    const refresh = wrapper
      .findAll('el-button-stub')
      .find((b: any) => b.text().trim() === '')
    await refresh.trigger('click')
    await flushPromises()
    expect(mockGet.mock.calls.length).toBe(base + 1)
  })

  it('日志为空 → el-empty 占位；日志存在 → 状态标签 v-if 两侧', async () => {
    mockGet.mockResolvedValue({ data: { ...fullOverview, recent_logs: [] } })
    const w1 = mountComp()
    await flushPromises()
    expect(w1.find('.empty-placeholder').exists()).toBe(true)

    mockGet.mockResolvedValue({ data: fullOverview })
    const w2 = mountComp()
    await flushPromises()
    expect(w2.find('.logs-list').exists()).toBe(true)
    expect(w2.find('.empty-placeholder').exists()).toBe(false)
  })

  it('el-table 行点击触发 handleModuleClick（row-click 事件）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    wrapper.findAllComponents({ name: 'ElTable' })[0].vm.$emit('row-click', rowA)
    expect(pushSafeMock).toHaveBeenCalledWith('/villages')
  })

  it('el-progress dashboard 插槽 percentage 渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const progress = wrapper.findAllComponents({ name: 'ElProgress' })
    expect(progress.length).toBeGreaterThan(0)
    expect(wrapper.text()).toContain('96.0%') // dashboard 插槽 toFixed(1)
    expect(wrapper.text()).toContain('88%') // 填报进度插槽
  })
})

describe('响应形态收尾', () => {
  it('res.data 有值 → 解包使用', async () => {
    const wrapper = mountComp()
    await flushPromises()
    ;(mockGet as any).mockResolvedValueOnce({ data: { villages: 7 } })
    await (wrapper.vm as any).loadOverview()
    expect((wrapper.vm as any).overview.villages).toBe(7)
    wrapper.unmount()
  })
})
