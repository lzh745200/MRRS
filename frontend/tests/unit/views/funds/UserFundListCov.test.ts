/**
 * views/funds/UserFundList.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：isManager/canEdit/canDelete 权限矩阵、fetchData 四种数据形态与异常、
 * stats 服务端/回退两种统计、loadFundStats/loadVillageOptions/loadSchoolOptions 全分支、
 * 搜索/重置/分页事件、三模式弹窗（申请/新增/编辑）与 openEditDialog 字段回退、
 * handleSubmitDialog 全分支（早退/校验失败/三模式/错误三形态）、handleDelete 全分支、
 * 字典函数、表格列模板（注入三行样本数据覆盖各行内 v-if 与 || 链两侧）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂会被提升到模块顶部注册，直接引用顶层变量会触发 TDZ；
// 所有被工厂引用的对象放入 vi.hoisted 中先行初始化。
const {
  ElMessage,
  confirmMock,
  mockGet,
  mockPost,
  mockPut,
  mockDel,
  mockApiRequest,
  getSupportedVillagesMock,
  schoolsListMock,
  logError,
  pushSafe,
  authState,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPut: vi.fn(),
  mockDel: vi.fn(),
  mockApiRequest: vi.fn(),
  getSupportedVillagesMock: vi.fn(),
  schoolsListMock: vi.fn(),
  logError: vi.fn(),
  pushSafe: vi.fn(),
  authState: { user: { role: 'admin', id: 1 } as any },
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: mockDel,
  apiRequest: mockApiRequest,
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/api/supportedVillage', () => ({
  getSupportedVillages: getSupportedVillagesMock,
}))

vi.mock('@/api/schools', () => ({
  schoolsApi: { list: schoolsListMock },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe }),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import UserFundList from '@/views/funds/UserFundList.vue'

const sampleFunds = [
  {
    id: 1,
    name: '修路经费',
    type: 'project',
    amount: 100,
    status: 'pending',
    date: '2024-01-01',
    created_by: 1,
  },
  {
    id: 2,
    name: '助学经费',
    type: 'education',
    amount: 50,
    status: 'allocated',
    date: '2024-01-02',
    created_by: 1,
  },
]

// 注入表格列模板的三行样本：分别命中各 || 链的左/中/右三段
const rowA = {
  id: 1,
  name: '修路经费',
  type: 'project',
  amount: 1234.5,
  project_name: '道路项目',
  status: 'pending',
  source: '专项',
  date: '2024-01-01',
  created_at: '',
  created_by: 1,
  fund_source: 'military',
  village_id: 3,
  school_id: 4,
  purpose: '修路',
  remarks: '备注',
}
const rowB = {
  id: 2,
  name: 'B经费',
  type: 'weird_type',
  amount: 'xyz',
  project_name: '',
  project: '村项目',
  status: 'weird_status',
  source: '',
  date: '',
  created_at: '2024-02-02T10:00:00',
  created_by: 99,
}
const rowC = {
  id: 3,
  name: '',
  type: '',
  amount: 0,
  project_name: '',
  project: '',
  status: '',
  date: '',
  created_at: '',
  created_by: 1,
}

function defaultGetImpl(url: string) {
  if (url === '/funds/statistics/overview') {
    return Promise.resolve({
      data: {
        total_amount: 1000,
        total_allocated: 600,
        by_status: { pending: { count: 3 } },
        total_count: 9,
      },
    })
  }
  return Promise.resolve({ data: {} })
}

function mountComp() {
  // el-dialog 需要具名插槽 stub（默认+footer），且仅 modelValue 为真时渲染，
  // 保持 dialogFormRef 在未打开时为 undefined（?. 短路侧）；
  // el-table-column 注入三行样本覆盖列模板各 || 链与 v-if 两侧。
  return mount(UserFundList, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-dialog': {
          name: 'ElDialog',
          props: ['modelValue', 'title'],
          emits: ['update:modelValue', 'close'],
          template:
            '<div v-if="modelValue" class="el-dialog-stub"><slot /><slot name="footer" /></div>',
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>',
          data() {
            return { rowA, rowB, rowC }
          },
        },
      },
    },
  })
}

/** 可复用的表单 ref mock（每次调用提交前需重新赋值，防止重渲染同步回 stub） */
function mockFormRef(valid = true) {
  return { validate: vi.fn((cb: (v: boolean) => void) => cb(valid)), resetFields: vi.fn() }
}

/** 打开弹窗并把 dialogFormRef 换成 mock */
async function openDialogWithMockRef(wrapper: any, opener: () => void) {
  opener()
  await nextTick()
  const vm = wrapper.vm as any
  vm.dialogFormRef = mockFormRef()
  return vm
}

beforeEach(() => {
  vi.resetAllMocks()
  authState.user = { role: 'admin', id: 1 }
  mockGet.mockImplementation(defaultGetImpl)
  mockApiRequest.mockResolvedValue({ data: { items: sampleFunds, total: 2 } })
  mockPost.mockResolvedValue({ data: {} })
  mockPut.mockResolvedValue({ data: {} })
  mockDel.mockResolvedValue({ data: {} })
  getSupportedVillagesMock.mockResolvedValue({
    data: {
      items: [
        { id: 3, village_name: '幸福村' },
        { id: 5, name: '星光村' },
      ],
    },
  })
  schoolsListMock.mockResolvedValue({
    data: {
      items: [
        { id: 4, school_name: '希望小学' },
        { id: 6, name: '育才中学' },
      ],
    },
  })
  confirmMock.mockResolvedValue(undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与初始化', () => {
  it('onMounted 并发加载列表/统计/村/校，渲染统计卡片与表格', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'GET', url: '/funds' })
    )
    expect(vm.tableData).toHaveLength(2)
    expect(vm.total).toBe(2)
    expect(vm.loading).toBe(false)
    // 服务端统计形态
    expect(vm.stats.totalAmount).toBe('1,000.00')
    expect(vm.stats.allocatedAmount).toBe('600.00')
    expect(vm.stats.pendingCount).toBe(3)
    expect(vm.stats.totalCount).toBe(9)
    // 村/校选项
    expect(vm.villageOptions).toHaveLength(2)
    expect(vm.schoolOptions).toHaveLength(2)
    expect(vm.villageLoading).toBe(false)
    expect(vm.schoolLoading).toBe(false)
    // 申请入口统一为“提交经费申请”（重复的“新增经费记录”按钮已移除）
    expect(wrapper.text()).toContain('提交经费申请')
    expect(wrapper.text()).not.toContain('新增经费记录')
    wrapper.unmount()
  })

  it('普通用户：新增按钮可见（canOperate）；viewer 只读全隐藏；user 为 null 时角色回退空串', async () => {
    authState.user = { role: 'user', id: 2 }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isManager).toBe(false)
    expect(vm.canOperate).toBe(true)
    expect(wrapper.text()).toContain('提交经费申请')
    // canEdit/canDelete 直调覆盖各臂
    expect(vm.canEdit({ created_by: 2, status: 'pending' })).toBe(true)
    expect(vm.canEdit({ created_by: 2, status: 'rejected' })).toBe(true)
    expect(vm.canEdit({ created_by: 2, status: 'approved' })).toBe(false)
    expect(vm.canEdit({ created_by: 99, status: 'pending' })).toBe(false)
    expect(vm.canDelete({ created_by: 2, status: 'pending' })).toBe(true)
    expect(vm.canDelete({ created_by: 99, status: 'pending' })).toBe(false)
    expect(vm.canDelete({ created_by: 2, status: 'approved' })).toBe(false)
    wrapper.unmount()

    // viewer 只读：按钮隐藏，canEdit/canDelete 全 false
    authState.user = { role: 'viewer', id: 3 }
    const wrapperV = mountComp()
    await flushPromises()
    const vmV = wrapperV.vm as any
    expect(vmV.canOperate).toBe(false)
    expect(wrapperV.text()).not.toContain('新增经费记录')
    expect(vmV.canEdit({ created_by: 3, status: 'pending' })).toBe(false)
    expect(vmV.canDelete({ created_by: 3, status: 'pending' })).toBe(false)
    wrapperV.unmount()

    authState.user = null
    const wrapper2 = mountComp()
    await flushPromises()
    expect((wrapper2.vm as any).isManager).toBe(false)
    expect((wrapper2.vm as any).canOperate).toBe(false)
    expect((wrapper2.vm as any).currentUserId).toBeUndefined()
    wrapper2.unmount()
  })
})

describe('fetchData 数据形态', () => {
  it('items / 嵌套 items / 裸数组 / 空对象 / 异常 五种路径', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 嵌套 data.data.items
    mockApiRequest.mockResolvedValueOnce({ data: { data: { items: [sampleFunds[0]], total: 5 } } })
    await vm.fetchData()
    expect(vm.tableData).toHaveLength(1)
    expect(vm.total).toBe(5)
    // 裸数组
    mockApiRequest.mockResolvedValueOnce({ data: [sampleFunds[0], sampleFunds[1]] })
    await vm.fetchData()
    expect(vm.tableData).toHaveLength(2)
    expect(vm.total).toBe(2)
    // 空对象 → 回退空数组 + total 回退 length
    mockApiRequest.mockResolvedValueOnce({ data: {} })
    await vm.fetchData()
    expect(vm.tableData).toEqual([])
    expect(vm.total).toBe(0)
    // 异常 → 日志
    mockApiRequest.mockRejectedValueOnce(new Error('net'))
    await vm.fetchData()
    expect(logError).toHaveBeenCalledWith('加载数据失败:', expect.any(Error))
    expect(vm.loading).toBe(false)
    wrapper.unmount()
  })
})

describe('统计回退与加载分支', () => {
  it('服务端统计缺失时回退到当前页数据（含 NaN 金额与 total 回退）', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/funds/statistics/overview') return Promise.reject(new Error('net'))
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.serverFundStats).toBeNull()
    vm.tableData = [
      { amount: 100, status: 'allocated' },
      { amount: 'abc', status: 'pending' },
      { amount: 50, status: 'completed' },
    ]
    vm.total = 0
    await nextTick()
    expect(vm.stats.totalAmount).toBe('150.00')
    expect(vm.stats.allocatedAmount).toBe('150.00')
    expect(vm.stats.pendingCount).toBe(1)
    expect(vm.stats.totalCount).toBe(3) // total=0 回退 list.length
    wrapper.unmount()
  })

  it('回退统计：allocated 行金额缺失时按 0 计入 allocatedAmount', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/funds/statistics/overview') return Promise.reject(new Error('net'))
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.tableData = [
      { amount: 100, status: 'allocated' },
      { status: 'audited' }, // amount 缺失 → Number(undefined)=NaN → || 0
    ]
    await nextTick()
    expect(vm.stats.allocatedAmount).toBe('100.00')
    wrapper.unmount()
  })

  it('loadFundStats：res.data||res 右侧、d 为空对象（?? 回退）与 {data:null}（不赋值）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 无 data 字段 → res.data || res 右侧
    mockGet.mockImplementationOnce(() => Promise.resolve({ total_amount: 5 }))
    await vm.loadFundStats()
    expect(vm.serverFundStats.total_amount).toBe(5)
    // 空对象 → 各 ?? 回退
    mockGet.mockImplementationOnce(() => Promise.resolve({ data: {} }))
    await vm.loadFundStats()
    expect(vm.stats.totalAmount).toBe('0.00')
    expect(vm.stats.pendingCount).toBe(0)
    expect(vm.stats.totalCount).toBe(vm.total)
    // data 为 null → 不覆盖
    mockGet.mockImplementationOnce(() => Promise.resolve({ data: null }))
    await vm.loadFundStats()
    expect(vm.serverFundStats).toEqual({})
    wrapper.unmount()
  })
})

describe('筛选与分页', () => {
  it('搜索/重置/分页尺寸/翻页事件与参数组装', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // v-model 绑定（关键字输入框 + 类型/状态下拉）
    const keyword = wrapper
      .findAll('el-input-stub')
      .find((i) => i.attributes('placeholder') === '名称/项目/来源')
    expect(keyword).toBeTruthy()
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    inputs[0].vm.$emit('update:modelValue', '修路')
    expect(vm.filterForm.keyword).toBe('修路')
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 'project')
    selects[1].vm.$emit('update:modelValue', 'pending')
    expect(vm.filterForm.type).toBe('project')
    expect(vm.filterForm.status).toBe('pending')
    // 回车搜索
    await keyword!.trigger('keyup.enter')
    await flushPromises()
    expect(vm.currentPage).toBe(1)
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        params: expect.objectContaining({ search: '修路', type: 'project', status: 'pending' }),
      })
    )
    // 搜索按钮
    const searchBtn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('搜索'))!
    await searchBtn.trigger('click')
    expect(mockApiRequest).toHaveBeenCalled()
    // 重置
    const resetBtn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '重置')!
    await resetBtn.trigger('click')
    expect(vm.filterForm.keyword).toBe('')
    expect(vm.filterForm.type).toBe('')
    expect(vm.filterForm.status).toBe('')
    // 分页器事件
    const pager = wrapper.findComponent({ name: 'ElPagination' })
    vm.currentPage = 3
    pager.vm.$emit('size-change', 50)
    expect(vm.currentPage).toBe(1)
    pager.vm.$emit('current-change', 2)
    pager.vm.$emit('update:currentPage', 2)
    expect(vm.currentPage).toBe(2)
    pager.vm.$emit('update:pageSize', 50)
    expect(vm.pageSize).toBe(50)
    await flushPromises()
    // 空筛选时参数为 undefined（|| 右侧）
    expect(mockApiRequest).toHaveBeenLastCalledWith(
      expect.objectContaining({
        params: expect.objectContaining({ search: undefined, type: undefined, status: undefined }),
      })
    )
    wrapper.unmount()
  })
})

describe('表格列模板', () => {
  it('三行样本覆盖名称链接/类型/金额/项目/状态/日期/操作各分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const text = wrapper.text()
    // 类型字典命中与未命中
    expect(text).toContain('项目经费')
    expect(text).toContain('weird_type')
    // 金额格式化与 NaN 回退
    expect(text).toContain('1,234.50')
    expect(text).toContain('0.00')
    // 项目名三段：project_name / project / '-'
    expect(text).toContain('道路项目')
    expect(text).toContain('村项目')
    // 状态文本命中与未命中
    expect(text).toContain('待审批')
    expect(text).toContain('weird_status')
    // 日期三段：date / created_at 截取 / '-'
    expect(text).toContain('2024-01-01')
    expect(text).toContain('2024-02-02')
    // 名称链接点击 → 查看详情
    const links = wrapper.findAll('el-link-stub')
    expect(links.length).toBeGreaterThan(0)
    await links[0].trigger('click')
    expect(pushSafe).toHaveBeenCalledWith('/funds/1')
    // 操作列按钮（管理员三行均可编辑/删除）
    const viewBtns = wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '查看')
    await viewBtns[0].trigger('click')
    expect(pushSafe).toHaveBeenCalledWith('/funds/1')
    const editBtns = wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '编辑')
    expect(editBtns.length).toBe(3)
    const vm = wrapper.vm as any
    vm.dialogFormRef = mockFormRef()
    await editBtns[0].trigger('click')
    await nextTick()
    expect(vm.dialogMode).toBe('edit')
    expect(vm.editingId).toBe(1)
    // 删除按钮：与后端一致——仅 pending 状态可删除（rowA pending 显示；weird_status/空不显示）
    const delBtns = wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '删除')
    expect(delBtns.length).toBe(1)
    await delBtns[0].trigger('click')
    await flushPromises()
    expect(mockDel).toHaveBeenCalledWith('/funds/1')
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    wrapper.unmount()
  })

  it('字典函数边界：未知与空值', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getTypeName('project')).toBe('项目经费')
    expect(vm.getTypeName('unknown')).toBe('unknown')
    expect(vm.getTypeName('')).toBe('-')
    expect(vm.getStatusType('pending')).toBe('warning')
    expect(vm.getStatusType('unknown')).toBe('info')
    expect(vm.getStatusText('allocated')).toBe('已拨付')
    expect(vm.getStatusText('unknown')).toBe('unknown')
    expect(vm.getStatusText('')).toBe('-')
    wrapper.unmount()
  })
})

describe('弹窗三模式', () => {
  it('申请/新增弹窗：标题、按钮文案、editingId 重置', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 申请
    const applyBtn = wrapper
      .findAll('el-button-stub')
      .find((b) => b.text().includes('提交经费申请'))!
    vm.dialogFormRef = mockFormRef()
    await applyBtn.trigger('click')
    await nextTick()
    expect(vm.dialogMode).toBe('apply')
    expect(vm.dialogTitle).toBe('提交经费申请')
    expect(vm.submitButtonText).toBe('提交申请')
    expect(vm.editingId).toBeNull()
    expect(vm.dialogVisible).toBe(true)
    // “新增经费记录”重复按钮已移除，页面上不应再出现
    expect(wrapper.findAll('el-button-stub').some((b) => b.text().includes('新增经费记录'))).toBe(
      false
    )
    wrapper.unmount()
  })

  it('openEditDialog 字段回退三段（全字段/部分/空）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 全字段
    vm.openEditDialog(rowA)
    expect(vm.dialogForm.name).toBe('修路经费')
    expect(vm.dialogForm.village_id).toBe(3)
    expect(vm.dialogForm.school_id).toBe(4)
    expect(vm.dialogForm.date).toBe('2024-01-01')
    // 部分字段：project 回退、created_at 截取、amount NaN→0
    vm.openEditDialog(rowB)
    expect(vm.dialogForm.project_name).toBe('村项目')
    expect(vm.dialogForm.date).toBe('2024-02-02')
    expect(vm.dialogForm.amount).toBe(0)
    expect(vm.dialogForm.village_id).toBeUndefined()
    // 空字段：全部 || 右侧
    vm.openEditDialog(rowC)
    expect(vm.dialogForm.name).toBe('')
    expect(vm.dialogForm.date).toBe('')
    expect(vm.dialogForm.project_name).toBe('')
    wrapper.unmount()
  })

  it('弹窗内 v-model 控件全量触发 + 取消按钮 + dialog v-model/close', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await openDialogWithMockRef(wrapper, () => (wrapper.vm as any).openApplyDialog())
    const vm = wrapper.vm as any
    // 表单控件 v-model
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    for (const c of inputs) c.vm.$emit('update:modelValue', 'x')
    expect(vm.dialogForm.name).toBe('x')
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    for (const c of selects) c.vm.$emit('update:modelValue', 'project')
    const number = wrapper.findComponent({ name: 'ElInputNumber' })
    number.vm.$emit('update:modelValue', 88)
    expect(vm.dialogForm.amount).toBe(88)
    const datePicker = wrapper.findComponent({ name: 'ElDatePicker' })
    datePicker.vm.$emit('update:modelValue', '2024-03-03')
    expect(vm.dialogForm.date).toBe('2024-03-03')
    // 取消按钮（内联赋值箭头）
    const cancelBtn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '取消')!
    await cancelBtn.trigger('click')
    expect(vm.dialogVisible).toBe(false)
    // dialog v-model 与 close 事件
    vm.openApplyDialog()
    await nextTick()
    const dialog = wrapper.findComponent({ name: 'ElDialog' })
    dialog.vm.$emit('update:modelValue', false)
    expect(vm.dialogVisible).toBe(false)
    // close → resetDialogForm（ref 为 stub 实例前先换 mock）
    vm.dialogFormRef = mockFormRef()
    vm.dialogForm.name = '脏数据'
    dialog.vm.$emit('close')
    expect(vm.dialogForm.name).toBe('')
    expect(vm.dialogFormRef.resetFields).toHaveBeenCalled()
    wrapper.unmount()
  })
})

describe('handleSubmitDialog', () => {
  it('ref 缺失与校验失败两条早退路径', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // dialogFormRef 为 undefined → 直接返回
    await vm.handleSubmitDialog()
    expect(mockPost).not.toHaveBeenCalled()
    // 校验失败 → 不提交
    vm.dialogFormRef = mockFormRef(false)
    await vm.handleSubmitDialog()
    expect(mockPost).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('申请模式：全字段 payload 与成功后续动作', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = await openDialogWithMockRef(wrapper, () => (wrapper.vm as any).openApplyDialog())
    Object.assign(vm.dialogForm, {
      name: '新申请',
      type: 'project',
      amount: 66,
      fund_source: 'military',
      village_id: 3,
      school_id: 4,
      project_name: '道路',
      purpose: '用途',
      remarks: '备注',
      date: '2024-04-04',
    })
    vm.dialogFormRef = mockFormRef()
    mockApiRequest.mockClear()
    mockGet.mockClear()
    await vm.handleSubmitDialog()
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith('/funds/apply', {
      name: '新申请',
      type: 'project',
      amount: 66,
      fund_source: 'military',
      village_id: 3,
      school_id: 4,
      project_name: '道路',
      purpose: '用途',
      remarks: '备注',
      date: '2024-04-04',
      status: 'pending',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('经费申请已提交，等待审批')
    expect(vm.dialogVisible).toBe(false)
    expect(vm.submitting).toBe(false)
    expect(mockApiRequest).toHaveBeenCalled()
    expect(mockGet).toHaveBeenCalledWith('/funds/statistics/overview')
    wrapper.unmount()
  })

  it('编辑模式（含 editingId 为空时不发请求）与申请模式最小 payload', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = await openDialogWithMockRef(wrapper, () => (wrapper.vm as any).openEditDialog(rowA))
    // 编辑
    vm.dialogFormRef = mockFormRef()
    await vm.handleSubmitDialog()
    await flushPromises()
    expect(mockPut).toHaveBeenCalledWith(
      '/funds/1',
      expect.objectContaining({
        name: '修路经费',
        fund_source: 'military',
        village_id: 3,
        school_id: 4,
      })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('经费记录已更新')
    // edit 模式但 editingId 为 null → 不匹配任何分支，不发请求（新增入口已并入“提交经费申请”）
    vm.dialogMode = 'edit'
    vm.editingId = null
    vm.dialogFormRef = mockFormRef()
    mockPost.mockClear()
    mockPut.mockClear()
    await vm.handleSubmitDialog()
    await flushPromises()
    expect(mockPost).not.toHaveBeenCalled()
    expect(mockPut).not.toHaveBeenCalled()
    // 申请模式：openApplyDialog 重置表单后最小 payload（|| undefined 与 if 假侧）
    vm.openApplyDialog()
    vm.dialogForm.name = '最小记录'
    vm.dialogForm.type = 'other'
    vm.dialogFormRef = mockFormRef()
    mockPost.mockClear()
    await vm.handleSubmitDialog()
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith('/funds/apply', {
      name: '最小记录',
      type: 'other',
      amount: 0,
      project_name: undefined,
      purpose: undefined,
      remarks: undefined,
      date: undefined,
      status: 'pending',
    })
    wrapper.unmount()
  })

  it('提交失败三种错误形态（detail/message/默认）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = await openDialogWithMockRef(wrapper, () => (wrapper.vm as any).openApplyDialog())
    vm.dialogForm.name = 'x'
    // detail
    vm.dialogFormRef = mockFormRef()
    mockPost.mockRejectedValueOnce({ response: { data: { detail: '名称重复' } } })
    await vm.handleSubmitDialog()
    expect(ElMessage.error).toHaveBeenCalledWith('名称重复')
    expect(vm.submitting).toBe(false)
    // message
    vm.dialogFormRef = mockFormRef()
    mockPost.mockRejectedValueOnce(new Error('网络错误'))
    await vm.handleSubmitDialog()
    expect(ElMessage.error).toHaveBeenCalledWith('网络错误')
    // 默认
    vm.dialogFormRef = mockFormRef()
    mockPost.mockRejectedValueOnce('string-error')
    await vm.handleSubmitDialog()
    expect(ElMessage.error).toHaveBeenCalledWith('操作失败')
    wrapper.unmount()
  })
})

describe('村校选项加载分支', () => {
  it('items / 嵌套 / 裸数组 / 空 / 异常五种形态与 res.data||res 右侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.villageOptions[0].village_name).toBe('幸福村')
    // 嵌套
    getSupportedVillagesMock.mockResolvedValueOnce({
      data: { data: { items: [{ id: 7, name: '嵌套村' }] } },
    })
    await vm.loadVillageOptions()
    expect(vm.villageOptions[0].name).toBe('嵌套村')
    // 裸数组（res.data || res 右侧：data 为数组本身仍走 res.data 真值）
    getSupportedVillagesMock.mockResolvedValueOnce({ data: [{ id: 8, name: '数组村' }] })
    await vm.loadVillageOptions()
    expect(vm.villageOptions[0].name).toBe('数组村')
    // 无 data 字段 → res.data || res 右侧
    getSupportedVillagesMock.mockResolvedValueOnce({ items: [{ id: 9, name: '直返村' }] })
    await vm.loadVillageOptions()
    expect(vm.villageOptions[0].name).toBe('直返村')
    // 空对象 → 回退空数组
    getSupportedVillagesMock.mockResolvedValueOnce({ data: {} })
    await vm.loadVillageOptions()
    expect(vm.villageOptions).toEqual([])
    // 异常 → 静默
    getSupportedVillagesMock.mockRejectedValueOnce(new Error('net'))
    schoolsListMock.mockRejectedValueOnce(new Error('net'))
    await vm.loadVillageOptions()
    await vm.loadSchoolOptions()
    expect(vm.villageLoading).toBe(false)
    expect(vm.schoolLoading).toBe(false)
    // 学校嵌套形态
    schoolsListMock.mockResolvedValueOnce({
      data: { data: { items: [{ id: 10, name: '嵌套校' }] } },
    })
    await vm.loadSchoolOptions()
    expect(vm.schoolOptions[0].name).toBe('嵌套校')
    // 学校：无 data 字段 → res.data || res 右侧
    schoolsListMock.mockResolvedValueOnce({ items: [{ id: 11, name: '直返校' }] })
    await vm.loadSchoolOptions()
    expect(vm.schoolOptions[0].name).toBe('直返校')
    // 学校：裸数组 → Array.isArray 分支
    schoolsListMock.mockResolvedValueOnce([{ id: 12, name: '数组校' }])
    await vm.loadSchoolOptions()
    expect(vm.schoolOptions[0].name).toBe('数组校')
    // 学校：空对象 → 回退空数组（: [] 侧）
    schoolsListMock.mockResolvedValueOnce({ data: {} })
    await vm.loadSchoolOptions()
    expect(vm.schoolOptions).toEqual([])
    wrapper.unmount()
  })
})

describe('handleDelete', () => {
  it('确认删除成功 / 取消 / 非 cancel 异常（含 toString 分支）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const row = { id: 9, name: '待删经费' }
    // 成功
    mockApiRequest.mockClear()
    await vm.handleDelete(row)
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledWith('确定要删除经费记录「待删经费」吗？', '删除确认', {
      type: 'warning',
    })
    expect(mockDel).toHaveBeenCalledWith('/funds/9')
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    expect(mockApiRequest).toHaveBeenCalled()
    // 取消（字符串 'cancel' → 第一条件短路）
    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleDelete(row)
    expect(ElMessage.error).not.toHaveBeenCalled()
    // 异常带 toString（Error 对象 → 第二条件评估）
    confirmMock.mockResolvedValueOnce(undefined)
    mockDel.mockRejectedValueOnce(new Error('cancel'))
    await vm.handleDelete(row)
    expect(ElMessage.error).toHaveBeenCalledWith('cancel')
    // del 失败带 detail
    mockDel.mockRejectedValueOnce({ response: { data: { detail: '外键约束' } } })
    await vm.handleDelete(row)
    expect(ElMessage.error).toHaveBeenCalledWith('外键约束')
    // del 失败默认形态
    mockDel.mockRejectedValueOnce('oops')
    await vm.handleDelete(row)
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
    wrapper.unmount()
  })
})
