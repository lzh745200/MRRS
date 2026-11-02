/**
 * views/system/ChunkedUploadManager.vue 覆盖率攻坚
 * 覆盖：文件选择/移除、上传全流程（初始化→分片→合并）、分片失败、
 * 轮询各状态分支（进行中/完成/已合并/错误/无会话/异常继续）、
 * 取消上传确认流、formatSize 全量级、会话状态 computed 全映射、
 * 以及模板各 v-if 卡片、块级进度条三态、按钮显示条件两侧。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂会被提升到模块顶部注册，直接引用下方 const 会触发 TDZ；
// 所有被工厂引用的对象放入 vi.hoisted 中先行初始化。
const {
  ElMessage,
  confirmMock,
  apiInitUpload,
  apiUploadChunk,
  apiGetProgress,
  apiMergeChunks,
  apiCancelUpload,
} = vi.hoisted(() => {
  return {
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
    confirmMock: vi.fn(),
    apiInitUpload: vi.fn(),
    apiUploadChunk: vi.fn(),
    apiGetProgress: vi.fn(),
    apiMergeChunks: vi.fn(),
    apiCancelUpload: vi.fn(),
  }
})

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/chunkedUpload', () => ({
  chunkedUploadApi: {
    initUpload: apiInitUpload,
    uploadChunk: apiUploadChunk,
    getProgress: apiGetProgress,
    mergeChunks: apiMergeChunks,
    cancelUpload: apiCancelUpload,
  },
}))

import ChunkedUploadManager from '@/views/system/ChunkedUploadManager.vue'

const CHUNK = 5 * 1024 * 1024

const initResult = {
  session_id: 's1',
  file_name: 'test.bin',
  file_size: 100,
  chunk_size: CHUNK,
  total_chunks: 1,
  status: 'uploading',
}

const progressDone = {
  session_id: 's1',
  file_name: 'test.bin',
  total_chunks: 1,
  uploaded_chunks: 1,
  progress: 100,
  status: 'completed',
}

const mergeResult = {
  session_id: 's1',
  file_path: '/uploads/test.bin',
  file_name: 'test.bin',
  status: 'done',
}

function makeFile(size: number, name = 'test.bin') {
  return new File([new Uint8Array(size)], name)
}

function mountComp() {
  // setup.ts 的全局 el-* stub 默认不渲染插槽，需 renderStubDefaultSlot；
  // 具名插槽（header/tip/extra）需自定义 stub。
  return mount(ChunkedUploadManager, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
        },
        'el-upload': {
          name: 'ElUpload',
          template: '<div class="el-upload-stub"><slot /><slot name="tip" /></div>',
        },
        'el-result': {
          name: 'ElResult',
          template: '<div class="el-result-stub"><slot /><slot name="extra" /></div>',
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  apiInitUpload.mockResolvedValue({ ...initResult })
  apiUploadChunk.mockResolvedValue({ success: true, chunk_index: 0 })
  apiGetProgress.mockResolvedValue({ ...progressDone })
  apiMergeChunks.mockResolvedValue({ ...mergeResult })
  apiCancelUpload.mockResolvedValue({ success: true, message: 'ok' })
  confirmMock.mockResolvedValue(undefined)
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('挂载与工具函数', () => {
  it('挂载：idle 状态只渲染文件选择卡', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.uploadState).toBe('idle')
    expect(wrapper.find('.upload-card').exists()).toBe(true)
    expect(wrapper.find('.info-card').exists()).toBe(false)
    expect(wrapper.find('.progress-card').exists()).toBe(false)
    expect(wrapper.find('.result-card').exists()).toBe(false)
    expect(wrapper.find('.actions-card').exists()).toBe(false)
    expect(wrapper.text()).toContain('点击上传')
    expect(wrapper.text()).toContain('支持任意类型大文件')
  })

  it('formatSize 全量级分支', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.formatSize(500)).toBe('500 B')
    expect(vm.formatSize(2048)).toBe('2.0 KB')
    expect(vm.formatSize(5 * 1024 * 1024)).toBe('5.0 MB')
    expect(vm.formatSize(2 * 1024 * 1024 * 1024)).toBe('2.00 GB')
  })

  it('onFileChange：file.raw 有/无两侧；onFileRemove 清空', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const f = makeFile(10)
    vm.onFileChange({ raw: f })
    expect(vm.selectedFile).toBe(f)
    const f2 = makeFile(20)
    vm.onFileChange(f2)
    expect(vm.selectedFile).toBe(f2)
    vm.onFileRemove()
    expect(vm.selectedFile).toBeNull()
    expect(vm.uploadState).toBe('idle')
  })

  it('sessionStatusType / sessionStatusText computed 全映射', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    // 无会话 → info
    expect(vm.sessionStatusType).toBe('info')
    vm.sessionInfo = { ...initResult }
    vm.uploadState = 'done'
    expect(vm.sessionStatusType).toBe('success')
    expect(vm.sessionStatusText).toBe('已完成')
    vm.uploadState = 'error'
    expect(vm.sessionStatusType).toBe('danger')
    expect(vm.sessionStatusText).toBe('失败')
    vm.uploadState = 'uploading'
    expect(vm.sessionStatusType).toBe('warning')
    expect(vm.sessionStatusText).toBe('上传中')
    vm.uploadState = 'merging'
    expect(vm.sessionStatusType).toBe('info')
    expect(vm.sessionStatusText).toBe('合并中')
    vm.uploadState = 'idle'
    expect(vm.sessionStatusText).toBe('就绪')
  })

  it('resetAll：uploadRef 为空与有 clearFiles 两侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const clearFiles = vi.fn()
    vm.uploadRef = { clearFiles }
    vm.selectedFile = makeFile(10)
    vm.resetAll()
    expect(clearFiles).toHaveBeenCalled()
    expect(vm.selectedFile).toBeNull()
    vm.uploadRef = null
    vm.resetAll() // 不抛错
  })

  it('stopPolling：无定时器时安全返回', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.stopPolling()
  })
})

describe('startUpload 上传流程', () => {
  it('未选择文件 → 警告并返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.startUpload()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择文件')
    expect(apiInitUpload).not.toHaveBeenCalled()
  })

  it('单文件完整流程：初始化 → 分片上传 → 终检完成 → 合并成功', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const file = makeFile(100)
    vm.selectedFile = file
    await vm.startUpload()
    expect(apiInitUpload).toHaveBeenCalledWith({
      file_name: 'test.bin',
      file_size: 100,
      chunk_size: CHUNK,
    })
    expect(apiUploadChunk).toHaveBeenCalledTimes(1)
    expect(apiUploadChunk.mock.calls[0][0]).toBe('s1')
    expect(apiUploadChunk.mock.calls[0][1]).toBe(0)
    expect(apiGetProgress).toHaveBeenCalledWith('s1')
    expect(apiMergeChunks).toHaveBeenCalledWith('s1')
    expect(vm.uploadState).toBe('done')
    expect(vm.currentStep).toBe(3)
    expect(vm.mergeResult).toEqual(mergeResult)
    expect(vm.sessionInfo.session_id).toBe('s1')
    expect(vm.progressInfo.status).toBe('completed')
    expect(vm.chunkStatuses).toEqual([{ index: 0, done: true, current: false, pending: false }])
    expect(ElMessage.success).toHaveBeenCalledWith('文件上传并合并成功！')
    expect(vm.initializing).toBe(false)
  })

  it('多块文件：循环上传全部成功', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedFile = makeFile(CHUNK + 10)
    apiInitUpload.mockResolvedValueOnce({ ...initResult, total_chunks: 2 })
    await vm.startUpload()
    expect(apiUploadChunk).toHaveBeenCalledTimes(2)
    expect(vm.uploadState).toBe('done')
  })

  it('分片上传失败 → 报错、状态 error、停止轮询并返回', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedFile = makeFile(100)
    apiUploadChunk.mockRejectedValueOnce(new Error('net'))
    await vm.startUpload()
    expect(ElMessage.error).toHaveBeenCalledWith('块 1 上传失败')
    expect(vm.uploadState).toBe('error')
    expect(vm.initializing).toBe(false)
    expect(apiMergeChunks).not.toHaveBeenCalled()
  })

  it('上传循环中状态被外部改变 → break 跳出且不再终检', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedFile = makeFile(CHUNK + 10)
    apiInitUpload.mockResolvedValueOnce({ ...initResult, total_chunks: 2 })
    apiUploadChunk.mockImplementationOnce(async () => {
      vm.uploadState = 'merging' // 模拟轮询已把状态推进到 merging
      return { success: true }
    })
    await vm.startUpload()
    expect(apiUploadChunk).toHaveBeenCalledTimes(1)
    expect(apiGetProgress).not.toHaveBeenCalled()
    expect(apiMergeChunks).not.toHaveBeenCalled()
    expect(vm.uploadState).toBe('merging')
  })

  it('终检进度未完成 → 不触发合并', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedFile = makeFile(100)
    apiGetProgress.mockResolvedValueOnce({ ...progressDone, status: 'uploading', progress: 50 })
    await vm.startUpload()
    expect(apiMergeChunks).not.toHaveBeenCalled()
    expect(vm.uploadState).toBe('uploading')
    expect(vm.progressInfo.progress).toBe(50)
  })

  it('初始化失败：err.message 与兜底文案两分支', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedFile = makeFile(100)
    apiInitUpload.mockRejectedValueOnce(new Error('初始化被拒'))
    await vm.startUpload()
    expect(ElMessage.error).toHaveBeenCalledWith('初始化被拒')
    expect(vm.uploadState).toBe('error')
    apiInitUpload.mockRejectedValueOnce({})
    await vm.startUpload()
    expect(ElMessage.error).toHaveBeenCalledWith('初始化上传失败')
    expect(vm.initializing).toBe(false)
  })
})

describe('doMerge 合并', () => {
  it('无会话 → 直接返回', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    await vm.doMerge()
    expect(apiMergeChunks).not.toHaveBeenCalled()
  })

  it('合并失败：err.message 与兜底文案两分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.sessionInfo = { ...initResult }
    apiMergeChunks.mockRejectedValueOnce(new Error('磁盘满'))
    await vm.doMerge()
    expect(ElMessage.error).toHaveBeenCalledWith('磁盘满')
    expect(vm.uploadState).toBe('error')
    apiMergeChunks.mockRejectedValueOnce(null)
    await vm.doMerge()
    expect(ElMessage.error).toHaveBeenCalledWith('合并失败')
  })
})

describe('cancelUpload 取消上传', () => {
  it('无会话 → 直接返回', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    await vm.cancelUpload()
    expect(confirmMock).not.toHaveBeenCalled()
  })

  it('用户取消确认 → 不发请求', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.sessionInfo = { ...initResult }
    confirmMock.mockRejectedValueOnce('cancel')
    await vm.cancelUpload()
    expect(apiCancelUpload).not.toHaveBeenCalled()
    expect(vm.cancelling).toBe(false)
  })

  it('确认取消成功 → 提示并复位会话', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.sessionInfo = { ...initResult }
    vm.uploadState = 'uploading'
    await vm.cancelUpload()
    expect(apiCancelUpload).toHaveBeenCalledWith('s1')
    expect(ElMessage.success).toHaveBeenCalledWith('上传已取消')
    expect(vm.cancelling).toBe(false)
    expect(vm.sessionInfo).toBeNull()
    expect(vm.uploadState).toBe('idle')
  })

  it('取消接口失败 → 错误提示但仍复位', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.sessionInfo = { ...initResult }
    apiCancelUpload.mockRejectedValueOnce(new Error('net'))
    await vm.cancelUpload()
    expect(ElMessage.error).toHaveBeenCalledWith('取消失败')
    expect(vm.cancelling).toBe(false)
    expect(vm.sessionInfo).toBeNull()
  })
})

describe('轮询进度', () => {
  it('进行中 → 更新进度与块状态（done/current/pending 三态）', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.sessionInfo = { ...initResult, total_chunks: 3 }
    apiGetProgress.mockResolvedValue({
      session_id: 's1',
      file_name: 'test.bin',
      total_chunks: 3,
      uploaded_chunks: 1,
      progress: 33.3,
      status: 'uploading',
    })
    vm.startPolling()
    await vi.advanceTimersByTimeAsync(500)
    expect(vm.progressInfo.progress).toBeCloseTo(33.3)
    expect(vm.chunkStatuses).toEqual([
      { index: 0, done: true, current: false, pending: false },
      { index: 1, done: false, current: true, pending: false },
      { index: 2, done: false, current: false, pending: true },
    ])
    expect(vm.uploadState).toBe('idle') // 未完成不改状态
    vm.stopPolling()
  })

  it('轮询到 completed → 转合并并完成', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.sessionInfo = { ...initResult }
    vm.uploadState = 'uploading'
    vm.startPolling()
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()
    expect(apiMergeChunks).toHaveBeenCalledWith('s1')
    expect(vm.uploadState).toBe('done')
    expect(ElMessage.success).toHaveBeenCalledWith('文件上传并合并成功！')
  })

  it('轮询到 merged → 同样触发合并（|| 右支）', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.sessionInfo = { ...initResult }
    vm.uploadState = 'uploading'
    apiGetProgress.mockResolvedValue({ ...progressDone, status: 'merged' })
    vm.startPolling()
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()
    expect(apiMergeChunks).toHaveBeenCalled()
    expect(vm.uploadState).toBe('done')
  })

  it('轮询到 error → 状态 error 并提示', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.sessionInfo = { ...initResult }
    vm.uploadState = 'uploading'
    apiGetProgress.mockResolvedValue({ ...progressDone, status: 'error' })
    vm.startPolling()
    await vi.advanceTimersByTimeAsync(500)
    expect(vm.uploadState).toBe('error')
    expect(ElMessage.error).toHaveBeenCalledWith('上传过程中出现错误')
  })

  it('会话为空 → 轮询回调直接返回', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.startPolling()
    await vi.advanceTimersByTimeAsync(500)
    expect(apiGetProgress).not.toHaveBeenCalled()
    vm.stopPolling()
  })

  it('进度接口异常 → 静默继续（catch 分支）', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.sessionInfo = { ...initResult }
    apiGetProgress.mockRejectedValueOnce(new Error('net'))
    vm.startPolling()
    await vi.advanceTimersByTimeAsync(500)
    expect(vm.uploadState).toBe('idle') // 不受影响
    // 下一轮正常返回
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()
    expect(apiGetProgress).toHaveBeenCalledTimes(2)
    vm.stopPolling()
  })

  it('连续 10 次进度接口失败 → 进入 error 终态并停止轮询', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.sessionInfo = { ...initResult }
    apiGetProgress.mockRejectedValue(new Error('session gone'))
    vm.startPolling()
    for (let i = 0; i < 10; i += 1) {
      await vi.advanceTimersByTimeAsync(500)
    }
    expect(vm.uploadState).toBe('error')
    expect(ElMessage.error).toHaveBeenCalledWith('上传状态获取失败，请重试')
    const callsAfterStop = apiGetProgress.mock.calls.length
    await vi.advanceTimersByTimeAsync(1000)
    expect(apiGetProgress.mock.calls.length).toBe(callsAfterStop)
  })

  it('卸载组件时停止轮询', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.sessionInfo = { ...initResult }
    vm.startPolling()
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(1000)
    expect(apiGetProgress).not.toHaveBeenCalled()
  })
})

describe('模板状态渲染', () => {
  it('会话卡 + 进度卡（uploading）：块条三态与进度文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.sessionInfo = { ...initResult, total_chunks: 3 }
    vm.uploadState = 'uploading'
    vm.progressInfo = {
      session_id: 's1',
      file_name: 'test.bin',
      total_chunks: 3,
      uploaded_chunks: 1,
      progress: 33.3,
      status: 'uploading',
    }
    vm.chunkStatuses = [
      { index: 0, done: true, current: false, pending: false },
      { index: 1, done: false, current: true, pending: false },
      { index: 2, done: false, current: false, pending: true },
    ]
    await nextTick()
    expect(wrapper.find('.info-card').exists()).toBe(true)
    expect(wrapper.find('.progress-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('1 / 3 块 (33.3%)')
    expect(wrapper.text()).toContain('上传中')
    expect(wrapper.findAll('.chunk-bar')).toHaveLength(3)
    const bars = wrapper.findAll('.chunk-bar')
    expect(bars[0].attributes('title')).toBe('块 1: 已完成')
    expect(bars[1].attributes('title')).toBe('块 2: 上传中')
    expect(bars[2].attributes('title')).toBe('块 3: 待上传')
    expect(wrapper.find('.chunk-done').exists()).toBe(true)
    expect(wrapper.find('.chunk-current').exists()).toBe(true)
    expect(wrapper.find('.chunk-pending').exists()).toBe(true)
    // uploading → 取消上传按钮
    const cancelBtn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('取消上传'))
    expect(cancelBtn).toBeDefined()
  })

  it('progressInfo 为空 → 0 值兜底渲染；merging → 块条仍显示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.sessionInfo = { ...initResult }
    vm.uploadState = 'merging'
    vm.progressInfo = null
    vm.chunkStatuses = [{ index: 0, done: true, current: false, pending: false }]
    await nextTick()
    expect(wrapper.text()).toContain('0 / 0 块 (0.0%)')
    expect(wrapper.find('.chunk-progress-bars').exists()).toBe(true)
  })

  it('done：结果卡渲染 + 重新上传按钮；error：开始/重新按钮并存', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.sessionInfo = { ...initResult }
    vm.uploadState = 'done'
    vm.mergeResult = { ...mergeResult }
    await nextTick()
    expect(wrapper.find('.result-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('/uploads/test.bin')
    const texts = wrapper.findAll('el-button-stub').map((b) => b.text())
    expect(texts.some((t) => t.includes('重新上传'))).toBe(true)
    expect(texts.some((t) => t.includes('开始上传'))).toBe(false)
    // error 态：开始上传（error 支）与重新上传（error 支）同时出现
    vm.uploadState = 'error'
    vm.mergeResult = null
    await nextTick()
    const texts2 = wrapper.findAll('el-button-stub').map((b) => b.text())
    expect(texts2.some((t) => t.includes('开始上传'))).toBe(true)
    expect(texts2.some((t) => t.includes('重新上传'))).toBe(true)
    expect(wrapper.find('.result-card').exists()).toBe(false)
  })

  it('操作卡 v-if 两侧：仅选文件（无会话）与仅有会话（无文件）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedFile = makeFile(10)
    await nextTick()
    expect(wrapper.find('.actions-card').exists()).toBe(true)
    // idle + 有文件 → 开始上传按钮（idle 支）
    const texts = wrapper.findAll('el-button-stub').map((b) => b.text())
    expect(texts.some((t) => t.includes('开始上传'))).toBe(true)
    vm.selectedFile = null
    vm.sessionInfo = { ...initResult }
    await nextTick()
    expect(wrapper.find('.actions-card').exists()).toBe(true)
    vm.sessionInfo = null
    await nextTick()
    expect(wrapper.find('.actions-card').exists()).toBe(false)
  })
})
