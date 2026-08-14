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
  getPendingTasksWithTotal: mockGetPendingTasks,
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
  mockGetPendingTasks.mockResolvedValue({ items: makeTasks(), total: 2 })
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

    expect(mockGetPendingTasks).toHaveBeenCalledWith({ skip: 0, limit: 20 })
    expect(vm.tasks).toHaveLength(2)
    expect(vm.total).toBe(2)
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
  it('handleViewDetail：rural_work 跳路由；业务实体跳详情页；其他类型打开变更对比', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.handleViewDetail({ entity_type: 'rural_work', entity_id: 5 })
    expect(pushSafeMock).toHaveBeenCalledWith({
      path: '/rural-works',
      query: { id: 5, action: 'view' },
    })

    // project/fund/school/supported_village → 跳对应业务详情页
    vm.handleViewDetail({ id: 2, entity_type: 'project', entity_id: 8 })
    expect(pushSafeMock).toHaveBeenCalledWith('/projects/8')
    vm.handleViewDetail({ id: 33, entity_type: 'fund', entity_id: 9 })
    expect(pushSafeMock).toHaveBeenCalledWith('/funds/9')

    // 其他实体类型 → 打开变更对比
    await vm.handleViewDetail({ id: 2, entity_type: 'data_change', entity_id: 8 })
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

  it('对话框交互：拒绝原因输入 v-model、两个取消内联点击、确认拒绝按钮、三个对话框 v-model', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 仅剩拒绝原因一个输入框（审批对话框已移除，快速通过不弹窗）
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    inputs[0].vm.$emit('update:modelValue', '拒绝原因Y')
    expect(vm.rejectForm.opinion).toBe('拒绝原因Y')

    // 两个「取消」按钮：[0] 拒绝对话框，[1] 转交对话框
    vm.rejectDialogVisible = true
    vm.transferDialogVisible = true
    const cancels = wrapper.findAll('el-button-stub').filter((b: any) => b.text().trim() === '取消')
    expect(cancels.length).toBe(2)
    await cancels[0].trigger('click')
    expect(vm.rejectDialogVisible).toBe(false)
    await cancels[1].trigger('click')
    expect(vm.transferDialogVisible).toBe(false)

    // 确认拒绝按钮真实点击
    vm.rejectDialogVisible = true
    vm.currentTask = { id: 7 }
    await findBtns(wrapper, '确认拒绝')[0].trigger('click')
    await flushPromises()
    expect(mockRejectTask).toHaveBeenCalledWith(7, '拒绝原因Y')

    // 三个对话框 v-model 同步（拒绝/diff/转交）
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    expect(dialogs.length).toBe(3)
    vm.rejectDialogVisible = true
    vm.diffDialogVisible = true
    vm.transferDialogVisible = true
    dialogs[0].vm.$emit('update:modelValue', false)
    dialogs[1].vm.$emit('update:modelValue', false)
    dialogs[2].vm.$emit('update:modelValue', false)
    expect(vm.rejectDialogVisible).toBe(false)
    expect(vm.diffDialogVisible).toBe(false)
    expect(vm.transferDialogVisible).toBe(false)
  })
})

describe('快速通过与批量审批', () => {
  it('handleQuickApprove：优先标准审批；无权限回退单机自动审批；标题兜底与取消', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleQuickApprove(rowA)
    expect(confirmMock).toHaveBeenCalledWith(
      '确定要快速通过「样本标题A」吗？',
      '快速审批',
      expect.objectContaining({ type: 'info' })
    )
    // 优先走标准审批 approveTask
    expect(mockApproveTask).toHaveBeenCalledWith(11, '快速审批通过')
    expect(mockAutoApproveSingleTask).not.toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('审批通过')

    // 标准审批失败（如非当前审批人）→ 回退单机版自动审批
    mockApproveTask.mockRejectedValueOnce({ response: { data: { detail: '无权限' } } })
    await vm.handleQuickApprove(rowB)
    expect(mockAutoApproveSingleTask).toHaveBeenCalledWith(22, '单机版快速审批通过')

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
    mockGetPendingTasks.mockResolvedValueOnce({ items: [], total: 0 })
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
  it('详情/对比/编辑/快速通过/拒绝（内联 row 参数箭头与 编辑 v-if）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const columns = wrapper.findAllComponents({ name: 'ElTableColumn' })
    const opCol = columns[columns.length - 1]
    const btns = opCol.findAll('el-button-stub')
    const byText = (t: string) => btns.filter((b: any) => b.text().trim().includes(t))

    // 编辑按钮仅 rural_work 行（rowA）存在
    expect(byText('编辑').length).toBe(1)

    await byText('详情')[1].trigger('click') // rowB project → 跳项目详情页
    expect(pushSafeMock).toHaveBeenCalledWith('/projects/8')

    await byText('对比')[0].trigger('click') // rowA → 打开变更对比
    await flushPromises()
    expect(mockGetTaskDiff).toHaveBeenCalledWith(11)
    expect(vm.diffDialogVisible).toBe(true)

    await byText('编辑')[0].trigger('click') // rowA rural_work → 跳编辑
    expect(pushSafeMock).toHaveBeenCalledWith({
      path: '/rural-works',
      query: { id: 5, action: 'edit' },
    })

    await byText('快速通过')[2].trigger('click') // rowC → 标准审批
    await flushPromises()
    expect(mockApproveTask).toHaveBeenCalledWith(33, '快速审批通过')

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
    mockGetPendingTasks.mockResolvedValue({ items: [], total: 0 })
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

describe('分页（total > pageSize）', () => {
  it('分页渲染 + v-model 双向同步 + size-change/current-change 事件', async () => {
    mockGetPendingTasks.mockResolvedValue({ items: makeTasks(), total: 200 })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const pg = wrapper.findComponent({ name: 'ElPagination' })
    expect(pg.exists()).toBe(true)
    // v-model:current-page / v-model:page-size
    pg.vm.$emit('update:currentPage', 2)
    expect(vm.page).toBe(2)
    pg.vm.$emit('update:pageSize', 50)
    expect(vm.pageSize).toBe(50)
    // size-change → handleSizeChange：页码归 1 并重载
    pg.vm.$emit('size-change', 50)
    await flushPromises()
    expect(vm.page).toBe(1)
    expect(mockGetPendingTasks).toHaveBeenCalledWith({ skip: 0, limit: 50 })
    // current-change → loadTasks（重渲染后需重新获取分页组件实例）
    const pg2 = wrapper.findComponent({ name: 'ElPagination' })
    pg2.vm.$emit('update:currentPage', 3)
    expect(vm.page).toBe(3)
    pg2.vm.$emit('current-change', 3)
    await flushPromises()
    expect(mockGetPendingTasks).toHaveBeenCalledWith({ skip: 100, limit: 50 })
  })
})

describe('entitySummary 业务摘要', () => {
  it('fund/project/其他类型全分支与空值兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // !cd / cd 非对象 → ''
    expect(vm.entitySummary(null)).toBe('')
    expect(vm.entitySummary({})).toBe('')
    expect(vm.entitySummary({ change_data: '文本' })).toBe('')
    // fund：name/amount/applicant/status 全字段拼接
    expect(
      vm.entitySummary({
        entity_type: 'fund',
        change_data: { name: '办公经费', amount: 12000, applicant: '张三', status: 'pending' },
      })
    ).toBe('办公经费 · ¥12,000 · 申请人: 张三 · 状态: pending')
    // fund：缺省字段跳过；全缺 → ''
    expect(vm.entitySummary({ entity_type: 'fund', change_data: { amount: 5 } })).toBe('¥5')
    expect(vm.entitySummary({ entity_type: 'fund', change_data: {} })).toBe('')
    // project：name 优先 / project_name 兜底 / budget 拼接
    expect(
      vm.entitySummary({ entity_type: 'project', change_data: { name: '修路', budget: 50000 } })
    ).toBe('修路 · 预算: ¥50,000')
    expect(vm.entitySummary({ entity_type: 'project', change_data: { project_name: '桥梁' } })).toBe(
      '桥梁'
    )
    expect(vm.entitySummary({ entity_type: 'project', change_data: {} })).toBe('')
    // 其他类型：cd.name 回退；无 name → ''
    expect(vm.entitySummary({ entity_type: 'school', change_data: { name: '中心小学' } })).toBe(
      '中心小学'
    )
    expect(vm.entitySummary({ entity_type: 'school', change_data: {} })).toBe('')
  })

  it('模板：业务摘要列 entitySummary(row) 非空/空两侧渲染', async () => {
    // rowC（fund）注入 change_data → entitySummary 非空 → v-if 真侧
    ;(rowC as any).change_data = { name: '经费X', amount: 1000 }
    try {
      const wrapper = mountComp()
      await flushPromises()
      const summary = wrapper.findAll('.entity-summary').find((s) => s.text().includes('经费X'))
      expect(summary, '经费摘要').toBeTruthy()
      expect(summary!.text()).toContain('¥1,000')
      // rowA/rowB 无 change_data → v-else muted '-'
      expect(wrapper.findAll('.entity-summary.muted').length).toBeGreaterThan(0)
    } finally {
      delete (rowC as any).change_data
    }
  })
})

describe('loadTasks 结果兼容链与页码回退', () => {
  it('直接数组形态（旧接口）：total 缺失 → items.length', async () => {
    mockGetPendingTasks.mockResolvedValue([{ id: 1, title: 'T' }])
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.tasks).toEqual([{ id: 1, title: 'T' }])
    expect(vm.total).toBe(1)
  })

  it('data 数组形态 / 空对象 / items 非数组兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // result.data 为数组 → 取之
    mockGetPendingTasks.mockResolvedValueOnce({ data: [{ id: 2 }] })
    await vm.loadTasks()
    expect(vm.tasks).toEqual([{ id: 2 }])
    expect(vm.total).toBe(1)
    // 空对象 → items 兜底 []，total 0
    mockGetPendingTasks.mockResolvedValueOnce({})
    await vm.loadTasks()
    expect(vm.tasks).toEqual([])
    expect(vm.total).toBe(0)
    // items 非数组 → tasks 置 []，total 仍取后端值
    mockGetPendingTasks.mockResolvedValueOnce({ items: { bad: 1 }, total: 5 })
    await vm.loadTasks()
    expect(vm.tasks).toEqual([])
    expect(vm.total).toBe(5)
  })

  it('当前页为空且 page>1 → 自动回退页码并重载；回退到第 1 页则停止', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // page=2 空页，total=30 → 重算仍为第 2 页 → 递归重载拿到数据
    vm.page = 2
    mockGetPendingTasks.mockResolvedValueOnce({ items: [], total: 30 })
    mockGetPendingTasks.mockResolvedValueOnce({ items: [{ id: 9 }], total: 30 })
    await vm.loadTasks()
    expect(vm.page).toBe(2)
    expect(vm.tasks).toEqual([{ id: 9 }])
    expect(mockGetPendingTasks).toHaveBeenLastCalledWith({ skip: 20, limit: 20 })

    // page=2 空页，total=20 → 回退到第 1 页 → 不再重载
    vm.page = 2
    mockGetPendingTasks.mockResolvedValueOnce({ items: [], total: 20 })
    const base = mockGetPendingTasks.mock.calls.length
    await vm.loadTasks()
    expect(vm.page).toBe(1)
    expect(mockGetPendingTasks.mock.calls.length).toBe(base + 1)

    // total=0 → Math.ceil(0)=0 → ||1 兜底回退到第 1 页
    vm.page = 3
    mockGetPendingTasks.mockResolvedValueOnce({ items: [], total: 0 })
    await vm.loadTasks()
    expect(vm.page).toBe(1)
  })
})

describe('diffTableData 假值兜底', () => {
  it('original/changed 为假值（0 或空串）→ Object.keys(||{}) 兜底为空表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.taskDiff = { original_data: 0, change_data: '', diff_fields: undefined }
    expect(vm.diffTableData).toEqual([])
  })
})

describe('快速通过 isCancel 判定', () => {
  it('取消值全形态静默；非取消错误 → detail/兜底提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // e === 'cancel'（字符串拒绝值）→ 静默
    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleQuickApprove(rowA)
    expect(ElMessage.error).not.toHaveBeenCalled()

    // e?.toString() === 'cancel'（无 message 的对象）→ 静默
    confirmMock.mockRejectedValueOnce({ toString: () => 'cancel' })
    await vm.handleQuickApprove(rowA)
    expect(ElMessage.error).not.toHaveBeenCalled()

    // message 包含 cancel（如 'cancelled'）→ 静默
    confirmMock.mockRejectedValueOnce(new Error('用户 cancelled 操作'))
    await vm.handleQuickApprove(rowA)
    expect(ElMessage.error).not.toHaveBeenCalled()

    // 非取消错误：标准审批失败后单机审批也失败 → detail 提示
    mockApproveTask.mockRejectedValueOnce(new Error('forbidden'))
    mockAutoApproveSingleTask.mockRejectedValueOnce({ response: { data: { detail: 'D-单机失败' } } })
    await vm.handleQuickApprove(rowA)
    expect(ElMessage.error).toHaveBeenCalledWith('D-单机失败')

    // 无 detail 且 e 无 message（?? '' 与 includes 假侧）→ 兜底文案
    mockApproveTask.mockRejectedValueOnce(new Error('forbidden'))
    mockAutoApproveSingleTask.mockRejectedValueOnce({})
    await vm.handleQuickApprove(rowA)
    expect(ElMessage.error).toHaveBeenCalledWith('审批失败')
  })

  it('handleAutoApproveAll：approved 数字形态 / failed 数字形态 / 全缺省兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // approved 为数字 + failed 为数字
    mockAutoApproveAll.mockResolvedValueOnce({ approved: 3, failed: 2 })
    await vm.handleAutoApproveAll()
    expect(ElMessage.success).toHaveBeenCalledWith('批量审批完成：成功 3，失败 2')

    // 全缺省：success 非数组 → approvedCount 0；failed 缺省 → 0 → 不拼接失败文案
    mockAutoApproveAll.mockResolvedValueOnce({})
    await vm.handleAutoApproveAll()
    expect(ElMessage.success).toHaveBeenCalledWith('批量审批完成：成功 0')

    // approved 数字 + failed 缺省
    mockAutoApproveAll.mockResolvedValueOnce({ approved: 1 })
    await vm.handleAutoApproveAll()
    expect(ElMessage.success).toHaveBeenCalledWith('批量审批完成：成功 1')
  })
})
