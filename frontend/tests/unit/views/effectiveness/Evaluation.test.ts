/**
 * views/effectiveness/Evaluation.vue 测试（按后端 /effectiveness 真实响应契约）
 * 覆盖：村庄加载（多形态/失败提示）、onMounted（无参/带参 GET 报告/404 引导）、
 * reportItems/indicatorItems/compareItems（真实契约渲染与兜底）、handleFormChange 清空残留、
 * handleEvaluate（守卫/成功/失败 userMessage 透传）、handleCompare（守卫/成功/失败）、
 * 角色显隐（admin 见「开始评估」、viewer 隐藏）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const {
  ElMessage,
  mockApiRequest,
  mockEvaluateVillage,
  mockCompareEvaluations,
  mockGetReport,
  routeQuery,
  mockUserStore,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockApiRequest: vi.fn(),
  mockEvaluateVillage: vi.fn(),
  mockCompareEvaluations: vi.fn(),
  mockGetReport: vi.fn(),
  routeQuery: {} as Record<string, any>,
  mockUserStore: { currentUser: { role: 'admin' } as any },
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeQuery }),
  useRouter: () => ({ resolve: () => ({ name: 'X', matched: [1] }) }),
}))

vi.mock('@/stores/user', () => ({ useUserStore: () => mockUserStore }))

vi.mock('@/api/effectiveness', () => ({
  evaluateVillage: mockEvaluateVillage,
  compareEvaluations: mockCompareEvaluations,
  getEvaluationReport: mockGetReport,
  getRankings: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  apiRequest: mockApiRequest,
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

import Evaluation from '@/views/effectiveness/Evaluation.vue'

// 后端 _eval_to_dict 真实契约形态
const report = {
  village_id: 1,
  year: 2025,
  economic_score: 85.2,
  social_score: 76.5,
  ecological_score: 66.7,
  total_score: 90.5,
  rank: 3,
  grade: 'excellent',
  indicators: {
    per_capita_income: 18000,
    income_growth_rate: 12.5,
    infrastructure_count: 2,
    industry_count: 3,
    data_complete: true,
  },
  evaluated_at: '2025-12-31T10:00:00',
  village_name: '甲村',
}

// 后端 compare_evaluations 真实契约：三层嵌套 {year1_data, year2_data, delta}
const compareData = {
  village_id: 1,
  year1: 2024,
  year2: 2025,
  year1_data: { total_score: 80 },
  year2_data: { total_score: 90.5 },
  delta: { total_score: 10.5, economic_score: -2.0, social_score: 0, ecological_score: 5.5 },
}

const villages = [{ id: 1, name: '甲村' }, { id: 2, village_name: '乙村' }, { id: 3 }]

function mountComp() {
  return mount(Evaluation, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-form': { name: 'ElForm', template: '<div class="el-form-stub"><slot /></div>' },
        'el-form-item': {
          name: 'ElFormItem',
          template: '<div class="el-form-item-stub"><slot /></div>',
        },
        'el-select': {
          name: 'ElSelect',
          template: '<div class="el-select-stub"><slot /></div>',
          emits: ['update:modelValue', 'change'],
        },
        'el-option': { name: 'ElOption', template: '<div class="el-option-stub"><slot /></div>' },
        'el-descriptions': {
          name: 'ElDescriptions',
          template: '<div class="el-descriptions-stub"><slot /></div>',
        },
        'el-descriptions-item': {
          name: 'ElDescriptionsItem',
          props: ['label'],
          template: '<div class="el-descriptions-item-stub">{{ label }}<slot /></div>',
        },
        'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
        'el-empty': { name: 'ElEmpty', template: '<div class="el-empty-stub"><slot /></div>' },
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
  Object.keys(routeQuery).forEach((k) => delete routeQuery[k])
  mockUserStore.currentUser = { role: 'admin' }
  mockApiRequest.mockResolvedValue({ data: { items: villages } })
  mockEvaluateVillage.mockResolvedValue({ data: report })
  mockCompareEvaluations.mockResolvedValue({ data: compareData })
  mockGetReport.mockResolvedValue({ data: report })
})

describe('挂载与村庄加载', () => {
  it('onMounted：加载村庄选项（name 兜底链）；无查询参数不评估也不拉报告', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ url: '/supported-villages', params: { page_size: 200 } })
    )
    expect(vm.villageOptions).toEqual([
      { id: 1, name: '甲村' },
      { id: 2, name: '乙村' },
      { id: 3, name: 'ID:3' },
    ])
    expect(mockEvaluateVillage).not.toHaveBeenCalled()
    expect(mockGetReport).not.toHaveBeenCalled()
    expect(wrapper.find('.el-empty-stub').exists()).toBe(true)
  })

  it('loadVillages：裸对象/数组/嵌套形态；失败 → 空选项 + 错误提示', async () => {
    mockApiRequest.mockResolvedValue({ items: villages })
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).villageOptions).toHaveLength(3)

    mockApiRequest.mockResolvedValue({ data: villages })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).villageOptions).toHaveLength(3)

    mockApiRequest.mockResolvedValue({ data: {} })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).villageOptions).toEqual([])

    mockApiRequest.mockResolvedValue(null)
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).villageOptions).toEqual([])

    mockApiRequest.mockRejectedValue(new Error('net'))
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).villageOptions).toEqual([])
    expect(ElMessage.error).toHaveBeenCalledWith('村庄列表加载失败，请刷新重试')
  })

  it('onMounted 带查询参数 → 先 GET 已有报告（不触发写操作）', async () => {
    routeQuery.villageId = '1'
    routeQuery.year = '2025'
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.evalForm.villageId).toBe(1)
    expect(vm.evalForm.year).toBe(2025)
    expect(mockGetReport).toHaveBeenCalledWith(1, 2025)
    expect(mockEvaluateVillage).not.toHaveBeenCalled()
    expect(vm.evaluationResult).toEqual(report)
    // 报告按真实契约渲染：等级映射、排名整数、指标明细
    const text = wrapper.text()
    expect(text).toContain('2025年度')
    expect(text).toContain('甲村')
    expect(text).toContain('90.5')
    expect(text).toContain('优秀')
    expect(text).toContain('第 3 名')
    expect(text).toContain('18000')
    expect(text).toContain('12.5%')
  })

  it('onMounted 带参数但报告 404 → info 引导，不报错', async () => {
    routeQuery.villageId = '5'
    mockGetReport.mockRejectedValue({ response: { status: 404 } })
    mountComp()
    await flushPromises()
    expect(ElMessage.info).toHaveBeenCalledWith('该年度尚未评估，可点击"开始评估"')
    expect(mockEvaluateVillage).not.toHaveBeenCalled()
  })

  it('报告加载非 404 失败 → error 提示（userMessage 优先）', async () => {
    routeQuery.villageId = '5'
    mockGetReport.mockRejectedValue({ response: { status: 500 }, userMessage: '服务异常' })
    mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('服务异常')
  })

  it('loadExistingReport：响应无 .data 包装（裸对象）→ 直接采用', async () => {
    routeQuery.villageId = '1'
    mockGetReport.mockResolvedValue(report) // 裸响应（后端直接返回报告对象）
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).evaluationResult).toEqual(report)
  })

  it('loadExistingReport 非 404 失败且无 userMessage → 兜底文案', async () => {
    routeQuery.villageId = '5'
    mockGetReport.mockRejectedValue({ response: { status: 500 } })
    mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('评估报告加载失败')
  })

  it('loadExistingReport 404 + 非管理员 → 联系管理员文案', async () => {
    mockUserStore.currentUser = { role: 'viewer' }
    routeQuery.villageId = '5'
    mockGetReport.mockRejectedValue({ response: { status: 404 } })
    mountComp()
    await flushPromises()
    expect(ElMessage.info).toHaveBeenCalledWith('该年度尚未评估，请联系管理员评估')
  })

  it('loadVillages 失败带 userMessage → 透传业务文案', async () => {
    mockApiRequest.mockRejectedValue({ userMessage: '网络异常' })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).villageOptions).toEqual([])
    expect(ElMessage.error).toHaveBeenCalledWith('网络异常')
  })
})

describe('handleEvaluate', () => {
  it('未选村庄 → 警告早退', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.evalForm.villageId = 0
    await vm.handleEvaluate()
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择村庄')
    expect(mockEvaluateVillage).not.toHaveBeenCalled()
  })

  it('成功：评估按钮点击触发，报告渲染且对比结果清空', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.evalForm.villageId = 1
    vm.evalForm.year = 2025
    vm.compareResult = compareData
    await findBtn(wrapper, '开始评估').trigger('click')
    await flushPromises()
    expect(mockEvaluateVillage).toHaveBeenCalledWith({ village_id: 1, year: 2025 })
    expect(vm.evaluationResult).toEqual(report)
    expect(vm.compareResult).toBeNull()
    expect(ElMessage.success).toHaveBeenCalledWith('评估完成')
    expect(vm.evaluating).toBe(false)
    expect(wrapper.text()).toContain('2025年度')
  })

  it('失败 → 透传后端 userMessage', async () => {
    mockEvaluateVillage.mockRejectedValue({ userMessage: '需要管理员权限' })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.evalForm.villageId = 1
    await vm.handleEvaluate()
    expect(ElMessage.error).toHaveBeenCalledWith('需要管理员权限')
    expect(vm.evaluating).toBe(false)
  })

  it('失败且无 userMessage → 兜底文案', async () => {
    mockEvaluateVillage.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.evalForm.villageId = 1
    await vm.handleEvaluate()
    expect(ElMessage.error).toHaveBeenCalledWith('评估失败')
  })

  it('成功但响应无 .data 包装（裸对象）→ 直接采用', async () => {
    mockEvaluateVillage.mockResolvedValue(report) // 裸响应
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.evalForm.villageId = 1
    await vm.handleEvaluate()
    expect(vm.evaluationResult).toEqual(report)
    expect(ElMessage.success).toHaveBeenCalledWith('评估完成')
    expect(vm.evaluating).toBe(false)
  })

  it('失败带 response.data.detail（无 userMessage）→ 透传 detail', async () => {
    mockEvaluateVillage.mockRejectedValue({ response: { data: { detail: '权限不足' } } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.evalForm.villageId = 1
    await vm.handleEvaluate()
    expect(ElMessage.error).toHaveBeenCalledWith('权限不足')
    expect(vm.evaluating).toBe(false)
  })
})

describe('handleCompare', () => {
  it('未选村庄 / 同年份 → 警告', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.evalForm.villageId = 0
    await vm.handleCompare()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择村庄')

    vm.evalForm.villageId = 1
    vm.compareForm.year1 = 2025
    vm.compareForm.year2 = 2025
    await vm.handleCompare()
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择不同的年度进行对比')
    expect(mockCompareEvaluations).not.toHaveBeenCalled()
  })

  it('成功：delta 按真实契约渲染（含正负号）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.evalForm.villageId = 1
    vm.compareForm.year1 = 2024
    vm.compareForm.year2 = 2025
    vm.evaluationResult = report // 对比区块 v-if 依赖
    await nextTick()
    await findBtn(wrapper, '对比').trigger('click')
    await flushPromises()
    expect(mockCompareEvaluations).toHaveBeenCalledWith(1, 2024, 2025)
    expect(vm.compareResult).toEqual(compareData)
    expect(vm.comparing).toBe(false)
    const text = wrapper.text()
    expect(text).toContain('+10.5')
    expect(text).toContain('-2')
    expect(text).toContain('80.0')
    expect(text).toContain('2024 年总分')
  })

  it('失败 → 透传业务错误（缺少年度数据）；成功后旧对比结果先清空', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.evalForm.villageId = 1
    vm.compareResult = compareData
    mockCompareEvaluations.mockRejectedValue({ userMessage: '缺少 2024 年的评估数据，无法对比' })
    await vm.handleCompare()
    expect(ElMessage.error).toHaveBeenCalledWith('缺少 2024 年的评估数据，无法对比')
    expect(vm.compareResult).toBeNull() // 失败不留旧结果
    expect(vm.comparing).toBe(false)
  })

  it('成功：裸响应（无 .data）且 delta 含 null → 差值渲染为 -', async () => {
    const bareCompare = {
      year1: 2024,
      year2: 2025,
      // 无 year1_data/year2_data，delta 部分为 null
      delta: { total_score: null, economic_score: null, social_score: 0, ecological_score: null },
    }
    mockCompareEvaluations.mockResolvedValue(bareCompare) // 裸响应
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.evalForm.villageId = 1
    vm.compareForm.year1 = 2024
    vm.compareForm.year2 = 2025
    vm.evaluationResult = report // 对比区块 v-if 依赖
    await nextTick()
    await vm.handleCompare()
    expect(mockCompareEvaluations).toHaveBeenCalledWith(1, 2024, 2025)
    expect(vm.compareResult).toEqual(bareCompare)
    expect(vm.compareItems).toHaveLength(6)
    expect(vm.compareItems.map((i: any) => i.value)).toEqual(['-', '-', '-', '-', '0', '-'])
    expect(wrapper.text()).toContain('2024 年总分')
    expect(wrapper.text()).toContain('2025 年总分')
  })

  it('失败带 response.data.detail（无 userMessage）→ 透传 detail', async () => {
    mockCompareEvaluations.mockRejectedValue({ response: { data: { detail: '对比数据缺失' } } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.evalForm.villageId = 1
    await vm.handleCompare()
    expect(ElMessage.error).toHaveBeenCalledWith('对比数据缺失')
    expect(vm.comparing).toBe(false)
  })

  it('失败无任何信息 → 兜底文案', async () => {
    mockCompareEvaluations.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.evalForm.villageId = 1
    await vm.handleCompare()
    expect(ElMessage.error).toHaveBeenCalledWith('对比失败')
    expect(vm.comparing).toBe(false)
  })
})

describe('计算属性与残留清理', () => {
  it('reportItems/indicatorItems 兜底：rank/indicators 缺失', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.reportItems).toEqual([])
    expect(vm.indicatorItems).toEqual([])
    vm.evaluationResult = {
      village_id: 1,
      year: 2025,
      total_score: null,
      rank: null,
      grade: null,
      indicators: null,
      evaluated_at: 'not-a-date',
    }
    await nextTick()
    const text = wrapper.text()
    expect(text).not.toContain('第') // rank null → '-'
    expect(text).toContain('not-a-date') // 非法日期原样输出
    expect(vm.indicatorItems).toEqual([])
  })

  it('compareItems：无 delta → 空；切换村庄/年度清空结果', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.compareItems).toEqual([])
    vm.compareResult = { village_id: 1 }
    expect(vm.compareItems).toEqual([])

    vm.evaluationResult = report
    vm.compareResult = compareData
    vm.handleFormChange()
    expect(vm.evaluationResult).toBeNull()
    expect(vm.compareResult).toBeNull()
  })

  it('select change 事件触发清空（模板绑定）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.evaluationResult = report
    await nextTick()
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 2)
    selects[0].vm.$emit('change', 2)
    expect(vm.evalForm.villageId).toBe(2)
    expect(vm.evaluationResult).toBeNull()
  })

  it('reportItems/indicatorItems 兜底：year/evaluated_at/指标字段全 null + 未知等级', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.evaluationResult = {
      village_id: 1,
      year: null,
      total_score: null,
      grade: 'unknown', // 未映射等级 → 原样输出
      rank: 5,
      indicators: {
        per_capita_income: null,
        income_growth_rate: null,
        infrastructure_count: null,
        industry_count: null,
        data_complete: false,
      },
      evaluated_at: null,
    }
    await nextTick()
    const ri = vm.reportItems
    expect(ri.find((i: any) => i.label === '评估年度').value).toBe('-')
    expect(ri.find((i: any) => i.label === '等级').value).toBe('unknown')
    expect(ri.find((i: any) => i.label === '评估时间').value).toBe('-')
    expect(vm.indicatorItems.map((i: any) => i.value)).toEqual([
      '-',
      '-',
      '-',
      '-',
      '未录入（按基线评估）',
    ])
  })

  it('v-model 双向绑定：年度/对比年度选择器更新表单值', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.evaluationResult = report // 展开对比区块（额外渲染两个对比年度选择器）
    await nextTick()
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(selects).toHaveLength(4) // 村庄/年度 + 对比年1/年2
    selects[1].vm.$emit('update:modelValue', 2024)
    expect(vm.evalForm.year).toBe(2024)
    selects[2].vm.$emit('update:modelValue', 2023)
    expect(vm.compareForm.year1).toBe(2023)
    selects[3].vm.$emit('update:modelValue', 2024)
    expect(vm.compareForm.year2).toBe(2024)
  })
})

describe('角色显隐', () => {
  it('viewer 不渲染「开始评估」按钮，空态提示变化', async () => {
    mockUserStore.currentUser = { role: 'viewer' }
    const wrapper = mountComp()
    await flushPromises()
    const btns = wrapper.findAll('el-button-stub')
    expect(btns.some((b: any) => b.text().includes('开始评估'))).toBe(false)
    expect((wrapper.vm as any).emptyHint).toBe('选择村庄和年度查看评估报告')
  })

  it('admin 渲染「开始评估」按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    expect(findBtn(wrapper, '开始评估')).toBeTruthy()
  })

  it('currentUser 为空 → 非管理员视图（无评估按钮）', async () => {
    mockUserStore.currentUser = null
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isAdmin).toBe(false)
    expect(vm.emptyHint).toBe('选择村庄和年度查看评估报告')
    const btns = wrapper.findAll('el-button-stub')
    expect(btns.some((b: any) => b.text().includes('开始评估'))).toBe(false)
  })

  it('非 admin/super_admin 但 is_superuser=true → 视为管理员', async () => {
    mockUserStore.currentUser = { role: 'user', is_superuser: true }
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).isAdmin).toBe(true)
    expect(findBtn(wrapper, '开始评估')).toBeTruthy()
  })
})
