import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const { downloadBlobMock } = vi.hoisted(() => ({ downloadBlobMock: vi.fn() }))

vi.mock('@/api/request', () => ({
  downloadBlob: downloadBlobMock,
  default: {},
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import { exportUtil } from '@/utils/exportUtil'

function readBlobText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = reject
    reader.readAsText(blob)
  })
}

function readBlobBytes(blob: Blob): Promise<Uint8Array> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer))
    reader.onerror = reject
    reader.readAsArrayBuffer(blob)
  })
}

describe('utils/exportUtil', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('escapeCSVField', () => {
    it('普通值原样返回', () => {
      expect(exportUtil.escapeCSVField('abc')).toBe('abc')
    })

    it('逗号字段加引号', () => {
      expect(exportUtil.escapeCSVField('a,b')).toBe('"a,b"')
    })

    it('引号字段转义为双引号', () => {
      expect(exportUtil.escapeCSVField('say "hi"')).toBe('"say ""hi"""')
    })

    it('换行字段加引号', () => {
      expect(exportUtil.escapeCSVField('a\nb')).toBe('"a\nb"')
    })

    it('回车字段加引号', () => {
      expect(exportUtil.escapeCSVField('a\rb')).toBe('"a\rb"')
    })

    it('null/undefined 转为空串', () => {
      expect(exportUtil.escapeCSVField(null)).toBe('')
      expect(exportUtil.escapeCSVField(undefined)).toBe('')
    })
  })

  describe('exportToCSV', () => {
    it('空数据直接返回,不触发下载', () => {
      exportUtil.exportToCSV([], 'test')
      expect(downloadBlobMock).not.toHaveBeenCalled()
    })

    it('基本数据导出 CSV,带 BOM', async () => {
      exportUtil.exportToCSV([{ name: '张三', age: 25 }], 'users')
      expect(downloadBlobMock).toHaveBeenCalledTimes(1)
      const [blob, filename] = downloadBlobMock.mock.calls[0]
      expect(filename).toBe('users.csv')
      expect(blob).toBeInstanceOf(Blob)
      const bytes = await readBlobBytes(blob)
      expect([bytes[0], bytes[1], bytes[2]]).toEqual([0xef, 0xbb, 0xbf])
      const text = await readBlobText(blob)
      expect(text).toContain('name,age')
      expect(text).toContain('张三,25')
    })

    it('自定义 headers 时使用 header 标签', async () => {
      exportUtil.exportToCSV([{ name: '张三' }], 'users', { name: '姓名' })
      const [blob] = downloadBlobMock.mock.calls[0]
      const text = await readBlobText(blob)
      expect(text.startsWith('姓名')).toBe(true)
    })

    it('包含逗号/引号值时正确转义', async () => {
      exportUtil.exportToCSV([{ note: 'a,b"c' }], 'f')
      const [blob] = downloadBlobMock.mock.calls[0]
      const text = await readBlobText(blob)
      expect(text).toContain('"a,b""c"')
    })
  })

  describe('exportToExcel', () => {
    // exportToExcel 为 async（xlsx 按需动态导入），所有断言需 await 等待完成
    it('空数据直接返回', async () => {
      await exportUtil.exportToExcel([], 'test')
      expect(downloadBlobMock).not.toHaveBeenCalled()
    })

    it('导出真实 xlsx blob', async () => {
      await exportUtil.exportToExcel(
        [{ name: '张三', amount: 100 }],
        'funds',
        { name: '名称', amount: '金额' }
      )
      expect(downloadBlobMock).toHaveBeenCalledTimes(1)
      const [blob, filename] = downloadBlobMock.mock.calls[0]
      expect(filename).toBe('funds.xlsx')
      expect(blob).toBeInstanceOf(Blob)
      expect(blob.type).toContain('spreadsheetml')
      expect(blob.size).toBeGreaterThan(0)
    })

    it('无 headers 时使用数据键名', async () => {
      await exportUtil.exportToExcel([{ name: '张三' }], 'funds')
      expect(downloadBlobMock).toHaveBeenCalledTimes(1)
      const [blob] = downloadBlobMock.mock.calls[0]
      expect(blob.size).toBeGreaterThan(0)
    })

    it('null 值转为空串', async () => {
      await exportUtil.exportToExcel([{ name: null, amount: undefined }] as any, 'f')
      expect(downloadBlobMock).toHaveBeenCalledTimes(1)
    })
  })

  describe('exportToPDF', () => {
    it('空数据直接返回', () => {
      const openSpy = vi.spyOn(window, 'open').mockReturnValue(null)
      exportUtil.exportToPDF('title', [])
      expect(openSpy).not.toHaveBeenCalled()
    })

    it('生成打印页面并调用 print', () => {
      const mockWin = {
        document: { write: vi.fn(), close: vi.fn() },
        print: vi.fn(),
      }
      vi.spyOn(window, 'open').mockReturnValue(mockWin as any)
      exportUtil.exportToPDF('测试 <报告>', [{ name: '张三', note: '<b>x</b>' }], {
        name: '姓名',
        note: '备注',
      })
      expect(window.open).toHaveBeenCalledWith('', '_blank')
      expect(mockWin.document.write).toHaveBeenCalled()
      const html = mockWin.document.write.mock.calls[0][0] as string
      expect(html).toContain('<title>测试 &lt;报告&gt;</title>')
      expect(html).toContain('<th>姓名</th>')
      expect(html).toContain('<th>备注</th>')
      expect(html).toContain('<td>张三</td>')
      expect(html).toContain('<td>&lt;b&gt;x&lt;/b&gt;</td>')
      expect(mockWin.document.close).toHaveBeenCalled()
      expect(mockWin.print).toHaveBeenCalled()
    })

    it('window.open 返回 null 时不抛错', () => {
      vi.spyOn(window, 'open').mockReturnValue(null)
      expect(() => exportUtil.exportToPDF('t', [{ a: 1 }])).not.toThrow()
    })

    it('无 headers 时使用数据键名', () => {
      const mockWin = {
        document: { write: vi.fn(), close: vi.fn() },
        print: vi.fn(),
      }
      vi.spyOn(window, 'open').mockReturnValue(mockWin as any)
      exportUtil.exportToPDF('t', [{ name: '张三' }])
      expect(mockWin.document.write).toHaveBeenCalled()
    })

    it('null/undefined 单元格值转为空串', () => {
      const mockWin = {
        document: { write: vi.fn(), close: vi.fn() },
        print: vi.fn(),
      }
      vi.spyOn(window, 'open').mockReturnValue(mockWin as any)
      exportUtil.exportToPDF('t', [{ name: null, age: undefined }] as any)
      const html = mockWin.document.write.mock.calls[0][0] as string
      expect(html).toContain('<td></td>')
    })
  })
})
