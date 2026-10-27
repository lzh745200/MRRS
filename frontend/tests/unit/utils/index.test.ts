/**
 * utils/index.ts 统一导出测试
 * 覆盖：logger/request/exportUtil/copyToClipboard 四个 re-export + format 工具集全部分支
 *
 * 说明：dataManagement/Index.vue 的视图测试已收敛到
 * tests/unit/views/dataManagement/Index.test.ts —— 同一被覆盖率门槛锁定的 .vue
 * 只允许一个测试文件执行，避免全量覆盖率按 id 合并 fnMap 时互相污染。
 */
const { mockRequest } = vi.hoisted(() => ({ mockRequest: vi.fn() }))

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('@/api/request', () => ({
  default: mockRequest,
  get: vi.fn(),
  apiRequest: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

/**
 * utils/index.ts 统一导出（与上方 Index.vue 视图测试同名文件共存）
 * 覆盖：logger/request/exportUtil/copyToClipboard 四个 re-export + format 工具集全部分支
 */
import { logger, request, exportUtil, copyToClipboard, format } from '@/utils/index'

describe('utils/index.ts 统一导出', () => {
  describe('format.formatDateTime', () => {
    it('默认 fmt YYYY-MM-DD HH:mm:ss（本地时区）', () => {
      const d = new Date(2024, 0, 5, 9, 8, 7)
      expect(format.formatDateTime(d)).toBe('2024-01-05 09:08:07')
    })

    it('字符串日期 + 自定义 fmt', () => {
      expect(format.formatDateTime('2024-05-01T10:30:00', 'YYYY/MM/DD HH:mm')).toBe(
        '2024/05/01 10:30'
      )
    })

    it('非法日期返回原值', () => {
      expect(format.formatDateTime('not-a-date')).toBe('not-a-date')
      const invalid = new Date('invalid')
      expect(format.formatDateTime(invalid)).toBe(String(invalid))
    })

    // 守卫与兄弟函数（formatDateTimeLocale / formatDate / formatDateTimeFull）对齐：
    // 原实现遇到 null/undefined 会走 d.getTime() 抛 TypeError（渲染期整页崩溃）。
    it('null / undefined / 空串回退 "-" 而不抛 TypeError', () => {
      expect(format.formatDateTime(null as any)).toBe('-')
      expect(format.formatDateTime(undefined as any)).toBe('-')
      expect(format.formatDateTime('' as any)).toBe('-')
    })
  })

  describe('format.formatDateTimeLocale', () => {
    it('空值/非法日期返回 -', () => {
      expect(format.formatDateTimeLocale('' as any)).toBe('-')
      expect(format.formatDateTimeLocale(null as any)).toBe('-')
      expect(format.formatDateTimeLocale(undefined as any)).toBe('-')
      expect(format.formatDateTimeLocale('bad-date')).toBe('-')
    })

    it('合法日期按 zh-CN locale 格式化', () => {
      const r = format.formatDateTimeLocale(new Date(2024, 0, 5, 9, 8, 7))
      expect(r.length).toBeGreaterThan(0)
      expect(r).toContain('2024')
    })
  })

  describe('format.formatDate / formatDateTimeFull', () => {
    it('空值返回 -', () => {
      expect(format.formatDate(null as any)).toBe('-')
      expect(format.formatDateTimeFull(null as any)).toBe('-')
    })

    it('日期格式化', () => {
      const d = new Date(2024, 0, 5)
      expect(format.formatDate(d)).toBe('2024-01-05')
      expect(format.formatDateTimeFull(d)).toBe('2024-01-05 00:00:00')
    })
  })

  // 2026-10-03：把各页面自行实现的日期格式化统一收敛到 utils/index.ts，
  // 以下用例锁定新增变体的行为（空值兜底、格式形状、分支全覆盖）。
  describe('format 统一补齐的日期时间变体', () => {
    const d = new Date(2024, 0, 5, 9, 8, 7) // 本地 2024-01-05 09:08:07

    it('formatLocalDate：zh-CN 仅日期；空值/非法走兜底文案', () => {
      expect(format.formatLocalDate(d)).toBe('2024/1/5')
      expect(format.formatLocalDate(null)).toBe('-')
      expect(format.formatLocalDate('bad-date', '无')).toBe('无')
      expect(format.formatLocalDate(undefined, '')).toBe('')
    })

    it('formatLocalDate2Digit：两位补零', () => {
      expect(format.formatLocalDate2Digit(d)).toBe('2024/01/05')
      expect(format.formatLocalDate2Digit('bad-date')).toBe('-')
      expect(format.formatLocalDate2Digit('', 'N/A')).toBe('N/A')
    })

    it('formatLocalDateTime2Digit：补零日期时间', () => {
      expect(format.formatLocalDateTime2Digit(d)).toBe('2024/01/05 09:08:07')
      expect(format.formatLocalDateTime2Digit('bad-date', '--')).toBe('--')
    })

    it('formatCnDate：中文长日期 + 星期', () => {
      expect(format.formatCnDate(new Date(2024, 0, 5))).toBe('2024年1月5日 周五')
      expect(format.formatCnDate('bad-date')).toBe('-')
      expect(format.formatCnDate(null, '未知')).toBe('未知')
    })

    it('formatRelativeTime：刚刚 / 分钟前 / 小时前 / 更早显示短日期时间', () => {
      const now = Date.now()
      expect(format.formatRelativeTime(new Date(now - 10 * 1000))).toBe('刚刚')
      expect(format.formatRelativeTime(new Date(now - 5 * 60000))).toBe('5分钟前')
      expect(format.formatRelativeTime(new Date(now - 3 * 3600000))).toBe('3小时前')
      // 天级档（来自 src/api/message.ts 原实现的能力并集）
      expect(format.formatRelativeTime(new Date(now - 2 * 86400000))).toBe('2天前')
      const older = new Date(2020, 9, 2, 20, 3)
      expect(format.formatRelativeTime(older)).toBe('10月2日 20:03')
      expect(format.formatRelativeTime(null)).toBe('--:--')
      expect(format.formatRelativeTime('bad-date', '-')).toBe('-')
    })

    it('formatShortDateTime / formatShortDateTimePadded：短日期时间', () => {
      expect(format.formatShortDateTime(d)).toBe('1/5 9:08')
      expect(format.formatShortDateTime('bad-date')).toBe('')
      expect(format.formatShortDateTimePadded(d)).toBe('01-05 09:08')
      expect(format.formatShortDateTimePadded(undefined, '-')).toBe('-')
    })

    it('formatDuration：天 / 小时 / 分钟三档 + 空值文案可配', () => {
      expect(format.formatDuration(90061)).toBe('1 天 1 小时')
      expect(format.formatDuration(3720)).toBe('1 小时 2 分钟')
      expect(format.formatDuration(125)).toBe('2 分钟')
      expect(format.formatDuration(0)).toBe('-')
      expect(format.formatDuration(-5)).toBe('-')
      expect(format.formatDuration(null)).toBe('-')
      expect(format.formatDuration(undefined, '未知')).toBe('未知')
      expect(format.formatDuration(Number.NaN)).toBe('-')
    })

    it('统一入口接受 Date 实例与数字时间戳（toDate 各分支）', () => {
      const ts = d.getTime()
      expect(format.formatDateTimeLocale(d)).toBe(d.toLocaleString('zh-CN'))
      expect(format.formatDateTimeLocale(ts)).toBe(d.toLocaleString('zh-CN'))
      expect(format.formatLocalDate(ts)).toBe('2024/1/5')
    })

    // 收敛前各页面自带 try/catch（`new Date()` 与 `toLocaleString()` 都可能抛错），
    // 统一实现必须保留同等韧性，否则等于"越改越脆"。
    it('极端输入与宿主 locale 异常都不抛错（双层兜底）', () => {
      // ① toDate 内部 try/catch：Symbol 会让 new Date() 直接抛 TypeError
      expect(format.formatDateTimeLocale(Symbol('x') as unknown as string)).toBe('-')
      expect(format.formatDateTimeLocale(Symbol('x') as unknown as string, 'N/A')).toBe('N/A')
      expect(format.formatDate(Symbol('x') as unknown as string, '无')).toBe('无')

      // ② localeFormat 内部 try/catch：toLocaleString/toLocaleDateString 抛错 → 回退文案
      const origDateTime = Date.prototype.toLocaleString
      const origDate = Date.prototype.toLocaleDateString
      Date.prototype.toLocaleString = () => {
        throw new Error('boom')
      }
      Date.prototype.toLocaleDateString = () => {
        throw new Error('boom')
      }
      try {
        const valid = new Date(2024, 0, 5, 9, 8, 7)
        expect(format.formatDateTimeLocale(valid)).toBe('-')
        expect(format.formatLocalDate(valid)).toBe('-')
        expect(format.formatLocalDate2Digit(valid, '无')).toBe('无')
        expect(format.formatLocalDateTime2Digit(valid, '--')).toBe('--')
        // 相对时间的"更早"分支同样走 locale，异常时回退
        expect(format.formatRelativeTime(new Date(2020, 9, 2, 20, 3), 'X')).toBe('X')
      } finally {
        Date.prototype.toLocaleString = origDateTime
        Date.prototype.toLocaleDateString = origDate
      }
    })
  })

  // 2026-10-03：各页面空值文案不一（`-` / ``/ `无` / `N/A` / `--`），
  // 为此给核心函数加可选 fallback；不传时保持历史行为不变。
  describe('format 兜底文案参数（fallback）', () => {
    it('formatDateTime：传 fallback 时空值与非法值都用它', () => {
      expect(format.formatDateTime(null, 'YYYY-MM-DD', '-')).toBe('-')
      expect(format.formatDateTime('bad-date', 'YYYY-MM-DD', '-')).toBe('-')
      expect(format.formatDateTime(new Date(2024, 0, 5), 'YYYY-MM-DD', '-')).toBe('2024-01-05')
    })

    it('formatDateTime：不传 fallback 时保持历史行为（空值 - / 非法值原样回显）', () => {
      expect(format.formatDateTime(null)).toBe('-')
      expect(format.formatDateTime('bad-date', 'YYYY-MM-DD')).toBe('bad-date')
    })

    it('formatDate / formatDateTimeFull：支持自定义兜底', () => {
      expect(format.formatDate(new Date(2024, 0, 5), '无')).toBe('2024-01-05')
      expect(format.formatDate(null, '无')).toBe('无')
      expect(format.formatDateTimeFull('bad-date', '')).toBe('')
      expect(format.formatDateTimeFull(new Date(2024, 0, 5, 6, 7, 8), '')).toBe(
        '2024-01-05 06:07:08'
      )
    })
  })

  describe('format.formatCurrency', () => {
    it('千分位 + 默认单位元 + 最多4位小数去尾零', () => {
      expect(format.formatCurrency(1234567.891)).toBe('1,234,567.891元')
      expect(format.formatCurrency(1234567.89)).toBe('1,234,567.89元')
    })

    it('自定义单位', () => {
      expect(format.formatCurrency(100, '万元')).toBe('100万元')
    })

    // 原实现直接 value.toLocaleString()：null/undefined 抛 TypeError，NaN 渲染成 'NaN'。
    it('null / undefined / 空串回退 "-" 而不抛 TypeError', () => {
      expect(format.formatCurrency(null)).toBe('-')
      expect(format.formatCurrency(undefined)).toBe('-')
      expect(format.formatCurrency('')).toBe('-')
    })

    it('非有限数（NaN / Infinity / 非数字串）回退 "-" 而不渲染 NaN', () => {
      expect(format.formatCurrency(Number.NaN)).toBe('-')
      expect(format.formatCurrency(Number.POSITIVE_INFINITY)).toBe('-')
      expect(format.formatCurrency('not-a-number')).toBe('-')
    })
  })

  /**
   * formatMoney4：金额（万元）格式化，入参容忍 number|string|null|undefined。
   * 重点覆盖 `!Number.isFinite(n)` 的真侧——脏数据（非数字字符串）与
   * 非有限数（Infinity/NaN）必须回落 '0' 而不是渲染出 'NaN'/'∞'。
   */
  describe('format.formatMoney4', () => {
    it('千分位 + 最多4位小数去尾零', () => {
      expect(format.formatMoney4(1234567.891)).toBe('1,234,567.891')
      expect(format.formatMoney4(1234.5)).toBe('1,234.5')
      expect(format.formatMoney4(100)).toBe('100')
      // 第5位小数被四舍五入到第4位
      expect(format.formatMoney4(0.123456)).toBe('0.1235')
    })

    it('数字字符串先转数再格式化', () => {
      expect(format.formatMoney4('1234.5')).toBe('1,234.5')
      expect(format.formatMoney4('0')).toBe('0')
    })

    it('null/undefined 经 `?? 0` 归零（有限侧）', () => {
      expect(format.formatMoney4(null)).toBe('0')
      expect(format.formatMoney4(undefined)).toBe('0')
      // 空串不走 `?? 0`（'' 非 nullish），但 Number('') === 0 仍属有限侧
      expect(format.formatMoney4('')).toBe('0')
    })

    it('非数字字符串 → Number() 得 NaN → 非有限分支回落 "0"', () => {
      // 后端导入脏数据/空单元格时常见，绝不能把 'NaN' 渲染到表格
      expect(format.formatMoney4('abc')).toBe('0')
      expect(format.formatMoney4('1,234')).toBe('0')
      expect(format.formatMoney4('暂无')).toBe('0')
    })

    it('Infinity / -Infinity / NaN → 非有限分支回落 "0"', () => {
      expect(format.formatMoney4(Infinity)).toBe('0')
      expect(format.formatMoney4(-Infinity)).toBe('0')
      expect(format.formatMoney4(NaN)).toBe('0')
    })

    it('0 与负值正常格式化（不误入非有限分支）', () => {
      expect(format.formatMoney4(0)).toBe('0')
      expect(format.formatMoney4(-1234.5)).toBe('-1,234.5')
    })
  })

  describe('re-exports 断言', () => {
    it('logger 是 logger 实例', () => {
      expect(typeof logger.debug).toBe('function')
      expect(typeof logger.info).toBe('function')
      expect(typeof logger.warn).toBe('function')
      expect(typeof logger.error).toBe('function')
    })

    it('request 是函数（@/api/request 默认导出，测试中为 mock）', () => {
      expect(typeof request).toBe('function')
      request('/system/ping')
      expect(mockRequest).toHaveBeenCalledWith('/system/ping')
    })

    it('exportUtil 提供 CSV/Excel/PDF/escapeCSVField', () => {
      expect(typeof exportUtil.exportToCSV).toBe('function')
      expect(typeof exportUtil.exportToExcel).toBe('function')
      expect(typeof exportUtil.exportToPDF).toBe('function')
      expect(typeof exportUtil.escapeCSVField).toBe('function')
    })

    it('copyToClipboard 导出（空文本直接 false）', async () => {
      expect(typeof copyToClipboard).toBe('function')
      expect(await copyToClipboard('')).toBe(false)
    })
  })
})
