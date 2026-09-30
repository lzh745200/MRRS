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
const { ElMessage, confirmMock, mockPost } = vi.hoisted(() => {
  return {
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
    },
    confirmMock: vi.fn(),
    mockPost: vi.fn(),
  }
})

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/request', () => ({
  post: mockPost,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

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
        { year: currentYear - 6, militaryInvestment: 5, localInvestment: 6, leaderVisits: 2, soldierVisits: 3 },
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
  mockPost.mockResolvedValue({ data: { id: 101 } })
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
  it('保存草稿：服务器成功与失败两条提示路径', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('保存草稿'))!
    // 成功
    mockPost.mockResolvedValueOnce({ data: { id: 101 } })
    await btn.trigger('click')
    await flushPromises()
    expect(ElMessage.success).toHaveBeenCalledWith('草稿已保存到服务器')
    // 失败（落本地）
    mockPost.mockRejectedValueOnce(new Error('net'))
    await btn.trigger('click')
    await flushPromises()
    expect(ElMessage.success).toHaveBeenCalledWith('草稿已保存到本地')
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
    await wrapper.findAll('el-button-stub').find((b) => b.text() === '提交审核')!.trigger('click')
    await flushPromises()
    expect(ElMessage.error).not.toHaveBeenCalled()
    expect(ElMessage.success).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('提交审核：确认非 cancel 异常时按取消处理不报错', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    vm.currentStep = 4
    await nextTick()
    // 确认弹窗 reject 非 'cancel' 值 → 走 ElMessage.error
    confirmMock.mockRejectedValueOnce('close')
    await wrapper.findAll('el-button-stub').find((b) => b.text() === '提交审核')!.trigger('click')
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('提交失败')
    wrapper.unmount()
  })

  it('提交审核成功：清除草稿、提示成功、回到步骤0', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    // 先保存一次草稿，验证提交后清除
    vm.saveDraftToLocal()
    expect(localStorage.getItem(DRAFT_KEY)).toBeTruthy()
    vm.currentStep = 4
    await nextTick()
    await wrapper.findAll('el-button-stub').find((b) => b.text() === '提交审核')!.trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledWith('确认提交数据进行审核？提交后将清除本地草稿。', '提交确认', {
      type: 'info',
    })
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
    expect(ElMessage.error).toHaveBeenCalledWith('提交失败')
    wrapper.unmount()
  })
})

describe('submitVillageData 数据组装', () => {
  it('villageId 直连 + 年度数据条件提交全组合', async () => {
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
      { year: 2024, totalPopulation: 100, households: 0, povertyAlleviatedPopulation: 0, perCapitaIncome: 0, collectiveEconomyIncome: 0 },
      // 人口：右侧真（households>0）；收入：左侧真（perCapitaIncome>0）
      { year: 2023, totalPopulation: 0, households: 5, povertyAlleviatedPopulation: 0, perCapitaIncome: 5000, collectiveEconomyIncome: 0 },
      // 人口：两侧假；收入：右侧真（collectiveEconomyIncome>0）
      { year: 2022, totalPopulation: 0, households: 0, povertyAlleviatedPopulation: 0, perCapitaIncome: 0, collectiveEconomyIncome: 88 },
      // 全零：均不提交
      { year: 2021, totalPopulation: 0, households: 0, povertyAlleviatedPopulation: 0, perCapitaIncome: 0, collectiveEconomyIncome: 0 },
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

  it('villageId 嵌套形态与空值早退；可选字段假值侧为 undefined', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fillBasic(vm)
    // 嵌套 { data: { id } }
    mockPost.mockResolvedValue({ data: { data: { id: 102 } } })
    await vm.submitVillageData()
    expect(mockPost).toHaveBeenCalledWith(
      '/supported-villages',
      expect.objectContaining({
        city: undefined,
        county: undefined,
        township: undefined,
        is_revitalization_tier: undefined,
      })
    )
    // res.data 为 null → 直接返回，不发年度请求
    mockPost.mockClear()
    mockPost.mockResolvedValue({ data: null })
    const result = await vm.submitVillageData()
    expect(result).toBeNull()
    expect(mockPost).toHaveBeenCalledTimes(1)
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
