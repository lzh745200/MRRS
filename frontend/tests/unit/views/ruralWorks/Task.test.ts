/**
 * views/ruralWorks/Task.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 三路加载全分支、筛选/分页 computed、CRUD 保存全路径（API/本地回退）、
 * 单个/批量分配、进度更新与历史、导入 CSV（FileReader 桩）、导出 CSV、
 * 辅助函数（标签/状态/截止/过期/格式化）、deadline 校验器，
 * 以及模板 v-model 箭头、内联 @click 赋值、el-dropdown command 箭头、el-progress format 箭头、
 * 表格三样本行覆盖优先级/进度三元与 v-if 两侧。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂会被提升到模块顶部注册，直接引用下方 const 会触发 TDZ；
// 所有被工厂引用的对象放入 vi.hoisted 中先行初始化。
const {
  ElMessage,
  confirmMock,
  mockGet,
  mockGetRuralWorks,
  mockCreateRuralWork,
  mockUpdateRuralWork,
  mockDeleteRuralWork,
  logWarn,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  confirmMock: vi.fn(),
  mockGet: vi.fn(),
  mockGetRuralWorks: vi.fn(),
  mockCreateRuralWork: vi.fn(),
  mockUpdateRuralWork: vi.fn(),
  mockDeleteRuralWork: vi.fn(),
  logWarn: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/api/ruralWork', () => ({
  getRuralWorks: mockGetRuralWorks,
  createRuralWork: mockCreateRuralWork,
  updateRuralWork: mockUpdateRuralWork,
  deleteRuralWork: mockDeleteRuralWork,
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: vi.fn(), warn: logWarn, info: vi.fn(), debug: vi.fn() },
}))

import Task from '@/views/ruralWorks/Task.vue'

// API 任务样本：覆盖映射两侧（planned→pending、status 空兜底、id 空兜底、created_at 有无）
const apiItem1 = {
  id: 101,
  name: '修路工程',
  village_name: '幸福村',
  responsible_person: '张三',
  status: 'planned',
  progress: 50,
  start_date: '2024-01-01',
  end_date: '2099-12-31',
  created_at: '2024-01-01T08:00:00',
  description: '修路',
}
const apiItem2 = {
  id: 102,
  name: '',
  village_name: '',
  responsible_person: '',
  status: '',
  progress: 0,
  start_date: '',
  end_date: '',
  created_at: '',
  description: '',
}
const apiItem3 = { id: '', name: '无编号任务', status: 'in_progress', progress: 100 }

// 表格列 stub 注入的三行样本：
// rowA 高优先级/pending/进度100/已过期；rowB 中优先级/in_progress/进度70/2天后截止；rowC 低优先级/cancelled/进度30/无截止日期
const twoDaysLater = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
const rowA = {
  id: '1',
  name: '任务A',
  projectId: '10',
  projectName: '项目甲',
  assigneeId: '1',
  assigneeName: '张三',
  status: 'pending',
  priority: 'high',
  progress: 100,
  startDate: '2019-12-01',
  deadline: '2020-01-01',
  createdDate: '2020-01-01',
  description: 'd1',
}
const rowB = {
  id: '2',
  name: '任务B',
  projectId: '',
  projectName: '项目乙',
  assigneeId: '',
  assigneeName: '',
  status: 'in_progress',
  priority: 'medium',
  progress: 70,
  startDate: '',
  deadline: twoDaysLater,
  createdDate: '',
  description: '',
}
const rowC = {
  id: '3',
  name: '任务C',
  projectId: '',
  projectName: '项目丙',
  assigneeId: '2',
  assigneeName: '李四',
  status: 'cancelled',
  priority: 'low',
  progress: 30,
  startDate: '',
  deadline: '',
  createdDate: '',
  description: '',
}

function defaultGetImpl(url: string) {
  if (url === '/users/staff-list') {
    // 覆盖 name/position/avatar 全部兜底链：name→real_name→username→用户id；position→role→员工
    return Promise.resolve({
      data: {
        items: [
          { id: 1, name: '张三', position: '经理', avatar: 'a.png' },
          { id: 2, real_name: '李四', role: '主管' },
          { id: 3, username: 'wangwu' },
          { id: 4 },
        ],
      },
    })
  }
  if (url === '/projects') {
    // response?.items 分支（无 data 层）；覆盖 name→title→项目id 兜底链
    return Promise.resolve({
      items: [{ id: 10, name: '项目A' }, { id: 11, title: '项目B' }, { id: 12 }],
    })
  }
  return Promise.resolve({})
}

function mountComp() {
  // setup.ts 的全局 el-* stub 默认不渲染插槽，需 renderStubDefaultSlot；
  // 具名插槽（footer/dropdown/prefix）与作用域插槽（表格行）需自定义 stub。
  return mount(Task, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-table': { name: 'ElTable', template: '<div class="el-table-stub"><slot /></div>' },
        // 注入三行样本数据，覆盖优先级/进度三元、assigneeName 空、isOverdue/getDeadlineClass 多分支、
        // 分配按钮 v-if、dropdown 进度项 v-if 的两侧
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
        'el-dropdown': {
          name: 'ElDropdown',
          template: '<div class="el-dropdown-stub"><slot /><slot name="dropdown" /></div>',
        },
        'el-input': {
          name: 'ElInput',
          template: '<div class="el-input-stub"><slot name="prefix" /><slot /></div>',
        },
        'el-select': { name: 'ElSelect', template: '<div class="el-select-stub"><slot /></div>' },
        'el-radio-group': {
          name: 'ElRadioGroup',
          template: '<div class="el-radio-group-stub"><slot /></div>',
        },
        'el-date-picker': { name: 'ElDatePicker', template: '<div class="el-date-picker-stub" />' },
        'el-slider': { name: 'ElSlider', template: '<div class="el-slider-stub" />' },
        'el-pagination': { name: 'ElPagination', template: '<div class="el-pagination-stub" />' },
        'el-progress': {
          name: 'ElProgress',
          props: ['percentage', 'status', 'strokeWidth', 'format'],
          template: '<div class="el-progress-stub" />',
        },
      },
    },
  })
}

/** 捕获组件创建的 file input 元素 */
function captureInputs() {
  const inputs: HTMLInputElement[] = []
  const orig = document.createElement.bind(document)
  const spy = vi.spyOn(document, 'createElement').mockImplementation((tag: any, opts?: any) => {
    const el = orig(tag, opts)
    if (String(tag).toLowerCase() === 'input') inputs.push(el as HTMLInputElement)
    return el
  })
  return { inputs, spy }
}

/** FileReader 桩：readAsText 同步回凋 onload，result 由 holder 控制 */
let fileReaderResult: any = ''
class MockFileReader {
  onload: ((e: any) => void) | null = null
  readAsText() {
    if (this.onload) this.onload({ target: { result: fileReaderResult } })
  }
}

beforeEach(() => {
  vi.resetAllMocks()
  mockGet.mockImplementation(defaultGetImpl)
  mockGetRuralWorks.mockResolvedValue({ items: [apiItem1, apiItem2, apiItem3] })
  mockCreateRuralWork.mockResolvedValue({ id: 555 })
  mockUpdateRuralWork.mockResolvedValue({})
  mockDeleteRuralWork.mockResolvedValue({})
  confirmMock.mockResolvedValue(undefined)
  fileReaderResult = ''
  vi.stubGlobal('FileReader', MockFileReader)
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

/**
 * 挂载并确保人员/项目加载完成。
 * 注意：onMounted 中 loadStaffFromApi() 与 loadProjectsFromApi() 并发执行
 * `await import('@/api/request')`，vite-node 对同一模块的并发动态 import
 * 只兑现其中一个 promise，导致 loadProjectsFromApi 永远挂起（真实浏览器无此问题）。
 * 因此挂载后手动补调一次 loadProjectsFromApi。
 */
async function mountReady() {
  const wrapper = mountComp()
  await flushPromises()
  const vm = wrapper.vm as any
  await vm.loadProjectsFromApi()
  return wrapper
}

describe('挂载与数据加载', () => {
  it('onMounted 并行加载人员/项目/任务，字段映射与兜底正确', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // onMounted 的并发动态 import 只兑现 staff-list；手动补调项目加载（见 mountReady 注释）
    await vm.loadProjectsFromApi()
    expect(mockGet).toHaveBeenCalledWith('/users/staff-list')
    expect(mockGet).toHaveBeenCalledWith('/projects', { page_size: 100 })
    expect(mockGetRuralWorks).toHaveBeenCalledWith({ limit: 100 })
    expect(vm.staff).toEqual([
      { id: '1', name: '张三', position: '经理', avatar: 'a.png' },
      { id: '2', name: '李四', position: '主管', avatar: '' },
      { id: '3', name: 'wangwu', position: '员工', avatar: '' },
      { id: '4', name: '用户4', position: '员工', avatar: '' },
    ])
    expect(vm.projects).toEqual([
      { id: '10', name: '项目A' },
      { id: '11', name: '项目B' },
      { id: '12', name: '项目12' },
    ])
    // planned → pending；status 空 → pending；id 空 → T003 兜底；created_at 空 → ''
    expect(vm.tasks).toHaveLength(3)
    expect(vm.tasks[0]).toMatchObject({ id: '101', status: 'pending', createdDate: '2024-01-01' })
    expect(vm.tasks[1]).toMatchObject({ id: '102', name: '', status: 'pending', createdDate: '' })
    expect(vm.tasks[2]).toMatchObject({ id: 'T003', status: 'in_progress' })
    expect(vm.loading).toBe(false)
  })

  it('loadStaffFromApi：response.items 分支（无 data 层）', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/users/staff-list') return Promise.resolve({ items: [{ id: 5, name: '王五' }] })
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).staff).toEqual([
      { id: '5', name: '王五', position: '员工', avatar: '' },
    ])
  })

  it('loadStaffFromApi：直接返回数组 → || response 分支', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/users/staff-list') return Promise.resolve([{ id: 6, name: '赵六' }])
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).staff).toHaveLength(1)
  })

  it('loadStaffFromApi：空数组/非数组/空响应 → 保持空列表', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/users/staff-list') return Promise.resolve([])
      return defaultGetImpl(url)
    })
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).staff).toEqual([])
    wrapper.unmount()

    mockGet.mockImplementation((url: string) => {
      if (url === '/users/staff-list') return Promise.resolve(42)
      return defaultGetImpl(url)
    })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).staff).toEqual([])
    wrapper.unmount()

    mockGet.mockImplementation((url: string) => {
      if (url === '/users/staff-list') return Promise.resolve(null)
      return defaultGetImpl(url)
    })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).staff).toEqual([])
  })

  it('loadStaffFromApi：请求异常 → logger.warn 并保持空列表', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/users/staff-list') return Promise.reject(new Error('net'))
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect(logWarn).toHaveBeenCalled()
    expect((wrapper.vm as any).staff).toEqual([])
  })

  it('loadProjectsFromApi：直接数组 / 空响应 / 空数组 / 异常分支', async () => {
    // onMounted 的项目加载因并发动态 import 挂起，各分支统一手动调用验证
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    mockGet.mockImplementation((url: string) => {
      if (url === '/projects') return Promise.resolve([{ id: 20, name: '直项' }])
      return defaultGetImpl(url)
    })
    await vm.loadProjectsFromApi()
    expect(vm.projects).toEqual([{ id: '20', name: '直项' }])

    vm.projects = []
    mockGet.mockImplementation((url: string) => {
      if (url === '/projects') return Promise.resolve(null)
      return defaultGetImpl(url)
    })
    await vm.loadProjectsFromApi()
    expect(vm.projects).toEqual([])

    mockGet.mockImplementation((url: string) => {
      if (url === '/projects') return Promise.resolve([])
      return defaultGetImpl(url)
    })
    await vm.loadProjectsFromApi()
    expect(vm.projects).toEqual([])

    mockGet.mockImplementation((url: string) => {
      if (url === '/projects') return Promise.reject(new Error('net'))
      return defaultGetImpl(url)
    })
    await vm.loadProjectsFromApi()
    expect(logWarn).toHaveBeenCalled()
    expect(vm.projects).toEqual([])
  })

  it('loadData：items 为空 / items 缺失 / res 为 null / 请求异常 → 任务保持空', async () => {
    mockGetRuralWorks.mockResolvedValue({ items: [] })
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).tasks).toEqual([])
    wrapper.unmount()

    mockGetRuralWorks.mockResolvedValue({})
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).tasks).toEqual([])
    wrapper.unmount()

    mockGetRuralWorks.mockResolvedValue(null)
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).tasks).toEqual([])
    wrapper.unmount()

    mockGetRuralWorks.mockRejectedValue(new Error('net'))
    wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.tasks).toEqual([])
    expect(vm.loading).toBe(false)
  })
})

describe('工具栏交互与筛选', () => {
  it('点击查询按钮 → 回到第 1 页并重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentPage = 3
    mockGetRuralWorks.mockClear()
    const btn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('查询'))!
    expect(btn).toBeTruthy()
    await btn.trigger('click')
    await flushPromises()
    expect(vm.currentPage).toBe(1)
    expect(mockGetRuralWorks).toHaveBeenCalled()
  })

  it('点击重置按钮 → 清空全部筛选并重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchQuery = 'x'
    vm.selectedStatus = 'pending'
    vm.selectedPriority = 'high'
    vm.selectedAssignee = '1'
    vm.currentPage = 2
    const btn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('重置'))!
    await btn.trigger('click')
    await flushPromises()
    expect(vm.searchQuery).toBe('')
    expect(vm.selectedStatus).toBe('')
    expect(vm.selectedPriority).toBe('')
    expect(vm.selectedAssignee).toBe('')
    expect(vm.currentPage).toBe(1)
  })

  it('搜索框 keyup.enter → 触发查询', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentPage = 5
    mockGetRuralWorks.mockClear()
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    expect(inputs.length).toBeGreaterThan(0)
    inputs[0].vm.$emit('keyup', { key: 'Enter' })
    await flushPromises()
    expect(vm.currentPage).toBe(1)
    expect(mockGetRuralWorks).toHaveBeenCalled()
  })

  it('全部 v-model 组件触发 update:modelValue 箭头', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 进度对话框内容在 v-if="currentTaskProgress" 内，先打开使进度输入框/滑块渲染
    vm.viewTaskProgress(vm.tasks[0])
    await nextTick()

    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    for (const c of inputs) c.vm.$emit('update:modelValue', 'x')
    expect(vm.searchQuery).toBe('x')
    expect(vm.currentTask.name).toBe('x')
    expect(vm.currentTask.description).toBe('x')
    expect(vm.assignForm.note).toBe('x')
    expect(vm.progressUpdateForm.description).toBe('x')
    expect(vm.batchAssignForm.note).toBe('x')

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(selects.length).toBeGreaterThan(0)
    for (const c of selects) c.vm.$emit('update:modelValue', '1')
    expect(vm.selectedStatus).toBe('1')
    expect(vm.selectedPriority).toBe('1')
    expect(vm.selectedAssignee).toBe('1')
    expect(vm.currentTask.projectId).toBe('1')
    expect(vm.currentTask.assigneeId).toBe('1')
    expect(vm.currentTask.status).toBe('1')
    expect(vm.assignForm.assigneeId).toBe('1')
    expect(vm.batchAssignForm.assigneeId).toBe('1')

    const radios = wrapper.findAllComponents({ name: 'ElRadioGroup' })
    expect(radios.length).toBe(1)
    radios[0].vm.$emit('update:modelValue', 'high')
    expect(vm.currentTask.priority).toBe('high')

    const pickers = wrapper.findAllComponents({ name: 'ElDatePicker' })
    expect(pickers.length).toBe(2)
    for (const c of pickers) c.vm.$emit('update:modelValue', '2024-06-01')
    expect(vm.currentTask.startDate).toBe('2024-06-01')
    expect(vm.currentTask.deadline).toBe('2024-06-01')

    const sliders = wrapper.findAllComponents({ name: 'ElSlider' })
    expect(sliders.length).toBe(1)
    sliders[0].vm.$emit('update:modelValue', 55)
    expect(vm.progressUpdateForm.progress).toBe(55)

    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    expect(dialogs.length).toBe(4)
    for (const d of dialogs) d.vm.$emit('update:modelValue', true)
    expect(vm.taskDialogVisible).toBe(true)
    expect(vm.assignDialogVisible).toBe(true)
    expect(vm.progressDialogVisible).toBe(true)
    expect(vm.batchAssignDialogVisible).toBe(true)
    await nextTick()
  })

  it('分页器 v-model 与 size-change/current-change 处理器', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const pager = wrapper.findComponent({ name: 'ElPagination' })
    expect(pager.exists()).toBe(true)
    pager.vm.$emit('update:currentPage', 2)
    pager.vm.$emit('update:pageSize', 20)
    expect(vm.currentPage).toBe(2)
    expect(vm.pageSize).toBe(20)
    pager.vm.$emit('size-change', 50)
    expect(vm.pageSize).toBe(50)
    expect(vm.currentPage).toBe(1)
    pager.vm.$emit('current-change', 3)
    expect(vm.currentPage).toBe(3)
  })

  it('filteredTasks：搜索词命中名称/负责人/项目名三条 || 臂', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.tasks = [
      { ...rowA, id: 'a', name: '苹果', assigneeName: '', projectName: '' },
      { ...rowB, id: 'b', name: '香蕉', assigneeName: '果农甲', projectName: '' },
      { ...rowC, id: 'c', name: '橙子', assigneeName: '', projectName: '果园项目' },
    ]
    vm.searchQuery = '苹果'
    expect(vm.filteredTasks.map((t: any) => t.id)).toEqual(['a'])
    vm.searchQuery = '果农甲' // 命中负责人（assigneeName 真值臂）
    expect(vm.filteredTasks.map((t: any) => t.id)).toEqual(['b'])
    vm.searchQuery = '果园' // 负责人为空（&& 短路）后命中项目名
    expect(vm.filteredTasks.map((t: any) => t.id)).toEqual(['c'])
    vm.searchQuery = '不存在'
    expect(vm.filteredTasks).toEqual([])
  })

  it('filteredTasks：状态/优先级/负责人过滤与分页切片', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.tasks = [
      { ...rowA, id: 'a', status: 'pending', priority: 'high', assigneeId: '1' },
      { ...rowB, id: 'b', status: 'completed', priority: 'low', assigneeId: '2' },
      { ...rowC, id: 'c', status: 'completed', priority: 'low', assigneeId: '3' },
    ]
    vm.selectedStatus = 'completed'
    expect(vm.filteredTasks.map((t: any) => t.id)).toEqual(['b', 'c'])
    vm.selectedStatus = ''
    vm.selectedPriority = 'high'
    expect(vm.filteredTasks.map((t: any) => t.id)).toEqual(['a'])
    vm.selectedPriority = ''
    vm.selectedAssignee = '3'
    expect(vm.filteredTasks.map((t: any) => t.id)).toEqual(['c'])
    vm.selectedAssignee = ''
    vm.pageSize = 1
    vm.currentPage = 2
    expect(vm.filteredTasks.map((t: any) => t.id)).toEqual(['b'])
  })

  it('表格 selection-change / row-dblclick 事件与选中计数渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const table = wrapper.findComponent({ name: 'ElTable' })
    table.vm.$emit('selection-change', [rowA, rowB])
    await nextTick()
    expect(vm.selectedTasks).toHaveLength(2)
    // 批量分配按钮计数 v-if 真值侧
    const batchBtn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('批量分配'))!
    expect(batchBtn.text()).toContain('(2)')

    table.vm.$emit('row-dblclick', rowA)
    await nextTick()
    expect(vm.taskDialogVisible).toBe(true)
    expect(vm.isEditMode).toBe(true)
    expect(vm.currentTask.name).toBe('任务A')
  })
})

describe('新建/编辑/保存任务', () => {
  it('openCreateTaskDialog：taskFormRef 存在 → resetFields 并重置表单', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const resetFields = vi.fn()
    vm.taskFormRef = { resetFields, validate: vi.fn() }
    vm.isEditMode = true
    vm.currentTask.name = '脏数据'
    vm.openCreateTaskDialog()
    expect(resetFields).toHaveBeenCalled()
    expect(vm.isEditMode).toBe(false)
    expect(vm.currentTask.name).toBe('')
    expect(vm.currentTask.status).toBe('pending')
    expect(vm.taskDialogVisible).toBe(true)
  })

  it('openCreateTaskDialog：taskFormRef 为空 → 跳过 resetFields', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.taskFormRef = null
    vm.openCreateTaskDialog()
    expect(vm.taskDialogVisible).toBe(true)
  })

  it('saveTask：taskFormRef 为空 → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.taskFormRef = null
    await vm.saveTask()
    expect(mockCreateRuralWork).not.toHaveBeenCalled()
    expect(mockUpdateRuralWork).not.toHaveBeenCalled()
  })

  it('saveTask：校验失败 → 捕获并中止', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.taskFormRef = { validate: vi.fn().mockRejectedValue(new Error('invalid')) }
    await vm.saveTask()
    expect(mockCreateRuralWork).not.toHaveBeenCalled()
    expect(vm.taskDialogVisible).toBe(false) // 初始即关闭，未被改动
  })

  it('saveTask 创建成功：名称/负责人解析 + status pending → planned', async () => {
    const wrapper = await mountReady() // 需要 projects/staff 已加载
    const vm = wrapper.vm as any
    vm.currentTask = {
      ...vm.currentTask,
      name: '新任务',
      projectId: '10',
      assigneeId: '1',
      status: 'pending',
      startDate: '2024-01-01',
      deadline: '2024-02-01',
      description: 'd',
      progress: 10,
    }
    vm.isEditMode = false
    vm.taskFormRef = { validate: vi.fn().mockResolvedValue(true) }
    vm.taskDialogVisible = true
    await vm.saveTask()
    expect(vm.currentTask.projectName).toBe('项目A')
    expect(vm.currentTask.assigneeName).toBe('张三')
    expect(mockCreateRuralWork).toHaveBeenCalledWith(
      expect.objectContaining({ name: '新任务', status: 'planned', responsible_person: '张三' })
    )
    expect(vm.currentTask.id).toBe('555')
    expect(ElMessage.success).toHaveBeenCalledWith('任务创建成功')
    expect(vm.taskDialogVisible).toBe(false)
    expect(vm.currentPage).toBe(1)
  })

  it('saveTask 创建：result 为 null → Date.now 兜底；status in_progress 直传', async () => {
    mockCreateRuralWork.mockResolvedValue(null)
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentTask = {
      ...vm.currentTask,
      name: 'n',
      status: 'in_progress',
      projectId: '',
      assigneeId: '',
    }
    vm.isEditMode = false
    vm.taskFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.saveTask()
    expect(mockCreateRuralWork).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'in_progress' })
    )
    expect(vm.currentTask.id).not.toBe('')
    expect(vm.currentTask.assigneeName).toBe('') // assigneeId 空 → else 臂
  })

  it('saveTask 创建失败 → 本地 unshift 回退；status 其他 → completed', async () => {
    mockCreateRuralWork.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const before = vm.tasks.length
    // saveTask 末尾会重新 loadData；让重载返回空以保留本地回退结果
    mockGetRuralWorks.mockResolvedValue({ items: [] })
    vm.currentTask = {
      ...vm.currentTask,
      name: '本地任务',
      status: 'cancelled',
      projectId: '',
      assigneeId: '',
    }
    vm.isEditMode = false
    vm.taskFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.saveTask()
    expect(mockCreateRuralWork).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'completed' })
    )
    expect(vm.tasks.length).toBe(before + 1)
    expect(vm.tasks[0].name).toBe('本地任务')
    expect(ElMessage.success).toHaveBeenCalledWith('任务创建成功（本地）')
  })

  it('saveTask 编辑成功：projectId 找不到时保留原项目名', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.editTask({ ...rowA, projectId: '999', projectName: '原项目' })
    vm.taskFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.saveTask()
    expect(mockUpdateRuralWork).toHaveBeenCalledWith(1, expect.objectContaining({ name: '任务A' }))
    expect(vm.currentTask.projectName).toBe('原项目') // find 未命中 → 不覆盖
    expect(ElMessage.success).toHaveBeenCalledWith('任务更新成功')
  })

  it('saveTask 编辑失败 → 本地替换（index 命中）', async () => {
    mockUpdateRuralWork.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // saveTask 末尾会重新 loadData；让重载返回空以保留本地回退结果
    mockGetRuralWorks.mockResolvedValue({ items: [] })
    vm.editTask({ ...vm.tasks[0], name: '改后名' })
    vm.taskFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.saveTask()
    expect(vm.tasks[0].name).toBe('改后名')
    expect(ElMessage.success).toHaveBeenCalledWith('任务更新成功（本地）')
  })

  it('saveTask 编辑失败 → index 未命中不替换；assigneeId 找不到保留原名', async () => {
    mockUpdateRuralWork.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.isEditMode = true
    vm.currentTask = {
      ...rowA,
      id: 'NOT-EXIST',
      name: '幽灵',
      assigneeId: '999',
      assigneeName: '原人',
    }
    vm.taskFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.saveTask()
    expect(vm.tasks.some((t: any) => t.name === '幽灵')).toBe(false)
    expect(vm.currentTask.assigneeName).toBe('原人') // find 未命中 → 不覆盖
    expect(ElMessage.success).toHaveBeenCalledWith('任务更新成功（本地）')
  })
})

describe('任务分配（单个/批量）', () => {
  it('点击行内分配按钮 → assignTask 打开对话框并重置表单', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const btn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '分配')!
    expect(btn).toBeTruthy()
    await btn.trigger('click')
    expect(vm.assignDialogVisible).toBe(true)
    expect(vm.assignForm).toEqual({ assigneeId: '', note: '' })
    expect(vm.currentTask.name).toBe('任务A') // rowA 为 pending，才有分配按钮
  })

  it('confirmAssign：assignFormRef 为空 → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.assignFormRef = null
    await vm.confirmAssign()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('confirmAssign：校验失败 → 捕获并中止', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.assignFormRef = { validate: vi.fn().mockRejectedValue(new Error('invalid')) }
    await vm.confirmAssign()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('confirmAssign 成功：更新负责人并置为进行中', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // confirmAssign 末尾会重新 loadData；让重载返回空以保留本地修改
    mockGetRuralWorks.mockResolvedValue({ items: [] })
    vm.assignTask(vm.tasks[0])
    vm.assignForm.assigneeId = '2'
    vm.assignFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.confirmAssign()
    expect(vm.tasks[0].assigneeId).toBe('2')
    expect(vm.tasks[0].assigneeName).toBe('李四')
    expect(vm.tasks[0].status).toBe('in_progress')
    expect(ElMessage.success).toHaveBeenCalledWith('任务分配成功')
    expect(vm.assignDialogVisible).toBe(false)
  })

  it('confirmAssign：任务不在列表 / 负责人找不到 → 不更新但仍提示成功', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 负责人找不到（index 命中但 assignee undefined）
    vm.assignTask(vm.tasks[0])
    vm.assignForm.assigneeId = '999'
    vm.assignFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.confirmAssign()
    expect(vm.tasks[0].assigneeId).toBe('')
    expect(ElMessage.success).toHaveBeenCalledWith('任务分配成功')

    // 任务不在列表（index -1）
    vm.currentTask = { ...rowA, id: 'NOT-EXIST' }
    vm.assignForm.assigneeId = '1'
    vm.assignFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.confirmAssign()
    expect(ElMessage.success).toHaveBeenCalledWith('任务分配成功')
  })

  it('batchAssignTasks：未选择 → 警告；已选择 → 打开对话框', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedTasks = []
    vm.batchAssignTasks()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择需要分配的任务')
    expect(vm.batchAssignDialogVisible).toBe(false)

    vm.selectedTasks = [vm.tasks[0]]
    vm.batchAssignTasks()
    expect(vm.batchAssignDialogVisible).toBe(true)
    expect(vm.batchAssignForm).toEqual({ assigneeId: '', note: '' })
  })

  it('confirmBatchAssign：formRef 为空 / 校验失败 → 中止', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.batchAssignFormRef = null
    await vm.confirmBatchAssign()
    expect(ElMessage.success).not.toHaveBeenCalled()
    vm.batchAssignFormRef = { validate: vi.fn().mockRejectedValue(new Error('invalid')) }
    await vm.confirmBatchAssign()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('confirmBatchAssign 成功：含不在列表中的选中项（index -1 臂）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // confirmBatchAssign 末尾会重新 loadData；让重载返回空以保留本地修改
    mockGetRuralWorks.mockResolvedValue({ items: [] })
    vm.selectedTasks = [vm.tasks[0], vm.tasks[1], { ...rowA, id: 'NOT-EXIST' }]
    vm.batchAssignForm.assigneeId = '1'
    vm.batchAssignFormRef = { validate: vi.fn().mockResolvedValue(true) }
    vm.batchAssignDialogVisible = true
    await vm.confirmBatchAssign()
    expect(vm.tasks[0].assigneeName).toBe('张三')
    expect(vm.tasks[0].status).toBe('in_progress')
    expect(vm.tasks[1].assigneeName).toBe('张三')
    expect(ElMessage.success).toHaveBeenCalledWith('成功分配 3 个任务')
    expect(vm.selectedTasks).toEqual([])
    expect(vm.batchAssignDialogVisible).toBe(false)
  })

  it('confirmBatchAssign：负责人找不到 → 不更新但仍提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedTasks = [vm.tasks[0]]
    vm.batchAssignForm.assigneeId = '999'
    vm.batchAssignFormRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.confirmBatchAssign()
    expect(vm.tasks[0].assigneeId).toBe('')
    expect(ElMessage.success).toHaveBeenCalledWith('成功分配 1 个任务')
  })
})

describe('任务进度', () => {
  it('viewTaskProgress：填充进度表单并打开对话框', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.viewTaskProgress(vm.tasks[0])
    expect(vm.currentTaskProgress).toMatchObject({ id: '101', history: [] })
    expect(vm.progressUpdateForm).toEqual({ progress: 50, description: '', attachments: [] })
    expect(vm.progressDialogVisible).toBe(true)
  })

  it('updateTaskProgress：currentTaskProgress 为空 → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentTaskProgress = null
    await vm.updateTaskProgress()
    expect(ElMessage.warning).not.toHaveBeenCalled()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('updateTaskProgress：进度无变化 → 警告', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.viewTaskProgress(vm.tasks[0])
    vm.progressUpdateForm.progress = 50
    await vm.updateTaskProgress()
    expect(ElMessage.warning).toHaveBeenCalledWith('进度没有变化')
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('updateTaskProgress 到 100% → 自动完成并写入历史', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.viewTaskProgress(vm.tasks[0]) // progress 50，responsible_person 张三
    vm.progressUpdateForm = {
      progress: 100,
      description: '完工',
      attachments: [{ name: 'f.png', url: '', uid: '1' }],
    }
    await vm.updateTaskProgress()
    expect(vm.tasks[0].progress).toBe(100)
    expect(vm.tasks[0].status).toBe('completed')
    expect(vm.currentTaskProgress.history).toHaveLength(1)
    expect(vm.currentTaskProgress.history[0]).toMatchObject({
      assigneeName: '张三',
      oldProgress: 50,
      newProgress: 100,
      description: '完工',
    })
    expect(vm.currentTaskProgress.progress).toBe(100)
    expect(vm.progressUpdateForm).toEqual({ progress: 100, description: '', attachments: [] })
    expect(ElMessage.success).toHaveBeenCalledWith('进度更新成功')
  })

  it('updateTaskProgress：进度<100 且任务已完成 → 回到进行中；history 空 → 初始化', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.viewTaskProgress(vm.tasks[0])
    vm.tasks[0].status = 'completed'
    vm.currentTaskProgress.history = undefined // 覆盖 !history → 初始化臂
    vm.currentTaskProgress.assigneeName = '' // 覆盖 '系统' 兜底臂
    vm.progressUpdateForm = { progress: 60, description: '', attachments: [] }
    await vm.updateTaskProgress()
    expect(vm.tasks[0].status).toBe('in_progress')
    expect(vm.tasks[0].progress).toBe(60)
    expect(vm.currentTaskProgress.history[0].assigneeName).toBe('系统')

    // 进度<100 且状态非 completed → 状态不变
    vm.progressUpdateForm = { progress: 70, description: '', attachments: [] }
    await vm.updateTaskProgress()
    expect(vm.tasks[0].status).toBe('in_progress')
    expect(vm.tasks[0].progress).toBe(70)
  })

  it('updateTaskProgress：任务不在列表 → 静默不提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.viewTaskProgress({ ...rowA, id: 'NOT-EXIST', progress: 10 })
    vm.progressUpdateForm.progress = 80
    await vm.updateTaskProgress()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('进度对话框渲染：有/无负责人两侧 + 已过期徽标 + 空历史文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 有负责人（头像取自 staff，姓名取首字）
    vm.viewTaskProgress({ ...rowA, assigneeId: '1', assigneeName: '张三', deadline: '2020-01-01' })
    await nextTick()
    expect(wrapper.text()).toContain('张三')
    expect(wrapper.text()).toContain('已过期')
    expect(wrapper.text()).toContain('暂无进度记录')

    // 无负责人 → '未' 与 '未分配' 兜底
    vm.viewTaskProgress({ ...rowB, assigneeId: '', assigneeName: '', deadline: twoDaysLater })
    await nextTick()
    expect(wrapper.text()).toContain('未分配')
    expect(wrapper.text()).not.toContain('已过期')

    // progress 为 0 → currentTaskProgress?.progress || 0 右臂
    vm.viewTaskProgress({ ...rowC, progress: 0 })
    // attachments 为 undefined → el-upload :file-list 的 || [] 右臂
    vm.progressUpdateForm.attachments = undefined
    await nextTick()
    expect(wrapper.text()).toContain('任务C')
  })

  it('进度历史渲染：描述/附件 v-if 两侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.viewTaskProgress(vm.tasks[0])
    vm.currentTaskProgress.history = [
      {
        timestamp: '2024-01-02T10:00:00',
        assigneeName: '张三',
        oldProgress: 0,
        newProgress: 50,
        description: '中期汇报',
        attachments: [{ name: '报告.pdf' }],
      },
      {
        timestamp: '2024-01-01T09:00:00',
        assigneeName: '李四',
        oldProgress: 0,
        newProgress: 0,
        description: '',
        attachments: [],
      },
    ]
    await nextTick()
    expect(wrapper.text()).toContain('中期汇报')
    expect(wrapper.text()).toContain('报告.pdf')
    expect(wrapper.text()).toContain('进度更新:')
  })

  it('进度对话框底部按钮：completed 显示任务已完成，否则更新进度', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.viewTaskProgress({ ...rowA, status: 'completed' })
    await nextTick()
    let btn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('任务已完成'))!
    expect(btn).toBeTruthy()

    vm.viewTaskProgress({ ...rowB, status: 'in_progress', progress: 70 })
    await nextTick()
    btn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '更新进度')!
    expect(btn).toBeTruthy()
  })

  it('el-progress format 内联箭头返回百分比文本', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.viewTaskProgress(vm.tasks[0])
    await nextTick()
    const progresses = wrapper.findAllComponents({ name: 'ElProgress' })
    const withFormat = progresses.find((p) => typeof p.props('format') === 'function')!
    expect(withFormat).toBeTruthy()
    expect(withFormat.props('format')(50)).toBe('50%')
  })
})

describe('删除任务与 dropdown 命令', () => {
  it('handleActionCommand：progress / delete / 未知命令', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const dropdowns = wrapper.findAllComponents({ name: 'ElDropdown' })
    expect(dropdowns.length).toBeGreaterThan(0)

    dropdowns[0].vm.$emit('command', 'progress')
    expect(vm.progressDialogVisible).toBe(true)
    expect(vm.currentTaskProgress.name).toBe('任务A')

    dropdowns[1].vm.$emit('command', 'delete')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledWith(
      '确定要删除该任务吗？此操作不可恢复。',
      '警告',
      expect.objectContaining({ type: 'warning' })
    )
    expect(mockDeleteRuralWork).toHaveBeenCalledWith(2)
    expect(ElMessage.success).toHaveBeenCalledWith('任务删除成功')

    dropdowns[2].vm.$emit('command', 'unknown') // 无匹配 case → 不报错
  })

  it('deleteTask：API 失败 → 本地删除（index 命中 / 未命中两臂）', async () => {
    mockDeleteRuralWork.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const before = vm.tasks.length
    // deleteTask 末尾会重新 loadData；让重载返回空以保留本地删除结果
    mockGetRuralWorks.mockResolvedValue({ items: [] })
    vm.deleteTask(vm.tasks[0].id)
    await flushPromises()
    expect(vm.tasks.length).toBe(before - 1)
    expect(ElMessage.success).toHaveBeenCalledWith('任务删除成功（本地）')

    vm.deleteTask('NOT-EXIST') // index -1 → 不 splice
    await flushPromises()
    expect(ElMessage.success).toHaveBeenCalledWith('任务删除成功（本地）')
  })

  it('deleteTask：取消确认 → 静默返回', async () => {
    confirmMock.mockRejectedValue(new Error('cancel'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.deleteTask('101')
    await flushPromises()
    expect(mockDeleteRuralWork).not.toHaveBeenCalled()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })
})

describe('导入/导出任务', () => {
  it('importTasks：未选择文件 → 直接返回', async () => {
    const { inputs, spy } = captureInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.importTasks()
    expect(inputs).toHaveLength(1)
    expect(inputs[0].type).toBe('file')
    expect(inputs[0].accept).toBe('.csv,.xlsx,.xls')
    Object.defineProperty(inputs[0], 'files', { value: [], configurable: true })
    inputs[0].dispatchEvent(new Event('change'))
    await flushPromises()
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(ElMessage.warning).not.toHaveBeenCalled()
    spy.mockRestore()
  })

  it('importTasks：内容不足两行 → 警告', async () => {
    fileReaderResult = '任务编号,任务名称'
    const { inputs, spy } = captureInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const before = vm.tasks.length
    vm.importTasks()
    const file = new File(['x'], 't.csv', { type: 'text/csv' })
    Object.defineProperty(inputs[0], 'files', { value: [file], configurable: true })
    inputs[0].dispatchEvent(new Event('change'))
    await flushPromises()
    expect(ElMessage.warning).toHaveBeenCalledWith('文件内容为空或格式不正确')
    expect(vm.tasks.length).toBe(before)
    spy.mockRestore()
  })

  it('importTasks 成功：跳过短行/空名称行，去引号，提示导入数', async () => {
    fileReaderResult =
      '编号,名称,,项目,负责人,,,,开始,截止,描述\n' +
      '"1","灌溉工程",,"项目甲","张三",,,,"2024-01-01","2024-03-01","说明"\n' +
      'short\n' +
      '2,\n' +
      '"3","道路硬化",,"项目乙","李四"\n' +
      '"5","缺列任务"' // 仅两列 → cols[3]/cols[4] 等 || '' 兜底臂
    const { inputs, spy } = captureInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const before = vm.tasks.length
    vm.importTasks()
    const file = new File(['x'], 't.csv', { type: 'text/csv' })
    Object.defineProperty(inputs[0], 'files', { value: [file], configurable: true })
    inputs[0].dispatchEvent(new Event('change'))
    await flushPromises()
    expect(vm.tasks.length).toBe(before + 3)
    const imported = vm.tasks.slice(-3)
    expect(imported[0]).toMatchObject({
      name: '灌溉工程',
      projectName: '项目甲',
      assigneeName: '张三',
    })
    expect(imported[1]).toMatchObject({ name: '道路硬化', projectName: '项目乙' })
    expect(imported[2]).toMatchObject({ name: '缺列任务', projectName: '', assigneeName: '' })
    expect(ElMessage.success).toHaveBeenCalledWith('成功导入 3 个任务')
    spy.mockRestore()
  })

  it('importTasks：解析异常 → 错误提示', async () => {
    fileReaderResult = null // result 为 null → text.split 抛 TypeError 进 catch
    const { inputs, spy } = captureInputs()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.importTasks()
    const file = new File(['x'], 't.csv', { type: 'text/csv' })
    Object.defineProperty(inputs[0], 'files', { value: [file], configurable: true })
    inputs[0].dispatchEvent(new Event('change'))
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('文件解析失败，请检查文件格式')
    spy.mockRestore()
  })

  it('exportTasks：无数据 → 警告', async () => {
    mockGetRuralWorks.mockResolvedValue({ items: [] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.exportTasks()
    expect(ElMessage.warning).toHaveBeenCalledWith('没有可导出的任务数据')
  })

  it('exportTasks 成功：状态/优先级映射表命中与回退，生成下载链接', async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 覆盖 statusMap/priorityMap 未命中回退、assigneeName/description 空值兜底
    vm.tasks = [
      { ...rowA, status: 'pending', priority: 'high', assigneeName: '张三', description: 'd' },
      { ...rowB, status: 'weird', priority: 'alien', assigneeName: '', description: '' },
    ]
    vm.exportTasks()
    expect(clickSpy).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('任务数据导出成功')
    clickSpy.mockRestore()
  })
})

describe('辅助函数', () => {
  it('getPriorityLabel / getStatusLabel / getStatusTagType 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getPriorityLabel('high')).toBe('高优先级')
    expect(vm.getPriorityLabel('medium')).toBe('中优先级')
    expect(vm.getPriorityLabel('low')).toBe('低优先级')
    expect(vm.getPriorityLabel('x')).toBe('未知优先级')

    expect(vm.getStatusLabel('pending')).toBe('待分配')
    expect(vm.getStatusLabel('in_progress')).toBe('进行中')
    expect(vm.getStatusLabel('completed')).toBe('已完成')
    expect(vm.getStatusLabel('delayed')).toBe('已延期')
    expect(vm.getStatusLabel('cancelled')).toBe('已取消')
    expect(vm.getStatusLabel('x')).toBe('未知状态')

    expect(vm.getStatusTagType('pending')).toBe('info')
    expect(vm.getStatusTagType('in_progress')).toBe('primary')
    expect(vm.getStatusTagType('completed')).toBe('success')
    expect(vm.getStatusTagType('delayed')).toBe('danger')
    expect(vm.getStatusTagType('cancelled')).toBe('warning')
    expect(vm.getStatusTagType('x')).toBe('info')
  })

  it('getProgressStatus 四分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getProgressStatus(100)).toBe('success')
    expect(vm.getProgressStatus(80)).toBe('')
    expect(vm.getProgressStatus(50)).toBe('warning')
    expect(vm.getProgressStatus(10)).toBe('')
  })

  it('getAssigneeAvatar：空 id / 命中头像 / 命中无头像 / 未命中', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getAssigneeAvatar('')).toBe('')
    expect(vm.getAssigneeAvatar('1')).toBe('a.png')
    expect(vm.getAssigneeAvatar('3')).toBe('')
    expect(vm.getAssigneeAvatar('999')).toBe('')
  })

  it('getDeadlineClass 五分支与 isOverdue 四分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getDeadlineClass({ status: 'completed', deadline: '2020-01-01' })).toBe(
      'deadline-normal'
    )
    expect(vm.getDeadlineClass({ status: 'cancelled', deadline: '2020-01-01' })).toBe(
      'deadline-normal'
    )
    expect(vm.getDeadlineClass({ status: 'pending', deadline: '2020-01-01' })).toBe(
      'deadline-overdue'
    )
    expect(vm.getDeadlineClass({ status: 'pending', deadline: twoDaysLater })).toBe(
      'deadline-warning'
    )
    expect(vm.getDeadlineClass({ status: 'pending', deadline: '2099-12-31' })).toBe(
      'deadline-normal'
    )
    // 无截止日期：不得因 Invalid Date → NaN 而被静默判为正常/超期
    expect(vm.getDeadlineClass({ status: 'pending', deadline: '' })).toBe('deadline-normal')

    expect(vm.isOverdue({ status: 'completed', deadline: '2020-01-01' })).toBe(false)
    expect(vm.isOverdue({ status: 'cancelled', deadline: '2020-01-01' })).toBe(false)
    expect(vm.isOverdue({ status: 'pending', deadline: '2020-01-01' })).toBe(true)
    expect(vm.isOverdue({ status: 'pending', deadline: '2099-12-31' })).toBe(false)
    expect(vm.isOverdue({ status: 'pending', deadline: '' })).toBe(false)
  })

  it('formatDate / formatDateTime 空值与正常值', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatDate('')).toBe('')
    expect(vm.formatDate('2024-01-15')).not.toBe('')
    expect(vm.formatDateTime('')).toBe('')
    expect(vm.formatDateTime('2024-01-15T10:00:00')).not.toBe('')
  })

  it('deadline 校验器：空值 / 早于开始日期 / 合法 / 无开始日期', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const validator = vm.taskRules.deadline[1].validator

    let err: any = 'unset'
    validator({}, '', (e: any) => (err = e))
    expect(err?.message).toBe('请选择截止日期')

    vm.currentTask.startDate = '2024-06-01'
    err = 'unset'
    validator({}, '2024-05-01', (e: any) => (err = e))
    expect(err?.message).toBe('截止日期不能早于开始日期')

    err = 'unset'
    validator({}, '2024-07-01', (e: any) => (err = e))
    expect(err).toBeUndefined()

    vm.currentTask.startDate = ''
    err = 'unset'
    validator({}, '2024-05-01', (e: any) => (err = e))
    expect(err).toBeUndefined()
  })

  it('handleFileChange / handleProgressFileChange 写回附件列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const files = [{ name: 'a.png', uid: '1' }]
    vm.handleFileChange({}, files)
    expect(vm.currentTask.attachments).toEqual(files) // 经响应式代理，不用 toBe
    const pFiles = [{ name: 'b.png', uid: '2' }]
    vm.handleProgressFileChange({}, pFiles)
    expect(vm.progressUpdateForm.attachments).toEqual(pFiles)
  })
})

describe('模板行渲染与内联按钮', () => {
  it('三样本行覆盖优先级/进度三元、未分配、过期标签、分配按钮 v-if、dropdown 进度项 v-if', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const text = wrapper.text()
    // 优先级标签（replace 去“优先级”后渲染）
    expect(text).toContain('任务A')
    expect(text).toContain('任务B')
    expect(text).toContain('任务C')
    // rowB assigneeName 空 → 未分配
    expect(text).toContain('未分配')
    // rowA 过期标签
    expect(text).toContain('过期')
    // 分配按钮仅 pending 的 rowA 有
    const assignBtns = wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '分配')
    expect(assignBtns.length).toBe(1)
    // 查看进度项仅非 cancelled 行渲染
    const progressItems = wrapper
      .findAll('el-dropdown-item-stub')
      .filter((b) => b.text().includes('查看进度'))
    expect(progressItems.length).toBe(2)
    const deleteItems = wrapper
      .findAll('el-dropdown-item-stub')
      .filter((b) => b.text().includes('删除任务'))
    expect(deleteItems.length).toBe(3)
  })

  it('点击行内编辑按钮 → editTask 并解析项目名', async () => {
    const wrapper = await mountReady() // 需要 projects 已加载以解析 projectId → 项目名
    const vm = wrapper.vm as any
    const btn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '编辑')!
    await btn.trigger('click')
    expect(vm.isEditMode).toBe(true)
    expect(vm.taskDialogVisible).toBe(true)
    expect(vm.currentTask.name).toBe('任务A')
    expect(vm.currentTask.projectName).toBe('项目A') // projectId 10 → 项目A
  })

  it('editTask：projectId 为空 → 不解析项目名', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.editTask({ ...rowB, projectName: '原项目乙' })
    expect(vm.isEditMode).toBe(true)
    expect(vm.currentTask.projectName).toBe('原项目乙')
  })

  it('对话框底部按钮内联赋值：取消×3 / 关闭 / 保存 / 确认分配×2 / 更新进度', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 三个“取消”按钮分别关闭三个对话框
    const cancels = wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '取消')
    expect(cancels.length).toBe(3)
    vm.taskDialogVisible = true
    vm.assignDialogVisible = true
    vm.batchAssignDialogVisible = true
    await cancels[0].trigger('click')
    await cancels[1].trigger('click')
    await cancels[2].trigger('click')
    expect(vm.taskDialogVisible).toBe(false)
    expect(vm.assignDialogVisible).toBe(false)
    expect(vm.batchAssignDialogVisible).toBe(false)

    // 进度对话框“关闭”
    const closeBtn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '关闭')!
    vm.progressDialogVisible = true
    await closeBtn.trigger('click')
    expect(vm.progressDialogVisible).toBe(false)

    // 保存（formRef 置空 → saveTask 早退，仍覆盖 @click 绑定）
    const saveBtn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '保存')!
    vm.taskFormRef = null
    await saveBtn.trigger('click')

    // 确认分配 ×2（formRef 置空 → 早退）
    const confirmBtns = wrapper
      .findAll('el-button-stub')
      .filter((b) => b.text().includes('确认分配'))
    expect(confirmBtns.length).toBe(2)
    vm.assignFormRef = null
    vm.batchAssignFormRef = null
    await confirmBtns[0].trigger('click')
    await confirmBtns[1].trigger('click')

    // 更新进度（currentTaskProgress 为空 → 早退）
    const updateBtn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '更新进度')!
    vm.currentTaskProgress = null
    await updateBtn.trigger('click')
  })

  it('点击导入/导出/批量分配/新建任务按钮 → 触发对应处理器', async () => {
    const { inputs, spy } = captureInputs()
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    const importBtn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('导入'))!
    await importBtn.trigger('click')
    expect(inputs).toHaveLength(1)

    const exportBtn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('导出'))!
    await exportBtn.trigger('click')
    expect(ElMessage.success).toHaveBeenCalledWith('任务数据导出成功')

    // 未选择时点击批量分配 → 警告
    vm.selectedTasks = []
    const batchBtn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('批量分配'))!
    await batchBtn.trigger('click')
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择需要分配的任务')

    const createBtn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('新建任务'))!
    // 模板 ref 指向的是 stub 实例（无 resetFields），点击前替换为 mock
    vm.taskFormRef = { resetFields: vi.fn(), validate: vi.fn() }
    await createBtn.trigger('click')
    expect(vm.taskDialogVisible).toBe(true)
    expect(vm.isEditMode).toBe(false)
    spy.mockRestore()
    clickSpy.mockRestore()
  })
})
