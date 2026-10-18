/**
 * api/supportedVillage.ts —— w17-007 一村一档 PDF 下载函数测试。
 *
 * 与既有 supportedVillageFull/Export/Rollforward 测试合跑时，本文件补齐
 * downloadVillageDossier 的语句/分支覆盖（四指标 100%）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockDownloadBlobAsFile } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockDownloadBlobAsFile: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/api/request', () => ({
  default: { get: (...args: any[]) => mockGet(...args) },
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  parseContentDisposition: vi.fn(),
  downloadBlob: vi.fn(),
}))

vi.mock('@/api/helpers/blobDownload', () => ({
  downloadBlobAsFile: (...args: any[]) => mockDownloadBlobAsFile(...args),
}))

import { downloadVillageDossier } from '@/api/supportedVillage'

describe('downloadVillageDossier (w17-007)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('请求 /supported-villages/{id}/dossier.pdf（blob）并走统一下载工具', async () => {
    const response = { data: new Blob(['%PDF-']), headers: {} }
    mockGet.mockResolvedValue(response)

    await downloadVillageDossier(7)

    expect(mockDownloadBlobAsFile).toHaveBeenCalledWith(expect.any(Function), {
      fallbackFileName: '帮扶村档案册.pdf',
    })

    // 下载工具内部回调必须真实发起请求（文件名解析依赖原始响应头）
    const requestFn = mockDownloadBlobAsFile.mock.calls[0][0]
    await expect(requestFn()).resolves.toEqual(response)
    expect(mockGet).toHaveBeenCalledWith('/supported-villages/7/dossier.pdf', {
      responseType: 'blob',
    })
  })
})
