import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost, mockDelete } = vi.hoisted(() => ({
  mockGet: vi.fn().mockResolvedValue({ data: {} }),
  mockPost: vi.fn().mockResolvedValue({ data: {} }),
  mockDelete: vi.fn().mockResolvedValue({ data: {} }),
}))

vi.mock('@/api/request', () => {
  const requestInstance = {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
  }
  return {
    default: requestInstance,
    get: requestInstance.get,
    post: requestInstance.post,
    del: requestInstance.delete,
  }
})

import { restoreFund, previewPurgeFund, purgeFund } from '@/api/fundsRecycle'
import { restoreSchool, previewPurgeSchool, purgeSchool } from '@/api/schoolsRecycle'
import { clearTiles, importTiles, TILE_IMPORT_TIMEOUT_MS } from '@/api/offlineMap'

describe('api/fundsRecycle', () => {
  beforeEach(() => vi.clearAllMocks())

  it('restoreFund POST /funds/{id}/restore', async () => {
    await restoreFund(7)
    expect(mockPost).toHaveBeenCalledWith('/funds/7/restore', {})
  })

  it('previewPurgeFund GET /funds/{id}/purge/preview', async () => {
    await previewPurgeFund(7)
    expect(mockGet).toHaveBeenCalledWith('/funds/7/purge/preview')
  })

  it('purgeFund 携带确认密码；缺省时为空串', async () => {
    await purgeFund(7, 'pw')
    expect(mockPost).toHaveBeenCalledWith('/funds/7/purge', { confirm_password: 'pw' })
    await purgeFund(7)
    expect(mockPost).toHaveBeenCalledWith('/funds/7/purge', { confirm_password: '' })
  })
})

describe('api/schoolsRecycle', () => {
  beforeEach(() => vi.clearAllMocks())

  it('restoreSchool POST /schools/{id}/restore', async () => {
    await restoreSchool(3)
    expect(mockPost).toHaveBeenCalledWith('/schools/3/restore', {})
  })

  it('previewPurgeSchool GET /schools/{id}/purge/preview', async () => {
    await previewPurgeSchool(3)
    expect(mockGet).toHaveBeenCalledWith('/schools/3/purge/preview')
  })

  it('purgeSchool 携带确认密码', async () => {
    await purgeSchool(3, 'pw')
    expect(mockPost).toHaveBeenCalledWith('/schools/3/purge', { confirm_password: 'pw' })
  })

  /**
   * `confirmPassword || ''` 的假侧。
   * 上方用例只传了真值密码；省略参数 / 空串 / 显式 undefined 三种写法
   * 都必须归一为 `confirm_password: ''`，而不是把 undefined 传给后端
   * （JSON 序列化会直接丢字段，导致后端 422）。
   */
  it('purgeSchool 缺省密码 → confirm_password 为空串', async () => {
    await purgeSchool(3)
    expect(mockPost).toHaveBeenCalledWith('/schools/3/purge', { confirm_password: '' })
  })

  it('purgeSchool 显式 undefined / 空串 → 同样归一为空串', async () => {
    await purgeSchool(3, undefined)
    expect(mockPost).toHaveBeenLastCalledWith('/schools/3/purge', { confirm_password: '' })

    await purgeSchool(3, '')
    expect(mockPost).toHaveBeenLastCalledWith('/schools/3/purge', { confirm_password: '' })
    // 两次调用均携带完整 payload 形状
    expect(mockPost).toHaveBeenCalledTimes(2)
    mockPost.mock.calls.forEach(([, body]) => {
      expect(Object.keys(body as object)).toEqual(['confirm_password'])
    })
  })
})

describe('api/offlineMap', () => {
  beforeEach(() => vi.clearAllMocks())

  it('importTiles 走 multipart 且携带 zip 文件', async () => {
    const file = new File(['x'], 'tiles.zip')
    await importTiles(file)
    const [url, body] = mockPost.mock.calls[0]
    expect(url).toBe('/map/tiles/import')
    expect((body as FormData).get('file')).toBe(file)
  })

  it('importTiles 使用 15 分钟超时（大包解压 60s+，全局 30s 会误报超时）', async () => {
    await importTiles(new File(['x'], 'tiles.zip'))
    const config = mockPost.mock.calls[0][2] as any
    expect(config.timeout).toBe(TILE_IMPORT_TIMEOUT_MS)
    expect(TILE_IMPORT_TIMEOUT_MS).toBe(15 * 60 * 1000)
  })

  it('importTiles 支持自定义超时与上传进度回调（0~100 截断）', async () => {
    const seen: number[] = []
    await importTiles(new File(['x'], 'tiles.zip'), {
      timeoutMs: 1234,
      onProgress: (p) => seen.push(p),
    })
    const config = mockPost.mock.calls[0][2] as any
    expect(config.timeout).toBe(1234)
    config.onUploadProgress({ loaded: 50, total: 100 })
    config.onUploadProgress({ loaded: 200, total: 100 })
    config.onUploadProgress({ loaded: 0, total: 0 }) // total 未知 → 忽略
    expect(seen).toEqual([50, 100])
  })

  it('clearTiles 走 DELETE /offline-map/clear', async () => {
    await clearTiles()
    expect(mockDelete).toHaveBeenCalledWith('/offline-map/clear')
  })
})
