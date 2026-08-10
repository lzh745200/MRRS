/**
 * views/projects/Detail.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 并行加载 5 路数据（成功/失败）、错误态重试、
 * computed（statusType/statusText/progressColor/任务进度/状态分布）、
 * 任务 CRUD（新建/编辑/校验/删除）、附件上传/下载/删除、
 * formatSize/taskStatusType/priorityType、模板分支与 v-model。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { ElMessage, projectsApiMock, logError, pushSafeMock, routeBox } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  projectsApiMock: {
    get: vi.fn(),
    getTasks: vi.fn(),
    getFunds: vi.fn(),
    listFiles: vi.fn(),
    getChangeHistory: vi.fn(),
    createTask: vi.fn(),
    updateTask: vi.fn(),
    deleteTask: vi.fn(),
    uploadFiles: vi.fn(),
    getFileDownloadUrl: vi.fn(),
    deleteFile: vi.fn(),
  },
  logError: vi.fn(),
  pushSafeMock: vi.fn(),
  routeBox: { params: { id: '7' } as Record<string, any> },
}))

vi.mock('vue-router', () => ({ useRoute: () => routeBox }))

vi.mock('element-plus', () => ({ ElMessage, ElMessageBox: { confirm: vi.fn() } }))

vi.mock('@/api/projects', () => ({ projectsApi: projectsApiMock }))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
  safeRouteParam: (v: any) => Number(v) || v,
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import Detail from '@/views/projects/Detail.vue'

const project = {
  id: 7,
  name: '产业路项目',
  code: 'XM-007',
  type: 'infrastructure',
  status: 'in_progress',
  progress: 60,
  budget: 200,
  responsible_unit: '镇府',
  village: '村A',
  start_date: '2024-01-01',
  end_date: '2024-12-31',
  created_at: '2023-12-01',
  description: '项目描述',
}

const taskCompleted = { id: 1, title: '完成的任务', status: 'completed', priority: 'high', assignee: '张三', due_date: '2024-06-01' }
const taskPending = { id: 2, title: '待处理任务', status: 'pending', priority: 'low', assignee: '李四' }
const taskProgress = { id: 3, title: '进行中任务', status: 'in_progress', priority: 'urgent', assignee: '王五', due_date: '' }

const fund = { id: 1, name: '项目经费', amount: 100, status: 'approved', type: 'project' }

const file = { id: 1, filename: '报告.pdf', name: '报告.pdf', category: 'attachment', size: 2048, created_at: '2024-01-02T00:00:00' }
const fileNoFilename = { id: 2, name: '附图.png', category: 'other', size: 0, created_at: '' }

const historyItem = { changed_at: '2024-01-03', field: '预算', old_value: '100', new_value: '200', changed_by: '赵六' }
const historyItem2 = { changed_at: '2024-01-04', field: '状态', old_value: null, new_value: null, changed_by: '' }

const fetchMock = vi.hoisted(() => vi.fn())

function mountComp() {
  return mount(Detail, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-skeleton': { template: '<div class="el-skeleton-stub" />' },
        'el-result': { template: '<div class="el-result-stub"><slot name="extra" /></div>' },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-progress': { template: '<div class="el-progress-stub" />' },
        'el-tabs': {
          template:
            '<div class="el-tabs-stub" @click="$emit(\'update:modelValue\', \'tasks\')"><slot /></div>',
        },
        'el-tab-pane': { template: '<div class="el-tab-pane-stub"><slot /></div>' },
        'el-descriptions': { template: '<div class="el-descriptions-stub"><slot /></div>' },
        'el-descriptions-item': { template: '<div class="el-desc-item-stub"><slot /></div>' },
        'el-table': {
          template:
            '<div class="el-table-stub"><slot name="empty" /><slot name="default" /></div>',
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /><slot :row="rowD" /></div>',
          data() {
            return {
              rowA: { ...taskCompleted },
              rowB: { ...taskPending },
              rowC: { ...taskProgress },
              rowD: { id: 9, title: '缺字段任务', status: undefined, priority: undefined, amount: null },
            }
          },
        },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-icon': { template: '<span class="el-icon-stub"><slot /></span>' },
        'el-upload': {
          template:
            '<div class="el-upload-stub" @click="beforeUpload && beforeUpload()"><slot /></div>',
          props: ['beforeUpload'],
        },
        'el-popconfirm': {
          template:
            '<div class="el-popconfirm-stub" @click="$emit(\'confirm\', rowA)"><slot name="reference" /></div>',
        },
        'el-empty': {
          template: '<div class="el-empty-stub">{{ description }}<slot /></div>',
          props: ['description'],
        },
        'el-timeline': { template: '<div class="el-timeline-stub"><slot /></div>' },
        'el-timeline-item': { template: '<div class="el-timeline-item-stub"><slot /></div>' },
        'el-card': { template: '<div class="el-card-stub"><slot /></div>' },
        'el-form': { template: '<div class="el-form-stub"><slot /></div>' },
        'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
        'el-input': {
          template:
            '<div class="el-input-stub" @click="$emit(\'update:modelValue\', \'V\')" />',
        },
        'el-select': {
          template:
            '<div class="el-select-stub" @click="$emit(\'update:modelValue\', \'x\')"><slot /></div>',
        },
        'el-option': { template: '<div class="el-option-stub" />' },
        'el-date-picker': {
          template:
            '<div class="el-date-picker-stub" @click="$emit(\'update:modelValue\', \'2024-01-01\')" />',
        },
        'el-dialog': {
          template:
            '<div class="el-dialog-stub" @click="$emit(\'update:modelValue\', false)"><slot /><slot name="footer" /></div>',
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  routeBox.params = { id: '7' }
  projectsApiMock.get.mockResolvedValue(project)
  projectsApiMock.getTasks.mockResolvedValue({ items: [taskCompleted, taskPending, taskProgress] })
  projectsApiMock.getFunds.mockResolvedValue({ items: [fund] })
  projectsApiMock.listFiles.mockResolvedValue({ items: [file, fileNoFilename] })
  projectsApiMock.getChangeHistory.mockResolvedValue({ items: [historyItem, historyItem2] })
  projectsApiMock.createTask.mockResolvedValue({})
  projectsApiMock.updateTask.mockResolvedValue({})
  projectsApiMock.deleteTask.mockResolvedValue({})
  projectsApiMock.uploadFiles.mockResolvedValue({})
  projectsApiMock.deleteFile.mockResolvedValue({})
  projectsApiMock.getFileDownloadUrl.mockReturnValue('/api/v1/projects/7/files/1/download')
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockResolvedValue({ ok: true, blob: vi.fn().mockResolvedValue(new Blob(['x'])) })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('挂载与加载', () => {
  it('onMounted 并行加载 5 路数据', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(projectsApiMock.get).toHaveBeenCalledWith(7)
    expect(projectsApiMock.getTasks).toHaveBeenCalledWith(7)
    expect(projectsApiMock.getFunds).toHaveBeenCalledWith(7)
    expect(projectsApiMock.listFiles).toHaveBeenCalledWith(7)
    expect(projectsApiMock.getChangeHistory).toHaveBeenCalledWith(7)
    expect(vm.project).toEqual(project)
    expect(vm.tasks).toHaveLength(3)
    expect(vm.funds).toHaveLength(1)
    expect(vm.files).toHaveLength(2)
    expect(vm.history).toHaveLength(2)
    expect(vm.loading).toBe(false)
  })

  it('loadProject 失败 → error 状态', async () => {
    projectsApiMock.get.mockRejectedValue(new Error('boom'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(logError).toHaveBeenCalled()
    expect(vm.error).toBe('boom')
    expect(vm.loading).toBe(false)
  })

  it('loadProject 失败无 message → 兜底文案', async () => {
    projectsApiMock.get.mockRejectedValue({})
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).error).toBe('项目详情加载失败，请重试')
  })

  it('重新加载按钮 → loadProject；错误态返回列表', async () => {
    projectsApiMock.get.mockRejectedValueOnce(new Error('x')).mockResolvedValueOnce(project)
    const wrapper = mountComp()
    await flushPromises()
    projectsApiMock.get.mockClear()
    pushSafeMock.mockClear()
    const btns = wrapper.findAll('.el-button-stub')
    const retry = btns.find((b) => b.text().includes('重新加载'))
    await retry!.trigger('click')
    await flushPromises()
    expect(projectsApiMock.get).toHaveBeenCalled()
    expect((wrapper.vm as any).error).toBe('')

    // 再次进入错误态并点击返回列表
    projectsApiMock.get.mockRejectedValueOnce(new Error('x'))
    await (wrapper.vm as any).loadProject()
    await flushPromises()
    const back = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('返回列表'))
    await back!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/projects')
  })

  it('子数据加载失败 → logger 不阻塞', async () => {
    projectsApiMock.getTasks.mockRejectedValue(new Error('tasks'))
    projectsApiMock.getFunds.mockRejectedValue(new Error('funds'))
    projectsApiMock.listFiles.mockRejectedValue(new Error('files'))
    projectsApiMock.getChangeHistory.mockRejectedValue(new Error('history'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect((wrapper.vm as any).tasksLoading).toBe(false)
    expect((wrapper.vm as any).fundsLoading).toBe(false)
    expect((wrapper.vm as any).filesLoading).toBe(false)
    expect((wrapper.vm as any).historyLoading).toBe(false)
  })

  it('子数据直返数组格式', async () => {
    projectsApiMock.getTasks.mockResolvedValue([taskCompleted])
    projectsApiMock.getFunds.mockResolvedValue([fund])
    projectsApiMock.listFiles.mockResolvedValue([file])
    projectsApiMock.getChangeHistory.mockResolvedValue([historyItem])
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.tasks).toHaveLength(1)
    expect(vm.funds).toHaveLength(1)
    expect(vm.files).toHaveLength(1)
    expect(vm.history).toHaveLength(1)
  })

  it('子数据返回 null → 空数组兜底', async () => {
    projectsApiMock.getTasks.mockResolvedValue(null)
    projectsApiMock.getFunds.mockResolvedValue(null)
    projectsApiMock.listFiles.mockResolvedValue(null)
    projectsApiMock.getChangeHistory.mockResolvedValue(null)
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.tasks).toEqual([])
    expect(vm.funds).toEqual([])
    expect(vm.files).toEqual([])
    expect(vm.history).toEqual([])
  })

  it('导航按钮：编辑/返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btns = wrapper.findAll('.el-button-stub')
    const edit = btns.find((b) => b.text().includes('编辑'))
    await edit!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/projects/7/edit')
    const back = btns.find((b) => b.text().includes('返回'))
    await back!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/projects')
  })
})

describe('computed 计算属性', () => {
  it('statusType/statusText 映射与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.statusType).toBe('warning')
    expect(vm.statusText).toBe('进行中')
    vm.project = { status: 'unknown' }
    await nextTick()
    expect(vm.statusType).toBe('info')
    expect(vm.statusText).toBe('unknown')
  })

  it('progressColor 三分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.project = { progress: 90 }
    await nextTick()
    expect(vm.progressColor).toBe('#40916c')
    vm.project = { progress: 60 }
    await nextTick()
    expect(vm.progressColor).toBe('#e6a23c')
    vm.project = { progress: 20 }
    await nextTick()
    expect(vm.progressColor).toBe('#f56c6c')
    vm.project = {}
    await nextTick()
    expect(vm.progressColor).toBe('#f56c6c')
  })

  it('任务进度计算', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.taskTotal).toBe(3)
    expect(vm.taskCompleted).toBe(1)
    expect(vm.taskProgressPercent).toBe(33)
    expect(vm.taskProgressColor).toBe('#f56c6c')
    expect(vm.taskStatusCounts).toEqual({ pending: 1, in_progress: 1, completed: 1 })

    vm.tasks = []
    await nextTick()
    expect(vm.taskProgressPercent).toBe(0)
    expect(vm.taskProgressColor).toBe('#f56c6c')

    vm.tasks = [{ status: 'completed' }, { status: 'completed' }]
    await nextTick()
    expect(vm.taskProgressPercent).toBe(100)
    expect(vm.taskProgressColor).toBe('#40916c')

    vm.tasks = [{ status: 'completed' }, { status: 'pending' }]
    await nextTick()
    expect(vm.taskProgressPercent).toBe(50)
    expect(vm.taskProgressColor).toBe('#e6a23c')
  })

  it('taskStatusType/priorityType 全映射与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.taskStatusType('pending')).toBe('info')
    expect(vm.taskStatusType('in_progress')).toBe('warning')
    expect(vm.taskStatusType('completed')).toBe('success')
    expect(vm.taskStatusType('x')).toBe('info')
    expect(vm.priorityType('low')).toBe('info')
    expect(vm.priorityType('normal')).toBe('')
    expect(vm.priorityType('high')).toBe('warning')
    expect(vm.priorityType('urgent')).toBe('danger')
    expect(vm.priorityType('x')).toBe('info')
  })

  it('formatSize 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatSize(null)).toBe('-')
    expect(vm.formatSize(undefined)).toBe('-')
    expect(vm.formatSize(500)).toBe('500 B')
    expect(vm.formatSize(2048)).toBe('2.0 KB')
    expect(vm.formatSize(2 * 1048576)).toBe('2.0 MB')
  })
})

describe('任务 CRUD', () => {
  it('openTaskDialog 新建/编辑', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openTaskDialog()
    expect(vm.editingTask).toBeNull()
    expect(vm.taskForm.title).toBe('')
    expect(vm.taskDialogVisible).toBe(true)

    vm.openTaskDialog(taskPending)
    expect(vm.editingTask).toEqual(taskPending)
    expect(vm.taskForm.assignee).toBe('李四')
    expect(vm.taskForm.due_date).toBe('')
  })

  it('保存任务：空标题 → warning', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleSaveTask()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入任务名称')
  })

  it('保存任务：更新成功', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openTaskDialog(taskPending)
    vm.taskForm.title = '新标题'
    projectsApiMock.getTasks.mockClear()
    await vm.handleSaveTask()
    expect(projectsApiMock.updateTask).toHaveBeenCalledWith(7, 2, expect.objectContaining({ name: vm.taskForm.title.trim() }))
    expect(ElMessage.success).toHaveBeenCalledWith('任务已更新')
    expect(vm.taskDialogVisible).toBe(false)
    expect(projectsApiMock.getTasks).toHaveBeenCalled()
  })

  it('保存任务：创建成功', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.taskForm.title = '新任务'
    projectsApiMock.getTasks.mockClear()
    await vm.handleSaveTask()
    expect(projectsApiMock.createTask).toHaveBeenCalledWith(7, expect.objectContaining({ name: vm.taskForm.title.trim() }))
    expect(ElMessage.success).toHaveBeenCalledWith('任务已创建')
  })

  it('保存任务：失败 → logger + 提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.taskForm.title = '新任务'
    projectsApiMock.createTask.mockRejectedValue(new Error('保存任务失败'))
    await vm.handleSaveTask()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('保存任务失败')
    expect(vm.taskSaving).toBe(false)

    projectsApiMock.createTask.mockRejectedValueOnce({})
    await vm.handleSaveTask()
    expect(ElMessage.error).toHaveBeenCalledWith('保存任务失败')
  })

  it('删除任务：成功/失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    projectsApiMock.getTasks.mockClear()
    await vm.handleDeleteTask(1)
    expect(projectsApiMock.deleteTask).toHaveBeenCalledWith(7, 1)
    expect(ElMessage.success).toHaveBeenCalledWith('任务已删除')
    expect(projectsApiMock.getTasks).toHaveBeenCalled()

    projectsApiMock.deleteTask.mockRejectedValueOnce(new Error('删除任务失败'))
    await vm.handleDeleteTask(1)
    expect(ElMessage.error).toHaveBeenCalledWith('删除任务失败')

    projectsApiMock.deleteTask.mockRejectedValueOnce({})
    await vm.handleDeleteTask(1)
    expect(ElMessage.error).toHaveBeenCalledWith('删除任务失败')
  })

  it('新建任务/编辑按钮 + 删除 popconfirm', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const create = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('新建任务'))
    await create!.trigger('click')
    expect(vm.taskDialogVisible).toBe(true)
    vm.taskDialogVisible = false
    // 任务表格中的编辑按钮（最后一个编辑按钮；第一个是页头编辑）
    const editBtns = wrapper.findAll('.el-button-stub').filter((b) => b.text().includes('编辑'))
    await editBtns[editBtns.length - 1].trigger('click')
    expect(vm.taskDialogVisible).toBe(true)

    projectsApiMock.getTasks.mockClear()
    await wrapper.find('.el-popconfirm-stub').trigger('click')
    await flushPromises()
    expect(projectsApiMock.deleteTask).toHaveBeenCalled()
  })

  it('任务表单 v-model 更新 + 保存/取消按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.taskForm.title = 'T'
    for (const el of wrapper.findAll('.el-input-stub')) {
      await el.trigger('click')
    }
    for (const sel of wrapper.findAll('.el-select-stub')) {
      await sel.trigger('click')
    }
    await wrapper.find('.el-date-picker-stub').trigger('click')
    await flushPromises()
    expect(vm.taskForm.title).toBe('V')
    expect(vm.taskForm.status).toBe('x')
    expect(vm.taskForm.priority).toBe('x')
    expect(vm.taskForm.assignee).toBe('V')
    expect(vm.taskForm.due_date).toBe('2024-01-01')

    projectsApiMock.getTasks.mockClear()
    const save = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('保存'))
    await save!.trigger('click')
    await flushPromises()
    expect(projectsApiMock.createTask).toHaveBeenCalled()

    vm.taskDialogVisible = true
    const cancel = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('取消'))
    await cancel!.trigger('click')
    expect(vm.taskDialogVisible).toBe(false)
  })
})

describe('附件操作', () => {
  it('上传附件成功/失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    projectsApiMock.listFiles.mockClear()
    await vm.handleFileUpload({ file: new File(['x'], 'a.pdf') })
    expect(projectsApiMock.uploadFiles).toHaveBeenCalledWith(7, 'attachment', expect.any(Array))
    expect(ElMessage.success).toHaveBeenCalledWith('上传成功')
    expect(projectsApiMock.listFiles).toHaveBeenCalled()

    projectsApiMock.uploadFiles.mockRejectedValueOnce(new Error('上传失败'))
    await vm.handleFileUpload({ file: {} })
    expect(ElMessage.error).toHaveBeenCalledWith('上传失败')

    projectsApiMock.uploadFiles.mockRejectedValueOnce({})
    await vm.handleFileUpload({ file: {} })
    expect(ElMessage.error).toHaveBeenCalledWith('上传失败')
  })

  it('下载附件成功', async () => {
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleDownload(file)
    expect(fetchMock).toHaveBeenCalled()
    clickSpy.mockRestore()
  })

  it('下载附件失败 → 提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    fetchMock.mockRejectedValue(new Error('下载失败'))
    await (wrapper.vm as any).handleDownload(file)
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('下载失败')

    fetchMock.mockRejectedValueOnce({})
    await (wrapper.vm as any).handleDownload(file)
    expect(ElMessage.error).toHaveBeenCalledWith('下载失败')
  })

  it('下载附件响应非 ok → 失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    fetchMock.mockResolvedValue({ ok: false })
    await (wrapper.vm as any).handleDownload(file)
    expect(ElMessage.error).toHaveBeenCalledWith('Download failed')
  })

  it('删除附件成功/失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    projectsApiMock.listFiles.mockClear()
    await vm.handleDeleteFile(1)
    expect(projectsApiMock.deleteFile).toHaveBeenCalledWith(7, 1)
    expect(ElMessage.success).toHaveBeenCalledWith('附件已删除')
    expect(projectsApiMock.listFiles).toHaveBeenCalled()

    projectsApiMock.deleteFile.mockRejectedValueOnce(new Error('删除附件失败'))
    await vm.handleDeleteFile(1)
    expect(ElMessage.error).toHaveBeenCalledWith('删除附件失败')

    projectsApiMock.deleteFile.mockRejectedValueOnce({})
    await vm.handleDeleteFile(1)
    expect(ElMessage.error).toHaveBeenCalledWith('删除附件失败')
  })

  it('下载/删除附件按钮', async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    const dl = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('下载'))
    await dl!.trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalled()

    projectsApiMock.deleteFile.mockClear()
    const delBtns = wrapper.findAll('.el-button-stub').filter((b) => b.text().includes('删除'))
    for (const d of delBtns) {
      await d.trigger('click')
    }
    await flushPromises()
    expect(projectsApiMock.deleteFile).toHaveBeenCalled()
    clickSpy.mockRestore()
  })
})

describe('模板渲染', () => {
  it('tab 切换', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const tabs = wrapper.find('.el-tabs-stub')
    expect(tabs.exists()).toBe(true)
    await tabs.trigger('click')
    await nextTick()
    expect((wrapper.vm as any).activeTab).toBe('tasks')
  })

  it('上传控件 before-upload 调用', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.el-upload-stub').trigger('click')
  })

  it('空态渲染：无历史记录', async () => {
    projectsApiMock.getChangeHistory.mockResolvedValue({ items: [] })
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.text()).toContain('暂无变更记录')
  })

  it('加载态渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    wrapper.vm.loading = true
    await nextTick()
    expect(wrapper.find('.el-skeleton-stub').exists()).toBe(true)
  })
})

describe('任务字段分支', () => {
  it('task.name 优先 / reject 带 detail', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    projectsApiMock.getTasks.mockClear()
    projectsApiMock.createTask.mockRejectedValue({ response: { data: { detail: '任务超限' } } })
    vm.taskForm.title = '新任务'
    await vm.handleSaveTask().catch(() => {})
    expect(ElMessage.error).toHaveBeenCalledWith('任务超限')
    wrapper.unmount()
  })
})

describe('任务名优先分支', () => {
  it('task.name 优先于 title', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openTaskDialog({ id: 1, name: '指定名', title: '标题' })
    expect(vm.taskForm.title).toBe('指定名')
    wrapper.unmount()
  })
})
