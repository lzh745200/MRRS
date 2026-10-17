import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  getReminders: vi.fn(),
  triggerReminderScan: vi.fn(),
  handleReminder: vi.fn(),
  ignoreReminder: vi.fn(),
  snoozeReminder: vi.fn(),
  reopenReminder: vi.fn(),
  pushSafe: vi.fn(),
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  messageBox: { prompt: vi.fn(), confirm: vi.fn() },
}))

vi.mock('@/api/reminders', () => ({
  getReminders: mocks.getReminders,
  triggerReminderScan: mocks.triggerReminderScan,
  handleReminder: mocks.handleReminder,
  ignoreReminder: mocks.ignoreReminder,
  snoozeReminder: mocks.snoozeReminder,
  reopenReminder: mocks.reopenReminder,
}))

vi.mock('element-plus', () => ({ ElMessage: mocks.message, ElMessageBox: mocks.messageBox }))
vi.mock('@element-plus/icons-vue', () => ({ RefreshRight: { name: 'RefreshRight' } }))
vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mocks.pushSafe }),
}))

import ReminderCenter from '@/views/reminder/Index.vue'

const FUTURE = '2099-01-01T00:00:00'
const PAST = '2000-01-01T00:00:00'

/** 覆盖：待处理/已处理/已忽略、已延期、备注、可跳转/不可跳转、未知类型 */
const FIXTURE = [
  {
    id: 1,
    type: 'approval_overtime',
    title: '审批A',
    content: '超时48小时',
    is_read: false,
    state: 'open',
    entity_id: 5,
  },
  {
    id: 2,
    type: 'deadline_warning',
    title: '项目B',
    content: '3天后到期',
    is_read: true,
    state: 'open',
    snooze_until: FUTURE,
    entity_id: 3,
    created_at: '2026-08-01T10:00:00',
  },
  {
    id: 3,
    type: 'budget_warning',
    title: '经费C',
    content: '预算超支',
    is_read: false,
    state: 'handled',
    note: '已核实',
    entity_id: 9,
  },
  {
    id: 4,
    type: 'package_reminder',
    title: '数据包D',
    content: '待导入',
    is_read: true,
    state: 'ignored',
    note: '重复提醒',
    entity_id: null,
  },
  {
    id: 5,
    type: 'unknown-x',
    title: '未知E',
    content: '内容',
    is_read: false,
    entity_id: null,
  },
]

function mountComp() {
  return mount(ReminderCenter, {
    global: {
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="card"><slot name="header" /><slot /></div>',
        },
        'el-button': {
          name: 'ElButton',
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
        'el-alert': { name: 'ElAlert', template: '<div class="alert"><slot /></div>' },
        'el-tag': { name: 'ElTag', template: '<span class="tag"><slot /></span>' },
        'el-empty': {
          name: 'ElEmpty',
          props: ['description'],
          template: '<div class="empty">{{ description }}</div>',
        },
        'el-icon': { name: 'ElIcon', template: '<span><slot /></span>' },
      },
    },
  })
}

function buttonByText(w: ReturnType<typeof mountComp>, text: string) {
  return w.findAll('button').find((b) => b.text() === text)
}

async function clickFilter(w: ReturnType<typeof mountComp>, label: string) {
  const btn = buttonByText(w, label)
  expect(btn).toBeTruthy()
  await btn!.trigger('click')
  await flushPromises()
}

describe('ReminderCenter.vue（提醒中心 + 处置闭环）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getReminders.mockResolvedValue({
      items: FIXTURE,
      total: 5,
      unread: 2,
    })
    mocks.triggerReminderScan.mockResolvedValue({ created: 2 })
    mocks.handleReminder.mockResolvedValue({ message_id: 1, state: 'handled' })
    mocks.ignoreReminder.mockResolvedValue({ message_id: 1, state: 'ignored' })
    mocks.snoozeReminder.mockResolvedValue({ message_id: 1, state: 'open' })
    mocks.reopenReminder.mockResolvedValue({ message_id: 3, state: 'open' })
    mocks.messageBox.prompt.mockResolvedValue({ value: '重复' })
  })

  it('挂载加载：默认待处理过滤 + 后端无 stats 时本地兜底统计', async () => {
    const w = mountComp()
    await flushPromises()
    expect(mocks.getReminders).toHaveBeenCalledWith(true)
    // 待处理：1/2/5；已处理/已忽略默认不展示
    expect(w.text()).toContain('审批A')
    expect(w.text()).toContain('项目B')
    expect(w.text()).toContain('未知E')
    expect(w.text()).not.toContain('经费C')
    expect(w.text()).not.toContain('数据包D')
    // 本地兜底统计：pending 3 / handled 1 / ignored 1 / snoozed 1
    expect(w.text()).toContain('待处理 3')
    expect(w.text()).toContain('已处理 1')
    expect(w.text()).toContain('已忽略 1')
    expect(w.text()).toContain('已延期 1')
    expect(w.text()).toContain('未读 2')
    expect(w.text()).toContain('待处理（5）')
    // 延期角标与备注
    expect(w.text()).toContain('已延期')
    expect(w.text()).toContain('延期至 01-01 00:00')
    w.unmount()
  })

  it('后端返回 stats 时优先采用（不本地兜底）', async () => {
    mocks.getReminders.mockResolvedValue({
      items: FIXTURE,
      total: 5,
      unread: 2,
      stats: { pending: 11, handled: 12, ignored: 13, snoozed: 14, total: 50 },
    })
    const w = mountComp()
    await flushPromises()
    expect(w.text()).toContain('待处理 11')
    expect(w.text()).toContain('已处理 12')
    expect(w.text()).toContain('已忽略 13')
    expect(w.text()).toContain('已延期 14')
    w.unmount()
  })

  it('过滤页签切换：已处理 / 已忽略 / 全部', async () => {
    const w = mountComp()
    await flushPromises()
    expect(w.text()).toContain('待处理（5）')

    await clickFilter(w, '已处理')
    expect(w.text()).toContain('已处理（5）')
    expect(w.text()).toContain('经费C')
    expect(w.text()).toContain('已处理')
    expect(w.text()).toContain('备注：已核实')
    expect(w.text()).toContain('重新打开')
    expect(w.text()).not.toContain('审批A')

    await clickFilter(w, '已忽略')
    expect(w.text()).toContain('数据包D')
    expect(w.text()).toContain('备注：重复提醒')
    expect(w.text()).not.toContain('经费C')

    await clickFilter(w, '全部')
    expect(w.text()).toContain('全部（5）')
    expect(w.text()).toContain('审批A')
    expect(w.text()).toContain('经费C')
    expect(w.text()).toContain('数据包D')
    w.unmount()
  })

  it('标签与状态辅助函数', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    expect(vm.tagType('approval_overtime')).toBe('danger')
    expect(vm.tagType('deadline_warning')).toBe('warning')
    expect(vm.tagType('budget_warning')).toBe('danger')
    expect(vm.tagType('backup_reminder')).toBe('info')
    expect(vm.tagType('weird')).toBe('info')
    expect(vm.typeLabel('approval_overtime')).toBe('审批超时')
    expect(vm.typeLabel('approval_approaching')).toBe('审批临期')
    expect(vm.typeLabel('deadline_warning')).toBe('项目到期')
    expect(vm.typeLabel('budget_warning')).toBe('预算预警')
    expect(vm.typeLabel('backup_reminder')).toBe('备份提醒')
    expect(vm.typeLabel('package_reminder')).toBe('数据包')
    expect(vm.typeLabel('weird')).toBe('weird')

    expect(vm.stateLabel({ state: 'handled' })).toBe('已处理')
    expect(vm.stateLabel({ state: 'ignored' })).toBe('已忽略')
    expect(vm.stateLabel({ state: 'open', snooze_until: FUTURE })).toBe('已延期')
    expect(vm.stateLabel({ state: 'open', snooze_until: PAST })).toBe('')
    expect(vm.stateLabel({ state: 'open', snooze_until: 'not-a-date' })).toBe('')
    expect(vm.stateLabel({})).toBe('')

    expect(vm.stateTagType({ state: 'handled' })).toBe('success')
    expect(vm.stateTagType({ state: 'ignored' })).toBe('info')
    expect(vm.stateTagType({ state: 'open', snooze_until: FUTURE })).toBe('warning')
    expect(vm.stateTagType({})).toBe('warning')

    expect(vm.isOpen({})).toBe(true)
    expect(vm.isOpen({ state: 'handled' })).toBe(false)
    expect(vm.isOpen({ state: 'ignored' })).toBe(false)
    w.unmount()
  })

  it('localStats 各分支（含非法/过去时间）', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    expect(vm.localStats([])).toEqual({ pending: 0, handled: 0, ignored: 0, snoozed: 0, total: 0 })
    expect(
      vm.localStats([
        { state: 'handled' },
        { state: 'ignored' },
        {},
        { state: 'open', snooze_until: FUTURE },
        { state: 'open', snooze_until: PAST },
        { state: 'open', snooze_until: 'bad' },
      ])
    ).toEqual({ pending: 4, handled: 1, ignored: 1, snoozed: 1, total: 6 })
    w.unmount()
  })

  it('jumpRoute 全类型矩阵 + goTo 调用 pushSafe', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    expect(vm.jumpRoute({ type: 'approval_overtime' })).toBe('/approval/pending')
    expect(vm.jumpRoute({ type: 'approval_approaching' })).toBe('/approval/pending')
    expect(vm.jumpRoute({ type: 'deadline_warning', entity_id: 3 })).toBe('/projects/3')
    expect(vm.jumpRoute({ type: 'deadline_warning' })).toBeNull()
    expect(vm.jumpRoute({ type: 'budget_warning', entity_id: 9 })).toBe('/funds/9')
    expect(vm.jumpRoute({ type: 'budget_warning' })).toBeNull()
    expect(vm.jumpRoute({ type: 'backup_reminder' })).toBe('/system/backup')
    expect(vm.jumpRoute({ type: 'package_reminder' })).toBe('/data-package')
    expect(vm.jumpRoute({ type: 'weird' })).toBeNull()

    vm.goTo({ type: 'deadline_warning', entity_id: 3 })
    expect(mocks.pushSafe).toHaveBeenCalledWith('/projects/3', '提醒处理')
    mocks.pushSafe.mockClear()
    vm.goTo({ type: 'weird' })
    expect(mocks.pushSafe).not.toHaveBeenCalled()
    w.unmount()
  })

  it('处理成功 → 调 API + 提示 + 重新加载', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    await vm.handleItem({ id: 1 })
    expect(mocks.handleReminder).toHaveBeenCalledWith(1)
    expect(mocks.message.success).toHaveBeenCalledWith('已标记处理')
    expect(mocks.getReminders).toHaveBeenCalledTimes(2)
    w.unmount()
  })

  it('处理失败 / 重新打开失败提示', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    mocks.handleReminder.mockRejectedValueOnce(new Error('net'))
    await vm.handleItem({ id: 1 })
    expect(mocks.message.error).toHaveBeenCalledWith('操作失败，请稍后重试')

    mocks.reopenReminder.mockRejectedValueOnce(new Error('net'))
    await vm.reopenItem({ id: 3 })
    expect(mocks.message.error).toHaveBeenCalledTimes(2)
    w.unmount()
  })

  it('重新打开成功', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    await vm.reopenItem({ id: 3 })
    expect(mocks.reopenReminder).toHaveBeenCalledWith(3)
    expect(mocks.message.success).toHaveBeenCalledWith('已重新打开')
    w.unmount()
  })

  it('忽略：填写原因 / 原因为空 / 取消', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any

    mocks.messageBox.prompt.mockResolvedValueOnce({ value: '重复' })
    await vm.ignoreItem({ id: 1 })
    expect(mocks.ignoreReminder).toHaveBeenCalledWith(1, '重复')
    expect(mocks.message.success).toHaveBeenCalledWith('已忽略该提醒')

    mocks.messageBox.prompt.mockResolvedValueOnce({ value: undefined })
    await vm.ignoreItem({ id: 2 })
    expect(mocks.ignoreReminder).toHaveBeenLastCalledWith(2, '')

    mocks.ignoreReminder.mockClear()
    mocks.messageBox.prompt.mockRejectedValueOnce(new Error('cancel'))
    await vm.ignoreItem({ id: 1 })
    expect(mocks.ignoreReminder).not.toHaveBeenCalled()
    w.unmount()
  })

  it('延期：合法天数 / 非法输入 / 取消 / 失败', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any

    mocks.messageBox.prompt.mockResolvedValueOnce({ value: '3' })
    await vm.snoozeItem({ id: 1 })
    expect(mocks.snoozeReminder).toHaveBeenCalledWith(1, 3)
    expect(mocks.message.success).toHaveBeenCalledWith('已延期 3 天')

    for (const bad of ['abc', '0', '91']) {
      mocks.snoozeReminder.mockClear()
      mocks.messageBox.prompt.mockResolvedValueOnce({ value: bad })
      await vm.snoozeItem({ id: 1 })
      expect(mocks.snoozeReminder).not.toHaveBeenCalled()
    }
    expect(mocks.message.error).toHaveBeenCalledWith('延期天数须为 1-90 的整数')

    mocks.messageBox.prompt.mockRejectedValueOnce(new Error('cancel'))
    await vm.snoozeItem({ id: 1 })
    expect(mocks.snoozeReminder).not.toHaveBeenCalled()

    mocks.messageBox.prompt.mockResolvedValueOnce({ value: '5' })
    mocks.snoozeReminder.mockRejectedValueOnce(new Error('net'))
    await vm.snoozeItem({ id: 1 })
    expect(mocks.message.error).toHaveBeenCalledWith('操作失败，请稍后重试')
    w.unmount()
  })

  it('页面按钮点击链路（前往处理/处理/延期/忽略/重新打开）', async () => {
    const w = mountComp()
    await flushPromises()

    await buttonByText(w, '前往处理')!.trigger('click')
    expect(mocks.pushSafe).toHaveBeenCalledWith('/approval/pending', '提醒处理')

    await buttonByText(w, '处理')!.trigger('click')
    await flushPromises()
    expect(mocks.handleReminder).toHaveBeenCalledWith(1)

    await buttonByText(w, '延期')!.trigger('click')
    await flushPromises()
    expect(mocks.messageBox.prompt).toHaveBeenCalled()

    await buttonByText(w, '忽略')!.trigger('click')
    await flushPromises()
    expect(mocks.ignoreReminder).toHaveBeenCalled()

    await clickFilter(w, '已处理')
    await buttonByText(w, '重新打开')!.trigger('click')
    await flushPromises()
    expect(mocks.reopenReminder).toHaveBeenCalledWith(3)
    w.unmount()
  })

  it('空列表显示空态', async () => {
    mocks.getReminders.mockResolvedValue({ items: [], total: 0, unread: 0 })
    const w = mountComp()
    await flushPromises()
    expect(w.text()).toContain('暂无提醒')
    expect(w.text()).not.toContain('未读')
    w.unmount()
  })

  it('过滤后无数据也显示空态', async () => {
    mocks.getReminders.mockResolvedValue({
      items: [
        { id: 9, type: 'system', title: '仅已处理', content: 'x', is_read: true, state: 'handled' },
      ],
      total: 1,
      unread: 0,
      stats: { pending: 0, handled: 1, ignored: 0, snoozed: 0, total: 1 },
    })
    const w = mountComp()
    await flushPromises()
    // 默认"待处理"页签下为空
    expect(w.text()).toContain('暂无提醒')
    await clickFilter(w, '已处理')
    expect(w.text()).toContain('仅已处理')
    w.unmount()
  })

  it('加载失败提示', async () => {
    mocks.getReminders.mockRejectedValue(new Error('net'))
    const w = mountComp()
    await flushPromises()
    expect(mocks.message.error).toHaveBeenCalledWith('加载提醒失败')
    w.unmount()
  })

  it('手动扫描成功后刷新', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    await vm.handleScan()
    expect(mocks.triggerReminderScan).toHaveBeenCalled()
    expect(mocks.message.success).toHaveBeenCalledWith('扫描完成，新增 2 条提醒')
    expect(mocks.getReminders).toHaveBeenCalledTimes(2)
    w.unmount()
  })

  it('手动扫描失败提示', async () => {
    mocks.triggerReminderScan.mockRejectedValue(new Error('net'))
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    await vm.handleScan()
    expect(mocks.message.error).toHaveBeenCalledWith('扫描失败')
    w.unmount()
  })

  it('formatTime 空值与非法日期', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    expect(vm.formatTime(null)).toBe('')
    expect(vm.formatTime(undefined)).toBe('')
    // 2026-10-03 收敛：非法值统一走空串兜底（不再回显原串）
    expect(vm.formatTime('not-a-date')).toBe('')
    expect(vm.formatTime('2026-08-01T10:00:00')).toBe('08-01 10:00')
    w.unmount()
  })

  it('响应为 null → res?.items/total/unread ?? 兜底', async () => {
    mocks.getReminders.mockResolvedValue(null)
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    expect(vm.items).toEqual([])
    expect(vm.total).toBe(0)
    expect(vm.unread).toBe(0)
    expect(vm.stats).toEqual({ pending: 0, handled: 0, ignored: 0, snoozed: 0, total: 0 })
    expect(w.text()).toContain('暂无提醒')
    w.unmount()
  })

  it('扫描响应无 created 字段 → ?? 0 兜底', async () => {
    mocks.triggerReminderScan.mockResolvedValue({})
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    await vm.handleScan()
    expect(mocks.message.success).toHaveBeenCalledWith('扫描完成，新增 0 条提醒')
    w.unmount()
  })
})
