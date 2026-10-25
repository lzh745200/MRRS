/**
 * getErrorMessage 契约测试（2026-10-25 用户反馈 "Request failed with status code 422"）
 *
 * 核心契约：**任何**输入都不得让 axios 原文漏到用户面前。
 * 这条契约是全局兜底 —— 视图里 200+ 处错误提示都走它。
 */

import { describe, it, expect } from 'vitest'
import {
  extractServerMessage,
  getErrorMessage,
  isRawAxiosMessage,
  statusFallbackMessage,
} from '@/utils/getErrorMessage'

/** 构造一个"像 axios"的 4xx 错误 */
function axiosError(status: number, data?: any, message?: string) {
  return Object.assign(new Error(message ?? `Request failed with status code ${status}`), {
    response: { status, data },
    config: {},
    isAxiosError: true,
  })
}

describe('isRawAxiosMessage', () => {
  it.each([
    'Request failed with status code 422',
    'Request failed with status code 500',
    'Network Error',
    'timeout of 30000ms exceeded',
    'Failed to fetch',
  ])('识别技术原文: %s', (text) => {
    expect(isRawAxiosMessage(text)).toBe(true)
  })

  it.each(['权限不足', '用户名或密码错误', '请求参数有误，请检查填写内容后重试', ''])(
    '不误判正常文案: %s',
    (text) => {
      expect(isRawAxiosMessage(text)).toBe(false)
    }
  )

  it('非字符串一律 false', () => {
    expect(isRawAxiosMessage(undefined)).toBe(false)
    expect(isRawAxiosMessage(422)).toBe(false)
    expect(isRawAxiosMessage({ message: 'Request failed with status code 422' })).toBe(false)
  })
})

describe('statusFallbackMessage', () => {
  it.each([
    [400, '请求参数有误，请检查填写内容后重试'],
    [422, '请求参数有误，请检查填写内容后重试'],
    [401, '登录已过期，请重新登录'],
    [403, '权限不足，无法执行该操作'],
    [404, '请求的资源不存在或已被删除'],
    [409, '数据冲突，请刷新后重试'],
    [429, '操作过于频繁，请稍后再试'],
    [500, '服务器繁忙，请稍后重试'],
    [503, '服务器繁忙，请稍后重试'],
  ])('状态 %s → 中文兜底', (status, expected) => {
    expect(statusFallbackMessage(status)).toBe(expected)
  })

  it('未知/缺省状态返回空串（交由调用方 fallback）', () => {
    expect(statusFallbackMessage(418)).toBe('')
    expect(statusFallbackMessage(undefined)).toBe('')
  })
})

describe('extractServerMessage', () => {
  it('优先取 message 字符串', () => {
    expect(extractServerMessage(axiosError(400, { message: '用户名已存在' }))).toBe('用户名已存在')
  })

  it('message 缺失时取 detail 字符串', () => {
    expect(extractServerMessage(axiosError(400, { detail: '权限不足' }))).toBe('权限不足')
  })

  it('detail 是数组时拼接前两条 msg（历史 FastAPI 形态）', () => {
    const data = {
      detail: [
        { loc: ['body', 'username'], msg: 'String should have at least 3 characters' },
        { loc: ['body', 'password'], msg: 'Field required' },
        { loc: ['body', 'x'], msg: '第三条不应出现' },
      ],
    }
    expect(extractServerMessage(axiosError(422, data))).toBe(
      'String should have at least 3 characters；Field required'
    )
  })

  it('detail 数组里混入字符串也能读', () => {
    expect(extractServerMessage(axiosError(422, { detail: ['第一条', '第二条'] }))).toBe('第一条；第二条')
  })

  it('errors 数组（本仓库 422 信封）也能读', () => {
    const data = { errors: [{ msg: '密码不能为空' }, { msg: '用户名长度不能少于 3 个字符' }] }
    expect(extractServerMessage(axiosError(422, data))).toBe('密码不能为空；用户名长度不能少于 3 个字符')
  })

  it('嵌套 error.message 也能读', () => {
    expect(extractServerMessage(axiosError(500, { error: { message: '服务异常' } }))).toBe('服务异常')
  })

  it('纯文本响应体可读；HTML 不读', () => {
    expect(extractServerMessage(axiosError(500, '内部错误'))).toBe('内部错误')
    expect(extractServerMessage(axiosError(500, '<html>oops</html>'))).toBe('')
  })

  it('无响应体返回空串', () => {
    expect(extractServerMessage(new Error('boom'))).toBe('')
    expect(extractServerMessage(undefined)).toBe('')
  })
})

describe('getErrorMessage 核心契约', () => {
  it('【回归】422 无 detail 时绝不返回 axios 原文', () => {
    const err = axiosError(422, undefined)
    const msg = getErrorMessage(err, '保存失败')
    expect(msg).not.toContain('Request failed')
    expect(msg).toBe('请求参数有误，请检查填写内容后重试')
  })

  it('【回归】500 无响应体时绝不返回 axios 原文', () => {
    expect(getErrorMessage(axiosError(500))).toBe('服务器繁忙，请稍后重试')
  })

  it('【回归】任意状态的裸 axios 错误都不漏原文', () => {
    for (const status of [400, 401, 403, 404, 409, 418, 422, 429, 500, 503]) {
      const msg = getErrorMessage(axiosError(status), '兜底文案')
      expect(msg).not.toContain('Request failed')
      expect(msg.length).toBeGreaterThan(0)
    }
  })

  it('优先使用拦截器挂载的 userMessage', () => {
    const err = Object.assign(axiosError(422, { detail: '服务端 detail' }), { userMessage: '拦截器文案' })
    expect(getErrorMessage(err)).toBe('拦截器文案')
  })

  it('userMessage 是 axios 原文时被忽略（防拦截器漏改）', () => {
    const err = Object.assign(axiosError(422, undefined), {
      userMessage: 'Request failed with status code 422',
    })
    expect(getErrorMessage(err)).toBe('请求参数有误，请检查填写内容后重试')
  })

  it('服务端中文字符串 detail 直接采用（后端 422 已中文化）', () => {
    const err = axiosError(422, { message: '请求参数验证失败：密码不能为空', detail: '请求参数验证失败：密码不能为空' })
    expect(getErrorMessage(err)).toBe('请求参数验证失败：密码不能为空')
  })

  it('页面自己抛的业务 Error 保留原文', () => {
    expect(getErrorMessage(new Error('请先选择帮扶村'), '保存失败')).toBe('请先选择帮扶村')
  })

  it('超时 / 网络错误给中文提示', () => {
    expect(getErrorMessage(Object.assign(new Error('timeout'), { code: 'ECONNABORTED' }))).toBe(
      '请求超时，请检查网络后重试'
    )
    expect(getErrorMessage(Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK' }))).toBe(
      '网络连接失败，请检查网络后重试'
    )
  })

  it('无信息时用传入 fallback', () => {
    expect(getErrorMessage(undefined, '自定义兜底')).toBe('自定义兜底')
    expect(getErrorMessage(null, '自定义兜底')).toBe('自定义兜底')
    expect(getErrorMessage({}, '自定义兜底')).toBe('自定义兜底')
  })

  it('只有状态码、没有 message 时用状态码兜底', () => {
    // 真实形态：某些封装层 reject 一个裸对象（无 message / 无 code）
    expect(getErrorMessage({ response: { status: 503 } })).toBe('服务器繁忙，请稍后重试')
    expect(getErrorMessage({ status: 409 })).toBe('数据冲突，请刷新后重试')
  })

  it('状态码无对应文案时仍回落 fallback', () => {
    expect(getErrorMessage({ response: { status: 418 } }, '自定义兜底')).toBe('自定义兜底')
  })
})
