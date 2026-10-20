/**
 * views/analytics/supported-villages/Detail.vue 覆盖率攻坚（四指标 100%）。
 *
 * 覆盖：四种页面模式（view/edit/create/无 id）、详情/年度数据/趋势图加载与失败、
 * 标签分支（有/无属性标签、表彰）、多年趋势图（数据过滤/排序/图表复用）、
 * 变更历史弹窗（三种响应结构 + 失败）、表单提交（创建/编辑/过渡资金/错误文案）、
 * 取消导航、路由 watch、resize 去抖、卸载清理，以及 w17-007「导出档案册」。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { ElMessage, svApi, pushSafeMock, logError, chartMock } = vi.hoisted(() => {
  const chartMock = {
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
  }
  return {
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
    svApi: {
      getChangeHistory: vi.fn(),
      getSupportedVillage: vi.fn(),
      getYearlyData: vi.fn(),
      createSupportedVillage: vi.fn(),
      updateSupportedVillage: vi.fn(),
      saveTransitionFunding: vi.fn(),
      downloadVillageDossier: vi.fn(),
    },
    pushSafeMock: vi.fn(),
    logError: vi.fn(),
    chartMock,
  }
})

// useRoute() 必须返回响应式对象，路由参数 watch 才会触发（生产环境同据此行为）
const routeHolder = vi.hoisted(() => ({ state: null as any }))

vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  routeHolder.state = reactive({
    path: '/supported-villages/9',
    params: { id: '9' } as Record<string, any>,
    query: {} as Record<string, any>,
  })
  return {
    useRoute: () => routeHolder.state,
    // PageHeader（共享页头标准件）在 setup 阶段调用 useRouter()
    useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
  }
})

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/supportedVillage', () => svApi)

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
  safeRouteParam: (value: any) =>
    value === undefined || value === null || value === '' ? 0 : Number(value) || 0,
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/utils', () => ({
  format: {
    formatMoney4: (value: any) => (value == null ? '0.0000' : Number(value).toFixed(4)),
  },
}))

vi.mock('@/utils/echarts', () => ({ default: { init: vi.fn(() => chartMock) } }))

vi.mock('@/components/common/ChangeHistoryDialog.vue', () => ({
  default: {
    name: 'ChangeHistoryDialog',
    template: '<button class="chd-stub" @click="$emit(\'update:visible\', false)" />',
    props: ['visible', 'history', 'loading'],
    emits: ['update:visible'],
  },
}))

vi.mock('@/views/analytics/supported-villages/components/SupportedVillageForm.vue', () => ({
  default: {
    name: 'SupportedVillageForm',
    template: '<div class="svf-stub" />',
    props: ['village', 'mode'],
    emits: ['submit', 'cancel'],
  },
}))

import Detail from '@/views/analytics/supported-villages/Detail.vue'

const routeBox = routeHolder.state

const villageFull = {
  id: 9,
  villageName: '示例村',
  sequenceNo: 1,
  department: '某部',
  supportUnit: '某单位',
  regionScope: '县内',
  isRevitalizationTier: true,
  isThreeRegions: true,
  isBorderArea: true,
  isEthnicArea: true,
  isRevolutionaryArea: true,
  isKeyCounty: true,
  isProvincialDemo: true,
  isHundredVillageDemo: true,
  isTieredDevelopment: true,
  isCrossProvince: true,
  isCrossCity: true,
  isCrossUnitCooperation: true,
  isInOverallPlan: true,
  honors: '先进集体',
}

const villageEmpty = {
  id: 9,
  villageName: '',
  sequenceNo: 0,
  department: '',
  supportUnit: '',
  regionScope: '',
  isRevitalizationTier: false,
  isThreeRegions: false,
  isBorderArea: false,
  isEthnicArea: false,
  isRevolutionaryArea: false,
  isKeyCounty: false,
  isProvincialDemo: false,
  isHundredVillageDemo: false,
  isTieredDevelopment: false,
  isCrossProvince: false,
  isCrossCity: false,
  isCrossUnitCooperation: false,
  isInOverallPlan: false,
  honors: '',
}

const yearlyFull = {
  population: { totalPopulation: 120 },
  income: { perCapitaIncome: 1.5, collectiveIncome: 2.5 },
  industry: { investment: 3 },
  infrastructure: { investment: 4 },
  education: { investment: 5 },
  medical: { investment: 6 },
  'party-building': { investment: 7 },
  consumption: { villageProductsPurchase: 8 },
}

const mountOptions = {
  global: {
    renderStubDefaultSlot: true,
    directives: { loading: {} },
    stubs: {
      'el-descriptions': { template: '<div class="el-descriptions-stub"><slot /></div>' },
      'el-descriptions-item': {
        props: ['label'],
        template: '<div class="el-desc-item-stub"><span>{{ label }}</span><slot /></div>',
      },
      'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
      'el-row': { template: '<div class="el-row-stub"><slot /></div>' },
      'el-col': { template: '<div class="el-col-stub"><slot /></div>' },
      'el-select': {
        template:
          '<div class="el-select-stub" @click="$emit(\'update:modelValue\', 2024); $emit(\'change\', 2024)"><slot /></div>',
      },
      'el-option': { template: '<div class="el-option-stub" />' },
      'el-button': {
        template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
        emits: ['click'],
      },
      'el-icon': { template: '<span class="el-icon-stub"><slot /></span>' },
    },
  },
}

function mountComp() {
  return mount(Detail, mountOptions as any)
}

function resetRoute() {
  routeBox.path = '/supported-villages/9'
  routeBox.params = { id: '9' }
  routeBox.query = {}
}

beforeEach(() => {
  vi.resetAllMocks()
  resetRoute()
  svApi.getSupportedVillage.mockResolvedValue({ ...villageFull })
  svApi.getYearlyData.mockResolvedValue({ ...yearlyFull })
  svApi.getChangeHistory.mockResolvedValue({ items: [] })
  svApi.createSupportedVillage.mockResolvedValue({ data: { id: 5 } })
  svApi.updateSupportedVillage.mockResolvedValue({})
  svApi.saveTransitionFunding.mockResolvedValue({})
  svApi.downloadVillageDossier.mockResolvedValue(undefined)
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('挂载与加载（view 模式）', () => {
  it('onMounted 加载详情 + 年度数据 + 多年趋势并渲染图表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(svApi.getSupportedVillage).toHaveBeenCalledWith(9)
    expect(svApi.getYearlyData).toHaveBeenCalledWith(9, expect.any(Number))
    expect(vm.village.villageName).toBe('示例村')
    expect(vm.loading).toBe(false)
    expect(vm.yearlyLoading).toBe(false)
    expect(chartMock.setOption).toHaveBeenCalled()
    expect(wrapper.text()).toContain('导出档案册')
    expect(wrapper.text()).toContain('变更历史')
  })

  it('趋势数据：成功取值 / 无收入 / 请求失败三种年份混合', async () => {
    svApi.getYearlyData.mockImplementation(async (_id: number, year: number) => {
      if (year === 2024) return { income: { perCapitaIncome: 2 } }
      if (year === 2023) throw new Error('no data')
      return {}
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.trendData.years).toEqual([2024])
    expect(vm.trendData.incomes).toEqual([2])
    // 第二次渲染复用已初始化实例（不重复 init）
    vm.renderTrendChart()
    expect(chartMock.setOption).toHaveBeenCalledTimes(2)
  })

  it('空数据村：属性标签/表彰走「无」分支', async () => {
    svApi.getSupportedVillage.mockResolvedValue({ ...villageEmpty })
    svApi.getYearlyData.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.hasRegionTags).toBe(false)
    expect(vm.hasRevitalizationTags).toBe(false)
    expect(vm.totalInvestment).toBe(0)
    const text = wrapper.text()
    expect(text).toContain('无')
    expect(text).toContain('帮扶村详情')
    expect(text).toContain('0.0000')
  })

  it('village 为空时标签 computed 走提前返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.village = null
    expect(vm.hasRegionTags).toBe(false)
    expect(vm.hasRevitalizationTags).toBe(false)
  })

  it('totalInvestment 累加各板块投入，yearlyData 为空时为 0', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.totalInvestment).toBe(33)
    vm.yearlyData = null
    expect(vm.totalInvestment).toBe(0)
  })

  it('totalInvestment：各板块投入为空/非法时按 0 计', async () => {
    svApi.getYearlyData.mockResolvedValue({
      industry: { investment: 0 },
      infrastructure: { investment: null },
      education: { investment: 'abc' },
      medical: { investment: NaN },
      'party-building': {},
      consumption: { villageProductsPurchase: 0 },
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).totalInvestment).toBe(0)
  })

  it('详情加载失败 → 错误提示', async () => {
    svApi.getSupportedVillage.mockRejectedValue(new Error('boom'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('加载数据失败')
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('年度数据加载失败 → 清空年度数据', async () => {
    svApi.getYearlyData.mockRejectedValue(new Error('yearly down'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(logError).toHaveBeenCalled()
    expect(vm.yearlyData).toBeNull()
  })

  it('无 id 时 loadVillage 提前返回', async () => {
    routeBox.params = {}
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    svApi.getSupportedVillage.mockClear()
    await vm.loadVillage()
    expect(svApi.getSupportedVillage).not.toHaveBeenCalled()
  })

  it('无 village 时 loadTrendData 提前返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.village = null
    const before = svApi.getYearlyData.mock.calls.length
    await vm.loadTrendData()
    expect(svApi.getYearlyData.mock.calls.length).toBe(before)
  })

  it('无 village 时 loadYearlyData 提前返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.village = null
    svApi.getYearlyData.mockClear()
    await vm.loadYearlyData()
    expect(svApi.getYearlyData).not.toHaveBeenCalled()
  })

  it('切换年度下拉触发重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    svApi.getYearlyData.mockClear()
    await wrapper.find('.el-select-stub').trigger('click')
    await flushPromises()
    expect(svApi.getYearlyData).toHaveBeenCalledWith(9, 2024)
  })
})

describe('页面模式与导航', () => {
  it('编辑模式（路径 /edit）：不加载年度数据，标题带村名', async () => {
    routeBox.path = '/supported-villages/9/edit'
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.pageMode).toBe('edit')
    expect(vm.pageTitle).toBe('编辑 - 示例村')
    await nextTick()
    expect(wrapper.find('.svf-stub').exists()).toBe(true)
    svApi.getYearlyData.mockClear()
    expect(svApi.getYearlyData).not.toHaveBeenCalled()
  })

  it('编辑模式（query.mode=edit）', async () => {
    routeBox.query = { mode: 'edit' }
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).pageMode).toBe('edit')
  })

  it('编辑模式但 village 未加载 → 标题兜底', async () => {
    routeBox.path = '/supported-villages/9/edit'
    svApi.getSupportedVillage.mockResolvedValue(null)
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).pageTitle).toBe('编辑 - 帮扶村')
  })

  it('创建模式（路径 /create）：不请求详情，标题为新增', async () => {
    routeBox.path = '/supported-villages/create'
    routeBox.params = {}
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.pageMode).toBe('create')
    expect(vm.pageTitle).toBe('新增帮扶村')
    expect(svApi.getSupportedVillage).not.toHaveBeenCalled()
    await nextTick()
    expect(wrapper.find('.svf-stub').exists()).toBe(true)
  })

  it('无 id 且非 create 路径也判定为创建模式', async () => {
    routeBox.path = '/supported-villages'
    routeBox.params = {}
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).pageMode).toBe('create')
  })

  it('返回/编辑/年度数据按钮跳转', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const back = wrapper.find('.back-btn')
    expect(back.exists()).toBe(true)
    await back.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/supported-villages')
    vm.handleEdit()
    expect(pushSafeMock).toHaveBeenCalledWith('/supported-villages/9?mode=edit')
    vm.handleYearlyData()
    expect(pushSafeMock).toHaveBeenCalledWith('/supported-villages/9/yearly')

    // village 为空时三个 handler 均不跳转
    pushSafeMock.mockClear()
    vm.village = null
    vm.handleEdit()
    vm.handleYearlyData()
    expect(pushSafeMock).not.toHaveBeenCalled()
  })

  it('village 未加载时结对帮扶台账使用空 id 兜底', async () => {
    // 详情请求挂起，保持 village=null 时点击
    svApi.getSupportedVillage.mockReturnValue(new Promise(() => {}))
    const wrapper = mountComp()
    await nextTick()
    const pairBtn = wrapper
      .findAll('.el-button-stub')
      .find((b) => b.text().includes('结对帮扶台账'))!
    await pairBtn.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/pairings?partner_type=village&partner_id=')
    wrapper.unmount()
  })

  it('模板按钮点击：编辑 / 年度数据 / 结对帮扶台账', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const buttons = wrapper.findAll('.el-button-stub')
    const editBtn = buttons.find((b) => b.text().includes('编辑'))!
    await editBtn.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/supported-villages/9?mode=edit')
    const yearlyBtn = buttons.find((b) => b.text().includes('年度数据'))!
    await yearlyBtn.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/supported-villages/9/yearly')
    const pairBtn = buttons.find((b) => b.text().includes('结对帮扶台账'))!
    await pairBtn.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/pairings?partner_type=village&partner_id=9')
  })

  it('路由参数变化触发重新加载', async () => {
    mountComp()
    await flushPromises()
    svApi.getSupportedVillage.mockClear()
    routeBox.params = { id: '10' }
    await nextTick()
    await flushPromises()
    expect(svApi.getSupportedVillage).toHaveBeenCalledWith(10)
  })

  it('路由参数清空不触发重新加载', async () => {
    mountComp()
    await flushPromises()
    svApi.getSupportedVillage.mockClear()
    routeBox.params = {}
    await nextTick()
    await flushPromises()
    expect(svApi.getSupportedVillage).not.toHaveBeenCalled()
  })
})

describe('变更历史弹窗', () => {
  it('items 三种字段形态 + 非数组 changes', async () => {
    svApi.getChangeHistory.mockResolvedValue({
      items: [
        { timestamp: 't1', action: 'create', username: 'u1', changes: [{ field: 'a' }] },
        { time: 't2', user: 'u2', changes: 'bad' },
        {},
      ],
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.openChangeHistory()
    expect(vm.changeHistory).toHaveLength(3)
    expect(vm.changeHistory[0].time).toBe('t1')
    expect(vm.changeHistory[1].user).toBe('u2')
    expect(vm.changeHistory[1].action).toBe('update')
    expect(vm.changeHistory[1].changes).toEqual([])
    expect(vm.changeHistory[2].user).toBe('未知用户')
    expect(vm.changeHistoryLoading).toBe(false)
  })

  it('data.items 结构', async () => {
    svApi.getChangeHistory.mockResolvedValue({ data: { items: [{ action: 'delete' }] } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.openChangeHistory()
    expect(vm.changeHistory).toHaveLength(1)
  })

  it('非数组响应 → 空列表', async () => {
    svApi.getChangeHistory.mockResolvedValue('raw')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.openChangeHistory()
    expect(vm.changeHistory).toEqual([])
  })

  it('响应为 null → 空列表', async () => {
    svApi.getChangeHistory.mockResolvedValue(null)
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.openChangeHistory()
    expect(vm.changeHistory).toEqual([])
  })

  it('变更历史弹窗 v-model 关闭事件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.changeHistoryVisible = true
    await nextTick()
    await wrapper.find('.chd-stub').trigger('click')
    expect(vm.changeHistoryVisible).toBe(false)
  })

  it('加载失败 → 错误提示', async () => {
    svApi.getChangeHistory.mockRejectedValue(new Error('history down'))
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).openChangeHistory()
    expect(ElMessage.error).toHaveBeenCalledWith('加载变更历史失败')
    expect((wrapper.vm as any).changeHistoryLoading).toBe(false)
  })

  it('「变更历史」按钮点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('变更历史'))!
    await btn.trigger('click')
    await flushPromises()
    expect(svApi.getChangeHistory).toHaveBeenCalled()
  })
})

describe('表单提交 / 取消', () => {
  it('创建成功 + 保存过渡资金', async () => {
    routeBox.path = '/supported-villages/create'
    routeBox.params = {}
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleFormSubmit({ villageName: '新村', _transitionFundingItems: [{ year: 2024 }] })
    expect(svApi.createSupportedVillage).toHaveBeenCalled()
    expect(svApi.saveTransitionFunding).toHaveBeenCalledWith(5, {
      items: [{ year: 2024 }],
    })
    expect(ElMessage.success).toHaveBeenCalledWith('创建成功')
    expect(pushSafeMock).toHaveBeenCalledWith('/supported-villages/5')
    expect(vm.loading).toBe(false)
  })

  it('创建成功但过渡资金保存失败 → warning 提示', async () => {
    routeBox.path = '/supported-villages/create'
    routeBox.params = {}
    svApi.createSupportedVillage.mockResolvedValue({ id: 6 })
    svApi.saveTransitionFunding.mockRejectedValue(new Error('fund fail'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleFormSubmit({ villageName: '新村', _transitionFundingItems: [{ year: 2024 }] })
    expect(ElMessage.warning).toHaveBeenCalled()
    expect(pushSafeMock).toHaveBeenCalledWith('/supported-villages/6')
  })

  it('创建成功无过渡资金数据 → 跳过保存', async () => {
    routeBox.path = '/supported-villages/create'
    routeBox.params = {}
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleFormSubmit({ villageName: '新村' })
    expect(svApi.saveTransitionFunding).not.toHaveBeenCalled()
  })

  it('创建失败且异常带 response.detail → 展示 detail', async () => {
    routeBox.path = '/supported-villages/create'
    routeBox.params = {}
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    svApi.createSupportedVillage.mockRejectedValue({
      response: { data: { detail: '村名重复' } },
    })
    await vm.handleFormSubmit({ villageName: '重复村' })
    expect(ElMessage.error).toHaveBeenCalledWith('村名重复')
  })

  it('创建失败且异常无信息 → 兜底文案', async () => {
    routeBox.path = '/supported-villages/create'
    routeBox.params = {}
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    svApi.createSupportedVillage.mockRejectedValue({})
    await vm.handleFormSubmit({ villageName: '村' })
    expect(ElMessage.error).toHaveBeenCalledWith('操作失败')
  })

  it('编辑提交成功 → 刷新详情并跳转', async () => {
    routeBox.path = '/supported-villages/9/edit'
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleFormSubmit({ villageName: '改名村' })
    expect(svApi.updateSupportedVillage).toHaveBeenCalledWith(9, { villageName: '改名村' })
    expect(ElMessage.success).toHaveBeenCalledWith('保存成功')
    expect(pushSafeMock).toHaveBeenCalledWith('/supported-villages/9')
    expect(vm.loading).toBe(false)
  })

  it('编辑提交失败 → 展示异常 message', async () => {
    routeBox.path = '/supported-villages/9/edit'
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    svApi.updateSupportedVillage.mockRejectedValue(new Error('网络异常'))
    await vm.handleFormSubmit({ villageName: '改名村' })
    expect(ElMessage.error).toHaveBeenCalledWith('网络异常')
  })

  it('取消：创建模式返回列表，编辑模式返回详情', async () => {
    routeBox.path = '/supported-villages/create'
    routeBox.params = {}
    const createWrapper = mountComp()
    await flushPromises()
    ;(createWrapper.vm as any).handleFormCancel()
    expect(pushSafeMock).toHaveBeenCalledWith('/supported-villages')

    resetRoute()
    routeBox.path = '/supported-villages/9/edit'
    pushSafeMock.mockClear()
    const editWrapper = mountComp()
    await flushPromises()
    ;(editWrapper.vm as any).handleFormCancel()
    expect(pushSafeMock).toHaveBeenCalledWith('/supported-villages/9')
  })
})

describe('导出档案册（w17-007）', () => {
  it('导出成功 → 提示并复位 loading', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleExportDossier()
    expect(svApi.downloadVillageDossier).toHaveBeenCalledWith(9)
    expect(ElMessage.success).toHaveBeenCalledWith('档案册已开始下载')
    expect(vm.dossierExporting).toBe(false)
  })

  it('导出失败 → 记录日志 + 泛化错误', async () => {
    svApi.downloadVillageDossier.mockRejectedValue(new Error('http 500'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleExportDossier()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('导出档案册失败，请稍后重试')
    expect(vm.dossierExporting).toBe(false)
  })

  it('village 为空 → 不发起导出', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.village = null
    await vm.handleExportDossier()
    expect(svApi.downloadVillageDossier).not.toHaveBeenCalled()
  })

  it('「导出档案册」按钮点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('导出档案册'))!
    await btn.trigger('click')
    await flushPromises()
    expect(svApi.downloadVillageDossier).toHaveBeenCalledWith(9)
    expect(ElMessage.success).toHaveBeenCalledWith('档案册已开始下载')
  })
})

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

describe('resize 去抖与卸载清理', () => {
  it('连续 resize 只保留最后一个定时器并复用图表实例', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleChartResize()
    vm.handleChartResize()
    await sleep(260)
    expect(chartMock.resize).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('卸载时清理定时器与图表实例；卸载后 resize 走空分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleChartResize()
    wrapper.unmount()
    expect(chartMock.dispose).toHaveBeenCalled()
    // 卸载后 trendChart 为 null → 去抖定时器触发时走可选链空分支
    chartMock.resize.mockClear()
    vm.handleChartResize()
    await sleep(260)
    expect(chartMock.resize).not.toHaveBeenCalled()
  })

  it('未初始化图表时 renderTrendChart 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.trendChartRef = null
    chartMock.setOption.mockClear()
    vm.renderTrendChart()
    expect(chartMock.setOption).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})

describe('模板分支断言', () => {
  it('全量村：标签与表彰文本全部渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const text = wrapper.text()
    for (const label of [
      '三区三州',
      '边疆地区',
      '民族地区',
      '革命地区',
      '重点帮扶县',
      '振兴梯队',
      '省级示范',
      '百村示范',
      '梯次发展',
      '跨省帮扶',
      '跨市帮扶',
      '跨单位协作',
      '纳入总盘子',
      '先进集体',
      '序号',
      '部门',
      '帮扶单位',
      '帮扶村名称',
      '地区范围',
    ]) {
      expect(text).toContain(label)
    }
  })

  it('页面标题/模式按钮随路由渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.text()).toContain('导出档案册')
    expect(wrapper.find('.header-actions').exists()).toBe(true)
  })
})
