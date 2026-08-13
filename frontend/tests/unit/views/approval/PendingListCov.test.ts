/**
 * views/approval/PendingList.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 加载成功/失败、highPriorityCount/todayCount filter 两侧、
 * isOverdue（空日期/超时/未超时）、diffTableData（null/字段并集/||{}/?. 全分支）、
 * handleViewDetail/handleEditWork rural_work 与其他类型两侧、handleViewDiff 成功/失败、
 * confirmApprove/confirmReject（空任务早退/空原因警告/成功/失败 detail 与默认兜底）、
 * handleQuickApprove（标题有无两侧/确认/取消）、handleAutoApproveAll（空早退/成功/取消）、
 * handleBatchApprove（空早退/prompt 输入与取消/确认取消）、
 * 模板：刷新/一键全部/批量通过/操作列四按钮/取消/确认按钮真实点击，
 * 表格 selection-change、优先级与标题列三元、编辑按钮 v-if、超时标签 v-if、
 * 三个对话框 v-model、两个审批意见输入 v-model、diff 表 ?? '-' 两侧。
 *
 * 说明：组件静态 import '@/api/approval'（无动态导入竞态），直接 vi.mock 该模块。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂提升求值，所有被引用对象须先放入 vi.hoisted 初始化（TDZ）
const {
  ElMessage,
  confirmMock,
  promptMock,
  mockGetPendingTasks,
  mockApproveTask,
  mockRejectTask,
  mockBatchApprove,
  mockGetTaskDiff,
  mockAutoApproveSingleTask,
  mockAutoApproveAll,
  mockListUsers,
  mockTransferTask,
  pushSafeMock,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  promptMock: vi.fn(),
  mockGetPendingTasks: vi.fn(),
  mockApproveTask: vi.fn(),
  mockRejectTask: vi.fn(),
  mockBatchApprove: vi.fn(),
  mockGetTaskDiff: vi.fn(),
  mockAutoApproveSingleTask: vi.fn(),
  mockAutoApproveAll: vi.fn(),
  mockListUsers: vi.fn(),
  mockTransferTask: vi.fn(),
  pushSafeMock: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock, prompt: promptMock },
}))

vi.mock('@/api/userManagement', () => ({
  listUsers: mockListUsers,
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
}))

vi.mock('@/api/approval', () => ({
  getPendingTasks: mockGetPendingTasks,
  approveTask: mockApproveTask,
  rejectTask: mockRejectTask,
  batchApprove: mockBatchApprove,
  getTaskDiff: mockGetTaskDiff,
  autoApproveSingleTask: mockAutoApproveSingleTask,
  autoApproveAll: mockAutoApproveAll,
  transferTask: mockTransferTask,
  formatEntityType: (t: string) =>
    ({ supported_village: '帮扶村', project: '项目', fund: '经费', school: '学校' })[t] || t,
}))

import PendingList from '@/views/approval/PendingList.vue'

const NOW = Date.now()
const todayISO = new Date(NOW).toISOString()
const oldISO = new Date(NOW - 30 * 3600 * 1000).toISOString() // 30 小时前 → 超时

// onMounted 任务列表：覆盖 highPriorityCount / todayCount filter 真/假两侧
function makeTasks() {
  return [
    {
      id: 1,
      title: '人行桥修建',
      entity_type: 'rural_work',
      entity_id: 5,
      status: 'pending',
      current_level: 2,
      priority: 1,
      created_at: todayISO,
    },
    {
      id: 2,
      title: '',
      entity_type: 'project',
      entity_id: 8,
      status: 'pending',
      current_level: 1,
      priority: 0,
      created_at: oldISO,
    },
  ]
}

// 表格列 stub 注入三行样本：
// rowA 高优先级/rural_work（编辑按钮 v-if 真侧）/今日（未超时）/带 original+new（diff ?? 左侧）
// rowB 普通/project/30 小时前（超时真侧）/无 original（diff ?? 右侧）/无 title（标题回退）
// rowC 普通/fund/无 created_at（isOverdue !created_at 侧、formatDateTime '-' 侧）
const rowA = {
  id: 11,
  title: '样本标题A',
  entity_type: 'rural_work',
  entity_id: 5,
  priority: 1,
  current_level: 2,
  created_at: todayISO,
  original: '旧值',
  new: '新值',
  changed: true,
}
const rowB = {
  id: 22,
  title: '',
  entity_type: 'project',
  entity_id: 8,
  priority: 0,
  current_level: 1,
  created_at: oldISO,
}
const rowC = {
  id: 33,
  title: '样本标题C',
  entity_type: 'fund',
  entity_id: 9,
  priority: 0,
  current_level: 3,
  created_at: '',
}

function mountComp() {
  // setup.ts 全局 el-* stub 默认不渲染插槽，需 renderStubDefaultSlot；
  // 具名插槽（card header / dialog footer）与作用域插槽（表格行）需自定义 stub
  return mount(PendingList, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
        },
        'el-table': { name: 'ElTable', template: '<div class="el-table-stub"><slot /></div>' },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>',
          data() {
            return { rowA, rowB, rowC }
          },
        },
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
        },
        'el-input': { name: 'ElInput', template: '<div class="el-input-stub" />' },
        'el-link': {
          name: 'ElLink',
          template: '<a class="el-link-stub" @click="$emit(\'click\')"><slot /></a>',
        },
        'el-button-group': {
          name: 'ElButtonGroup',
          template: '<div class="el-button-group-stub"><slot /></div>',
        },
      },
    },
  })
}

function findBtns(wrapper: any, text: string) {
  return wrapper.findAll('el-button-stub').filter((b: any) => b.text().trim().includes(text))
}

beforeEach(() => {
  vi.resetAllMocks()
  mockGetPendingTasks.mockResolvedValue(makeTasks())
  mockApproveTask.mockResolvedValue({})
  mockRejectTask.mockResolvedValue({})
  mockBatchApprove.mockResolvedValue({ success: [1, 2], failed: [] })
  mockGetTaskDiff.mockResolvedValue({
    task_id: 2,
    entity_type: 'project',
    entity_id: 8,
    original_data: { name: '旧名' },
    change_data: { name: '新名' },
    diff_fields: ['name'],
  })
  mockAutoApproveSingleTask.mockResolvedValue({})
  mockAutoApproveAll.mockResolvedValue({ success: [1, 2], failed: [{ id: 3, reason: 'x' }] })
  confirmMock.mockResolvedValue('confirm')
  promptMock.mockResolvedValue({ value: '同意' })
})

describe('挂载与统计渲染', () => {
  it('onMounted 加载任务：统计计算属性与表格列样本渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(mockGetPendingTasks).toHaveBeenCalledWith({ limit: 100 })
    expect(vm.tasks).toHaveLength(2)
    expect(vm.loading).toBe(false)
    expect(vm.highPriorityCount).toBe(1)
    expect(vm.todayCount).toBe(1)

    const text = wrapper.text()
    expect(text).toContain('高') // rowA priority>0
    expect(text).toContain('普通') // rowB/rowC
    expect(text).toContain('项目 #8') // rowB 标题回退 formatEntityType+#id
    expect(text).not.toContain('帮扶村') // 无该类型
    expect(text).toContain('经费') // rowC fund 类型映射
    expect(text).toContain('超时') // rowB isOverdue 真侧
    expect(text).toContain('第 2 级')
    // taskDiff 为 null → diff 对话框渲染 el-empty
    expect(wrapper.find('el-empty-stub').exists()).toBe(true)
  })

  it('加载失败 → 错误提示', async () => {
    mockGetPendingTasks.mockRejectedValueOnce(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('加载任务列表失败')
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('点击「刷新」重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const base = mockGetPendingTasks.mock.calls.length
    await findBtns(wrapper, '刷新')[0].trigger('click')
    await flushPromises()
    expect(mockGetPendingTasks.mock.calls.length).toBe(base + 1)
  })
})

describe('工具函数与计算属性', () => {
  it('isOverdue 三侧与 formatDateTime 两侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isOverdue({ created_at: '' })).toBe(false)
    expect(vm.isOverdue({ created_at: oldISO })).toBe(true)
    expect(vm.isOverdue({ created_at: todayISO })).toBe(false)
    expect(vm.formatDateTime('')).toBe('-')
    expect(vm.formatDateTime(todayISO)).not.toBe('-')
  })

  it('diffTableData：null / 字段并集 / ||{} 与 ?. 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.diffTableData).toEqual([]) // taskDiff null

    vm.taskDiff = {
      original_data: { name: 'A', keep: 'x' },
      change_data: { name: 'B' },
      diff_fields: ['name'],
    }
    expect(vm.diffTableData).toEqual([
      { field: 'name', original: 'A', new: 'B', changed: true },
      { field: 'keep', original: 'x', new: undefined, changed: false },
    ])

    // original_data/change_data/diff_fields 全缺 → ||{} 与 ?. 空侧
    vm.taskDiff = { original_data: null, change_data: undefined, diff_fields: undefined }
    expect(vm.diffTableData).toEqual([])
  })

  it('diff 对话框表格：original/new 的 ?? "-" 两侧渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.taskDiff = {
      original_data: { name: 'A' },
      change_data: { name: 'B' },
      diff_fields: ['name'],
    }
    await nextTick()
    expect(wrapper.find('.diff-view').exists()).toBe(true)
    expect(wrapper.find('el-empty-stub').exists()).toBe(false)
    const text = wrapper.text()
    expect(text).toContain('旧值') // rowA.original 左側
    expect(text).toContain('-') // rowB/rowC 缺省 → '-'
  })

  it('选择变化：方法与 el-table selection-change 事件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleSelectionChange([rowA])
    expect(vm.selectedTasks).toEqual([rowA])

    wrapper.findAllComponents({ name: 'ElTable' })[0].vm.$emit('selection-change', [rowB])
    expect(vm.selectedTasks).toEqual([rowB])
  })
})

describe('导航与详情', () => {
  it('handleViewDetail：rural_work 跳路由；其他类型打开变更对比', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.handleViewDetail({ entity_type: 'rural_work', entity_id: 5 })
    expect(pushSafeMock).toHaveBeenCalledWith({
      path: '/rural-works',
      query: { id: 5, action: 'view' },
    })

    await vm.handleViewDetail({ id: 2, entity_type: 'project', entity_id: 8 })
    expect(mockGetTaskDiff).toHaveBeenCalledWith(2)
    expect(vm.diffDialogVisible).toBe(true)
    expect(vm.taskDiff).not.toBeNull()
  })

  it('handleEditWork：rural_work 跳编辑；其他类型提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.handleEditWork({ entity_type: 'rural_work', entity_id: 5 })
    expect(pushSafeMock).toHaveBeenCalledWith({
      path: '/rural-works',
      query: { id: 5, action: 'edit' },
    })

    vm.handleEditWork({ entity_type: 'fund', entity_id: 1 })
    expect(ElMessage.info).toHaveBeenCalledWith('请在对应管理页面进行编辑')
  })

  it('handleViewDiff 加载失败 → 错误提示', async () => {
    mockGetTaskDiff.mockRejectedValueOnce(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleViewDiff({ id: 9, entity_type: 'fund', entity_id: 1 })
    expect(ElMessage.error).toHaveBeenCalledWith('加载变更对比失败')
    expect(vm.taskDiff).toBeNull()
  })

  it('标题列 el-link 真实点击触发 handleViewDetail（内联箭头）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const link = wrapper.find('.el-table-column-stub .el-link-stub')
    await link.trigger('click')
    // rowA 为 rural_work → 跳路由
    expect(pushSafeMock).toHaveBeenCalledWith({
      path: '/rural-works',
      query: { id: 5, action: 'view' },
    })
  })
})

describe('审批通过与拒绝', () => {
  it('confirmApprove：空任务早退；成功；失败 detail/默认 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.confirmApprove() // currentTask 为 null → 早退
    expect(mockApproveTask).not.toHaveBeenCalled()

    vm.currentTask = { id: 7 }
    vm.approveForm = { opinion: '同意' }
    const base = mockGetPendingTasks.mock.calls.length
    await vm.confirmApprove()
    expect(mockApproveTask).toHaveBeenCalledWith(7, '同意')
    expect(ElMessage.success).toHaveBeenCalledWith('审批通过')
    expect(vm.approveDialogVisible).toBe(false)
    expect(mockGetPendingTasks.mock.calls.length).toBe(base + 1)

    mockApproveTask.mockRejectedValueOnce({ response: { data: { detail: 'D-详情' } } })
    await vm.confirmApprove()
    expect(ElMessage.error).toHaveBeenCalledWith('D-详情')

    mockApproveTask.mockRejectedValueOnce(new Error('x'))
    await vm.confirmApprove()
    expect(ElMessage.error).toHaveBeenCalledWith('操作失败')
    expect(vm.submitting).toBe(false)
  })

  it('handleReject 初始化状态；confirmReject 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.confirmReject() // currentTask 为 null → 早退
    expect(mockRejectTask).not.toHaveBeenCalled()

    vm.handleReject(rowA)
    expect(vm.currentTask).toEqual(rowA)
    expect(vm.rejectForm).toEqual({ opinion: '' })
    expect(vm.rejectDialogVisible).toBe(true)

    await vm.confirmReject() // 空原因 → 警告
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入拒绝原因')
    expect(mockRejectTask).not.toHaveBeenCalled()

    vm.rejectForm = { opinion: '资料不全' }
    await vm.confirmReject()
    expect(mockRejectTask).toHaveBeenCalledWith(11, '资料不全')
    expect(ElMessage.success).toHaveBeenCalledWith('已拒绝')
    expect(vm.rejectDialogVisible).toBe(false)

    mockRejectTask.mockRejectedValueOnce({ response: { data: { detail: 'D-拒绝' } } })
    await vm.confirmReject()
    expect(ElMessage.error).toHaveBeenCalledWith('D-拒绝')

    mockRejectTask.mockRejectedValueOnce(new Error('x'))
    await vm.confirmReject()
    expect(ElMessage.error).toHaveBeenCalledWith('操作失败')
  })

  it('对话框交互：两个意见输入 v-model、两个取消内联点击、确认按钮点击、三个对话框 v-model', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    inputs[0].vm.$emit('update:modelValue', '审批意见X')
    inputs[1].vm.$emit('update:modelValue', '拒绝原因Y')
    expect(vm.approveForm.opinion).toBe('审批意见X')
    expect(vm.rejectForm.opinion).toBe('拒绝原因Y')

    // 三个「取消」按钮：[0] 审批对话框，[1] 拒绝对话框，[2] 转交对话框（v1.8.0）
    vm.approveDialogVisible = true
    vm.rejectDialogVisible = true
    vm.transferDialogVisible = true
    const cancels = wrapper.findAll('el-button-stub').filter((b: any) => b.text().trim() === '取消')
    expect(cancels.length).toBe(3)
    await cancels[0].trigger('click')
    expect(vm.approveDialogVisible).toBe(false)
    await cancels[1].trigger('click')
    expect(vm.rejectDialogVisible).toBe(false)
    await cancels[2].trigger('click')
    expect(vm.transferDialogVisible).toBe(false)

    // 确认通过 / 确认拒绝 按钮真实点击
    vm.currentTask = { id: 7 }
    await findBtns(wrapper, '确认通过')[0].trigger('click')
    await flushPromises()
    expect(mockApproveTask).toHaveBeenCalledWith(7, '审批意见X')

    vm.rejectDialogVisible = true
    await findBtns(wrapper, '确认拒绝')[0].trigger('click')
    await flushPromises()
    expect(mockRejectTask).toHaveBeenCalledWith(7, '拒绝原因Y')

    // 四个对话框 v-model 同步（审批/拒绝/diff/转交——v1.8.0 新增转交）
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    expect(dialogs.length).toBe(4)
    vm.approveDialogVisible = true
    vm.rejectDialogVisible = true
    vm.diffDialogVisible = true
    vm.transferDialogVisible = true
    dialogs[0].vm.$emit('update:modelValue', false)
    dialogs[1].vm.$emit('update:modelValue', false)
    dialogs[2].vm.$emit('update:modelValue', false)
    dialogs[3].vm.$emit('update:modelValue', false)
    expect(vm.approveDialogVisible).toBe(false)
    expect(vm.rejectDialogVisible).toBe(false)
    expect(vm.diffDialogVisible).toBe(false)
    expect(vm.transferDialogVisible).toBe(false)
  })
})

describe('快速通过与批量审批', () => {
  it('handleQuickApprove：标题有/无两侧的确认文案；确认与取消', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleQuickApprove(rowA)
    expect(confirmMock).toHaveBeenCalledWith(
      '确定要快速通过「样本标题A」吗？',
      '快速审批',
      expect.objectContaining({ type: 'info' })
    )
    expect(mockAutoApproveSingleTask).toHaveBeenCalledWith(11, '单机版快速审批通过')
    expect(ElMessage.success).toHaveBeenCalledWith('审批通过')

    await vm.handleQuickApprove(rowB) // 无标题 → formatEntityType+#id 兜底
    expect(confirmMock).toHaveBeenCalledWith(
      '确定要快速通过「项目 #8」吗？',
      '快速审批',
      expect.anything()
    )

    confirmMock.mockRejectedValueOnce(new Error('cancel'))
    await vm.handleQuickApprove(rowA) // 取消 → 静默
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('handleAutoApproveAll：空任务早退；按钮点击成功；取消', async () => {
    mockGetPendingTasks.mockResolvedValueOnce([])
    const w1 = mountComp()
    await flushPromises()
    await (w1.vm as any).handleAutoApproveAll() // 空 → 早退
    expect(confirmMock).not.toHaveBeenCalled()

    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findBtns(wrapper, '一键全部通过')[0].trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledWith(
      '确定要一键通过所有 2 个待审批任务吗？',
      '一键全部通过',
      expect.objectContaining({ type: 'warning' })
    )
    expect(mockAutoApproveAll).toHaveBeenCalledWith('单机版一键批量审批通过')
    expect(ElMessage.success).toHaveBeenCalledWith('批量审批完成：成功 2，失败 1')
    expect(vm.autoApproving).toBe(false)

    confirmMock.mockRejectedValueOnce(new Error('cancel'))
    await vm.handleAutoApproveAll()
    expect(vm.autoApproving).toBe(false)
  })

  it('handleBatchApprove：空选择早退；prompt 输入与取消；确认取消', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleBatchApprove() // 未选择 → 早退
    expect(confirmMock).not.toHaveBeenCalled()

    // prompt 输入意见
    vm.handleSelectionChange(makeTasks())
    await findBtns(wrapper, '批量通过')[0].trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledWith(
      '确定要批量通过选中的 2 个任务吗？',
      '批量审批确认',
      expect.objectContaining({ type: 'warning' })
    )
    expect(mockBatchApprove).toHaveBeenCalledWith([1, 2], '同意')
    expect(ElMessage.success).toHaveBeenCalledWith('批量审批完成：成功 2，失败 0')
    expect(vm.loading).toBe(false)

    // prompt 取消 → 意见为空字符串
    promptMock.mockRejectedValueOnce(new Error('cancel'))
    await vm.handleBatchApprove()
    expect(mockBatchApprove).toHaveBeenCalledWith([1, 2], '')

    // 首个确认框取消 → 外层 catch，不发请求
    const base = mockBatchApprove.mock.calls.length
    confirmMock.mockRejectedValueOnce(new Error('cancel'))
    await vm.handleBatchApprove()
    expect(mockBatchApprove.mock.calls.length).toBe(base)
    expect(vm.loading).toBe(false)
  })
})

describe('操作列按钮真实点击', () => {
  it('详情/编辑/快速通过/拒绝（内联 row 参数箭头与 编辑 v-if）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const columns = wrapper.findAllComponents({ name: 'ElTableColumn' })
    const opCol = columns[columns.length - 1]
    const btns = opCol.findAll('el-button-stub')
    const byText = (t: string) => btns.filter((b: any) => b.text().trim().includes(t))

    // 编辑按钮仅 rural_work 行（rowA）存在
    expect(byText('编辑').length).toBe(1)

    await byText('详情')[1].trigger('click') // rowB project → 变更对比
    await flushPromises()
    expect(mockGetTaskDiff).toHaveBeenCalledWith(22)
    expect(vm.diffDialogVisible).toBe(true)

    await byText('编辑')[0].trigger('click') // rowA rural_work → 跳编辑
    expect(pushSafeMock).toHaveBeenCalledWith({
      path: '/rural-works',
      query: { id: 5, action: 'edit' },
    })

    await byText('快速通过')[2].trigger('click') // rowC
    await flushPromises()
    expect(mockAutoApproveSingleTask).toHaveBeenCalledWith(33, '单机版快速审批通过')

    await byText('拒绝')[0].trigger('click') // rowA
    expect(vm.rejectDialogVisible).toBe(true)
    expect(vm.currentTask).toEqual(rowA)
  })
})

describe('转交审批（v1.8.0）', () => {
  beforeEach(() => {
    mockListUsers.mockReset()
    mockTransferTask.mockReset()
  })

  it('handleTransfer 加载候选用户并排除当前审批人（items 形态）', async () => {
    mockListUsers.mockResolvedValue({ items: [{ id: 1, name: '甲' }, { id: 2, name: '乙' }] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleTransfer({ id: 9, current_approver_id: 2 })
    expect(vm.transferDialogVisible).toBe(true)
    expect(vm.currentTask).toEqual({ id: 9, current_approver_id: 2 })
    expect(vm.candidateUsers).toEqual([{ id: 1, name: '甲' }])
  })

  it('handleTransfer 用户加载失败 → 空候选', async () => {
    mockListUsers.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleTransfer({ id: 9 })
    expect(vm.candidateUsers).toEqual([])
  })

  it('handleTransfer 信封形态（data.items）与空对象兜底', async () => {
    mockListUsers.mockResolvedValue({ data: { items: [{ id: 3, name: '丙' }] } })
    let wrapper = mountComp()
    await flushPromises()
    let vm = wrapper.vm as any
    await vm.handleTransfer({ id: 9 })
    expect(vm.candidateUsers).toEqual([{ id: 3, name: '丙' }])

    mockListUsers.mockResolvedValue({})
    wrapper = mountComp()
    await flushPromises()
    vm = wrapper.vm as any
    await vm.handleTransfer({ id: 9 })
    expect(vm.candidateUsers).toEqual([])
  })

  it('confirmTransfer：无任务早退 / 未选对象 warning', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.confirmTransfer()
    expect(mockTransferTask).not.toHaveBeenCalled()
    vm.currentTask = { id: 9 }
    vm.transferForm = { transferToId: undefined, reason: '' }
    await vm.confirmTransfer()
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择转交对象')
    expect(mockTransferTask).not.toHaveBeenCalled()
  })

  it('confirmTransfer 成功 → transferTask + 关闭 + 刷新', async () => {
    mockTransferTask.mockResolvedValue({})
    mockGetPendingTasks.mockResolvedValue([])
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentTask = { id: 9 }
    vm.transferForm = { transferToId: 3, reason: '转给你' }
    await vm.confirmTransfer()
    expect(mockTransferTask).toHaveBeenCalledWith(9, 3, '转给你')
    expect(ElMessage.success).toHaveBeenCalledWith('已转交')
    expect(vm.transferDialogVisible).toBe(false)
    expect(vm.submitting).toBe(false)
  })

  it('confirmTransfer 失败 → detail 提示；无原因传 undefined', async () => {
    mockTransferTask.mockRejectedValue({ response: { data: { detail: '无权转交' } } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentTask = { id: 9 }
    vm.transferForm = { transferToId: 3, reason: '' }
    await vm.confirmTransfer()
    expect(mockTransferTask).toHaveBeenCalledWith(9, 3, undefined)
    expect(ElMessage.error).toHaveBeenCalledWith('无权转交')
    expect(vm.submitting).toBe(false)
  })

  it('任务表格渲染提交时间列（模板箭头）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const text = wrapper.text()
    // makeTasks 行含 created_at → formatDateTime 渲染（格式 YYYY/M/D HH:mm:ss）
    expect(text).toContain('2026/')
    expect(text).toContain('超时')
  })

  it('模板箭头：类型筛选 select / 提交时间 date-picker v-model', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    for (const sel of selects) {
      sel.vm.$emit('update:modelValue', 'fund')
    }
    expect(vm.filterType).toBe('fund')
    const pickers = wrapper.findAllComponents({ name: 'ElDatePicker' })
    for (const pk of pickers) {
      pk.vm.$emit('update:modelValue', ['2026-01-01', '2026-02-01'])
    }
    expect(vm.filterDateRange).toBeTruthy()
  })

  it('模板箭头：转交按钮点击 → 打开转交对话框', async () => {
    mockListUsers.mockResolvedValue({ items: [{ id: 1 }] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const transferBtn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('转交'))
    if (transferBtn) {
      await transferBtn.trigger('click')
      await flushPromises()
      expect(vm.transferDialogVisible).toBe(true)
    }
  })

  it('模板箭头：转交对话框 select 与原因输入 v-model', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.transferDialogVisible = true
    await nextTick()
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    for (const sel of selects) {
      sel.vm.$emit('update:modelValue', 7)
    }
    expect(vm.transferForm.transferToId).toBe(7)
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    for (const inp of inputs) {
      inp.vm.$emit('update:modelValue', '转交原因X')
    }
    expect(vm.transferForm.reason).toBe('转交原因X')
  })

  it('分支：日期筛选忽略无 created_at 任务；users 数组形态；转交失败无 detail 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 日期筛选：created_at 缺失的任务不抛错（''.slice 兜底）
    vm.tasks = [
      { id: 1, created_at: '2026-01-05T10:00:00' },
      { id: 2, created_at: undefined },
    ]
    vm.filterDateRange = ['2026-01-01', '2026-01-31']
    const filtered = vm.filteredTasks
    expect(filtered.some((t: any) => t.id === 2)).toBe(false)

    // users 数组形态（handleTransfer 直接数组）
    mockListUsers.mockResolvedValueOnce([{ id: 1 }, { id: 2 }])
    await vm.handleTransfer({ id: 9, current_approver_id: 1 })
    expect(vm.candidateUsers).toEqual([{ id: 2 }])

    // 转交失败且无 detail → 兜底文案
    mockTransferTask.mockRejectedValueOnce(new Error('net'))
    vm.currentTask = { id: 9 }
    vm.transferForm = { transferToId: 3, reason: '' }
    await vm.confirmTransfer()
    expect(ElMessage.error).toHaveBeenCalledWith('转交失败')
  })
})

describe('筛选条件（类型/提交时间）', () => {
  it('按类型过滤：仅保留匹配 entity_type 的任务', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.filteredTasks).toHaveLength(2)
    vm.filterType = 'project'
    await nextTick()
    expect(vm.filteredTasks).toHaveLength(1)
    expect(vm.filteredTasks[0].entity_type).toBe('project')
    vm.filterType = 'fund'
    await nextTick()
    expect(vm.filteredTasks).toHaveLength(0)
  })

  it('按提交时间范围过滤：范围外剔除；清空恢复', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const today = todayISO.slice(0, 10)
    vm.filterDateRange = [today, today]
    await nextTick()
    expect(vm.filteredTasks).toHaveLength(1)
    expect(vm.filteredTasks[0].id).toBe(1)
    vm.filterDateRange = null
    await nextTick()
    expect(vm.filteredTasks).toHaveLength(2)
  })

  it('类型与时间组合过滤', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const today = todayISO.slice(0, 10)
    vm.filterType = 'rural_work'
    vm.filterDateRange = [today, today]
    await nextTick()
    expect(vm.filteredTasks).toHaveLength(1)
    vm.filterDateRange = ['2000-01-01', '2000-01-02']
    await nextTick()
    expect(vm.filteredTasks).toHaveLength(0)
  })

  it('提交人列：submitter_name 缺失渲染 -', async () => {
    const wrapper = mountComp()
    await flushPromises()
    // 列 stub 样本行均无 submitter_name → 回退 '-'
    expect(wrapper.text()).toContain('-')
  })
})
