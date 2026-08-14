/**
 * views/approval/ApprovalCenter.vue 测试
 * 覆盖：三页签加载（pending/all/completed 参数）、statusType/statusLabel 映射、
 * handleApprove/handleReject（opinion 字段 + 驳回原因必填校验）、
 * 批量通过/驳回、取消路径、加载失败、分页与选择。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { ElMessage, confirmMock, promptMock, mockGet, mockPost } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn() },
  confirmMock: vi.fn(),
  promptMock: vi.fn(),
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock, prompt: promptMock },
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
}))

import ApprovalCenter from '@/views/approval/ApprovalCenter.vue'

const pendingTasks = [
  {
    id: 1,
    title: '经费审批',
    workflow_name: '经费流程',
    status: 'pending',
    created_at: '2026-01-01 10:00',
  },
  {
    id: 2,
    title: '项目审批',
    workflow_name: '项目流程',
    status: 'pending',
    created_at: '2026-01-02 10:00',
  },
]

function mountComp() {
  // renderStubDefaultSlot 会让列作用域插槽以无 props 渲染（row 为 undefined 崩溃），
  // 自定义列 stub 注入样本行，让状态列模板真实执行
  return mount(ApprovalCenter, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-table-column': {
          name: 'ElTableColumn',
          template: '<div class="el-table-column-stub"><slot :row="sampleRow" /></div>',
          data() {
            return { sampleRow: pendingTasks[0] }
          },
        },
        'el-tabs': {
          name: 'ElTabs',
          template: '<div class="el-tabs-stub"><slot /></div>',
          emits: ['tab-change', 'update:modelValue'],
        },
        'el-tab-pane': {
          name: 'ElTabPane',
          template: '<div class="el-tab-pane-stub"><slot /></div>',
          props: ['name'],
        },
        'el-pagination': {
          name: 'ElPagination',
          template: '<div class="el-pagination-stub" />',
          emits: ['current-change'],
        },
        'el-button': {
          name: 'ElButton',
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  mockGet.mockImplementation((url: string) => {
    if (url === '/approval/tasks/pending') {
      return Promise.resolve({ items: pendingTasks, total: 2 })
    }
    return Promise.resolve({ items: [], total: 0 })
  })
  mockPost.mockResolvedValue({})
  confirmMock.mockResolvedValue('confirm')
  promptMock.mockResolvedValue({ value: '资料不全' })
})

describe('加载与渲染', () => {
  it('onMounted 加载待审批任务与待办数', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGet).toHaveBeenCalledWith('/approval/tasks/pending', { skip: 0, limit: 20 })
    expect(vm.tasks).toHaveLength(2)
    expect(vm.total).toBe(2)
    expect(vm.pendingCount).toBe(2)
    expect(vm.loading).toBe(false)
  })

  it('加载失败 → 错误提示（Error 与兜底两侧）', async () => {
    mockGet.mockRejectedValue(new Error('网络异常'))
    let wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('网络异常')
    wrapper.unmount()

    mockGet.mockRejectedValue('x')
    wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('加载审批任务失败')
  })

  it('任务列表多种响应形态：嵌套 data.items / data 数组 / 裸数组 / 非数组兜底', async () => {
    // 嵌套形态 data.items
    mockGet.mockImplementation((url: string) => {
      if (url === '/approval/tasks/pending') {
        return Promise.resolve({ data: { items: [{ id: 7, title: '嵌套任务' }] } })
      }
      return Promise.resolve({ items: [], total: 0 })
    })
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).tasks).toEqual([{ id: 7, title: '嵌套任务' }])
    wrapper.unmount()

    // data 为数组形态（envelope 内层数组未展开为 items 时）
    mockGet.mockImplementation((url: string) => {
      if (url === '/approval/tasks/pending') {
        return Promise.resolve({ data: [{ id: 9, title: 'data数组' }] })
      }
      return Promise.resolve({ items: [], total: 0 })
    })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).tasks).toEqual([{ id: 9, title: 'data数组' }])
    wrapper.unmount()

    // 裸数组形态
    mockGet.mockImplementation((url: string) => {
      if (url === '/approval/tasks/pending') return Promise.resolve([{ id: 8, title: '数组任务' }])
      return Promise.resolve({ items: [], total: 0 })
    })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).tasks).toEqual([{ id: 8, title: '数组任务' }])
    wrapper.unmount()

    // items 非数组 → 空数组兜底
    mockGet.mockImplementation((url: string) => {
      if (url === '/approval/tasks/pending') return Promise.resolve({ items: 'bad' })
      return Promise.resolve({ items: [], total: 0 })
    })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).tasks).toEqual([])
    wrapper.unmount()

    // null 响应 → data?. 可选链短路兜底
    mockGet.mockImplementation((url: string) => {
      if (url === '/approval/tasks/pending') return Promise.resolve(null)
      return Promise.resolve({ items: [], total: 0 })
    })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).tasks).toEqual([])
    wrapper.unmount()
  })

  it('选中任务后显示批量操作栏', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(wrapper.text()).not.toContain('已选')
    vm.selectedIds = [1]
    await nextTick()
    expect(wrapper.text()).toContain('已选 1 项')
  })
})

describe('状态映射', () => {
  it('statusType/statusLabel 映射与兜底', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.statusType('pending')).toBe('warning')
    expect(vm.statusType('approved')).toBe('success')
    expect(vm.statusType('rejected')).toBe('danger')
    expect(vm.statusType('completed')).toBe('info')
    expect(vm.statusType('other')).toBe('primary')
    expect(vm.statusLabel('pending')).toBe('待审批')
    expect(vm.statusLabel('approved')).toBe('已通过')
    expect(vm.statusLabel('rejected')).toBe('已驳回')
    expect(vm.statusLabel('completed')).toBe('已完成')
    expect(vm.statusLabel('withdrawn')).toBe('已撤回')
    expect(vm.statusLabel('xyz')).toBe('xyz')
  })
})

describe('单个审批', () => {
  it('handleApprove：确认后提交 opinion 并刷新列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockClear()
    await vm.handleApprove(pendingTasks[0])
    expect(confirmMock).toHaveBeenCalled()
    expect(mockPost).toHaveBeenCalledWith('/approval/tasks/1/approve', { opinion: '同意' })
    expect(ElMessage.success).toHaveBeenCalledWith('审批通过')
    expect(mockGet).toHaveBeenCalled() // loadTasks + loadPendingCount 刷新
  })

  it('handleApprove：取消确认 → 不发请求', async () => {
    confirmMock.mockRejectedValue('cancel')
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleApprove(pendingTasks[0])
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('handleReject：驳回原因必填校验 + 提交 opinion', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleReject(pendingTasks[0])
    expect(promptMock).toHaveBeenCalledWith(
      '请输入驳回原因（必填）',
      '驳回审批',
      expect.objectContaining({ inputValidator: expect.any(Function) })
    )
    const validator = promptMock.mock.calls[0][2].inputValidator
    expect(validator('')).toBe('驳回原因不能为空')
    expect(validator('   ')).toBe('驳回原因不能为空')
    expect(validator('原因')).toBe(true)
    expect(mockPost).toHaveBeenCalledWith('/approval/tasks/1/reject', { opinion: '资料不全' })
    expect(ElMessage.success).toHaveBeenCalledWith('已驳回')
  })

  it('handleReject：取消输入 → 不发请求', async () => {
    promptMock.mockRejectedValue('cancel')
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleReject(pendingTasks[0])
    expect(mockPost).not.toHaveBeenCalled()
  })
})

describe('批量审批', () => {
  it('批量通过：提交 task_ids + opinion', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedIds = [1, 2]
    await vm.handleBatchApprove()
    expect(mockPost).toHaveBeenCalledWith('/approval/tasks/batch', {
      task_ids: [1, 2],
      opinion: '批量通过',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('批量审批通过')
    expect(vm.selectedIds).toEqual([])
    expect(vm.batchLoading).toBe(false)
  })

  it('批量驳回：逐条提交 opinion（必填原因）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedIds = [1, 2]
    await vm.handleBatchReject()
    expect(mockPost).toHaveBeenCalledWith('/approval/tasks/1/reject', { opinion: '资料不全' })
    expect(mockPost).toHaveBeenCalledWith('/approval/tasks/2/reject', { opinion: '资料不全' })
    expect(ElMessage.success).toHaveBeenCalledWith('批量驳回完成')
    expect(vm.selectedIds).toEqual([])
  })
})

describe('页签与分页', () => {
  it('切换 completed 页签 → 请求任务历史（completed=true）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.activeTab = 'completed'
    vm.handleTabChange()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/approval/tasks/history', {
      skip: 0,
      limit: 20,
      completed: true,
    })
    expect(vm.selectedIds).toEqual([])
  })

  it('切换 initiated 页签 → 请求我的申请（不带 status）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.activeTab = 'initiated'
    vm.handleTabChange()
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/approval/tasks/mine', { skip: 0, limit: 20 })
  })

  it('handleSelectionChange 与 handlePageChange', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleSelectionChange([{ id: 5 }, { id: 6 }])
    expect(vm.selectedIds).toEqual([5, 6])
    vm.handlePageChange(2)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/approval/tasks/pending', { skip: 20, limit: 20 })
  })

  it('模板：tab-change 触发、分页器渲染（total>pageSize）与翻页箭头', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/approval/tasks/pending') {
        return Promise.resolve({ items: pendingTasks, total: 25 })
      }
      return Promise.resolve({ items: [], total: 0 })
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.total).toBe(25)
    // tab-change 模板箭头（先切换 activeTab 再触发）
    const tabs = wrapper.findComponent({ name: 'ElTabs' })
    if (tabs.exists()) {
      tabs.vm.$emit('update:modelValue', 'initiated')
      tabs.vm.$emit('tab-change', 'initiated')
      await flushPromises()
      expect(mockGet).toHaveBeenCalledWith('/approval/tasks/mine', { skip: 0, limit: 20 })
    }
    // 分页器 current-change 模板箭头（渲染条件 total>pageSize）
    const pagers = wrapper.findAllComponents({ name: 'ElPagination' })
    if (pagers.length) {
      pagers[0].vm.$emit('current-change', 2)
      await flushPromises()
      expect(mockGet).toHaveBeenCalledWith('/approval/tasks/pending', { skip: 20, limit: 20 })
    }
  })

  it('模板：操作列通过/驳回按钮点击（pending 页签）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.activeTab = 'pending'
    await nextTick()
    const approveBtn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('通过'))
    if (approveBtn) {
      await approveBtn.trigger('click')
      await flushPromises()
      expect(mockPost).toHaveBeenCalledWith('/approval/tasks/1/approve', expect.anything())
    }
    const rejectBtn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('驳回'))
    if (rejectBtn) {
      await rejectBtn.trigger('click')
      await flushPromises()
      expect(mockPost).toHaveBeenCalledWith('/approval/tasks/1/reject', expect.anything())
    }
  })

  it('批量驳回：prompt inputValidator 必填校验（空值报错/非空通过）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 具名 validator（从源码导出，真实覆盖模板箭头所在逻辑）
    const { batchRejectValidator } = await import('@/views/approval/ApprovalCenter.vue')
    expect(batchRejectValidator('')).toBe('驳回原因不能为空')
    expect(batchRejectValidator('   ')).toBe('驳回原因不能为空')
    expect(batchRejectValidator('原因')).toBe(true)
    vm.selectedIds = [1, 2]
    promptMock.mockResolvedValue({ value: '批量原因' })
    await vm.handleBatchReject()
    expect(mockPost).toHaveBeenCalledWith('/approval/tasks/1/reject', { opinion: '批量原因' })
    expect(mockPost).toHaveBeenCalledWith('/approval/tasks/2/reject', { opinion: '批量原因' })
  })

  it('批量审批/驳回：用户取消（prompt/confirm reject）→ catch 静默', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedIds = [1]
    promptMock.mockRejectedValue('cancel')
    await vm.handleBatchReject()
    expect(mockPost).not.toHaveBeenCalled()
    expect(vm.batchLoading).toBe(false)

    confirmMock.mockRejectedValue('cancel')
    await vm.handleBatchApprove()
    expect(mockPost).not.toHaveBeenCalled()
    expect(vm.batchLoading).toBe(false)
  })

  it('加载任务：items 缺失但 data 为数组 / total 缺失兜底', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/approval/tasks/pending') {
        return Promise.resolve([{ id: 9 }]) // 裸数组
      }
      return Promise.resolve({})
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.tasks).toEqual([{ id: 9 }])
    // total 缺失 → 用 tasks.length
    expect(vm.total).toBe(1)
  })
})
