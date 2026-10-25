import { describe, it, expect } from 'vitest'
import getErrorMessage, {
  getErrorMessage as named,
  statusFallbackMessage,
} from '@/utils/getErrorMessage'

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
    expect(getErrorMessage(new Error('Network Error'))).toBe('网络连接失败，请检查网络后重试')
  })

  it('message 非字符串/为空 → 兜底', () => {
    expect(getErrorMessage({ message: 42 })).toBe('操作失败')
    expect(getErrorMessage({})).toBe('操作失败')
  })
})

/**
 * statusFallbackMessage 是全站"服务端没给可读文案时"的唯一兜底出口
 * （request.ts 的 _buildUserMessage 也复用它）。e11d27c 一次补齐了
 * 405/408/504/409/413/429 与 5xx 分支，但当时没有配套用例 ——
 * 覆盖率门禁因此在这一段跌穿 100%。本组用例逐个状态码钉死文案，
 * 同时守住"不认识的 4xx 返回空串、由调用方决定最终兜底"的契约。
 */
describe('utils/getErrorMessage — statusFallbackMessage 全分支', () => {
  it.each([
    [400, '请求参数有误，请检查填写内容后重试'],
    [422, '请求参数有误，请检查填写内容后重试'],
    [401, '登录已过期，请重新登录'],
    [403, '权限不足，无法执行该操作'],
    [404, '请求的资源不存在或已被删除'],
    [405, '该操作不被支持'],
    [408, '请求超时，请稍后重试'],
    [504, '请求超时，请稍后重试'],
    [409, '数据冲突，请刷新后重试'],
    [413, '提交内容过大，请减小后重试'],
    [429, '操作过于频繁，请稍后再试'],
  ])('状态码 %i → %s', (status, expected) => {
    expect(statusFallbackMessage(status)).toBe(expected)
  })

  it('5xx（未单列的）→ 服务器繁忙', () => {
    expect(statusFallbackMessage(500)).toBe('服务器繁忙，请稍后重试')
    expect(statusFallbackMessage(502)).toBe('服务器繁忙，请稍后重试')
    expect(statusFallbackMessage(503)).toBe('服务器繁忙，请稍后重试')
  })

  it('未登记的 4xx → 空串（交给调用方兜底，不臆造文案）', () => {
    expect(statusFallbackMessage(418)).toBe('')
    expect(statusFallbackMessage(451)).toBe('')
  })

  it('非数字 / 缺失状态码 → 空串', () => {
    expect(statusFallbackMessage(undefined)).toBe('')
    expect(statusFallbackMessage(null)).toBe('')
    expect(statusFallbackMessage('500')).toBe('')
    expect(statusFallbackMessage(NaN)).toBe('')
  })

  it('axios 原文 + 已知状态码 → 用状态码文案（绝不下发技术原文）', () => {
    expect(
      getErrorMessage({
        message: 'Request failed with status code 405',
        response: { status: 405 },
      })
    ).toBe('该操作不被支持')
    // 408 走的是"原始文案 + 状态码"分支里的 timeout 前置判断，同样不得下发原文
    expect(
      getErrorMessage({
        message: 'Request failed with status code 413',
        response: { status: 413 },
      })
    ).toBe('提交内容过大，请减小后重试')
  })

  it('响应体直接是数组 → 走 detail 数组提取（FastAPI 历史形态）', () => {
    expect(getErrorMessage({ response: { data: [{ msg: '字段必填' }] } })).toBe('字段必填')
    // 数组里全是无法提取的项 → 空串，继续向下兜底
    expect(getErrorMessage({ response: { data: [] } })).toBe('操作失败')
    expect(getErrorMessage({ response: { data: [123, null] } })).toBe('操作失败')
  })

  it('未登记状态码且无可用原文 → 回落到调用方 fallback（不臆造文案）', () => {
    // 157 行不命中（无 message），151 行不命中（非网络错误）→ byStatus 为空 → fallback
    expect(getErrorMessage({ response: { status: 418 } }, '自定义兜底')).toBe('自定义兜底')
    expect(getErrorMessage({ response: { status: 451 } })).toBe('操作失败')
  })
})
