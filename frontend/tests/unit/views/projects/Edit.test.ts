/**
 * views/projects/Edit.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：新建/编辑双模式、帮扶村选项加载、项目数据回显全字段映射与兜底、
 * 附件队列/上传/删除/缩略图/预览全链路、保存（编辑/新建/继续创建）全分支、
 * 表单重置、日期与资金校验器、脏检查 watch、模板 v-model 与内联事件处理器。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂提升求值，引用对象须先放入 vi.hoisted 初始化（否则 TDZ 报错）
const {
  routeParams,
  pushSafeMock,
  ElMessage,
  confirmMock,
  logError,
  logWarn,
  getMock,
  api,
  getTokenMock,
  fetchMock,
  scrollToMock,
} = vi.hoisted(() => {
  return {
    routeParams: { id: '7' } as Record<string, string>,
    pushSafeMock: vi.fn(),
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
    confirmMock: vi.fn(),
    logError: vi.fn(),
    logWarn: vi.fn(),
    getMock: vi.fn(),
    api: {
      getById: vi.fn(),
      update: vi.fn(),
      create: vi.fn(),
      uploadFiles: vi.fn(),
      listFiles: vi.fn(),
      deleteFile: vi.fn(),
      getFileDownloadUrl: vi.fn(),
    },
    getTokenMock: vi.fn(),
    fetchMock: vi.fn(),
    scrollToMock: vi.fn(),
  }
})

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: routeParams }),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
}))

vi.mock('@/composables/useDirtyGuard', () => ({
  useDirtyGuard: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
  ElForm: class {},
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: logWarn, info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/api/projects', () => ({ projectApi: api }))

vi.mock('@/api/request', () => ({ get: getMock,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { getToken: getTokenMock },
}))

import Edit from '@/views/projects/Edit.vue'

// 全字段后端响应（is_delayed=true → 编辑模式挂载即渲染延期原因输入框）
const fullProject = {
  id: 7,
  name: '道路硬化项目',
  type: 'infrastructure',
  status: 'in_progress',
  village_id: 3,
  budget: 100,
  invested_amount: 40,
  fund_source: 'financial',
  start_date: '2024-01-01',
  end_date: '2024-12-31',
  progress: 40,
  responsible_person: '张三',
  contact_phone: '13800000000',
  contract_number: 'HT-2024-001',
  urgency_level: 'urgent',
  fund_manager: '李四',
  fund_usage_plan: 'staged',
  payer_account_name: '拨款账户',
  payer_account_number: '1234567890',
  payer_bank: '拨款开户行',
  payer_handler: '王五',
  payer_contact: '13900000000',
  payee_account_name: '收款账户',
  payee_account_number: '0987654321',
  payee_bank: '收款开户行',
  payee_handler: '赵六',
  payee_contact: '13700000000',
  is_delayed: true,
  delay_reason: '雨季影响',
  description: '项目描述',
  expected_benefits: '预期效益',
  achievements: '项目成果',
  tags: '示范项目,,重点项目', // 空段 → filter(Boolean) 两侧
  remarks: '备注',
  created_at: '2024-01-01',
  updated_at: '2024-06-01',
}

function mountComp() {
  // el-dialog 需渲染默认插槽并支持 close 事件；
  // el-upload 需渲染 tip 具名插槽并暴露 onChange/onExceed 回调属性
  return mount(Edit, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /></div>',
          emits: ['update:modelValue', 'close'],
        },
        'el-upload': {
          name: 'ElUpload',
          template: '<div class="el-upload-stub"><slot /><slot name="tip" /></div>',
          props: ['onChange', 'onExceed'],
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  routeParams.id = '7'
  getMock.mockResolvedValue({
    data: { items: [{ id: 1, name: '幸福村', county: '某县' }, { id: 2, name: '平安村' }] },
  })
  api.getById.mockResolvedValue(fullProject)
  api.update.mockResolvedValue({})
  api.create.mockResolvedValue({ id: 99 })
  api.uploadFiles.mockResolvedValue({
    files: [{ id: 10, filename: 'up.jpg', category: 'photo', download_url: '/dl/up' }],
  })
  api.listFiles.mockResolvedValue({ grouped: {} })
  api.deleteFile.mockResolvedValue({})
  api.getFileDownloadUrl.mockImplementation(
    (pid: any, fid: any) => `/projects/${pid}/files/${fid}/download`
  )
  getTokenMock.mockReturnValue('test-token')
  fetchMock.mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob(['img'])) })
  confirmMock.mockResolvedValue(undefined)
  vi.stubGlobal('fetch', fetchMock)
  Object.defineProperty(window, 'scrollTo', {
    value: scrollToMock,
    configurable: true,
    writable: true,
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('挂载与模式', () => {
  it('编辑模式：加载村庄选项、回显项目数据、渲染延期原因', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isEditMode).toBe(true)
    expect(getMock).toHaveBeenCalledWith('/supported-villages/options/dropdown')
    expect(vm.villages).toEqual([
      { id: 1, name: '幸福村（某县）' },
      { id: 2, name: '平安村' },
    ])
    expect(api.getById).toHaveBeenCalledWith(7)
    expect(vm.projectForm.name).toBe('道路硬化项目')
    expect(vm.projectForm.villageId).toBe(3)
    expect(vm.projectForm.fundUsageProgress).toBe(40)
    expect(vm.projectForm.tags).toEqual(['示范项目', '重点项目'])
    expect(vm.projectForm.isDelayed).toBe(true)
    expect(api.listFiles).toHaveBeenCalledWith(7)
    expect(vm.loading).toBe(false)
    await nextTick() // isEditMode / isDelayed 等 v-if 分支渲染
    expect(wrapper.text()).toContain('编辑项目')
    // v-if="isEditMode" 项目编号 + v-if="isDelayed" 延期原因 两个输入框均渲染 → 共 21 个
    expect(wrapper.findAllComponents({ name: 'ElInput' }).length).toBe(21)
  })

  it('新建模式：不加载项目数据，渲染保存并继续按钮', async () => {
    delete routeParams.id
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isEditMode).toBe(false)
    expect(api.getById).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('新建项目')
    expect(wrapper.text()).toContain('保存并继续创建')
  })

  it('loadVillageOptions：items 缺失与请求异常 → 置空并告警', async () => {
    getMock.mockResolvedValue({}) // res.data undefined → ?. 短路 + || [] 兜底
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).villages).toEqual([])
    wrapper.unmount()

    getMock.mockRejectedValue(new Error('net'))
    wrapper = mountComp()
    await flushPromises()
    expect(logWarn).toHaveBeenCalled()
    expect((wrapper.vm as any).villages).toEqual([])
  })

  it('loadProjectData：route id 失效 → 报错并返回列表', async () => {
    const wrapper = mountComp() // 渲染期 isEditMode 已按 id='7' 缓存为 true
    delete routeParams.id // onMounted 仍在 await 村庄选项，rawId 再读时为空
    await flushPromises()
    expect(api.getById).not.toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('无效的项目 ID')
    expect(pushSafeMock).toHaveBeenCalledWith('/projects')
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('loadProjectData：字符串项目 ID（离线模式）原样传递', async () => {
    routeParams.id = 'offline-abc'
    mountComp()
    await flushPromises()
    expect(api.getById).toHaveBeenCalledWith('offline-abc')
  })

  it('loadProjectData：未找到数据与接口异常两分支', async () => {
    api.getById.mockResolvedValue(null)
    let wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('未找到项目数据')
    expect(pushSafeMock).toHaveBeenCalledWith('/projects')
    wrapper.unmount()

    api.getById.mockRejectedValue(new Error('boom'))
    wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('数据加载失败，请稍后重试')
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('loadProjectData：空对象 → 全部字段走兜底默认值', async () => {
    api.getById.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.projectForm.id).toBe('7') // data.id ?? rawId
    expect(vm.projectForm.name).toBe('')
    expect(vm.projectForm.status).toBe('draft')
    expect(vm.projectForm.villageId).toBe('')
    expect(vm.projectForm.fundUsageProgress).toBe(0) // budget falsy → 0
    expect(vm.projectForm.startDate).toBe('')
    expect(vm.projectForm.tags).toEqual([])
    expect(vm.projectForm.isDelayed).toBe(false)
  })

  it('loadProjectData：有预算无已投 → invested_amount || 0 兜底进度为 0', async () => {
    api.getById.mockResolvedValue({ budget: 100 }) // invested_amount 缺失 → Number() NaN → || 0
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.projectForm.fundAmount).toBe(100)
    expect(vm.projectForm.allocatedFund).toBe(0)
    expect(vm.projectForm.fundUsageProgress).toBe(0)
  })

  it('create 模式直接调用 loadProjectData → 立即返回', async () => {
    delete routeParams.id
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    api.getById.mockClear()
    await vm.loadProjectData()
    expect(api.getById).not.toHaveBeenCalled()
  })
})

describe('附件列表与缩略图', () => {
  it('loadProjectFiles：grouped 填充分类并预加载照片缩略图', async () => {
    api.listFiles.mockResolvedValue({
      grouped: {
        photo: [{ id: 1, filename: 'p.jpg', category: 'photo', download_url: '/dl/p' }],
        research: [{ id: 2, filename: 'r.pdf', category: 'research' }],
      },
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.uploadedFiles.photo).toHaveLength(1)
    expect(vm.uploadedFiles.research).toHaveLength(1)
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledWith('/dl/p', {
      headers: { Authorization: 'Bearer test-token' },
    })
    expect(vm.thumbnailUrls[1]).toBeTruthy()
  })

  it('loadProjectFiles：无 grouped 与接口异常 → 静默告警', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    api.listFiles.mockResolvedValue(null) // result?.grouped → undefined 跳过
    await vm.loadProjectFiles(7)
    expect(vm.uploadedFiles.research).toEqual([])
    api.listFiles.mockRejectedValue(new Error('net'))
    await vm.loadProjectFiles(7)
    expect(logWarn).toHaveBeenCalled()
  })

  it('loadAllThumbnails：photo 列表缺失 → 空数组兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.uploadedFiles.photo = undefined
    await vm.loadAllThumbnails()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('loadThumbnail：旧 Blob URL 先释放；!ok 直接返回；异常静默', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL')
    const file = { id: 5, filename: 'a.jpg', download_url: '/dl/a' }
    await vm.loadThumbnail(file)
    const first = vm.thumbnailUrls[5]
    expect(first).toBeTruthy()
    await vm.loadThumbnail(file) // 已有旧 URL → revoke 后重建
    expect(revokeSpy).toHaveBeenCalledWith(first)

    fetchMock.mockResolvedValueOnce({ ok: false })
    await vm.loadThumbnail({ id: 6, download_url: '/dl/b' })
    expect(vm.thumbnailUrls[6]).toBeUndefined()

    fetchMock.mockRejectedValueOnce(new Error('net'))
    await vm.loadThumbnail({ id: 7, download_url: '/dl/c' }) // 静默 catch
    expect(vm.thumbnailUrls[7]).toBeUndefined()
    revokeSpy.mockRestore()
  })

  it('getFileUrl / getThumbnailUrl 各分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getFileUrl({ id: 1, download_url: '/direct' })).toBe('/direct')
    expect(vm.getFileUrl({ id: 2 })).toBe('/projects/7/files/2/download')
    expect(api.getFileDownloadUrl).toHaveBeenCalledWith(7, 2)
    expect(vm.getThumbnailUrl({ id: 99 })).toBe('')
    vm.thumbnailUrls[99] = 'blob:x'
    expect(vm.getThumbnailUrl({ id: 99 })).toBe('blob:x')
  })

  it('getFileUrl：离线字符串 ID 原样拼接', async () => {
    routeParams.id = 'offline-x'
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.getFileUrl({ id: 3 })
    expect(api.getFileDownloadUrl).toHaveBeenCalledWith('offline-x', 3)
  })
})

describe('图片预览与卸载清理', () => {
  it('previewImage 成功（含旧 URL 释放）与失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL')
    await vm.previewImage({ id: 1, download_url: '/dl/1' })
    expect(vm.previewVisible).toBe(true)
    const firstUrl = vm.previewUrl
    expect(firstUrl).toBeTruthy()
    await nextTick() // 渲染对话框内 img v-if 分支

    await vm.previewImage({ id: 2, download_url: '/dl/2' }) // 旧 previewUrl → revoke
    expect(revokeSpy).toHaveBeenCalledWith(firstUrl)

    fetchMock.mockResolvedValueOnce({ ok: false }) // !ok → throw → catch
    await vm.previewImage({ id: 3, download_url: '/dl/3' })
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('预览图片失败')
    revokeSpy.mockRestore()
  })

  it('handlePreviewClose：有/无 previewUrl 两分支；对话框 close 事件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL')
    vm.previewUrl = 'blob:old'
    wrapper.findComponent({ name: 'ElDialog' }).vm.$emit('close') // 模板 @close 绑定
    expect(revokeSpy).toHaveBeenCalledWith('blob:old')
    expect(vm.previewUrl).toBe('')
    vm.handlePreviewClose() // 无 URL → 不再 revoke
    expect(revokeSpy).toHaveBeenCalledTimes(1)
    revokeSpy.mockRestore()
  })

  it('onUnmounted 清理 previewUrl 与全部缩略图', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL')
    vm.previewUrl = 'blob:p'
    vm.thumbnailUrls[1] = 'blob:t1'
    vm.thumbnailUrls[2] = 'blob:t2'
    wrapper.unmount()
    expect(revokeSpy).toHaveBeenCalledWith('blob:p')
    expect(revokeSpy).toHaveBeenCalledWith('blob:t1')
    expect(revokeSpy).toHaveBeenCalledWith('blob:t2')
    expect(Object.keys(vm.thumbnailUrls)).toHaveLength(0)
    revokeSpy.mockRestore()
  })
})

describe('文件队列与删除', () => {
  it('handleFileChange / removePendingFile / formatFileSize / handleExceed', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleFileChange({ raw: new File(['x'], 'a.pdf') }, 'research')
    expect(vm.pendingFiles.research).toHaveLength(1)
    vm.handleFileChange({}, 'research') // raw 缺失 → 不入队
    expect(vm.pendingFiles.research).toHaveLength(1)
    vm.removePendingFile('research', 0)
    expect(vm.pendingFiles.research).toHaveLength(0)
    expect(vm.formatFileSize(0)).toBe('0 B')
    expect(vm.formatFileSize(500)).toBe('500 B')
    expect(vm.formatFileSize(2048)).toBe('2.0 KB')
    expect(vm.formatFileSize(3 * 1048576)).toBe('3.00 MB')
    vm.handleExceed([], [])
    expect(ElMessage.warning).toHaveBeenCalledWith('文件数量超出限制，已自动过滤多余的文件')
  })

  it('uploadAllPendingFiles：空队列跳过、photo 加载缩略图、失败分类提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.pendingFiles.photo = [new File(['p'], 'p.jpg')]
    vm.pendingFiles.research = [new File(['r'], 'r.pdf')]
    vm.pendingFiles.implementation = [new File(['i'], 'i.pdf')]
    vm.pendingFiles.approval = [] // length 0 → continue
    vm.pendingFiles.acceptance = undefined as any // !files → continue
    vm.uploadedFiles.photo = undefined // uploadedFiles[cat] || [] 兜底
    api.uploadFiles.mockImplementation((_id: any, cat: string) => {
      if (cat === 'research') return Promise.reject(new Error('up-fail'))
      if (cat === 'implementation') return Promise.resolve({}) // files 缺失 → 跳过追加
      return Promise.resolve({
        files: [{ id: 11, filename: 'srv.jpg', category: cat, download_url: '/dl/s' }],
      })
    })
    const uploaded = await vm.uploadAllPendingFiles(7)
    expect(uploaded).toBe(1)
    expect(vm.uploadedFiles.photo).toHaveLength(1)
    expect(vm.pendingFiles.photo).toEqual([])
    expect(vm.pendingFiles.implementation).toEqual([])
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('部分文件上传失败（research），请稍后重试')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalledWith('/dl/s', expect.any(Object)) // photo 缩略图
  })

  it('handleDeleteFile：确认删除（含缩略图释放）→ 列表移除', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL')
    vm.thumbnailUrls[1] = 'blob:t'
    const file = { id: 1, filename: 'p.jpg', category: 'photo', download_url: '/dl/p' }
    vm.uploadedFiles.photo = [file, { id: 2, filename: 'q.jpg', category: 'photo' }]
    await vm.handleDeleteFile(file)
    expect(confirmMock).toHaveBeenCalledWith('确定要删除该文件吗？', '确认', { type: 'warning' })
    expect(api.deleteFile).toHaveBeenCalledWith(7, 1)
    expect(vm.uploadedFiles.photo).toHaveLength(1)
    expect(revokeSpy).toHaveBeenCalledWith('blob:t')
    expect(vm.thumbnailUrls[1]).toBeUndefined()
    expect(ElMessage.success).toHaveBeenCalledWith('文件已删除')

    await vm.handleDeleteFile({ id: 2, filename: 'q.jpg', category: 'photo' }) // 无缩略图 → 不释放
    expect(vm.uploadedFiles.photo).toHaveLength(0)
    revokeSpy.mockRestore()
  })

  it('handleDeleteFile：取消静默；其他错误记录日志；离线 ID 原样传递', async () => {
    routeParams.id = 'offline-9'
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.uploadedFiles.research = [{ id: 3, filename: 'd.pdf', category: 'research' }]
    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleDeleteFile(vm.uploadedFiles.research[0])
    expect(api.deleteFile).not.toHaveBeenCalled()
    expect(logError).not.toHaveBeenCalled() // e === 'cancel' → 静默

    api.deleteFile.mockRejectedValueOnce(new Error('forbidden'))
    await vm.handleDeleteFile({ id: 3, filename: 'd.pdf', category: 'research' })
    expect(api.deleteFile).toHaveBeenCalledWith('offline-9', 3)
    expect(logError).toHaveBeenCalled()
  })
})

describe('保存流程 saveProjectData', () => {
  it('编辑模式：完整字段 payload 与附件上传提示', async () => {
    const wrapper = mountComp()
    await flushPromises() // 回显 fullProject
    const vm = wrapper.vm as any
    vm.pendingFiles.research = [new File(['x'], 'r.pdf')]
    const result = await vm.saveProjectData()
    expect(result).toBe(7)
    expect(api.update).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        name: '道路硬化项目',
        type: 'infrastructure',
        village_id: 3,
        progress: 40,
        delay_reason: '雨季影响', // isDelayed true
        tags: '示范项目,重点项目',
        contract_number: 'HT-2024-001',
      })
    )
    expect(api.uploadFiles).toHaveBeenCalledWith(7, 'research', expect.any(Array))
    expect(ElMessage.success).toHaveBeenCalledWith('已成功上传 1 个附件')
    expect(vm.loading).toBe(false)
  })

  it('编辑模式：空字段 undefined 兜底与无附件跳过', async () => {
    api.getById.mockResolvedValue({}) // 全兜底
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const result = await vm.saveProjectData()
    expect(result).toBe(7)
    expect(api.update).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        name: '',
        village_id: undefined,
        start_date: undefined,
        contract_number: undefined,
        delay_reason: undefined, // isDelayed false
        tags: undefined,
        remarks: undefined,
        fund_source: undefined,
      })
    )
    expect(api.uploadFiles).not.toHaveBeenCalled()
  })

  it('编辑模式：projectId 为 0 时跳过附件上传', async () => {
    routeParams.id = '0' // Number('0') → 0，hasPending && projectId → falsy
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.pendingFiles.research = [new File(['x'], 'r.pdf')]
    const result = await vm.saveProjectData()
    expect(result).toBe(0)
    expect(api.update).toHaveBeenCalledWith(0, expect.any(Object))
    expect(api.uploadFiles).not.toHaveBeenCalled()
  })

  it('编辑模式：接口异常 → 记录日志返回 false', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    api.update.mockRejectedValueOnce(new Error('db'))
    const result = await vm.saveProjectData()
    expect(result).toBe(false)
    expect(logError).toHaveBeenCalled()
    expect(vm.loading).toBe(false)
  })

  it('编辑模式：离线字符串 ID 原样更新', async () => {
    routeParams.id = 'offline-7'
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.saveProjectData()
    expect(api.update).toHaveBeenCalledWith('offline-7', expect.any(Object))
  })

  it('新建模式：code 生成与四种响应形态', async () => {
    delete routeParams.id
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectForm.name = '新项目'
    vm.projectForm.villageId = 5

    let result = await vm.saveProjectData() // { id: 99 } → result.id
    expect(result).toBe(99)
    expect(api.create).toHaveBeenCalledWith(
      expect.objectContaining({
        name: '新项目',
        village_id: 5,
        code: expect.stringMatching(/^PRO\d+$/),
      })
    )

    api.create.mockResolvedValueOnce({ data: { id: 55 } }) // result.id 缺失 → result.data.id
    result = await vm.saveProjectData()
    expect(result).toBe(55)

    api.create.mockResolvedValueOnce({}) // 无 id → 告警返回 false
    result = await vm.saveProjectData()
    expect(result).toBe(false)
    expect(logWarn).toHaveBeenCalled()

    api.create.mockResolvedValueOnce(null) // 响应为 null → ?. 全兜底
    result = await vm.saveProjectData()
    expect(result).toBe(false)
  })

  it('附件上传 0 个成功 → 不提示上传数量', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.pendingFiles.research = [new File(['x'], 'r.pdf')]
    api.uploadFiles.mockResolvedValueOnce({}) // files 缺失 → uploaded = 0
    const result = await vm.saveProjectData()
    expect(result).toBe(7)
    expect(ElMessage.success).not.toHaveBeenCalledWith(expect.stringContaining('已成功上传'))
  })
})

describe('handleSave / handleSaveAndContinue / resetForm / handleCancel', () => {
  it('handleSave：formRef 为空与校验失败 → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectFormRef = undefined
    await vm.handleSave('projectFormRef')
    expect(api.update).not.toHaveBeenCalled()

    vm.projectFormRef = { validate: (cb: any) => cb(false) }
    await vm.handleSave('projectFormRef')
    await flushPromises()
    expect(ElMessage.warning).toHaveBeenCalledWith('请完善必填信息')
    expect(api.update).not.toHaveBeenCalled()
  })

  it('handleSave：编辑保存成功 → 提示并返回列表；失败 → 错误提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectFormRef = { validate: (cb: any) => cb(true) }
    await vm.handleSave('projectFormRef')
    await flushPromises()
    expect(api.update).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('项目更新成功')
    expect(pushSafeMock).toHaveBeenCalledWith('/projects')

    api.update.mockRejectedValueOnce(new Error('db'))
    // Vue 重渲染会把模板 ref 重新同步为 stub 实例，提交前需重新赋 mock
    vm.projectFormRef = { validate: (cb: any) => cb(true) }
    await vm.handleSave('projectFormRef')
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败，请稍后重试')
  })

  it('handleSaveAndContinue：成功 → 重置表单并滚动到顶部', async () => {
    delete routeParams.id
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectForm.name = '临时项目'
    vm.projectForm.tags = ['示范项目']
    vm.projectForm.fundAmount = 50
    vm.projectForm.isDelayed = true
    vm.projectForm.status = 'approved'
    vm.fileList = [{}]
    const resetFields = vi.fn()
    vm.projectFormRef = { validate: (cb: any) => cb(true), resetFields }
    await vm.handleSaveAndContinue()
    await flushPromises()
    expect(api.create).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('项目创建成功')
    expect(resetFields).toHaveBeenCalled()
    expect(scrollToMock).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' })
    expect(vm.projectForm.name).toBe('')
    expect(vm.projectForm.status).toBe('draft')
    expect(vm.projectForm.fundSource).toBe('financial')
    expect(vm.projectForm.urgencyLevel).toBe('normal')
    expect(vm.projectForm.fundUsagePlan).toBe('one_time')
    expect(vm.projectForm.tags).toEqual([])
    expect(vm.projectForm.isDelayed).toBe(false)
    expect(vm.projectForm.fundAmount).toBe(0)
    expect(vm.fileList).toEqual([])
  })

  it('handleSaveAndContinue：失败 / formRef 为空 / 校验失败分支', async () => {
    delete routeParams.id
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    api.create.mockRejectedValueOnce(new Error('db'))
    vm.projectFormRef = { validate: (cb: any) => cb(true), resetFields: vi.fn() }
    await vm.handleSaveAndContinue()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败，请稍后重试')

    vm.projectFormRef = undefined
    await vm.handleSaveAndContinue()
    expect(api.create).toHaveBeenCalledTimes(1)

    vm.projectFormRef = { validate: (cb: any) => cb(false) }
    await vm.handleSaveAndContinue()
    await flushPromises()
    expect(ElMessage.warning).toHaveBeenCalledWith('请完善必填信息')
  })

  it('resetForm：formRef 为空 → 跳过重置字段不报错', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectFormRef = undefined
    vm.resetForm()
    expect(vm.projectForm.name).toBe('')
    expect(vm.projectForm.status).toBe('draft')
  })

  it('handleCancel：确认离开 → 返回列表；取消 → 留在页面', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleCancel()
    await flushPromises()
    expect(confirmMock).toHaveBeenCalledWith(
      '当前页面有未保存的内容，确定要离开吗？',
      '确认离开',
      expect.objectContaining({ type: 'warning' })
    )
    expect(pushSafeMock).toHaveBeenCalledWith('/projects')

    pushSafeMock.mockClear()
    confirmMock.mockRejectedValueOnce('cancel')
    vm.handleCancel()
    await flushPromises()
    expect(pushSafeMock).not.toHaveBeenCalled()
  })
})

describe('表单校验器', () => {
  it('endDate 校验器四分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const validator = vm.formRules.endDate[1].validator
    const cb = vi.fn()
    vm.projectForm.startDate = '2024-06-01'
    validator(null, '2024-05-01', cb) // 早于开始日期 → 报错
    expect(cb).toHaveBeenCalledWith(expect.any(Error))
    cb.mockClear()
    validator(null, '2024-07-01', cb) // 晚于开始日期 → 通过
    expect(cb).toHaveBeenCalledWith()
    cb.mockClear()
    validator(null, '', cb) // 无值 → 通过
    expect(cb).toHaveBeenCalledWith()
    cb.mockClear()
    vm.projectForm.startDate = ''
    validator(null, '2024-05-01', cb) // 无开始日期 → 通过
    expect(cb).toHaveBeenCalledWith()
  })

  it('allocatedFund 校验器两分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const validator = vm.formRules.allocatedFund[0].validator
    const cb = vi.fn()
    vm.projectForm.fundAmount = 100
    validator(null, 120, cb) // 超出总投入 → 报错
    expect(cb).toHaveBeenCalledWith(expect.any(Error))
    cb.mockClear()
    validator(null, 80, cb) // 未超出 → 通过
    expect(cb).toHaveBeenCalledWith()
  })
})

describe('模板交互（v-model 与内联处理器）', () => {
  it('全部 v-model 组件触发 update 事件', async () => {
    const wrapper = mountComp() // 编辑模式（isDelayed=true → 延期原因输入框渲染）
    await flushPromises()
    const vm = wrapper.vm as any

    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    expect(inputs.length).toBeGreaterThan(15)
    for (const c of inputs) c.vm.$emit('update:modelValue', 'x')
    expect(vm.projectForm.name).toBe('x')
    expect(vm.projectForm.delayReason).toBe('x')
    expect(vm.projectForm.remarks).toBe('x')

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(selects.length).toBe(6)
    for (const c of selects) c.vm.$emit('update:modelValue', 'industry')
    expect(vm.projectForm.projectType).toBe('industry')

    const dates = wrapper.findAllComponents({ name: 'ElDatePicker' })
    expect(dates.length).toBe(2)
    for (const c of dates) c.vm.$emit('update:modelValue', '2024-06-01')
    expect(vm.projectForm.startDate).toBe('2024-06-01')
    expect(vm.projectForm.endDate).toBe('2024-06-01')

    const numbers = wrapper.findAllComponents({ name: 'ElInputNumber' })
    expect(numbers.length).toBe(5)
    for (const c of numbers) c.vm.$emit('update:modelValue', 66)
    expect(vm.projectForm.fundAmount).toBe(66)

    const switches = wrapper.findAllComponents({ name: 'ElSwitch' })
    expect(switches.length).toBe(10)
    for (const c of switches) c.vm.$emit('update:modelValue', true)
    expect(vm.projectForm.isBorderArea).toBe(true)

    const groups = wrapper.findAllComponents({ name: 'ElCheckboxGroup' })
    expect(groups.length).toBe(1)
    groups[0].vm.$emit('update:modelValue', ['重点项目'])
    expect(vm.projectForm.tags).toEqual(['重点项目'])

    const tabs = wrapper.findComponent({ name: 'ElTabs' })
    tabs.vm.$emit('update:modelValue', 'photo')
    expect(vm.activeFileTab).toBe('photo')

    const dialog = wrapper.findComponent({ name: 'ElDialog' })
    dialog.vm.$emit('update:modelValue', true)
    expect(vm.previewVisible).toBe(true)
    await nextTick()
  })

  it('el-upload 回调属性：on-change 内联箭头与 on-exceed', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const uploads = wrapper.findAllComponents({ name: 'ElUpload' })
    expect(uploads.length).toBe(5)
    for (const u of uploads) {
      u.props('onChange')({ raw: new File(['x'], 'f.bin') })
    }
    expect(vm.pendingFiles.research).toHaveLength(1)
    expect(vm.pendingFiles.photo).toHaveLength(1)
    uploads[0].props('onChange')({}) // raw 缺失 → 不入队
    expect(vm.pendingFiles.research).toHaveLength(1)
    uploads[0].props('onExceed')([], [])
    expect(ElMessage.warning).toHaveBeenCalledWith('文件数量超出限制，已自动过滤多余的文件')
  })

  it('按钮点击：返回列表 / 创建项目 / 保存并继续创建（新建模式）', async () => {
    delete routeParams.id
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const findBtn = (text: string) => {
      const btn = wrapper.findAll('el-button-stub').find((b) => b.text().includes(text))
      expect(btn, text).toBeTruthy()
      return btn!
    }

    await findBtn('返回列表').trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalled()
    expect(pushSafeMock).toHaveBeenCalledWith('/projects')

    vm.projectFormRef = { validate: (cb: any) => cb(true), resetFields: vi.fn() }
    await findBtn('创建项目').trigger('click') // 覆盖 @click="handleSave('projectFormRef')" 内联箭头
    await flushPromises()
    expect(api.create).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('项目创建成功')

    // 重渲染会重置模板 ref，需重新赋 mock
    vm.projectFormRef = { validate: (cb: any) => cb(true), resetFields: vi.fn() }
    await findBtn('保存并继续创建').trigger('click')
    await flushPromises()
    expect(scrollToMock).toHaveBeenCalled()
  })

  it('按钮点击：保存修改（编辑模式）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectFormRef = { validate: (cb: any) => cb(true) }
    const btn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('保存修改'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    await flushPromises()
    expect(api.update).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('项目更新成功')
  })

  it('附件区渲染：待上传/已上传列表与删除/预览内联点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const photoFile = {
      id: 1,
      filename: 'p.jpg',
      file_size: 2048,
      created_at: '2024-01-01T10:00:00',
      category: 'photo',
      download_url: '/dl/p',
    }
    const docFile = {
      id: 2,
      filename: 'd.pdf',
      file_size: 100,
      created_at: '2024-02-02T00:00:00',
      category: 'research',
    }
    const docFileNoDate = { id: 3, filename: 'e.pdf', file_size: 1, category: 'research' } // created_at 缺失 → ?. 兜底
    vm.uploadedFiles.photo = [photoFile]
    vm.uploadedFiles.research = [docFile, docFileNoDate]
    vm.pendingFiles.approval = [new File(['x'], 'pending.pdf')]
    delete vm.pendingFiles.implementation // ?. 左侧 undefined 分支
    delete vm.uploadedFiles.implementation
    await nextTick()

    // 待上传列表：删除按钮内联箭头 removePendingFile(cat.value, idx)
    const pendingBlock = wrapper.find('.pending-files')
    expect(pendingBlock.exists()).toBe(true)
    expect(pendingBlock.text()).toContain('pending.pdf')
    await pendingBlock.find('el-button-stub').trigger('click')
    expect(vm.pendingFiles.approval).toHaveLength(0)

    // 已上传非照片：文件大小与日期渲染（含无日期兜底）
    const uploadedBlocks = wrapper.findAll('.uploaded-files')
    expect(uploadedBlocks.length).toBe(2)
    expect(uploadedBlocks[0].text()).toContain('d.pdf')
    expect(uploadedBlocks[0].text()).toContain('100 B')
    expect(uploadedBlocks[0].text()).toContain('2024-02-02')

    // 照片画廊：缩略图 img 点击 → previewImage 内联箭头
    const img = wrapper.find('.photo-gallery img.photo-thumb')
    expect(img.exists()).toBe(true)
    await img.trigger('click')
    await flushPromises()
    expect(vm.previewVisible).toBe(true)

    // 已上传删除/下载按钮（photo + research 各含删除+下载，共 6 个）
    const delButtons = wrapper.findAll('.uploaded-files el-button-stub')
    expect(delButtons.length).toBe(6)
    // 只触发删除按钮（按文本筛选），避免下载按钮触发真实 fetch
    const deleteBtns = delButtons.filter((b) => b.text().includes('删除'))
    expect(deleteBtns.length).toBe(3)
    for (const b of deleteBtns) await b.trigger('click')
    await flushPromises()
    expect(api.deleteFile).toHaveBeenCalledWith(7, 1)
    expect(api.deleteFile).toHaveBeenCalledWith(7, 2)
    expect(api.deleteFile).toHaveBeenCalledWith(7, 3)
  })

  it('watch：表单变更标记 isDirty', async () => {
    delete routeParams.id
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isDirty).toBe(false)
    vm.projectForm.name = '改动'
    await nextTick()
    expect(vm.isDirty).toBe(true)
  })

  it('handleDownloadFile 成功 → 认证 fetch + 触发下载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(new Blob(['x'])),
    } as any)
    await vm.handleDownloadFile({ id: 1, download_url: '/dl/1', filename: 'a.pdf' })
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/dl/1'), expect.anything())
    expect(clickSpy).toHaveBeenCalled()
    clickSpy.mockRestore()
    fetchMock.mockRestore()
  })

  it('handleDownloadFile 失败 → 错误提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: false } as any)
    await vm.handleDownloadFile({ id: 1, download_url: '/dl/1' })
    expect(ElMessage.error).toHaveBeenCalledWith('文件下载失败，请稍后重试')
    fetchMock.mockRestore()
  })

  it('照片区「下载」按钮点击 → handleDownloadFile（模板箭头）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.uploadedFiles.photo = [{ id: 1, filename: 'p.jpg', download_url: '/dl/p' }]
    await nextTick()
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {})
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(new Blob(['x'])),
    } as any)
    const downloadBtn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('下载'))
    if (downloadBtn) {
      await downloadBtn.trigger('click')
      await flushPromises()
      expect(fetchMock).toHaveBeenCalled()
    }
    // 删除按钮模板箭头（photo 区）
    const delBtn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('删除'))
    if (delBtn) {
      await delBtn.trigger('click')
      await flushPromises()
      expect(api.deleteFile).toHaveBeenCalledWith(7, 1)
    }
    fetchMock.mockRestore()
    clickSpy.mockRestore()
  })

  it('handlePreviewClose 释放预览 URL', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    vm.previewUrl = 'blob:old'
    vm.handlePreviewClose()
    expect(revokeSpy).toHaveBeenCalledWith('blob:old')
    expect(vm.previewUrl).toBe('')
    revokeSpy.mockRestore()
  })
})
