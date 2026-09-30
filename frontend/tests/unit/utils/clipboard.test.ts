import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn() },
}))

import { ElMessage } from 'element-plus'
import { copyToClipboard, generateRandomPassword, flattenTree } from '@/utils/clipboard'

describe('utils/clipboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('copyToClipboard', () => {
    it('空 text 返回 false', async () => {
      const r = await copyToClipboard('')
      expect(r).toBe(false)
      expect(ElMessage.success).not.toHaveBeenCalled()
    })

    it('navigator.clipboard 可用 + secure context: 成功', async () => {
      const writeText = vi.fn().mockResolvedValue(undefined)
      Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
      Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true })
      const r = await copyToClipboard('hello', 'greeting')
      expect(r).toBe(true)
      expect(writeText).toHaveBeenCalledWith('hello')
      expect(ElMessage.success).toHaveBeenCalledWith('greeting已复制到剪贴板')
    })

    it('navigator.clipboard 抛错 -> 降级到 execCommand', async () => {
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
        configurable: true,
      })
      Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true })
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
      // execCommand 必须返回布尔 true 才算复制成功（实现以返回值判定，不再无条件提示成功）
      const exec = vi.fn(() => true)
      document.execCommand = exec
      const r = await copyToClipboard('text', 'X')
      expect(r).toBe(true)
      expect(exec).toHaveBeenCalledWith('copy')
      expect(ElMessage.success).toHaveBeenCalledWith('X已复制到剪贴板')
      consoleError.mockRestore()
    })

    it('非 secure context: 直接走 execCommand', async () => {
      Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
      Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true })
      const exec = vi.fn(() => true)
      document.execCommand = exec
      const r = await copyToClipboard('t', 'Y')
      expect(r).toBe(true)
      expect(exec).toHaveBeenCalled()
    })

    it('execCommand 返回 false（复制未真正生效）: 报错且不提示成功', async () => {
      Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
      Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true })
      document.execCommand = vi.fn(() => false)
      const r = await copyToClipboard('t')
      expect(r).toBe(false)
      expect(ElMessage.success).not.toHaveBeenCalled()
      expect(ElMessage.error).toHaveBeenCalledWith('复制失败，请手动复制')
    })

    it('execCommand 缺失（非函数）: 不误判为成功', async () => {
      Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
      Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true })
      // @ts-expect-error 模拟旧环境无 execCommand
      document.execCommand = undefined
      const r = await copyToClipboard('t')
      expect(r).toBe(false)
      expect(ElMessage.error).toHaveBeenCalledWith('复制失败，请手动复制')
    })

    it('execCommand 也失败: 错误消息', async () => {
      Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
      Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true })
      document.execCommand = vi.fn(() => {
        throw new Error('exec fail')
      })
      const r = await copyToClipboard('t')
      expect(r).toBe(false)
      expect(ElMessage.error).toHaveBeenCalledWith('复制失败，请手动复制')
    })
  })

  describe('generateRandomPassword', () => {
    it('默认长度 12', () => {
      const p = generateRandomPassword()
      expect(p.length).toBe(12)
    })

    it('自定义长度', () => {
      expect(generateRandomPassword(20).length).toBe(20)
    })

    it('不包含 I, l, O, 0', () => {
      const p = generateRandomPassword(100)
      expect(p).not.toMatch(/[IlO0]/)
    })

    it('包含大小写字母 + 数字 + 特殊字符', () => {
      const p = generateRandomPassword(100)
      expect(p).toMatch(/[A-Z]/)
      expect(p).toMatch(/[a-z]/)
      expect(p).toMatch(/[2-9]/) // digits 2-9
      expect(p).toMatch(/[!@#$%]/)
    })
  })

  describe('flattenTree', () => {
    it('空数组', () => {
      expect(flattenTree([])).toEqual([])
    })

    it('单层数组', () => {
      expect(flattenTree([{ id: 1 }, { id: 2 }])).toEqual([{ id: 1 }, { id: 2 }])
    })

    it('嵌套数组', () => {
      const tree = [{ id: 1, children: [{ id: 2 }, { id: 3, children: [{ id: 4 }] }] }, { id: 5 }]
      expect(flattenTree(tree).map((n: any) => n.id)).toEqual([1, 2, 3, 4, 5])
    })

    it('空 children 数组不递归', () => {
      const tree = [{ id: 1, children: [] }]
      expect(flattenTree(tree)).toEqual([{ id: 1, children: [] }])
    })

    it('自定义 childrenKey', () => {
      const tree = [{ id: 1, items: [{ id: 2 }] }]
      expect(flattenTree(tree, 'items' as any).map((n: any) => n.id)).toEqual([1, 2])
    })

    it('无 childrenKey 字段视为叶子', () => {
      const tree = [{ id: 1 }, { id: 2 }]
      expect(flattenTree(tree).map((n: any) => n.id)).toEqual([1, 2])
    })
  })
})
