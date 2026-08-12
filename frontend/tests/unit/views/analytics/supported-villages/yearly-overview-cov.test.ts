/**
 * YearlyOverview.vue 覆盖率攻坚
 * 覆盖：板块 stats 构建（有/无数据）、趋势图加载/渲染（含空数据/异常年份）、饼图渲染、
 * 导入导出全分支、编辑弹窗、返回导航、resize/卸载清理
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const mocks = vi.hoisted(() => ({
  getSupportedVillage: vi.fn(),
  getYearlyData: vi.fn(),
  downloadTemplate: vi.fn(),
  importSectionData: vi.fn(),
  downloadAllTemplates: vi.fn(),
  importAllSectionsData: vi.fn(),
  pushSafe: vi.fn(),
  setOption: vi.fn(),
  resize: vi.fn(),
  dispose: vi.fn(),
  init: vi.fn(),
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('@/api/supportedVillage', () => ({
  getSupportedVillage: (...a: any[]) => mocks.getSupportedVillage(...a),
  getYearlyData: (...a: any[]) => mocks.getYearlyData(...a),
  downloadTemplate: (...a: any[]) => mocks.downloadTemplate(...a),
  importSectionData: (...a: any[]) => mocks.importSectionData(...a),
  downloadAllTemplates: (...a: any[]) => mocks.downloadAllTemplates(...a),
  importAllSectionsData: (...a: any[]) => mocks.importAllSectionsData(...a),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mocks.pushSafe }),
  safeRouteParam: (p: unknown) => p ?? 1,
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' }, query: {} }),
  useRouter: () => ({ push: vi.fn(), resolve: vi.fn(() => ({ name: 'x', matched: [{ path: '/x' }] })) }),
}))

vi.mock('element-plus', () => ({ ElMessage: mocks.ElMessage }))

vi.mock('@/utils/echarts', () => ({
  default: {
    init: (...a: any[]) => {
      mocks.init(...a)
      return { setOption: mocks.setOption, resize: mocks.resize, dispose: mocks.dispose }
    },
  },
}))

vi.mock('@element-plus/icons-vue', () => {
  const stub = { template: '<i class="icon-stub" />' }
  return {
    ArrowLeft: stub, Edit: stub, Download: stub, Upload: stub, User: stub,
    Money: stub, Medal: stub, OfficeBuilding: stub, Tools: stub, Stamp: stub,
    FirstAidKit: stub, ShoppingCart: stub, Briefcase: stub, Reading: stub, House: stub,
  }
})

import YearlyOverview from '@/views/analytics/supported-villages/YearlyOverview.vue'

const fullData = {
  villageId: 1,
  year: 2026,
  population: { totalPopulation: 100, totalHouseholds: 30, residentPopulation: 90 },
  income: { perCapitaIncome: 1.2, collectiveIncome: 3.4 },
  'force-investment': { seniorLeaderVisits: 5, unitSoldierVisits: 8 },
  industry: { investment: 10 },
  infrastructure: { investment: 20 },
  'party-building': { investment: 30, jointActivities: 4 },
  medical: { investment: 40, patientsServed: 50 },
  consumption: { villageProductsPurchase: 6 },
  employment: { hiredPopulation: 7, trainedPopulation: 9 },
  education: { investment: 8, aidedStudents: 12 },
  committee: { members: [{ name: 'a' }, { name: 'b' }], collectiveIncomeAmount: 5 },
}

function mountComp() {
  return mount(YearlyOverview as any, {
    global: {
      stubs: {
        // 图表容器在 el-card/el-col 内部，必须渲染 slot 才能拿到 ref
        'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
        'el-row': { template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { template: '<div class="el-col-stub"><slot /></div>' },
        'el-icon': { template: '<span class="icon-stub"><slot /></span>' },
      },
    },
  })
}

function st(wrapper: ReturnType<typeof mountComp>) {
  return (wrapper.vm as any).$.setupState
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getSupportedVillage.mockResolvedValue({ id: 1, villageName: '示范村' })
  mocks.getYearlyData.mockResolvedValue(fullData)
  mocks.downloadTemplate.mockResolvedValue({})
  mocks.downloadAllTemplates.mockResolvedValue({})
  mocks.importSectionData.mockResolvedValue({ imported: 3, failed: 0 })
  mocks.importAllSectionsData.mockResolvedValue({ imported: 5, failed: 0, sections: ['population'] })
})

describe('YearlyOverview.vue 加载与板块统计', () => {
  it('加载成功：填充村庄名/年度数据/11 个板块 stats', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.villageName).toBe('示范村')
    expect(vm.yearlyData).toEqual(fullData)
    expect(vm.sections).toHaveLength(11)
    expect(vm.sections[0].stats).toHaveLength(3) // population
    expect(vm.sections[0].stats[0].value).toBe(100)
    expect(vm.sections[1].stats[0].value).toBe('1.20') // income toFixed
    expect(vm.sections[10].stats[0].value).toBe(2) // committee members
    expect(vm.loading).toBe(false)
  })

  it('加载失败：error 提示', async () => {
    mocks.getSupportedVillage.mockRejectedValue(new Error('网络错误'))
    const wrapper = mountComp()
    await flushPromises()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('网络错误')
  })

  it('加载失败且无 message：默认文案', async () => {
    mocks.getSupportedVillage.mockRejectedValue({})
    const wrapper = mountComp()
    await flushPromises()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('加载数据失败')
  })

  it('yearlyData 未加载(null)时：各板块 stats 为空（?. 空值分支）', async () => {
    const wrapper = mountComp()
    // 不 await flushPromises：loadAllData 未完成，yearlyData 仍为 null
    const vm = wrapper.vm as any
    expect(vm.yearlyData).toBeNull()
    expect(vm.sections).toHaveLength(11)
    expect(vm.sections.every((s: any) => s.stats.length === 0)).toBe(true)
    expect(vm.investmentDistribution).toEqual([])
  })

  it('committee 板块字段缺失：成员数/集体收入 0 兜底', async () => {
    mocks.getYearlyData.mockResolvedValue({ committee: {} })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const committee = vm.sections.find((s: any) => s.key === 'committee')
    expect(committee.stats[0].value).toBe(0)
    expect(committee.stats[1].value).toBe('0.00')
  })

  it('employment/education 板块字段缺失：0 兜底', async () => {
    mocks.getYearlyData.mockResolvedValue({ employment: {}, education: {} })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const employment = vm.sections.find((s: any) => s.key === 'employment')
    expect(employment.stats[0].value).toBe(0)
    expect(employment.stats[1].value).toBe(0)
    const education = vm.sections.find((s: any) => s.key === 'education')
    expect(education.stats[0].value).toBe('0.00')
    expect(education.stats[1].value).toBe(0)
  })

  it('party/medical/consumption 板块字段缺失：0 兜底', async () => {
    mocks.getYearlyData.mockResolvedValue({
      'party-building': {},
      medical: {},
      consumption: {},
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const party = vm.sections.find((s: any) => s.key === 'party_building')
    expect(party.stats[0].value).toBe('0.00')
    expect(party.stats[1].value).toBe(0)
    const medical = vm.sections.find((s: any) => s.key === 'medical')
    expect(medical.stats[0].value).toBe('0.00')
    expect(medical.stats[1].value).toBe(0)
    const consumption = vm.sections.find((s: any) => s.key === 'consumption')
    expect(consumption.stats[0].value).toBe('0.00')
  })

  it('force/industry/infrastructure 板块字段缺失：0 兜底', async () => {
    mocks.getYearlyData.mockResolvedValue({
      'force-investment': {},
      industry: {},
      infrastructure: {},
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const force = vm.sections.find((s: any) => s.key === 'force_investment')
    expect(force.stats[0].value).toBe(0)
    expect(force.stats[1].value).toBe(0)
    const industry = vm.sections.find((s: any) => s.key === 'industry')
    expect(industry.stats[0].value).toBe('0.00')
    const infra = vm.sections.find((s: any) => s.key === 'infrastructure')
    expect(infra.stats[0].value).toBe('0.00')
  })

  it('population/income 板块字段缺失：0 兜底', async () => {
    mocks.getYearlyData.mockResolvedValue({ population: {}, income: {} })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const population = vm.sections.find((s: any) => s.key === 'population')
    expect(population.stats.map((x: any) => x.value)).toEqual([0, 0, 0])
    const income = vm.sections.find((s: any) => s.key === 'income')
    expect(income.stats.map((x: any) => x.value)).toEqual(['0.00', '0.00'])
  })

  it('无年度数据：各板块 stats 为空数组', async () => {
    mocks.getYearlyData.mockResolvedValue({ villageId: 1, year: 2026 })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.sections.every((s: any) => s.stats.length === 0)).toBe(true)
    expect(vm.investmentDistribution).toEqual([])
  })
})

describe('YearlyOverview.vue 趋势图', () => {
  it('loadTrendData：有收入年份入列、异常年份跳过、渲染图表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    // mount 时的 loadAllData 已消费一次默认 mock，此处为 loadTrendData 的 6 次调用设置序列
    mocks.getYearlyData
      .mockResolvedValueOnce({ income: { perCapitaIncome: 1.5, collectiveIncome: 2.5 } })
      .mockRejectedValueOnce(new Error('no data'))
      .mockResolvedValueOnce({ income: { perCapitaIncome: null, collectiveIncome: null } })
      .mockResolvedValueOnce({ income: { perCapitaIncome: 3 } })
      .mockResolvedValueOnce({ income: { perCapitaIncome: null, collectiveIncome: 4 } })
      .mockResolvedValue({})
    const vm = wrapper.vm as any
    await vm.loadTrendData()
    await nextTick()
    expect(vm.trendData.years.length).toBeGreaterThan(0)
    expect(mocks.setOption).toHaveBeenCalled()
  })

  it('renderTrendChart：无趋势数据 → 空态标题', async () => {
    mocks.getYearlyData.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.loadTrendData()
    await nextTick()
    expect(mocks.setOption).toHaveBeenCalled()
    const lastCall = mocks.setOption.mock.calls.at(-1)[0]
    expect(lastCall.title).toBeTruthy() // 暂无收入数据
  })
})

describe('YearlyOverview.vue 饼图与分布', () => {
  it('investmentDistribution：仅统计 >0 的投入', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.investmentDistribution).toEqual([
      { name: '产业帮扶', value: 10 },
      { name: '基础设施', value: 20 },
      { name: '党建帮扶', value: 30 },
      { name: '医疗帮扶', value: 40 },
      { name: '教育帮扶', value: 8 },
    ])
  })

  it('yearlyData 变化 → 饼图重渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    mocks.setOption.mockClear()
    mocks.getYearlyData.mockResolvedValue({ ...fullData, industrySupport: { investment: 99 } })
    await (wrapper.vm as any).loadAllData()
    await nextTick()
    expect(mocks.setOption).toHaveBeenCalled()
  })

  it('renderPieChart：图表容器不存在时提前返回', async () => {
    // 不渲染 slot 的 stub → 图表容器 ref 为 null
    const wrapper = mount(YearlyOverview as any, {
      global: {
        stubs: { 'el-card': true, 'el-row': true, 'el-col': true, 'el-icon': true },
      },
    })
    await flushPromises()
    // watch(yearlyData) → renderPieChart → ref 为 null → 提前 return，不创建图表
    expect(mocks.init).not.toHaveBeenCalled()
  })
})

describe('YearlyOverview.vue 导入导出', () => {
  it('handleDownloadTemplate 成功/失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDownloadTemplate('population')
    expect(mocks.downloadTemplate).toHaveBeenCalled()
    mocks.downloadTemplate.mockRejectedValue(new Error('x'))
    await vm.handleDownloadTemplate('population')
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('模板下载失败')
  })

  it('handleDownloadAllTemplates 成功/失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDownloadAllTemplates()
    expect(mocks.downloadAllTemplates).toHaveBeenCalled()
    expect(mocks.ElMessage.success).toHaveBeenCalled()
    mocks.downloadAllTemplates.mockRejectedValue(new Error('网络'))
    await vm.handleDownloadAllTemplates()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('网络')
    mocks.downloadAllTemplates.mockRejectedValue({})
    await vm.handleDownloadAllTemplates()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('模板下载失败')
    expect(vm.downloadingAll).toBe(false)
  })

  it('handleImportSection：无文件/非 Excel/超 10MB 拒绝', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleImportSection('population', {})
    expect(mocks.importSectionData).not.toHaveBeenCalled()
    await vm.handleImportSection('population', { raw: { name: 'a.txt', size: 100 } })
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('只能上传 Excel 文件(.xlsx/.xls)')
    await vm.handleImportSection('population', { raw: { name: 'a.xlsx', size: 11 * 1024 * 1024 } })
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('文件大小不能超过 10MB')
    // file 为 null → 提前返回
    await vm.handleImportSection('population', null)
    await vm.handleImportSection('population', undefined)
    expect(mocks.importSectionData).not.toHaveBeenCalled()
  })

  it('handleImportSection：成功（含 failed>0）与失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mocks.importSectionData.mockResolvedValue({ imported: 3, failed: 2 })
    await vm.handleImportSection('population', { raw: { name: 'a.xlsx', size: 100 } })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('导入成功 3 条')
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('2 条导入失败')
    mocks.importSectionData.mockRejectedValue({ response: { data: { detail: '格式错误' } } })
    await vm.handleImportSection('population', { raw: { name: 'a.xlsx', size: 100 } })
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('格式错误')
    mocks.importSectionData.mockRejectedValue({ message: '失败' })
    await vm.handleImportSection('population', { raw: { name: 'a.xlsx', size: 100 } })
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('失败')
    expect(vm.sectionImporting).toBe('')
  })

  it('handleImportSection：rows/0 兜底、无 message 失败、非字符串 message', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // imported 缺失 → rows 兜底
    mocks.importSectionData.mockResolvedValue({ rows: 6 })
    await vm.handleImportSection('population', { raw: { name: 'a.xlsx', size: 100 } })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('导入成功 6 条')
    // 全缺失 → 0 兜底
    mocks.importSectionData.mockResolvedValue({})
    await vm.handleImportSection('population', { raw: { name: 'a.xlsx', size: 100 } })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('导入成功 0 条')
    // 失败无任何 message → 默认文案
    mocks.importSectionData.mockRejectedValue({})
    await vm.handleImportSection('population', { raw: { name: 'a.xlsx', size: 100 } })
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('导入失败')
    // message 非字符串 → 提示检查文件格式
    mocks.importSectionData.mockRejectedValue({ message: { code: 500 } })
    await vm.handleImportSection('population', { raw: { name: 'a.xlsx', size: 100 } })
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('导入失败，请检查文件格式')
  })

  it('handleImportAll：成功（含 failed>0 与失败）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mocks.importAllSectionsData.mockResolvedValue({ imported: 5, failed: 1, sections: ['a', 'b'] })
    await vm.handleImportAll({ raw: { name: 'all.xlsx', size: 100 } })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('全部导入完成：成功 5 条（2 个板块）')
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('1 条数据导入失败')
    mocks.importAllSectionsData.mockRejectedValue(new Error('全部导入失败'))
    await vm.handleImportAll({ raw: { name: 'all.xlsx', size: 100 } })
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('全部导入失败')
    expect(vm.importingAll).toBe(false)
  })

  it('handleImportAll：无 raw 取 file、sheets/rows/0 兜底、无 message 失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 无 raw → 直接用 file；sections 缺失 → sheets 兜底
    mocks.importAllSectionsData.mockResolvedValue({ imported: 0, failed: 0, sheets: 3 })
    await vm.handleImportAll({ name: 'all.xlsx', size: 100 })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('全部导入完成：成功 0 条（3 个板块）')
    // 全部缺失 → 0 兜底
    mocks.importAllSectionsData.mockResolvedValue({})
    await vm.handleImportAll({ raw: { name: 'a.xlsx', size: 100 } })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('全部导入完成：成功 0 条（0 个板块）')
    // imported 缺失 → rows 兜底
    mocks.importAllSectionsData.mockResolvedValue({ rows: 7, sections: ['x'] })
    await vm.handleImportAll({ raw: { name: 'a.xlsx', size: 100 } })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('全部导入完成：成功 7 条（1 个板块）')
    // 失败无 message → 默认文案
    mocks.importAllSectionsData.mockRejectedValue({})
    await vm.handleImportAll({ raw: { name: 'a.xlsx', size: 100 } })
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('全部导入失败')
  })
})

describe('YearlyOverview.vue 交互与生命周期', () => {
  it('openEditDialog：找到板块标题并打开弹窗', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openEditDialog('population')
    expect(vm.editSectionKey).toBe('population')
    expect(vm.editSectionTitle).toBe('人口数据')
    expect(vm.editDialogVisible).toBe(true)
  })

  it('openEditDialog：未知板块 key → 标题空字符串兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openEditDialog('unknown_key')
    expect(vm.editSectionKey).toBe('unknown_key')
    expect(vm.editSectionTitle).toBe('')
    expect(vm.editDialogVisible).toBe(true)
  })

  it('handleBack：跳转村庄详情页', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleBack()
    expect(mocks.pushSafe).toHaveBeenCalledWith('/supported-villages/1')
  })

  it('resize：防抖后 resize 图表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleChartResize()
    vm.handleChartResize()
    await new Promise((r) => setTimeout(r, 250))
    expect(mocks.resize).toHaveBeenCalled()
  })

  it('年份选择变更：v-model 更新并触发 loadAllData', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const select = wrapper.findComponent({ name: 'ElSelect' })
    select.vm.$emit('update:modelValue', 2024)
    await nextTick()
    expect(vm.selectedYear).toBe(2024)
    select.vm.$emit('change', 2024)
    await flushPromises()
    expect(mocks.getYearlyData).toHaveBeenCalled()
  })

  it('板块卡片按钮：填写/模板按钮点击触发对应函数', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 自动 stub 渲染 el-button-stub 标签（不渲染 slot 文本），DOM click 转发给父级 @click
    const buttons = wrapper.findAll('el-button-stub')
    expect(buttons.length).toBeGreaterThan(0)
    // 遍历触发：其中包含"填写"(@click=openEditDialog)与"模板"(@click=handleDownloadTemplate)按钮
    for (const b of buttons) {
      await b.trigger('click')
    }
    expect(vm.editDialogVisible).toBe(true)
    expect(vm.editSectionKey).toBeTruthy()
    expect(vm.editSectionTitle).toBeTruthy()
    expect(mocks.downloadTemplate).toHaveBeenCalled()
  })

  it('上传组件：before-upload 拦截 + on-change 触发导入', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const uploads = wrapper.findAllComponents({ name: 'ElUpload' })
    expect(uploads.length).toBeGreaterThan(0)
    const allUpload = uploads[0]
    // 自动 stub 保留原始 kebab-case 键
    const before = (allUpload.vm.$attrs as any)['before-upload']
    expect(typeof before).toBe('function')
    expect(before()).toBe(false)
    const onChange = (allUpload.vm.$attrs as any)['on-change']
    onChange({ raw: { name: 'all.xlsx', size: 100 } })
    await flushPromises()
    expect(mocks.importAllSectionsData).toHaveBeenCalled()
    // 板块级上传：before-upload 拦截 + on-change → handleImportSection
    const sectionUpload = uploads[1]
    const secBefore = (sectionUpload.vm.$attrs as any)['before-upload']
    expect(secBefore()).toBe(false)
    const secOnChange = (sectionUpload.vm.$attrs as any)['on-change']
    secOnChange({ raw: { name: 'sec.xlsx', size: 100 } })
    await flushPromises()
    expect(mocks.importSectionData).toHaveBeenCalled()
  })

  it('编辑弹窗关闭：触发 v-model 更新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openEditDialog('income')
    await nextTick()
    const dialog = wrapper.findComponent({ name: 'ElDialog' })
    dialog.vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.editDialogVisible).toBe(false)
  })

  it('tooltip formatter：趋势图与饼图格式化逻辑', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // availableYears computed 求值（模板 stub 不渲染 option，需直接访问）
    expect(vm.availableYears.length).toBeGreaterThan(0)
    expect(vm.availableYears[0]).toBeGreaterThan(2017)
    await vm.loadTrendData()
    await nextTick()
    const trendOption = mocks.setOption.mock.calls.map((c: any[]) => c[0]).find((o: any) => o.series?.[0]?.type === 'line')
    const trendFmt = trendOption.tooltip.formatter
    const trendHtml = trendFmt([{ marker: 'm', seriesName: '人均纯收入', value: 1.234 }, { marker: 'm', seriesName: '集体收入', value: 2.5 }])
    expect(trendHtml).toContain('万元')
    // 单对象参数（非数组）与 value 为空的兜底分支
    const singleHtml = trendFmt({ marker: 'm', seriesName: '集体收入', value: null })
    expect(singleHtml).toContain('万元')
    const pieOption = mocks.setOption.mock.calls.map((c: any[]) => c[0]).find((o: any) => o.series?.[0]?.type === 'pie')
    const pieFmt = pieOption.tooltip.formatter
    const pieHtml = pieFmt({ marker: 'm', name: '产业帮扶', value: 10, percent: 25 })
    expect(pieHtml).toContain('25%')
  })

  it('卸载：移除监听并 dispose 图表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    // 触发图表创建
    await (wrapper.vm as any).loadTrendData()
    await nextTick()
    wrapper.unmount()
    expect(mocks.dispose).toHaveBeenCalled()
  })
})
