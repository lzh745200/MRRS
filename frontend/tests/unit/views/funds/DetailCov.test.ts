/**
 * views/funds/Detail.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：三种页面模式（查看/创建/编辑）、loadFundDetail/loadAllHistory 全分支、
 * isManager/canEditFund computed、六状态工作流按钮与 submitWorkflow 全 action、
 * 附件上传/预览/下载/删除、handleSubmit 创建/编辑/失败分支、handleDelete、
 * watch(route.path)、onBeforeUnmount 资源清理、全部字典/格式化辅助函数，
 * 以及模板 v-model 箭头、内联三元/赋值按钮、el-popconfirm confirm 箭头。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'

// vi.mock 工厂会被提升到模块顶部注册，直接引用下方 const 会触发 TDZ；
// 所有被工厂引用的对象放入 vi.hoisted 中先行初始化。
const {
  ElMessage,
  ElNotification,
  confirmMock,
  mockGet,
  mockPost,
  mockPut,
  mockDel,
  logError,
  pushSafe,
  dsMock,
  routeHolder,
  authState,
  listAttachments,
  getAttachmentBlob,
  downloadAttachmentMock,
  deleteAttachmentMock,
  approveMock,
  rejectMock,
  allocateMock,
  startUseMock,
  completeMock,
  auditMock,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  ElNotification: vi.fn(),
  confirmMock: vi.fn(),
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPut: vi.fn(),
  mockDel: vi.fn(),
  logError: vi.fn(),
  pushSafe: vi.fn(),
  dsMock: vi.fn(),
  // useRoute 返回值持有者：beforeEach 中重建为 reactive 对象以支持 watch
  routeHolder: { current: null as any },
  authState: { user: { role: 'admin', id: 1 } as any },
  listAttachments: vi.fn(),
  getAttachmentBlob: vi.fn(),
  downloadAttachmentMock: vi.fn(),
  deleteAttachmentMock: vi.fn(),
  approveMock: vi.fn(),
  rejectMock: vi.fn(),
  allocateMock: vi.fn(),
  startUseMock: vi.fn(),
  completeMock: vi.fn(),
  auditMock: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElNotification,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: mockPut,
  del: mockDel,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/api/funds', () => ({
  fundApi: {
    approve: approveMock,
    reject: rejectMock,
    allocate: allocateMock,
    startUse: startUseMock,
    complete: completeMock,
    audit: auditMock,
    listAttachments,
    getAttachmentBlob,
    downloadAttachment: downloadAttachmentMock,
    deleteAttachment: deleteAttachmentMock,
  },
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeHolder.current,
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe }),
}))

vi.mock('@/composables/useDesensitize', () => ({
  useDesensitize: () => ({ ds: dsMock }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import Detail from '@/views/funds/Detail.vue'

// 详情数据（全字段真值）
const fundDetail = {
  id: 5,
  code: 'F001',
  name: '修路经费',
  date: '2024-01-10',
  type: 'project',
  fund_source: 'military',
  source: 'government',
  amount: 100,
  planned_amount: 90,
  approved_amount: 80,
  allocated_amount: 70,
  used_amount: 60,
  remaining_amount: 10,
  project_id: 'p1',
  project_name: '道路硬化',
  village_id: 3,
  school_id: null,
  purpose: '修路',
  operator: '经办人',
  applicant: '申请人',
  receiver: '接收人',
  usage_description: '使用说明',
  approved_by: '审批人',
  approval_date: '2024-01-11T00:00:00',
  allocation_date: '2024-01-12T00:00:00',
  allocation_method: '银行转账',
  start_date: '2024-01-13T00:00:00',
  end_date: '2024-12-31T00:00:00',
  audit_date: '2025-01-01T00:00:00',
  audit_result: '通过',
  audit_opinion: '无意见',
  status: 'pending',
  remarks: '备注',
  created_by: 1,
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-01-02T00:00:00',
}

// 状态日志：from_status 空 → '新建' 兜底；remark 有/无两侧；operator_name 空 → '-'
const statusItems = [
  {
    id: 1,
    from_status: '',
    to_status: 'pending',
    operator_name: '张三',
    operation_time: '2024-01-01T00:00:00',
    remark: '提交申请',
  },
  {
    id: 2,
    from_status: 'pending',
    to_status: 'approved',
    operator_name: '',
    operation_time: '',
    remark: '',
  },
]
const fieldItems = [
  {
    id: 1,
    field_name: '金额',
    old_value: '1',
    new_value: '2',
    changed_by_name: '李四',
    changed_at: '2024-01-02T00:00:00',
  },
]
const operationItems = [
  {
    id: 1,
    operation_type: 'attachment_upload',
    operation_detail: '{"a":1}',
    operator_name: '王五',
    created_at: '2024-01-03T00:00:00',
  },
]
const attachmentItems = [
  {
    id: 11,
    file_name: '合同.pdf',
    category: 'contract',
    file_size: 2048,
    uploaded_by: '张三',
    created_at: '2024-01-01T00:00:00',
  },
]

// el-table-column stub 注入的两行样本：覆盖列模板 || '-' 两侧、分类/大小/操作类型映射
const rowX = {
  id: 11,
  file_name: '合同.pdf',
  category: 'contract',
  file_size: 2048,
  uploaded_by: '张三',
  created_at: '2024-01-01T00:00:00',
  field_name: '金额',
  old_value: '1',
  new_value: '2',
  changed_by_name: '李四',
  changed_at: '2024-01-02T00:00:00',
  operation_type: 'attachment_upload',
  operation_detail: '{"a":1}',
  operator_name: '王五',
}
const rowY = {
  id: 12,
  file_name: '',
  category: 'alien',
  file_size: 0,
  uploaded_by: '',
  created_at: '',
  field_name: '备注',
  old_value: '',
  new_value: '',
  changed_by_name: '',
  changed_at: '',
  operation_type: 'mystery',
  operation_detail: '',
  operator_name: '',
}

function defaultGetImpl(url: string) {
  if (url === '/funds/5') return Promise.resolve({ data: { ...fundDetail } })
  if (url === '/funds/5/history/status')
    return Promise.resolve({ data: { items: [...statusItems] } })
  if (url === '/funds/5/history/fields')
    return Promise.resolve({ data: { items: [...fieldItems] } })
  if (url === '/funds/5/history/operations')
    return Promise.resolve({ data: { items: [...operationItems] } })
  return Promise.resolve({ data: {} })
}

/** 设置当前路由（查看 /funds/5、创建 /funds/create、编辑 /funds/5/edit、无 id /funds/） */
function setRoute(path: string, id?: string) {
  routeHolder.current = reactive({ params: id ? { id } : {}, path })
}

function mountComp() {
  // setup.ts 的全局 el-* stub 默认不渲染插槽，需 renderStubDefaultSlot；
  // 具名插槽（footer/reference）与作用域插槽（表格行）需自定义 stub。
  return mount(Detail, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
        },
        'el-popconfirm': {
          name: 'ElPopconfirm',
          template: '<span class="el-popconfirm-stub"><slot name="reference" /></span>',
        },
        'el-tabs': { name: 'ElTabs', template: '<div class="el-tabs-stub"><slot /></div>' },
        'el-input': { name: 'ElInput', template: '<div class="el-input-stub" />' },
        'el-select': { name: 'ElSelect', template: '<div class="el-select-stub"><slot /></div>' },
        'el-date-picker': { name: 'ElDatePicker', template: '<div class="el-date-picker-stub" />' },
        'el-input-number': {
          name: 'ElInputNumber',
          template: '<div class="el-input-number-stub" />',
        },
        // 注入两行样本数据，覆盖列模板 v-if/v-else 与 || '-' 两侧
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowX" /><slot :row="rowY" /></div>',
          data() {
            return { rowX, rowY }
          },
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  setRoute('/funds/5', '5')
  authState.user = { role: 'admin', id: 1 }
  mockGet.mockImplementation(defaultGetImpl)
  mockPost.mockResolvedValue({})
  mockPut.mockResolvedValue({})
  mockDel.mockResolvedValue({})
  confirmMock.mockResolvedValue(undefined)
  dsMock.mockImplementation((v: any) => v)
  listAttachments.mockResolvedValue({ items: [...attachmentItems] })
  getAttachmentBlob.mockResolvedValue(new Blob(['x']))
  downloadAttachmentMock.mockResolvedValue(undefined)
  deleteAttachmentMock.mockResolvedValue(undefined)
  approveMock.mockResolvedValue({})
  rejectMock.mockResolvedValue({})
  allocateMock.mockResolvedValue({})
  startUseMock.mockResolvedValue({})
  completeMock.mockResolvedValue({})
  auditMock.mockResolvedValue({})
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('页面模式与数据加载', () => {
  it('查看模式：loading 过渡后加载详情与全部历史/附件', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    // loading v-if 侧（onMounted 的 await 未完成）
    expect(wrapper.find('.loading-container').exists()).toBe(true)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/funds/5')
    expect(mockGet).toHaveBeenCalledWith('/funds/5/history/status')
    expect(mockGet).toHaveBeenCalledWith('/funds/5/history/fields')
    expect(mockGet).toHaveBeenCalledWith('/funds/5/history/operations')
    expect(listAttachments).toHaveBeenCalledWith(5)
    expect(vm.loading).toBe(false)
    expect(vm.fundData.name).toBe('修路经费')
    expect(vm.statusHistory).toHaveLength(2)
    expect(vm.fieldChanges).toHaveLength(1)
    expect(vm.operationLogs).toHaveLength(1)
    expect(vm.attachments).toHaveLength(1)
    expect(wrapper.text()).toContain('经费详情')
    expect(wrapper.text()).toContain('F001')
    expect(wrapper.text()).toContain('道路硬化')
    // 状态历史渲染：remark 有/无、操作人 '-' 兜底
    expect(wrapper.text()).toContain('提交申请')
  })

  it('附件加载：响应缺 items 字段时兜底为空数组', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    listAttachments.mockResolvedValueOnce({})
    await vm.loadAttachments()
    expect(vm.attachments).toEqual([])
    wrapper.unmount()
  })

  it('创建模式：跳过详情加载，历史加载因无 id 全部早退', async () => {
    setRoute('/funds/create')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isCreate).toBe(true)
    expect(vm.isEdit).toBe(true)
    expect(vm.loading).toBe(false)
    expect(mockGet).not.toHaveBeenCalled()
    expect(listAttachments).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('新增经费记录')
    expect(wrapper.text()).toContain('填写经费信息')
  })

  it('编辑模式：isEdit 直进并加载详情', async () => {
    setRoute('/funds/5/edit', '5')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isEdit).toBe(true)
    expect(vm.isCreate).toBe(false)
    expect(mockGet).toHaveBeenCalledWith('/funds/5')
    expect(wrapper.text()).toContain('编辑经费记录')
    expect(wrapper.text()).toContain('编辑经费信息')
    // syncFormData 真值臂
    expect(vm.formData.name).toBe('修路经费')
    expect(vm.formData.dateRange).toEqual(['2024-01-13', '2024-12-31'])
  })

  it('无 id：提示无效并返回列表', async () => {
    setRoute('/funds/')
    mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('无效的经费记录ID')
    expect(pushSafe).toHaveBeenCalledWith('/funds')
  })

  it('详情加载失败：提示并返回列表', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/funds/5') return Promise.reject(new Error('net'))
      return defaultGetImpl(url)
    })
    mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('加载经费详情失败')
    expect(pushSafe).toHaveBeenCalledWith('/funds')
  })

  it('历史/附件加载失败：记录日志；items 缺失 → 空数组兜底', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/funds/5') return Promise.resolve({ data: { ...fundDetail } })
      if (url.includes('/history/')) return Promise.reject(new Error('net'))
      return defaultGetImpl(url)
    })
    listAttachments.mockRejectedValue(new Error('net'))
    let wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalledTimes(4)
    wrapper.unmount()

    // items 缺失 → || [] 兜底
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/history/')) return Promise.resolve({ data: {} })
      return defaultGetImpl(url)
    })
    wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.statusHistory).toEqual([])
    expect(vm.fieldChanges).toEqual([])
    expect(vm.operationLogs).toEqual([])
  })

  it('空详情渲染：全部 || 兜底（-、无、0.00、ds 空、syncFormData 全空臂）', async () => {
    // 挂载1：fund_source 空而 source 真 → 模板 getSourceName 的 || source 臂
    mockGet.mockImplementation((url: string) => {
      if (url === '/funds/5') {
        return Promise.resolve({ data: { id: 5, source: 'government', status: 'pending' } })
      }
      return defaultGetImpl(url)
    })
    dsMock.mockReturnValue('')
    let wrapper = mountComp()
    await flushPromises()
    let text = wrapper.text()
    expect(text).toContain('无')
    expect(text).toContain('0 万元')
    expect(text).toContain('政府') // source 臂
    wrapper.unmount()

    // 挂载2：source/status 均空 → syncFormData 的 '' 与 'pending' 兜底臂
    mockGet.mockImplementation((url: string) => {
      if (url === '/funds/5') return Promise.resolve({ data: { id: 5 } })
      return defaultGetImpl(url)
    })
    wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    text = wrapper.text()
    expect(text).toContain('无')
    expect(vm.formData.type).toBe('project')
    expect(vm.formData.status).toBe('pending')
    expect(vm.formData.source).toBe('')
    expect(vm.formData.dateRange).toBeNull()
  })

  it('syncFormData：start_date 与 end_date 缺一 → dateRange null', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/funds/5') {
        return Promise.resolve({
          data: { ...fundDetail, start_date: '2024-01-13T00:00:00', end_date: null },
        })
      }
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).formData.dateRange).toBeNull()
  })
})

describe('权限 computed', () => {
  it('isManager：admin/super_admin 为真，manager/user/viewer 为假（含 user 为空）', async () => {
    setRoute('/funds/create')
    let wrapper = mountComp()
    expect((wrapper.vm as any).isManager).toBe(true)
    wrapper.unmount()

    authState.user = { role: 'super_admin', id: 1 }
    wrapper = mountComp()
    expect((wrapper.vm as any).isManager).toBe(true)
    wrapper.unmount()

    authState.user = { role: 'manager', id: 1 }
    wrapper = mountComp()
    expect((wrapper.vm as any).isManager).toBe(false)
    wrapper.unmount()

    authState.user = { role: 'user', id: 1 }
    wrapper = mountComp()
    expect((wrapper.vm as any).isManager).toBe(false)
    wrapper.unmount()

    authState.user = null // role || '' 臂
    wrapper = mountComp()
    expect((wrapper.vm as any).isManager).toBe(false)
  })

  it('canEditFund：管理员直通；普通用户仅本人待审批/驳回可编辑；viewer 只读', async () => {
    // 普通用户 + 本人 + pending → true
    authState.user = { role: 'user', id: 1 }
    mockGet.mockImplementation((url: string) => {
      if (url === '/funds/5') {
        return Promise.resolve({ data: { ...fundDetail, created_by: 1, status: 'pending' } })
      }
      return defaultGetImpl(url)
    })
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).canEditFund).toBe(true)
    wrapper.unmount()

    // 本人 + rejected → true
    mockGet.mockImplementation((url: string) => {
      if (url === '/funds/5') {
        return Promise.resolve({ data: { ...fundDetail, created_by: 1, status: 'rejected' } })
      }
      return defaultGetImpl(url)
    })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).canEditFund).toBe(true)
    wrapper.unmount()

    // 本人 + approved → false
    mockGet.mockImplementation((url: string) => {
      if (url === '/funds/5') {
        return Promise.resolve({ data: { ...fundDetail, created_by: 1, status: 'approved' } })
      }
      return defaultGetImpl(url)
    })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).canEditFund).toBe(false)
    wrapper.unmount()

    // 非本人 → false（且无编辑按钮，覆盖 header-actions v-if 假侧）
    mockGet.mockImplementation((url: string) => {
      if (url === '/funds/5') {
        return Promise.resolve({ data: { ...fundDetail, created_by: 2, status: 'pending' } })
      }
      return defaultGetImpl(url)
    })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).canEditFund).toBe(false)
    expect(wrapper.findAll('el-button-stub').some((b) => b.text().trim() === '编辑')).toBe(false)
    wrapper.unmount()

    // viewer + 本人 + pending → false（canOperate 守卫）
    authState.user = { role: 'viewer', id: 1 }
    mockGet.mockImplementation((url: string) => {
      if (url === '/funds/5') {
        return Promise.resolve({ data: { ...fundDetail, created_by: 1, status: 'pending' } })
      }
      return defaultGetImpl(url)
    })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).canOperate).toBe(false)
    expect((wrapper.vm as any).canEditFund).toBe(false)
    wrapper.unmount()
  })
})

describe('工作流', () => {
  it('六状态按钮渲染与点击 → doWorkflow 打开对话框', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const clickBtn = async (text: string) => {
      const btn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === text)
      expect(btn, text).toBeTruthy()
      await btn!.trigger('click')
    }
    // pending → 审批通过 + 驳回
    await clickBtn('审批通过')
    expect(vm.wfAction).toBe('approve')
    expect(vm.wfDialogTitle).toBe('审批通过')
    expect(vm.wfDialogVisible).toBe(true)
    await clickBtn('驳回')
    expect(vm.wfAction).toBe('reject')

    vm.fundData.status = 'approved'
    await nextTick()
    await clickBtn('拨付')
    expect(vm.wfAction).toBe('allocate')
    expect(vm.wfForm.allocated_amount).toBe(80) // approved_amount 臂

    vm.fundData.status = 'allocated'
    await nextTick()
    await clickBtn('开始使用')
    expect(vm.wfAction).toBe('start_use')

    vm.fundData.status = 'in_use'
    await nextTick()
    await clickBtn('完成使用')
    expect(vm.wfAction).toBe('complete')

    vm.fundData.status = 'completed'
    await nextTick()
    await clickBtn('审计')
    expect(vm.wfAction).toBe('audit')
  })

  it('doWorkflow：未知 action 用原名；allocated_amount 三层兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.doWorkflow('mystery')
    expect(vm.wfDialogTitle).toBe('mystery')

    vm.fundData.approved_amount = null
    vm.fundData.amount = 55
    vm.doWorkflow('allocate')
    expect(vm.wfForm.allocated_amount).toBe(55) // amount 臂

    vm.fundData.approved_amount = null
    vm.fundData.amount = 0
    vm.doWorkflow('allocate')
    expect(vm.wfForm.allocated_amount).toBe(0) // || 0 臂
  })

  it('submitWorkflow：六种 action 分发与载荷差异（opinion 有/无）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockClear()

    const run = async (action: string, mockFn: any, extra?: object) => {
      vm.wfAction = action
      vm.wfDialogTitle = action
      await vm.submitWorkflow()
      expect(mockFn).toHaveBeenCalledWith(5, expect.objectContaining(extra || {}))
    }
    vm.wfForm.opinion = '同意'
    await run('approve', approveMock, { opinion: '同意' })
    vm.wfForm.opinion = '' // 驳回原因必填：空意见被拦截，不发起请求
    vm.wfAction = 'reject'
    vm.wfDialogTitle = 'reject'
    rejectMock.mockClear()
    await vm.submitWorkflow()
    expect(rejectMock).not.toHaveBeenCalled()
    expect(ElMessage.warning).toHaveBeenCalledWith('驳回时必须填写驳回原因')
    vm.wfForm.opinion = '资料不全，退回补充'
    await run('reject', rejectMock, { opinion: '资料不全，退回补充' })

    vm.wfForm.allocated_amount = 70
    vm.wfForm.allocation_method = '银行转账'
    await run('allocate', allocateMock, { allocated_amount: 70, allocation_method: '银行转账' })
    expect(allocateMock.mock.calls[0][1].audit_result).toBeUndefined()

    await run('start_use', startUseMock)
    await run('complete', completeMock)

    vm.wfForm.audit_result = '通过'
    await run('audit', auditMock, { audit_result: '通过' })
    expect(auditMock.mock.calls[0][1].allocated_amount).toBeUndefined()

    expect(ElNotification).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'audit', type: 'success' })
    )
    expect(vm.wfDialogVisible).toBe(false)
    expect(vm.wfSubmitting).toBe(false)
    expect(mockGet).toHaveBeenCalledWith('/funds/5') // 成功后重新加载
  })

  it('submitWorkflow：未知 action 直接返回；API 失败两种提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.wfAction = 'mystery'
    await vm.submitWorkflow()
    expect(approveMock).not.toHaveBeenCalled()
    expect(vm.wfSubmitting).toBe(false) // finally 复位

    vm.wfAction = 'approve'
    approveMock.mockRejectedValue({ response: { data: { detail: '无权操作' } } })
    await vm.submitWorkflow()
    expect(ElMessage.error).toHaveBeenCalledWith('无权操作')

    approveMock.mockRejectedValue({ response: { data: { detail: { code: 1 } } } })
    await vm.submitWorkflow()
    expect(ElMessage.error).toHaveBeenCalledWith('操作失败')
  })

  it('工作流对话框：allocate/audit 表单项 v-if 与 v-model，底部取消/确认', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 查看模式下编辑表单不渲染，wf 对话框内的组件数可精确探针 v-if 分支
    expect(wrapper.findAllComponents({ name: 'ElInputNumber' }).length).toBe(1) // +报销对话框金额输入
    expect(wrapper.findAllComponents({ name: 'ElSelect' }).length).toBe(0)

    vm.doWorkflow('allocate')
    await nextTick()
    // allocate → 拨付金额(input-number) + 拨付方式(input) 出现
    const inputNumbers = wrapper.findAllComponents({ name: 'ElInputNumber' })
    expect(inputNumbers.length).toBe(2) // +报销金额
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    expect(inputs.length).toBeGreaterThanOrEqual(4) // allocate/audit 两态数量不同；+报销3输入
    for (const c of inputNumbers) c.vm.$emit('update:modelValue', 66)
    expect(vm.wfForm.allocated_amount).toBe(66)
    for (const c of inputs) c.vm.$emit('update:modelValue', 'x')
    expect(vm.wfForm.allocation_method).toBe('x')
    expect(vm.wfForm.opinion).toBe('x')

    vm.doWorkflow('audit')
    await nextTick()
    // audit → 拨付字段消失，审计结果 select 出现
    expect(wrapper.findAllComponents({ name: 'ElInputNumber' }).length).toBe(1) // +报销对话框金额输入
    expect(wrapper.findAllComponents({ name: 'ElInput' }).length).toBe(4) // opinion + 报销3输入
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(selects.length).toBe(1)
    selects[0].vm.$emit('update:modelValue', '不通过')
    expect(vm.wfForm.audit_result).toBe('不通过')

    // 底部“取消”内联赋值箭头
    vm.wfDialogVisible = true
    const allCancel = wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '取消')
    const btns = allCancel.slice(0, allCancel.length - 1) // 排除报销对话框的取消
    expect(btns.length).toBeGreaterThan(0)
    await btns[btns.length - 1].trigger('click')
    expect(vm.wfDialogVisible).toBe(false)

    // 底部“确认”→ submitWorkflow
    vm.wfAction = 'approve'
    const confirmBtn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '确认')!
    await confirmBtn.trigger('click')
    await flushPromises()
    expect(approveMock).toHaveBeenCalled()
  })
})

describe('附件管理', () => {
  it('handleBeforeUpload 恒真；上传成功走 multipart 并刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.handleBeforeUpload(new File(['x'], 'a.pdf'))).toBe(true)

    listAttachments.mockClear()
    await vm.handleUploadAttachment({ file: new File(['x'], 'a.pdf') })
    expect(mockPost).toHaveBeenCalledWith(
      '/funds/5/attachments',
      expect.any(FormData),
      expect.objectContaining({ headers: { 'Content-Type': 'multipart/form-data' } })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('上传成功')
    expect(listAttachments).toHaveBeenCalledWith(5)
    expect(vm.uploadingAttachment).toBe(false)
  })

  it('上传：无 id 早退；失败提示且 finally 复位', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fundData.id = null
    await vm.handleUploadAttachment({ file: new File(['x'], 'a.pdf') })
    expect(mockPost).not.toHaveBeenCalled()

    vm.fundData.id = 5
    mockPost.mockRejectedValue(new Error('net'))
    await vm.handleUploadAttachment({ file: new File(['x'], 'a.pdf') })
    expect(ElMessage.error).toHaveBeenCalledWith('上传失败')
    expect(vm.uploadingAttachment).toBe(false)
  })

  it('预览成功：打开对话框并设置标题（file_name 有/无两臂）', async () => {
    const createSpy = vi.spyOn(URL, 'createObjectURL')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    const previewBtns = wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '预览')
    expect(previewBtns.length).toBe(2)
    await previewBtns[0].trigger('click')
    await flushPromises()
    expect(getAttachmentBlob).toHaveBeenCalledWith(11)
    expect(createSpy).toHaveBeenCalled()
    expect(vm.previewVisible).toBe(true)
    expect(vm.previewTitle).toBe('合同.pdf')
    expect(vm.previewUrl).toBe('blob:mock-url')
    await nextTick()
    expect(wrapper.find('iframe').exists()).toBe(true) // v-if previewUrl 真侧

    // file_name 空 → '附件预览' 兜底
    await previewBtns[1].trigger('click')
    await flushPromises()
    expect(getAttachmentBlob).toHaveBeenCalledWith(12)
    expect(vm.previewTitle).toBe('附件预览')
    createSpy.mockRestore()
  })

  it('预览失败：提示加载失败', async () => {
    getAttachmentBlob.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.previewAttachment({ id: 11, file_name: 'x.pdf' })
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('预览加载失败')
  })

  it('handlePreviewClose：有 url 撤销并清空；空 url 跳过', async () => {
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.previewUrl = 'blob:mock-url'
    // 通过对话框 close 事件触发
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    dialogs[0].vm.$emit('close')
    expect(revokeSpy).toHaveBeenCalledWith('blob:mock-url')
    expect(vm.previewUrl).toBe('')
    // 空 url → 不再撤销
    revokeSpy.mockClear()
    vm.handlePreviewClose()
    expect(revokeSpy).not.toHaveBeenCalled()
    revokeSpy.mockRestore()
  })

  it('下载成功与失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const downloadBtns = wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '下载')
    await downloadBtns[0].trigger('click')
    expect(downloadAttachmentMock).toHaveBeenCalledWith(11, '合同.pdf')

    downloadAttachmentMock.mockRejectedValue(new Error('net'))
    await downloadBtns[1].trigger('click')
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('下载失败')
  })

  it('删除附件：popconfirm confirm 箭头 → 成功刷新；失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    listAttachments.mockClear()
    const confirms = wrapper.findAllComponents({ name: 'ElPopconfirm' })
    expect(confirms.length).toBe(2)
    confirms[0].vm.$emit('confirm')
    await flushPromises()
    expect(deleteAttachmentMock).toHaveBeenCalledWith(11)
    // 成功静默：删除成功不弹提示
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(listAttachments).toHaveBeenCalledWith(5)

    deleteAttachmentMock.mockRejectedValue(new Error('net'))
    confirms[1].vm.$emit('confirm')
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })

  it('空附件渲染 el-empty；空历史渲染暂无文案', async () => {
    listAttachments.mockResolvedValue({ items: [] })
    mockGet.mockImplementation((url: string) => {
      if (url.includes('/history/')) return Promise.resolve({ data: { items: [] } })
      return defaultGetImpl(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const text = wrapper.text()
    // el-empty 的 description 是 prop，验证 stub 存在即可
    expect(wrapper.find('el-empty-stub').exists()).toBe(true)
    expect(text).toContain('暂无状态变更记录')
    expect(text).toContain('暂无字段修改记录')
    expect(text).toContain('暂无操作日志')
  })
})

describe('辅助函数', () => {
  it('getCategoryLabel / formatFileSize 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getCategoryLabel('contract')).toBe('合同')
    expect(vm.getCategoryLabel('invoice')).toBe('发票')
    expect(vm.getCategoryLabel('receipt')).toBe('收据')
    expect(vm.getCategoryLabel('report')).toBe('报告')
    expect(vm.getCategoryLabel('allocation_order')).toBe('分配令')
    expect(vm.getCategoryLabel('other')).toBe('其他')
    expect(vm.getCategoryLabel('alien')).toBe('alien')
    expect(vm.getCategoryLabel('')).toBe('其他')

    expect(vm.formatFileSize(0)).toBe('-')
    expect(vm.formatFileSize(512)).toBe('512 B')
    expect(vm.formatFileSize(2048)).toBe('2.0 KB')
    expect(vm.formatFileSize(5 * 1024 * 1024)).toBe('5.0 MB')
  })

  it('getTypeName / getSourceName / getStatusType / getStatusText 映射与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getTypeName('project')).toBe('项目经费')
    expect(vm.getTypeName('operation')).toBe('运营经费')
    expect(vm.getTypeName('education')).toBe('教育帮扶')
    expect(vm.getTypeName('infrastructure')).toBe('基础设施')
    expect(vm.getTypeName('emergency')).toBe('应急经费')
    expect(vm.getTypeName('other')).toBe('其他')
    expect(vm.getTypeName('alien')).toBe('alien')
    expect(vm.getTypeName('')).toBe('-')

    expect(vm.getSourceName('military')).toBe('专项')
    expect(vm.getSourceName('government')).toBe('政府')
    expect(vm.getSourceName('donation')).toBe('捐赠')
    expect(vm.getSourceName('enterprise')).toBe('企业')
    expect(vm.getSourceName('other')).toBe('其他')
    expect(vm.getSourceName('alien')).toBe('alien')
    expect(vm.getSourceName('')).toBe('-')

    expect(vm.getStatusType('pending')).toBe('warning')
    expect(vm.getStatusType('planned')).toBe('info')
    expect(vm.getStatusType('approved')).toBe('primary')
    expect(vm.getStatusType('allocated')).toBe('info')
    expect(vm.getStatusType('in_use')).toBe('primary')
    expect(vm.getStatusType('completed')).toBe('success')
    expect(vm.getStatusType('audited')).toBe('success')
    expect(vm.getStatusType('rejected')).toBe('danger')
    expect(vm.getStatusType('alien')).toBe('info')

    expect(vm.getStatusText('pending')).toBe('待审批')
    expect(vm.getStatusText('planned')).toBe('已计划')
    expect(vm.getStatusText('approved')).toBe('已批准')
    expect(vm.getStatusText('allocated')).toBe('已拨付')
    expect(vm.getStatusText('in_use')).toBe('使用中')
    expect(vm.getStatusText('completed')).toBe('已完成')
    expect(vm.getStatusText('audited')).toBe('已审计')
    expect(vm.getStatusText('rejected')).toBe('已驳回')
    expect(vm.getStatusText('alien')).toBe('alien')
    expect(vm.getStatusText('')).toBe('-')
  })

  it('formatMoney / formatDateTime / getOperationTypeLabel / formatOperationDetail', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatMoney(null)).toBe('0')
    expect(vm.formatMoney(1234.5)).toBe('1,234.5')

    expect(vm.formatDateTime(null)).toBe('-')
    expect(vm.formatDateTime('')).toBe('-')
    expect(vm.formatDateTime('2024-01-11T08:00:00')).toBe('2024-01-11')
    // toString 抛错 → catch 臂（catch 内 String 仍抛 → 向外传播）
    const bad = Object.create(null)
    expect(() => vm.formatDateTime(bad)).toThrow()

    expect(vm.getOperationTypeLabel('attachment_upload')).toBe('附件上传')
    expect(vm.getOperationTypeLabel('attachment_delete')).toBe('附件删除')
    expect(vm.getOperationTypeLabel('status_change')).toBe('状态变更')
    expect(vm.getOperationTypeLabel('field_update')).toBe('字段更新')
    expect(vm.getOperationTypeLabel('create')).toBe('创建')
    expect(vm.getOperationTypeLabel('delete')).toBe('删除')
    expect(vm.getOperationTypeLabel('mystery')).toBe('mystery')

    expect(vm.formatOperationDetail('')).toBe('-')
    expect(vm.formatOperationDetail('{"a":1}')).toBe('{"a":1}')
    expect(vm.formatOperationDetail({ b: 2 })).toBe('{"b":2}')
    expect(vm.formatOperationDetail('plain-text')).toBe('plain-text') // JSON.parse 抛错 → catch
    expect(vm.formatOperationDetail(42 as any)).toBe('42') // 非 object → String(detail)
  })
})

describe('编辑与提交', () => {
  it('编辑模式 v-model 全组件 update 箭头', async () => {
    setRoute('/funds/5/edit', '5')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    expect(inputs.length).toBeGreaterThan(0)
    for (const c of inputs) c.vm.$emit('update:modelValue', 'x')
    expect(vm.formData.code).toBe('x')
    expect(vm.formData.name).toBe('x')
    expect(vm.formData.project_name).toBe('x')
    expect(vm.formData.operator).toBe('x')
    expect(vm.formData.receiver).toBe('x')
    expect(vm.formData.purpose).toBe('x')
    expect(vm.formData.usage_description).toBe('x')
    expect(vm.formData.remarks).toBe('x')

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    for (const c of selects) c.vm.$emit('update:modelValue', 'other')
    expect(vm.formData.type).toBe('other')
    expect(vm.formData.fund_source).toBe('other')
    expect(vm.formData.status).toBe('other')

    const numbers = wrapper.findAllComponents({ name: 'ElInputNumber' })
    expect(numbers.length).toBe(7)
    for (const c of numbers) c.vm.$emit('update:modelValue', 9.5)
    expect(vm.formData.amount).toBe(9.5)
    expect(vm.formData.planned_amount).toBe(9.5)
    expect(vm.formData.approved_amount).toBe(9.5)
    expect(vm.formData.allocated_amount).toBe(9.5)
    expect(vm.formData.used_amount).toBe(9.5)
    expect(vm.formData.remaining_amount).toBe(9.5)

    const pickers = wrapper.findAllComponents({ name: 'ElDatePicker' })
    expect(pickers.length).toBe(3) // +报销对话框日期
    pickers[0].vm.$emit('update:modelValue', '2024-06-01')
    expect(vm.formData.date).toBe('2024-06-01')
    pickers[1].vm.$emit('update:modelValue', ['2024-06-01', '2024-07-01'])
    expect(vm.formData.dateRange).toEqual(['2024-06-01', '2024-07-01'])
  })

  it('handleSubmit 创建成功：payload 清洗（删空/dateRange 展开/保留真值）', async () => {
    setRoute('/funds/create')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.name = '新经费'
    vm.formData.date = '2024-06-01'
    vm.formData.code = '' // 空串 → 删除
    vm.formData.approved_amount = null // null → 删除
    vm.formData.dateRange = ['2024-06-01', '2024-07-01']
    vm.formRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleSubmit()
    expect(mockPost).toHaveBeenCalledWith(
      '/funds',
      expect.objectContaining({
        name: '新经费',
        date: '2024-06-01',
        start_date: '2024-06-01',
        end_date: '2024-07-01',
      })
    )
    const payload = mockPost.mock.calls[0][1]
    expect('code' in payload).toBe(false)
    expect('approved_amount' in payload).toBe(false)
    expect('dateRange' in payload).toBe(false)
    expect('village_id' in payload).toBe(false)
    // 成功静默：创建成功不弹提示
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(pushSafe).toHaveBeenCalledWith('/funds')
    expect(vm.submitting).toBe(false)
  })

  it('handleSubmit 创建：date 与 dateRange 为空 → 删除且不展开', async () => {
    setRoute('/funds/create')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.name = '新经费'
    vm.formData.date = null // delete payload.date 臂
    vm.formData.dateRange = null // 不展开臂
    vm.formRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleSubmit()
    const payload = mockPost.mock.calls[0][1]
    expect('date' in payload).toBe(false)
    expect('start_date' in payload).toBe(false)
    expect('end_date' in payload).toBe(false)
  })

  it('handleSubmit 编辑成功：put 并重新加载', async () => {
    setRoute('/funds/5/edit', '5')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockClear()
    vm.formData.name = '改后名'
    vm.formRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleSubmit()
    expect(mockPut).toHaveBeenCalledWith('/funds/5', expect.objectContaining({ name: '改后名' }))
    // 成功静默：保存成功不弹提示
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(vm.isEdit).toBe(false)
    expect(mockGet).toHaveBeenCalledWith('/funds/5')
    expect(vm.submitting).toBe(false)
  })

  it('handleSubmit：formRef 为空 → 直接返回', async () => {
    setRoute('/funds/5/edit', '5')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formRef = null
    await vm.handleSubmit()
    expect(mockPut).not.toHaveBeenCalled()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('handleSubmit：校验失败（error.fields）→ 静默不提示', async () => {
    setRoute('/funds/5/edit', '5')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formRef = { validate: vi.fn().mockRejectedValue({ fields: { name: ['必填'] } }) }
    await vm.handleSubmit()
    expect(ElMessage.error).not.toHaveBeenCalled()
    expect(mockPut).not.toHaveBeenCalled()
    expect(vm.submitting).toBe(false)
  })

  it('handleSubmit：API 失败三种提示（detail / message / 无）', async () => {
    setRoute('/funds/5/edit', '5')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    mockPut.mockRejectedValue({ response: { data: { detail: '金额超限' } } })
    vm.formRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleSubmit()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败: 金额超限')

    mockPut.mockRejectedValue({ response: { data: { message: '服务器忙' } } })
    vm.formRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleSubmit()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败: 服务器忙')

    mockPut.mockRejectedValue(new Error('net'))
    vm.formRef = { validate: vi.fn().mockResolvedValue(true) }
    await vm.handleSubmit()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败，请检查输入')
    expect(vm.submitting).toBe(false)
  })

  it('取消按钮：创建模式走 goBack；编辑模式走 cancelEdit 并还原表单', async () => {
    // 创建模式
    setRoute('/funds/create')
    let wrapper = mountComp()
    await flushPromises()
    let cancelBtn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '取消')!
    await cancelBtn.trigger('click')
    expect(pushSafe).toHaveBeenCalledWith('/funds')
    wrapper.unmount()

    // 编辑模式
    setRoute('/funds/5/edit', '5')
    wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.name = '脏数据'
    cancelBtn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '取消')!
    await cancelBtn.trigger('click')
    expect(vm.isEdit).toBe(false)
    expect(vm.formData.name).toBe('修路经费') // syncFormData(fundData) 还原
  })

  it('点击头部编辑按钮 → handleEdit 进入编辑', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const editBtn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '编辑')!
    expect(editBtn).toBeTruthy()
    await editBtn.trigger('click')
    expect(vm.isEdit).toBe(true)
  })

  it('提交按钮文本：创建/保存两侧', async () => {
    setRoute('/funds/create')
    let wrapper = mountComp()
    await flushPromises()
    expect(wrapper.findAll('el-button-stub').some((b) => b.text().trim() === '创建')).toBe(true)
    wrapper.unmount()

    setRoute('/funds/5/edit', '5')
    wrapper = mountComp()
    await flushPromises()
    expect(wrapper.findAll('el-button-stub').some((b) => b.text().trim() === '保存')).toBe(true)
  })
})

describe('删除记录', () => {
  it('确认删除 → del + 提示 + 返回列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete()
    expect(confirmMock).toHaveBeenCalledWith(
      '确定要删除这条经费记录吗？',
      '提示',
      expect.objectContaining({ type: 'warning' })
    )
    expect(mockDel).toHaveBeenCalledWith('/funds/5')
    // 成功静默：删除成功不弹提示
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(pushSafe).toHaveBeenCalledWith('/funds')
  })

  it('点击头部删除按钮触发 handleDelete；取消（cancel）静默', async () => {
    confirmMock.mockRejectedValue('cancel')
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '删除')!
    expect(btn).toBeTruthy()
    await btn.trigger('click')
    await flushPromises()
    expect(mockDel).not.toHaveBeenCalled()
    expect(logError).not.toHaveBeenCalled()
  })

  it('删除接口失败（非 cancel）→ 记录日志', async () => {
    confirmMock.mockResolvedValue(undefined)
    mockDel.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete()
    expect(logError).toHaveBeenCalledWith('删除失败', expect.any(Error))
  })
})

describe('路由 watch 与生命周期', () => {
  it('watch(route.path)：切到 /edit 重新检测模式并重载；创建模式跳过重载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isEdit).toBe(false)
    mockGet.mockClear()
    routeHolder.current.path = '/funds/5/edit'
    await nextTick()
    expect(vm.isEdit).toBe(true)
    expect(mockGet).toHaveBeenCalledWith('/funds/5')
    wrapper.unmount()

    // 创建模式下变更 path → 跳过重载臂
    setRoute('/funds/create')
    mountComp()
    await flushPromises()
    mockGet.mockClear()
    routeHolder.current.path = '/funds/anything'
    await nextTick()
    expect(mockGet).not.toHaveBeenCalled()
  })

  it('onBeforeUnmount：previewUrl 非空撤销；空则跳过', async () => {
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL')
    let wrapper = mountComp()
    await flushPromises()
    ;(wrapper.vm as any).previewUrl = 'blob:mock-url'
    wrapper.unmount()
    expect(revokeSpy).toHaveBeenCalledWith('blob:mock-url')

    revokeSpy.mockClear()
    wrapper = mountComp()
    await flushPromises()
    wrapper.unmount()
    expect(revokeSpy).not.toHaveBeenCalled()
    revokeSpy.mockRestore()
  })

  it('对话框 v-model 箭头：previewVisible 与 wfDialogVisible', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    expect(dialogs.length).toBe(3)
    dialogs[0].vm.$emit('update:modelValue', true)
    expect(vm.previewVisible).toBe(true)
    dialogs[1].vm.$emit('update:modelValue', true)
    expect(vm.wfDialogVisible).toBe(true)
  })

  it('el-tabs v-model 箭头切换 activeTab', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const tabs = wrapper.findComponent({ name: 'ElTabs' })
    tabs.vm.$emit('update:modelValue', 'approval')
    expect(vm.activeTab).toBe('approval')
  })

  it('返回列表按钮 → goBack', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('返回列表'))!
    await btn.trigger('click')
    expect(pushSafe).toHaveBeenCalledWith('/funds')
  })
})

describe('审批流程可视化（v1.8.0）', () => {
  it('approvalActiveStep：无节点 → 0；current 命中 → idx+1', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.approvalFlow = { nodes: [] }
    expect(vm.approvalActiveStep).toBe(0)
    vm.approvalFlow = { nodes: [{ key: 'a', reached: true }, { key: 'b', current: true }] }
    expect(vm.approvalActiveStep).toBe(2)
  })

  it('approvalActiveStep：无 current → 按 reached 计数', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.approvalFlow = { nodes: [{ key: 'a', reached: true }, { key: 'b', reached: false }] }
    expect(vm.approvalActiveStep).toBe(1)
  })

  it('loadApprovalFlow 失败 → logger.error 且不抛错', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fundData.id = 5
    // mount 后再设置（mount 时 onMounted 的 get 会消耗 once）
    mockGet.mockRejectedValueOnce(new Error('net'))
    await vm.loadApprovalFlow()
    expect(logError).toHaveBeenCalled()
  })

  it('loadApprovalFlow 成功 → 归一化字段（camelCase 兼容）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fundData.id = 5
    mockGet.mockResolvedValueOnce({
      current_status: 'pending',
      current_approver: '张三',
      nodes: [{ key: 'submit', reached: true }],
    })
    await vm.loadApprovalFlow()
    expect(vm.approvalFlow.currentStatus).toBe('pending')
    expect(vm.approvalFlow.currentApprover).toBe('张三')
    expect(vm.approvalFlow.nodes).toHaveLength(1)
  })

  it('历史记录：状态日志数组/信封/items 多形态与失败兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fundData.id = 5
    // 数组形态
    mockGet.mockResolvedValueOnce([{ id: 1 }])
    await vm.loadStatusHistory()
    expect(vm.statusHistory).toEqual([{ id: 1 }])
    // items 信封形态（拦截器解包后 data.items）
    mockGet.mockResolvedValueOnce({ data: { items: [{ id: 2 }] } })
    await vm.loadStatusHistory()
    expect(vm.statusHistory).toEqual([{ id: 2 }])
    // 空对象兜底
    mockGet.mockResolvedValueOnce({})
    await vm.loadStatusHistory()
    expect(vm.statusHistory).toEqual([])
    // 失败 → logger + 空数组
    mockGet.mockRejectedValueOnce(new Error('net'))
    await vm.loadStatusHistory()
    expect(vm.statusHistory).toEqual([])
  })

  it('字段变更/操作日志：数组与 items 信封多形态 + 空兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fundData.id = 5
    // 字段变更：数组形态
    mockGet.mockResolvedValueOnce([{ field: 'a' }])
    await vm.loadFieldChanges()
    expect(vm.fieldChanges).toEqual([{ field: 'a' }])
    // 字段变更：items 形态
    mockGet.mockResolvedValueOnce({ data: { items: [{ field: 'b' }] } })
    await vm.loadFieldChanges()
    expect(vm.fieldChanges).toEqual([{ field: 'b' }])
    // 操作日志：数组形态
    mockGet.mockResolvedValueOnce([{ op: 'x' }])
    await vm.loadOperationLogs()
    expect(vm.operationLogs).toEqual([{ op: 'x' }])
    // 操作日志：items 形态 + 空兜底
    mockGet.mockResolvedValueOnce({ data: { items: [{ op: 'y' }] } })
    await vm.loadOperationLogs()
    expect(vm.operationLogs).toEqual([{ op: 'y' }])
    mockGet.mockResolvedValueOnce({})
    await vm.loadOperationLogs()
    expect(vm.operationLogs).toEqual([])
  })

  it('loadApprovalFlow：响应无 data 字段 → 原对象兜底 → 空 {}', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fundData.id = 5
    // 无 data 字段：res 直接是流程对象
    mockGet.mockResolvedValueOnce({ current_status: 'approved', nodes: [] })
    await vm.loadApprovalFlow()
    expect(vm.approvalFlow.currentStatus).toBe('approved')
    // 两者皆空 → {}
    mockGet.mockResolvedValueOnce({})
    await vm.loadApprovalFlow()
    expect(vm.approvalFlow.currentStatus).toBe('')
    expect(vm.approvalFlow.nodes).toEqual([])
    // 响应整体为空 → || {} 最终兜底
    mockGet.mockResolvedValueOnce(null)
    await vm.loadApprovalFlow()
    expect(vm.approvalFlow.currentStatus).toBe('')
    expect(vm.approvalFlow.currentApprover).toBe('')
    expect(vm.approvalFlow.nodes).toEqual([])
  })
})
