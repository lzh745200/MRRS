import { describe, it, expect, vi } from 'vitest'
import { md5 } from '@/utils/crypto'
import { escapeHtml } from '@/utils/sanitize'
import { format } from '@/utils/index'
import { parseError, ErrorType, createBusinessError } from '@/utils/errorHandler'

// ==================== crypto ====================
describe('crypto - md5', () => {
  it('返回8位十六进制字符串', () => {
    const result = md5('hello')
    expect(result).toMatch(/^[0-9a-f]{8,}$/)
  })

  it('相同输入产生相同输出', () => {
    expect(md5('test')).toBe(md5('test'))
  })

  it('不同输入产生不同输出', () => {
    expect(md5('abc')).not.toBe(md5('xyz'))
  })

  it('空字符串不报错', () => {
    expect(md5('')).toMatch(/^[0-9a-f]+$/)
  })
})

// ==================== sanitize ====================
describe('sanitize - escapeHtml', () => {
  it('转义 & < > " \'', () => {
    expect(escapeHtml('&<>"\'')).toBe('&amp;&lt;&gt;&quot;&#39;')
  })

  it('普通文本不变', () => {
    expect(escapeHtml('hello world')).toBe('hello world')
  })

  it('空字符串返回空', () => {
    expect(escapeHtml('')).toBe('')
  })

  it('null/undefined 返回空', () => {
    expect(escapeHtml(null as any)).toBe('')
    expect(escapeHtml(undefined as any)).toBe('')
  })
})

// ==================== format ====================
describe('format', () => {
  describe('formatDateTime', () => {
    it('格式化 Date 对象', () => {
      const d = new Date(2024, 0, 15, 10, 30, 45)
      expect(format.formatDateTime(d)).toBe('2024-01-15 10:30:45')
    })

    it('格式化字符串日期', () => {
      const result = format.formatDateTime('2024-06-01T08:00:00Z')
      expect(result).toMatch(/2024-06-01/)
    })

    it('无效日期返回原始字符串', () => {
      expect(format.formatDateTime('not-a-date')).toBe('not-a-date')
    })

    it('自定义格式', () => {
      const d = new Date(2024, 5, 15)
      expect(format.formatDateTime(d, 'YYYY-MM-DD')).toBe('2024-06-15')
    })
  })

  describe('formatDate', () => {
    it('返回 YYYY-MM-DD 格式', () => {
      const d = new Date(2024, 11, 25, 15, 30)
      expect(format.formatDate(d)).toBe('2024-12-25')
    })
  })

  describe('formatCurrency', () => {
    it('格式化货币值', () => {
      expect(format.formatCurrency(12345.678)).toMatch(/12.*345.*678.*元/)
    })

    it('自定义单位', () => {
      expect(format.formatCurrency(100, '万元')).toMatch(/100.*万元/)
    })
  })
})

// ==================== errorHandler ====================
describe('errorHandler - parseError', () => {
  it('解析 Axios response error', () => {
    const error = {
      response: { status: 401, data: { message: '未授权' } },
    }
    const result = parseError(error)
    expect(result.type).toBe(ErrorType.AUTH)
    expect(result.message).toBe('未授权')
    expect(result.code).toBe(401)
  })

  it('解析 404 错误', () => {
    const error = { response: { status: 404, data: {} } }
    const result = parseError(error)
    expect(result.type).toBe(ErrorType.NOT_FOUND)
  })

  it('解析 500 服务器错误', () => {
    const error = { response: { status: 500, data: { detail: '服务端异常' } } }
    const result = parseError(error)
    expect(result.type).toBe(ErrorType.SERVER)
    expect(result.message).toBe('服务端异常')
  })

  it('解析 422 验证错误', () => {
    const error = { response: { status: 422, data: {} } }
    expect(parseError(error).type).toBe(ErrorType.VALIDATION)
  })

  it('解析网络错误（有 request 无 response）', () => {
    const error = { request: {}, message: '网络异常' }
    const result = parseError(error)
    expect(result.type).toBe(ErrorType.NETWORK)
    expect(result.retryable).toBe(true)
  })

  it('解析超时错误', () => {
    const error = { request: {}, code: 'ECONNABORTED', message: 'timeout' }
    const result = parseError(error)
    expect(result.type).toBe(ErrorType.TIMEOUT)
  })

  it('解析业务错误', () => {
    const error = { code: 'BIZ_001', message: '余额不足' }
    const result = parseError(error)
    expect(result.type).toBe(ErrorType.BUSINESS)
    expect(result.code).toBe('BIZ_001')
  })

  it('解析 Error 对象', () => {
    const error = new Error('普通错误')
    const result = parseError(error)
    expect(result.type).toBe(ErrorType.UNKNOWN)
    expect(result.message).toBe('普通错误')
  })

  it('解析字符串错误', () => {
    const result = parseError('字符串错误')
    expect(result.type).toBe(ErrorType.UNKNOWN)
    expect(result.message).toBe('字符串错误')
  })

  it('解析 null/undefined', () => {
    expect(parseError(null).type).toBe(ErrorType.UNKNOWN)
    expect(parseError(undefined).message).toBe('未知错误')
  })
})

describe('errorHandler - createBusinessError', () => {
  it('创建业务错误对象', () => {
    const err = createBusinessError('FUND_001', '经费不足', { remaining: 0 })
    expect(err.type).toBe(ErrorType.BUSINESS)
    expect(err.code).toBe('FUND_001')
    expect(err.message).toBe('经费不足')
    expect(err.details).toEqual({ remaining: 0 })
    expect(err.retryable).toBe(false)
    expect(err.timestamp).toBeGreaterThan(0)
  })
})
