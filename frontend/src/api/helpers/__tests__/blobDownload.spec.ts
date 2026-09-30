/**
 * blobDownload.ts 单元测试
 *
 * 测试覆盖：
 * 1. parseFileName — 文件名解析（RFC 5987 / ASCII / 边界情况）
 * 2. downloadBlobAsFile — 下载流程（成功/失败/回调）
 * 3. getFileNameFromResponse — 便捷方法
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { AxiosResponse } from 'axios'
import { parseFileName, downloadBlobAsFile, getFileNameFromResponse } from '../blobDownload'

// ─── Mock DOM ───

let clickHandler: (() => void) | null = null
let createdObjectURLs: string[] = []
let revokedURLs: string[] = []

beforeEach(() => {
  // Mock URL.createObjectURL / revokeObjectURL
  createdObjectURLs = []
  revokedURLs = []
  vi.stubGlobal('URL', {
    createObjectURL: vi.fn((_blob: Blob) => {
      const url = `blob:mock/${createdObjectURLs.length}`
      createdObjectURLs.push(url)
      return url
    }),
    revokeObjectURL: vi.fn((url: string) => {
      revokedURLs.push(url)
    }),
  })

  // Mock document.createElement / document.body.appendChild
  clickHandler = null
  const mockLink = {
    href: '',
    download: '',
    style: { display: '' },
    click: vi.fn(() => {
      clickHandler?.()
    }),
  }
  vi.stubGlobal('document', {
    createElement: vi.fn(() => mockLink),
    body: {
      appendChild: vi.fn(),
      removeChild: vi.fn(),
    },
  })
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

// ─── parseFileName 测试 ───

describe('parseFileName', () => {
  it('解析 RFC 5987 UTF-8 编码文件名', () => {
    const cd = "attachment; filename*=UTF-8''%E5%B8%AE%E6%89%B6%E6%9D%91.xlsx"
    expect(parseFileName(cd)).toBe('帮扶村.xlsx')
  })

  it('解析 ASCII 引号文件名', () => {
    const cd = 'attachment; filename="report.csv"'
    expect(parseFileName(cd)).toBe('report.csv')
  })

  it('解析无引号 ASCII 文件名', () => {
    const cd = 'attachment; filename=data.json'
    expect(parseFileName(cd)).toBe('data.json')
  })

  it('优先使用 RFC 5987 格式', () => {
    const cd = 'attachment; filename="fallback.txt"; filename*=UTF-8\'\'%E4%B8%AD%E6%96%87.txt'
    expect(parseFileName(cd)).toBe('中文.txt')
  })

  it('空字符串返回 null', () => {
    expect(parseFileName('')).toBeNull()
  })

  it('undefined 返回 null', () => {
    expect(parseFileName(undefined)).toBeNull()
  })

  it('null 返回 null', () => {
    expect(parseFileName(null)).toBeNull()
  })

  it('无 filename 字段返回 null', () => {
    expect(parseFileName('attachment')).toBeNull()
  })

  it('RFC 5987 格式无分隔符返回 null', () => {
    const cd = 'attachment; filename*=UTF-8data.xlsx'
    expect(parseFileName(cd)).toBeNull() // 畸形头解析失败返回 null，调用方回退兜底文件名
  })

  it('URL 编码解析失败时回退到 ASCII', () => {
    // 无效的 percent-encoding
    const cd = 'attachment; filename*=UTF-8\'\'%ZZ; filename="fallback.csv"'
    expect(parseFileName(cd)).toBe('fallback.csv')
  })
})

// ─── downloadBlobAsFile 测试 ───

describe('downloadBlobAsFile', () => {
  it('处理 AxiosResponse<Blob> 并解析文件名', async () => {
    const mockBlob = new Blob(['test'], { type: 'text/csv' })
    const mockResponse: Partial<AxiosResponse<Blob>> = {
      data: mockBlob,
      headers: {
        'content-disposition': "attachment; filename*=UTF-8''%E7%BB%8F%E8%B4%B9.csv",
      },
    }

    vi.useFakeTimers()
    await downloadBlobAsFile(async () => mockResponse as AxiosResponse<Blob>)

    expect(createdObjectURLs).toHaveLength(1)
    vi.advanceTimersByTime(100) // downloadBlob 在 setTimeout(100ms) 后才 revokeObjectURL
    expect(revokedURLs).toHaveLength(1)
  })

  it('处理纯 Blob 返回（来自 apiRequest）', async () => {
    const mockBlob = new Blob(['data'], { type: 'application/pdf' })

    vi.useFakeTimers()
    await downloadBlobAsFile(async () => mockBlob, {
      fallbackFileName: 'export.pdf',
    })

    expect(createdObjectURLs).toHaveLength(1)
    vi.advanceTimersByTime(100) // downloadBlob 在 setTimeout(100ms) 后才 revokeObjectURL
    expect(revokedURLs).toHaveLength(1)
  })

  it('使用 fallbackFileName 当响应头无文件名时', async () => {
    const mockBlob = new Blob(['data'], { type: 'text/plain' })
    const mockResponse: Partial<AxiosResponse<Blob>> = {
      data: mockBlob,
      headers: {},
    }

    const onStart = vi.fn()
    const onEnd = vi.fn()

    vi.useFakeTimers()
    await downloadBlobAsFile(async () => mockResponse as AxiosResponse<Blob>, {
      fallbackFileName: 'default.txt',
      onStart,
      onEnd,
    })

    expect(onStart).toHaveBeenCalledTimes(1)
    expect(onEnd).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(100) // 冲刷 downloadBlob 内部 100ms 清理定时器，避免拆除后泄漏触发
  })

  it('onStart 和 onEnd 回调正确调用', async () => {
    const mockBlob = new Blob(['data'])
    const onStart = vi.fn()
    const onEnd = vi.fn()

    vi.useFakeTimers()
    await downloadBlobAsFile(async () => mockBlob, { onStart, onEnd })

    expect(onStart).toHaveBeenCalledTimes(1)
    expect(onEnd).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(100) // 同上：防止真实定时器在 document 解除 stub 后触发 removeChild
  })

  it('onError 在请求失败时被调用', async () => {
    const onError = vi.fn()
    const error = new Error('Network error')

    await expect(
      downloadBlobAsFile(async () => Promise.reject(error), { onError })
    ).rejects.toThrow('Network error')

    expect(onError).toHaveBeenCalledTimes(1)
    expect(onError).toHaveBeenCalledWith(error)
  })

  it('onEnd 在请求失败时仍被调用', async () => {
    const onEnd = vi.fn()
    const error = new Error('Network error')

    await expect(downloadBlobAsFile(async () => Promise.reject(error), { onEnd })).rejects.toThrow(
      'Network error'
    )

    expect(onEnd).toHaveBeenCalledTimes(1)
  })

  it('非 Blob 且非 AxiosResponse 的返回值抛出错误', async () => {
    await expect(downloadBlobAsFile(async () => 'invalid' as any)).rejects.toThrow(
      '既不是 Blob 也不是 AxiosResponse'
    )
  })

  it('AxiosResponse.data 不是 Blob（204/空响应）时判失败并走 onError', async () => {
    const onError = vi.fn()
    const onEnd = vi.fn()
    await expect(
      downloadBlobAsFile(async () => ({ data: '', headers: {} }) as any, { onError, onEnd })
    ).rejects.toThrow('下载失败：响应内容不是文件')
    expect(onError).toHaveBeenCalledTimes(1)
    expect(onEnd).toHaveBeenCalledTimes(1)
    // 未触发下载（不会在 URL.createObjectURL 上抛 TypeError）
    expect(createdObjectURLs).toHaveLength(0)
  })

  it('AxiosResponse.data 是 HTML 错误页 Blob 时判失败', async () => {
    const htmlBlob = new Blob(['<html>403</html>'], { type: 'text/html; charset=utf-8' })
    await expect(
      downloadBlobAsFile(async () => ({ data: htmlBlob, headers: {} }) as any)
    ).rejects.toThrow('下载失败：服务端返回了错误页面')
    expect(createdObjectURLs).toHaveLength(0)
  })

  it('下载文件名解析复用 request.parseContentDisposition（无回归）', async () => {
    const cd = "attachment; filename*=UTF-8''%E5%B8%AE%E6%89%B6.csv"
    expect(parseFileName(cd)).toBe('帮扶.csv')
    expect(parseFileName('attachment; filename=plain.txt')).toBe('plain.txt')
  })
})

// ─── getFileNameFromResponse 测试 ───

describe('getFileNameFromResponse', () => {
  it('从响应头解析文件名', () => {
    const response: Partial<AxiosResponse> = {
      headers: {
        'content-disposition': "attachment; filename*=UTF-8''%E6%95%B0%E6%8D%AE.xlsx",
      },
    }

    expect(getFileNameFromResponse(response as AxiosResponse, 'default.xlsx')).toBe('数据.xlsx')
  })

  it('无响应头时使用 fallback', () => {
    const response: Partial<AxiosResponse> = {
      headers: {},
    }

    expect(getFileNameFromResponse(response as AxiosResponse, 'default.xlsx')).toBe('default.xlsx')
  })

  it('headers 为 undefined 时使用 fallback', () => {
    const response: Partial<AxiosResponse> = {
      headers: undefined,
    }

    expect(getFileNameFromResponse(response as AxiosResponse, 'default.xlsx')).toBe('default.xlsx')
  })
})
