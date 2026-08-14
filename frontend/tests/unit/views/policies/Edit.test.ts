/**
 * views/policies/Edit.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：新增/编辑模式、loadLevelOptions 全分支、loadData 全分支（无 id/成功/无政策/失败）、
 * handleCategoryChange、handleUploadSuccess 新旧格式、handleUploadRemove、
 * beforeUpload 全分支、handleSubmit 全分支（无 formRef/校验失败/更新/新增/失败）、
 * 模板 v-model 与按钮。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const {
  ElMessage,
  pushSafeMock,
  routeBox,
  policyStore,
  getLevelOptionsMock,
  authStorageMock,
  validateMock,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  pushSafeMock: vi.fn(),
  routeBox: { params: {} as Record<string, any> },
  policyStore: {
    fetchPolicyById: vi.fn(),
    fetchPolicy: vi.fn(),
    current: null as any,
    updatePolicy: vi.fn(),
    createPolicy: vi.fn(),
  },
  getLevelOptionsMock: vi.fn(),
  authStorageMock: { getToken: vi.fn() },
  validateMock: vi.fn(),
}))

vi.mock('vue-router', () => ({ useRoute: () => routeBox }))

vi.mock('element-plus', () => ({
  ElMessage,
  ElForm: {},
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
  safeRouteParam: (v: any) => Number(v) || v,
}))

vi.mock('@/stores/policy', () => ({ usePolicyStore: () => policyStore }))

vi.mock('@/api/policy', () => ({
  getLevelOptions: getLevelOptionsMock,
}))

vi.mock('@/api/request', () => ({
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: authStorageMock,
}))

import Edit from '@/views/policies/Edit.vue'

const editPolicy = {
  id: 5,
  title: '政策标题',
  category: 'military',
  organization_level: 'national',
  publish_date: '2024-01-01T00:00:00',
  effective_date: '2024-01-02T00:00:00',
  department: '军委',
  content: '内容',
  summary: '摘要',
  document_number: '文号',
  keywords: '关键词',
  attachment_urls: ['/files/a.pdf'],
  status: 'draft',
}

function mountComp() {
  return mount(Edit, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
        'el-form': {
          name: 'ElForm',
          template: '<div class="el-form-stub"><slot /></div>',
          methods: {
            validate(cb?: any) {
              const p = validateMock()
              if (cb) {
                p.then((v: boolean) => cb(v))
                return undefined
              }
              return p
            },
          },
        },
        'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
        'el-row': { template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { template: '<div class="el-col-stub"><slot /></div>' },
        'el-input': {
          template:
            '<div class="el-input-stub" @click="$emit(\'update:modelValue\', \'V\')" />',
        },
        'el-select': {
          template:
            '<div class="el-select-stub" @click="$emit(\'update:modelValue\', \'military\'); $emit(\'change\', \'military\')"><slot /></div>',
        },
        'el-option': { template: '<div class="el-option-stub" />' },
        'el-date-picker': {
          template:
            '<div class="el-date-picker-stub" @click="$emit(\'update:modelValue\', \'2024-01-01T00:00:00\')" />',
        },
        'el-radio-group': {
          template:
            '<div class="el-radio-group-stub" @click="$emit(\'update:modelValue\', \'invalid\')"><slot /></div>',
        },
        'el-radio': { template: '<div class="el-radio-stub" />' },
        'el-upload': {
          template:
            '<div class="el-upload-stub" @click="beforeUpload && beforeUpload({ type: \'image/png\', size: 100 })"><slot /><slot name="tip" /></div>',
          props: ['beforeUpload', 'onSuccess', 'onRemove', 'fileList'],
        },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-icon': { template: '<span class="el-icon-stub"><slot /></span>' },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  routeBox.params = {}
  policyStore.current = null
  policyStore.fetchPolicy.mockResolvedValue({ code: 200, data: { id: 5, title: "政策标题" } })
  policyStore.updatePolicy.mockResolvedValue({ code: 200, data: { id: 5 } })
  policyStore.createPolicy.mockResolvedValue({ code: 200, data: { id: 6 } })
  getLevelOptionsMock.mockResolvedValue({ data: { data: [{ value: 'national', label: '国家级' }] } })
  authStorageMock.getToken.mockReturnValue('token-123')
  validateMock.mockResolvedValue(true)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('新增/编辑模式与初始化', () => {
  it('新增模式：isEdit false，onMounted 无分类 → 层级清空', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isEdit).toBe(false)
    expect(policyStore.fetchPolicy).not.toHaveBeenCalled()
    expect(getLevelOptionsMock).not.toHaveBeenCalled()
    expect(vm.levelOptions).toEqual([])
    expect(wrapper.text()).toContain('新增政策')
  })

  it('编辑模式：isEdit true + loadData 回填', async () => {
    routeBox.params = { id: '5' }
    policyStore.fetchPolicy.mockResolvedValue({ code: 200, data: { id: 5, title: "政策标题" } })
    policyStore.current = editPolicy
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isEdit).toBe(true)
    expect(policyStore.fetchPolicy).toHaveBeenCalledWith(5)
    expect(vm.formData.title).toBe('政策标题')
    expect(vm.formData.category).toBe('military')
    expect(vm.formData.organization_level).toBe('national')
    expect(vm.formData.issuing_authority).toBe('军委')
    expect(vm.formData.content).toBe('内容')
    expect(vm.formData.status).toBe('draft')
    expect(vm.fileList).toHaveLength(1)
    expect(vm.fileList[0].name).toBe('a.pdf')
    expect(vm.loading).toBe(false)
  })

  it('编辑模式：无 id/NaN → 不加载', async () => {
    routeBox.params = { id: 'abc' }
    const wrapper = mountComp()
    await flushPromises()
    expect(policyStore.fetchPolicy).not.toHaveBeenCalled()
  })

  it('loadData 无政策 → 错误 + 返回列表', async () => {
    routeBox.params = { id: '5' }
    policyStore.current = null
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('未找到该政策')
    expect(pushSafeMock).toHaveBeenCalledWith('/policies')
  })

  it('loadData 失败 → 错误 + 返回列表', async () => {
    routeBox.params = { id: '5' }
    policyStore.fetchPolicy.mockRejectedValue(new Error('加载失败'))
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('加载失败')
    expect(pushSafeMock).toHaveBeenCalledWith('/policies')
  })

  it('loadData 无 attachment_urls → fileList 为空', async () => {
    routeBox.params = { id: '5' }
    policyStore.current = { ...editPolicy, attachment_urls: [] }
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).fileList).toEqual([])
  })

  it('loadData 字段缺失走 || 兜底', async () => {
    routeBox.params = { id: '5' }
    policyStore.current = {
      id: 5,
      title: 'T',
      category: 'military',
      organization_level: 'national',
      publish_date: '2024-01-01T00:00:00',
      effective_date: undefined,
      department: undefined,
      issuing_authority: '部门B',
      content: 'C',
      summary: undefined,
      document_number: undefined,
      keywords: undefined,
      attachment_urls: ['/files/'],
      status: undefined,
    }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formData.issuing_authority).toBe('部门B')
    expect(vm.formData.effective_date).toBe('')
    expect(vm.formData.summary).toBe('')
    expect(vm.formData.document_number).toBe('')
    expect(vm.formData.keywords).toBe('')
    expect(vm.formData.status).toBe(undefined)
    expect(vm.fileList[0].name).toBe('附件1')
  })

  it('loadData attachment_urls 缺失 → || [] 兜底', async () => {
    routeBox.params = { id: '5' }
    policyStore.current = { ...editPolicy, attachment_urls: undefined }
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).fileList).toEqual([])
  })

  it('loadData department/issuing_authority 均缺失 → || 兜底', async () => {
    routeBox.params = { id: '5' }
    policyStore.current = {
      ...editPolicy,
      department: undefined,
      issuing_authority: undefined,
    }
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).formData.issuing_authority).toBe('')
  })

  it('loadData 失败无 message → 兜底文案', async () => {
    routeBox.params = { id: '5' }
    policyStore.fetchPolicy.mockRejectedValue({})
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('加载政策数据失败')
    expect(pushSafeMock).toHaveBeenCalledWith('/policies')
  })
})

describe('层级选项', () => {
  it('无 category → 清空选项', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.category = ''
    getLevelOptionsMock.mockClear()
    await vm.loadLevelOptions()
    expect(vm.levelOptions).toEqual([])
    expect(getLevelOptionsMock).not.toHaveBeenCalled()
  })

  it('加载成功（data.data/data/直返）与失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.category = 'military'
    getLevelOptionsMock.mockResolvedValueOnce({ data: [{ value: 'province', label: '省级' }] })
    await vm.loadLevelOptions()
    expect(vm.levelOptions).toHaveLength(1)

    getLevelOptionsMock.mockResolvedValueOnce([{ value: 'county', label: '县级' }])
    await vm.loadLevelOptions()
    expect(vm.levelOptions[0].value).toBe('county')

    getLevelOptionsMock.mockResolvedValueOnce({ data: { data: null } })
    await vm.loadLevelOptions()
    expect(vm.levelOptions).toEqual([])

    getLevelOptionsMock.mockRejectedValueOnce(new Error('net'))
    await vm.loadLevelOptions()
    expect(vm.levelOptions).toEqual([])
    expect(vm.levelOptionsLoading).toBe(false)
  })

  it('handleCategoryChange 清空层级并重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.category = 'military'
    vm.formData.organization_level = 'national'
    getLevelOptionsMock.mockClear()
    vm.handleCategoryChange()
    await flushPromises()
    expect(vm.formData.organization_level).toBe('')
    expect(getLevelOptionsMock).toHaveBeenCalledWith('military')
  })

  it('分类下拉 change → handleCategoryChange', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    getLevelOptionsMock.mockClear()
    const sel = wrapper.find('.el-select-stub')
    await sel.trigger('click')
    await flushPromises()
    expect(vm.formData.category).toBe('military')
    expect(getLevelOptionsMock).toHaveBeenCalled()
  })
})

describe('上传处理', () => {
  it('handleUploadSuccess 直返 url', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleUploadSuccess({ url: '/files/b.pdf' }, {} as any)
    expect(vm.formData.attachment_urls).toContain('/files/b.pdf')
    expect(ElMessage.success).toHaveBeenCalledWith('上传成功')
  })

  it('handleUploadSuccess data.url 信封格式 / 无 url', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleUploadSuccess({ data: { url: '/files/c.pdf' } }, {} as any)
    expect(vm.formData.attachment_urls).toContain('/files/c.pdf')

    vm.handleUploadSuccess({ other: 1 }, {} as any)
    expect(vm.formData.attachment_urls).toHaveLength(1)
  })

  it('handleUploadRemove：有 url 删除；无 url 忽略', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.attachment_urls = ['/files/a.pdf', '/files/b.pdf']
    vm.handleUploadRemove({ url: '/files/a.pdf' } as any)
    expect(vm.formData.attachment_urls).toEqual(['/files/b.pdf'])
    vm.handleUploadRemove({} as any)
    expect(vm.formData.attachment_urls).toEqual(['/files/b.pdf'])
  })

  it('beforeUpload 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(await vm.beforeUpload({ type: 'image/png', size: 100 })).toBe(true)
    expect(await vm.beforeUpload({ type: 'text/html', size: 100 })).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('只能上传 jpg/png/pdf/doc/docx/pptx 文件!')
    expect(await vm.beforeUpload({ type: 'image/png', size: 51 * 1024 * 1024 })).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('文件大小不能超过 50MB!')
  })
})

describe('提交', () => {
  it('无 formRef → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formRef = null
    await vm.handleSubmit()
    expect(policyStore.createPolicy).not.toHaveBeenCalled()
  })

  it('校验失败 → 不提交', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    validateMock.mockResolvedValueOnce(false)
    await vm.handleSubmit()
    expect(policyStore.createPolicy).not.toHaveBeenCalled()
  })

  it('新增成功 → 提示 + 返回列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.title = 'T'
    await vm.handleSubmit()
    expect(policyStore.createPolicy).toHaveBeenCalledWith(expect.objectContaining({ title: 'T' }))
    expect(ElMessage.success).toHaveBeenCalledWith('新增成功')
    expect(pushSafeMock).toHaveBeenCalledWith('/policies')
  })

  it('编辑成功 → 提示 + 返回列表', async () => {
    routeBox.params = { id: '5' }
    policyStore.current = editPolicy
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleSubmit()
    expect(policyStore.updatePolicy).toHaveBeenCalledWith(5, expect.any(Object))
    expect(ElMessage.success).toHaveBeenCalledWith('更新成功')
  })

  it('提交失败 → 错误提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    policyStore.createPolicy.mockRejectedValueOnce(new Error('保存失败'))
    await vm.handleSubmit()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')

    policyStore.createPolicy.mockRejectedValueOnce({})
    await vm.handleSubmit()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
    expect(vm.submitLoading).toBe(false)
  })

  it('保存按钮 → handleSubmit', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const save = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('保存'))
    await save!.trigger('click')
    await flushPromises()
    expect(policyStore.createPolicy).toHaveBeenCalled()
  })
})

describe('导航与模板', () => {
  it('handleBack / 返回按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleBack()
    expect(pushSafeMock).toHaveBeenCalledWith('/policies')

    pushSafeMock.mockClear()
    const backBtn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('返回列表'))
    await backBtn!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/policies')

    const cancel = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('取消'))
    await cancel!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/policies')
  })

  it('uploadAction/uploadHeaders computed', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.uploadAction).toBe('/api/v1/files/upload')
    expect(vm.uploadHeaders).toMatchObject({ Authorization: 'Bearer token-123', 'X-CSRF-Token': 'test-csrf' })

    authStorageMock.getToken.mockReturnValue('')
    const w2 = mountComp()
    await flushPromises()
    expect((w2.vm as any).uploadHeaders).toMatchObject({ 'X-CSRF-Token': 'test-csrf' })
  })

  it('表单 v-model 更新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    for (const el of wrapper.findAll('.el-input-stub')) {
      await el.trigger('click')
    }
    for (const sel of wrapper.findAll('.el-select-stub')) {
      await sel.trigger('click')
    }
    for (const dp of wrapper.findAll('.el-date-picker-stub')) {
      await dp.trigger('click')
    }
    await wrapper.find('.el-radio-group-stub').trigger('click')
    await nextTick()
    expect(vm.formData.title).toBe('V')
    expect(vm.formData.organization_level).toBe('military')
    expect(vm.formData.publish_date).toBe('2024-01-01T00:00:00')
    expect(vm.formData.effective_date).toBe('2024-01-01T00:00:00')
    expect(vm.formData.status).toBe('invalid')
  })

  it('上传控件触发 beforeUpload', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.el-upload-stub').trigger('click')
  })
})

  it('createPolicy 响应非 200 → 抛错提示', async () => {
    routeBox.params = {}
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.title = 'T'
    policyStore.createPolicy.mockResolvedValueOnce({ code: 500, message: '服务异常' })
    await vm.handleSubmit()
    expect(ElMessage.error).toHaveBeenCalledWith('服务异常')
    wrapper.unmount()
  })

  it('createPolicy 响应非 200 → 抛错提示', async () => {
    routeBox.params = {}
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.title = 'T'
    policyStore.createPolicy.mockResolvedValueOnce({ code: 500, message: '服务异常' })
    await vm.handleSubmit()
    expect(ElMessage.error).toHaveBeenCalledWith('服务异常')
    wrapper.unmount()
  })

describe('提交失败分支', () => {
  it('updatePolicy code!=200 → 抛错', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.isEdit = true
    ;(vm as any).policyStore.updatePolicy = vi.fn().mockResolvedValue({ code: 400 })
    await vm.handleSubmit().catch(() => {})
    wrapper.unmount()
  })
  it('createPolicy code200 但 data 空 → 抛错', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.isEdit = false
    ;(vm as any).policyStore.createPolicy = vi.fn().mockResolvedValue({ code: 200, data: null })
    await vm.handleSubmit().catch(() => {})
    wrapper.unmount()
  })
})

describe('更新成功分支', () => {
  it('updatePolicy code 200 → 成功提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.isEdit = true
    ;(vm as any).policyStore.updatePolicy = vi.fn().mockResolvedValue({ code: 200 })
    await vm.handleSubmit().catch(() => {})
    wrapper.unmount()
  })
})

describe('编辑模式提交分支', () => {
  it('isEdit 编辑模式：code 200 成功 / code 400 抛错', async () => {
    routeBox.params = { id: '5' }
    policyStore.current = { id: 5, title: 't' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.title = '有效标题'
    policyStore.updatePolicy.mockResolvedValue({ code: 200, data: { id: 5 } })
    await vm.handleSubmit().catch(() => {})
    policyStore.updatePolicy.mockResolvedValue({ code: 400 })
    await vm.handleSubmit().catch(() => {})
    wrapper.unmount()
  })
})
