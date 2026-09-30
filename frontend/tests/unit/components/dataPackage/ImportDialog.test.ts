/**
 * components/dataPackage/ImportDialog.vue 覆盖率攻坚
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { ElMessage, mockPost } = vi.hoisted(() => {
  return {
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
    mockPost: vi.fn(),
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

import ImportDialog from '@/components/dataPackage/ImportDialog.vue'

function mountDialog(props = {}) {
  return mount(ImportDialog, {
    props: { modelValue: true, ...props },
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-form': {
          name: 'ElForm',
          template: '<form><slot /></form>',
        },
        'el-upload': {
          name: 'ElUpload',
          props: ['modelValue', 'fileList'],
          emits: ['change', 'remove'],
          template: '<div class="upload-stub"><slot /><slot name="tip" /></div>',
        },
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('dataPackage/ImportDialog.vue', () => {
  it('渲染对话框', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    expect(wrapper.find('.upload-stub').exists()).toBe(true)
    wrapper.unmount()
  })

  it('选择文件后导入成功', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.vm.handleFileChange({ raw: new File(['x'], 'pkg.zip') })
    mockPost.mockResolvedValue({ message: '导入完成' })
    await wrapper.vm.handleImport()
    expect(mockPost).toHaveBeenCalledWith(
      '/data-packages/import',
      expect.any(FormData),
      expect.any(Object)
    )
    expect(ElMessage.success).toHaveBeenCalledWith('导入完成')
    expect(wrapper.emitted('success')).toBeTruthy()
    expect(wrapper.vm.selectedFile).toBeNull()
    wrapper.unmount()
  })

  it('未选文件时警告', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    await wrapper.vm.handleImport()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择数据包文件')
    expect(mockPost).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('接口异常提示错误', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.vm.handleFileChange({ raw: new File(['x'], 'pkg.zip') })
    mockPost.mockRejectedValue({ response: { data: { detail: '导入失败原因' } } })
    await wrapper.vm.handleImport()
    expect(ElMessage.error).toHaveBeenCalledWith('导入失败原因')
    expect(wrapper.vm.submitting).toBe(false)
    // 无 detail 走默认提示
    wrapper.vm.handleFileChange({ raw: new File(['x'], 'pkg2.zip') })
    mockPost.mockRejectedValue(new Error('net'))
    await wrapper.vm.handleImport()
    expect(ElMessage.error).toHaveBeenCalledWith('导入失败')
    wrapper.unmount()
  })

  it('file.raw 为空时 selectedFile 为 null', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.vm.handleFileChange({ raw: null })
    expect(wrapper.vm.selectedFile).toBeNull()
    wrapper.unmount()
  })

  it('移除文件清空选择', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.vm.handleFileChange({ raw: new File(['x'], 'pkg.zip') })
    wrapper.vm.handleFileRemove()
    expect(wrapper.vm.selectedFile).toBeNull()
    expect(wrapper.vm.fileList).toEqual([])
    wrapper.unmount()
  })

  it('关闭对话框即清空已选文件：重新打开不带旧文件、不能直接再次导入', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.vm.handleFileChange({ raw: new File(['x'], 'pkg.zip') })
    wrapper.vm.fileList = [{ name: 'pkg.zip', raw: new File(['x'], 'pkg.zip') }]
    expect(wrapper.vm.selectedFile).toBeInstanceOf(File)

    // 取消关闭
    await wrapper.setProps({ modelValue: false })
    await flushPromises()
    expect(wrapper.vm.selectedFile).toBeNull()
    expect(wrapper.vm.fileList).toEqual([])

    // 重新打开：仍是空状态（"导入"按钮的 disabled 绑定即 !selectedFile，故不可点）
    await wrapper.setProps({ modelValue: true })
    await flushPromises()
    expect(wrapper.vm.selectedFile).toBeNull()
    expect(wrapper.vm.fileList).toEqual([])

    await wrapper.vm.handleImport()
    expect(mockPost).not.toHaveBeenCalled()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择数据包文件')
    wrapper.unmount()
  })

  it('导入成功后再次打开（modelValue 变化）保持空状态', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    wrapper.vm.handleFileChange({ raw: new File(['x'], 'pkg.zip') })
    mockPost.mockResolvedValue({ message: '导入完成' })
    await wrapper.vm.handleImport()
    expect(wrapper.vm.selectedFile).toBeNull()

    await wrapper.setProps({ modelValue: false })
    await wrapper.setProps({ modelValue: true })
    await flushPromises()
    expect(wrapper.vm.selectedFile).toBeNull()
    expect(wrapper.vm.fileList).toEqual([])
    wrapper.unmount()
  })
})

it('模板事件处理器(dialog update)与 success 默认提示', async () => {
  const wrapper = mountDialog()
  await flushPromises()
  wrapper.findComponent({ name: 'ElDialog' }).vm.$emit('update:modelValue', false)
  expect(wrapper.emitted('update:modelValue')).toContainEqual([false])
  // success 无 message 走默认提示
  wrapper.vm.handleFileChange({ raw: new File(['x'], 'pkg.zip') })
  mockPost.mockResolvedValue({})
  await wrapper.vm.handleImport()
  expect(ElMessage.success).toHaveBeenCalled()
  wrapper.unmount()
})
