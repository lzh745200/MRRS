/**
 * views/dataEntry/ComprehensiveEntry.vue 覆盖率攻坚
 * 覆盖：五步向导渲染与导航、步骤校验全分支、全量 v-model 处理器、
 * 地区智能识别、年份区间 watch（新增/缩减/排序）、成员与表彰动态行增删、
 * 草稿本地保存/恢复/过期/损坏、自动保存定时器、保存草稿与提交审核全路径、
 * submitVillageData 的 villageId 三形态与年度数据条件提交全组合。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂会被提升到模块顶部注册，直接引用顶层变量会触发 TDZ；
// 所有被工厂引用的对象放入 vi.hoisted 中先行初始化。
const { ElMessage, confirmMock, mockPost, mockGet, mockPut } = vi.hoisted(() => {
  return {
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
    },
    confirmMock: vi.fn(),
    mockPost: vi.fn(),
    mockGet: vi.fn(),
    mockPut: vi.fn(),
  }
})

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/request', () => ({
  post: mockPost,
  get: mockGet,
  put: mockPut,
  del: vi.fn(),
  apiRequest: vi.fn(),
  default: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

import ComprehensiveEntry from '@/views/dataEntry/ComprehensiveEntry.vue'

const DRAFT_KEY = 'comprehensive_entry_draft'
const currentYear = new Date().getFullYear()

function mountComp() {
  // 具名插槽（upload tip）与 v-model 事件需要自定义 stub；
  // 其余 el-* 由 setup.ts 全局 stub + renderStubDefaultSlot 渲染默认插槽。
  return mount(ComprehensiveEntry, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-input': {
          name: 'ElInput',
          props: ['modelValue'],
          emits: ['update:modelValue', 'change'],
          template: '<div class="el-input-stub"><slot /><slot name="append" /></div>',
        },
        'el-select': {
          name: 'ElSelect',
          props: ['modelValue'],
          emits: ['update:modelValue', 'change'],
          template: '<div class="el-select-stub"><slot /></div>',
        },
        'el-switch': {
          name: 'ElSwitch',
          props: ['modelValue'],
          emits: ['update:modelValue', 'change'],
          template: '<div class="el-switch-stub" />',
        },
        'el-input-number': {
          name: 'ElInputNumber',
          props: ['modelValue'],
          emits: ['update:modelValue', 'change'],
          template: '<div class="el-input-number-stub" />',
        },
        'el-tabs': {
          name: 'ElTabs',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<div class="el-tabs-stub"><slot /></div>',
        },
        'el-upload': {
          name: 'ElUpload',
          emits: ['change'],
          template: '<div class="el-upload-stub"><slot /><slot name="tip" /></div>',
        },
      },
    },
  })
}

/** 填充步骤0必填字段 + 后续步骤校验数据（投资/专项/消费帮扶） */
function fillBasic(vm: any) {
  vm.formData.basicInfo.department = '某部'
  vm.formData.basicInfo.supportUnit = '某旅'
  vm.formData.basicInfo.villageName = '幸福村'
  vm.formData.basicInfo.helpType = 'industry'
  vm.formData.basicInfo.province = '520000'
  // 填充投资数据(步骤1校验要求: 任一年度四项齐全)
  vm.formData.investmentData.forEach((d: any) => {
    d.militaryInvestment = 1
    d.localInvestment = 1
    d.leaderVisits = 1
    d.soldierVisits = 1
  })
  // 步骤2：专项板块（项目/活动类型与投入金额联动）
  vm.formData.industryHelp.projectType = '种植'
  vm.formData.industryHelp.investment = 10
  vm.formData.infrastructureHelp.projectType = '道路'
  vm.formData.infrastructureHelp.investment = 20
  vm.formData.partyBuildingHelp.activityType = '党课'
  vm.formData.partyBuildingHelp.investment = 5
  vm.formData.medicalHelp.activityType = '义诊'
  vm.formData.medicalHelp.investment = 3
  // 步骤3：消费帮扶（采购与销售额需同时填写）
  vm.formData.consumptionHelp.purchaseAmount = 100
  vm.formData.consumptionHelp.salesAmount = 90
}

/** 构造完整草稿 */
function makeFullDraft() {
  return {
    formData: {
      basicInfo: { department: '草稿部门', villageName: '草稿村' },
      committeeInfo: { overview: '村委会介绍' },
      industryHelp: { investment: 3 },
      infrastructureHelp: { investment: 4 },
      partyBuildingHelp: { activityCount: 2 },
      medicalHelp: { beneficiaries: 9 },
      consumptionHelp: { purchaseAmount: 7 },
      employmentHelp: { employedCount: 5 },
      educationHelp: { aidedStudents: 11 },
      collaboration: { isCrossUnit: true },
      honors: [{ level: '省级', honorName: '先进', year: currentYear, recipient: '张三' }],
      populationData: [
        {
          year: currentYear - 6,
          totalPopulation: 100,
          households: 30,
          povertyAlleviatedPopulation: 10,
          perCapitaIncome: 8000,
          collectiveEconomyIncome: 20,
        },
      ],
      investmentData: [
        {
          year: currentYear - 6,
          militaryInvestment: 5,
          localInvestment: 6,
          leaderVisits: 2,
          soldierVisits: 3,
        },
      ],
    },
    currentStep: 2,
    popYearStart: currentYear - 6,
    popYearEnd: currentYear - 4,
    investYearStart: currentYear - 6,
    investYearEnd: currentYear - 5,
    relatedSchoolText: '希望小学',
    relatedFundText: 'F-001',
    savedAt: new Date().toISOString(),
  }
}

beforeEach(() => {
  vi.resetAllMocks()
  // 用例间隔离：残留草稿会被 loadDraftFromLocal 恢复，导致"不会保存的项"随执行顺序漂移
  localStorage.clear()
  mockPost.mockResolvedValue({ data: { id: 101 } })
  // W27：提交前会先按「县 + 村名」查重（getSupportedVillages），默认查无同名村 → 走新建
  mockGet.mockResolvedValue({ items: [] })
  confirmMock.mockResolvedValue(undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与初始化', () => {
  it('默认渲染五步条与步骤0面板，底部按钮 v-if 两侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(wrapper.text()).toContain('综合数据录入')
    expect(vm.currentStep).toBe(0)
    // 年份区间默认行数（起始=当前年-5/-4）
    expect(vm.yearRange).toHaveLength(6)
    expect(vm.investYearRange).toHaveLength(5)
    expect(wrapper.findAll('.year-data-row').length).toBe(6 + 5)
    // 底部按钮：上一步/提交隐藏，下一步/保存草稿可见
    const btnTexts = wrapper.findAll('el-button-stub').map((b) => b.text())
    expect(btnTexts).toContain('下一步')
    expect(btnTexts).toContain('保存草稿')
    expect(btnTexts).not.toContain('上一步')
    expect(btnTexts).not.toContain('提交审核')
    // 自动保存提示未显示
    expect(wrapper.find('.auto-save-hint').exists()).toBe(false)
    wrapper.unmount()
  })

  it('投入汇总 computeds 随数据变化', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.totalMilitaryInvest).toBe(0)
    expect(vm.totalLocalInvest).toBe(0)
    expect(vm.totalVisits).toBe(0)
    vm.formData.investmentData[0].militaryInvestment = 10
    vm.formData.investmentData[1].localInvestment = 5
    vm.formData.investmentData[2].leaderVisits = 3
    vm.formData.investmentData[2].soldierVisits = 4
    await nextTick()
    expect(vm.totalMilitaryInvest).toBe(10)
    expect(vm.totalLocalInvest).toBe(5)
    expect(vm.totalVisits).toBe(7)
    wrapper.unmount()
  })
})

describe('全量 v-model 处理器', () => {
  it('所有输入控件触发 update:modelValue（同值回写避免副作用）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 先造出动态行（成员/表彰），让其内部 v-model 也参与
    const addMemberBtn = wrapper
      .findAll('el-button-stub')
      .find((b) => b.text().includes('添加村委会成员'))
    await addMemberBtn!.trigger('click')
    const addHonorBtn = wrapper
      .findAll('el-button-stub')
      .find((b) => b.text().includes('添加表彰记录'))
    await addHonorBtn!.trigger('click')
    await nextTick()
    expect(vm.formData.committeeInfo.members).toHaveLength(1)
    expect(vm.formData.honors).toHaveLength(1)

    // 同值回写：每个 v-model 处理器都执行一次，但不改变状态（避免年份 watch 风暴）
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    expect(inputs.length).toBeGreaterThan(10)
    for (const c of inputs) c.vm.$emit('update:modelValue', c.props('modelValue'))
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(selects.length).toBeGreaterThan(5)
    for (const c of selects) c.vm.$emit('update:modelValue', c.props('modelValue'))
    const switches = wrapper.findAllComponents({ name: 'ElSwitch' })
    expect(switches.length).toBeGreaterThan(8)
    for (const c of switches) c.vm.$emit('update:modelValue', c.props('modelValue'))
    const numbers = wrapper.findAllComponents({ name: 'ElInputNumber' })
    expect(numbers.length).toBeGreaterThan(30)
    for (const c of numbers) c.vm.$emit('update:modelValue', c.props('modelValue'))

    // tabs v-model 切换
    const tabs = wrapper.findComponent({ name: 'ElTabs' })
    tabs.vm.$emit('update:modelValue', 'party')
    expect(vm.helpTab).toBe('party')

    // @change 注册（省份下拉、市/州与县/区输入框均挂 onRegionChange）
    for (const c of selects) c.vm.$emit('change', c.props('modelValue'))
    for (const c of inputs) c.vm.$emit('change', c.props('modelValue'))
    await nextTick()

    // 状态未被破坏（同值回写）
    expect(vm.formData.committeeInfo.members).toHaveLength(1)
    expect(vm.formData.honors).toHaveLength(1)
    wrapper.unmount()
  })

  it('动态行内联 splice 删除成员与表彰', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.addCommitteeMember()
    vm.addHonor()
    await nextTick()
    const delBtns = () => wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '×')
    expect(delBtns().length).toBe(2)
    await delBtns()[0].trigger('click')
    await nextTick()
    await delBtns()[0].trigger('click')
    await nextTick()
    expect(vm.formData.committeeInfo.members).toHaveLength(0)
    expect(vm.formData.honors).toHaveLength(0)
    wrapper.unmount()
  })
})

describe('地区智能识别与辅助函数', () => {
  it('省市县变化不再静默覆盖手工填写的区域属性', async () => {
    // 回归背景（v1.12.9）：原先 @change=onRegionChange 会调用 detectRegionAttributes
    // 并把"三区三州/边疆/民族/革命老区/重点县"一律写回 false —— 用户手工勾选或
    // 后端回填的真实标记会在改省市区时被静默清空。
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.basicInfo.isRevolutionaryArea = true
    vm.formData.basicInfo.isBorderArea = true
    vm.formData.basicInfo.isKeyCounty = true
    vm.formData.basicInfo.province = '520000'
    vm.formData.basicInfo.city = '贵阳市'
    vm.formData.basicInfo.county = '云岩区'
    await nextTick()
    expect(vm.formData.basicInfo.isRevolutionaryArea).toBe(true)
    expect(vm.formData.basicInfo.isBorderArea).toBe(true)
    expect(vm.formData.basicInfo.isKeyCounty).toBe(true)
    // 组件不应再暴露会覆盖真实标记的处理函数
    expect(typeof vm.onRegionChange).not.toBe('function')
    wrapper.unmount()
  })

  it('detectRegionAttributes 只返回省份标签，不返回无依据的布尔属性', async () => {
    const { detectRegionAttributes } = await import('@/config/regionDictionary')
    const attrs = detectRegionAttributes('520000') as Record<string, unknown>
    expect(attrs.province).toBe('贵州省')
    expect('isBorderArea' in attrs).toBe(false)
    expect('isKeyCounty' in attrs).toBe(false)
    expect('isThreeRegionsThreeStates' in attrs).toBe(false)
  })

  it('getPopData/getInvestData 未命中年份时回退首条', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getPopData(1900)).toBe(vm.formData.populationData[0])
    expect(vm.getInvestData(1900)).toBe(vm.formData.investmentData[0])
    expect(vm.getPopData(currentYear).year).toBe(currentYear)
    wrapper.unmount()
  })
})

describe('年份区间 watch', () => {
  it('扩大区间新增年份数据，缩小区间移除并排序', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const before = vm.formData.populationData.length
    // 扩大一年 → push 分支
    vm.popYearEnd = currentYear + 1
    await nextTick()
    expect(vm.formData.populationData.length).toBe(before + 1)
    expect(vm.formData.populationData.at(-1).year).toBe(currentYear + 1)
    // 缩回两年 → 全部命中（不 push）+ filter 移除
    vm.popYearEnd = currentYear - 1
    await nextTick()
    expect(vm.formData.populationData.map((d: any) => d.year)).toEqual([
      currentYear - 5,
      currentYear - 4,
      currentYear - 3,
      currentYear - 2,
      currentYear - 1,
    ])
    // 投入年份同理
    const invBefore = vm.formData.investmentData.length
    vm.investYearEnd = currentYear + 1
    await nextTick()
    expect(vm.formData.investmentData.length).toBe(invBefore + 1)
    vm.investYearEnd = currentYear - 1
    await nextTick()
    expect(vm.formData.investmentData.at(-1).year).toBe(currentYear - 1)
    wrapper.unmount()
  })
})

describe('草稿本地存取', () => {
  it('保存草稿写入 localStorage 并显示时间提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const btn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('保存草稿'))
    mockPost.mockResolvedValueOnce({ data: { id: 101 } })
    await btn!.trigger('click')
    await flushPromises()
    expect(localStorage.getItem(DRAFT_KEY)).toBeTruthy()
    expect(vm.lastSavedAt).toBeTruthy()
    await nextTick()
    expect(wrapper.find('.auto-save-hint').exists()).toBe(true)
    wrapper.unmount()
  })

  it('完整草稿恢复：全字段 Object.assign + 可选字段真值侧 + info 提示', async () => {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(makeFullDraft()))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(ElMessage.info).toHaveBeenCalledWith(expect.stringContaining('已恢复上次草稿'))
    expect(vm.formData.basicInfo.department).toBe('草稿部门')
    expect(vm.formData.honors).toHaveLength(1)
    expect(vm.currentStep).toBe(2)
    expect(vm.popYearStart).toBe(currentYear - 6)
    expect(vm.relatedSchoolText).toBe('希望小学')
    expect(vm.relatedFundText).toBe('F-001')
    // 年份变化触发 watch，人口数据补齐到区间长度
    await nextTick()
    expect(vm.formData.populationData.length).toBe(3)
    expect(vm.formData.investmentData.length).toBe(2)
    wrapper.unmount()
  })

  it('极简草稿：可选字段缺省走假值侧', async () => {
    localStorage.setItem(
      DRAFT_KEY,
      JSON.stringify({ formData: { basicInfo: { department: '极简部门' } } })
    )
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(ElMessage.info).toHaveBeenCalled()
    expect(vm.formData.basicInfo.department).toBe('极简部门')
    expect(vm.formData.honors).toEqual([])
    expect(vm.currentStep).toBe(0)
    expect(vm.relatedSchoolText).toBe('')
    wrapper.unmount()
  })

  it('过期草稿（>7天）被清除且不恢复', async () => {
    const draft = makeFullDraft()
    draft.savedAt = new Date(Date.now() - 10 * 24 * 3600 * 1000).toISOString()
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(ElMessage.info).not.toHaveBeenCalled()
    expect(localStorage.getItem(DRAFT_KEY)).toBeNull()
    expect(vm.formData.basicInfo.department).toBe('')
    wrapper.unmount()
  })

  it('无 basicInfo 的草稿与损坏 JSON 均静默忽略', async () => {
    localStorage.setItem(DRAFT_KEY, JSON.stringify({ foo: 1 }))
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.info).not.toHaveBeenCalled()
    wrapper.unmount()

    localStorage.setItem(DRAFT_KEY, 'not-json{{{')
    const wrapper2 = mountComp()
    await flushPromises()
    expect(ElMessage.info).not.toHaveBeenCalled()
    wrapper2.unmount()
  })

  it('localStorage 写入失败时静默忽略', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vi.spyOn(localStorage, 'setItem').mockImplementationOnce(() => {
      throw new Error('quota exceeded')
    })
    vm.saveDraftToLocal()
    expect(vm.lastSavedAt).toBe('')
    wrapper.unmount()
  })
})

describe('步骤校验与导航', () => {
  it('步骤0逐项校验失败提示，全部补齐后进入下一步', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const nextBtn = () => wrapper.findAll('el-button-stub').find((b) => b.text() === '下一步')!

    // department 为 undefined（可选链短路侧）
    vm.formData.basicInfo.department = undefined
    await nextBtn().trigger('click')
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写部门单位')
    expect(vm.currentStep).toBe(0)

    vm.formData.basicInfo.department = '某部'
    await nextBtn().trigger('click')
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写帮扶单位')

    vm.formData.basicInfo.supportUnit = '某旅'
    await nextBtn().trigger('click')
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写帮扶村名称')

    vm.formData.basicInfo.villageName = '幸福村'
    await nextBtn().trigger('click')
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择帮扶类型')

    vm.formData.basicInfo.helpType = 'industry'
    await nextBtn().trigger('click')
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择省份')

    vm.formData.basicInfo.province = '520000'
    await nextBtn().trigger('click')
    await flushPromises()
    expect(vm.currentStep).toBe(1)
    // 通过校验后保存了草稿
    expect(localStorage.getItem(DRAFT_KEY)).toBeTruthy()
    wrapper.unmount()
  })

  it('五步导航：下一步/上一步按钮流转与 v-if 两侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    const nextBtn = () => wrapper.findAll('el-button-stub').find((b) => b.text() === '下一步')
    const prevBtn = () => wrapper.findAll('el-button-stub').find((b) => b.text() === '上一步')
    const submitBtn = () => wrapper.findAll('el-button-stub').find((b) => b.text() === '提交审核')

    // 步骤0在最前：无上一步按钮
    expect(prevBtn()).toBeUndefined()
    for (let i = 0; i < 4; i++) {
      await nextBtn()!.trigger('click')
      await nextTick()
    }
    expect(vm.currentStep).toBe(4)
    // 步骤4：无下一步按钮，有提交审核与上一步
    expect(nextBtn()).toBeUndefined()
    expect(submitBtn()).toBeTruthy()
    await prevBtn()!.trigger('click')
    await nextTick()
    expect(vm.currentStep).toBe(3)
    // 步骤0 调用 goPrevStep 不越界
    vm.currentStep = 0
    vm.goPrevStep()
    expect(vm.currentStep).toBe(0)
    wrapper.unmount()
  })
})

describe('步骤校验扩展分支', () => {
  it('步骤1投资数据不完整/为空时拦截', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.currentStep = 1
    // 清除投资数据 → 为空警告
    vm.formData.investmentData.forEach((d: any) => {
      d.militaryInvestment = 0
      d.localInvestment = 0
      d.leaderVisits = 0
      d.soldierVisits = 0
    })
    expect(vm.validateCurrentStep()).toBe(false)
    expect(ElMessage.warning).toHaveBeenCalledWith('请至少填写一个年度的投资数据')
    // 部分填写 → 不完整警告
    vm.formData.investmentData[0].militaryInvestment = 5
    expect(vm.validateCurrentStep()).toBe(false)
    expect(ElMessage.warning).toHaveBeenCalledWith('投资数据填写不完整：请补全已填写年度的各项数据')
    wrapper.unmount()
  })

  it('步骤2专项与步骤3消费帮扶成对校验', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.currentStep = 2
    // 清零 fillBasic 预填的专项数据(保证分支互不污染)
    vm.formData.industryHelp.projectType = ''
    vm.formData.industryHelp.investment = 0
    vm.formData.infrastructureHelp.projectType = ''
    vm.formData.infrastructureHelp.investment = 0
    vm.formData.partyBuildingHelp.activityType = ''
    vm.formData.partyBuildingHelp.investment = 0
    vm.formData.medicalHelp.activityType = ''
    vm.formData.medicalHelp.investment = 0
    // 产业帮扶: 有类型无金额
    vm.formData.industryHelp.projectType = '肉牛养殖'
    vm.formData.industryHelp.investment = 0
    expect(vm.validateCurrentStep()).toBe(false)
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写产业帮扶的投资额')
    // 有金额无类型
    vm.formData.industryHelp.projectType = ''
    vm.formData.industryHelp.investment = 100
    expect(vm.validateCurrentStep()).toBe(false)
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写产业帮扶的项目类型')
    // 基建: 有类型无投资
    vm.formData.industryHelp.projectType = ''
    vm.formData.industryHelp.investment = 0
    vm.formData.infrastructureHelp.projectType = '道路硬化'
    vm.formData.infrastructureHelp.investment = 0
    expect(vm.validateCurrentStep()).toBe(false)
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写基础设施帮扶的投资额')
    // 基建: 有投资无类型
    vm.formData.infrastructureHelp.projectType = ''
    vm.formData.infrastructureHelp.investment = 50
    expect(vm.validateCurrentStep()).toBe(false)
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写基础设施帮扶的项目类型')
    // 党建帮扶: 有活动类型无金额
    vm.formData.infrastructureHelp.projectType = ''
    vm.formData.infrastructureHelp.investment = 0
    vm.formData.partyBuildingHelp.activityType = '支部共建'
    expect(vm.validateCurrentStep()).toBe(false)
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写党建帮扶的投入金额')
    // 医疗: 有类型无金额 / 有金额无类型
    vm.formData.partyBuildingHelp.activityType = ''
    vm.formData.medicalHelp.activityType = '义诊'
    vm.formData.medicalHelp.investment = 0
    expect(vm.validateCurrentStep()).toBe(false)
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写医疗帮扶的投入金额')
    vm.formData.medicalHelp.activityType = ''
    vm.formData.medicalHelp.investment = 30
    expect(vm.validateCurrentStep()).toBe(false)
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写医疗帮扶的活动类型')
    // 步骤3 消费帮扶: 采购有销售额无 / 销售额有采购无
    vm.formData.medicalHelp.investment = 0
    vm.currentStep = 3
    vm.formData.consumptionHelp.purchaseAmount = 10
    vm.formData.consumptionHelp.salesAmount = 0
    expect(vm.validateCurrentStep()).toBe(false)
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写消费帮扶的销售额')
    vm.formData.consumptionHelp.purchaseAmount = 0
    vm.formData.consumptionHelp.salesAmount = 20
    expect(vm.validateCurrentStep()).toBe(false)
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写消费帮扶的采购金额')
    wrapper.unmount()
  })

  it('validateAllSteps 全部通过返回 true', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    expect(vm.validateAllSteps()).toBe(true)
    wrapper.unmount()
  })
})

describe('保存草稿与提交审核', () => {
  it('保存草稿：只写本机 localStorage，绝不请求服务器（W27 P0-5）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('保存草稿'))!
    mockPost.mockClear()
    await btn.trigger('click')
    await flushPromises()
    // 核心回归：草稿不得触发任何服务器写入（原实现会 POST 新建帮扶村）
    expect(mockPost).not.toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('草稿已保存到本机（未提交到服务器）')
    expect(localStorage.getItem(DRAFT_KEY)).toBeTruthy()
    wrapper.unmount()
  })

  it('提交审核：基础信息缺失时警告并停留在当前步骤不提交', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentStep = 4
    await nextTick()
    const submitBtn = wrapper.findAll('el-button-stub').find((b) => b.text() === '提交审核')!
    await submitBtn.trigger('click')
    await flushPromises()
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写部门单位')
    expect(confirmMock).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('提交审核：用户取消确认不报错', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.currentStep = 4
    await nextTick()
    confirmMock.mockRejectedValueOnce('cancel')
    await wrapper
      .findAll('el-button-stub')
      .find((b) => b.text() === '提交审核')!
      .trigger('click')
    await flushPromises()
    expect(ElMessage.error).not.toHaveBeenCalled()
    expect(ElMessage.success).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('提交审核：关窗（close）也按取消处理，不弹错误', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.currentStep = 4
    await nextTick()
    confirmMock.mockRejectedValueOnce('close')
    await wrapper
      .findAll('el-button-stub')
      .find((b) => b.text() === '提交审核')!
      .trigger('click')
    await flushPromises()
    expect(ElMessage.error).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('提交审核：真实异常显示失败原因', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.currentStep = 4
    await nextTick()
    confirmMock.mockRejectedValueOnce(new Error('disk full'))
    await wrapper
      .findAll('el-button-stub')
      .find((b) => b.text() === '提交审核')!
      .trigger('click')
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('disk full')
    wrapper.unmount()
  })

  it('提交审核成功：清除草稿、提示成功、回到步骤0', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.saveDraftToLocal()
    expect(localStorage.getItem(DRAFT_KEY)).toBeTruthy()
    vm.currentStep = 4
    await nextTick()
    await wrapper
      .findAll('el-button-stub')
      .find((b) => b.text() === '提交审核')!
      .trigger('click')
    await flushPromises()
    // 确认框始终开启 HTML 渲染（用于列出"不会保存"的项）
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('确认提交数据进行审核？提交后将清除本地草稿。'),
      '提交确认',
      expect.objectContaining({ dangerouslyUseHTMLString: true })
    )
    expect(mockPost).toHaveBeenCalledWith(
      '/supported-villages',
      expect.objectContaining({ department: '某部', village_name: '幸福村', province: '贵州省' })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('数据已提交审核')
    expect(localStorage.getItem(DRAFT_KEY)).toBeNull()
    expect(vm.lastSavedAt).toBe('')
    expect(vm.currentStep).toBe(0)
    wrapper.unmount()
  })

  it('提交审核：存在"不会保存"的板块时用 warning 并逐项列出（W27 P0-5 核心）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    // 这些字段与后端模型口径不一致，必须显式告知而不是静默丢弃
    vm.formData.industryHelp.projectType = '光伏'
    vm.formData.consumptionHelp.purchaseAmount = 12
    vm.formData.honors = [{ name: '先进集体' }]
    vm.formData.collaboration.isCrossUnit = true
    vm.currentStep = 4
    await nextTick()
    await wrapper
      .findAll('el-button-stub')
      .find((b) => b.text() === '提交审核')!
      .trigger('click')
    await flushPromises()
    const [msg, , opts] = confirmMock.mock.calls[confirmMock.mock.calls.length - 1]
    expect(opts.type).toBe('warning')
    expect(msg).toContain('以下内容本次不会保存到服务器')
    expect(msg).toContain('产业帮扶')
    expect(msg).toContain('消费帮扶')
    expect(msg).toContain('荣誉记录')
    expect(msg).toContain('跨单位协作信息')
    wrapper.unmount()
  })

  it('提交审核：其余"不会保存"分支同样被列出（基建/党建/医疗/教育/村委成员/附件/就业）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.formData.infrastructureHelp.projectCount = 2
    vm.formData.partyBuildingHelp.activityType = '主题党日'
    vm.formData.medicalHelp.beneficiaries = 30
    vm.formData.educationHelp.activityCount = 4
    vm.formData.employmentHelp.employedCount = 8
    vm.formData.committeeInfo.members = [{ name: '张三' }]
    vm.fileList = [{ name: 'a.png' }]
    vm.currentStep = 4
    await nextTick()
    await wrapper
      .findAll('el-button-stub')
      .find((b) => b.text() === '提交审核')!
      .trigger('click')
    await flushPromises()
    const msg = confirmMock.mock.calls[confirmMock.mock.calls.length - 1][0] as string
    expect(msg).toContain('基础设施')
    expect(msg).toContain('党建帮扶')
    expect(msg).toContain('医疗帮扶')
    expect(msg).toContain('教育帮扶')
    expect(msg).toContain('就业帮扶')
    expect(msg).toContain('村委成员名单')
    expect(msg).toContain('附件')
    wrapper.unmount()
  })

  it('提交审核：无"不会保存"项时不显示提示段，类型为 info', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 只填必填步骤（步骤0 基础信息 + 步骤1 投资数据），专项/消费留空
    vm.formData.basicInfo.department = '某部'
    vm.formData.basicInfo.supportUnit = '某旅'
    vm.formData.basicInfo.villageName = '幸福村'
    vm.formData.basicInfo.helpType = 'industry'
    vm.formData.basicInfo.province = '520000'
    vm.formData.investmentData.forEach((d: any) => {
      d.militaryInvestment = 1
      d.localInvestment = 1
      d.leaderVisits = 1
      d.soldierVisits = 1
    })
    vm.currentStep = 4
    await nextTick()
    await wrapper
      .findAll('el-button-stub')
      .find((b) => b.text() === '提交审核')!
      .trigger('click')
    await flushPromises()
    const call = confirmMock.mock.calls[confirmMock.mock.calls.length - 1]
    expect(call[0]).toBe('确认提交数据进行审核？提交后将清除本地草稿。')
    expect(call[2].type).toBe('info')
    wrapper.unmount()
  })

  it('提交审核接口失败：带 detail 与不带 detail 两种提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.currentStep = 4
    await nextTick()
    const submitBtn = () => wrapper.findAll('el-button-stub').find((b) => b.text() === '提交审核')!
    mockPost.mockRejectedValueOnce({ response: { data: { detail: '村名重复' } } })
    await submitBtn().trigger('click')
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('村名重复')
    mockPost.mockRejectedValueOnce(new Error('boom'))
    await submitBtn().trigger('click')
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('boom')
    wrapper.unmount()
  })
})

describe('submitVillageData 数据组装', () => {
  it('新建帮扶村 + 年度数据条件提交全组合', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.formData.basicInfo.city = '贵阳市'
    vm.formData.basicInfo.county = '云岩区'
    vm.formData.basicInfo.township = '某镇'
    vm.formData.basicInfo.isRevitalizationTier = true
    vm.formData.populationData = [
      // 人口：左侧真（totalPopulation>0）
      {
        year: 2024,
        totalPopulation: 100,
        households: 0,
        povertyAlleviatedPopulation: 0,
        perCapitaIncome: 0,
        collectiveEconomyIncome: 0,
      },
      // 人口：右侧真（households>0）；收入：左侧真（perCapitaIncome>0）
      {
        year: 2023,
        totalPopulation: 0,
        households: 5,
        povertyAlleviatedPopulation: 0,
        perCapitaIncome: 5000,
        collectiveEconomyIncome: 0,
      },
      // 人口：两侧假；收入：右侧真（collectiveEconomyIncome>0）
      {
        year: 2022,
        totalPopulation: 0,
        households: 0,
        povertyAlleviatedPopulation: 0,
        perCapitaIncome: 0,
        collectiveEconomyIncome: 88,
      },
      // 全零：均不提交
      {
        year: 2021,
        totalPopulation: 0,
        households: 0,
        povertyAlleviatedPopulation: 0,
        perCapitaIncome: 0,
        collectiveEconomyIncome: 0,
      },
    ]
    vm.formData.investmentData = [
      { year: 2024, militaryInvestment: 0, localInvestment: 0, leaderVisits: 2, soldierVisits: 0 },
      { year: 2023, militaryInvestment: 0, localInvestment: 0, leaderVisits: 0, soldierVisits: 3 },
      { year: 2022, militaryInvestment: 0, localInvestment: 0, leaderVisits: 0, soldierVisits: 0 },
    ]
    await vm.submitVillageData()
    // 村创建 payload 含真值可选字段
    expect(mockPost).toHaveBeenCalledWith(
      '/supported-villages',
      expect.objectContaining({
        city: '贵阳市',
        county: '云岩区',
        township: '某镇',
        is_revitalization_tier: true,
      })
    )
    const urls = mockPost.mock.calls.map((c) => c[0] as string)
    expect(urls).toContain('/supported-villages/101/yearly/2024/population')
    expect(urls).toContain('/supported-villages/101/yearly/2023/population')
    expect(urls).not.toContain('/supported-villages/101/yearly/2022/population')
    expect(urls).toContain('/supported-villages/101/yearly/2023/income')
    expect(urls).toContain('/supported-villages/101/yearly/2022/income')
    expect(urls).not.toContain('/supported-villages/101/yearly/2021/income')
    expect(urls).toContain('/supported-villages/101/yearly/2024/force-investment')
    expect(urls).toContain('/supported-villages/101/yearly/2023/force-investment')
    expect(urls).not.toContain('/supported-villages/101/yearly/2022/force-investment')
    wrapper.unmount()
  })

  it('同「县 + 村名」已存在时改为更新，不重复建村（W27 P0-5）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.formData.basicInfo.county = '云岩区'
    // 后端已有同名村 → 应走 PUT 而不是 POST
    mockGet.mockResolvedValue({
      items: [{ id: 77, village_name: '幸福村', county: '云岩区' }],
    })
    await vm.submitVillageData()
    expect(mockPut).toHaveBeenCalledWith(
      '/supported-villages/77',
      expect.objectContaining({ village_name: '幸福村' })
    )
    expect(mockPost).not.toHaveBeenCalledWith('/supported-villages', expect.anything())
    wrapper.unmount()
  })

  it('查重接口异常时退回新建（不阻断提交）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    mockGet.mockRejectedValue(new Error('net'))
    await vm.submitVillageData()
    expect(mockPost).toHaveBeenCalledWith(
      '/supported-villages',
      expect.objectContaining({ village_name: '幸福村' })
    )
    wrapper.unmount()
  })

  it('专项帮扶与村委信息按可映射字段提交（W27 P0-5 核心）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.formData.industryHelp.investment = 10
    vm.formData.infrastructureHelp.investment = 20
    vm.formData.partyBuildingHelp.investment = 30
    vm.formData.medicalHelp.investment = 40
    vm.formData.educationHelp.investment = 50
    vm.formData.educationHelp.aidedStudents = 6
    vm.formData.committeeInfo.overview = '概况'
    vm.formData.committeeInfo.specialIndustry = '茶叶'
    await vm.submitVillageData()
    const urls = mockPost.mock.calls.map((c) => c[0] as string)
    for (const section of [
      'industry',
      'infrastructure',
      'party-building',
      'medical',
      'education',
    ]) {
      expect(urls.some((u) => u.endsWith(`/${section}`))).toBe(true)
    }
    // 教育额外带 aided_students
    const eduCall = mockPost.mock.calls.find((c) => String(c[0]).endsWith('/education'))!
    expect(eduCall[1]).toEqual(expect.objectContaining({ investment: 50, aided_students: 6 }))
    // 村委信息走专用端点，字段名与后端模型一致
    const committeeCall = mockPost.mock.calls.find((c) => String(c[0]).endsWith('/committee'))!
    expect(committeeCall[1]).toEqual(
      expect.objectContaining({
        overview: '概况',
        special_industry: '茶叶',
        collective_income_amount: 0,
      })
    )
    wrapper.unmount()
  })

  it('零值板块不提交；任一项失败则抛出并汇总（不伪装成功）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    // 零值 → 不产生请求
    vm.formData.industryHelp.investment = 0
    await vm.submitVillageData()
    const urls = mockPost.mock.calls.map((c) => c[0] as string)
    expect(urls.some((u) => u.endsWith('/industry'))).toBe(false)

    // 有值但保存失败 → 必须 throw（上层显示「提交失败」而不是「已提交审核」）
    mockPost.mockClear()
    vm.formData.infrastructureHelp.investment = 5
    mockPost.mockImplementation((url: string) => {
      if (String(url).endsWith('/infrastructure')) {
        return Promise.reject({ response: { data: { detail: '字段非法' } } })
      }
      return Promise.resolve({ data: { id: 101 } })
    })
    await expect(vm.submitVillageData()).rejects.toThrow(/1 项保存失败/)
    wrapper.unmount()
  })

  it('后端未返回 ID 时抛出（不再静默返回）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    mockPost.mockResolvedValue({ data: null })
    await expect(vm.submitVillageData()).rejects.toThrow(/未返回有效 ID/)
    wrapper.unmount()
  })

  it('村名为空时不查重、不提交（resolveVillageId 早退）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.formData.basicInfo.villageName = '   '
    await expect(vm.submitVillageData()).rejects.toThrow(/未返回有效 ID/)
    expect(mockGet).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('查重返回数组/裸 data 两种形态都能识别（unwrapList 两侧）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.formData.basicInfo.county = '云岩区'
    // 直接是数组
    mockGet.mockResolvedValue([{ id: 88, village_name: '幸福村', county: '云岩区' }])
    await vm.submitVillageData()
    expect(mockPut).toHaveBeenCalledWith('/supported-villages/88', expect.anything())

    // 裸 data 数组形态
    mockPut.mockClear()
    mockPost.mockClear()
    mockGet.mockResolvedValue({ data: [{ id: 89, village_name: '幸福村', county: '云岩区' }] })
    await vm.submitVillageData()
    expect(mockPut).toHaveBeenCalledWith('/supported-villages/89', expect.anything())
    wrapper.unmount()
  })

  it('教育仅填资助学生、村委仅填单个字段时也会提交（分支两侧）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.formData.educationHelp.investment = 0
    vm.formData.educationHelp.aidedStudents = 3 // 第二操作数为真
    vm.formData.committeeInfo.overview = ''
    vm.formData.committeeInfo.specialIndustry = ''
    vm.formData.committeeInfo.collectiveIncomeDesc = '说明' // 第三操作数为真
    vm.formData.committeeInfo.collectiveIncomeAmount = 0
    await vm.submitVillageData()
    const urls = mockPost.mock.calls.map((c) => c[0] as string)
    expect(urls.some((u) => u.endsWith('/education'))).toBe(true)

    // 只填集体收入金额（第四操作数为真）
    mockPost.mockClear()
    vm.formData.committeeInfo.collectiveIncomeDesc = ''
    vm.formData.committeeInfo.collectiveIncomeAmount = 12
    await vm.submitVillageData()
    const urls2 = mockPost.mock.calls.map((c) => c[0] as string)
    expect(urls2.some((u) => u.endsWith('/committee'))).toBe(true)
    wrapper.unmount()
  })

  it('村委全空时不提交 committee 端点', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.formData.committeeInfo.overview = ''
    vm.formData.committeeInfo.specialIndustry = ''
    vm.formData.committeeInfo.collectiveIncomeDesc = ''
    vm.formData.committeeInfo.collectiveIncomeAmount = 0
    await vm.submitVillageData()
    const urls = mockPost.mock.calls.map((c) => c[0] as string)
    expect(urls.some((u) => u.endsWith('/committee'))).toBe(false)
    wrapper.unmount()
  })

  it('查重结果不匹配（县不同 / 村名为空）时仍走新建', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.formData.basicInfo.county = '云岩区'
    mockGet.mockResolvedValue({
      items: [
        { id: 90, village_name: '幸福村', county: '南明区' }, // 村名同、县不同
        { id: 91, village_name: '', county: '云岩区' }, // 村名为空（走 '' 兜底）
        { id: 92, county: '云岩区' }, // village_name 字段缺失
      ],
    })
    await vm.submitVillageData()
    expect(mockPut).not.toHaveBeenCalled()
    expect(mockPost).toHaveBeenCalledWith(
      '/supported-villages',
      expect.objectContaining({ village_name: '幸福村' })
    )
    wrapper.unmount()
  })

  it('查重返回 null 时安全退回新建（列表解包兜底分支）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    mockGet.mockResolvedValue(null) // res ?? {} 的 null 侧
    await vm.submitVillageData()
    expect(mockPost).toHaveBeenCalledWith(
      '/supported-villages',
      expect.objectContaining({ village_name: '幸福村' })
    )
    wrapper.unmount()
  })

  it('候选记录缺 county 字段时不匹配（比较兜底分支）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.formData.basicInfo.county = '云岩区'
    mockGet.mockResolvedValue({ items: [{ id: 93, village_name: '幸福村' }] }) // 无 county
    await vm.submitVillageData()
    expect(mockPut).not.toHaveBeenCalled()
    expect(mockPost).toHaveBeenCalledWith(
      '/supported-villages',
      expect.objectContaining({ village_name: '幸福村' })
    )
    wrapper.unmount()
  })

  it('村庄名为空字符串时早退（字段缺省兜底）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.formData.basicInfo.villageName = ''
    await expect(vm.submitVillageData()).rejects.toThrow(/未返回有效 ID/)
    expect(mockGet).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('提交异常无 detail/message 时显示兜底文案「提交失败」', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.currentStep = 4
    await nextTick()
    // 查重失败后新建也失败，且异常对象既无 response.detail 也无 message
    mockGet.mockRejectedValue({})
    mockPost.mockRejectedValue({})
    await wrapper
      .findAll('el-button-stub')
      .find((b) => b.text() === '提交审核')!
      .trigger('click')
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('提交失败')
    wrapper.unmount()
  })

  it('省份为空时回退贵州省', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    // 直接调用 submitVillageData（不经步骤校验），构造无法识别省份的空值形态
    vm.formData.basicInfo.province = ''
    await vm.submitVillageData()
    expect(mockPost).toHaveBeenCalledWith(
      '/supported-villages',
      expect.objectContaining({ province: '贵州省' })
    )
    wrapper.unmount()
  })

  it('保存失败且异常无 message 时使用兜底文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.formData.industryHelp.projectType = ''
    mockPost.mockImplementation((url: string) => {
      if (String(url).endsWith('/industry')) {
        return Promise.reject({}) // 无 response.detail、无 message
      }
      return Promise.resolve({ data: { id: 101 } })
    })
    await expect(vm.submitVillageData()).rejects.toThrow(/保存失败/)
    wrapper.unmount()
  })
})

describe('文件上传与自动保存定时器', () => {
  it('上传 change 事件触发 handleFileChange', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const upload = wrapper.findComponent({ name: 'ElUpload' })
    expect(upload.exists()).toBe(true)
    upload.vm.$emit('change', { name: 'a.png' }, [{ name: 'a.png' }])
    // 提示插槽渲染
    expect(wrapper.text()).toContain('支持图片和文档格式')
    wrapper.unmount()
  })

  it('30 秒自动保存定时器触发，卸载时清理', async () => {
    vi.useFakeTimers()
    try {
      const wrapper = mountComp()
      await vi.advanceTimersByTimeAsync(0)
      const vm = wrapper.vm as any
      expect(vm.lastSavedAt).toBe('')
      await vi.advanceTimersByTimeAsync(30_000)
      expect(vm.lastSavedAt).toBeTruthy()
      expect(localStorage.getItem(DRAFT_KEY)).toBeTruthy()
      wrapper.unmount()
      // 卸载后定时器已清理，不再推进
      localStorage.removeItem(DRAFT_KEY)
      await vi.advanceTimersByTimeAsync(60_000)
      expect(localStorage.getItem(DRAFT_KEY)).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })
})
