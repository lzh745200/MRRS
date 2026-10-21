import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockGet = vi.fn()
const mockPost = vi.fn()
const mockDelete = vi.fn()

vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  post: (...args: any[]) => mockPost(...args),
  del: (...args: any[]) => mockDelete(...args),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

import { clearTiles, importTiles } from '@/api/offlineMap'

describe('api/offlineMap', () => {
  beforeEach(() => vi.clearAllMocks())

  it('importTiles POST /map/tiles/import，multipart 字段名 file', async () => {
    const file = new File(['zip-bytes'], 'guizhou.zip', { type: 'application/zip' })
    await importTiles(file)

    expect(mockPost).toHaveBeenCalledTimes(1)
    const [url, body] = mockPost.mock.calls[0]
    expect(url).toBe('/map/tiles/import')
    expect(body).toBeInstanceOf(FormData)
    const form = body as FormData
    expect(form.get('file')).toBe(file)
  })

  it('clearTiles DELETE /offline-map/clear', async () => {
    await clearTiles()
    expect(mockDelete).toHaveBeenCalledWith('/offline-map/clear')
  })

  it('已下线的假下载端点不再导出（getTiles / downloadTiles / getMapStatus）', async () => {
    const mod = (await import('@/api/offlineMap')) as Record<string, unknown>
    expect(mod.getTiles).toBeUndefined()
    expect(mod.downloadTiles).toBeUndefined()
    expect(mod.getMapStatus).toBeUndefined()
    expect(mod.offlineMapApi).toBeUndefined()
  })
})
