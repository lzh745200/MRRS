/**
 * views/dataPackage/ReceivePackage.vue 覆盖率攻坚（四指标 100%）
 *
 * 覆盖：onMounted 加载（含组织失败 catch）、loadReports/resetFilters 全分支、
 * 列表行 7 列模板全部 ||/??/v-if 两侧（4 行样本注入）、接收/拒绝/预览/下载交互、
 * 本地导入三步流（handleLocalFileChange/confirmLocalImport/clearLocalImport 全分支）、
 * onErrorCaptured 错误边界两侧、分页与 3 个对话框 v-model 内联处理器。
 *
 * 方案：真实 Pinia + 真实 store，mock 底层 '@/api/request'（apiRequest/post 按 URL 路由），
 * store 内部吞错的分支（loadReports catch / onMounted 组织 catch）用 vi.spyOn store 方法触发。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

// vi.mock 工厂提升求值，引用对象须先放入 vi.hoisted 初始化
const { ElMessage, confirmMock, mockPost, mockApiRequest, mockGet, logError, authState } = vi.hoisted(() => {
  return {
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
    confirmMock: vi.fn(),
    mockPost: vi.fn(),
    mockApiRequest: vi.fn(),
    mockGet: vi.fn(),
    logError: vi.fn(),
    authState: { isAdmin: true },
  }
})

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import ReceivePackage from '@/views/dataPackage/ReceivePackage.vue'
import { useDataReportStore } from '@/stores/dataReport'
import { useOrganizationStore } from '@/stores/organization'

// ── 样本数据 ──
const rep1 = {
  id: 1,
  source_org_id: 1,
  source_org_name: '单位甲',
  package_code: 'PKG-1',
  data_types: ['villages'],
  record_count: 5,
  status: 'pending',
  submitted_at: '2024-01-01T02:00:00',
  created_at: '2024-01-01T01:00:00',
}

// 列模板 4 行样本：覆盖所有 ||/??/v-if 组合
const rowA = {
  id: 101,
  source_org_id: 1,
  source_org_name: '单位甲',
  package_code: 'PKG-A',
  data_types: '["villages","projects"]', // JSON 字符串解析侧
  record_count: 5,
  status: 'pending', // 接收/拒绝按钮 v-if 左支
  submitted_at: '2024-01-01T02:00:00',
  created_at: '2024-01-01T01:00:00',
}
const rowB = {
  id: 102,
  source_org_id: 2,
  title: '标题乙', // source_org_name 缺省 → title 侧
  report_code: 'RC-B', // package_code 缺省 → report_code 侧
  data_types: ['funds'], // 数组直返侧
  record_count: null, // ?? '-' 右侧
  status: 'submitted', // v-if 左假右真
  submitted_at: null, // || created_at 右侧
  created_at: '2024-02-01T02:00:00',
}
const rowC = {
  id: 103,
  source_org_id: 3, // 名称/标题全缺 → `单位#3`
  // package_code/report_code 全缺 → '-'
  data_types: 'not-json', // JSON 解析失败 → []
  status: 'received', // v-if 双假 → 无接收/拒绝按钮
  // submitted_at/created_at 全缺 → formatDate(undefined) → '-'
}
const rowD = {
  id: 104,
  source_org_id: 4,
  source_org_name: '单位丁',
  package_code: 'PKG-D',
  data_types: [], // 空数组 → '-' span
  record_count: 0, // ?? 左侧（0 不触发 ??）
  status: 'weird', // getStatusLabel/getStatusType 未知回退
  submitted_at: '2024-03-01T02:00:00',
  created_at: '2024-03-01T01:00:00',
}

const previewArray = [
  { data_type: 'villages', total: 2, columns: ['id', 'name', 'mystery_col'], sample: [{ id: 1 }] },
  { data_type: 'unknown_type', total: 0, columns: [], sample: [] },
]

// ── apiRequest 默认 URL 路由 ──
function defaultApiRouter(config: any): Promise<any> {
  const url: string = config?.url || ''
  if (url === '/data-reports/received') return Promise.resolve({ items: [rep1], total: 1 })
  if (url === '/organizations/subordinates') {
    return Promise.resolve({ data: [{ id: 1, name: '下级单位A' }] })
  }
  if (/^\/data-reports\/\d+$/.test(url)) return Promise.resolve(previewArray)
  return Promise.resolve({})
}

function defaultPostRouter(url: string): Promise<any> {
  if (url === '/data-packages/import') return Promise.resolve({ package_id: 42 })
  return Promise.resolve({})
}

// 接收记录样本：覆盖 validation_summary 解析 / 文件大小格式化 / 校验结果展示
const recv1 = {
  id: 11,
  package_code: 'PKG-R1',
  org_name: '单位甲',
  org_code: null,
  exported_by_name: '张三',
  file_name: 'a.zip',
  file_size: 2048,
  record_count: 3,
  status: 'validated',
  imported_at: '2024-01-01T02:00:00',
  validation_summary: ['通过2条/纠正1条/拒绝0条', '字段X校验未通过'],
}
const recv2 = {
  id: 12,
  package_code: 'PKG-R2',
  org_name: null,
  org_code: 'ORG-2',
  exported_by_name: null,
  file_name: null,
  file_size: 5000000,
  record_count: null,
  status: 'pending',
  created_at: '2024-02-01T02:00:00',
  validation_summary: ['字段Y已自动纠正'],
}

function defaultGetRouter(url: string): Promise<any> {
  if (url === '/data-packages/received') return Promise.resolve({ items: [recv1, recv2], total: 2 })
  if (/^\/data-packages\/\d+\/preview$/.test(url)) return Promise.resolve(previewArray)
  return Promise.resolve({})
}

function mountComp(extraStubs: Record<string, any> = {}, pinia?: any) {
  // el-dialog 需 footer 具名插槽 + v-model/close；el-table-column 注入 4 行样本；
  // el-result 需 #extra 插槽（错误回退卡）；el-upload 需 clearFiles 方法（模板 ref 调用）
  return mount(ReceivePackage, {
    global: {
      plugins: [pinia || createPinia()],
      renderStubDefaultSlot: true,
      stubs: {
        'el-dialog': {
          name: 'ElDialog',
          props: ['modelValue', 'title'],
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue', 'close'],
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /><slot :row="rowD" /></div>',
          data() {
            return { rowA, rowB, rowC, rowD }
          },
        },
        'el-result': {
          name: 'ElResult',
          props: ['title', 'subTitle', 'icon'],
          template:
            '<div class="el-result-stub"><span class="el-result-title">{{ title }}</span><slot /><slot name="extra" /></div>',
        },
        'el-upload': {
          name: 'ElUpload',
          template: '<div class="el-upload-stub"><slot /></div>',
          methods: { clearFiles() {} },
        },
        ...extraStubs,
      },
    },
  })
}

/** 按文本精确匹配点击按钮（trim 避免「拒绝」误点「确认拒绝」） */
async function clickBtn(wrapper: any, text: string, index = 0) {
  const btns = wrapper.findAll('el-button-stub').filter((b: any) => b.text().trim() === text)
  expect(btns.length, `按钮「${text}」x${index}`).toBeGreaterThan(index)
  await btns[index].trigger('click')
  await flushPromises()
}

beforeEach(() => {
  vi.resetAllMocks()
  authState.isAdmin = true
  mockApiRequest.mockImplementation(defaultApiRouter)
  mockPost.mockImplementation(defaultPostRouter)
  mockGet.mockImplementation(defaultGetRouter)
  confirmMock.mockResolvedValue('confirm')
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('初始加载与筛选', () => {
  it('挂载加载列表/组织，渲染行样本覆盖 7 列模板全部分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'GET', url: '/data-reports/received' })
    )
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'GET', url: '/organizations/subordinates' })
    )
    expect(vm.reports).toEqual([rep1])
    expect(vm.total).toBe(1)
    expect(vm.subordinateOrgs).toEqual([{ id: 1, name: '下级单位A' }])
    // 上报单位列三级 ||：名称 / 标题 / 单位#id
    expect(wrapper.text()).toContain('单位甲')
    expect(wrapper.text()).toContain('标题乙')
    expect(wrapper.text()).toContain('单位#3')
    // 编码列三级 ||：package_code / report_code / '-'
    expect(wrapper.text()).toContain('PKG-A')
    expect(wrapper.text()).toContain('RC-B')
    // 数据类型列：JSON 字符串 / 数组 / 解析失败 / 空数组
    expect(wrapper.text()).toContain('村庄数据')
    expect(wrapper.text()).toContain('项目数据')
    expect(wrapper.text()).toContain('资金数据')
    // 状态列：待接收/已提交/已接收/未知回退原样
    expect(wrapper.text()).toContain('待接收')
    expect(wrapper.text()).toContain('已提交')
    expect(wrapper.text()).toContain('已接收')
    expect(wrapper.text()).toContain('weird')
    // 分页 total>0 渲染
    expect(wrapper.findComponent({ name: 'ElPagination' }).exists()).toBe(true)
    wrapper.unmount()
  })

  it('筛选 v-model + 查询携带全部参数；重置清空并重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    mockApiRequest.mockClear()

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 1) // filters.sourceOrgId
    selects[1].vm.$emit('update:modelValue', 'pending') // filters.status
    const range: [Date, Date] = [new Date('2024-01-01T00:00:00'), new Date('2024-01-31T00:00:00')]
    wrapper.findComponent({ name: 'ElDatePicker' }).vm.$emit('update:modelValue', range)
    await nextTick()

    await clickBtn(wrapper, '查询')
    const receivedCall = mockApiRequest.mock.calls.find(
      (c: any) => c[0]?.url === '/data-reports/received'
    )
    expect(receivedCall[0].params).toEqual({
      page: 1,
      page_size: 20,
      source_org_id: 1,
      status: 'pending',
      start_date: range[0].toISOString(),
      end_date: range[1].toISOString(),
    })

    const vm = wrapper.vm as any
    mockApiRequest.mockClear()
    await clickBtn(wrapper, '重置')
    expect(vm.filters).toEqual({ sourceOrgId: null, status: '', dateRange: null })
    expect(vm.pagination.page).toBe(1)
    // 重置后参数走 || undefined 侧
    const resetCall = mockApiRequest.mock.calls.find(
      (c: any) => c[0]?.url === '/data-reports/received'
    )
    expect(resetCall[0].params.source_org_id).toBeUndefined()
    expect(resetCall[0].params.status).toBeUndefined()
    wrapper.unmount()
  })

  it('loadReports：store 方法抛错 → catch 提示加载数据失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const store = useDataReportStore()
    vi.spyOn(store, 'fetchReceivedReports').mockRejectedValue(new Error('boom'))
    const vm = wrapper.vm as any
    await vm.loadReports()
    expect(ElMessage.error).toHaveBeenCalledWith('加载数据失败')
    expect(vm.loading).toBe(false)
    wrapper.unmount()
  })

  it('onMounted 组织加载抛错 → logger.error 记录', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const orgStore = useOrganizationStore()
    vi.spyOn(orgStore, 'fetchSubordinateOrganizations').mockRejectedValue(new Error('org down'))
    const wrapper = mountComp({}, pinia)
    await flushPromises()
    expect(logError).toHaveBeenCalledWith('[ReceivePackage] 加载组织失败', expect.any(Error))
    wrapper.unmount()
  })

  it('空列表渲染 el-empty；total=0 分页隐藏', async () => {
    mockApiRequest.mockImplementation((config: any) => {
      if (config?.url === '/data-reports/received') return Promise.resolve({ items: [], total: 0 })
      return defaultApiRouter(config)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.find('el-empty-stub').exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'ElPagination' }).exists()).toBe(false)
    wrapper.unmount()
  })
})

describe('列表行交互：接收/拒绝/下载', () => {
  it('点击「接收」：确认 → approve → 成功提示并回到第 1 页重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.pagination.page = 3 // 验证重置到第 1 页
    mockApiRequest.mockClear()
    await clickBtn(wrapper, '接收', 0) // rowA（source_org_name 侧）
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('单位甲'),
      '确认接收',
      expect.objectContaining({ type: 'info' })
    )
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'POST', url: '/data-reports/101/approve' })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('接收成功')
    expect(vm.pagination.page).toBe(1)
    expect(mockApiRequest.mock.calls.some((c: any) => c[0]?.url === '/data-reports/received')).toBe(
      true
    )
    wrapper.unmount()
  })

  it('handleReceive：title 侧与 单位# 兜底；cancel / toString cancel 静默', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // title 侧（rowB）
    await clickBtn(wrapper, '接收', 1)
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('标题乙'),
      '确认接收',
      expect.anything()
    )
    // 单位# 兜底（无名称无标题）
    await vm.handleReceive({ id: 5, source_org_id: 7, status: 'pending' })
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining('单位#7'),
      '确认接收',
      expect.anything()
    )
    // 用户取消 → 静默
    ElMessage.error.mockClear()
    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleReceive(rowA as any)
    expect(ElMessage.error).not.toHaveBeenCalled()
    // toString() === 'cancel' 的对象 → 静默
    confirmMock.mockRejectedValueOnce({ toString: () => 'cancel' })
    await vm.handleReceive(rowA as any)
    expect(ElMessage.error).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('handleReceive：失败提示 error.message 与「接收失败」兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockApiRequest.mockImplementation((config: any) => {
      if (config?.url?.endsWith('/approve')) return Promise.reject(new Error('审批冲突'))
      return defaultApiRouter(config)
    })
    await vm.handleReceive(rowA as any)
    expect(ElMessage.error).toHaveBeenCalledWith('审批冲突')
    mockApiRequest.mockImplementation((config: any) => {
      if (config?.url?.endsWith('/approve')) return Promise.reject({})
      return defaultApiRouter(config)
    })
    await vm.handleReceive(rowA as any)
    expect(ElMessage.error).toHaveBeenCalledWith('接收失败')
    wrapper.unmount()
  })

  it('拒绝流程：空原因警告 → 输入原因 → 确认成功；失败 message 与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await clickBtn(wrapper, '拒绝', 0) // rowA
    expect(vm.currentReport).toEqual(rowA)
    expect(vm.showRejectDialog).toBe(true)
    expect(vm.rejectForm.reason).toBe('')

    // 空原因 → 警告
    await vm.confirmReject()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入拒绝原因')

    // 拒绝对话框 v-model 内联更新（ElInput 拒绝原因）
    wrapper.findComponent({ name: 'ElInput' }).vm.$emit('update:modelValue', '数据不全')
    await nextTick()
    expect(vm.rejectForm.reason).toBe('数据不全')

    // 确认拒绝成功
    mockApiRequest.mockClear()
    vm.pagination.page = 2
    await clickBtn(wrapper, '确认拒绝')
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'POST',
        url: '/data-reports/101/review',
        data: { decision: 'reject', comment: '数据不全' },
      })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('已拒绝该数据包')
    expect(vm.showRejectDialog).toBe(false)
    expect(vm.pagination.page).toBe(1)
    expect(vm.rejecting).toBe(false)

    // 失败：message 与「操作失败」兜底
    vm.handleReject(rowB as any)
    mockApiRequest.mockImplementation((config: any) => {
      if (config?.url?.endsWith('/review')) return Promise.reject(new Error('理由太短'))
      return defaultApiRouter(config)
    })
    vm.rejectForm.reason = 'x'
    await vm.confirmReject()
    expect(ElMessage.error).toHaveBeenCalledWith('理由太短')
    mockApiRequest.mockImplementation((config: any) => {
      if (config?.url?.endsWith('/review')) return Promise.reject({})
      return defaultApiRouter(config)
    })
    await vm.confirmReject()
    expect(ElMessage.error).toHaveBeenCalledWith('操作失败')
    expect(vm.rejecting).toBe(false)
    wrapper.unmount()
  })

  it('拒绝对话框「取消」内联关闭', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleReject(rowA as any)
    await nextTick()
    expect(vm.showRejectDialog).toBe(true)
    // 「取消」[0] 是本地导入对话框 footer，[1] 才是拒绝对话框 footer（内联 showRejectDialog=false）
    await clickBtn(wrapper, '取消', 1)
    expect(vm.showRejectDialog).toBe(false)
    wrapper.unmount()
  })

  it('点击「下载」：成功提示；失败提示下载失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await clickBtn(wrapper, '下载', 0) // rowA
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'GET', url: '/data-reports/101/package' })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('下载已开始')
    mockApiRequest.mockImplementation((config: any) => {
      if (config?.url?.endsWith('/package')) return Promise.reject(new Error('net'))
      return defaultApiRouter(config)
    })
    await vm.handleDownload(rowB as any)
    expect(ElMessage.error).toHaveBeenCalledWith('下载失败')
    wrapper.unmount()
  })
})

describe('预览对话框', () => {
  it('点击「预览」：数组响应渲染 tabs/列/未知类型回退，currentReport 字段左侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await clickBtn(wrapper, '预览', 0) // rowA
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'GET', url: '/data-reports/101' })
    )
    expect(vm.showPreviewDialog).toBe(true)
    expect(vm.previewData).toEqual(previewArray)
    await nextTick()
    // currentReport 左侧面：单位甲 / PKG-A / 5
    expect(wrapper.text()).toContain('单位甲')
    expect(wrapper.text()).toContain('PKG-A')
    // getDataTypeLabel 已知 + 未知回退（stub 未声明 props，label 落在 attrs 上）
    // 前两个页签为页面级「上报列表/接收记录」，其余为预览数据类型页签
    const tabLabels = wrapper.findAll('el-tab-pane-stub').map((t: any) => t.attributes('label'))
    expect(tabLabels).toEqual(['上报列表', '接收记录', '村庄数据 (2)', 'unknown_type (0)'])
    // getColumnLabel 已知 + 未知回退（列 label 同为 attr）
    const colLabels = wrapper
      .findAll('.el-table-column-stub')
      .map((c: any) => c.attributes('label'))
    expect(colLabels).toContain('编号')
    expect(colLabels).toContain('名称')
    expect(colLabels).toContain('mystery_col')
    wrapper.unmount()
  })

  it('预览：{data:[...]} 嵌套形态 + 稀疏 currentReport 全部右侧兜底', async () => {
    mockApiRequest.mockImplementation((config: any) => {
      if (/^\/data-reports\/\d+$/.test(config?.url || '')) {
        return Promise.resolve({ data: previewArray })
      }
      return defaultApiRouter(config)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handlePreview({ id: 9 } as any) // 无任何可选字段
    expect(vm.previewData).toEqual(previewArray)
    await nextTick()
    const text = wrapper.text()
    expect(text).not.toContain('单位#9') // 预览对话框名称缺失 → '-'
    wrapper.unmount()
  })

  it('预览：null 响应 → [] 兜底渲染「暂无预览数据」；接口失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockApiRequest.mockImplementation((config: any) => {
      if (/^\/data-reports\/\d+$/.test(config?.url || '')) return Promise.resolve(null)
      return defaultApiRouter(config)
    })
    await vm.handlePreview(rowA as any)
    expect(vm.previewData).toEqual([])
    await nextTick()
    // v-else 分支：预览 el-empty 渲染（description 落在 attr 上）
    const empties = wrapper.findAll('el-empty-stub')
    expect(empties.some((e: any) => e.attributes('description') === '暂无预览数据')).toBe(true)

    mockApiRequest.mockImplementation((config: any) => {
      if (/^\/data-reports\/\d+$/.test(config?.url || '')) return Promise.reject(new Error('down'))
      return defaultApiRouter(config)
    })
    await vm.handlePreview(rowB as any)
    expect(ElMessage.error).toHaveBeenCalledWith('加载预览数据失败')
    expect(logError).toHaveBeenCalledWith('[ReceivePackage] 预览失败:', expect.any(Error))
    wrapper.unmount()
  })
})

describe('本地文件导入', () => {
  it('点击「从本地文件导入」打开对话框；对话框 v-model 内联更新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.showLocalImport).toBe(false)
    await clickBtn(wrapper, '从本地文件导入')
    expect(vm.showLocalImport).toBe(true)

    // 三个对话框 v-model 内联 onUpdate:modelValue
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    dialogs[0].vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.showLocalImport).toBe(false)

    vm.showPreviewDialog = true
    vm.showRejectDialog = true
    await nextTick()
    dialogs[1].vm.$emit('update:modelValue', false)
    dialogs[2].vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.showPreviewDialog).toBe(false)
    expect(vm.showRejectDialog).toBe(false)
    wrapper.unmount()
  })

  it('handleLocalFileChange：raw 直传/嵌套/空返回；验证失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // file 为 null → !raw 直接返回
    await vm.handleLocalFileChange(null)
    expect(mockPost).not.toHaveBeenCalled()
    // file.raw 嵌套侧
    const raw = new File(['x'], 'pkg.zip')
    await vm.handleLocalFileChange({ raw })
    expect(mockPost).toHaveBeenCalledWith(
      '/data-packages/import',
      expect.any(FormData),
      expect.objectContaining({ headers: { 'Content-Type': 'multipart/form-data' } })
    )
    expect(vm.localImportStep).toBe(1)
    expect(vm.localImportInfo).toEqual({ fileName: 'pkg.zip', packageId: '42' })
    // file 直传侧（无 .raw 包装）+ errors 非空 → 验证失败
    mockPost.mockResolvedValueOnce({ errors: ['格式错误A'] })
    vm.localImportStep = 0
    await vm.handleLocalFileChange(new File(['x'], 'bad.zip'))
    expect(ElMessage.error).toHaveBeenCalledWith('数据包验证失败: 格式错误A')
    expect(vm.localImportStep).toBe(0)
    // 上传异常 → 提示失败
    mockPost.mockRejectedValueOnce(new Error('net'))
    await vm.handleLocalFileChange(new File(['x'], 'bad2.zip'))
    expect(ElMessage.error).toHaveBeenCalledWith('数据包上传失败，请检查文件格式')
    wrapper.unmount()
  })

  it('导入成功但无 package_id → 步骤 1 显示「-」', async () => {
    mockPost.mockImplementation((url: string) => {
      if (url === '/data-packages/import') return Promise.resolve({})
      return defaultPostRouter(url)
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleLocalFileChange(new File(['x'], 'pkg.zip'))
    expect(vm.localImportStep).toBe(1)
    expect(vm.localImportInfo.packageId).toBe('')
    await nextTick()
    expect(wrapper.text()).toContain('pkg.zip')
    wrapper.unmount()
  })

  it('确认导入：无 packageId 直接返回；成功进步骤 2 并渲染「关闭」；失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 无 packageId → 直接返回
    await vm.confirmLocalImport()
    expect(mockPost.mock.calls.some((c: any) => String(c[0]).includes('/confirm'))).toBe(false)

    // 成功：上传 → 步骤 1 → 点击「确认导入」→ 步骤 2
    await vm.handleLocalFileChange(new File(['x'], 'pkg.zip'))
    await nextTick()
    mockPost.mockClear()
    mockApiRequest.mockClear()
    vm.pagination.page = 4
    await clickBtn(wrapper, '确认导入')
    expect(mockPost).toHaveBeenCalledWith('/data-packages/42/confirm', {
      package_id: 42,
      confirm: true,
    })
    expect(vm.localImportStep).toBe(2)
    expect(ElMessage.success).toHaveBeenCalledWith('数据包导入成功')
    expect(vm.pagination.page).toBe(1)
    expect(vm.localImporting).toBe(false)
    expect(mockApiRequest.mock.calls.some((c: any) => c[0]?.url === '/data-reports/received')).toBe(
      true
    )
    await nextTick()
    // footer 按钮步骤 2 → 「关闭」三元右侧
    const closeBtns = wrapper
      .findAll('el-button-stub')
      .filter((b: any) => b.text().trim() === '关闭')
    expect(closeBtns.length).toBe(1)
    // 点击「关闭」→ closeLocalImport：清空并关窗
    await closeBtns[0].trigger('click')
    await flushPromises()
    expect(vm.showLocalImport).toBe(false)
    expect(vm.localImportStep).toBe(0)
    expect(vm.localImportInfo).toEqual({ fileName: '', packageId: '' })

    // 失败：confirm 接口抛错
    await vm.handleLocalFileChange(new File(['x'], 'pkg.zip'))
    mockPost.mockImplementation((url: string) => {
      if (url.includes('/confirm')) return Promise.reject(new Error('net'))
      return defaultPostRouter(url)
    })
    await vm.confirmLocalImport()
    expect(ElMessage.error).toHaveBeenCalledWith('导入确认失败')
    expect(vm.localImporting).toBe(false)
    wrapper.unmount()
  })

  it('clearLocalImport：clearFiles 调用 / localUploadRef 为 null / 无 clearFiles 三侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 步骤 0 时 upload stub 已挂载（带 clearFiles 方法）→ ?.clearFiles?.() 调用侧
    const clearSpy = vi.spyOn(vm.localUploadRef, 'clearFiles')
    vm.localImportStep = 1
    vm.localImportInfo.fileName = 'x.zip'
    vm.clearLocalImport()
    expect(clearSpy).toHaveBeenCalled()
    expect(vm.localImportStep).toBe(0)
    expect(vm.localImportInfo.fileName).toBe('')
    // 模板 ref 为 null 的短路侧
    vm.localUploadRef = null
    vm.clearLocalImport()
    expect(vm.localImportStep).toBe(0)
    // clearFiles 不存在的 ?. 短路侧
    vm.localUploadRef = {}
    vm.localImportStep = 1
    vm.clearLocalImport()
    expect(vm.localImportStep).toBe(0)
    wrapper.unmount()
  })
})

describe('分页与错误边界', () => {
  it('el-pagination：v-model 内联更新与 size-change/current-change 触发加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const pager = wrapper.findComponent({ name: 'ElPagination' })
    pager.vm.$emit('update:currentPage', 2)
    pager.vm.$emit('update:pageSize', 50)
    await nextTick()
    expect(vm.pagination.page).toBe(2)
    expect(vm.pagination.pageSize).toBe(50)

    mockApiRequest.mockClear()
    pager.vm.$emit('size-change', 50)
    await flushPromises()
    expect(mockApiRequest.mock.calls.some((c: any) => c[0]?.url === '/data-reports/received')).toBe(
      true
    )
    mockApiRequest.mockClear()
    pager.vm.$emit('current-change', 2)
    await flushPromises()
    expect(mockApiRequest.mock.calls.some((c: any) => c[0]?.url === '/data-reports/received')).toBe(
      true
    )
    wrapper.unmount()
  })

  it('子组件抛 Error → 错误回退卡展示，点击「重试」清除并重新加载', async () => {
    const wrapper = mountComp({
      'el-tag': {
        name: 'ElTag',
        setup() {
          throw new Error('标签渲染爆炸')
        },
        template: '<div class="el-tag-throw" />',
      },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(logError).toHaveBeenCalledWith('[ReceivePackage] 组件异常:', expect.any(Error))
    expect(vm.componentError).toBe('标签渲染爆炸')
    await nextTick()
    expect(wrapper.text()).toContain('页面加载异常')
    await clickBtn(wrapper, '重试')
    expect(vm.componentError).toBe('')
    wrapper.unmount()
  })

  it('子组件抛非 Error → 兜底文案「未知错误，请重试」', async () => {
    const wrapper = mountComp({
      'el-tag': {
        name: 'ElTag',
        setup() {
          // eslint-disable-next-line no-throw-literal
          throw '字符串异常'
        },
        template: '<div class="el-tag-throw" />',
      },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.componentError).toBe('未知错误，请重试')
    wrapper.unmount()
  })
})

describe('接收记录 tab（仅管理员）', () => {
  it('parseValidationSummary / classifyWarningLine / formatFileSize 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // parseValidationSummary：非数组 / 匹配 / 无匹配
    expect(vm.parseValidationSummary(null)).toBeNull()
    expect(vm.parseValidationSummary('not-array')).toBeNull()
    expect(vm.parseValidationSummary(['通过2条/纠正1条/拒绝0条'])).toEqual({ ok: 2, corrected: 1, rejected: 0 })
    expect(vm.parseValidationSummary(['无匹配行'])).toBeNull()
    // classifyWarningLine 三态
    expect(vm.classifyWarningLine('某字段校验未通过')).toBe('rejected')
    expect(vm.classifyWarningLine('某字段已自动纠正')).toBe('corrected')
    expect(vm.classifyWarningLine('通过3条/纠正0条/拒绝0条')).toBe('summary')
    // formatFileSize 四档
    expect(vm.formatFileSize(undefined)).toBe('-')
    expect(vm.formatFileSize(0)).toBe('-')
    expect(vm.formatFileSize(500)).toBe('500B')
    expect(vm.formatFileSize(2048)).toBe('2.0KB')
    expect(vm.formatFileSize(5000000)).toBe('4.77MB')
    wrapper.unmount()
  })

  it('loadReceived 成功解析 _vs；handleTabChange 触发加载；非管理员早退', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.loadReceived()
    expect(mockGet).toHaveBeenCalledWith('/data-packages/received', { page: 1, page_size: 20 })
    expect(vm.receivedItems).toHaveLength(2)
    expect(vm.receivedItems[0]._vs).toEqual({ ok: 2, corrected: 1, rejected: 0 })
    expect(vm.receivedItems[1]._vs).toBeNull()
    expect(vm.receivedTotal).toBe(2)
    expect(vm.receivedLoading).toBe(false)

    // handleTabChange('received') 触发加载
    mockGet.mockClear()
    vm.handleTabChange('received')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/data-packages/received', expect.anything())

    // handleTabChange('reports') 不触发
    mockGet.mockClear()
    vm.handleTabChange('reports')
    await flushPromises()
    expect(mockGet).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('非管理员：loadReceived 早退不请求', async () => {
    authState.isAdmin = false
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGet.mockClear()
    await vm.loadReceived()
    expect(mockGet).not.toHaveBeenCalled()
    expect(vm.receivedItems).toEqual([])
    wrapper.unmount()
  })

  it('loadReceived 失败 → 提示并置空', async () => {
    mockGet.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.loadReceived()
    expect(ElMessage.error).toHaveBeenCalledWith('加载接收记录失败')
    expect(vm.receivedItems).toEqual([])
    expect(vm.receivedTotal).toBe(0)
    expect(vm.receivedLoading).toBe(false)
    wrapper.unmount()
  })

  it('previewReceived 成功（数组/嵌套）与失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 数组直返
    await vm.previewReceived(recv1)
    expect(mockGet).toHaveBeenCalledWith('/data-packages/11/preview')
    expect(vm.previewData).toEqual(previewArray)
    expect(vm.currentReport.source_org_name).toBe('单位甲')
    expect(vm.currentReport.package_code).toBe('PKG-R1')
    expect(vm.currentReport.record_count).toBe(3)
    expect(vm.currentReport.created_at).toBe('2024-01-01T02:00:00')
    expect(vm.validationWarnings).toEqual(recv1.validation_summary)
    expect(vm.showPreviewDialog).toBe(true)

    // 嵌套 data.data 形态
    mockGet.mockImplementation((url: string) => {
      if (/\/preview$/.test(url)) return Promise.resolve({ data: previewArray })
      return defaultGetRouter(url)
    })
    await vm.previewReceived({ id: 99, validation_summary: 'not-array' } as any)
    expect(vm.previewData).toEqual(previewArray)
    expect(vm.validationWarnings).toEqual([]) // 非数组 → []

    // 失败
    mockGet.mockImplementation((url: string) => {
      if (/\/preview$/.test(url)) return Promise.reject(new Error('down'))
      return defaultGetRouter(url)
    })
    await vm.previewReceived(recv1)
    expect(ElMessage.error).toHaveBeenCalledWith('加载预览数据失败')
    expect(logError).toHaveBeenCalledWith('[ReceivePackage] 接收记录预览失败:', expect.any(Error))
    wrapper.unmount()
  })

  it('handleReceivedDownload 成功与失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockApiRequest.mockImplementation((config: any) => {
      if (config?.url?.endsWith('/download')) return Promise.resolve(new Blob(['x']))
      return defaultApiRouter(config)
    })
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await vm.handleReceivedDownload({ id: 11, file_name: 'a.zip' })
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'GET', url: '/data-packages/11/download' })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('下载已开始')
    // 文件名缺省 → package_code / package 兜底
    await vm.handleReceivedDownload({ id: 12, package_code: 'PKG-R2' })
    expect(ElMessage.success).toHaveBeenCalledWith('下载已开始')
    clickSpy.mockRestore()

    // 失败
    mockApiRequest.mockImplementation((config: any) => {
      if (config?.url?.endsWith('/download')) return Promise.reject(new Error('net'))
      return defaultApiRouter(config)
    })
    await vm.handleReceivedDownload({ id: 13 })
    expect(ElMessage.error).toHaveBeenCalledWith('下载失败')
    wrapper.unmount()
  })

  it('handleLocalFileChange：validation.warnings 写入字段校验报告', async () => {
    mockPost.mockResolvedValue({ package_id: 1, validation: { warnings: ['字段X校验未通过'] } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleLocalFileChange(new File(['x'], 'pkg.zip'))
    expect(vm.validationWarnings).toEqual(['字段X校验未通过'])
    wrapper.unmount()
  })

  it('接收记录列模板渲染 + 预览/下载/分页/tab 事件', async () => {
    const receivedColStub = {
      'el-table-column': {
        name: 'ElTableColumn',
        template:
          '<div class="el-table-column-stub"><slot :row="r1" /><slot :row="r2" /><slot :row="r3" /></div>',
        data() {
          return {
            r1: {
              id: 11,
              source_org_id: 1,
              source_org_name: '单位甲',
              package_code: 'PKG-R1',
              data_types: ['villages'],
              record_count: 3,
              status: 'validated',
              submitted_at: '2024-01-01T02:00:00',
              created_at: '2024-01-01T01:00:00',
              org_name: '单位甲',
              org_code: null,
              exported_by_name: '张三',
              file_name: 'a.zip',
              file_size: 2048,
              imported_at: '2024-01-01T02:00:00',
              _vs: { ok: 2, corrected: 1, rejected: 0 },
            },
            r2: {
              id: 12,
              source_org_id: 2,
              package_code: 'PKG-R2',
              data_types: '[]',
              record_count: null,
              status: 'pending',
              submitted_at: null,
              created_at: '2024-02-01T02:00:00',
              org_name: null,
              org_code: 'ORG-2',
              exported_by_name: null,
              file_name: null,
              file_size: 5000000,
              imported_at: null,
              _vs: null,
            },
            r3: {
              id: 13,
              source_org_id: 3,
              data_types: [],
              record_count: 0,
              status: 'weird',
              file_size: 500,
              _vs: undefined,
            },
          }
        },
      },
    }
    const wrapper = mountComp(receivedColStub)
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.loadReceived() // 填充 receivedTotal>0 → 分页渲染
    await nextTick()

    const text = wrapper.text()
    // 校验结果列：_vs 有值 → 通过/纠正/拒绝
    expect(text).toContain('通过2')
    expect(text).toContain('纠正1')
    expect(text).toContain('拒绝0')
    // 文件大小格式化三档
    expect(text).toContain('2.0KB')
    expect(text).toContain('4.77MB')
    expect(text).toContain('500B')
    // 来源组织 org_code 兜底
    expect(text).toContain('ORG-2')

    // 接收记录 预览 按钮（仅 validated 行）：报告列表 3 + 接收记录 1
    const previewBtns = wrapper.findAll('el-button-stub').filter((b: any) => b.text().trim() === '预览')
    expect(previewBtns.length).toBe(4)
    await previewBtns[3].trigger('click')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/data-packages/11/preview')
    expect(vm.showPreviewDialog).toBe(true)

    // 接收记录 下载 按钮：报告列表 3 + 接收记录 3，取最后一个
    mockApiRequest.mockImplementation((config: any) => {
      if (config?.url?.endsWith('/download')) return Promise.resolve(new Blob(['x']))
      return defaultApiRouter(config)
    })
    const dlBtns = wrapper.findAll('el-button-stub').filter((b: any) => b.text().trim() === '下载')
    expect(dlBtns.length).toBe(6)
    await dlBtns[5].trigger('click')
    await flushPromises()
    expect(ElMessage.success).toHaveBeenCalledWith('下载已开始')

    // 接收记录分页 v-model + size/current change（第二个 el-pagination）
    const pagers = wrapper.findAllComponents({ name: 'ElPagination' })
    expect(pagers.length).toBe(2)
    pagers[1].vm.$emit('update:currentPage', 2)
    pagers[1].vm.$emit('update:pageSize', 50)
    await nextTick()
    expect(vm.receivedPagination.page).toBe(2)
    expect(vm.receivedPagination.pageSize).toBe(50)
    mockGet.mockClear()
    pagers[1].vm.$emit('size-change', 50)
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/data-packages/received', expect.anything())

    // el-tabs v-model + tab-change
    const tabs = wrapper.findComponent({ name: 'ElTabs' })
    tabs.vm.$emit('update:modelValue', 'received')
    await nextTick()
    expect(vm.activeTab).toBe('received')
    mockGet.mockClear()
    tabs.vm.$emit('tab-change', 'received')
    await flushPromises()
    expect(mockGet).toHaveBeenCalledWith('/data-packages/received', expect.anything())

    wrapper.unmount()
  })
})

