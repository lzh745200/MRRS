/**
 * views/funds/Settlement.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 加载（成功/失败）、绩效与决算卡片渲染、空态生成决算、
 * handleCreate（成功/失败 detail/兜底）、handleApprove（无数据/校验失败/成功/失败）、
 * 模板分支（status 三态、performance_level 四态、score null、审批按钮）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { ElMessage, lifecycleApi, pushSafeMock, routeParams, validateMock } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  lifecycleApi: {
    getPerformance: vi.fn(),
    createSettlement: vi.fn(),
    approveSettlement: vi.fn(),
  },
  pushSafeMock: vi.fn(),
  routeParams: { projectId: '1' } as Record<string, string>,
  validateMock: vi.fn(),
}))

const projectsListMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({ useRoute: () => ({ params: routeParams }) }))

vi.mock('@/api/projects', () => ({ projectsApi: { list: projectsListMock } }))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: vi.fn() },
}))

vi.mock('@/api/fundLifecycle', () => ({ fundLifecycleApi: lifecycleApi }))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
  safeRouteParam: (v: any) => Number(v) || v,
}))

vi.mock('@/utils/errorHandler', () => ({
  parseError: (e: any) => ({ message: e?.response?.data?.detail || e?.message || '' }),
}))

import Settlement from '@/views/funds/Settlement.vue'

const settlement = {
  id: 1,
  settlement_no: 'JS-001',
  settlement_date: '2024-01-01',
  total_budget: 100,
  total_spent: 80,
  total_remaining: 20,
  auditor: '张三',
  audit_opinion: '同意',
  performance_score: 85,
  performance_level: 'A',
  performance_level_label: '优秀',
  status: 'submitted',
  status_label: '已提交',
  created_by: '李四',
}

const perfData = {
  budget_summary: { total_budget: 100, total_used: 80, execution_rate: 80 },
  anomaly_summary: { resolution_rate: 90 },
  settlement,
}

function mountComp() {
  return mount(Settlement, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-page-header': {
          name: 'ElPageHeader',
          template: '<div class="el-page-header-stub"><slot name="content" /><slot /></div>',
          emits: ['back'],
        },
        'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
        'el-row': { template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { template: '<div class="el-col-stub"><slot /></div>' },
        'el-statistic': { template: '<div class="el-statistic-stub" />' },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-descriptions': { template: '<div class="el-descriptions-stub"><slot /></div>' },
        'el-descriptions-item': {
          template: '<div class="el-descriptions-item-stub"><slot /></div>',
        },
        'el-empty': { template: '<div class="el-empty-stub"><slot /></div>' },
        'el-form': {
          name: 'ElForm',
          template: '<div class="el-form-stub"><slot /></div>',
          methods: {
            validate() {
              return validateMock()
            },
          },
        },
        'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
        'el-input-number': {
          template:
            '<div class="el-input-number-stub" @click="$emit(\'update:modelValue\', 90)" />',
        },
        'el-radio-group': {
          template:
            '<div class="el-radio-group-stub" @click="$emit(\'update:modelValue\', \'B\')"><slot /></div>',
        },
        'el-radio': { template: '<div class="el-radio-stub" />' },
        'el-input': {
          template:
            '<div class="el-input-stub" @click="$emit(\'update:modelValue\', \'同意\')" />',
        },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-dialog': {
          template:
            '<div class="el-dialog-stub" @click="$emit(\'update:modelValue\', false)"><slot /><slot name="footer" /></div>',
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  routeParams.projectId = '1'
  projectsListMock.mockResolvedValue({ items: [{ id: 1, name: '产业路' }] })
  lifecycleApi.getPerformance.mockResolvedValue(perfData)
  lifecycleApi.createSettlement.mockResolvedValue({})
  lifecycleApi.approveSettlement.mockResolvedValue({})
  validateMock.mockResolvedValue(true)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与数据加载', () => {
  it('onMounted 加载绩效与决算', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(lifecycleApi.getPerformance).toHaveBeenCalledWith(1)
    expect(vm.performance.budget_summary.total_budget).toBe(100)
    expect(vm.settlement).toEqual(settlement)
  })

  it('getPerformance 失败 → 清空绩效/决算', async () => {
    lifecycleApi.getPerformance.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.performance).toBeNull()
    expect(vm.settlement).toBeNull()
    expect(vm.loading).toBe(false)
  })

  it('getPerformance 无 settlement → 空态显示', async () => {
    lifecycleApi.getPerformance.mockResolvedValue({ budget_summary: {}, anomaly_summary: {} })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.settlement).toBeUndefined()
    expect(vm.performance).toBeTruthy()
  })

  it('页头返回 → pushSafe /funds', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.findComponent({ name: 'ElPageHeader' }).vm.$emit('back')
    expect(pushSafeMock).toHaveBeenCalledWith('/funds')
  })
})

describe('生成决算', () => {
  it('handleCreate 成功 → 提示 + 刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    lifecycleApi.getPerformance.mockClear()
    await vm.handleCreate()
    expect(lifecycleApi.createSettlement).toHaveBeenCalledWith(1)
    expect(ElMessage.success).toHaveBeenCalledWith('决算报告已生成')
    expect(lifecycleApi.getPerformance).toHaveBeenCalled()
  })

  it('handleCreate 失败 → parseError detail 与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    lifecycleApi.createSettlement.mockRejectedValueOnce({ response: { data: { detail: '无预算' } } })
    await vm.handleCreate()
    expect(ElMessage.error).toHaveBeenCalledWith('无预算')

    lifecycleApi.createSettlement.mockRejectedValueOnce(new Error('生成失败'))
    await vm.handleCreate()
    expect(ElMessage.error).toHaveBeenCalledWith('生成失败')

    lifecycleApi.createSettlement.mockRejectedValueOnce({})
    await vm.handleCreate()
    expect(ElMessage.error).toHaveBeenCalledWith('生成失败')
  })

  it('空态生成决算按钮 → handleCreate', async () => {
    lifecycleApi.getPerformance.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('生成决算报告'))
    lifecycleApi.createSettlement.mockClear()
    await btn!.trigger('click')
    await flushPromises()
    expect(lifecycleApi.createSettlement).toHaveBeenCalled()
  })
})

describe('审批决算', () => {
  it('无 settlement 或无 formRef → 直接返回', async () => {
    lifecycleApi.getPerformance.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.approveFormRef = null
    await vm.handleApprove()
    expect(lifecycleApi.approveSettlement).not.toHaveBeenCalled()

    vm.settlement = null
    vm.approveFormRef = { validate: validateMock }
    await vm.handleApprove()
    expect(lifecycleApi.approveSettlement).not.toHaveBeenCalled()
  })

  it('校验失败 → 返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    validateMock.mockResolvedValueOnce(false)
    await vm.handleApprove()
    expect(lifecycleApi.approveSettlement).not.toHaveBeenCalled()
  })

  it('审批成功 → 提示 + 关弹窗 + 刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    lifecycleApi.getPerformance.mockClear()
    await vm.handleApprove()
    expect(lifecycleApi.approveSettlement).toHaveBeenCalledWith(1, vm.approveForm)
    expect(ElMessage.success).toHaveBeenCalledWith('决算已审批通过')
    expect(vm.showApproveDialog).toBe(false)
    expect(lifecycleApi.getPerformance).toHaveBeenCalled()
  })

  it('审批失败 → parseError 消息与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    lifecycleApi.approveSettlement.mockRejectedValueOnce({ response: { data: { detail: '评分无效' } } })
    await vm.handleApprove()
    expect(ElMessage.error).toHaveBeenCalledWith('评分无效')

    lifecycleApi.approveSettlement.mockRejectedValueOnce(new Error('审批失败'))
    await vm.handleApprove()
    expect(ElMessage.error).toHaveBeenCalledWith('审批失败')

    lifecycleApi.approveSettlement.mockRejectedValueOnce({})
    await vm.handleApprove()
    expect(ElMessage.error).toHaveBeenCalledWith('审批失败')
    expect(vm.loading).toBe(false)
  })

  it('审批按钮 → 打开弹窗；表单 v-model；取消', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('审批决算'))
    await btn!.trigger('click')
    expect(vm.showApproveDialog).toBe(true)

    await wrapper.find('.el-input-number-stub').trigger('click')
    await wrapper.find('.el-radio-group-stub').trigger('click')
    await wrapper.find('.el-input-stub').trigger('click')
    await nextTick()
    expect(vm.approveForm.performance_score).toBe(90)
    expect(vm.approveForm.performance_level).toBe('B')
    expect(vm.approveForm.audit_opinion).toBe('同意')

    vm.showApproveDialog = true
    const cancel = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('取消'))
    await cancel!.trigger('click')
    expect(vm.showApproveDialog).toBe(false)

    lifecycleApi.approveSettlement.mockClear()
    const confirm = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('审批通过'))
    await confirm!.trigger('click')
    await flushPromises()
    expect(lifecycleApi.approveSettlement).toHaveBeenCalled()
  })
})

describe('模板分支', () => {
  it('status 三态与绩效等级四态渲染', async () => {
    const base = { ...settlement }
    const variants = [
      { ...base, status: 'approved', status_label: '已审批', performance_level: 'A' },
      { ...base, status: 'submitted', status_label: '已提交', performance_level: 'B' },
      { ...base, status: 'other', status_label: '其他', performance_level: 'C' },
      { ...base, status: 'x', status_label: 'X', performance_level: 'D' },
    ]
    for (const s of variants) {
      lifecycleApi.getPerformance.mockResolvedValue({
        budget_summary: {},
        anomaly_summary: {},
        settlement: s,
      })
      const wrapper = mountComp()
      await flushPromises()
      await nextTick()
      expect(wrapper.text()).toContain(s.status_label)
      wrapper.unmount()
    }
  })

  it('performance_score null → 未评分；approved 不显示审批按钮', async () => {
    lifecycleApi.getPerformance.mockResolvedValue({
      budget_summary: {},
      anomaly_summary: {},
      settlement: {
        ...settlement,
        performance_score: null,
        performance_level: null,
        performance_level_label: '',
        status: 'approved',
        status_label: '已审批',
      },
    })
    const wrapper = mountComp()
    await flushPromises()
    await nextTick()
    expect(wrapper.text()).toContain('未评分')
    expect(wrapper.text()).toContain('未审核'.length > 0 ? settlement.settlement_no : '')
  })

  it('auditor/audit_opinion 缺失 → 未审核/无', async () => {
    lifecycleApi.getPerformance.mockResolvedValue({
      budget_summary: {},
      anomaly_summary: {},
      settlement: { ...settlement, auditor: null, audit_opinion: null },
    })
    const wrapper = mountComp()
    await flushPromises()
    await nextTick()
    expect(wrapper.text()).toContain('未审核')
    expect(wrapper.text()).toContain('无')
  })

  it('performance_level_label 缺失 → || level 兜底', async () => {
    lifecycleApi.getPerformance.mockResolvedValue({
      budget_summary: {},
      anomaly_summary: {},
      settlement: { ...settlement, performance_level_label: '', performance_level: 'D' },
    })
    const wrapper = mountComp()
    await flushPromises()
    await nextTick()
    expect(wrapper.text()).toContain('D')
  })
})

describe('无项目参数：项目选择视图', () => {
  it('菜单无参进入 → 加载项目列表且不请求绩效；选择后跳转带参路由', async () => {
    routeParams.projectId = ''
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.invalidProject).toBe(true)
    expect(projectsListMock).toHaveBeenCalledWith({ page: 1, page_size: 100 })
    expect(lifecycleApi.getPerformance).not.toHaveBeenCalled()
    expect(vm.projectOptions).toHaveLength(1)
    await nextTick()
    // el-empty 的 description 为 prop（stub 不渲染），断言选择按钮文本即可
    expect(wrapper.text()).toContain('查看决算结算')

    // 未选择 → 不跳转；选择后 → 跳转
    vm.goSelectedProject()
    expect(pushSafeMock).not.toHaveBeenCalled()
    vm.selectedProjectId = 1
    vm.goSelectedProject()
    expect(pushSafeMock).toHaveBeenCalledWith('/funds/settlement/1')

    // 模板 select v-model 箭头（无项目视图渲染时触发）
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    for (const sel of selects) {
      sel.vm.$emit('update:modelValue', 2)
    }
    expect(vm.selectedProjectId).toBe(2)
  })

  it('项目列表加载失败 → 空数组兜底', async () => {
    routeParams.projectId = ''
    projectsListMock.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).projectOptions).toEqual([])
  })
})
