/**
 * components/dataPackage/ExportDialog.vue 覆盖率攻坚
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { ElMessage, mockPost, downloadMock } = vi.hoisted(() => {
  return {
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
    mockPost: vi.fn(),
    downloadMock: vi.fn().mockResolvedValue(undefined),
  }
})

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: vi.fn() },
}))

vi.mock('@/api/request', () => ({
  post: mockPost,
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/stores/dataPackage', () => ({
  useDataPackageStore: () => ({ downloadPackage: downloadMock }),
}))

import ExportDialog from '@/components/dataPackage/ExportDialog.vue'

function mountDialog(props = {}) {
  return mount(ExportDialog, {
    props: { modelValue: true, ...props },
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-form': {
          name: 'ElForm',
          props: ['model'],
          emits: ['submit'],
          template: '<form><slot /></form>',
        },
        'el-checkbox-group': {
          name: 'ElCheckboxGroup',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<div class="cg-stub"><slot /></div>',
        },
        'el-checkbox': {
          name: 'ElCheckbox',
          props: ['label', 'modelValue'],
          emits: ['update:modelValue'],
          template: '<label class="cb-stub" />',
        },
        'el-input': {
          name: 'ElInput',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template: '<div class="input-stub" />',
        },
      },
    },
  })
}

function makeFormRef(wrapper: any, pass: boolean) {
  wrapper.vm.formRef = {
    validate: vi.fn(pass ? () => Promise.resolve() : () => Promise.reject(new Error('invalid'))),
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('dataPackage/ExportDialog.vue', () => {
  it('渲染对话框与默认数据类型', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    expect(wrapper.vm.form.data_types).toContain('villages')
    wrapper.unmount()
  })

  it('打开时重置表单', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.vm.form.data_types = ['schools']
    wrapper.vm.form.description = '备注'
    await wrapper.setProps({ modelValue: false })
    await wrapper.setProps({ modelValue: true })
    await flushPromises()
    expect(wrapper.vm.form.data_types).toEqual(['villages', 'projects', 'funds', 'schools'])
    expect(wrapper.vm.form.description).toBe('')
    wrapper.unmount()
  })

  it('导出成功: 有 package_id 时提示并关闭', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    makeFormRef(wrapper, true)
    mockPost.mockResolvedValue({ package_id: 7 })
    await wrapper.vm.handleExport()
    expect(mockPost).toHaveBeenCalledWith(
      '/data-packages/export',
      expect.objectContaining({ data_types: expect.any(Array) })
    )
    expect(ElMessage.success).toHaveBeenCalledWith(expect.stringContaining('7'))
    expect(wrapper.emitted('success')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
    wrapper.unmount()
  })

  it('导出成功: 无 package_id 走默认提示', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    makeFormRef(wrapper, true)
    mockPost.mockResolvedValue({})
    await wrapper.vm.handleExport()
    expect(ElMessage.success).toHaveBeenCalledWith('数据包导出成功')
    wrapper.unmount()
  })

  it('校验失败直接返回不请求', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    makeFormRef(wrapper, false)
    await wrapper.vm.handleExport()
    expect(mockPost).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('接口异常提示错误', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    makeFormRef(wrapper, true)
    mockPost.mockRejectedValue({ response: { data: { detail: '导出失败原因' } } })
    await wrapper.vm.handleExport()
    expect(ElMessage.error).toHaveBeenCalledWith('导出失败原因')
    expect(wrapper.vm.submitting).toBe(false)
    // 无 detail 走默认提示
    wrapper.vm.formRef = { validate: vi.fn(() => Promise.resolve()) }
    mockPost.mockRejectedValue(new Error('net'))
    await wrapper.vm.handleExport()
    expect(ElMessage.error).toHaveBeenCalledWith('导出失败')
    wrapper.unmount()
  })
})


  it('模板事件处理器执行(dialog/checkbox/input update)', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.findComponent({ name: 'ElDialog' }).vm.$emit('update:modelValue', false)
    expect(wrapper.emitted('update:modelValue')).toContainEqual([false])
    wrapper.findComponent({ name: 'ElCheckboxGroup' }).vm.$emit('update:modelValue', ['schools'])
    expect(wrapper.vm.form.data_types).toEqual(['schools'])
    wrapper.findComponent({ name: 'ElInput' }).vm.$emit('update:modelValue', '备注X')
    expect(wrapper.vm.form.description).toBe('备注X')
    wrapper.unmount()
  })

  it('formRef 缺失时直接返回', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.vm.formRef = null
    await wrapper.vm.handleExport()
    expect(mockPost).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('导出成功但无 message 时走默认提示', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.vm.formRef = { validate: vi.fn(() => Promise.resolve()) }
    mockPost.mockResolvedValue({ package_id: 1 })
    await wrapper.vm.handleExport()
    expect(ElMessage.success).toHaveBeenCalled()
    wrapper.unmount()
})

describe('导出后自动下载', () => {
  it('有 package_id → 自动下载 + 关闭对话框；无 id → 仅提示；下载失败不阻塞', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.vm.formRef = { validate: vi.fn(() => Promise.resolve()) }
    mockPost.mockResolvedValue({ package_id: 5 })
    await wrapper.vm.handleExport()
    expect(mockPost).toHaveBeenCalled()
    expect(downloadMock).toHaveBeenCalledWith(5)
    expect(ElMessage.success).toHaveBeenCalled()

    mockPost.mockResolvedValue({ success: true })
    await wrapper.vm.handleExport()
    expect(ElMessage.success).toHaveBeenCalledWith('数据包导出成功')

    downloadMock.mockRejectedValue(new Error('net'))
    mockPost.mockResolvedValue({ package_id: 6 })
    await wrapper.vm.handleExport()
    expect(ElMessage.error).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
