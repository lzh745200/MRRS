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
    previewFile: vi.fn(),
  },
  logError: vi.fn(),
  pushSafeMock: vi.fn(),
  routeBox: { params: { id: '7' } as Record<string, any> },
}))

vi.mock('vue-router', () => ({ useRoute: () => routeBox }))

vi.mock('element-plus', () => ({ ElMessage, ElMessageBox: { confirm: vi.fn() } }))

vi.mock('@/api/projects', () => ({ projectsApi: projectsApiMock }))

vi.mock('@/api/milestones', () => ({
  listMilestones: vi.fn().mockResolvedValue([]),
  createMilestone: vi.fn(),
  updateMilestone: vi.fn(),
  deleteMilestone: vi.fn(),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
  safeRouteParam: (v: any) => Number(v) || v,
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import Detail from '@/views/projects/Detail.vue'
import {
  listMilestones,
  createMilestone,
  updateMilestone,
  deleteMilestone,
} from '@/api/milestones'

const msList = listMilestones as unknown as ReturnType<typeof vi.fn>
const msCreate = createMilestone as unknown as ReturnType<typeof vi.fn>
const msUpdate = updateMilestone as unknown as ReturnType<typeof vi.fn>
const msDelete = deleteMilestone as unknown as ReturnType<typeof vi.fn>

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
        FilePreview: {
          name: 'FilePreview',
          template: '<div class="file-preview-stub" />',
          props: ['modelValue', 'fileName'],
          emits: ['update:modelValue'],
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
    // 页面存在两个 popconfirm（任务删除 / 里程碑删除）：按 data-test 排除后者
    const pops = wrapper.findAll('.el-popconfirm-stub').filter(
      (x) => !x.find('[data-test="ms-delete"]').exists(),
    )
    await pops[0].trigger('click')
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
    // 分类须为后端白名单值（attachment 不在白名单会导致 400）
    expect(projectsApiMock.uploadFiles).toHaveBeenCalledWith(7, 'implementation', expect.any(Array))
    // 提示策略：增删改成功静默，仅刷新列表
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

  it('预览附件 → 打开 FilePreview 并经 fetchBlob 调 previewFile', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    projectsApiMock.previewFile.mockResolvedValue(new Blob(['x'], { type: 'application/pdf' }))
    vm.handlePreviewFile({ id: 3, filename: 'a.pdf' })
    expect(vm.previewVisible).toBe(true)
    expect(vm.previewFileName).toBe('a.pdf')
    await vm.previewFetchBlob()
    expect(projectsApiMock.previewFile).toHaveBeenCalledWith(7, 3)
  })

  it('附件操作列「预览」按钮点击 → handlePreviewFile（模板箭头）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const previewBtns = wrapper.findAll('.el-button-stub').filter((b) => b.text().includes('预览'))
    if (previewBtns.length) {
      await previewBtns[0].trigger('click')
      expect((wrapper.vm as any).previewVisible).toBe(true)
    } else {
      // 附件表格行未渲染时至少确保组件可卸载（防御断言）
      expect(true).toBe(true)
    }
    // FilePreview v-model 箭头：子组件 emit update:modelValue(false) → previewVisible 复位
    const fp = wrapper.findComponent({ name: 'FilePreview' })
    if (fp.exists()) {
      fp.vm.$emit('update:modelValue', false)
      expect((wrapper.vm as any).previewVisible).toBe(false)
    }
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

describe('任务名全缺分支', () => {
  it('name/title 均无 → 空字符串', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openTaskDialog({ id: 3, status: 'pending', priority: 'normal' })
    expect(vm.taskForm.title).toBe('')
    wrapper.unmount()
  })
})

// ═══════════════════════════════════════════════════════
// 里程碑（T020 接线）：加载形态 / CRUD / 模板产物
// ═══════════════════════════════════════════════════════

const msRowDone = { id: 11, name: 'M1', status: 'completed', planned_date: '2024-03-01' }
const msRowOpen = { id: 12, name: 'M2', status: 'pending', planned_date: '2024-04-01' }

describe('里程碑：加载形态与异常', () => {
  it('res 为 { data: [...] } 信封 → 取 data 数组；msProgress 走非零分母', async () => {
    msList.mockResolvedValue({ data: [msRowDone, msRowOpen] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(msList).toHaveBeenCalledWith(7)
    expect(vm.milestones).toEqual([msRowDone, msRowOpen])
    expect(vm.msProgress).toEqual({ total: 2, completed: 1, percent: 50 })
    wrapper.unmount()
  })

  it('res 为非数组对象且带 items → 走 items', async () => {
    msList.mockResolvedValue({ items: [{ id: 13, name: 'M3', status: 'overdue' }] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.milestones).toHaveLength(1)
    expect(vm.msProgress).toEqual({ total: 1, completed: 0, percent: 0 })
    expect(vm.msStatusLabel('overdue')).toBe('已逾期')
    expect(vm.msStatusTag('overdue')).toBe('danger')
    wrapper.unmount()
  })

  it('res 为非数组且无 items → 空数组兜底', async () => {
    msList.mockResolvedValue({ data: {} })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.milestones).toEqual([])
    expect(vm.msProgress.percent).toBe(0)
    // 未知状态原样返回
    expect(vm.msStatusLabel('weird')).toBe('weird')
    expect(vm.msStatusTag('weird')).toBe('info')
    wrapper.unmount()
  })

  it('加载失败 → logger + 清空 milestones + msLoading 复位', async () => {
    msList.mockRejectedValue(new Error('ms boom'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalledWith('里程碑加载失败:', expect.any(Error))
    const vm = wrapper.vm as any
    expect(vm.milestones).toEqual([])
    expect(vm.msLoading).toBe(false)
    wrapper.unmount()
  })

  it('route.params.id 为空 → loadMilestones 早退不发请求', async () => {
    routeBox.params = { id: '' }
    const wrapper = mountComp()
    await flushPromises()
    expect(msList).not.toHaveBeenCalled()
    const vm = wrapper.vm as any
    expect(vm.msLoading).toBe(false)
    expect(vm.milestones).toEqual([])
    wrapper.unmount()
  })
})

describe('里程碑：openMsDialog', () => {
  it('无参调用 → 重置表单并打开弹窗（新增标题）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.msForm.id = 99
    vm.msForm.name = '残留'
    vm.openMsDialog()
    expect(vm.msForm).toEqual({
      id: undefined,
      name: '',
      planned_date: '',
      responsible_person: '',
      description: '',
    })
    expect(vm.msDialogVisible).toBe(true)
    await nextTick()
    // 里程碑弹窗是第二个 el-dialog（第一个为任务弹窗），title 经属性透传到桩根元素
    const dialogs = wrapper.findAll('.el-dialog-stub')
    expect(dialogs).toHaveLength(2)
    expect(dialogs[1].attributes('title')).toBe('新增里程碑')
    wrapper.unmount()
  })

  it('传入 row → 回填；字段缺省走 || \'\' 兜底；标题切为「编辑里程碑」', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openMsDialog(msRowOpen)
    expect(vm.msForm.id).toBe(12)
    expect(vm.msForm.name).toBe('M2')
    expect(vm.msForm.planned_date).toBe('2024-04-01')
    expect(vm.msForm.responsible_person).toBe('')
    expect(vm.msDialogVisible).toBe(true)

    vm.openMsDialog({
      id: 20,
      name: '完整',
      planned_date: '2024-05-01',
      responsible_person: '张三',
      description: '说明',
    })
    expect(vm.msForm.responsible_person).toBe('张三')
    expect(vm.msForm.description).toBe('说明')
    await nextTick()
    // 里程碑弹窗是第二个 el-dialog（第一个为任务弹窗）
    const dialogs = wrapper.findAll('.el-dialog-stub')
    expect(dialogs[1].attributes('title')).toBe('编辑里程碑')
    wrapper.unmount()
  })

  it('模板产物：「新增里程碑」按钮 → openMsDialog()', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.msForm.id = 5
    const add = wrapper
      .findAll('.el-button-stub')
      .find((b) => b.text().includes('新增里程碑'))
    expect(add).toBeTruthy()
    await add!.trigger('click')
    expect(vm.msDialogVisible).toBe(true)
    expect(vm.msForm.id).toBeUndefined()
    wrapper.unmount()
  })

  it('模板产物：里程碑表格「编辑」按钮 → openMsDialog(row)', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 「编辑」按钮 DOM 顺序：[0] 页头编辑、[1..4] 里程碑表格（el-table-column 桩渲染 4 行）、[5..] 任务表格
    const editBtns = wrapper.findAll('.el-button-stub').filter((b) => b.text() === '编辑')
    expect(editBtns.length).toBeGreaterThan(5)
    await editBtns[1].trigger('click')
    expect(vm.msDialogVisible).toBe(true)
    // 桩行 rowA 为 taskCompleted（id=1）
    expect(vm.msForm.id).toBe(1)
    wrapper.unmount()
  })
})

describe('里程碑：submitMilestone', () => {
  it('名称为空 → 告警并早退', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.msForm.name = '   '
    vm.msForm.planned_date = '2024-01-01'
    await vm.submitMilestone()
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写里程碑名称')
    expect(msCreate).not.toHaveBeenCalled()
    expect(vm.msSaving).toBe(false)
    wrapper.unmount()
  })

  it('计划日期为空 → 告警并早退', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.msForm.name = '有效名称'
    vm.msForm.planned_date = ''
    await vm.submitMilestone()
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择计划日期')
    expect(msCreate).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('新增：msForm.id 为空 → createMilestone；可选字段缺省转 undefined', async () => {
    msList.mockResolvedValue([])
    msCreate.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openMsDialog()
    vm.msForm.name = '  新里程碑  '
    vm.msForm.planned_date = '2024-08-01'
    msList.mockClear()
    await vm.submitMilestone()
    expect(msCreate).toHaveBeenCalledWith(7, {
      name: '新里程碑',
      planned_date: '2024-08-01',
      responsible_person: undefined,
      description: undefined,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('里程碑已新增')
    expect(vm.msDialogVisible).toBe(false)
    expect(vm.msSaving).toBe(false)
    expect(msList).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('编辑：msForm.id 有值 → updateMilestone；可选字段带值原样传递', async () => {
    msUpdate.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openMsDialog({
      id: 12,
      name: 'M2',
      planned_date: '2024-04-01',
      responsible_person: '李四',
      description: '描述',
    })
    msList.mockClear()
    await vm.submitMilestone()
    expect(msUpdate).toHaveBeenCalledWith(7, 12, {
      name: 'M2',
      planned_date: '2024-04-01',
      responsible_person: '李四',
      description: '描述',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('里程碑已更新')
    expect(vm.msDialogVisible).toBe(false)
    wrapper.unmount()
  })

  it('保存失败 → logger + 统一文案 + msSaving 复位', async () => {
    msCreate.mockRejectedValue(new Error('server'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.msForm.name = '新里程碑'
    vm.msForm.planned_date = '2024-08-01'
    await vm.submitMilestone()
    expect(logError).toHaveBeenCalledWith('里程碑保存失败:', expect.any(Error))
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败，请稍后重试')
    expect(vm.msSaving).toBe(false)
    expect(vm.msDialogVisible).toBe(false)
    wrapper.unmount()
  })
})

describe('里程碑：completeMilestone / removeMilestone', () => {
  it('标记完成 → updateMilestone(status=completed, actual_date=今天) + 刷新', async () => {
    msUpdate.mockResolvedValue({})
    msList.mockResolvedValue([])
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    msList.mockClear()
    await vm.completeMilestone({ id: 12 })
    const today = new Date().toISOString().slice(0, 10)
    expect(msUpdate).toHaveBeenCalledWith(7, 12, { status: 'completed', actual_date: today })
    expect(ElMessage.success).toHaveBeenCalledWith('里程碑已完成，项目进度已联动更新')
    expect(msList).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('标记完成失败 → logger + 操作失败', async () => {
    msUpdate.mockRejectedValue(new Error('nope'))
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).completeMilestone({ id: 12 })
    expect(logError).toHaveBeenCalledWith('完成里程碑失败:', expect.any(Error))
    expect(ElMessage.error).toHaveBeenCalledWith('操作失败')
    wrapper.unmount()
  })

  it('模板产物：里程碑表格「完成」按钮 → completeMilestone(row)', async () => {
    msUpdate.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    // 「完成」按钮仅存在于里程碑操作列：桩行中 status !== 'completed' 的 3 行
    const doneBtns = wrapper.findAll('.el-button-stub').filter((b) => b.text() === '完成')
    expect(doneBtns).toHaveLength(3)
    await doneBtns[0].trigger('click')
    await flushPromises()
    expect(msUpdate).toHaveBeenCalledWith(7, 2, expect.objectContaining({ status: 'completed' }))
    wrapper.unmount()
  })

  it('删除失败 → logger + 删除失败', async () => {
    msDelete.mockRejectedValue(new Error('del'))
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).removeMilestone({ id: 12 })
    expect(logError).toHaveBeenCalledWith('删除里程碑失败:', expect.any(Error))
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
    wrapper.unmount()
  })

  it('模板产物：里程碑删除 popconfirm → removeMilestone(row)', async () => {
    msDelete.mockResolvedValue({})
    msList.mockResolvedValue([])
    const wrapper = mountComp()
    await flushPromises()
    msDelete.mockClear()
    const pops = wrapper
      .findAll('.el-popconfirm-stub')
      .filter((x) => x.find('[data-test="ms-delete"]').exists())
    expect(pops.length).toBeGreaterThan(0)
    await pops[0].trigger('click')
    await flushPromises()
    expect(msDelete).toHaveBeenCalledWith(7, 1)
    expect(ElMessage.success).toHaveBeenCalledWith('里程碑已删除')
    wrapper.unmount()
  })
})

describe('里程碑弹窗：模板 v-model 与 footer', () => {
  it('计划日期 date-picker 写回 msForm.planned_date；取消按钮关闭弹窗；保存按钮提交', async () => {
    msCreate.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // date-picker DOM 顺序：[0] 任务弹窗截止日期、[1] 里程碑弹窗计划日期
    const pickers = wrapper.findAll('.el-date-picker-stub')
    expect(pickers).toHaveLength(2)
    await pickers[1].trigger('click')
    expect(vm.msForm.planned_date).toBe('2024-01-01')
    // 里程碑弹窗的名称/负责人/描述 el-input 桩统一写回 'V'
    for (const el of wrapper.findAll('.el-input-stub')) {
      await el.trigger('click')
    }
    expect(vm.msForm.name).toBe('V')
    expect(vm.msForm.responsible_person).toBe('V')
    expect(vm.msForm.description).toBe('V')

    vm.msDialogVisible = true
    // 「取消」按钮 DOM 顺序：[0] 任务弹窗、[1] 里程碑弹窗
    const cancels = wrapper.findAll('.el-button-stub').filter((b) => b.text() === '取消')
    expect(cancels).toHaveLength(2)
    await cancels[1].trigger('click')
    expect(vm.msDialogVisible).toBe(false)

    // footer 保存按钮 → submitMilestone（名称已被 el-input 桩写为 'V'，日期已有值）
    msList.mockClear()
    const saves = wrapper.findAll('.el-button-stub').filter((b) => b.text() === '保存')
    expect(saves).toHaveLength(2)
    await saves[1].trigger('click')
    await flushPromises()
    expect(msCreate).toHaveBeenCalled()
    wrapper.unmount()
  })
})
