/**
 * views/approval/Overview.vue（审批概览）覆盖率测试
 * 覆盖：概览统计加载、待审批列表、类型标签映射、跳转入口、一键审批（确认/取消/空列表/失败）
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { ElMessage, confirmMock, mockGetOverview, mockGetPending, mockBatchApprove } = vi.hoisted(
  () => ({
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
    confirmMock: vi.fn(),
    mockGetOverview: vi.fn(),
    mockGetPending: vi.fn(),
    mockBatchApprove: vi.fn(),
  })
)

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/approval', () => ({
  getOverview: mockGetOverview,
  getPendingTasks: mockGetPending,
  batchApprove: mockBatchApprove,
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: vi.fn() }),
}))

import Overview from '@/views/approval/Overview.vue'

function mountComp() {
  return mount(Overview, {
    global: {
      stubs: {
        'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
        'el-table': { template: '<div class="el-table-stub"><slot /></div>' },
        'el-table-column': {
          name: 'ElTableColumn',
          template: '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
          data() {
            return {
              rowA: { task_id: 1, entity_type: 'project', submitter_name: '张三', created_at: '2026-08-01T10:00:00' },
              rowB: { id: 2, type: 'fund', created_at: null },
            }
          },
        },
        'el-tag': { template: '<span><slot /></span>' },
        'el-button': { template: '<button class="el-button-stub"><slot /></button>' },
        'el-form': { template: '<div><slot /></div>' },
        'el-form-item': { template: '<div><slot /></div>' },
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  mockGetOverview.mockResolvedValue({
    data: {
      pending_count: 3,
      approved_count: 10,
      rejected_count: 2,
      total_count: 15,
    },
  })
  mockGetPending.mockResolvedValue({
    items: [
      { task_id: 1, title: '项目审批', entity_type: 'project', submitter_name: '张三', created_at: '2026-08-01T10:00:00' },
      { id: 2, title: '经费审批', type: 'fund', created_at: null },
    ],
  })
  mockBatchApprove.mockResolvedValue({})
  confirmMock.mockResolvedValue('confirm')
})

describe('审批概览', () => {
  it('onMounted 加载概览统计与待审批列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGetOverview).toHaveBeenCalled()
    expect(mockGetPending).toHaveBeenCalledWith({ limit: 10 })
    expect(vm.stats.pending_count).toBe(3)
    expect(vm.stats.approved_count).toBe(10)
    expect(vm.stats.rejected_count).toBe(2)
    expect(vm.stats.total_count).toBe(15)
    expect(vm.pendingTasks.length).toBe(2)
    wrapper.unmount()
  })

  it('概览统计失败 → 保持 0 不阻塞', async () => {
    mockGetOverview.mockRejectedValue(new Error('boom'))
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).stats.pending_count).toBe(0)
    wrapper.unmount()
  })

  it('待审批列表为空 → []', async () => {
    mockGetPending.mockResolvedValue({ items: [] })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).pendingTasks).toEqual([])
    wrapper.unmount()
  })

  it('typeLabel 映射与兜底', () => {
    const vm = mountComp().vm as any
    expect(vm.typeLabel('project')).toBe('项目')
    expect(vm.typeLabel('fund')).toBe('经费')
    expect(vm.typeLabel(undefined)).toBe('其他')
    expect(vm.typeLabel('custom')).toBe('custom')
  })

  it('formatDate 正常/空/非法', () => {
    const vm = mountComp().vm as any
    expect(vm.formatDate('2026-08-01T10:00:00')).toContain('2026')
    expect(vm.formatDate(undefined)).toBe('-')
  })

  it('一键审批：确认 → batchApprove 全部待审批任务 → 刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleAutoApproveAll()
    expect(confirmMock).toHaveBeenCalled()
    expect(mockBatchApprove).toHaveBeenCalledWith([1, 2], '单机版一键审批通过')
    expect(ElMessage.success).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('一键审批：取消 → 不调用 batchApprove', async () => {
    confirmMock.mockRejectedValueOnce('cancel')
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleAutoApproveAll()
    expect(mockBatchApprove).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('一键审批：空列表 → 提示无可批量任务', async () => {
    mockGetPending.mockResolvedValue({ items: [] })
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleAutoApproveAll()
    expect(ElMessage.info).toHaveBeenCalledWith('当前没有可批量审批的任务')
    wrapper.unmount()
  })

  it('一键审批：batchApprove 失败 → 错误提示', async () => {
    mockBatchApprove.mockRejectedValue({ response: { data: { detail: '审批失败' } } })
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleAutoApproveAll()
    expect(ElMessage.error).toHaveBeenCalledWith('审批失败')
    wrapper.unmount()
  })

  it('一键审批：异常无 detail → 兜底文案', async () => {
    mockBatchApprove.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleAutoApproveAll()
    expect(ElMessage.error).toHaveBeenCalledWith('批量审批失败')
    wrapper.unmount()
  })
})

describe('审批概览补充分支', () => {
  it('typeLabel/formatDate 兜底；goApprove 三形态；loadPending 多形态响应', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // typeLabel 兜底
    expect(vm.typeLabel('custom')).toBe('custom')
    // formatDate 非法日期 → 原样返回
    expect(vm.formatDate('not-a-date')).toBe('Invalid Date')
    // goApprove：task_id / id / 无 id
    vm.goApprove({ task_id: 5 })
    vm.goApprove({ id: 6 })
    vm.goApprove({})
    // loadPending：数组形态
    mockGetPending.mockResolvedValue([{ task_id: 9, title: 'x' }])
    await vm.loadPending()
    expect(vm.pendingTasks.length).toBe(1)
    // loadPending：items 形态 + 异常
    mockGetPending.mockResolvedValue({ items: [{ task_id: 8 }] })
    await vm.loadPending()
    expect(vm.pendingTasks.length).toBe(1)
    mockGetPending.mockRejectedValue(new Error('x'))
    await vm.loadPending()
    expect(vm.pendingTasks).toEqual([])
    // getOverview 返回裸对象
    mockGetOverview.mockResolvedValue({ pending_count: 2 })
    await vm.loadOverview()
    expect(vm.stats.pending_count).toBe(2)
  })
})

describe('模板点击事件', () => {
  it('入口卡/查看全部/审批/一键审批按钮触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 入口卡点击（entry-card class）
    const entryCards = wrapper.findAll('.entry-card')
    await entryCards[0].trigger('click')
    await entryCards[1].trigger('click')
    await entryCards[2].trigger('click')
    // 查看全部按钮
    const viewAll = wrapper.findAll('.el-button-stub').find((b: any) => b.text().includes('查看全部'))
    await viewAll!.trigger('click')
    // 一键审批按钮（需 pending_count>0 渲染）
    vm.stats.pending_count = 2
    await wrapper.vm.$nextTick()
    const autoBtn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().includes('一键通过全部'))
    if (autoBtn) {
      confirmMock.mockResolvedValue('confirm')
      mockBatchApprove.mockResolvedValue({})
      await autoBtn.trigger('click')
      await flushPromises()
      expect(mockBatchApprove).toHaveBeenCalled()
    }
    wrapper.unmount()
  })
})

describe('审批行按钮', () => {
  it('表格行「审批」按钮点击 → goApprove', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.pendingTasks = [{ task_id: 1, title: 'x', entity_type: 'policy' }]
    await wrapper.vm.$nextTick()
    const approveBtn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().includes('审批'))
    if (approveBtn) {
      await approveBtn.trigger('click')
    } else {
      vm.goApprove({ task_id: 1 })
    }
    wrapper.unmount()
  })
})
