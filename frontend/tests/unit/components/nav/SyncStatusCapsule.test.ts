import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const { getSyncLogsMock } = vi.hoisted(() => ({ getSyncLogsMock: vi.fn() }))
vi.mock('@/api/dataSync', () => ({ getSyncLogs: getSyncLogsMock }))

import SyncStatusCapsule from '@/components/nav/SyncStatusCapsule.vue'

function recentLog(hoursAgo = 2) {
  return {
    id: 'l1',
    action: 'import',
    status: 'success',
    message: '导入 12 条',
    created_at: new Date(Date.now() - hoursAgo * 3600_000).toISOString(),
  }
}

function mountCapsule() {
  return mount(SyncStatusCapsule, {
    global: {
      stubs: {
        'el-tooltip': {
          props: ['content'],
          template: '<span class="tip" :data-tip="content"><slot /></span>',
        },
        'el-drawer': {
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<div class="drawer-stub" :data-open="modelValue"><button class="dlg-close" @click="$emit(\'update:modelValue\', false)">x</button><button class="dlg-open" @click="$emit(\'update:modelValue\', true)">o</button><slot /><slot name="footer" /></div>',
        },
        'el-alert': { props: ['title'], template: '<div class="alert-stub">{{ title }}</div>' },
        'el-table': { props: ['data'], template: '<div class="table-stub" />' },
        'el-table-column': { template: '<div />' },
        'el-empty': { props: ['description'], template: '<div class="empty-stub">{{ description }}</div>' },
        'el-button': { template: '<button class="btn-stub" @click="$emit(\'click\')"><slot /></button>' },
      },
    },
  })
}

beforeEach(() => {
  getSyncLogsMock.mockReset()
  getSyncLogsMock.mockResolvedValue([])
})

describe('SyncStatusCapsule', () => {
  it('无同步记录 → 胶囊显示"未同步"、抽屉显示空状态', async () => {
    const wrapper = mountCapsule()
    await flushPromises()
    const capsule = wrapper.find('[data-testid="sync-capsule"]')
    expect(capsule.text()).toContain('未同步')
    expect(capsule.classes()).toContain('sync-capsule--unknown')
    expect(wrapper.find('.empty-stub').exists()).toBe(true)
  })

  it('最近同步 → 显示相对时间与 ok 级配色', async () => {
    getSyncLogsMock.mockResolvedValue([recentLog(2)])
    const wrapper = mountCapsule()
    await flushPromises()
    const capsule = wrapper.find('[data-testid="sync-capsule"]')
    expect(capsule.text()).toContain('小时前')
    expect(capsule.classes()).toContain('sync-capsule--ok')
  })

  it('久未同步 → stale 级配色（提醒对账）', async () => {
    getSyncLogsMock.mockResolvedValue([recentLog(24 * 30)])
    const wrapper = mountCapsule()
    await flushPromises()
    expect(wrapper.find('[data-testid="sync-capsule"]').classes()).toContain('sync-capsule--stale')
  })

  it('点击胶囊 → 打开抽屉并刷新一次', async () => {
    const wrapper = mountCapsule()
    await flushPromises()
    const callsAfterMount = getSyncLogsMock.mock.calls.length

    await wrapper.find('[data-testid="sync-capsule"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('.drawer-stub').attributes('data-open')).toBe('true')
    expect(getSyncLogsMock.mock.calls.length).toBe(callsAfterMount + 1)
  })

  it('键盘 Enter/Space 也能打开（可键盘操作）', async () => {
    const wrapper = mountCapsule()
    await flushPromises()
    await wrapper.find('[data-testid="sync-capsule"]').trigger('keydown.enter')
    expect(wrapper.find('.drawer-stub').attributes('data-open')).toBe('true')

    await wrapper.find('[data-testid="sync-capsule"]').trigger('keydown.space')
    expect(wrapper.find('.drawer-stub').attributes('data-open')).toBe('true')
  })

  it('有日志时抽屉展示表格与汇总文案', async () => {
    getSyncLogsMock.mockResolvedValue([recentLog(2)])
    const wrapper = mountCapsule()
    await flushPromises()
    expect(wrapper.find('.table-stub').exists()).toBe(true)
    expect(wrapper.find('[data-testid="sync-drawer-summary"]').text()).toContain('导入')
  })

  it('接口失败 → 抽屉内给出原因（顶栏不弹错）', async () => {
    getSyncLogsMock.mockRejectedValue(new Error('网络不可达'))
    const wrapper = mountCapsule()
    await flushPromises()
    expect(wrapper.find('.alert-stub').text()).toContain('网络不可达')
    expect(wrapper.find('[data-testid="sync-capsule"]').text()).toContain('未同步')
  })

  it('刷新按钮触发重新拉取', async () => {
    const wrapper = mountCapsule()
    await flushPromises()
    const before = getSyncLogsMock.mock.calls.length

    await wrapper.find('[data-testid="sync-drawer-refresh"]').trigger('click')
    await flushPromises()

    expect(getSyncLogsMock.mock.calls.length).toBeGreaterThan(before)
    expect(getSyncLogsMock).toHaveBeenLastCalledWith({ page: 1, page_size: 5 })
  })

  it('抽屉关闭事件 → 收起抽屉（不刷新）', async () => {
    const wrapper = mountCapsule()
    await flushPromises()
    await wrapper.find('[data-testid="sync-capsule"]').trigger('click')
    expect(wrapper.find('.drawer-stub').attributes('data-open')).toBe('true')

    const before = getSyncLogsMock.mock.calls.length
    await wrapper.find('.dlg-close').trigger('click')
    await flushPromises()

    expect(wrapper.find('.drawer-stub').attributes('data-open')).toBe('false')
    expect(getSyncLogsMock.mock.calls.length).toBe(before)
  })

  it('抽屉打开事件（组件自身触发）→ 打开并刷新', async () => {
    const wrapper = mountCapsule()
    await flushPromises()
    const before = getSyncLogsMock.mock.calls.length

    await wrapper.find('.dlg-open').trigger('click')
    await flushPromises()

    expect(wrapper.find('.drawer-stub').attributes('data-open')).toBe('true')
    expect(getSyncLogsMock.mock.calls.length).toBeGreaterThan(before)
  })

  it('tooltip 与 aria-label 提供无障碍描述', async () => {
    getSyncLogsMock.mockResolvedValue([recentLog(2)])
    const wrapper = mountCapsule()
    await flushPromises()
    expect(wrapper.find('.tip').attributes('data-tip')).toContain('点击查看台账')
    expect(wrapper.find('[data-testid="sync-capsule"]').attributes('aria-label')).toContain('数据同步状态')
  })
})
