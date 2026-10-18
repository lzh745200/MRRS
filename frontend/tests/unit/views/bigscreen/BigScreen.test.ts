import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const mocks = vi.hoisted(() => ({
  getDashboardStats: vi.fn(),
  getYearlyTrends: vi.fn(),
  getRankings: vi.fn(),
  projectList: vi.fn(),
  ElMessage: { warning: vi.fn(), success: vi.fn(), error: vi.fn() },
}))

vi.mock('@/api/dashboard', () => ({
  getDashboardStats: mocks.getDashboardStats,
  getYearlyTrends: mocks.getYearlyTrends,
}))

vi.mock('@/api/effectiveness', () => ({
  getRankings: mocks.getRankings,
}))

vi.mock('@/api/projects', () => ({
  projectApi: { list: mocks.projectList },
}))

vi.mock('element-plus', () => ({
  ElMessage: mocks.ElMessage,
}))

vi.mock('@/components/common/BaseChart.vue', () => ({
  default: { name: 'BaseChart', template: '<div class="chart-stub" />' },
}))

import BigScreen from '@/views/bigscreen/BigScreen.vue'
import { BIGSCREEN_CONFIG_KEY } from '@/views/bigscreen/bigscreenConfig'

// 局部桩：设置抽屉 / 开关 / 频率单选 / 按钮需要渲染插槽并主动 emit，
// 否则 v-model 产物与 @click 内联处理器永远不可达（functions 覆盖率缺口）。
const settingsStubs = {
  'el-button': {
    props: ['disabled'],
    emits: ['click'],
    template:
      '<button type="button" class="el-button-stub" :data-disabled="String(disabled)"' +
      ' @click="$emit(\'click\')"><slot /></button>',
  },
  'el-drawer': {
    props: ['modelValue', 'title'],
    emits: ['update:modelValue'],
    template:
      '<div class="el-drawer-stub" :data-open="String(modelValue)" :data-title="title">' +
      '<button type="button" class="drawer-close" @click="$emit(\'update:modelValue\', false)">x</button>' +
      '<slot /></div>',
  },
  'el-switch': {
    props: ['modelValue'],
    emits: ['update:modelValue', 'change'],
    template:
      '<button type="button" class="el-switch-stub" :data-on="String(modelValue)"' +
      ' @click="$emit(\'update:modelValue\', !modelValue); $emit(\'change\', !modelValue)" />',
  },
  'el-radio-group': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<div class="el-radio-group-stub" :data-value="String(modelValue)">' +
      '<button type="button" class="radio-60" @click="$emit(\'update:modelValue\', 60)">60</button>' +
      '<button type="button" class="radio-off" @click="$emit(\'update:modelValue\', 0)">off</button>' +
      '<slot /></div>',
  },
  'el-radio-button': {
    props: ['value'],
    template: '<span class="el-radio-button-stub"><slot /></span>',
  },
}

function mountComp() {
  return mount(BigScreen, {
    attachTo: document.body,
    global: { stubs: { ...settingsStubs } },
  })
}

describe('BigScreen.vue（帮扶成效大屏）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    // 真实后端契约（/dashboard/stats 返回体）：此前 mock 编造了
    // completion_rate/total_amount/by_status 等后端不存在的字段，
    // 导致测试全绿但真实大屏 KPI 恒 0、状态饼图恒空
    mocks.getDashboardStats.mockResolvedValue({
      total_villages: 12,
      total_projects: 34,
      total_schools: 5,
      data_completeness: 0.886,
      total_funds: 1234000,
      projects_by_status: { completed: 10, active: 8 },
    })
    mocks.getYearlyTrends.mockResolvedValue({
      trends: [
        { year: 2024, total_planned: 100, total_actual: 80, project_count: 5 },
        { year: 2025, total_planned: 120, total_actual: 110, project_count: 8 },
      ],
    })
    mocks.getRankings.mockResolvedValue({
      year: 2026,
      rankings: [
        { village_name: '甲村', score: 92 },
        { village_name: '乙村', score: 85 },
      ],
    })
    mocks.projectList.mockResolvedValue({
      items: [
        { id: 1, name: '示范项目甲', responsible_person: '张三' },
        { id: 2, name: '示范项目乙', responsible_person: '李四' },
      ],
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  it('挂载加载数据并渲染 KPI 与图表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    // 轮询走后端缓存：不传 refresh=true（缓存击穿修复）
    expect(mocks.getDashboardStats).toHaveBeenCalledWith()
    expect(mocks.getYearlyTrends).toHaveBeenCalledWith(5)
    expect(mocks.getRankings).toHaveBeenCalled()
    expect(wrapper.text()).toContain('帮扶成效总览大屏')
    const vm = wrapper.vm as any
    expect(vm.kpis.length).toBe(5)
    expect(vm.kpis[1].value).toBe(34)
    expect(wrapper.findAll('.chart-stub').length).toBe(4)
    wrapper.unmount()
  })

  it('契约对齐：KPI 使用真实后端字段（data_completeness/total_funds）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 完成率：data_completeness 0.886 → 88.6%
    expect(vm.kpis[3]).toEqual({ label: '完成率', value: '88.6%' })
    // 经费总额：total_funds 已是万元（SUM(Fund.amount)），不得再除 10000
    expect(vm.kpis[4]).toEqual({ label: '经费总额(万)', value: 1234000 })
    // 项目状态分布：读 stats.projects_by_status
    expect(vm.projectStatusOption.series[0].data).toEqual([
      { name: '已完成', value: 10 },
      { name: '进行中', value: 8 },
    ])
    wrapper.unmount()
  })

  it('接口失败静默降级（KPI 默认 0）', async () => {
    mocks.getDashboardStats.mockRejectedValue(new Error('net'))
    mocks.getYearlyTrends.mockRejectedValue(new Error('net'))
    mocks.getRankings.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.kpis[0].value).toBe(0)
    expect(vm.rankings).toEqual([])
    expect(vm.yearlyOption.series[0].data).toEqual([])
    wrapper.unmount()
  })

  it('stats 为空时各 computed 走 ?? {} 兜底（不抛错、返回空结构）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 后端无数据时 getDashboardStats 返回 null → stats 为 nullish
    vm.stats = null
    await nextTick()
    expect(vm.kpis.length).toBe(5)
    expect(vm.kpis[0].value).toBe(0)
    // projects_by_status 缺失 → 饼图空数据（此前该兜底分支无覆盖）
    expect(vm.projectStatusOption.series[0].data).toEqual([])
    wrapper.unmount()
  })

  it('时钟每秒更新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const before = vm.clock
    expect(before).toMatch(/^\d{4}-\d{2}-\d{2}/)
    vi.advanceTimersByTime(1000)
    expect(vm.clock).toMatch(/^\d{4}-\d{2}-\d{2}/)
    wrapper.unmount()
  })

  it('图表 computed: 排名/项目状态/年度数据组装', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 排名条形图
    expect(vm.rankOption.yAxis.data).toContain('甲村')
    expect(vm.rankOption.series[0].data).toContain(92)
    // 项目状态饼图
    expect(vm.projectStatusOption.series[0].data.length).toBe(2)
    // 年度柱状图
    expect(vm.yearlyOption.xAxis.data).toContain(2025)
    expect(vm.yearlyOption.series[0].data).toEqual([5, 8])
    // 经费趋势
    expect(vm.fundTrendOption.series.length).toBe(2)
    wrapper.unmount()
  })

  it('状态图对未知状态键回退显示原始键', async () => {
    mocks.getDashboardStats.mockResolvedValue({ projects_by_status: { weird: 3 } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.projectStatusOption.series[0].data[0].name).toBe('weird')
    wrapper.unmount()
  })

  it('全屏切换与 fullscreenchange 监听', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // requestFullscreen mock
    const origReq = document.documentElement.requestFullscreen
    const origExit = document.exitFullscreen
    ;(document.documentElement as any).requestFullscreen = vi.fn(() => Promise.resolve())
    ;(document as any).exitFullscreen = vi.fn(() => Promise.resolve())
    Object.defineProperty(document, 'fullscreenElement', { value: null, configurable: true, writable: true })
    vm.toggleFullscreen()
    expect(vm.isFullscreen).toBe(true)
    ;(document as any).fullscreenElement = document.documentElement
    document.dispatchEvent(new Event('fullscreenchange'))
    await nextTick()
    expect(vm.isFullscreen).toBe(true)
    vm.toggleFullscreen()
    expect(vm.isFullscreen).toBe(false)
    ;(document as any).fullscreenElement = null
    document.dispatchEvent(new Event('fullscreenchange'))
    await nextTick()
    expect(vm.isFullscreen).toBe(false)
    ;(document.documentElement as any).requestFullscreen = origReq
    ;(document as any).exitFullscreen = origExit
    wrapper.unmount()
  })

  it('卸载时清理定时器', async () => {
    const wrapper = mountComp()
    await flushPromises()
    wrapper.unmount()
    vi.advanceTimersByTime(1000) // 不应报错
  })

  it('字段缺失形态：?? 链全部走兜底侧（直接改写 ref 值）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // stats 为 null → stats.value ?? {} 兜底 → KPI 全 0 / 完成率 '—'
    vm.stats = null
    expect(vm.kpis.map((k: any) => k.value)).toEqual([0, 0, 0, '—', 0])
    // yearlyTrends 为 null → ?? [] 兜底
    vm.yearlyTrends = null
    expect(vm.fundTrendOption.xAxis.data).toEqual([])
    expect(vm.fundTrendOption.series[0].data).toEqual([])
    expect(vm.yearlyOption.xAxis.data).toEqual([])
    // rankings 为 null → ?? [] 兜底
    vm.rankings = null
    expect(vm.rankOption.yAxis.data).toEqual([])
    // stats 无 projects_by_status → ?? {} 兜底 → 空饼图
    vm.stats = {}
    expect(vm.projectStatusOption.series[0].data).toEqual([])
    // 年度数据：year 缺失 + planned/actual/count 两级 ?? 兜底
    vm.yearlyTrends = [
      { planned: 50, actual: 40, count: 5 }, // year 缺 → ''；total_planned 缺 → planned；total_actual 缺 → actual；project_count 缺 → count
      { year: 2026 }, // planned/actual/count 全缺 → 0
    ]
    expect(vm.fundTrendOption.xAxis.data).toEqual(['', 2026])
    expect(vm.fundTrendOption.series[0].data).toEqual([50, 0])
    expect(vm.fundTrendOption.series[1].data).toEqual([40, 0])
    expect(vm.yearlyOption.series[0].data).toEqual([5, 0])
    // 排名：village_name/name/village_id 三级 ?? 兜底 + score/total_score 两级 ?? 兜底
    vm.rankings = [
      { name: '甲', total_score: 9 },
      { village_id: 'v1' },
      {},
    ]
    expect(vm.rankOption.yAxis.data).toEqual(['甲', 'v1', ''])
    expect(vm.rankOption.series[0].data).toEqual([9, 0, 0])
    // 状态图：计数为 0 → Number(v) || 0 兜底
    vm.stats = { projects_by_status: { completed: 0, active: 8 } }
    expect(vm.projectStatusOption.series[0].data).toEqual([
      { name: '已完成', value: 0 },
      { name: '进行中', value: 8 },
    ])
    wrapper.unmount()
  })

  it('loadAll：接口全部返回 null → 静默兜底空对象/空数组', async () => {
    mocks.getDashboardStats.mockResolvedValue(null)
    mocks.getYearlyTrends.mockResolvedValue(null)
    mocks.getRankings.mockResolvedValue(null)
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.stats).toEqual({})
    expect(vm.yearlyTrends).toEqual([])
    expect(vm.rankings).toEqual([])
    wrapper.unmount()
  })

  it('rankings 数组直返 / items 旧格式兼容（Array.isArray 与双字段兜底）', async () => {
    // 数组直返
    mocks.getRankings.mockResolvedValue([{ village_name: '丙村', score: 77 }])
    let wrapper = mountComp()
    await flushPromises()
    let vm = wrapper.vm as any
    expect(vm.rankings).toEqual([{ village_name: '丙村', score: 77 }])
    expect(vm.rankOption.yAxis.data).toContain('丙村')
    wrapper.unmount()
    // items 旧格式（历史客户端兼容）
    mocks.getRankings.mockResolvedValue({ items: [{ village_name: '丁村', score: 66 }] })
    wrapper = mountComp()
    await flushPromises()
    vm = wrapper.vm as any
    expect(vm.rankings).toEqual([{ village_name: '丁村', score: 66 }])
    expect(vm.rankOption.yAxis.data).toContain('丁村')
    wrapper.unmount()
  })

  it('yearlyTrends 数组直返兼容', async () => {
    mocks.getYearlyTrends.mockResolvedValue([{ year: 2023, total_planned: 60 }])
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.yearlyTrends).toEqual([{ year: 2023, total_planned: 60 }])
    expect(vm.fundTrendOption.xAxis.data).toContain(2023)
    wrapper.unmount()
  })

  it('年度对比图：project_count 缺失时回退 fund_count/count（语义对齐真实项目数）', async () => {
    mocks.getYearlyTrends.mockResolvedValue({
      trends: [
        { year: 2026, fund_count: 7 },
        { year: 2027, count: 4 },
        { year: 2028 },
      ],
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.yearlyOption.series[0].data).toEqual([7, 4, 0])
    wrapper.unmount()
  })

  it('rankings 返回无 rankings/items 字段的对象 → 空数组兜底（不崩溃）', async () => {
    mocks.getRankings.mockResolvedValue({ error: 'no data' })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.rankings).toEqual([])
    expect(vm.rankOption.yAxis.data).toEqual([])
    wrapper.unmount()
  })

  // ─────────────────────────────────────────────
  // 010：大屏可配置（卡片取舍/顺序、刷新频率、汇报脱敏）
  // 注意：必须嵌套在本 describe 内，复用其 beforeEach（fake timers + 默认 mock）
  // ─────────────────────────────────────────────
  describe('大屏设置（010）', () => {
  function findButton(wrapper: any, text: string) {
    return wrapper.findAll('.el-button-stub').find((b: any) => b.text().includes(text))
  }

  function savedConfig() {
    return JSON.parse(localStorage.getItem(BIGSCREEN_CONFIG_KEY) as string)
  }

  it('设置抽屉：打开/关闭、卡片显示开关、顺序调整与持久化', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    const trigger = findButton(wrapper, '设置')
    expect(trigger).toBeTruthy()
    await trigger!.trigger('click')
    expect(vm.settingsVisible).toBe(true)
    expect(wrapper.find('.el-drawer-stub').attributes('data-open')).toBe('true')
    expect(wrapper.find('.el-drawer-stub').attributes('data-title')).toBe('大屏设置')

    // 5 张卡片开关 + 1 个脱敏开关
    const switches = wrapper.findAll('.el-switch-stub')
    expect(switches.length).toBe(6)

    // 隐藏「经费执行趋势」→ 图表少一张、配置写回 localStorage
    await switches[0].trigger('click')
    await flushPromises()
    expect(vm.config.cards[0].visible).toBe(false)
    expect(vm.visibleCards.map((c: any) => c.key)).not.toContain('fundTrend')
    expect(wrapper.findAll('.chart-stub').length).toBe(3)
    expect(savedConfig().cards[0].visible).toBe(false)

    // 下移第一张卡片 → 顺序交换
    let rows = wrapper.findAll('.settings-card-row')
    await rows[0].findAll('.el-button-stub')[1].trigger('click')
    await flushPromises()
    expect(vm.config.cards.map((c: any) => c.key).slice(0, 2)).toEqual(['rank', 'fundTrend'])
    expect(savedConfig().cards.map((c: any) => c.key).slice(0, 2)).toEqual(['rank', 'fundTrend'])

    // 「经费执行趋势」上移回第一位；再触发首行上移/末行下移的越界守卫
    rows = wrapper.findAll('.settings-card-row')
    await rows[1].findAll('.el-button-stub')[0].trigger('click')
    await flushPromises()
    expect(vm.config.cards[0].key).toBe('fundTrend')
    rows = wrapper.findAll('.settings-card-row')
    await rows[0].findAll('.el-button-stub')[0].trigger('click')
    await rows[rows.length - 1].findAll('.el-button-stub')[1].trigger('click')
    expect(vm.config.cards[0].key).toBe('fundTrend')

    // 关闭抽屉
    await wrapper.find('.drawer-close').trigger('click')
    expect(vm.settingsVisible).toBe(false)
    wrapper.unmount()
  })

  it('刷新频率：默认 30s；改 60s 后按新周期轮询；关闭自动刷新不产生任何轮询请求', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const calls = () => mocks.getDashboardStats.mock.calls.length

    expect(document.body.textContent).toContain('数据每 30 秒自动刷新')
    const initial = calls()
    vi.advanceTimersByTime(30000)
    await flushPromises()
    expect(calls()).toBe(initial + 1)

    // 切到 60 秒
    await wrapper.find('.radio-60').trigger('click')
    await flushPromises()
    expect((wrapper.vm as any).config.refreshInterval).toBe(60)
    expect(savedConfig().refreshInterval).toBe(60)
    const afterSwitch = calls()
    vi.advanceTimersByTime(30000)
    await flushPromises()
    expect(calls()).toBe(afterSwitch)
    vi.advanceTimersByTime(30000)
    await flushPromises()
    expect(calls()).toBe(afterSwitch + 1)

    // 关闭自动刷新：推进 5 分钟也不应产生轮询
    await wrapper.find('.radio-off').trigger('click')
    await flushPromises()
    expect((wrapper.vm as any).config.refreshInterval).toBe(0)
    expect(wrapper.text()).toContain('自动刷新已关闭')
    const offCount = calls()
    vi.advanceTimersByTime(300000)
    await flushPromises()
    expect(calls()).toBe(offCount)
    wrapper.unmount()
  })

  it('汇报脱敏：隐藏金额精度与负责人姓名，刷新后保持', async () => {
    mocks.getDashboardStats.mockResolvedValue({ total_villages: 1, total_funds: 1234000.567 })
    mocks.getYearlyTrends.mockResolvedValue({
      trends: [{ year: 2026, total_planned: 100.6, total_actual: 88.4, project_count: 3 }],
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 非脱敏：保留 2 位小数精度，负责人姓名原样展示
    expect(vm.kpis[4].value).toBe(1234000.57)
    expect(vm.fundTrendOption.series[0].data).toEqual([100.6])
    expect(wrapper.find('.leader-person').text()).toBe('张三')

    await wrapper.findAll('.el-switch-stub')[5].trigger('click')
    await flushPromises()
    expect(vm.config.desensitized).toBe(true)
    expect(savedConfig().desensitized).toBe(true)
    // 脱敏：金额隐藏小数精度、负责人姓名打码
    expect(vm.kpis[4].value).toBe(1234001)
    expect(vm.fundTrendOption.series[0].data).toEqual([101])
    expect(wrapper.find('.leader-person').text()).toBe('张*')
    expect(wrapper.text()).toContain('汇报脱敏模式')

    // 刷新（重新挂载）后配置仍保持
    wrapper.unmount()
    const remount = mountComp()
    await flushPromises()
    expect((remount.vm as any).config.desensitized).toBe(true)
    expect(remount.find('.leader-person').text()).toBe('张*')
    remount.unmount()
  })

  it('恢复默认：卡片全显示、30s、非脱敏，并重建轮询', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await wrapper.find('.radio-off').trigger('click')
    await wrapper.findAll('.el-switch-stub')[0].trigger('click')
    await wrapper.findAll('.el-switch-stub')[5].trigger('click')
    await flushPromises()
    expect(vm.config.refreshInterval).toBe(0)
    expect(vm.config.desensitized).toBe(true)

    await findButton(wrapper, '恢复默认')!.trigger('click')
    await flushPromises()
    expect(vm.config.refreshInterval).toBe(30)
    expect(vm.config.desensitized).toBe(false)
    expect(vm.config.cards.every((c: any) => c.visible)).toBe(true)

    const before = mocks.getDashboardStats.mock.calls.length
    vi.advanceTimersByTime(30000)
    await flushPromises()
    expect(mocks.getDashboardStats.mock.calls.length).toBe(before + 1)
    wrapper.unmount()
  })

  it('负责人卡片数据形态：数组直返 / items / 信封 data.items / null 兜底', async () => {
    mocks.projectList.mockResolvedValue([{ id: 1, name: '项目甲', responsible_person: '李四' }])
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).leaderRows).toEqual([{ id: 1, project: '项目甲', person: '李四' }])
    wrapper.unmount()

    mocks.projectList.mockResolvedValue({ items: [{ id: 2, name: '项目乙' }] })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).leaderRows[0]).toMatchObject({ project: '项目乙', person: '—' })
    wrapper.unmount()

    mocks.projectList.mockResolvedValue({ data: { items: [{ id: 3 }] } })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).leaderRows[0]).toMatchObject({ project: '—' })
    wrapper.unmount()

    mocks.projectList.mockResolvedValue(null)
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).projects).toEqual([])
    expect(wrapper.findAll('.leader-item').length).toBe(0)
    // 防御：projects 被置空（null/undefined）时 computed 兜底空数组
    ;(wrapper.vm as any).projects = null
    expect((wrapper.vm as any).leaderRows).toEqual([])
    wrapper.unmount()
  })

  it('四个数据接口全部失败 → 提示一次（failedCount === 4 分支）', async () => {
    mocks.getDashboardStats.mockRejectedValue(new Error('x'))
    mocks.getYearlyTrends.mockRejectedValue(new Error('x'))
    mocks.getRankings.mockRejectedValue(new Error('x'))
    mocks.projectList.mockRejectedValue(new Error('x'))
    const wrapper = mountComp()
    await flushPromises()
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('大屏数据加载失败，请检查服务连接')
    wrapper.unmount()
  })
  })
})
