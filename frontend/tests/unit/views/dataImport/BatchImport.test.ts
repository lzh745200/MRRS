/**
 * BatchImport.vue 组件测试
 *
 * 覆盖目标：src/views/dataImport/BatchImport.vue 100% statements
 * 场景：
 * 1. 步骤0 选择模板 - 表格插槽 / 模板选择 / 字段预览 / 下载模板（成功+失败）
 * 2. 步骤1 上传文件 - 文件选择 / 超出限制提示 / 导入模式切换
 * 3. 步骤2 数据校验 - 成功（有/无错误）/失败（停留步骤1并报错）/ 校验中状态
 * 4. 步骤3 预览 - 描述信息渲染
 * 5. 步骤4-5 导入执行 - 成功（含上传进度回调）/失败（返回预览页并报错）/ 结果页 / 重置
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// ==================== Mocks ====================

const mockPush = vi.fn(() => Promise.resolve())
const mockResolve = vi.fn(() => ({ name: 'SomeRoute', matched: [{ path: '/x' }] }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, resolve: mockResolve }),
  useRoute: () => ({ params: {}, query: {} }),
}))

const mockPost = vi.fn()
const mockRequestGet = vi.fn()
vi.mock('@/api/request', () => ({
  default: { get: (...args: any[]) => mockRequestGet(...args) },
  post: (...args: any[]) => mockPost(...args),
  get: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

// downloadBlobAsFile 默认实现：真正调用传入的 requestFn，覆盖组件内的 request.get 闭包
const mockDownloadBlobAsFile = vi.fn(async (requestFn: () => Promise<any>) => {
  await requestFn()
})
vi.mock('@/api/helpers/blobDownload', () => ({
  downloadBlobAsFile: (...args: any[]) => mockDownloadBlobAsFile(...args),
}))

const mockMessage = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
}))
vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...(actual as object), ElMessage: mockMessage }
})

import BatchImport from '@/views/dataImport/BatchImport.vue'

// ==================== Stubs ====================

/** el-table 列统一使用的示例行，覆盖所有列插槽中访问的字段 */
const sampleRow = {
  type: 'project',
  name: '帮扶项目',
  icon: 'span',
  sections: ['基本信息', '组织与资金'],
  fieldCount: 13,
  scenario: '项目批量建档',
  row: 2,
  field: '项目名称',
  message: '必填项缺失',
  error: '名称重复',
}

const stubs = {
  'el-icon': { template: '<i><slot/></i>' },
  'el-button': {
    template: '<button class="el-btn" :disabled="disabled" @click="$emit(\'click\')"><slot/></button>',
    props: ['type', 'disabled', 'loading'],
    emits: ['click'],
  },
  'el-table': { template: '<table><slot/></table>', props: ['data'] },
  'el-table-column': {
    template: '<td><slot :row="rowData" /></td>',
    props: ['prop', 'label', 'width', 'align'],
    setup() {
      return { rowData: sampleRow }
    },
  },
  'el-radio': {
    template:
      '<label class="el-radio-stub" @change="$emit(\'change\', $event)" @click="$emit(\'change\', value)"><slot/></label>',
    props: ['value', 'modelValue'],
    emits: ['change'],
  },
  'el-radio-group': {
    name: 'el-radio-group',
    template: '<div class="el-radio-group-stub"><slot/></div>',
    props: ['modelValue'],
    emits: ['update:modelValue'],
  },
  'el-input-number': {
    name: 'el-input-number',
    template: '<input class="el-input-number-stub" />',
    props: ['modelValue', 'min', 'max', 'step', 'controlsPosition'],
    emits: ['update:modelValue'],
  },
  'el-upload': {
    name: 'el-upload',
    template: '<div class="el-upload-stub"><slot/><slot name="tip"/></div>',
    props: ['onChange', 'onExceed', 'accept', 'limit', 'autoUpload', 'drag'],
  },
  'el-descriptions': { template: '<div><slot/></div>', props: ['column', 'border', 'size', 'title'] },
  'el-descriptions-item': { template: '<div><slot/></div>', props: ['label'] },
  'el-form': { template: '<form><slot/></form>' },
  'el-form-item': { template: '<div><label>{{ label }}</label><slot/></div>', props: ['label'] },
  'el-result': {
    template:
      '<div class="el-result-stub"><h3 class="result-title">{{ title }}</h3><p class="result-sub">{{ subTitle }}</p><slot/><slot name="extra"/></div>',
    props: ['icon', 'title', 'subTitle'],
  },
  'el-steps': { template: '<div><slot/></div>', props: ['active', 'finishStatus', 'alignCenter'] },
  'el-step': { template: '<div></div>', props: ['title', 'description'] },
  'el-progress': { template: '<div></div>', props: ['type', 'percentage', 'status'] },
  'el-tag': { template: '<span><slot/></span>', props: ['type', 'size', 'effect'] },
}

// ==================== Helpers ====================

function mountImport() {
  return mount(BatchImport, { global: { stubs } })
}

const xlsxFile = new File([new Blob(['pk'])], 'data.xlsx', {
  type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
})

/** 将组件推进到指定步骤（经模板按钮点击，顺带覆盖 step++/step-- 之外的语句） */
async function gotoStep(wrapper: any, vm: any, target: number) {
  vm.step = target
  await nextTick()
}

// ==================== 测试 ====================

beforeEach(() => {
  vi.clearAllMocks()
  mockRequestGet.mockResolvedValue({ data: new Blob(['x']) })
  mockPost.mockResolvedValue({ data: { error_count: 0, total_rows: 10 } })
})

describe('步骤0：选择模板', () => {
  it('初始渲染步骤0，包含模板表格与年度选择', () => {
    const wrapper = mountImport()
    expect(wrapper.text()).toContain('数据批量导入')
    expect(wrapper.text()).toContain('选择导入模板')
    expect(wrapper.text()).toContain('填报日期')
  })

  it('返回项目列表按钮触发 pushSafe', async () => {
    const wrapper = mountImport()
    const btn = wrapper.find('.header-actions .el-btn')
    await btn.trigger('click')
    expect(mockPush).toHaveBeenCalledWith('/projects')
  })

  it('选择模板后展示字段预览（必填/非必填标记）', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any

    // handleTemplateSelect 正常行
    vm.handleTemplateSelect({ type: 'project' })
    await nextTick()

    expect(vm.selectedTemplate).toBe('project')
    expect(vm.currentTemplateName).toBe('帮扶项目')
    expect(vm.previewSections.length).toBeGreaterThan(0)
    expect(wrapper.text()).toContain('项目名称')
    expect(wrapper.find('.required-mark').exists()).toBe(true)

    // handleTemplateSelect 空行不更新
    vm.handleTemplateSelect(null)
    expect(vm.selectedTemplate).toBe('project')
  })

  it('el-radio change 事件更新 selectedTemplate', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any

    const radio = wrapper.find('.el-radio-stub')
    await radio.trigger('click')
    expect(vm.selectedTemplate).toBe('project') // sampleRow.type
  })

  it('预览为空选择时 previewSections 返回空数组', () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    expect(vm.previewSections).toEqual([])
    expect(vm.currentTemplateName).toBe('')
  })

  it('点击"下一步"进入步骤1（step++ 内联语句）', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.selectedTemplate = 'fund'
    await nextTick()

    const nextBtn = wrapper.findAll('.step-actions .el-btn')[1]
    await nextBtn.trigger('click')
    expect(vm.step).toBe(1)
  })

  it('下载模板成功：调用 downloadBlobAsFile 并发起 request.get', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.selectedTemplate = 'school'
    await nextTick()

    // 通过点击"下载模板"按钮触发（覆盖模板 @click 语句）
    const downloadBtn = wrapper.findAll('.step-actions .el-btn')[0]
    await downloadBtn.trigger('click')
    await flushPromises()

    expect(mockDownloadBlobAsFile).toHaveBeenCalled()
    expect(mockRequestGet).toHaveBeenCalledWith(
      '/import/template',
      expect.objectContaining({ params: { entity_type: 'school' }, responseType: 'blob' })
    )
    // 兜底文件名包含模板名与年度
    const opts = mockDownloadBlobAsFile.mock.calls[0][1]
    expect(opts.fallbackFileName).toContain('学校信息')
    expect(opts.fallbackFileName).toContain(`${vm.selectedYear}`)
  })

  it('下载模板失败：提示错误', async () => {
    mockDownloadBlobAsFile.mockRejectedValueOnce(new Error('boom'))
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.selectedTemplate = ''
    await nextTick()

    await vm.handleDownloadTemplate()
    await flushPromises()

    expect(mockMessage.error).toHaveBeenCalledWith('下载模板失败')
  })
})

describe('步骤1：上传文件', () => {
  it('handleFileSelect 记录原始文件，信息条展示模板名', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.selectedTemplate = 'project'
    await gotoStep(wrapper, vm, 1)

    vm.handleFileSelect({ raw: xlsxFile })
    expect(vm.selectedFile).toBe(xlsxFile)
    expect(wrapper.text()).toContain('帮扶项目')
    expect(wrapper.text()).toContain('导入模式')
  })

  it('on-exceed 回调提示只能上传一个文件', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    await gotoStep(wrapper, vm, 1)

    const upload = wrapper.findComponent({ name: 'el-upload' })
    const onExceed = upload.props('onExceed') as () => void
    onExceed()
    expect(mockMessage.warning).toHaveBeenCalledWith('只能上传一个文件')
  })

  it('导入模式 radio-group v-model 更新', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    await gotoStep(wrapper, vm, 1)

    const group = wrapper.findComponent({ name: 'el-radio-group' })
    group.vm.$emit('update:modelValue', 'overwrite')
    await nextTick()
    expect(vm.importMode).toBe('overwrite')
  })

  it('年度 input-number v-model 更新', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any

    const inputNumber = wrapper.findComponent({ name: 'el-input-number' })
    inputNumber.vm.$emit('update:modelValue', 2030)
    await nextTick()
    expect(vm.selectedYear).toBe(2030)
  })

  it('点击"上一步"返回步骤0（step-- 内联语句）', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    await gotoStep(wrapper, vm, 1)

    const prevBtn = wrapper.findAll('.step-actions .el-btn')[0]
    await prevBtn.trigger('click')
    expect(vm.step).toBe(0)
  })
})

describe('步骤2：数据校验', () => {
  it('未选择文件时 handleValidate 直接返回', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    await vm.handleValidate()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('校验通过：无错误时渲染成功结果', async () => {
    mockPost.mockResolvedValue({ data: { error_count: 0, total_rows: 8 } })
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.selectedTemplate = 'project'
    vm.handleFileSelect({ raw: xlsxFile })
    await gotoStep(wrapper, vm, 1)

    // 通过点击"开始校验"按钮触发（覆盖模板 @click="handleValidate" 语句）
    const validateBtn = wrapper.findAll('.step-actions .el-btn')[1]
    await validateBtn.trigger('click')
    await flushPromises()

    expect(mockPost).toHaveBeenCalledWith(
      '/import/validate',
      expect.any(FormData),
      expect.objectContaining({ params: { entity_type: 'project' } })
    )
    expect(vm.step).toBe(2)
    expect(vm.validating).toBe(false)
    expect(vm.previewCount).toBe(8)
    expect(vm.validationErrors).toEqual([])
  })

  it('校验发现问题：错误映射到 validationErrors 并渲染表格', async () => {
    mockPost.mockResolvedValue({
      data: {
        error_count: 2,
        total_rows: 5,
        first_errors: [
          { row_number: 2, field_name: '项目名称', message: '必填项缺失' },
          { row: 3, field: '预算金额', message: '格式错误' },
        ],
      },
    })
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.handleFileSelect({ raw: xlsxFile })

    await vm.handleValidate()
    await flushPromises()

    expect(vm.validationErrors).toEqual([
      { row: 2, field: '项目名称', message: '必填项缺失' },
      { row: 3, field: '预算金额', message: '格式错误' },
    ])
    expect(wrapper.text()).toContain('发现 2 个问题')
  })

  it('校验接口异常：报错并停留步骤1（Bug#16 修复后不得进入步骤2成功页）', async () => {
    mockPost.mockRejectedValue(new Error('server error'))
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.handleFileSelect({ raw: xlsxFile })
    vm.step = 1 // 模拟真实流程：从上传页发起校验

    await vm.handleValidate()
    await flushPromises()

    expect(vm.previewCount).toBe(0)
    expect(vm.step).toBe(1)
    expect(mockMessage.error).toHaveBeenCalledWith('校验请求失败，请检查网络后重试')
  })

  it('校验中状态渲染加载提示', async () => {
    mockPost.mockImplementation(() => new Promise(() => {}))
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.handleFileSelect({ raw: xlsxFile })

    const p = vm.handleValidate()
    await nextTick()
    vm.step = 2 // finally 尚未执行，手动切到步骤2查看 validating 分支
    await nextTick()
    expect(vm.validating).toBe(true)
    expect(wrapper.text()).toContain('正在校验数据...')
    p.catch(() => {})
  })

  it('"返回修改"回到步骤1，"继续导入"进入步骤3', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    await gotoStep(wrapper, vm, 2)

    const backBtn = wrapper.findAll('.step-actions .el-btn')[0]
    await backBtn.trigger('click')
    expect(vm.step).toBe(1)

    await gotoStep(wrapper, vm, 2)
    const continueBtn = wrapper.findAll('.step-actions .el-btn')[1]
    await continueBtn.trigger('click')
    expect(vm.step).toBe(3)
  })
})

describe('步骤3：预览确认', () => {
  it('渲染预览信息（增量模式）', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.selectedTemplate = 'fund'
    vm.previewCount = 15
    await gotoStep(wrapper, vm, 3)

    expect(wrapper.text()).toContain('增量导入')
    expect(wrapper.text()).toContain('15 条')
  })

  it('渲染预览信息（全量覆盖模式）+ 上一步返回', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.importMode = 'overwrite'
    await gotoStep(wrapper, vm, 3)

    expect(wrapper.text()).toContain('全量覆盖')

    const prevBtn = wrapper.findAll('.step-actions .el-btn')[0]
    await prevBtn.trigger('click')
    expect(vm.step).toBe(2)
  })
})

describe('步骤4-5：导入执行与结果', () => {
  it('未选择文件时 handleImport 直接返回', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    await vm.handleImport()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('导入成功：进度到100并展示结果页', async () => {
    vi.useFakeTimers()
    try {
      mockPost.mockImplementation((_url: string, _data: any, config: any) => {
        // 触发上传进度回调（有 total 和无 total 两个分支）
        config.onUploadProgress({ loaded: 50, total: 100 })
        config.onUploadProgress({ loaded: 50, total: 0 })
        return Promise.resolve({
          data: {
            success_rows: 8,
            failed_rows: 2,
            errors: [{ row: 3, name: '项目X', error: '名称重复' }],
          },
        })
      })

      const wrapper = mountImport()
      const vm = wrapper.vm as any
      vm.selectedTemplate = 'project'
      vm.importMode = 'incremental'
      vm.handleFileSelect({ raw: xlsxFile })
      await gotoStep(wrapper, vm, 3)

      // 通过点击"确认导入"按钮触发（覆盖模板 @click="handleImport" 语句）
      const importBtn = wrapper.findAll('.step-actions .el-btn')[1]
      await importBtn.trigger('click')
      await flushPromises()
      expect(vm.importProgress).toBe(100)
      expect(vm.importResult).toEqual({
        success: 8,
        failed: 2,
        errors: [{ row: 3, name: '项目X', error: '名称重复' }],
      })
      expect(mockPost).toHaveBeenCalledWith(
        '/import/entities?mode=incremental&entity_type=project',
        expect.any(FormData),
        expect.objectContaining({ timeout: 120000 })
      )

      // 500ms 后进入结果页
      await vi.advanceTimersByTimeAsync(600)
      expect(vm.step).toBe(5)
      await nextTick()
      expect(wrapper.text()).toContain('导入完成')
      expect(wrapper.text()).toContain('失败记录')
    } finally {
      vi.useRealTimers()
    }
  })

  it('导入失败：提示后端 detail 并返回预览页（Bug#17 修复后不得进入成功结果页）', async () => {
    mockPost.mockRejectedValue({ response: { data: { detail: '文件格式不支持' } } })
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.handleFileSelect({ raw: xlsxFile })

    await vm.handleImport()
    expect(mockMessage.error).toHaveBeenCalledWith('文件格式不支持')
    // 不伪造成功结果，返回步骤3（预览确认）供重试
    expect(vm.importResult.failed).toBe(0)
    expect(vm.step).toBe(3)
  })

  it('导入失败且无 detail：使用默认提示并返回预览页', async () => {
    mockPost.mockRejectedValue(new Error('network'))
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.handleFileSelect({ raw: xlsxFile })

    await vm.handleImport()
    expect(mockMessage.error).toHaveBeenCalledWith('导入失败')
    expect(vm.step).toBe(3)
  })

  it('步骤4 导入中渲染进度；完成态渲染"导入完成"', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    await gotoStep(wrapper, vm, 4)
    expect(wrapper.text()).toContain('正在导入数据...')

    vm.importProgress = 100
    await nextTick()
    expect(wrapper.text()).toContain('导入完成')
  })

  it('结果页"查看项目列表"跳转，"继续导入"重置全部状态', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.selectedFile = xlsxFile
    vm.validationErrors = [{ row: 1 }]
    vm.previewCount = 9
    vm.importProgress = 100
    vm.importResult = { success: 3, failed: 1, errors: [] }
    await gotoStep(wrapper, vm, 5)

    const extraButtons = wrapper.findAll('.step-actions .el-btn, .el-result-stub .el-btn')
    // "继续导入"（handleReset）
    await extraButtons[0].trigger('click')
    expect(vm.step).toBe(0)
    expect(vm.selectedFile).toBeNull()
    expect(vm.validationErrors).toEqual([])
    expect(vm.previewCount).toBe(0)
    expect(vm.importProgress).toBe(0)
    expect(vm.importResult).toEqual({ success: 0, failed: 0 })

    // "查看项目列表"
    await gotoStep(wrapper, vm, 5)
    const btnsAgain = wrapper.findAll('.el-result-stub .el-btn')
    await btnsAgain[1].trigger('click')
    expect(mockPush).toHaveBeenCalledWith('/projects')
  })

  it('handleReset 直接调用重置状态', () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.step = 5
    vm.importResult = { success: 1, failed: 0 }
    vm.handleReset()
    expect(vm.step).toBe(0)
    expect(vm.importResult).toEqual({ success: 0, failed: 0 })
  })
})

describe('分支补全：|| 回退侧', () => {
  it('previewSections：模板类型无预定义字段时回退空数组（L464 || []）', async () => {
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    // 'unknown_type' 不在 entityPreviewFields 中 → 查表结果为 undefined → 走 || []
    vm.selectedTemplate = 'unknown_type'
    await nextTick()
    expect(vm.previewSections).toEqual([])
  })

  it('校验发现问题：错误项缺 row/field/message 且响应缺 total_rows 时全部回退默认值', async () => {
    // first_errors 元素为空对象 → L505 || 0 / L506 || '' / L507 || ''；
    // 响应无 total_rows → L510 || 0
    mockPost.mockResolvedValue({ data: { error_count: 1, first_errors: [{}] } })
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.handleFileSelect({ raw: xlsxFile })

    await vm.handleValidate()
    await flushPromises()

    expect(vm.validationErrors).toEqual([{ row: 0, field: '', message: '' }])
    expect(vm.previewCount).toBe(0)
    expect(vm.step).toBe(2)
  })

  it('校验接口异常且后端返回 detail：优先展示后端 detail（L516 || 左侧）', async () => {
    mockPost.mockRejectedValue({ response: { data: { detail: '校验服务暂不可用' } } })
    const wrapper = mountImport()
    const vm = wrapper.vm as any
    vm.handleFileSelect({ raw: xlsxFile })
    vm.step = 1 // 模拟真实流程：从上传页发起校验

    await vm.handleValidate()
    await flushPromises()

    expect(mockMessage.error).toHaveBeenCalledWith('校验服务暂不可用')
    expect(vm.previewCount).toBe(0)
    expect(vm.step).toBe(1)
  })

  it('导入成功但响应缺 success_rows/failed_rows/errors：回退默认结果（L543-545）', async () => {
    vi.useFakeTimers()
    try {
      mockPost.mockResolvedValue({ data: {} })
      const wrapper = mountImport()
      const vm = wrapper.vm as any
      vm.handleFileSelect({ raw: xlsxFile })

      await vm.handleImport()
      await flushPromises()

      expect(vm.importProgress).toBe(100)
      expect(vm.importResult).toEqual({ success: 0, failed: 0, errors: [] })

      await vi.advanceTimersByTimeAsync(600)
      expect(vm.step).toBe(5)
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('响应形态收尾', () => {
  it('res.data 有值 → 解包使用（校验 data 侧）', async () => {
    const wrapper = mountImport()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleFileSelect({ raw: xlsxFile })
    ;(mockPost as any).mockResolvedValueOnce({
      data: { error_count: 0, first_errors: [], total_rows: 3 },
    })
    await vm.handleValidate().catch(() => {})
    expect(vm.previewCount).toBe(3)
    wrapper.unmount()
  })
})

describe('响应形态收尾2', () => {
  it('校验响应无 data 包裹 → 直接使用', async () => {
    const wrapper = mountImport()
    await flushPromises()
    const vm = wrapper.vm as any
    ;(mockPost as any).mockResolvedValueOnce({ error_count: 0, first_errors: [], total_rows: 2 })
    vm.selectedFile = new File(['x'], 'a.csv')
    await vm.handleValidate().catch(() => {})
    expect(vm.previewCount).toBe(2)
    wrapper.unmount()
  })
})
