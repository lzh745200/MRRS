/**
 * views/system/TaskManager.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted/onUnmounted、fetchStats/fetchRunningCount/fetchTaskList 全分支
 * （success 真假、catch、showLoading 两侧、filter 有无）、refreshAll、
 * 自动刷新定时器（success×total_active 三态、异常静默、start/stop 两侧）、
 * handleSearch/resetFilters/handlePageChange、handleCancel/handleDelete
 * （confirm 通过、success 真假、message 有无、cancel 静默、异常 detail/兜底）、
 * handleCreateTask（ref 空、校验失败、JSON 非法、params/task_type 有无、success 真假、异常）、
 * statusTagType/statusLabel 全映射与兜底、formatDateTime 三分支、
 * 模板内联事件（刷新/创建任务/查询/重置/取消/删除/创建/取消对话框）、
 * el-switch/el-select/el-input/el-pagination/el-dialog 事件与 v-model，
 * el-table-column 五行样本覆盖进度/消息/操作列 v-if/v-else-if/v-else 三态。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂提升求值，引用对象须先放入 vi.hoisted 初始化
const { ElMessage, confirmMock, tasksApi } = vi.hoisted(() => {
  return {
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
    confirmMock: vi.fn(),
    tasksApi: {
      listTasks: vi.fn(),
      getStats: vi.fn(),
      getTask: vi.fn(),
      createTask: vi.fn(),
      cancelTask: vi.fn(),
      deleteTask: vi.fn(),
      getRunningCount: vi.fn(),
    },
  }
})

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/tasks', () => ({
  tasksApi,
}))

import TaskManager from '@/views/system/TaskManager.vue'

const taskA = {
  task_id: 'TID-abcdefghijklmno',
  task_name: '任务A',
  task_type: 'export',
  status: 'pending',
  progress: 0,
  message: 'M'.repeat(35),
  created_at: '2024-01-01T10:00:00',
  created_by: 'admin',
}

function mountComp() {
  // el-card/el-dialog 需渲染具名插槽；el-table-column 注入五行样本覆盖
  // 进度列 running/progress=100/completed/其他 三态、消息列 长/短/空、操作列 取消/删除、
  // task_id 可选链、task_type 与 created_by 的 || 兜底两侧
  return mount(TaskManager, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
        },
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue', 'closed'],
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /><slot :row="rowD" /><slot :row="rowE" /></div>',
          data() {
            return {
              rowA: { ...taskA },
              rowB: {
                task_id: undefined,
                task_name: '任务B',
                task_type: '',
                status: 'running',
                progress: 50,
                message: '短消息',
                created_at: '2024-01-02T10:00:00',
                created_by: '',
              },
              rowC: {
                task_id: 'TID-C',
                task_name: '任务C',
                task_type: 'import',
                status: 'running',
                progress: 100,
                message: '',
                created_at: '2024-01-03T10:00:00',
                created_by: 'bob',
              },
              rowD: {
                task_id: 'TID-D',
                task_name: '任务D',
                task_type: 'sync',
                status: 'completed',
                progress: 100,
                message: 'done',
                created_at: '2024-01-04T10:00:00',
                created_by: 'admin',
              },
              rowE: {
                task_id: 'TID-E',
                task_name: '任务E',
                task_type: 'sync',
                status: 'failed',
                progress: 30,
                message: '',
                created_at: '2024-01-05T10:00:00',
                created_by: 'alice',
              },
            }
          },
        },
      },
    },
  })
}

const findBtn = (wrapper: any, text: string, exact = false) => {
  const btn = wrapper.findAll('el-button-stub').find((b: any) =>
    exact ? b.text().trim() === text : b.text().includes(text)
  )
  expect(btn, text).toBeTruthy()
  return btn!
}

beforeEach(() => {
  vi.resetAllMocks()
  tasksApi.getStats.mockResolvedValue({
    success: true,
    data: { total: 5, by_status: { completed: 2, failed: 1, cancelled: 1 }, by_type: { export: 3 }, active_count: 1 },
  })
  tasksApi.getRunningCount.mockResolvedValue({
    success: true,
    data: { running: 1, pending: 2, total_active: 3 },
  })
  tasksApi.listTasks.mockResolvedValue({ success: true, data: { items: [taskA], total: 1 } })
  tasksApi.createTask.mockResolvedValue({ success: true, message: '任务已提交' })
  tasksApi.cancelTask.mockResolvedValue({ success: true, message: '已取消' })
  tasksApi.deleteTask.mockResolvedValue({ success: true, message: '已删除' })
  confirmMock.mockResolvedValue('confirm')
})

describe('挂载与数据加载', () => {
  it('onMounted refreshAll：stats/runningCount/taskList 全填充，lastUpdated 与徽标渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(tasksApi.getStats).toHaveBeenCalled()
    expect(tasksApi.getRunningCount).toHaveBeenCalled()
    expect(tasksApi.listTasks).toHaveBeenCalledWith({ page: 1, page_size: 20 })
    expect(vm.stats.total).toBe(5)
    expect(vm.runningCount.running).toBe(1)
    expect(vm.taskList).toHaveLength(1)
    expect(vm.total).toBe(1)
    expect(vm.lastUpdated).not.toBe('')
    expect(vm.loading).toBe(false)
    expect(wrapper.text()).toContain('运行中')
    expect(wrapper.text()).toContain('更新于')
    expect(wrapper.text()).toContain('export: 3')
  })

  it('统计卡片：by_type 缺失时渲染空占位', async () => {
    tasksApi.getStats.mockResolvedValue({
      success: true,
      data: { total: 2, by_status: {}, active_count: 0 },
    })
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.find('.stat-empty').exists()).toBe(true)
    wrapper.unmount()
  })

  it('fetchStats / fetchRunningCount：success=false 不更新；异常静默', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    tasksApi.getStats.mockResolvedValue({ success: false })
    tasksApi.getRunningCount.mockResolvedValue({ success: false })
    await vm.fetchStats()
    await vm.fetchRunningCount()
    expect(vm.stats.total).toBe(5) // 保持旧值
    expect(vm.runningCount.running).toBe(1)
    tasksApi.getStats.mockRejectedValue(new Error('net'))
    tasksApi.getRunningCount.mockRejectedValue(new Error('net'))
    await vm.fetchStats() // 不抛错
    await vm.fetchRunningCount()
  })

  it('fetchTaskList：filter 参数透传、success=false 不更新、异常提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.filterStatus = 'failed'
    vm.filterType = 'export'
    tasksApi.listTasks.mockClear()
    await vm.fetchTaskList()
    expect(tasksApi.listTasks).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
      status: 'failed',
      task_type: 'export',
    })
    expect(vm.loading).toBe(false)

    tasksApi.listTasks.mockResolvedValue({ success: false })
    await vm.fetchTaskList()
    expect(vm.taskList).toHaveLength(1) // 保持旧值

    tasksApi.listTasks.mockRejectedValue(new Error('net'))
    await vm.fetchTaskList()
    expect(ElMessage.error).toHaveBeenCalledWith('获取任务列表失败')
    expect(vm.loading).toBe(false)
  })
})

describe('自动刷新定时器', () => {
  it('toggle/start/stop 全分支：total_active>0 触发静默刷新，其余跳过，异常静默', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vi.useFakeTimers()
    try {
      tasksApi.listTasks.mockClear()

      // 开启 → startAutoRefresh（stop 分支 interval=null）
      vm.toggleAutoRefresh(true)
      tasksApi.getRunningCount.mockResolvedValueOnce({
        success: true,
        data: { running: 2, pending: 1, total_active: 3 },
      })
      await vi.advanceTimersByTimeAsync(5000)
      expect(tasksApi.listTasks).toHaveBeenCalledTimes(1) // fetchTaskList(false)

      // total_active=0 → 不刷新
      tasksApi.getRunningCount.mockResolvedValueOnce({
        success: true,
        data: { running: 0, pending: 0, total_active: 0 },
      })
      await vi.advanceTimersByTimeAsync(5000)
      expect(tasksApi.listTasks).toHaveBeenCalledTimes(1)

      // success=false → 不刷新
      tasksApi.getRunningCount.mockResolvedValueOnce({ success: false })
      await vi.advanceTimersByTimeAsync(5000)
      expect(tasksApi.listTasks).toHaveBeenCalledTimes(1)

      // 异常 → 静默
      tasksApi.getRunningCount.mockRejectedValueOnce(new Error('net'))
      await vi.advanceTimersByTimeAsync(5000)
      expect(tasksApi.listTasks).toHaveBeenCalledTimes(1)

      // 再次开启 → stopAutoRefresh 的 interval 非空分支
      vm.toggleAutoRefresh(false)
      vm.toggleAutoRefresh(true)
      // 卸载时 stopAutoRefresh 清理 interval
      wrapper.unmount()
    } finally {
      vi.useRealTimers()
    }
  })

  it('el-switch：change 事件触发 toggleAutoRefresh，v-model 同步 autoRefresh', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vi.useFakeTimers()
    try {
      const sw = wrapper.findAllComponents({ name: 'ElSwitch' })
      expect(sw.length).toBe(1)
      sw[0].vm.$emit('update:modelValue', true)
      expect(vm.autoRefresh).toBe(true)
      sw[0].vm.$emit('change', true)
      sw[0].vm.$emit('change', false)
      sw[0].vm.$emit('change', 0) // falsy → stop 分支
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('查询、重置与分页', () => {
  it('handleSearch 重置页码并查询；resetFilters 清空条件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.page = 3
    vm.filterStatus = 'running'
    vm.filterType = 'sync'
    tasksApi.listTasks.mockClear()
    vm.handleSearch()
    expect(vm.page).toBe(1)
    await flushPromises()
    expect(tasksApi.listTasks).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
      status: 'running',
      task_type: 'sync',
    })

    vm.resetFilters()
    expect(vm.filterStatus).toBe('')
    expect(vm.filterType).toBe('')
    await flushPromises()
    expect(tasksApi.listTasks).toHaveBeenCalledWith({ page: 1, page_size: 20 })
  })

  it('handlePageChange 触发列表刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    tasksApi.listTasks.mockClear()
    vm.handlePageChange()
    await flushPromises()
    expect(tasksApi.listTasks).toHaveBeenCalled()
  })

  it('点击「刷新」「查询」「重置」按钮与筛选控件事件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    tasksApi.getStats.mockClear()
    await findBtn(wrapper, '刷新').trigger('click')
    await flushPromises()
    expect(tasksApi.getStats).toHaveBeenCalled()

    tasksApi.listTasks.mockClear()
    await findBtn(wrapper, '查询').trigger('click')
    await flushPromises()
    expect(tasksApi.listTasks).toHaveBeenCalled()

    vm.filterStatus = 'failed'
    await findBtn(wrapper, '重置').trigger('click')
    expect(vm.filterStatus).toBe('')

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 'pending')
    expect(vm.filterStatus).toBe('pending')
    tasksApi.listTasks.mockClear()
    selects[0].vm.$emit('change', 'pending')
    await flushPromises()
    expect(tasksApi.listTasks).toHaveBeenCalled()

    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    expect(inputs.length).toBe(4) // 筛选 1 + 对话框 3
    inputs[0].vm.$emit('update:modelValue', 'export')
    expect(vm.filterType).toBe('export')
    tasksApi.listTasks.mockClear()
    inputs[0].vm.$emit('clear')
    await flushPromises()
    expect(tasksApi.listTasks).toHaveBeenCalled()
    inputs[0].vm.$emit('keyup', { key: 'Enter' })
    await flushPromises()

    const pager = wrapper.findAllComponents({ name: 'ElPagination' })
    pager[0].vm.$emit('size-change', 50)
    pager[0].vm.$emit('current-change', 2)
    await flushPromises()
    pager[0].vm.$emit('update:current-page', 3)
    pager[0].vm.$emit('update:page-size', 100)
    expect(vm.page).toBe(3)
    expect(vm.pageSize).toBe(100)
  })
})

describe('取消与删除任务', () => {
  it('handleCancel：confirm 通过 + success → 提示并刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.page = 2
    await vm.handleCancel(taskA as any)
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('任务A'),
      '确认取消',
      expect.any(Object)
    )
    expect(tasksApi.cancelTask).toHaveBeenCalledWith('TID-abcdefghijklmno')
    expect(ElMessage.success).toHaveBeenCalledWith('已取消')
    expect(vm.page).toBe(1)
  })

  it('handleCancel：success=false 时 message 有无两侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    tasksApi.cancelTask.mockResolvedValue({ success: false, message: '任务已在运行' })
    await vm.handleCancel(taskA as any)
    expect(ElMessage.error).toHaveBeenCalledWith('任务已在运行')
    tasksApi.cancelTask.mockResolvedValue({ success: false })
    await vm.handleCancel(taskA as any)
    expect(ElMessage.error).toHaveBeenCalledWith('取消失败')
  })

  it('handleCancel：cancel 静默（两种形态）与异常兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleCancel(taskA as any)
    expect(tasksApi.cancelTask).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()

    confirmMock.mockRejectedValueOnce({ message: 'cancel' })
    await vm.handleCancel(taskA as any)
    expect(ElMessage.error).not.toHaveBeenCalled()

    confirmMock.mockRejectedValueOnce(new Error('网络中断'))
    await vm.handleCancel(taskA as any)
    expect(ElMessage.error).toHaveBeenCalledWith('网络中断')

    confirmMock.mockRejectedValueOnce({})
    await vm.handleCancel(taskA as any)
    expect(ElMessage.error).toHaveBeenCalledWith('取消操作失败')
  })

  it('handleDelete：confirm 通过 + success / success=false message 有无', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete(taskA as any)
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('不可恢复'),
      '确认删除',
      expect.any(Object)
    )
    expect(tasksApi.deleteTask).toHaveBeenCalledWith('TID-abcdefghijklmno')
    expect(ElMessage.success).toHaveBeenCalledWith('已删除')
    expect(vm.page).toBe(1)

    tasksApi.deleteTask.mockResolvedValue({ success: false, message: '任务运行中' })
    await vm.handleDelete(taskA as any)
    expect(ElMessage.error).toHaveBeenCalledWith('任务运行中')
    tasksApi.deleteTask.mockResolvedValue({ success: false })
    await vm.handleDelete(taskA as any)
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })

  it('handleDelete：cancel 静默与异常 message/兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleDelete(taskA as any)
    expect(tasksApi.deleteTask).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()

    confirmMock.mockRejectedValueOnce({ message: 'cancel' })
    await vm.handleDelete(taskA as any)
    expect(ElMessage.error).not.toHaveBeenCalled()

    confirmMock.mockRejectedValueOnce(new Error('db 锁定'))
    await vm.handleDelete(taskA as any)
    expect(ElMessage.error).toHaveBeenCalledWith('db 锁定')

    confirmMock.mockRejectedValueOnce({})
    await vm.handleDelete(taskA as any)
    expect(ElMessage.error).toHaveBeenCalledWith('删除操作失败')
  })

  it('表格操作列：点击「取消」「删除」按钮（样本行）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const cancelBtns = wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '取消')
    const deleteBtns = wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '删除')
    // 3 个行内取消（pending/running×2）+ 1 个对话框页脚取消；2 个删除
    expect(cancelBtns.length).toBe(4)
    expect(deleteBtns.length).toBe(2)
    await cancelBtns[0].trigger('click')
    await flushPromises()
    expect(tasksApi.cancelTask).toHaveBeenCalledWith('TID-abcdefghijklmno')
    await deleteBtns[0].trigger('click')
    await flushPromises()
    expect(tasksApi.deleteTask).toHaveBeenCalledWith('TID-D')
  })
})

describe('创建任务', () => {
  it('createFormRef 为空或校验失败 → 早退', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.createFormRef = undefined
    await vm.handleCreateTask()
    expect(tasksApi.createTask).not.toHaveBeenCalled()

    vm.createFormRef = { validate: vi.fn().mockRejectedValue(new Error('invalid')) }
    await vm.handleCreateTask()
    expect(tasksApi.createTask).not.toHaveBeenCalled()
  })

  it('参数 JSON 非法 → 报错并复位 createLoading', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.createForm.task_name = 'T'
    vm.createForm.params = '{bad json'
    vm.createFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleCreateTask()
    expect(ElMessage.error).toHaveBeenCalledWith('参数格式错误，请输入有效的JSON')
    expect(vm.createLoading).toBe(false)
    expect(tasksApi.createTask).not.toHaveBeenCalled()
  })

  it('成功：params 解析、task_type 有无两侧、关闭对话框并刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.showCreateDialog = true
    vm.createForm.task_name = '导出任务'
    vm.createForm.task_type = 'export'
    vm.createForm.params = '{"key": "value"}'
    vm.createFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleCreateTask()
    expect(tasksApi.createTask).toHaveBeenCalledWith({
      task_name: '导出任务',
      task_type: 'export',
      params: { key: 'value' },
    })
    expect(ElMessage.success).toHaveBeenCalledWith('任务已提交')
    expect(vm.showCreateDialog).toBe(false)
    expect(vm.page).toBe(1)
    expect(vm.createLoading).toBe(false)

    // params 留空 + task_type 留空 → undefined 透传；message 缺失 → 兜底
    tasksApi.createTask.mockResolvedValue({ success: true })
    vm.createForm.params = '   '
    vm.createForm.task_type = ''
    vm.createFormRef = { validate: vi.fn().mockResolvedValue(true) } // 重渲染后重赋
    await vm.handleCreateTask()
    expect(tasksApi.createTask).toHaveBeenCalledWith({
      task_name: '导出任务',
      task_type: undefined,
      params: undefined,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('任务创建成功')
  })

  it('success=false（message 有无）与异常分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    tasksApi.createTask.mockResolvedValue({ success: false, message: '类型不支持' })
    vm.createFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleCreateTask()
    expect(ElMessage.error).toHaveBeenCalledWith('类型不支持')

    tasksApi.createTask.mockResolvedValue({ success: false })
    vm.createFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleCreateTask()
    expect(ElMessage.error).toHaveBeenCalledWith('创建失败')

    tasksApi.createTask.mockRejectedValue(new Error('net'))
    vm.createFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleCreateTask()
    expect(ElMessage.error).toHaveBeenCalledWith('创建任务失败')
    expect(vm.createLoading).toBe(false)
  })

  it('resetCreateForm：ref 有/无 resetFields 两侧；对话框 @closed 触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.createForm.task_name = 'X'
    vm.createForm.task_type = 'Y'
    vm.createForm.params = 'Z'
    const resetFields = vi.fn()
    vm.createFormRef = { resetFields }
    vm.resetCreateForm()
    expect(resetFields).toHaveBeenCalled()
    expect(vm.createForm).toMatchObject({ task_name: '', task_type: '', params: '' })

    vm.createFormRef = undefined
    vm.resetCreateForm() // 不抛错

    // 对话框 @closed → resetCreateForm
    vm.createForm.task_name = 'W'
    vm.createFormRef = { resetFields }
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    dialogs[0].vm.$emit('closed')
    expect(vm.createForm.task_name).toBe('')
  })

  it('对话框模板交互：创建任务按钮、el-input v-model、页脚取消/创建、v-model', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await findBtn(wrapper, '创建任务').trigger('click')
    expect(vm.showCreateDialog).toBe(true)
    await nextTick()

    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    inputs[1].vm.$emit('update:modelValue', '新任务')
    inputs[2].vm.$emit('update:modelValue', 'sync')
    inputs[3].vm.$emit('update:modelValue', '{"a":1}')
    expect(vm.createForm).toMatchObject({
      task_name: '新任务',
      task_type: 'sync',
      params: '{"a":1}',
    })

    // 重渲染会把模板 ref 重同步为 stub，提交前重新赋 mock
    vm.createFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await findBtn(wrapper, '创建', true).trigger('click')
    await flushPromises()
    expect(tasksApi.createTask).toHaveBeenCalledWith({
      task_name: '新任务',
      task_type: 'sync',
      params: { a: 1 },
    })
    expect(vm.showCreateDialog).toBe(false)

    // 页脚「取消」（操作列也有取消按钮，取最后一个精确匹配）
    vm.showCreateDialog = true
    await nextTick()
    const cancels = wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '取消')
    await cancels[cancels.length - 1].trigger('click')
    expect(vm.showCreateDialog).toBe(false)

    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    dialogs[0].vm.$emit('update:modelValue', true)
    expect(vm.showCreateDialog).toBe(true)
  })
})

describe('工具函数', () => {
  it('statusTagType / statusLabel 全映射与未知兜底', () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.statusTagType('pending')).toBe('info')
    expect(vm.statusTagType('running')).toBe('info') // map 值为 undefined → || 兜底
    expect(vm.statusTagType('completed')).toBe('success')
    expect(vm.statusTagType('failed')).toBe('danger')
    expect(vm.statusTagType('cancelled')).toBe('warning')
    expect(vm.statusTagType('weird')).toBe('info')
    expect(vm.statusLabel('pending')).toBe('等待中')
    expect(vm.statusLabel('running')).toBe('运行中')
    expect(vm.statusLabel('completed')).toBe('已完成')
    expect(vm.statusLabel('failed')).toBe('失败')
    expect(vm.statusLabel('cancelled')).toBe('已取消')
    expect(vm.statusLabel('weird')).toBe('weird')
  })

  it('formatDateTime：空值/非法日期 → --；合法日期 → 本地化；toLocaleString 抛错 → 兜底', () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.formatDateTime('')).toBe('--')
    // 2026-10-03 收敛：非法值统一走兜底 '--'（不再回显原串）
    expect(vm.formatDateTime('not-a-date')).toBe('--')
    const out = vm.formatDateTime('2024-01-01T10:00:00')
    expect(out).toContain('2024')

    // toLocaleString 抛错 → 统一实现内部 catch，回退兜底文案（渲染期不抛错）
    const orig = Date.prototype.toLocaleString
    Date.prototype.toLocaleString = () => {
      throw new Error('boom')
    }
    try {
      expect(vm.formatDateTime('2024-06-01T08:00:00')).toBe('--')
    } finally {
      Date.prototype.toLocaleString = orig
    }
  })

  it('表格列模板渲染：task_id 可选链、类型/创建人兜底、进度三态、消息长/短/空', () => {
    const wrapper = mountComp()
    const text = wrapper.text()
    expect(text).toContain('...')
    expect(text).toContain('--')
    // 操作列按钮由样本行渲染（在取消/删除用例中断言），此处确认长消息截断
    expect(wrapper.html()).toContain('MMMM')
  })


  it('listTasks: res.data 为空时兜底空数组', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    tasksApi.listTasks.mockResolvedValue({ success: true, data: null })
    await vm.fetchTaskList()
    expect(vm.taskList).toEqual([])
    expect(vm.total).toBe(0)
    wrapper.unmount()
  })
})
