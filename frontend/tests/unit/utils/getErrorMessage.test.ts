import { describe, it, expect } from 'vitest'
import getErrorMessage, { getErrorMessage as named } from '@/utils/getErrorMessage'

describe('utils/getErrorMessage — 零依赖错误消息提取', () => {
  it('默认导出与命名导出为同一函数', () => {
    expect(getErrorMessage).toBe(named)
  })

  it('error 为空（null/undefined）→ 返回兜底文案', () => {
    expect(getErrorMessage(null)).toBe('操作失败')
    expect(getErrorMessage(undefined, '自定义兜底')).toBe('自定义兜底')
  })

  it('userMessage 非空字符串 → 优先返回', () => {
    expect(getErrorMessage({ userMessage: '权限不足' })).toBe('权限不足')
  })

  it('userMessage 为空字符串/非字符串 → 继续向下提取', () => {
    expect(
      getErrorMessage({ userMessage: '', response: { data: { detail: '服务端detail' } } })
    ).toBe('服务端detail')
    expect(
      getErrorMessage({ userMessage: 123, response: { data: { message: '服务端message' } } })
    ).toBe('服务端message')
  })

  it('detail 为空字符串 → 继续取 message 字段', () => {
    expect(getErrorMessage({ response: { data: { detail: '', message: 'm' } } })).toBe('m')
  })

  it('无服务端字段 → 取 error.message（Network Error 除外）', () => {
    expect(getErrorMessage(new Error('boom'))).toBe('boom')
    expect(getErrorMessage(new Error('Network Error'))).toBe('操作失败')
  })

  it('message 非字符串/为空 → 兜底', () => {
    expect(getErrorMessage({ message: 42 })).toBe('操作失败')
    expect(getErrorMessage({})).toBe('操作失败')
  })
})
