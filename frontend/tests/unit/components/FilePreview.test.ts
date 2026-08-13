/**
 * FilePreview 通用文件预览组件测试（问题5/9/14）
 * 覆盖：PDF iframe 预览 / 图片 img 预览 / 不支持类型转下载 / 关闭释放 Blob URL
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import FilePreview from '@/components/FilePreview.vue'

const { downloadBlobMock, elMessageErrorMock } = vi.hoisted(() => ({
  downloadBlobMock: vi.fn(),
  elMessageErrorMock: vi.fn(),
}))
vi.mock('@/api/request', () => ({ downloadBlob: downloadBlobMock }))
vi.mock('element-plus', () => ({ ElMessage: { error: elMessageErrorMock } }))

const stubs = {
  'el-dialog': {
    template: '<div class="el-dialog-stub"><slot /></div>',
    props: ['modelValue', 'title'],
  },
  'el-empty': {
    template: '<div class="el-empty-stub">{{ description }}<slot /></div>',
    props: ['description'],
  },
  'el-button': {
    template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
  },
}

describe('FilePreview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    URL.createObjectURL = vi.fn(() => 'blob:mock-url')
    URL.revokeObjectURL = vi.fn()
  })

  it('PDF → iframe 内联预览', async () => {
    const fetchBlob = vi.fn().mockResolvedValue(new Blob(['x'], { type: 'application/pdf' }))
    const wrapper = mount(FilePreview, {
      props: { modelValue: true, fetchBlob, fileName: 'a.pdf' },
      global: { stubs },
    })
    await vi.waitFor(() => expect(wrapper.find('iframe').exists()).toBe(true))
    expect(URL.createObjectURL).toHaveBeenCalled()
    expect(fetchBlob).toHaveBeenCalledOnce()
  })

  it('图片 → img 直接渲染', async () => {
    const fetchBlob = vi.fn().mockResolvedValue(new Blob(['x'], { type: 'image/png' }))
    const wrapper = mount(FilePreview, {
      props: { modelValue: true, fetchBlob, fileName: 'p.png' },
      global: { stubs },
    })
    await vi.waitFor(() => expect(wrapper.find('img').exists()).toBe(true))
  })

  it('Office 等不支持类型 → 提示下载并可点击下载', async () => {
    const blob = new Blob(['x'], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    const fetchBlob = vi.fn().mockResolvedValue(blob)
    const wrapper = mount(FilePreview, {
      props: { modelValue: true, fetchBlob, fileName: 'doc.docx' },
      global: { stubs },
    })
    await vi.waitFor(() => expect(wrapper.find('.el-empty-stub').exists()).toBe(true))
    expect(wrapper.text()).toContain('不支持在线预览')
    await wrapper.find('.el-button-stub').trigger('click')
    expect(downloadBlobMock).toHaveBeenCalledWith(blob, 'doc.docx')
  })

  it('关闭 → revokeObjectURL + emit update:modelValue(false)', async () => {
    const fetchBlob = vi.fn().mockResolvedValue(new Blob(['x'], { type: 'application/pdf' }))
    const wrapper = mount(FilePreview, {
      props: { modelValue: true, fetchBlob, fileName: 'a.pdf' },
      global: { stubs },
    })
    await vi.waitFor(() => expect(wrapper.find('iframe').exists()).toBe(true))
    ;(wrapper.vm as any).handleClose()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
  })

  it('空 blob → 显示「暂无可预览的文件」', async () => {
    const fetchBlob = vi.fn().mockResolvedValue(new Blob([], { type: 'application/pdf' }))
    const wrapper = mount(FilePreview, {
      props: { modelValue: true, fetchBlob, fileName: 'a.pdf' },
      global: { stubs },
    })
    await vi.waitFor(() => expect(wrapper.find('.el-empty-stub').exists()).toBe(true))
    expect(wrapper.text()).toContain('暂无可预览的文件')
  })

  it('加载失败 → ElMessage.error「文件预览失败」', async () => {
    elMessageErrorMock.mockClear()
    const fetchBlob = vi.fn().mockRejectedValue(new Error('net'))
    const wrapper = mount(FilePreview, {
      props: { modelValue: true, fetchBlob, fileName: 'a.pdf' },
      global: { stubs },
    })
    await vi.waitFor(() => expect(elMessageErrorMock).toHaveBeenCalledWith('文件预览失败'))
  })

  it('分支：blobRef 空时 isImage 兜底 / blob 无 type / fileName 兜底', async () => {
    const fetchBlob = vi.fn().mockResolvedValue(new Blob(['x'])) // 无 type
    const wrapper = mount(FilePreview, {
      props: { modelValue: true, fetchBlob, fileName: '' },
      global: { stubs },
    })
    const vm = wrapper.vm as any
    // blobRef 空 → isImage 走 '' 分支
    expect(vm.isImage).toBe(false)
    await vi.waitFor(() => expect(vm.blobRef).toBeTruthy())
    // 无 type blob → type 兜底 '' → 非可预览 → unsupported
    expect(vm.unsupported).toBe(true)
    // fileName 空 → downloadBlob 用 'download'
    downloadBlobMock.mockClear()
    vm.handleDownload()
    expect(downloadBlobMock).toHaveBeenCalledWith(expect.any(Blob), 'download')
    // blobRef 空 → 早退
    vm.blobRef = null
    downloadBlobMock.mockClear()
    vm.handleDownload()
    expect(downloadBlobMock).not.toHaveBeenCalled()
  })
})
