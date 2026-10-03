import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  getReminders: vi.fn(),
  triggerReminderScan: vi.fn(),
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('@/api/reminders', () => ({
  getReminders: mocks.getReminders,
  triggerReminderScan: mocks.triggerReminderScan,
}))

vi.mock('element-plus', () => ({ ElMessage: mocks.message }))
vi.mock('@element-plus/icons-vue', () => ({ RefreshRight: { name: 'RefreshRight' } }))

import ReminderCenter from '@/views/reminder/Index.vue'

function mountComp() {
  return mount(ReminderCenter, {
    global: {
      stubs: {
        'el-card': { name: 'ElCard', template: '<div class="card"><slot name="header" /><slot /></div>' },
        'el-button': { name: 'ElButton', template: '<button @click="$emit(\'click\')"><slot /></button>' },
        'el-alert': { name: 'ElAlert', template: '<div class="alert"><slot /></div>' },
        'el-tag': { name: 'ElTag', template: '<span class="tag"><slot /></span>' },
        'el-empty': { name: 'ElEmpty', props: ['description'], template: '<div class="empty">{{ description }}</div>' },
        'el-icon': { name: 'ElIcon', template: '<span><slot /></span>' },
      },
    },
  })
}

describe('ReminderCenter.vue（提醒中心）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getReminders.mockResolvedValue({
      items: [
        { id: 1, type: 'approval_overtime', title: '审批A', content: '超时48小时', is_read: false },
        { id: 2, type: 'deadline_warning', title: '项目B', content: '3天后到期', is_read: true, created_at: '2026-08-01T10:00:00' },
        { id: 3, type: 'unknown-x', title: '未知', content: '内容', is_read: false },
      ],
      total: 3,
      unread: 2,
    })
    mocks.triggerReminderScan.mockResolvedValue({ created: 2 })
  })

  it('挂载加载提醒列表并渲染', async () => {
    const w = mountComp()
    await flushPromises()
    expect(mocks.getReminders).toHaveBeenCalled()
    expect(w.text()).toContain('审批A')
    expect(w.text()).toContain('项目B')
    expect(w.text()).toContain('审批超时')
    expect(w.text()).toContain('未读 2')
    expect(w.text()).toContain('08-01 10:00')
    w.unmount()
  })

  it('标签类型与文案映射（含未知类型回退）', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    expect(vm.tagType('approval_overtime')).toBe('danger')
    expect(vm.tagType('deadline_warning')).toBe('warning')
    expect(vm.tagType('budget_warning')).toBe('danger')
    expect(vm.tagType('backup_reminder')).toBe('info')
    expect(vm.tagType('weird')).toBe('info')
    expect(vm.typeLabel('approval_overtime')).toBe('审批超时')
    expect(vm.typeLabel('deadline_warning')).toBe('项目到期')
    expect(vm.typeLabel('budget_warning')).toBe('预算预警')
    expect(vm.typeLabel('backup_reminder')).toBe('备份提醒')
    expect(vm.typeLabel('package_reminder')).toBe('数据包')
    expect(vm.typeLabel('weird')).toBe('weird')
    expect(w.text()).toContain('未知')
    w.unmount()
  })

  it('空列表显示空态', async () => {
    mocks.getReminders.mockResolvedValue({ items: [], total: 0, unread: 0 })
    const w = mountComp()
    await flushPromises()
    expect(w.text()).toContain('暂无提醒')
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
