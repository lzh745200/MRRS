/**
 * views/projects/Import.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：五步向导切换、downloadTemplate（成功/失败）、handleFileChange 全分支
 * （扩展名非法/超 10MB/合法）、handleExceed、handleUpload（无文件/成功/解析失败/异常）、
 * confirmImport（成功/失败）、resetImport、redirectToList、模板各步骤渲染。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { ElMessage, pushSafeMock, requestMock } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  pushSafeMock: vi.fn(),
  requestMock: {
    requestGet: vi.fn(),
    post: vi.fn(),
    downloadBlob: vi.fn(),
    parseContentDisposition: vi.fn(),
  },
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
}))

vi.mock('@/api/request', () => ({
  default: { get: requestMock.requestGet },
  post: requestMock.post,
  downloadBlob: requestMock.downloadBlob,
  parseContentDisposition: requestMock.parseContentDisposition,
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/composables/useDesensitize', () => ({
  useDesensitize: () => ({
    ds: (value: any, _type: string) => String(value ?? ''),
    role: 'viewer',
  }),
}))

import Import from '@/views/projects/Import.vue'

const previewRows = [
  {
    row_number: 1,
    has_error: false,
    data: {
      name: '项目A',
      type: 'infrastructure',
      responsible_person: '张三',
      contact_phone: '13800138000',
      start_date: '2024-01-01',
      end_date: '2024-06-01',
      budget: 100,
      status: '规划中',
      village_name: '村A',
      description: '描述',
    },
  },
  {
    row_number: 2,
    has_error: true,
    errors: [{ message: '名称必填' }, { message: '日期格式错误' }],
    data: {},
  },
]

const emptyRow = {
  row_number: 3,
  has_error: false,
  data: {},
}

function mountComp() {
  return mount(Import, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
        'el-icon': { template: '<span class="el-icon-stub"><slot /></span>' },
        'el-breadcrumb': { template: '<div class="el-breadcrumb-stub"><slot /></div>' },
        'el-breadcrumb-item': { template: '<span class="el-breadcrumb-item-stub"><slot /></span>' },
        'el-steps': { template: '<div class="el-steps-stub"><slot /></div>' },
        'el-step': { template: '<div class="el-step-stub"><slot /></div>' },
        'el-alert': {
          template: '<div class="el-alert-stub"><slot /></div>',
          props: ['title', 'type'],
        },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-upload': { template: '<div class="el-upload-stub"><slot /><slot name="tip" /></div>' },
        'el-table': {
          template: '<div class="el-table-stub"><slot name="empty" /><slot name="default" /></div>',
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>',
          data() {
            return { rowA: previewRows[0], rowB: previewRows[1], rowC: emptyRow }
          },
        },
        'el-empty': {
          template:
            '<div class="el-empty-stub"><slot name="description" /><slot name="bottom" /></div>',
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  requestMock.requestGet.mockResolvedValue({ data: new Blob(['x']), headers: {} })
  requestMock.parseContentDisposition.mockReturnValue('项目导入模板.xlsx')
  requestMock.downloadBlob.mockReturnValue(undefined)
  requestMock.post.mockResolvedValue({
    rows: previewRows,
    invalid_rows: 1,
  })
  pushSafeMock.mockReturnValue(undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('步骤向导', () => {
  it('初始为步骤 0（下载模板）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).currentStep).toBe(0)
    expect(wrapper.text()).toContain('下载导入模板')
  })

  it('跳过步骤 → 步骤 1', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('跳过'))
    await btn!.trigger('click')
    expect((wrapper.vm as any).currentStep).toBe(1)
  })

  it('继续上传 → 步骤 2', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 自然流程：步骤0 → 跳过此步 → 步骤1 → 继续上传
    const skip = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('跳过'))
    await skip!.trigger('click')
    await wrapper.vm.$nextTick()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('继续上传'))
    expect(btn, '继续上传按钮').toBeTruthy()
    await btn!.trigger('click')
    await wrapper.vm.$nextTick()
    expect(vm.currentStep).toBe(2)
    // 再次点击（同一步骤块内重复触发编译后的缓存内联函数）
    vm.currentStep = 1
    await wrapper.vm.$nextTick()
    await wrapper
      .findAll('.el-button-stub')
      .find((b) => b.text().includes('继续上传'))!
      .trigger('click')
    await wrapper.vm.$nextTick()
    expect(vm.currentStep).toBe(2)
  })

  it('步骤3 返回修改 → 步骤 2', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentStep = 3
    vm.previewData = [previewRows[0]]
    await wrapper.vm.$nextTick()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('返回修改'))
    expect(btn, '步骤3返回修改按钮').toBeTruthy()
    await btn!.trigger('click')
    expect(vm.currentStep).toBe(2)
  })

  it('返回修改 → 步骤 1', async () => {
    const wrapper = mountComp()
    await flushPromises()
    ;(wrapper.vm as any).currentStep = 2
    await wrapper.vm.$nextTick()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('返回修改'))
    await btn!.trigger('click')
    expect((wrapper.vm as any).currentStep).toBe(1)
  })

  it('步骤3 校验失败视图的返回修改按钮 → 步骤 2（L168 内联处理器）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentStep = 3
    vm.loading = false
    vm.validationFailed = true
    vm.validationErrors = [{ index: 1, message: '名称必填' }]
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('名称必填')
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('返回修改'))
    expect(btn, '校验失败返回修改按钮').toBeTruthy()
    await btn!.trigger('click')
    expect(vm.currentStep).toBe(2)
  })
})

describe('downloadTemplate', () => {
  it('成功下载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.downloadTemplate()
    // 使用裸 axios 实例（default export）请求 Blob，便于读取响应头文件名
    expect(requestMock.requestGet).toHaveBeenCalledWith('/import/template', {
      params: { entity_type: 'project' },
      responseType: 'blob',
    })
    expect(requestMock.downloadBlob).toHaveBeenCalled()
    expect(vm.downloading).toBe(false)
  })

  it('失败 → 错误提示', async () => {
    requestMock.requestGet.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).downloadTemplate()
    expect(ElMessage.error).toHaveBeenCalledWith('模板下载失败，请重试')
  })

  it('下载模板按钮 → 触发下载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('下载导入模板'))
    await btn!.trigger('click')
    await flushPromises()
    expect(requestMock.requestGet).toHaveBeenCalled()
  })

  it('下载模板 resp 无 data → Blob 兜底（resp.data 缺失）', async () => {
    requestMock.requestGet.mockResolvedValue({ headers: {} })
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).downloadTemplate()
    expect(requestMock.downloadBlob).toHaveBeenCalled()
  })
})

describe('handleFileChange', () => {
  it('合法文件 → 加入列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const file = { name: 'data.xlsx', size: 1000 }
    const result = vm.handleFileChange(file, [file])
    expect(result).toBe(true)
    expect(vm.fileList).toHaveLength(1)
  })

  it('非法扩展名 → 错误 + 清空', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const file = { name: 'data.csv', size: 1000 }
    const result = vm.handleFileChange(file, [file])
    expect(result).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('请上传.xlsx或.xls格式的文件')
    expect(vm.fileList).toHaveLength(0)
  })

  it('超过 10MB → 错误 + 清空', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const file = { name: 'data.xlsx', size: 11 * 1024 * 1024 }
    const result = vm.handleFileChange(file, [file])
    expect(result).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('文件大小不能超过10MB')
    expect(vm.fileList).toHaveLength(0)
  })

  it('多文件时取最后一个', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const f1 = { name: 'a.xlsx', size: 1 }
    const f2 = { name: 'b.xlsx', size: 2 }
    vm.handleFileChange(f2, [f1, f2])
    expect(vm.fileList).toHaveLength(1)
  })

  it('handleExceed → 错误', async () => {
    const wrapper = mountComp()
    await flushPromises()
    ;(wrapper.vm as any).handleExceed()
    expect(ElMessage.error).toHaveBeenCalledWith('只能上传一个文件')
  })
})

describe('handleUpload', () => {
  it('无文件 → warning', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleUpload()
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择要上传的文件')
  })

  it('解析成功 → 步骤 3 + 预览数据', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fileList = [{ raw: new File(['x'], 'd.xlsx') }]
    await vm.handleUpload()
    expect(requestMock.post).toHaveBeenCalledWith(
      '/import/preview?entity_type=project',
      expect.any(FormData),
      expect.objectContaining({ timeout: 120000 })
    )
    expect(vm.currentStep).toBe(3)
    expect(vm.previewData).toHaveLength(2)
    expect(vm.previewData[0].projectName).toBe('项目A')
    expect(vm.previewData[1].projectName).toBe('')
    expect(vm.validationFailed).toBe(true)
    expect(vm.validationErrors).toEqual([{ index: 2, message: '名称必填; 日期格式错误' }])
    expect(vm.loading).toBe(false)
  })

  it('解析成功且无失败行 / project_name 兜底 / 无 errors 兜底', async () => {
    requestMock.post.mockResolvedValue({
      rows: [
        { row_number: 1, has_error: false, data: { project_name: 'P名称', budget: 5 } },
        { row_number: 2, has_error: true, data: {} },
      ],
      invalid_rows: 0,
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fileList = [{ raw: new File(['x'], 'd.xlsx') }]
    await vm.handleUpload()
    expect(vm.previewData[0].projectName).toBe('P名称')
    expect(vm.previewData[0].totalBudget).toBe(5)
    expect(vm.validationFailed).toBe(false)
    expect(vm.validationErrors).toEqual([{ index: 2, message: '' }])
  })

  it('全部行 has_error → 全部计入校验错误', async () => {
    requestMock.post.mockResolvedValue({
      rows: [
        { row_number: 1, has_error: true, errors: [{ message: 'E1' }], data: {} },
        { row_number: 2, has_error: true, errors: [{ message: 'E2' }], data: {} },
      ],
      invalid_rows: 2,
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fileList = [{ raw: new File(['x'], 'd.xlsx') }]
    await vm.handleUpload()
    expect(vm.validationErrors).toEqual([
      { index: 1, message: 'E1' },
      { index: 2, message: 'E2' },
    ])
  })

  it('行无 row_number → idx+1 兜底', async () => {
    requestMock.post.mockResolvedValue({
      rows: [{ has_error: false, data: { name: 'N' } }],
      invalid_rows: 0,
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fileList = [{ raw: new File(['x'], 'd.xlsx') }]
    await vm.handleUpload()
    expect(vm.previewData[0].rowIndex).toBe(1)
  })

  it('响应无 rows → 解析失败提示', async () => {
    requestMock.post.mockResolvedValue({ other: 1 })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fileList = [{ raw: new File(['x'], 'd.xlsx') }]
    await vm.handleUpload()
    expect(ElMessage.error).toHaveBeenCalledWith('文件解析失败，请检查文件格式')
  })

  it('file 无 raw 字段 → || file 兜底', async () => {
    requestMock.post.mockResolvedValue({ rows: [], invalid_rows: 0 })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fileList = [{ name: 'd.xlsx', size: 1 }]
    await vm.handleUpload()
    expect(requestMock.post).toHaveBeenCalled()
  })

  it('请求异常 → 解析失败 detail', async () => {
    requestMock.post.mockRejectedValue({ response: { data: { detail: '格式错误' } } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fileList = [{ raw: new File(['x'], 'd.xlsx') }]
    await vm.handleUpload()
    expect(ElMessage.error).toHaveBeenCalledWith('解析失败: 格式错误')

    requestMock.post.mockRejectedValue(new Error('网络错误'))
    await vm.handleUpload()
    expect(ElMessage.error).toHaveBeenCalledWith('解析失败: 网络错误')

    requestMock.post.mockRejectedValue({})
    await vm.handleUpload()
    expect(ElMessage.error).toHaveBeenCalledWith('解析失败: 文件解析失败')
  })

  it('开始解析按钮（disabled 无文件）→ 无文件提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    ;(wrapper.vm as any).currentStep = 2
    await wrapper.vm.$nextTick()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('开始解析'))
    expect(btn).toBeTruthy()
    // VTU trigger 会跳过 disabled 元素，先移除属性再点击
    btn!.element.removeAttribute('disabled')
    await btn!.trigger('click')
    await flushPromises()
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择要上传的文件')
  })
})

describe('confirmImport', () => {
  it('导入成功（有失败行）→ 步骤 4 + 结果', async () => {
    requestMock.post.mockResolvedValue({ success_rows: 2, failed_rows: 1, total_rows: 3 })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fileList = [{ raw: new File(['x'], 'd.xlsx') }]
    await vm.confirmImport()
    expect(vm.currentStep).toBe(4)
    expect(vm.importResult).toEqual({
      success: true,
      failure: true,
      successCount: 2,
      failureCount: 1,
      totalCount: 3,
    })
    expect(vm.importLoading).toBe(false)
  })

  it('导入成功无失败行/无计数 → || 0 兜底', async () => {
    requestMock.post.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fileList = [{ raw: new File(['x'], 'd.xlsx') }]
    await vm.confirmImport()
    expect(vm.importResult).toEqual({
      success: true,
      failure: false,
      successCount: 0,
      failureCount: 0,
      totalCount: 0,
    })
  })

  it('confirmImport 时 file 无 raw → || file 兜底', async () => {
    requestMock.post.mockResolvedValue({ success_rows: 1, failed_rows: 0, total_rows: 1 })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fileList = [{ name: 'd.xlsx' }]
    await vm.confirmImport()
    expect(vm.importResult.success).toBe(true)
  })

  it('导入失败 → 失败结果 + message', async () => {
    requestMock.post.mockRejectedValue({ response: { data: { detail: '导入失败' } } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fileList = [{ raw: new File(['x'], 'd.xlsx') }]
    vm.totalRows = 5
    await vm.confirmImport()
    expect(vm.currentStep).toBe(4)
    expect(vm.importResult).toEqual({
      success: false,
      failure: true,
      successCount: 0,
      failureCount: 5,
      totalCount: 5,
      message: '导入失败',
    })
  })

  it('导入失败无 detail/message → 兜底文案', async () => {
    requestMock.post.mockRejectedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.fileList = [{ raw: new File(['x'], 'd.xlsx') }]
    await vm.confirmImport()
    expect(vm.importResult.message).toBe('导入失败')
  })

  it('确认导入按钮 → confirmImport', async () => {
    requestMock.post.mockResolvedValue({ success_rows: 1, failed_rows: 0, total_rows: 1 })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentStep = 3
    vm.fileList = [{ raw: new File(['x'], 'd.xlsx') }]
    vm.previewData = [previewRows[0]]
    await wrapper.vm.$nextTick()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('确认导入'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    await flushPromises()
    expect(vm.currentStep).toBe(4)
  })
})

describe('结果页', () => {
  it('resetImport → 回到步骤 0 清空状态', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentStep = 4
    vm.fileList = [{ raw: 1 }]
    vm.previewData = [previewRows[0]]
    vm.totalRows = 1
    vm.validationFailed = true
    vm.resetImport()
    expect(vm.currentStep).toBe(0)
    expect(vm.fileList).toEqual([])
    expect(vm.previewData).toEqual([])
    expect(vm.totalRows).toBe(0)
    expect(vm.validationFailed).toBe(false)
    expect(vm.validationErrors).toEqual([])
    expect(vm.importResult.success).toBe(false)
  })

  it('重新导入按钮 → resetImport', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentStep = 4
    vm.importResult = {
      success: true,
      failure: false,
      successCount: 1,
      failureCount: 0,
      totalCount: 1,
    }
    await wrapper.vm.$nextTick()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('重新导入'))
    await btn!.trigger('click')
    expect(vm.currentStep).toBe(0)
  })

  it('查看项目列表 → pushSafe /projects', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentStep = 4
    vm.importResult = {
      success: true,
      failure: false,
      successCount: 1,
      failureCount: 0,
      totalCount: 1,
    }
    await wrapper.vm.$nextTick()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('查看项目列表'))
    await btn!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/projects')
  })

  it('导入失败视图 → 显示错误原因', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentStep = 4
    vm.importResult = {
      success: false,
      failure: true,
      successCount: 0,
      failureCount: 1,
      totalCount: 1,
      message: '',
    }
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('导入失败')
    expect(wrapper.text()).toContain('未知错误')
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('重新导入'))
    await btn!.trigger('click')
    expect(vm.currentStep).toBe(0)
  })
})

describe('projects/Import.vue 文件名校验兜底', () => {
  it('文件无名称 → 扩展名非法提示（空名兜底分支）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const st = (wrapper.vm as any).$.setupState
    st.handleFileChange({ name: '', size: 100 }, [])
    expect(ElMessage.error).toHaveBeenCalledWith('请上传.xlsx或.xls格式的文件')
  })
})


describe('downloadTemplate — 响应无 headers 字段的兜底分支', () => {
  it('resp.headers 为 undefined → 以 {} 解析文件名并使用默认文件名', async () => {
    requestMock.requestGet.mockResolvedValueOnce({ data: new Blob(['x']) })
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).downloadTemplate()
    expect(requestMock.parseContentDisposition).toHaveBeenCalledWith({}, '项目导入模板.xlsx')
    expect(requestMock.downloadBlob).toHaveBeenCalled()
  })
})
