import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const { loggerMock, notifyMock, elMessageMock } = vi.hoisted(() => {
  const msg = vi.fn((opts: any) => opts)
  msg.success = vi.fn((opts: any) => opts)
  msg.warning = vi.fn((opts: any) => opts)
  msg.error = vi.fn((opts: any) => opts)
  msg.info = vi.fn((opts: any) => opts)
  return {
    loggerMock: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
    notifyMock: vi.fn(),
    elMessageMock: msg,
  }
})

vi.mock('@/utils/logger', () => ({ logger: loggerMock }))
vi.mock('element-plus', () => ({ ElMessage: elMessageMock }))
vi.mock('@/utils/notify', () => ({ notify: notifyMock }))

import {
  ErrorType,
  parseError,
  handleError,
  createBusinessError,
  errorHandler,
  handleApiError,
  handleDeleteError,
  handleSaveError,
  handleLoadError,
  handleExportError,
  handleImportError,
  setupGlobalErrorHandler,
  default as errorHandlerDefault,
} from '@/utils/errorHandler'
import { getEventBus } from '@/composables/useEventBus'

const resp = (status: number, data: any = {}) => ({ response: { status, data } })

describe('utils/errorHandler', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('parseError — HTTP 状态码映射', () => {
    it.each([
      [400, ErrorType.VALIDATION],
      [422, ErrorType.VALIDATION],
      [401, ErrorType.AUTH],
      [403, ErrorType.PERMISSION],
      [404, ErrorType.NOT_FOUND],
      [408, ErrorType.TIMEOUT],
      [504, ErrorType.TIMEOUT],
      [500, ErrorType.SERVER],
      [599, ErrorType.SERVER],
      [302, ErrorType.UNKNOWN],
    ])('状态码 %s → %s', (status, type) => {
      const appError = parseError(resp(status))
      expect(appError.type).toBe(type)
      expect(appError.code).toBe(status)
      expect(appError.timestamp).toBeGreaterThan(0)
    })
  })

  describe('parseError — 响应消息提取', () => {
    it('优先取 data.message', () => {
      const appError = parseError(resp(400, { message: '参数错误' }))
      expect(appError.message).toBe('参数错误')
    })

    it('其次取 data.detail', () => {
      const appError = parseError(resp(400, { detail: '明细错误' }))
      expect(appError.message).toBe('明细错误')
    })

    it('再次取 data.error.message', () => {
      const appError = parseError(resp(400, { error: { message: '嵌套错误' } }))
      expect(appError.message).toBe('嵌套错误')
    })

    it('全部缺失时用 "请求失败 (status)"', () => {
      const appError = parseError(resp(404, {}))
      expect(appError.message).toBe('请求失败 (404)')
    })

    it('message 非字符串时回退 "请求失败 (status)"', () => {
      const appError = parseError(resp(400, { message: 12345 }))
      expect(appError.message).toBe('请求失败 (400)')
    })

    it('VALIDATION 类型 retryable=false', () => {
      expect(parseError(resp(422)).retryable).toBe(false)
    })

    it('SERVER 类型 retryable=true', () => {
      expect(parseError(resp(500)).retryable).toBe(true)
    })
  })

  describe('parseError — 请求层错误', () => {
    it('ECONNABORTED → TIMEOUT', () => {
      const appError = parseError({ request: {}, code: 'ECONNABORTED', message: '连接中断' })
      expect(appError.type).toBe(ErrorType.TIMEOUT)
      expect(appError.message).toBe('连接中断')
      expect(appError.retryable).toBe(true)
    })

    it('ECONNABORTED 无 message → 请求超时兜底', () => {
      const appError = parseError({ request: {}, code: 'ECONNABORTED' })
      expect(appError.type).toBe(ErrorType.TIMEOUT)
      expect(appError.message).toBe('请求超时')
    })

    it('message 含 timeout → TIMEOUT', () => {
      const appError = parseError({ request: {}, message: 'timeout of 5000ms exceeded' })
      expect(appError.type).toBe(ErrorType.TIMEOUT)
    })

    it('无 message 的请求错误 → 默认网络文案', () => {
      const appError = parseError({ request: {} })
      expect(appError.type).toBe(ErrorType.NETWORK)
      expect(appError.message).toBe('网络连接失败')
    })

    it('带 code 的请求错误 → NETWORK', () => {
      const appError = parseError({ request: {}, code: 'ERR_NETWORK', message: 'x' })
      expect(appError.type).toBe(ErrorType.NETWORK)
      expect(appError.code).toBe('ERR_NETWORK')
    })
  })

  describe('parseError — 业务与兜底', () => {
    it('字符串 code → BUSINESS 并携带 details', () => {
      const appError = parseError({ code: 'FUND-001', message: '额度不足', details: { id: 7 } })
      expect(appError.type).toBe(ErrorType.BUSINESS)
      expect(appError.code).toBe('FUND-001')
      expect(appError.details).toEqual({ id: 7 })
      expect(appError.retryable).toBe(false)
    })

    it('业务错误无 message → 业务错误兜底', () => {
      const appError = parseError({ code: 'FUND-002' })
      expect(appError.type).toBe(ErrorType.BUSINESS)
      expect(appError.message).toBe('业务错误')
    })

    it('数字 code 不命中业务分支', () => {
      const appError = parseError({ code: 123, message: 'm' })
      expect(appError.type).toBe(ErrorType.UNKNOWN)
      expect(appError.message).toBe('m')
    })

    it('ECONNABORTED code 不命中业务分支', () => {
      const appError = parseError({ code: 'ECONNABORTED', message: 'x' })
      expect(appError.type).toBe(ErrorType.UNKNOWN)
      expect(appError.message).toBe('x')
    })

    it('Error 实例 → UNKNOWN 带其 message', () => {
      const appError = parseError(new Error('boom'))
      expect(appError.type).toBe(ErrorType.UNKNOWN)
      expect(appError.message).toBe('boom')
    })

    it('含 message 的普通对象 → UNKNOWN', () => {
      const appError = parseError({ message: 'plain' })
      expect(appError.type).toBe(ErrorType.UNKNOWN)
      expect(appError.message).toBe('plain')
    })

    it('字符串错误 → UNKNOWN', () => {
      const appError = parseError('字符串错误')
      expect(appError.type).toBe(ErrorType.UNKNOWN)
      expect(appError.message).toBe('字符串错误')
    })

    it('null/undefined → UNKNOWN 未知错误', () => {
      expect(parseError(null).message).toBe('未知错误')
      expect(parseError(undefined).message).toBe('未知错误')
    })

    it('falsy 非空值 → String 化', () => {
      expect(parseError(0).message).toBe('0')
      expect(parseError(false).message).toBe('false')
    })
  })

  describe('handleError', () => {
    it('NETWORK 走通知并记录日志', () => {
      const appError = handleError(resp(500))
      expect(notifyMock).toHaveBeenCalledWith({
        type: 'error',
        title: '错误',
        message: appError.message,
      })
      expect(loggerMock.error).toHaveBeenCalledWith('[Error]', appError)
    })

    it('VALIDATION 走 ElMessage.warning 且不记录日志', () => {
      const appError = handleError(resp(400, { message: '校验失败' }))
      expect(elMessageMock.warning).toHaveBeenCalledWith('校验失败')
      expect(notifyMock).not.toHaveBeenCalled()
      expect(loggerMock.error).not.toHaveBeenCalled()
      expect(appError.type).toBe(ErrorType.VALIDATION)
    })

    it('showMessage=false 时抑制提示', () => {
      handleError(resp(400), false)
      expect(elMessageMock.warning).not.toHaveBeenCalled()
      expect(notifyMock).not.toHaveBeenCalled()
    })

    it('策略 shouldNotify=false 时即使 showMessage 也不提示', () => {
      errorHandler.configureStrategy(ErrorType.VALIDATION, { shouldNotify: false })
      handleError(resp(400), true)
      expect(elMessageMock.warning).not.toHaveBeenCalled()
      errorHandler.configureStrategy(ErrorType.VALIDATION, { shouldNotify: true })
      handleError(resp(400), true)
      expect(elMessageMock.warning).toHaveBeenCalledTimes(1)
    })

    it('按错误类型发布事件总线事件', () => {
      const handler = vi.fn()
      getEventBus().on('error:network', handler)
      handleError({ request: {} })
      expect(handler).toHaveBeenCalledTimes(1)
      expect(handler.mock.calls[0][0].type).toBe(ErrorType.NETWORK)
    })

    it('AUTH 发布 auth:expired 事件', () => {
      const handler = vi.fn()
      getEventBus().on('auth:expired', handler)
      handleError(resp(401))
      expect(handler).toHaveBeenCalledTimes(1)
    })
  })

  describe('createBusinessError', () => {
    it('构造业务错误对象', () => {
      const err = createBusinessError('B-1', '业务失败', { a: 1 })
      expect(err).toMatchObject({
        type: ErrorType.BUSINESS,
        code: 'B-1',
        message: '业务失败',
        details: { a: 1 },
        retryable: false,
      })
      expect(err.timestamp).toBeGreaterThan(0)
    })

    it('details 可省略', () => {
      const err = createBusinessError('B-2', 'm')
      expect(err.details).toBeUndefined()
    })
  })

  describe('errorHandler 实例', () => {
    it('getStrategy 返回默认策略（AUTH 含重定向）', () => {
      const strategy = errorHandler.getStrategy(ErrorType.AUTH)
      expect(strategy.redirectPath).toBe('/login')
      expect(strategy.shouldRedirect).toBe(true)
      expect(strategy.notificationType).toBe('message')
    })

    it('configureStrategy 与默认策略合并覆盖', () => {
      errorHandler.configureStrategy(ErrorType.AUTH, { severity: 'error' })
      const strategy = errorHandler.getStrategy(ErrorType.AUTH)
      expect(strategy.severity).toBe('error')
      expect(strategy.redirectPath).toBe('/login')
      errorHandler.configureStrategy(ErrorType.AUTH, { severity: 'warning' })
    })

    it('configureStrategy 多次调用逐层合并', () => {
      errorHandler.configureStrategy(ErrorType.TIMEOUT, { retryable: false })
      errorHandler.configureStrategy(ErrorType.TIMEOUT, { shouldNotify: false })
      const strategy = errorHandler.getStrategy(ErrorType.TIMEOUT)
      expect(strategy.retryable).toBe(false)
      expect(strategy.shouldNotify).toBe(false)
      expect(strategy.shouldLog).toBe(true)
      errorHandler.configureStrategy(ErrorType.TIMEOUT, { retryable: true, shouldNotify: true })
    })

    it('handleAsyncOperation 成功且无 successMessage', async () => {
      const result = await errorHandler.handleAsyncOperation(async () => 42)
      expect(result).toBe(42)
      expect(elMessageMock.success).not.toHaveBeenCalled()
    })

    it('handleAsyncOperation 成功展示成功提示', async () => {
      const result = await errorHandler.handleAsyncOperation(async () => 'ok', {
        successMessage: '保存成功',
      })
      expect(result).toBe('ok')
      expect(elMessageMock.success).toHaveBeenCalledWith('保存成功')
    })

    it('handleAsyncOperation 失败无重试 → 展示错误并返回 null', async () => {
      const error = resp(400)
      const result = await errorHandler.handleAsyncOperation(async () => {
        throw error
      })
      expect(result).toBeNull()
      expect(elMessageMock.warning).toHaveBeenCalled()
    })

    it('handleAsyncOperation 默认参数分支（showError 默认 true）', async () => {
      const result = await errorHandler.handleAsyncOperation(async () => {
        throw resp(500)
      })
      expect(result).toBeNull()
      expect(notifyMock).toHaveBeenCalled()
    })

    it('handleAsyncOperation 重试一次后成功并回调 onRetry', async () => {
      let calls = 0
      const onRetry = vi.fn()
      const result = await errorHandler.handleAsyncOperation(
        async () => {
          calls++
          if (calls === 1) throw new Error('first fail')
          return 'done'
        },
        { retryCount: 1, retryDelay: 0, onRetry }
      )
      expect(result).toBe('done')
      expect(onRetry).toHaveBeenCalledWith(1, expect.any(Error))
    })

    it('handleAsyncOperation 重试耗尽失败 → 返回 null', async () => {
      const onRetry = vi.fn()
      const result = await errorHandler.handleAsyncOperation(
        async () => {
          throw resp(400)
        },
        { retryCount: 1, retryDelay: 0, onRetry }
      )
      expect(result).toBeNull()
      expect(onRetry).toHaveBeenCalledTimes(1)
      expect(elMessageMock.warning).toHaveBeenCalled()
    })

    it('handleAsyncOperation showError=false 时不提示错误', async () => {
      const result = await errorHandler.handleAsyncOperation(
        async () => {
          throw resp(400)
        },
        { retryCount: 1, retryDelay: 0, showError: false }
      )
      expect(result).toBeNull()
      expect(elMessageMock.warning).not.toHaveBeenCalled()
      expect(notifyMock).not.toHaveBeenCalled()
    })
  })

  describe('handleApiError 与便捷方法', () => {
    it("error === 'cancel' 视为用户取消", () => {
      expect(handleApiError('cancel')).toBe(true)
      expect(elMessageMock.warning).not.toHaveBeenCalled()
    })

    it("error.message === 'cancel' 视为用户取消", () => {
      expect(handleApiError({ message: 'cancel' })).toBe(true)
    })

    it('普通错误 → 处理并返回 false', () => {
      expect(handleApiError({ message: '普通错误' })).toBe(false)
      expect(elMessageMock.warning).toHaveBeenCalledWith('普通错误')
    })

    it.each([
      [handleDeleteError, '删除失败'],
      [handleSaveError, '保存失败'],
      [handleLoadError, '加载失败'],
      [handleExportError, '导出失败'],
      [handleImportError, '导入失败'],
    ])('便捷方法委托 handleApiError（%s）', (fn, label) => {
      expect(fn({ message: '触发' })).toBe(false)
      expect(elMessageMock.warning).toHaveBeenLastCalledWith('触发')
      expect(label).toBeTruthy()
    })
  })

  describe('setupGlobalErrorHandler', () => {
    afterEach(() => {
      vi.restoreAllMocks()
    })

    it('忽略动态导入 ChunkLoadError', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      setupGlobalErrorHandler()
      const result = window.onerror!(
        'Failed to fetch dynamically imported module: /assets/x.js',
        'src/a.js',
        1,
        2,
        new Error('chunk')
      )
      expect(result).toBe(false)
      expect(consoleErrorSpy).not.toHaveBeenCalled()
    })

    it('忽略 ResizeObserver 警告', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      setupGlobalErrorHandler()
      window.onerror!('ResizeObserver loop limit exceeded', 'src/b.js', 1, 2, null)
      expect(consoleErrorSpy).not.toHaveBeenCalled()
    })

    it('普通同步错误记录 console.error（Error 实例提取 message）', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      setupGlobalErrorHandler()
      const result = window.onerror!('普通错误', 'src/c.js', 3, 4, new Error('detail-msg'))
      expect(result).toBe(false)
      expect(consoleErrorSpy).toHaveBeenCalledWith('[GlobalError]', {
        message: '普通错误',
        source: 'src/c.js',
        line: 3,
        col: 4,
        error: 'detail-msg',
      })
    })

    it('非字符串 message 也会被 String 化记录', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      setupGlobalErrorHandler()
      window.onerror!(12345 as any, 'src/d.js', 1, 1, null)
      expect(consoleErrorSpy).toHaveBeenCalledWith('[GlobalError]', expect.objectContaining({ message: '12345' }))
    })

    it('unhandledrejection：ChunkLoadError 仅告警', () => {
      const addSpy = vi.spyOn(window, 'addEventListener')
      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      setupGlobalErrorHandler()
      const handler = addSpy.mock.calls.find(([t]) => t === 'unhandledrejection')![1] as any
      const event = { reason: { message: 'Failed to fetch dynamically imported module x' }, preventDefault: vi.fn() }
      handler(event)
      expect(consoleWarnSpy).toHaveBeenCalledWith('[UnhandledRejection] ChunkLoadError:', 'Failed to fetch dynamically imported module x')
      expect(event.preventDefault).toHaveBeenCalled()
    })

    it('unhandledrejection：401 响应告警 token 过期', () => {
      const addSpy = vi.spyOn(window, 'addEventListener')
      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      setupGlobalErrorHandler()
      const handler = addSpy.mock.calls.find(([t]) => t === 'unhandledrejection')![1] as any
      const event = { reason: { response: { status: 401 } }, preventDefault: vi.fn() }
      handler(event)
      expect(consoleWarnSpy).toHaveBeenCalledWith('[UnhandledRejection] 401 — token may be expired')
      expect(event.preventDefault).toHaveBeenCalled()
    })

    it('unhandledrejection：其他拒绝交给 logger.error', () => {
      const addSpy = vi.spyOn(window, 'addEventListener')
      setupGlobalErrorHandler()
      const handler = addSpy.mock.calls.find(([t]) => t === 'unhandledrejection')![1] as any
      const event = { reason: { message: 'boom' }, preventDefault: vi.fn() }
      handler(event)
      expect(loggerMock.error).toHaveBeenCalledWith('[Unhandled Promise Rejection]', { message: 'boom' })
      expect(event.preventDefault).toHaveBeenCalled()
    })

    it('unhandledrejection：reason 为空时也拦截并记录', () => {
      const addSpy = vi.spyOn(window, 'addEventListener')
      setupGlobalErrorHandler()
      const handler = addSpy.mock.calls.find(([t]) => t === 'unhandledrejection')![1] as any
      const event = { reason: undefined, preventDefault: vi.fn() }
      handler(event)
      expect(loggerMock.error).toHaveBeenCalledWith('[Unhandled Promise Rejection]', undefined)
      expect(event.preventDefault).toHaveBeenCalled()
    })
  })

  describe('默认导出', () => {
    it('聚合导出全部工具', () => {
      expect(errorHandlerDefault.handleError).toBe(handleError)
      expect(errorHandlerDefault.errorHandler).toBe(errorHandler)
      expect(errorHandlerDefault.setupGlobalErrorHandler).toBe(setupGlobalErrorHandler)
      expect(errorHandlerDefault.handleApiError).toBe(handleApiError)
      expect(errorHandlerDefault.handleDeleteError).toBe(handleDeleteError)
      expect(errorHandlerDefault.handleSaveError).toBe(handleSaveError)
      expect(errorHandlerDefault.handleLoadError).toBe(handleLoadError)
      expect(errorHandlerDefault.handleExportError).toBe(handleExportError)
      expect(errorHandlerDefault.handleImportError).toBe(handleImportError)
    })
  })
})


describe('setupGlobalErrorHandler — unhandledrejection 兜底与去重', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  function captureRejectionHandler(): any {
    let captured: any = null
    const spy = vi
      .spyOn(window, 'addEventListener')
      .mockImplementation((type: any, fn: any) => {
        if (type === 'unhandledrejection') captured = fn
      })
    setupGlobalErrorHandler()
    spy.mockRestore()
    return captured
  }

  it('__silent / __CANCEL__ / ERR_CANCELED → 仅 preventDefault 不提示', () => {
    const handler = captureRejectionHandler()
    for (const reason of [{ __silent: true }, { __CANCEL__: true }, { code: 'ERR_CANCELED' }]) {
      const preventDefault = vi.fn()
      handler({ reason, preventDefault })
      expect(preventDefault).toHaveBeenCalled()
    }
    expect(elMessageMock).not.toHaveBeenCalled()
  })

  it('userMessage 存在 → 单条兜底提示；同类消息 2s 窗口内去重', () => {
    const handler = captureRejectionHandler()
    const evt = () => ({ reason: { userMessage: '权限不足-dedupe' }, preventDefault: vi.fn() })
    handler(evt())
    handler(evt())
    expect(elMessageMock).toHaveBeenCalledTimes(1)
    expect(elMessageMock).toHaveBeenCalledWith({
      message: '权限不足-dedupe',
      type: 'error',
      grouping: true,
    })
    // 不同消息不去重
    handler({ reason: { userMessage: '网络超时-diff' }, preventDefault: vi.fn() })
    expect(elMessageMock).toHaveBeenCalledTimes(2)
  })

  it('无 userMessage 的 HTTP/网络错误 → 通用提示', () => {
    const handler = captureRejectionHandler()
    for (const reason of [
      { response: { status: 500 } },
      { request: {} },
      { code: 'ERR_NETWORK' },
      { code: 'ECONNABORTED' },
    ]) {
      handler({ reason, preventDefault: vi.fn() })
    }
    // 4 次均为同一通用文案，但去重窗口内只提示 1 次
    expect(elMessageMock).toHaveBeenCalledWith({
      message: '请求失败，请稍后重试',
      type: 'error',
      grouping: true,
    })
  })

  it('ChunkLoadError 与 401 → 仅记录日志不提示', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const handler = captureRejectionHandler()
    handler({
      reason: { message: 'Failed to fetch dynamically imported module' },
      preventDefault: vi.fn(),
    })
    handler({ reason: { response: { status: 401 } }, preventDefault: vi.fn() })
    expect(warnSpy).toHaveBeenCalledTimes(2)
    expect(elMessageMock).not.toHaveBeenCalled()
    warnSpy.mockRestore()
  })

  it('其他未识别 rejection → logger.error 记录', () => {
    const handler = captureRejectionHandler()
    const reason = new Error('boom-unclassified')
    const preventDefault = vi.fn()
    handler({ reason, preventDefault })
    expect(loggerMock.error).toHaveBeenCalledWith('[Unhandled Promise Rejection]', reason)
    expect(preventDefault).toHaveBeenCalled()
  })
})
