/**
 * FilePreview 通用文件预览组件测试（问题5/9/14）
 * 覆盖：PDF iframe 预览 / 图片 img 预览 / 不支持类型转下载 / 关闭释放 Blob URL
 * 回归：Blob URL 必须在关闭、切换与卸载时释放，且卸载后迟到的响应不得再建 URL
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
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
    mount(FilePreview, {
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

  /**
   * `watch(() => props.modelValue, async (visible) => { if (!visible) return; ... },
   *        { immediate: true })`
   * 的【不可见】侧。上方所有用例都以 modelValue=true 挂载，
   * 因此 `if (!visible) return` 的真侧从未执行。
   * 真实场景：列表页把预览弹窗常驻在模板里（visible 初始为 false），
   * 此时绝不能发起认证 Blob 请求（否则首屏就打出大量无效流量）。
   */
  it('挂载即不可见（immediate watch + visible=false）→ 早退，不拉流不建 URL', async () => {
    const fetchBlob = vi.fn()
    const wrapper = mount(FilePreview, {
      props: { modelValue: false, fetchBlob, fileName: 'a.pdf' },
      global: { stubs },
    })
    await flushPromises()

    expect(fetchBlob).not.toHaveBeenCalled()
    expect(URL.createObjectURL).not.toHaveBeenCalled()
    const vm = wrapper.vm as any
    // 早退时不得误置 loading（否则弹窗一开就卡在骨架态）
    expect(vm.loading).toBe(false)
    expect(vm.blobRef).toBeNull()
    expect(vm.unsupported).toBe(false)
    expect(vm.objectUrl).toBe('')
  })

  it('true → false → true：关闭时早退，重新打开才拉取', async () => {
    const fetchBlob = vi.fn().mockResolvedValue(new Blob(['x'], { type: 'application/pdf' }))
    const wrapper = mount(FilePreview, {
      props: { modelValue: true, fetchBlob, fileName: 'a.pdf' },
      global: { stubs },
    })
    await vi.waitFor(() => expect(wrapper.find('iframe').exists()).toBe(true))
    expect(fetchBlob).toHaveBeenCalledTimes(1)

    // 关闭 → watch 早退，不重拉也不抛错
    await wrapper.setProps({ modelValue: false })
    await flushPromises()
    expect(fetchBlob).toHaveBeenCalledTimes(1)

    // 重新打开 → 再次拉取（认证 URL 可能已过期，必须重取）
    await wrapper.setProps({ modelValue: true })
    await vi.waitFor(() => expect(fetchBlob).toHaveBeenCalledTimes(2))
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('父组件直接置 visible=false（不触发 close 事件）→ 立即释放 Blob URL 并清空状态', async () => {
    const fetchBlob = vi.fn().mockResolvedValue(new Blob(['x'], { type: 'application/pdf' }))
    const wrapper = mount(FilePreview, {
      props: { modelValue: true, fetchBlob, fileName: 'a.pdf' },
      global: { stubs },
    })
    await vi.waitFor(() => expect(wrapper.find('iframe').exists()).toBe(true))

    await wrapper.setProps({ modelValue: false })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url')
    expect(vm.objectUrl).toBe('')
    expect(vm.blobRef).toBeNull()
    expect(vm.unsupported).toBe(false)
  })

  it('卸载 → 释放 Blob URL（onBeforeUnmount，父组件 v-if 摘除场景）', async () => {
    const fetchBlob = vi.fn().mockResolvedValue(new Blob(['x'], { type: 'application/pdf' }))
    const wrapper = mount(FilePreview, {
      props: { modelValue: true, fetchBlob, fileName: 'a.pdf' },
      global: { stubs },
    })
    await vi.waitFor(() => expect(wrapper.find('iframe').exists()).toBe(true))

    wrapper.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url')
  })

  it('卸载后迟到的 fetchBlob 响应 → 不再创建 Blob URL（请求令牌）', async () => {
    let resolveBlob!: (b: Blob) => void
    const fetchBlob = vi.fn(
      () =>
        new Promise<Blob>((r) => {
          resolveBlob = r
        })
    )
    const wrapper = mount(FilePreview, {
      props: { modelValue: true, fetchBlob, fileName: 'a.pdf' },
      global: { stubs },
    })
    await flushPromises()
    expect(fetchBlob).toHaveBeenCalledTimes(1)

    wrapper.unmount()
    resolveBlob(new Blob(['x'], { type: 'application/pdf' }))
    await flushPromises()
    // 组件已卸载 → 不得再为废弃文件创建 Blob URL（否则永久泄漏）
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })

  it('重新打开时加载失败 → 不残留上一个文件的可下载内容', async () => {
    const fetchBlob = vi
      .fn()
      .mockResolvedValueOnce(new Blob(['x'], { type: 'application/pdf' }))
      .mockRejectedValueOnce(new Error('net'))
    const wrapper = mount(FilePreview, {
      props: { modelValue: true, fetchBlob, fileName: 'a.pdf' },
      global: { stubs },
    })
    await vi.waitFor(() => expect(wrapper.find('iframe').exists()).toBe(true))

    await wrapper.setProps({ modelValue: false })
    await wrapper.setProps({ modelValue: true, fileName: 'b.pdf' })
    await vi.waitFor(() => expect(elMessageErrorMock).toHaveBeenCalledWith('文件预览失败'))
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.blobRef).toBeNull()
    expect(vm.objectUrl).toBe('')
    expect(vm.unsupported).toBe(false)
    // 下载按钮场景：blobRef 为空 → 不会把上一个文件的 blob 下载出去
    downloadBlobMock.mockClear()
    vm.handleDownload()
    expect(downloadBlobMock).not.toHaveBeenCalled()
  })

  it('重新打开拿到空 blob → 清空上一个文件的预览状态', async () => {
    const fetchBlob = vi
      .fn()
      .mockResolvedValueOnce(new Blob(['x'], { type: 'application/pdf' }))
      .mockResolvedValueOnce(new Blob([], { type: 'application/pdf' }))
    const wrapper = mount(FilePreview, {
      props: { modelValue: true, fetchBlob, fileName: 'a.pdf' },
      global: { stubs },
    })
    await vi.waitFor(() => expect(wrapper.find('iframe').exists()).toBe(true))

    await wrapper.setProps({ modelValue: false })
    await wrapper.setProps({ modelValue: true, fileName: 'empty.pdf' })
    await vi.waitFor(() => expect(wrapper.text()).toContain('暂无可预览的文件'))
    const vm = wrapper.vm as any
    expect(vm.blobRef).toBeNull()
    expect(vm.objectUrl).toBe('')
    expect(vm.unsupported).toBe(false)
    expect(wrapper.find('iframe').exists()).toBe(false)
  })
})
