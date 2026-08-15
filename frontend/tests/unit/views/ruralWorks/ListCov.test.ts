/**
 * views/ruralWorks/List.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 四路加载全分支（年限含/不含当前年/空数组/失败、村庄失败、
 * 统计 完整/部分 ?? 兜底/null/失败）、statsCards 服务端与本地 filter 回退两侧、
 * fetchData 参数 || undefined 与 items/total || 兜底及失败、
 * 搜索/筛选/重置/分页全部模板事件与 v-model 同步、
 * 对话框三模式（标题/页脚 v-if 两侧）与表单全部 v-model、取消/保存内联点击、
 * handleSave formRef 空/校验失败/新增/编辑/四级错误兜底、
 * handleDelete 取消/成功/三级错误兜底、表格行内 查看/编辑/删除 真实点击、
 * handleExport 空警告与 CSV 字段 ||/?? 全兜底、
 * 表格列三样本行覆盖 类型/状态 映射与回退、进度三元三侧、ds 脱敏渲染。
 *
 * 说明：组件通过并发 `await import('@/api/ruralWork')` 调接口，vi.mock 该模块时
 * 并发动态导入存在竞态（部分调用解析到真实模块）。因此本 spec 只 mock 更底层的
 * '@/api/request'（OtherViewsBatch 同款模式），让真实 API 薄封装打到 mock get/post/put/del 上。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂提升求值，所有被引用对象须先放入 vi.hoisted 初始化（TDZ）
const { ElMessage, confirmMock, mockGet, mockPost, mockPut, mockDel, mockDs, logError } =
  vi.hoisted(() => ({
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
    confirmMock: vi.fn(),
    mockGet: vi.fn(),
    mockPost: vi.fn(),
    mockPut: vi.fn(),
    mockDel: vi.fn(),
    mockDs: vi.fn(),
    logError: vi.fn(),
  }))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/composables/useDesensitize', () => ({
  useDesensitize: () => ({ ds: mockDs }),
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: mockDel,
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import List from '@/views/ruralWorks/List.vue'

const CUR_YEAR = new Date().getFullYear()

// fetchData 默认数据：四种状态齐全，statsCards 本地回退 filter 真/假两侧均有样本
const apiItems = [
  {
    id: 1,
    name: '修路工程',
    type: 'infrastructure',
    status: 'in_progress',
    progress: 50,
    village_name: '幸福村',
    responsible_person: '张三',
    start_date: '2025-01-01',
    end_date: '2025-06-01',
    description: '修路',
  },
  {
    id: 2,
    name: '技能培训班',
    type: 'education',
    status: 'completed',
    progress: 100,
    village_name: '民主村',
    responsible_person: '李四',
    start_date: '2025-02-01',
    end_date: '2025-03-01',
    description: '',
  },
  {
    id: 3,
    name: '蔬菜大棚',
    type: 'industry',
    status: 'delayed',
    progress: 30,
    village_name: '胜利村',
    responsible_person: '王五',
    start_date: '',
    end_date: '',
    description: '大棚',
  },
  {
    id: 4,
    name: '医疗规划',
    type: 'healthcare',
    status: 'planned',
    progress: 0,
    village_name: '',
    responsible_person: '',
    start_date: '',
    end_date: '',
    description: '',
  },
]

// 表格列 stub 注入三行样本：
// rowX 已知类型/已知状态/进度100（三元 ===100 侧）；
// rowY 未知类型/未知状态（|| 回退两侧）/进度70（>60 侧）/负责人空；
// rowZ 已知类型/进行中/进度30（warning 侧）
const rowX = {
  id: 11,
  name: '样本X',
  type: 'infrastructure',
  status: 'completed',
  progress: 100,
  responsible_person: '张三',
  village_name: '幸福村',
}
const rowY = {
  id: 22,
  name: '样本Y',
  type: 'alien_type',
  status: 'alien_status',
  progress: 70,
  responsible_person: '',
  village_name: '',
}
const rowZ = {
  id: 33,
  name: '样本Z',
  type: 'industry',
  status: 'in_progress',
  progress: 30,
  responsible_person: '李四',
  village_name: '胜利村',
}

// 各端点响应由可变变量控制（onMounted 并发请求，不能用 mockResolvedValueOnce 定序）
let listResult: any
let listError: any
let statsResult: any
let statsError: any
let yearsResult: any
let yearsError: any
let villagesResult: any
let villagesError: any

function defaultGetImpl(url: string): Promise<any> {
  if (url === '/rural-works/statistics/summary') {
    return statsError ? Promise.reject(statsError) : Promise.resolve(statsResult)
  }
  if (url === '/rural-works/years') {
    return yearsError ? Promise.reject(yearsError) : Promise.resolve(yearsResult)
  }
  if (url === '/rural-works/villages') {
    return villagesError ? Promise.reject(villagesError) : Promise.resolve(villagesResult)
  }
  if (url === '/rural-works') {
    return listError ? Promise.reject(listError) : Promise.resolve(listResult)
  }
  return Promise.resolve({})
}

/** 列表请求调用（URL 精确匹配，排除 statistics/years/villages 子路径） */
function listCalls() {
  return mockGet.mock.calls.filter((c: any[]) => c[0] === '/rural-works')
}

function mountComp() {
  // setup.ts 全局 el-* stub 默认不渲染插槽，需 renderStubDefaultSlot；
  // 具名插槽（dialog footer / input prefix）与作用域插槽（表格行）需自定义 stub
  return mount(List, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-table': { name: 'ElTable', template: '<div class="el-table-stub"><slot /></div>' },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowX" /><slot :row="rowY" /><slot :row="rowZ" /></div>',
          data() {
            return { rowX, rowY, rowZ }
          },
        },
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
        },
        'el-input': {
          name: 'ElInput',
          template: '<div class="el-input-stub"><slot name="prefix" /><slot /></div>',
        },
        'el-select': { name: 'ElSelect', template: '<div class="el-select-stub"><slot /></div>' },
        'el-date-picker': { name: 'ElDatePicker', template: '<div class="el-date-picker-stub" />' },
        'el-slider': { name: 'ElSlider', template: '<div class="el-slider-stub" />' },
        'el-pagination': { name: 'ElPagination', template: '<div class="el-pagination-stub" />' },
        'el-progress': {
          name: 'ElProgress',
          props: ['percentage', 'status', 'strokeWidth'],
          template: '<div class="el-progress-stub" />',
        },
        'el-form': { name: 'ElForm', template: '<form class="el-form-stub"><slot /></form>' },
      },
    },
  })
}

function findBtn(wrapper: any, text: string) {
  const btn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes(text))
  expect(btn, `按钮「${text}」`).toBeTruthy()
  return btn!
}

beforeEach(() => {
  vi.resetAllMocks()
  mockDs.mockImplementation((v: any) =>
    v === null || v === undefined || v === '' ? '' : `ds:${v}`
  )
  listResult = { items: apiItems, total: 4 }
  listError = null
  statsResult = { total: 10, in_progress: 3, completed: 5, delayed: 2 }
  statsError = null
  yearsResult = [CUR_YEAR - 2, CUR_YEAR - 1, CUR_YEAR]
  yearsError = null
  villagesResult = [{ id: 1, name: '幸福村' }]
  villagesError = null
  mockGet.mockImplementation(defaultGetImpl)
  mockPost.mockResolvedValue({ id: 100 })
  mockPut.mockResolvedValue({})
  mockDel.mockResolvedValue({})
  confirmMock.mockResolvedValue('confirm')
})

describe('挂载与初始加载', () => {
  it('onMounted 四路加载成功：数据/统计/年限（含当前年）/村庄，渲染统计卡与表格样本列', async () => {
    const wrapper = mountComp()
    // 首个用例承担 '@/api/ruralWork' 真实模块的加载成本，等动态导入全部落地再断言
    await vi.dynamicImportSettled()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(mockGet).toHaveBeenCalledWith('/rural-works', {
      skip: 0,
      limit: 10,
      search: undefined,
      status: undefined,
      type: undefined,
      year: undefined,
    })
    expect(mockGet).toHaveBeenCalledWith('/rural-works/statistics/summary')
    expect(mockGet).toHaveBeenCalledWith('/rural-works/years')
    expect(mockGet).toHaveBeenCalledWith('/rural-works/villages')
    expect(vm.tableData).toHaveLength(4)
    expect(vm.total).toBe(4)
    expect(vm.loading).toBe(false)

    // 服务端统计优先（?? 左侧全覆盖）
    expect(vm.statsCards).toEqual([
      { label: '工作总数', value: 10, color: 'var(--color-primary)' },
      { label: '进行中', value: 3, color: 'var(--color-warning)' },
      { label: '已完成', value: 5, color: 'var(--color-success)' },
      { label: '已延期', value: 2, color: 'var(--color-danger)' },
    ])
    expect(wrapper.text()).toContain('工作总数')

    // 年限含当前年 → 不 unshift；村庄选项就绪
    expect(vm.yearOptions).toEqual([CUR_YEAR - 2, CUR_YEAR - 1, CUR_YEAR])
    expect(vm.villageOptions).toEqual([{ id: 1, name: '幸福村' }])

    // 表格列样本：类型映射与回退、状态映射与回退、ds 脱敏
    const text = wrapper.text()
    expect(text).toContain('基础设施建设') // rowX typeLabels 命中
    expect(text).toContain('alien_type') // rowY typeLabels 回退
    expect(text).toContain('已完成') // rowX statusLabels 命中
    expect(text).toContain('alien_status') // rowY statusLabels 回退
    expect(text).toContain('ds:张三')

    // 进度三元三侧
    const progresses = wrapper.findAllComponents({ name: 'ElProgress' })
    expect(progresses.map((p: any) => p.props('status'))).toEqual(['success', '', 'warning'])
  })

  it('getTypeTagColor：映射命中与 || info 回退', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.getTypeTagColor('infrastructure')).toBe('primary')
    expect(vm.getTypeTagColor('industry')).toBe('success')
    expect(vm.getTypeTagColor('education')).toBe('warning')
    expect(vm.getTypeTagColor('healthcare')).toBe('danger')
    expect(vm.getTypeTagColor('environment')).toBe('info')
    expect(vm.getTypeTagColor('unknown')).toBe('info')
  })

  it('年限：不含当前年 → unshift；空数组与接口失败 → generateDefaultYears 兜底', async () => {
    yearsResult = [2020]
    const w1 = mountComp()
    await flushPromises()
    expect((w1.vm as any).yearOptions[0]).toBe(CUR_YEAR)
    expect((w1.vm as any).yearOptions).toContain(2020)

    yearsResult = []
    const w2 = mountComp()
    await flushPromises()
    expect((w2.vm as any).yearOptions).toHaveLength(6)
    expect((w2.vm as any).yearOptions[0]).toBe(CUR_YEAR)

    yearsError = new Error('years')
    const w3 = mountComp()
    await flushPromises()
    expect((w3.vm as any).yearOptions).toHaveLength(6)
  })

  it('村庄列表加载失败 → 空数组并记录日志', async () => {
    villagesError = new Error('villages')
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).villageOptions).toEqual([])
    expect(logError).toHaveBeenCalledWith('加载村庄列表失败', expect.any(Error))
  })

  it('统计接口失败/返回 null → 本地回退统计（filter 三状态 + total||length 两侧）', async () => {
    // 失败 → catch 静默，serverStats 保持 null → 本地回退（total 4 真侧）
    statsError = new Error('stats')
    const w1 = mountComp()
    await flushPromises()
    expect((w1.vm as any).serverStats).toBeNull()
    expect((w1.vm as any).statsCards.map((c: any) => c.value)).toEqual([4, 1, 1, 1])

    // null → if(stats) 假侧；total=0 → total||data.length 右側
    statsError = null
    statsResult = null
    listResult = { items: [{ id: 8 }, { id: 9 }], total: 0 }
    const w2 = mountComp()
    await flushPromises()
    expect((w2.vm as any).serverStats).toBeNull()
    expect((w2.vm as any).statsCards[0].value).toBe(2)
  })

  it('统计部分字段缺失 → ?? 0 兜底', async () => {
    statsResult = {}
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).statsCards.map((c: any) => c.value)).toEqual([0, 0, 0, 0])
  })
})

describe('fetchData 参数与失败', () => {
  it('带搜索/状态/类型/年度参数调用；items/total 缺省 → || 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentPage = 3
    vm.searchText = '修路'
    vm.filterStatus = 'planned'
    vm.filterType = 'industry'
    vm.filterYear = CUR_YEAR

    vm.handleSearch() // 页码归 1 并重新加载
    await flushPromises()
    expect(vm.currentPage).toBe(1)
    expect(listCalls().at(-1)![1]).toEqual({
      skip: 0,
      limit: 10,
      search: '修路',
      status: 'planned',
      type: 'industry',
      year: CUR_YEAR,
    })

    listResult = {}
    await vm.fetchData()
    expect(vm.tableData).toEqual([])
    expect(vm.total).toBe(0)
  })

  it('加载失败 → 错误提示并清空数据', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    listError = new Error('net')
    await vm.fetchData()
    expect(ElMessage.error).toHaveBeenCalledWith('加载数据失败')
    expect(logError).toHaveBeenCalledWith('加载数据失败', expect.any(Error))
    expect(vm.tableData).toEqual([])
    expect(vm.total).toBe(0)
    expect(vm.loading).toBe(false)
  })
})

describe('筛选与分页模板交互', () => {
  it('搜索框 v-model / clear / keyup.enter 与三个筛选 select 的 v-model / change', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const base = listCalls().length

    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    inputs[0].vm.$emit('update:modelValue', '大棚')
    expect(vm.searchText).toBe('大棚')

    inputs[0].vm.$emit('clear')
    await flushPromises()
    expect(listCalls().length).toBe(base + 1)

    inputs[0].vm.$emit('keyup', { key: 'Enter' })
    await flushPromises()
    expect(listCalls().length).toBe(base + 2)

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 'completed')
    selects[1].vm.$emit('update:modelValue', 'education')
    selects[2].vm.$emit('update:modelValue', CUR_YEAR - 1)
    expect(vm.filterStatus).toBe('completed')
    expect(vm.filterType).toBe('education')
    expect(vm.filterYear).toBe(CUR_YEAR - 1)

    for (let i = 0; i < 3; i++) {
      selects[i].vm.$emit('change', 'x')
    }
    await flushPromises()
    expect(listCalls().length).toBe(base + 5)
  })

  it('分页：size-change / current-change 触发搜索，两个 v-model 同步', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const pagination = wrapper.findAllComponents({ name: 'ElPagination' })[0]

    pagination.vm.$emit('update:currentPage', 3)
    pagination.vm.$emit('update:pageSize', 20)
    expect(vm.currentPage).toBe(3)
    expect(vm.pageSize).toBe(20)

    const base = listCalls().length
    pagination.vm.$emit('current-change', 2)
    pagination.vm.$emit('size-change', 50)
    await flushPromises()
    expect(listCalls().length).toBe(base + 2)
    expect(vm.currentPage).toBe(1) // handleSearch 归 1
  })

  it('点击「重置」清空全部筛选并刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchText = 'x'
    vm.filterStatus = 'planned'
    vm.filterType = 'industry'
    vm.filterYear = CUR_YEAR
    vm.currentPage = 5

    const base = listCalls().length
    await findBtn(wrapper, '重置').trigger('click')
    await flushPromises()
    expect(vm.searchText).toBe('')
    expect(vm.filterStatus).toBe('')
    expect(vm.filterType).toBe('')
    expect(vm.filterYear).toBe('')
    expect(vm.currentPage).toBe(1)
    expect(listCalls().length).toBe(base + 1)
  })
})

describe('对话框与表单交互', () => {
  it('新增工作：打开对话框并重置表单，全部表单 v-model 同步', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.name = '脏数据'

    await findBtn(wrapper, '新增工作').trigger('click')
    await nextTick()
    expect(vm.dialogMode).toBe('create')
    expect(vm.dialogVisible).toBe(true)
    expect(vm.dialogTitle).toBe('新增乡村工作')
    expect(vm.formData.name).toBe('') // resetForm
    expect(vm.formData.status).toBe('planned')

    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    inputs[1].vm.$emit('update:modelValue', '新工作')
    inputs[2].vm.$emit('update:modelValue', '赵六')
    inputs[3].vm.$emit('update:modelValue', '工作描述')
    expect(vm.formData.name).toBe('新工作')
    expect(vm.formData.responsible_person).toBe('赵六')
    expect(vm.formData.description).toBe('工作描述')

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[3].vm.$emit('update:modelValue', 'environment')
    selects[4].vm.$emit('update:modelValue', 'delayed')
    selects[5].vm.$emit('update:modelValue', 1)
    expect(vm.formData.type).toBe('environment')
    expect(vm.formData.status).toBe('delayed')
    expect(vm.formData.village_id).toBe(1)

    const pickers = wrapper.findAllComponents({ name: 'ElDatePicker' })
    pickers[0].vm.$emit('update:modelValue', '2025-04-01')
    pickers[1].vm.$emit('update:modelValue', '2025-09-30')
    expect(vm.formData.start_date).toBe('2025-04-01')
    expect(vm.formData.end_date).toBe('2025-09-30')

    wrapper.findAllComponents({ name: 'ElSlider' })[0].vm.$emit('update:modelValue', 55)
    expect(vm.formData.progress).toBe(55)

    // 对话框 v-model 同步
    wrapper.findAllComponents({ name: 'ElDialog' })[0].vm.$emit('update:modelValue', false)
    expect(vm.dialogVisible).toBe(false)
  })

  it('查看模式：标题/页脚 v-if 假侧；编辑模式：标题与数据回填', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.handleView(rowX)
    await nextTick()
    expect(vm.dialogTitle).toBe('查看乡村工作')
    expect(vm.formData.id).toBe(11)
    expect(wrapper.findAll('el-button-stub').some((b: any) => b.text().includes('保存'))).toBe(
      false
    ) // dialogMode==='view' → 页脚不渲染

    vm.handleEdit(rowZ)
    await nextTick()
    expect(vm.dialogTitle).toBe('编辑乡村工作')
    expect(vm.formData.id).toBe(33)
    findBtn(wrapper, '保存') // 页脚恢复渲染
  })

  it('点击「取消」内联关闭对话框', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleCreate()
    await nextTick()
    expect(vm.dialogVisible).toBe(true)

    await findBtn(wrapper, '取消').trigger('click')
    await nextTick()
    expect(vm.dialogVisible).toBe(false)
  })
})

describe('handleSave', () => {
  it('formRef 为空 → 早退；校验失败 → 早退', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.formRef = null
    await vm.handleSave()
    expect(mockPost).not.toHaveBeenCalled()

    vm.formRef = { validate: vi.fn().mockRejectedValue(new Error('invalid')) }
    await vm.handleSave()
    expect(mockPost).not.toHaveBeenCalled()
    expect(vm.saving).toBe(false)
  })

  it('新增成功：点击「保存」按钮走 create 分支并刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleCreate()
    await nextTick()
    vm.formData.name = '新工作'
    vm.formData.type = 'industry'

    const base = listCalls().length
    vm.formRef = { validate: vi.fn().mockResolvedValue(true) } // 重渲染前赋值，点击前有效
    await findBtn(wrapper, '保存').trigger('click')
    await flushPromises()

    expect(mockPost).toHaveBeenCalledWith(
      '/rural-works',
      expect.objectContaining({ name: '新工作', type: 'industry', status: 'planned', progress: 0 })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('新增成功')
    expect(vm.dialogVisible).toBe(false)
    expect(vm.saving).toBe(false)
    expect(listCalls().length).toBe(base + 1)
  })

  it('编辑成功：走 update 分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleEdit(apiItems[0])
    vm.formRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleSave()

    expect(mockPut).toHaveBeenCalledWith(
      '/rural-works/1',
      expect.objectContaining({ name: '修路工程', type: 'infrastructure' })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('保存成功')
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('保存失败：detail / message / error.message / 默认 四级兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const failWith = async (err: any, expected: string) => {
      mockPost.mockRejectedValueOnce(err)
      vm.formRef = { validate: vi.fn().mockResolvedValue(true) } // 每次调用前重新赋值
      await vm.handleSave()
      expect(ElMessage.error).toHaveBeenCalledWith(expected)
      expect(vm.saving).toBe(false)
    }
    await failWith({ response: { data: { detail: 'D-详情' } } }, 'D-详情')
    await failWith({ response: { data: { message: 'M-消息' } } }, 'M-消息')
    await failWith(new Error('E-异常'), 'E-异常')
    await failWith({}, '保存失败，请稍后重试')
  })
})

describe('handleDelete', () => {
  it('确认框取消 → 静默返回不发请求', async () => {
    confirmMock.mockRejectedValue('cancel')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete({ id: 1 })
    expect(mockDel).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('删除成功 → 提示并刷新列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const base = listCalls().length
    await vm.handleDelete({ id: 9 })
    expect(confirmMock).toHaveBeenCalledWith(
      '确认删除该工作项？此操作不可恢复。',
      '警告',
      expect.objectContaining({ type: 'warning' })
    )
    expect(mockDel).toHaveBeenCalledWith('/rural-works/9')
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    expect(listCalls().length).toBe(base + 1)
  })

  it('删除失败：detail / error.message / 默认 三级兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const failWith = async (err: any, expected: string) => {
      mockDel.mockRejectedValueOnce(err)
      await vm.handleDelete({ id: 1 })
      expect(ElMessage.error).toHaveBeenCalledWith(expected)
    }
    await failWith({ response: { data: { detail: 'DD-详情' } } }, 'DD-详情')
    await failWith(new Error('DE-异常'), 'DE-异常')
    await failWith({}, '删除失败')
  })

  it('表格行内「查看/编辑/删除」按钮真实点击（内联 row 参数箭头）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const columns = wrapper.findAllComponents({ name: 'ElTableColumn' })
    const opCol = columns[columns.length - 1]
    const btns = opCol.findAll('el-button-stub')
    // 每行 3 按钮：[查看, 编辑, 删除] × rowX/rowY/rowZ
    const byText = (t: string) => btns.filter((b: any) => b.text().includes(t))

    await byText('查看')[0].trigger('click')
    await nextTick()
    expect(vm.dialogMode).toBe('view')
    expect(vm.formData.id).toBe(11)

    await byText('编辑')[1].trigger('click')
    await nextTick()
    expect(vm.dialogMode).toBe('edit')
    expect(vm.formData.id).toBe(22)

    await byText('删除')[2].trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalled()
    expect(mockDel).toHaveBeenCalledWith('/rural-works/33')
  })
})

describe('导出 CSV', () => {
  it('无数据 → 警告不导出', async () => {
    listResult = { items: [], total: 0 }
    const wrapper = mountComp()
    await flushPromises()

    await findBtn(wrapper, '导出').trigger('click')
    expect(ElMessage.warning).toHaveBeenCalledWith('没有可导出的数据')
  })

  it('导出成功：字段 || / ?? 全兜底与引号转义，触发下载', async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.tableData = [
      // 全字段（各 || 左侧、?? 左侧）
      {
        name: '完整项',
        type: 'industry',
        status: 'delayed',
        progress: 80,
        village_name: '幸福村',
        responsible_person: '张三',
        start_date: '2025-01-01',
        end_date: '2025-02-01',
        description: '描述',
      },
      // 未知类型/状态回退原名，progress undefined → ?? 0，名称含引号
      { name: '含"引号', type: 'alien', status: 'alien', progress: undefined },
      // 全缺省（name/type/status 空 → || '' 末端）
      {},
    ]

    await findBtn(wrapper, '导出').trigger('click')
    expect(clickSpy).toHaveBeenCalled()
    expect(ElMessage.warning).not.toHaveBeenCalled()
    clickSpy.mockRestore()
  })
})

describe('loadVillages 补充', () => {
  it('数组/items/data/失败 四种形态', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // getVillagesForSelect 内部调 get('/rural-works/villages') → 由 mockGet 控制响应形态
    mockGet.mockResolvedValueOnce([{ id: 1, name: 'A' }])
    await vm.loadVillages()
    expect(vm.villageOptions.length).toBe(1)
    mockGet.mockResolvedValueOnce({ items: [{ id: 2, name: 'B' }] })
    await vm.loadVillages()
    expect(vm.villageOptions.length).toBe(1)
    mockGet.mockResolvedValueOnce({ data: [{ id: 3, name: 'C' }] })
    await vm.loadVillages()
    expect(vm.villageOptions.length).toBe(1)
    mockGet.mockRejectedValueOnce(new Error('x'))
    await vm.loadVillages()
    expect(vm.villageOptions).toEqual([])
  })
})

describe('村庄信封补充', () => {
  it('getVillagesForSelect {data:[...]} 信封 → 选项', async () => {
    const wrapper = mountComp()
    await flushPromises()
    ;(mockGet as any).mockResolvedValueOnce({ data: [{ id: 1, name: 'A村' }] })
    await (wrapper.vm as any).loadVillages()
    expect((wrapper.vm as any).villageOptions).toEqual([{ id: 1, name: 'A村' }])
    wrapper.unmount()
  })
  it('getVillagesForSelect 空对象 → 空选项', async () => {
    const wrapper = mountComp()
    await flushPromises()
    ;(mockGet as any).mockResolvedValueOnce({})
    await (wrapper.vm as any).loadVillages()
    expect((wrapper.vm as any).villageOptions).toEqual([])
    wrapper.unmount()
  })
})
