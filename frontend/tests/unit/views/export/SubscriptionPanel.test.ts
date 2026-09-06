/**
 * views/export/SubscriptionPanel.vue 专属测试（工单 003 订阅闭环）
 *
 * coverage-merge 不变量：本文件是 SubscriptionPanel.vue 的唯一执行者——
 * ReportExport.test.ts 以桩替换面板，router-index/smoke 亦不触碰。
 * 覆盖：列表加载（items/裸响应/undefined/失败）、freqLabel/freqDetail 四频次
 * 与回落、新建校验与成功失败、启停开关、立即生成、删除确认三态、
 * 对话框 v-model 与全部表单交互。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const {
  ElMessage,
  ElMessageBox,
  mockListSubscriptions,
  mockCreateSubscription,
  mockToggleSubscription,
  mockDeleteSubscription,
  mockGenerateSubscriptionNow,
  logError,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  ElMessageBox: { confirm: vi.fn() },
  mockListSubscriptions: vi.fn(),
  mockCreateSubscription: vi.fn(),
  mockToggleSubscription: vi.fn(),
  mockDeleteSubscription: vi.fn(),
  mockGenerateSubscriptionNow: vi.fn(),
  logError: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage, ElMessageBox }))

vi.mock('@/api/request', () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  downloadBlob: vi.fn(),
}))

vi.mock('@/api/reportSubscription', () => ({
  listSubscriptions: mockListSubscriptions,
  createSubscription: mockCreateSubscription,
  toggleSubscription: mockToggleSubscription,
  deleteSubscription: mockDeleteSubscription,
  generateSubscriptionNow: mockGenerateSubscriptionNow,
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() },
}))

import SubscriptionPanel from '@/views/export/SubscriptionPanel.vue'

const subRows = [
  {
    id: 1,
    name: '每月帮扶村汇总',
    frequency: 'monthly',
    send_day: 1,
    send_time: '08:00',
    is_active: true,
    last_sent_at: '2026-09-01T08:00:00',
    next_send_at: '2026-10-01T08:00:00',
  },
  {
    id: 2,
    name: '每周资金分析',
    frequency: 'weekly',
    send_day: 5,
    send_time: '06:30',
    is_active: false,
    last_sent_at: null,
    next_send_at: null,
  },
]

const stubs = {
  'el-button': {
    name: 'ElButton',
    props: ['disabled', 'loading'],
    template: '<button class="el-button-stub" :disabled="disabled"><slot /></button>',
  },
  'el-table-column': {
    name: 'ElTableColumn',
    template:
      '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
    data() {
      // is_active: 操作列「立即生成」的 :disabled 依赖它，缺省会让按钮
      // disabled → trigger('click') 被跳过 → 内联 handler 覆盖缺口
      return { rowA: { ...subRows[0] }, rowB: { ...subRows[1] } }
    },
  },
  'el-switch': {
    name: 'ElSwitch',
    template: '<div class="el-switch-stub" />',
    emits: ['update:modelValue', 'change'],
  },
  'el-select': {
    name: 'ElSelect',
    template: '<div class="el-select-stub"><slot /></div>',
    emits: ['update:modelValue', 'change'],
  },
  'el-dialog': {
    name: 'ElDialog',
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<div v-if="modelValue" class="el-dialog-stub"><slot /><slot name="footer" /></div>',
  },
  'el-input': {
    name: 'ElInput',
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      "<input class='el-input-stub' :value=\"modelValue\" @input=\"$emit('update:modelValue', $event.target.value)\" />",
  },
  'el-time-select': {
    name: 'ElTimeSelect',
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      "<input class='el-time-select-stub' :value=\"modelValue\" @input=\"$emit('update:modelValue', $event.target.value)\" />",
  },
  'el-form': { name: 'ElForm', template: '<form class="el-form-stub"><slot /></form>' },
  'el-form-item': {
    name: 'ElFormItem',
    props: ['label'],
    template: '<div class="el-form-item-stub"><slot /></div>',
  },
  'el-option': { name: 'ElOption', template: '<div class="el-option-stub"><slot /></div>' },
  'el-icon': { name: 'ElIcon', template: '<span class="el-icon-stub"><slot /></span>' },
}

function mountComp() {
  return mount(SubscriptionPanel, {
    global: { renderStubDefaultSlot: true, stubs },
  })
}

const findBtn = (wrapper: any, text: string) => {
  const btn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().trim().includes(text))
  expect(btn, `按钮「${text}」`).toBeTruthy()
  return btn!
}

beforeEach(() => {
  vi.resetAllMocks()
  mockListSubscriptions.mockResolvedValue({ data: { items: [] } })
})

describe('订阅列表加载', () => {
  it('onMounted 加载订阅；items 缺省 → []；失败 → logger.error', async () => {
    const wrapper = mountComp()
    await flushPromises()
    expect(mockListSubscriptions).toHaveBeenCalledWith({ page: 1, page_size: 50 })
    const vm = wrapper.vm as any
    expect(vm.subscriptions).toEqual([])

    mockListSubscriptions.mockResolvedValueOnce({ data: { items: subRows } })
    await vm.loadSubscriptions()
    expect(vm.subscriptions).toHaveLength(2)
    expect(vm.loadingSubs).toBe(false)

    mockListSubscriptions.mockRejectedValueOnce(new Error('net'))
    await vm.loadSubscriptions()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalled()
  })

  it('freqLabel 未知值回落原文；freqDetail 四频次与 send_time 缺省回落', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.freqLabel('daily')).toBe('每天')
    expect(vm.freqLabel('weekly')).toBe('每周')
    expect(vm.freqLabel('monthly')).toBe('每月')
    expect(vm.freqLabel('quarterly')).toBe('每季度')
    expect(vm.freqLabel('zzz')).toBe('zzz')
    expect(vm.freqDetail({ frequency: 'daily', send_time: '08:00' })).toBe('每天 08:00')
    expect(vm.freqDetail({ frequency: 'daily' })).toBe('每天 08:00')
    expect(vm.freqDetail({ frequency: 'weekly', send_day: 5, send_time: '06:30' })).toBe(
      '周五 06:30',
    )
    expect(vm.freqDetail({ frequency: 'weekly' })).toBe('周一 08:00')
    expect(vm.freqDetail({ frequency: 'monthly', send_day: 1, send_time: '08:00' })).toBe(
      '每月 1 号 08:00',
    )
    expect(vm.freqDetail({ frequency: 'quarterly', send_day: 15, send_time: '09:00' })).toBe(
      '每季度 15 号 09:00',
    )
  })

  it('订阅表数据经 vm 状态渲染（表格桩固定行，改断状态与卡片存在）', async () => {
    mockListSubscriptions.mockResolvedValue({ data: { items: subRows } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.subscriptions).toHaveLength(2)
    expect(vm.subscriptions[0].last_sent_at).toBe('2026-09-01T08:00:00')
    expect(vm.subscriptions[1].last_sent_at).toBeNull()
    expect(wrapper.find('.subscription-management').exists()).toBe(true)
    expect(
      wrapper.findAll('.el-button-stub').filter((b: any) => b.text().includes('立即生成')).length,
    ).toBeGreaterThanOrEqual(2)
  })

  it('loadSubscriptions：裸列表响应（res 无 data）→ 直接当 body；undefined → []', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockListSubscriptions.mockResolvedValueOnce({ items: subRows })
    await vm.loadSubscriptions()
    expect(vm.subscriptions).toHaveLength(2)
    mockListSubscriptions.mockResolvedValueOnce(undefined)
    await vm.loadSubscriptions()
    expect(vm.subscriptions).toEqual([])
  })
})

describe('新建订阅', () => {
  it('openSubscriptionDialog 打开对话框并重置表单；handleFreqChange 重置 send_day', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findBtn(wrapper, '新建订阅').trigger('click')
    expect(vm.subDialogVisible).toBe(true)
    expect(vm.subForm.name).toBe('')

    vm.subForm.frequency = 'weekly'
    vm.handleFreqChange()
    expect(vm.subForm.send_day).toBe(1)
  })

  it('handleCreateSub：空名称警告不提交；成功后关对话框刷新列表；daily 分支 send_day 置 null', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.subDialogVisible = true

    vm.subForm.name = '   '
    await vm.handleCreateSub()
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写订阅名称')
    expect(mockCreateSubscription).not.toHaveBeenCalled()

    vm.subForm.name = '每月汇总'
    vm.subForm.frequency = 'monthly'
    vm.subForm.send_day = 15
    mockCreateSubscription.mockResolvedValueOnce({ id: 9 })
    await vm.handleCreateSub()
    expect(mockCreateSubscription).toHaveBeenCalledWith(
      expect.objectContaining({ name: '每月汇总', frequency: 'monthly', send_day: 15, format: 'xlsx' }),
    )
    expect(ElMessage.success).toHaveBeenCalled()
    expect(vm.subDialogVisible).toBe(false)
    expect(mockListSubscriptions.mock.calls.length).toBeGreaterThan(1)

    vm.subDialogVisible = true
    vm.subForm.name = '每日简报'
    vm.subForm.frequency = 'daily'
    vm.subForm.send_day = 15
    await vm.handleCreateSub()
    expect(mockCreateSubscription).toHaveBeenLastCalledWith(
      expect.objectContaining({ frequency: 'daily', send_day: null }),
    )
  })

  it('handleCreateSub：失败 → userMessage 优先 / detail / 字面量兜底三侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.subDialogVisible = true
    vm.subForm.name = 'X'

    mockCreateSubscription.mockRejectedValueOnce({ userMessage: '限流' })
    await vm.handleCreateSub()
    expect(ElMessage.error).toHaveBeenCalledWith('限流')

    mockCreateSubscription.mockRejectedValueOnce({ response: { data: { detail: '重名' } } })
    await vm.handleCreateSub()
    expect(ElMessage.error).toHaveBeenCalledWith('重名')

    mockCreateSubscription.mockRejectedValueOnce(new Error('boom'))
    await vm.handleCreateSub()
    expect(ElMessage.error).toHaveBeenCalledWith('创建订阅失败')
    expect(vm.creatingSub).toBe(false)
  })
})

describe('订阅操作', () => {
  it('handleToggleSub：启用行 → 已禁用；禁用行 → 已启用；失败 userMessage 侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleToggleSub({ ...subRows[0] })
    expect(mockToggleSubscription).toHaveBeenCalledWith(1)
    expect(ElMessage.success).toHaveBeenCalledWith('订阅已禁用')

    await vm.handleToggleSub({ ...subRows[1] })
    expect(ElMessage.success).toHaveBeenCalledWith('订阅已启用')

    mockToggleSubscription.mockRejectedValueOnce({ userMessage: '切换限流' })
    await vm.handleToggleSub({ ...subRows[0] })
    expect(ElMessage.error).toHaveBeenCalledWith('切换限流')
  })

  it('handleGenerateNow：成功提示并刷新；失败 detail / userMessage / 字面量三侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const row = { ...subRows[0] }

    mockGenerateSubscriptionNow.mockResolvedValueOnce({ data: { file_name: 'f.xlsx' } })
    await vm.handleGenerateNow(row)
    expect(mockGenerateSubscriptionNow).toHaveBeenCalledWith(1)
    expect(ElMessage.success).toHaveBeenCalled()
    expect(vm.generatingId).toBe(null)

    mockGenerateSubscriptionNow.mockRejectedValueOnce({ response: { data: { detail: '磁盘不可写' } } })
    await vm.handleGenerateNow(row)
    expect(ElMessage.error).toHaveBeenCalledWith('磁盘不可写')

    mockGenerateSubscriptionNow.mockRejectedValueOnce({ userMessage: '生成限流' })
    await vm.handleGenerateNow(row)
    expect(ElMessage.error).toHaveBeenCalledWith('生成限流')

    mockGenerateSubscriptionNow.mockRejectedValueOnce(new Error('boom'))
    await vm.handleGenerateNow(row)
    expect(ElMessage.error).toHaveBeenCalledWith('生成失败')
    expect(vm.generatingId).toBe(null)
  })

  it('handleDeleteSub：确认后删除；取消不删；失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const row = { ...subRows[0] }

    mockDeleteSubscription.mockResolvedValueOnce({})
    await vm.handleDeleteSub(row)
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(mockDeleteSubscription).toHaveBeenCalledWith(1)
    expect(ElMessage.success).toHaveBeenCalledWith('订阅已删除')

    ElMessageBox.confirm.mockRejectedValueOnce('cancel')
    await vm.handleDeleteSub(row)
    expect(mockDeleteSubscription).toHaveBeenCalledTimes(1)

    ElMessageBox.confirm.mockResolvedValueOnce({})
    mockDeleteSubscription.mockRejectedValueOnce({ userMessage: '删除限流' })
    await vm.handleDeleteSub(row)
    expect(ElMessage.error).toHaveBeenCalledWith('删除限流')
  })
})

describe('模板交互（内联 handler 与分支两侧）', () => {
  it('卡片 刷新/新建 点击、switch onChange、槽位按钮、对话框表单 v-model 全交互', async () => {
    mockListSubscriptions.mockResolvedValue({ data: { items: subRows } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 卡片「刷新」
    const subRefresh = wrapper
      .findAll('.history-header button')
      .find((b: any) => b.text().includes('刷新'))
    expect(subRefresh).toBeTruthy()
    await subRefresh!.trigger('click')
    await flushPromises()

    // 槽位操作列：立即生成（启用行可点）/ 删除（确认 mock 吸收）
    const genBtns = wrapper
      .findAll('.el-button-stub')
      .filter((b: any) => b.text().includes('立即生成'))
    for (const b of genBtns) {
      await b.trigger('click')
      await flushPromises()
    }
    expect(mockGenerateSubscriptionNow).toHaveBeenCalled()
    const delBtns = wrapper
      .findAll('.el-button-stub')
      .filter((b: any) => b.text().trim() === '删除')
    for (const b of delBtns) {
      await b.trigger('click')
      await flushPromises()
    }
    expect(mockDeleteSubscription).toHaveBeenCalled()

    // 全部开关 onChange
    for (const sw of wrapper.findAllComponents({ name: 'ElSwitch' })) {
      await sw.vm.$emit('change')
    }
    await flushPromises()

    // 打开对话框 → 名称输入 v-model
    await findBtn(wrapper, '新建订阅').trigger('click')
    expect(vm.subDialogVisible).toBe(true)
    const nameInput = wrapper.find('input.el-input-stub')
    await nameInput.setValue('我的订阅')
    expect(vm.subForm.name).toBe('我的订阅')

    // 类型 / 频率 select
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(selects.length).toBeGreaterThanOrEqual(4)
    await selects[0].vm.$emit('update:modelValue', 'annual_summary')
    expect(vm.subForm.report_type).toBe('annual_summary')
    await selects[1].vm.$emit('update:modelValue', 'weekly')
    expect(vm.subForm.frequency).toBe('weekly')
    await nextTick()
    const daySelect = wrapper.findAllComponents({ name: 'ElSelect' })[2]
    await daySelect.vm.$emit('update:modelValue', 3)
    expect(vm.subForm.send_day).toBe(3)
    const formatSelect = wrapper.findAllComponents({ name: 'ElSelect' })[3]
    await formatSelect.vm.$emit('update:modelValue', 'pdf')
    expect(vm.subForm.format).toBe('pdf')

    // 时间选择
    const timeInput = wrapper.find('input.el-time-select-stub')
    await timeInput.setValue('09:30')
    expect(vm.subForm.send_time).toBe('09:30')

    // el-dialog v-model 两侧
    const dialog = wrapper.findComponent({ name: 'ElDialog' })
    await dialog.vm.$emit('update:modelValue', false)
    expect(vm.subDialogVisible).toBe(false)
    await dialog.vm.$emit('update:modelValue', true)
    expect(vm.subDialogVisible).toBe(true)
    await nextTick()

    // footer：取消（置 false）/ 创建订阅（成功）
    const cancelBtn = wrapper
      .findAll('.el-button-stub')
      .find((b: any) => b.text().trim() === '取消')
    await cancelBtn!.trigger('click')
    expect(vm.subDialogVisible).toBe(false)
    await findBtn(wrapper, '新建订阅').trigger('click')
    await nextTick()
    mockCreateSubscription.mockResolvedValueOnce({ id: 1 })
    const createBtn = wrapper
      .findAll('.el-button-stub')
      .find((b: any) => b.text().includes('创建订阅'))
    await createBtn!.trigger('click')
    await flushPromises()
    expect(mockCreateSubscription).toHaveBeenCalled()
  })
})
