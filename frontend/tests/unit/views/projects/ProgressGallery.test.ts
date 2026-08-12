/**
 * views/projects/ProgressGallery.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 加载项目与文件、Blob URL 加载（成功/失败/非 2xx）、
 * progressFiles 过滤、previewList、comparisonPairs 名称配对与顺序配对、
 * handleUpload（成功/失败）、handleDelete（取消/成功/失败）、
 * getStatusType/getStatusText 全分支、onUnmounted 释放 URL。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { ElMessage, confirmMock, projectsApiMock, logError, routeBox } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  projectsApiMock: {
    get: vi.fn(),
    listFiles: vi.fn(),
    getFileDownloadUrl: vi.fn(),
    uploadFiles: vi.fn(),
    deleteFile: vi.fn(),
  },
  logError: vi.fn(),
  routeBox: { params: { id: '5' } as Record<string, any> },
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeBox,
  useRouter: () => ({ back: vi.fn() }),
}))

vi.mock('element-plus', () => ({ ElMessage, ElMessageBox: { confirm: confirmMock } }))

vi.mock('@/api/projects', () => ({ projectsApi: projectsApiMock }))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: vi.fn() }),
  safeRouteParam: (v: any) => Number(v) || v,
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import ProgressGallery from '@/views/projects/ProgressGallery.vue'

const project = { id: 5, name: '产业路', code: 'XM-001', status: 'in_progress', responsible_unit: '镇府', budget: 100, start_date: '2024-01-01' }

const fileBefore = { id: 11, filename: 'before_施工1.jpg', name: 'before_施工1.jpg', category: 'progress', created_at: '2024-01-01T00:00:00' }
const fileAfter = { id: 12, filename: 'after_施工1.jpg', name: 'after_施工1.jpg', category: 'progress', created_at: '2024-01-02T00:00:00' }
const fileOther = { id: 13, filename: '合同.pdf', name: '合同.pdf', category: 'attachment' }
const fileSeq1 = { id: 14, filename: '图A.jpg', name: '图A.jpg', category: 'progress' }
const fileSeq2 = { id: 15, filename: '图B.jpg', name: '图B.jpg', category: 'progress' }
const fileNoCat = { id: 16, name: '无分类文件.pdf' }
const fileNoFilename = { id: 17, name: '仅name字段', category: 'progress' }
const fileEmptyNames = { id: 18, filename: '', name: '', category: 'progress' }

const fetchMock = vi.hoisted(() => vi.fn())

function mountComp() {
  return mount(ProgressGallery, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-page-header': {
          name: 'ElPageHeader',
          template: '<div class="el-page-header-stub"><slot name="content" /><slot /></div>',
          emits: ['back'],
        },
        'el-card': { template: '<div class="el-card-stub"><slot /></div>' },
        'el-skeleton': { template: '<div class="el-skeleton-stub" />' },
        'el-descriptions': { template: '<div class="el-descriptions-stub"><slot /></div>' },
        'el-descriptions-item': { template: '<div class="el-desc-item-stub"><slot /></div>' },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-divider': { template: '<div class="el-divider-stub"><slot /></div>' },
        'el-upload': { template: '<div class="el-upload-stub"><slot /></div>' },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-empty': {
          template:
            '<div class="el-empty-stub">{{ description }}<slot /></div>',
          props: ['description'],
        },
        'el-image': { template: '<div class="el-image-stub"><slot name="error" /></div>' },
        'el-icon': { template: '<span class="el-icon-stub"><slot /></span>' },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  routeBox.params = { id: '5' }
  projectsApiMock.get.mockResolvedValue(project)
  projectsApiMock.listFiles.mockResolvedValue({ items: [fileBefore, fileAfter, fileOther, fileSeq1, fileSeq2, fileNoCat, fileNoFilename, fileEmptyNames] })
  projectsApiMock.getFileDownloadUrl.mockReturnValue('/api/v1/projects/5/files/11/download')
  projectsApiMock.uploadFiles.mockResolvedValue({})
  projectsApiMock.deleteFile.mockResolvedValue({})
  confirmMock.mockResolvedValue(undefined)
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockResolvedValue({ ok: true, blob: vi.fn().mockResolvedValue(new Blob(['x'])) })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('挂载与数据加载', () => {
  it('onMounted 加载项目/文件并生成 Blob URL', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(projectsApiMock.get).toHaveBeenCalledWith(5)
    expect(projectsApiMock.listFiles).toHaveBeenCalledWith(5)
    expect(vm.project).toEqual(project)
    expect(vm.progressFiles).toHaveLength(6)
    expect(vm.previewList).toHaveLength(6)
    expect(vm.blobUrls[11]).toBeTruthy()
    expect(vm.loading).toBe(false)
  })

  it('后端返回 {files: [...]}（非 items）→ 兼容加载', async () => {
    projectsApiMock.listFiles.mockResolvedValue({ files: [fileBefore, fileAfter], grouped: { progress: [fileBefore] } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.allFiles).toHaveLength(2)
    expect(vm.progressFiles).toHaveLength(2)
  })

  it('fetch 非 2xx → 不设置 URL', async () => {
    fetchMock.mockResolvedValue({ ok: false })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).blobUrls[11]).toBeUndefined()
  })

  it('fetch 异常 → 静默', async () => {
    fetchMock.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).blobUrls).toEqual({})
    expect(logError).not.toHaveBeenCalled()
  })

  it('filesRes 直返数组格式', async () => {
    projectsApiMock.listFiles.mockResolvedValue([fileBefore, fileOther])
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).allFiles).toHaveLength(2)
  })

  it('加载失败 → logger + 错误提示', async () => {
    projectsApiMock.get.mockRejectedValue(new Error('boom'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('加载数据失败，请返回重试')
    expect((wrapper.vm as any).loading).toBe(false)
  })
})

describe('comparisonPairs', () => {
  it('名称配对（before/after）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const pairs = vm.comparisonPairs
    expect(pairs).toHaveLength(1)
    expect(pairs[0].label).toBe('对比 1')
    expect(pairs[0].beforeUrl).toBe(vm.blobUrls[11])
    expect(pairs[0].afterUrl).toBe(vm.blobUrls[12])
  })

  it('顺序配对兜底（无 before/after 命名）', async () => {
    projectsApiMock.listFiles.mockResolvedValue({ items: [fileSeq1, fileSeq2, fileBefore] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const pairs = vm.comparisonPairs
    expect(pairs.length).toBeGreaterThanOrEqual(1)
  })

  it('listFiles 返回 null → 空数组', async () => {
    projectsApiMock.listFiles.mockResolvedValue(null)
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).allFiles).toEqual([])
  })

  it('少于 2 张 → 空', async () => {
    projectsApiMock.listFiles.mockResolvedValue({ items: [fileSeq1, fileOther] })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).comparisonPairs).toEqual([])
  })

  it('文件缺 filename 与 name → ?? 链兜底为空串（不匹配 before/after 分组）', async () => {
    projectsApiMock.listFiles.mockResolvedValue({
      items: [
        { id: 20, category: 'progress' },
        { id: 21, filename: null, category: 'progress' },
      ],
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.progressFiles).toHaveLength(2)
    // 两个文件均不匹配 before/after 正则 → 走顺序配对兜底
    expect(vm.comparisonPairs).toHaveLength(1)
  })

  it('顺序配对但 Blob URL 缺失 → beforeUrl/afterUrl 空串兜底', async () => {
    fetchMock.mockResolvedValue({ ok: false })
    projectsApiMock.listFiles.mockResolvedValue({ items: [fileSeq1, fileSeq2] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.blobUrls).toEqual({})
    const pairs = vm.comparisonPairs
    expect(pairs).toHaveLength(1)
    expect(pairs[0].beforeUrl).toBe('')
    expect(pairs[0].afterUrl).toBe('')
  })
})

describe('上传', () => {
  it('上传成功 → 刷新文件列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    projectsApiMock.listFiles.mockClear()
    await vm.handleUpload({ file: new File(['x'], 'a.jpg', { type: 'image/jpeg' }) })
    expect(projectsApiMock.uploadFiles).toHaveBeenCalledWith(5, 'progress', expect.any(Array))
    expect(ElMessage.success).toHaveBeenCalledWith('上传成功')
    expect(projectsApiMock.listFiles).toHaveBeenCalled()
  })

  it('上传失败 → logger + 提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    projectsApiMock.uploadFiles.mockRejectedValue(new Error('上传失败'))
    await (wrapper.vm as any).handleUpload({ file: {} })
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('上传失败')
  })

  it('上传失败（err 为 null）→ e?.message 兜底「上传失败」', async () => {
    const wrapper = mountComp()
    await flushPromises()
    projectsApiMock.uploadFiles.mockRejectedValue(null)
    await (wrapper.vm as any).handleUpload({ file: {} })
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('上传失败')
  })

  it('上传成功但 listFiles 返回 null → 空数组', async () => {
    const wrapper = mountComp()
    await flushPromises()
    projectsApiMock.listFiles.mockResolvedValue(null)
    await (wrapper.vm as any).handleUpload({ file: {} })
    expect((wrapper.vm as any).allFiles).toEqual([])
  })

  it('上传成功且 listFiles 返回 {files:[...]}（后端实际结构）→ 兼容刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    projectsApiMock.listFiles.mockResolvedValue({ files: [fileBefore], grouped: { progress: [fileBefore] } })
    await (wrapper.vm as any).handleUpload({ file: {} })
    expect((wrapper.vm as any).allFiles).toHaveLength(1)
  })

  it('上传成功且 listFiles 返回数组直返 → 兼容刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    projectsApiMock.listFiles.mockResolvedValue([fileBefore])
    await (wrapper.vm as any).handleUpload({ file: {} })
    expect((wrapper.vm as any).allFiles).toHaveLength(1)
  })
})

describe('删除', () => {
  it('确认后删除成功并释放 URL', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    projectsApiMock.listFiles.mockClear()
    await vm.handleDelete(11)
    expect(confirmMock).toHaveBeenCalledWith('确定删除该进度照片？', '提示', { type: 'warning' })
    expect(projectsApiMock.deleteFile).toHaveBeenCalledWith(5, 11)
    expect(revoke).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('已删除')
    expect(projectsApiMock.listFiles).toHaveBeenCalled()
    revoke.mockRestore()
  })

  it('删除成功但 listFiles 返回 null → 空数组', async () => {
    const wrapper = mountComp()
    await flushPromises()
    projectsApiMock.listFiles.mockResolvedValue(null)
    await (wrapper.vm as any).handleDelete(11)
    expect((wrapper.vm as any).allFiles).toEqual([])
  })

  it('删除成功且 listFiles 返回 {files:[...]}（后端实际结构）→ 兼容刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    projectsApiMock.listFiles.mockResolvedValue({ files: [fileAfter], grouped: { progress: [fileAfter] } })
    await (wrapper.vm as any).handleDelete(11)
    expect((wrapper.vm as any).allFiles).toHaveLength(1)
  })

  it('删除成功且 listFiles 返回数组直返 → 兼容刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    projectsApiMock.listFiles.mockResolvedValue([fileAfter])
    await (wrapper.vm as any).handleDelete(11)
    expect((wrapper.vm as any).allFiles).toHaveLength(1)
  })

  it('取消 → 不删除', async () => {
    const wrapper = mountComp()
    await flushPromises()
    confirmMock.mockRejectedValueOnce('cancel')
    await (wrapper.vm as any).handleDelete(11)
    expect(projectsApiMock.deleteFile).not.toHaveBeenCalled()
  })

  it('删除失败（cancel 字符串形态）→ 不提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    confirmMock.mockResolvedValueOnce(undefined)
    projectsApiMock.deleteFile.mockRejectedValueOnce(new Error('cancel'))
    await (wrapper.vm as any).handleDelete(11)
    expect(ElMessage.error).not.toHaveBeenCalledWith('cancel')
  })

  it('删除失败 → logger + 提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    projectsApiMock.deleteFile.mockRejectedValueOnce(new Error('删除失败'))
    await (wrapper.vm as any).handleDelete(11)
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })

  it('删除失败（err 为 null）→ e?.message 兜底「删除失败」', async () => {
    const wrapper = mountComp()
    await flushPromises()
    confirmMock.mockResolvedValueOnce(undefined)
    projectsApiMock.deleteFile.mockRejectedValueOnce(null)
    await (wrapper.vm as any).handleDelete(11)
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })
})

describe('状态字典', () => {
  it('getStatusType 全映射与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getStatusType('draft')).toBe('info')
    expect(vm.getStatusType('pending')).toBe('info')
    expect(vm.getStatusType('approved')).toBe('primary')
    expect(vm.getStatusType('planning')).toBe('info')
    expect(vm.getStatusType('in_progress')).toBe('warning')
    expect(vm.getStatusType('completed')).toBe('success')
    expect(vm.getStatusType('cancelled')).toBe('danger')
    expect(vm.getStatusType('suspended')).toBe('danger')
    expect(vm.getStatusType('unknown')).toBe('info')
    expect(vm.getStatusType(undefined)).toBe('info')
  })

  it('getStatusText 全映射与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getStatusText('draft')).toBe('草稿')
    expect(vm.getStatusText('pending')).toBe('待审批')
    expect(vm.getStatusText('approved')).toBe('已审批')
    expect(vm.getStatusText('planning')).toBe('规划中')
    expect(vm.getStatusText('in_progress')).toBe('进行中')
    expect(vm.getStatusText('completed')).toBe('已完成')
    expect(vm.getStatusText('cancelled')).toBe('已取消')
    expect(vm.getStatusText('suspended')).toBe('已暂停')
    expect(vm.getStatusText('unknown')).toBe('unknown')
    expect(vm.getStatusText(undefined)).toBe('-')
  })

  it('goBack → router.back', async () => {
    const backMock = vi.fn()
    vi.mocked(await import('vue-router')).useRouter = () => ({ back: backMock })
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).goBack()
    expect(backMock).toHaveBeenCalled()
  })
})

describe('卸载清理', () => {
  it('onUnmounted 释放全部 Blob URL', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    wrapper.unmount()
    expect(revoke).toHaveBeenCalled()
    expect((wrapper.vm as any).blobUrls).toEqual({})
    revoke.mockRestore()
  })
})

describe('模板渲染', () => {
  it('空态与加载态渲染', async () => {
    projectsApiMock.listFiles.mockResolvedValue({ items: [] })
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.text()).toContain('暂无进度照片')
  })

  it('删除按钮点击触发 handleDelete', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const delBtn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('删除'))
    expect(delBtn).toBeTruthy()
    await delBtn!.trigger('click')
    await flushPromises()
    expect(projectsApiMock.deleteFile).toHaveBeenCalled()
  })

  it('页头 back → router.back', async () => {
    const backMock = vi.fn()
    vi.mocked(await import('vue-router')).useRouter = () => ({ back: backMock })
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.findComponent({ name: 'ElPageHeader' }).vm.$emit('back')
    expect(backMock).toHaveBeenCalled()
  })
})
