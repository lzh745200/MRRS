/**
 * api/media.ts 测试（四指标 100%）
 *
 * media.ts 依赖：`@/api/request`（get/post/put/del/apiRequest/default.get）
 * 与 `@/api/helpers/blobDownload`（downloadBlobAsFile）。
 * 对比图下载通过 mock 的 downloadBlobAsFile 驱动其请求回调，验证 GET 参数与兜底文件名。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost, mockPut, mockDel, mockApiRequest, mockRequestGet, mockDownload } =
  vi.hoisted(() => ({
    mockGet: vi.fn(),
    mockPost: vi.fn(),
    mockPut: vi.fn(),
    mockDel: vi.fn(),
    mockApiRequest: vi.fn(),
    mockRequestGet: vi.fn(),
    mockDownload: vi.fn(),
  }))

vi.mock('@/api/request', () => ({
  get: (...a: any[]) => mockGet(...a),
  post: (...a: any[]) => mockPost(...a),
  put: (...a: any[]) => mockPut(...a),
  del: (...a: any[]) => mockDel(...a),
  apiRequest: (...a: any[]) => mockApiRequest(...a),
  default: { get: (url: string, config?: any) => mockRequestGet(url, config) },
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/api/helpers/blobDownload', () => ({
  downloadBlobAsFile: (...a: any[]) => mockDownload(...a),
}))

import {
  getPhotos,
  createPhoto,
  updatePhoto,
  deletePhoto,
  getPhotoCompare,
  generateCompareImage,
  downloadCompareImage,
} from '@/api/media'

describe('api/media — 列表与 CRUD', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getPhotos：无参/带筛选参数', async () => {
    const list = { items: [{ id: 1 }], total: 1 }
    mockGet.mockResolvedValueOnce(list)
    expect(await getPhotos()).toBe(list)
    expect(mockGet).toHaveBeenCalledWith('/media/photos', undefined)

    const params = {
      page: 2,
      page_size: 24,
      village_id: 3,
      school_id: 4,
      project_id: 5,
      tag: '产业',
      date_from: '2024-01-01',
      date_to: '2024-12-31',
    }
    mockGet.mockResolvedValueOnce({ items: [], total: 0 })
    await getPhotos(params)
    expect(mockGet).toHaveBeenLastCalledWith('/media/photos', params)
  })

  it('createPhoto / updatePhoto / deletePhoto 端点与载荷', async () => {
    mockPost.mockResolvedValueOnce({ id: 9 })
    expect(await createPhoto({ file_url: '/uploads/a.jpg', tag: '村容' })).toEqual({ id: 9 })
    expect(mockPost).toHaveBeenCalledWith('/media/photos', {
      file_url: '/uploads/a.jpg',
      tag: '村容',
    })

    mockPut.mockResolvedValueOnce({ id: 9, tag: '新标签' })
    await updatePhoto(9, { tag: '新标签', spot_key: 'village-1' })
    expect(mockPut).toHaveBeenCalledWith('/media/photos/9', {
      tag: '新标签',
      spot_key: 'village-1',
    })

    mockDel.mockResolvedValueOnce(true)
    expect(await deletePhoto(9)).toBe(true)
    expect(mockDel).toHaveBeenCalledWith('/media/photos/9')
  })
})

describe('api/media — 拍摄点对比', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getPhotoCompare：spot_key 作为查询参数', async () => {
    const series = [{ id: 1, file_url: '/a.jpg', taken_at: '2024-01-01T00:00:00' }]
    mockGet.mockResolvedValueOnce(series)
    expect(await getPhotoCompare('village-1')).toBe(series)
    expect(mockGet).toHaveBeenCalledWith('/media/photos/compare', { spot_key: 'village-1' })
  })

  it('generateCompareImage：POST ids 并返回 Blob', async () => {
    const blob = new Blob(['png'], { type: 'image/png' })
    mockApiRequest.mockResolvedValueOnce(blob)
    expect(await generateCompareImage([1, 2, 3])).toBe(blob)
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'POST',
      url: '/media/photos/compare-image',
      data: { ids: [1, 2, 3] },
      responseType: 'blob',
    })
  })

  it('downloadCompareImage：GET 逗号分隔 ids + 兜底文件名', async () => {
    // mock 的 downloadBlobAsFile 执行请求回调，覆盖 media.ts 内联回调
    mockDownload.mockImplementationOnce(async (requestFn: () => Promise<any>) => {
      await requestFn()
    })
    mockRequestGet.mockResolvedValueOnce({ data: new Blob(['png']), headers: {} })

    await downloadCompareImage([2, 4])

    expect(mockRequestGet).toHaveBeenCalledWith('/media/photos/compare-image', {
      params: { ids: '2,4' },
      responseType: 'blob',
    })
    expect(mockDownload).toHaveBeenCalledWith(expect.any(Function), {
      fallbackFileName: '影像对比图.png',
    })
  })
})
