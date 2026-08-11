/**
 * views/system/ZeroTrust.vue 覆盖率攻坚
 * 覆盖：信任评估、事件统计、策略列表、访问评估、安全事件全分支
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick, defineComponent, h } from 'vue'

enableAutoUnmount(afterEach)

const { ElMessage, zeroTrustApi } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  zeroTrustApi: {
    getAssessment: vi.fn(),
    getEventStats: vi.fn(),
    listPolicies: vi.fn(),
    evaluateAccess: vi.fn(),
    listEvents: vi.fn(),
  },
}))

vi.mock('@/api/zeroTrust', () => ({
  zeroTrustApi,
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: vi.fn(() => Promise.resolve('confirm')), alert: vi.fn() },
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

import ZeroTrust from '@/views/system/ZeroTrust.vue'

const assessmentData = {
  success: true,
  data: {
    level: '良好',
    score: 75,
    factors: [
      { factor: '设备', score: 90, status: 'pass', detail: '正常' },
      { factor: '网络', score: 50, status: 'warning', detail: '异地' },
      { factor: '行为', score: 20, status: 'fail', detail: '异常' },
      { factor: '未知', score: 60, status: 'unknown', detail: '-' },
    ],
    recommendations: ['建议启用 MFA'],
    assessed_at: '2024-01-01T10:00:00Z',
  },
}

const eventStatsData = {
  success: true,
  data: {
    total_events: 10,
    high_severity_count: 2,
    by_severity: { critical: 2, high: 1, medium: 3, low: 4 },
    by_type: { auth_failure: 5, data_leak: 5 },
    security_posture: 'secure',
  },
}

const policiesData = {
  success: true,
  data: {
    policies: [
      { id: 'p1', name: '策略1', description: '描述', category: 'authentication', enabled: true, severity: 'critical', conditions: { ip: '1.1.1.1' }, actions: ['allow'] },
      { id: 'p2', name: '策略2', description: '', category: 'network', enabled: false, severity: 'low' },
    ],
    total: 2,
    enabled_count: 1,
  },
}

const eventsData = {
  success: true,
  data: {
    items: [
      { id: 1, event_type: 'auth_failure', source: '10.0.0.1', severity: 'critical', message: '多次失败', timestamp: '2024-01-01T10:00:00Z' },
      { id: 2, event_type: 'data_leak', source: '10.0.0.2', severity: 'medium', message: '泄露', timestamp: 'not-a-date' },
    ],
    total: 2,
  },
}

const ElFormStub = defineComponent({
  name: 'ElForm',
  props: ['model', 'rules'],
  emits: ['update:modelValue'],
  setup(_props, { expose, slots }) {
    expose({ validate: vi.fn(() => Promise.resolve(true)), resetFields: vi.fn() })
    return () => h('form', { class: 'el-form-stub' }, [slots.default?.()])
  },
})

async function mountComp() {
  const w = mount(ZeroTrust, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot /><slot name="header" /></div>',
        },
        'el-skeleton': { name: 'ElSkeleton', template: '<div class="el-skeleton-stub" />' },
        'el-empty': { name: 'ElEmpty', template: '<div class="el-empty-stub"><slot /></div>' },
        'el-tag': {
          name: 'ElTag',
          template: '<span class="el-tag-stub"><slot /></span>',
          emits: ['close'],
        },
        'el-button': {
          name: 'ElButton',
          template: '<button class="el-button-stub"><slot /></button>',
        },
        'el-icon': { name: 'ElIcon', template: '<span><slot /></span>' },
        'el-table': { name: 'ElTable', template: '<table class="el-table-stub"><slot /></table>' },
        'el-table-column': {
          name: 'ElTableColumn',
          props: ['formatter'],
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" />{{ formatter ? formatter(rowA) : "" }}</div>',
          data() {
            return {
              rowA: {
                factor: '设备', score: 90, status: 'pass', detail: '正常',
                name: '策略1', category: 'authentication', severity: 'critical', enabled: true, description: '描述',
                conditions: { ip: '1.1.1.1' }, actions: ['allow'],
                event_type: 'auth_failure', source: '10.0.0.1', message: '多次失败', timestamp: '2024-01-01T10:00:00Z',
              },
              rowB: {
                factor: '网络', score: 50, status: 'warning', detail: '异地',
                name: '策略2', category: 'network', severity: 'low', enabled: false, description: '',
                event_type: 'data_leak', source: '10.0.0.2', message: '泄露', timestamp: 'not-a-date',
              },
            }
          },
        },
        'el-row': { name: 'ElRow', template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { name: 'ElCol', template: '<div class="el-col-stub"><slot /></div>' },
        'el-statistic': {
          name: 'ElStatistic',
          template: '<div class="el-statistic-stub"><slot /></div>',
          props: ['title', 'value'],
        },
        'el-select': {
          name: 'ElSelect',
          props: ['modelValue'],
          emits: ['update:modelValue', 'change'],
          template:
            '<select class="el-select-stub" @change="$emit(\'update:modelValue\', $event.target.value); $emit(\'change\', $event.target.value)"><slot /></select>',
        },
        'el-option': { name: 'ElOption', props: ['value'], template: '<option :value="value"><slot /></option>' },
        'el-checkbox': {
          name: 'ElCheckbox',
          props: ['modelValue'],
          emits: ['update:modelValue', 'change'],
          template:
            '<label class="el-checkbox-stub"><input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked); $emit(\'change\', $event.target.checked)" /><slot /></label>',
        },
        'el-form': ElFormStub,
        'el-form-item': { name: 'ElFormItem', template: '<div><slot /></div>' },
        'el-input': {
          name: 'ElInput',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<input class="el-input-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        'el-alert': {
          name: 'ElAlert',
          template: '<div class="el-alert-stub"><slot /><slot name="title" /></div>',
        },
        'el-descriptions': { name: 'ElDescriptions', template: '<dl><slot /></dl>' },
        'el-descriptions-item': {
          name: 'ElDescriptionsItem',
          template: '<div class="el-desc-item-stub"><slot /></div>',
        },
        'el-pagination': {
          name: 'ElPagination',
          template: '<div class="el-pagination-stub"><slot /></div>',
        },
      },
    },
  })
  await flushPromises()
  await nextTick()
  return w
}

beforeEach(() => {
  vi.clearAllMocks()
  zeroTrustApi.getAssessment.mockResolvedValue(assessmentData)
  zeroTrustApi.getEventStats.mockResolvedValue(eventStatsData)
  zeroTrustApi.listPolicies.mockResolvedValue(policiesData)
  zeroTrustApi.evaluateAccess.mockResolvedValue({
    success: true,
    data: { resource: '/api', action: 'read', username: 'admin', result: 'allowed', message: '允许', evaluated_at: '2024-01-01T10:00:00Z' },
  })
  zeroTrustApi.listEvents.mockResolvedValue(eventsData)
})

describe('ZeroTrust.vue', () => {
  it('渲染并加载全部数据', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(zeroTrustApi.getAssessment).toHaveBeenCalled()
    expect(zeroTrustApi.getEventStats).toHaveBeenCalled()
    expect(zeroTrustApi.listPolicies).toHaveBeenCalled()
    expect(zeroTrustApi.listEvents).toHaveBeenCalled()
    expect(vm.assessment?.score).toBe(75)
    expect(vm.eventStats?.total_events).toBe(10)
    expect(vm.policies.length).toBe(2)
    expect(vm.events.length).toBe(2)
    expect(vm.scoreColorClass).toBe('score-green')
    expect(vm.levelTagType).toBe('success')
    expect(vm.postureTagType).toBe('success')
    expect(vm.postureLabel).toBe('安全')
  })

  it('refreshAll 成功', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vi.clearAllMocks()
    zeroTrustApi.getAssessment.mockResolvedValue(assessmentData)
    zeroTrustApi.getEventStats.mockResolvedValue(eventStatsData)
    zeroTrustApi.listPolicies.mockResolvedValue(policiesData)
    zeroTrustApi.listEvents.mockResolvedValue(eventsData)
    await vm.refreshAll()
    expect(ElMessage.success).toHaveBeenCalledWith('刷新完成')
    expect(vm.refreshingAll).toBe(false)
  })

  it('refreshAll 失败 → 各模块自行捕获（刷新完成仍触发，防御性 catch 不可达）', async () => {
    zeroTrustApi.getAssessment.mockRejectedValue(new Error('boom'))
    const w = await mountComp()
    const vm = w.vm as any
    await vm.refreshAll()
    // 每个 load* 内部自行捕获异常，Promise.all 不会 reject → '刷新失败' 分支不可达
    expect(ElMessage.success).toHaveBeenCalledWith('刷新完成')
    expect(vm.refreshingAll).toBe(false)
  })

  it('loadAssessment：无数据 → null', async () => {
    zeroTrustApi.getAssessment.mockResolvedValue({ success: false })
    const w = await mountComp()
    expect((w.vm as any).assessment).toBeNull()
    expect((w.vm as any).scoreColorClass).toBe('score-green')
    expect((w.vm as any).levelTagType).toBe('info')
  })

  it('loadAssessment：异常 → null + 错误提示', async () => {
    zeroTrustApi.getAssessment.mockRejectedValue({ response: { data: { detail: '评估服务异常' } } })
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('评估服务异常')
    expect((w.vm as any).assessment).toBeNull()
  })

  it('loadAssessment：异常无 detail → 默认文案', async () => {
    zeroTrustApi.getAssessment.mockRejectedValue({})
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('加载信任评估失败')
  })

  it('loadAssessment：异常带 message → 展示 message', async () => {
    zeroTrustApi.getAssessment.mockRejectedValue({ message: '评估服务不可用' })
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('评估服务不可用')
  })

  it('loadStats：无数据 → null + 姿态默认', async () => {
    zeroTrustApi.getEventStats.mockResolvedValue({ success: false })
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.eventStats).toBeNull()
    expect(vm.postureTagType).toBe('info')
    expect(vm.postureLabel).toBe('未知')
  })

  it('loadStats：姿态 warning / normal', async () => {
    zeroTrustApi.getEventStats.mockResolvedValue({
      success: true,
      data: { ...eventStatsData.data, security_posture: 'warning' },
    })
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.postureTagType).toBe('danger')
    expect(vm.postureLabel).toBe('警告')
    zeroTrustApi.getEventStats.mockResolvedValue({
      success: true,
      data: { ...eventStatsData.data, security_posture: 'normal' },
    })
    await vm.loadStats()
    expect(vm.postureLabel).toBe('一般')
  })

  it('loadStats：异常 → null + 错误提示', async () => {
    zeroTrustApi.getEventStats.mockRejectedValue({})
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('加载安全事件统计失败')
    expect((w.vm as any).eventStats).toBeNull()
  })

  it('loadStats：异常带 message → 展示 message', async () => {
    zeroTrustApi.getEventStats.mockRejectedValue({ message: '统计服务异常' })
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('统计服务异常')
  })

  it('loadStats：异常为 null → 默认文案', async () => {
    zeroTrustApi.getEventStats.mockRejectedValue(null)
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('加载安全事件统计失败')
  })

  it('事件统计：空分布 → 暂无数据标签', async () => {
    zeroTrustApi.getEventStats.mockResolvedValue({
      success: true,
      data: {
        total_events: 0,
        high_severity_count: 0,
        by_severity: {},
        by_type: {},
        security_posture: 'secure',
      },
    })
    const w = await mountComp()
    expect(w.text()).toContain('暂无数据')
  })

  it('loadPolicies：无数据 → 空策略', async () => {
    zeroTrustApi.listPolicies.mockResolvedValue({ success: false })
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.policies).toEqual([])
    expect(vm.policyTotal).toBe(0)
    expect(vm.policyEnabledCount).toBe(0)
  })

  it('loadPolicies：异常 → 空 + 错误提示', async () => {
    zeroTrustApi.listPolicies.mockRejectedValue({})
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('加载安全策略失败')
    expect((w.vm as any).policies).toEqual([])
  })

  it('loadPolicies：异常带 message → 展示 message', async () => {
    zeroTrustApi.listPolicies.mockRejectedValue({ message: '策略服务异常' })
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('策略服务异常')
  })

  it('loadPolicies：异常为 null → 默认文案', async () => {
    zeroTrustApi.listPolicies.mockRejectedValue(null)
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('加载安全策略失败')
  })

  it('loadPolicies：data 缺字段 → 空兜底', async () => {
    zeroTrustApi.listPolicies.mockResolvedValue({ success: true, data: {} })
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.policies).toEqual([])
    expect(vm.policyTotal).toBe(0)
    expect(vm.policyEnabledCount).toBe(0)
  })

  it('loadPolicies：筛选参数', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.policyFilterCategory = 'authentication'
    vm.policyFilterEnabledOnly = true
    await vm.loadPolicies()
    expect(zeroTrustApi.listPolicies).toHaveBeenCalledWith({ category: 'authentication', enabled_only: true })
  })

  it('策略筛选控件：分类 select / 启用 checkbox', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const selects = w.findAll('.el-select-stub')
    await selects[0].setValue('network')
    expect(vm.policyFilterCategory).toBe('network')
    vi.clearAllMocks()
    zeroTrustApi.listPolicies.mockResolvedValue(policiesData)
    const checkbox = w.find('.el-checkbox-stub input')
    await checkbox.setValue(true)
    await nextTick()
    await checkbox.setValue(false)
    await nextTick()
    expect(vm.policyFilterEnabledOnly).toBe(false)
    checkbox.setValue(true)
    await nextTick()
    expect(vm.policyFilterEnabledOnly).toBe(true)
    expect(zeroTrustApi.listPolicies).toHaveBeenCalledWith({ category: 'network', enabled_only: true })
  })

  it('loadStats：异常带 response.detail → 展示 detail', async () => {
    zeroTrustApi.getEventStats.mockRejectedValue({ response: { data: { detail: '统计服务拒绝' } } })
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('统计服务拒绝')
  })

  it('loadPolicies：异常带 response.detail → 展示 detail', async () => {
    zeroTrustApi.listPolicies.mockRejectedValue({ response: { data: { detail: '策略服务拒绝' } } })
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('策略服务拒绝')
  })

  it('handleEvaluate：异常带 response.detail → 展示 detail', async () => {
    zeroTrustApi.evaluateAccess.mockRejectedValue({ response: { data: { detail: '评估服务拒绝' } } })
    const w = await mountComp()
    const vm = w.vm as any
    vm.evaluateForm.resource = '/api'
    vm.evaluateForm.action = 'read'
    await vm.handleEvaluate()
    expect(ElMessage.error).toHaveBeenCalledWith('评估服务拒绝')
  })

  it('loadEvents：异常带 response.detail → 展示 detail', async () => {
    zeroTrustApi.listEvents.mockRejectedValue({ response: { data: { detail: '事件服务拒绝' } } })
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('事件服务拒绝')
  })

  it('handleEvaluate：拒绝结果 → 告警类型走拒绝分支', async () => {
    zeroTrustApi.evaluateAccess.mockResolvedValue({
      success: true,
      data: { resource: '/api', action: 'write', username: 'admin', result: 'denied', message: '拒绝', evaluated_at: '2024-01-01T10:00:00Z' },
    })
    const w = await mountComp()
    const vm = w.vm as any
    vm.evaluateForm.resource = '/api'
    vm.evaluateForm.action = 'write'
    await vm.handleEvaluate()
    await nextTick()
    expect(vm.evaluateResult?.result).toBe('denied')
  })

  it('handleEvaluate：校验失败 → 返回', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.evaluateFormRef = { validate: vi.fn(() => Promise.reject(false)) }
    await vm.handleEvaluate()
    expect(zeroTrustApi.evaluateAccess).not.toHaveBeenCalled()
  })

  it('handleEvaluate：成功（无 context）', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.evaluateForm.resource = '/api/funds'
    vm.evaluateForm.action = 'read'
    await vm.handleEvaluate()
    expect(zeroTrustApi.evaluateAccess).toHaveBeenCalledWith({
      resource: '/api/funds',
      action: 'read',
      context: undefined,
    })
    expect(vm.evaluateResult?.result).toBe('allowed')
    expect(vm.evaluating).toBe(false)
  })

  it('handleEvaluate：带合法 context JSON', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.evaluateForm.resource = '/api'
    vm.evaluateForm.action = 'write'
    vm.evaluateForm.contextText = '{"ip":"1.1.1.1"}'
    await vm.handleEvaluate()
    expect(zeroTrustApi.evaluateAccess).toHaveBeenCalledWith(
      expect.objectContaining({ context: { ip: '1.1.1.1' } })
    )
  })

  it('handleEvaluate：非法 context JSON → 警告并忽略', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.evaluateForm.resource = '/api'
    vm.evaluateForm.action = 'write'
    vm.evaluateForm.contextText = '{bad json'
    await vm.handleEvaluate()
    expect(ElMessage.warning).toHaveBeenCalledWith('上下文JSON格式无效，已忽略')
    expect(zeroTrustApi.evaluateAccess).toHaveBeenCalledWith(
      expect.objectContaining({ context: undefined })
    )
  })

  it('handleEvaluate：异常 → 错误提示', async () => {
    zeroTrustApi.evaluateAccess.mockRejectedValue({})
    const w = await mountComp()
    const vm = w.vm as any
    vm.evaluateForm.resource = '/api'
    vm.evaluateForm.action = 'read'
    await vm.handleEvaluate()
    expect(ElMessage.error).toHaveBeenCalledWith('访问评估失败')
    expect(vm.evaluating).toBe(false)
  })

  it('handleEvaluate：异常带 message → 展示 message', async () => {
    zeroTrustApi.evaluateAccess.mockRejectedValue({ message: '评估服务错误' })
    const w = await mountComp()
    const vm = w.vm as any
    vm.evaluateForm.resource = '/api'
    vm.evaluateForm.action = 'read'
    await vm.handleEvaluate()
    expect(ElMessage.error).toHaveBeenCalledWith('评估服务错误')
  })

  it('handleEvaluate：异常为 null → 默认文案', async () => {
    zeroTrustApi.evaluateAccess.mockRejectedValue(null)
    const w = await mountComp()
    const vm = w.vm as any
    vm.evaluateForm.resource = '/api'
    vm.evaluateForm.action = 'read'
    await vm.handleEvaluate()
    expect(ElMessage.error).toHaveBeenCalledWith('访问评估失败')
  })

  it('resetEvaluateForm：重置表单与结果', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.evaluateResult = { result: 'allowed' }
    const resetFields = vi.fn()
    vm.evaluateFormRef = { resetFields }
    vm.resetEvaluateForm()
    expect(resetFields).toHaveBeenCalled()
    expect(vm.evaluateResult).toBeNull()
  })

  it('评估表单输入 v-model', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const inputs = w.findAll('.el-input-stub')
    expect(inputs.length).toBeGreaterThanOrEqual(3)
    await inputs[0].setValue('/api/v1/funds')
    expect(vm.evaluateForm.resource).toBe('/api/v1/funds')
    await inputs[1].setValue('delete')
    expect(vm.evaluateForm.action).toBe('delete')
    await inputs[2].setValue('{"ip":"1.1.1.1"}')
    expect(vm.evaluateForm.contextText).toBe('{"ip":"1.1.1.1"}')
  })

  it('事件筛选：严重程度/类型 select → 重新加载', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const selects = w.findAll('.el-select-stub')
    await selects[1].setValue('high')
    expect(vm.eventFilterSeverity).toBe('high')
    await selects[2].setValue('data_leak')
    expect(vm.eventFilterType).toBe('data_leak')
    expect(zeroTrustApi.listEvents).toHaveBeenLastCalledWith(
      expect.objectContaining({ severity: 'high', event_type: 'data_leak', page: 1, page_size: 20 })
    )
    expect(vm.eventPage).toBe(1)
  })

  it('loadEvents：无数据 → 空', async () => {
    zeroTrustApi.listEvents.mockResolvedValue({ success: false })
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.events).toEqual([])
    expect(vm.eventTotal).toBe(0)
  })

  it('loadEvents：data 缺字段 → 空兜底', async () => {
    zeroTrustApi.listEvents.mockResolvedValue({ success: true, data: {} })
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.events).toEqual([])
    expect(vm.eventTotal).toBe(0)
  })

  it('loadEvents：异常 → 空 + 错误提示', async () => {
    zeroTrustApi.listEvents.mockRejectedValue({})
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('加载安全事件失败')
    expect((w.vm as any).events).toEqual([])
  })

  it('loadEvents：异常带 message → 展示 message', async () => {
    zeroTrustApi.listEvents.mockRejectedValue({ message: '事件服务异常' })
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('事件服务异常')
  })

  it('loadEvents：异常为 null → 默认文案', async () => {
    zeroTrustApi.listEvents.mockRejectedValue(null)
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('加载安全事件失败')
  })

  it('事件分页 current-change / size-change', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const pagination = w.findComponent({ name: 'ElPagination' })
    pagination.vm.$emit('update:currentPage', 3)
    await nextTick()
    expect(vm.eventPage).toBe(3)
    pagination.vm.$emit('update:pageSize', 50)
    await nextTick()
    expect(vm.eventPageSize).toBe(50)
    pagination.vm.$emit('current-change', 3)
    await nextTick()
    expect(zeroTrustApi.listEvents).toHaveBeenCalledWith(
      expect.objectContaining({ page: 3, page_size: 50 })
    )
  })

  it('工具函数：评分/状态/严重度/时间', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.getScoreClass(30)).toBe('score-text-red')
    expect(vm.getScoreClass(50)).toBe('score-text-yellow')
    expect(vm.getScoreClass(90)).toBe('score-text-green')
    expect(vm.getFactorStatusType('pass')).toBe('success')
    expect(vm.getFactorStatusType('passed')).toBe('success')
    expect(vm.getFactorStatusType('ok')).toBe('success')
    expect(vm.getFactorStatusType('good')).toBe('success')
    expect(vm.getFactorStatusType('warning')).toBe('warning')
    expect(vm.getFactorStatusType('warn')).toBe('warning')
    expect(vm.getFactorStatusType('fail')).toBe('danger')
    expect(vm.getFactorStatusType('failed')).toBe('danger')
    expect(vm.getFactorStatusType('error')).toBe('danger')
    expect(vm.getFactorStatusType('other')).toBe('info')
    expect(vm.getSeverityTagType('critical')).toBe('danger')
    expect(vm.getSeverityTagType('high')).toBe('warning')
    expect(vm.getSeverityTagType('medium')).toBe('info')
    expect(vm.getSeverityTagType('low')).toBe('success')
    expect(vm.getSeverityTagType('other')).toBe('info')
    expect(vm.formatDateTime('')).toBe('-')
    expect(vm.formatDateTime('2024-01-01T10:00:00Z')).toContain('2024-01-01')
    expect(vm.formatDateTime('not-a-date')).toBe('not-a-date')
  })

  it('评分颜色分支：低分/中分', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    zeroTrustApi.getAssessment.mockResolvedValue({
      success: true,
      data: { ...assessmentData.data, score: 30, level: '危险' },
    })
    await vm.loadAssessment()
    expect(vm.scoreColorClass).toBe('score-red')
    expect(vm.levelTagType).toBe('danger')
    zeroTrustApi.getAssessment.mockResolvedValue({
      success: true,
      data: { ...assessmentData.data, score: 60, level: '一般' },
    })
    await vm.loadAssessment()
    expect(vm.scoreColorClass).toBe('score-yellow')
    expect(vm.levelTagType).toBe('warning')
  })
})

describe('ZeroTrust.vue 状态判定兜底分支', () => {
  it('getFactorStatusType(undefined) → info', async () => {
    const w = await mountComp()
    const st = (w.vm as any).$.setupState
    expect(st.getFactorStatusType(undefined)).toBe('info')
  })

  it('getSeverityTagType(undefined) → info', async () => {
    const w = await mountComp()
    const st = (w.vm as any).$.setupState
    expect(st.getSeverityTagType(undefined)).toBe('info')
  })
})
