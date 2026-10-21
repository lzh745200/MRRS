/**
 * useDangerConfirm —— 危险操作统一二次确认（批次 3）
 *
 * 覆盖：普通确认（确认/取消/关闭）、高危录入确认（匹配/不匹配/取消）、
 * 非预期异常不向上抛、默认按钮文案。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mocks = vi.hoisted(() => ({
  confirm: vi.fn(),
  prompt: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessageBox: {
    confirm: (...args: unknown[]) => mocks.confirm(...args),
    prompt: (...args: unknown[]) => mocks.prompt(...args),
  },
}))

import { useDangerConfirm } from '@/composables/useDangerConfirm'

describe('useDangerConfirm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('普通确认：用户确认 → true，并使用默认按钮文案', async () => {
    mocks.confirm.mockResolvedValue('confirm')
    const { confirmDanger } = useDangerConfirm()

    const result = await confirmDanger({ title: '确认删除', message: '删除后不可恢复' })

    expect(result).toBe(true)
    expect(mocks.confirm).toHaveBeenCalledTimes(1)
    const [message, title, options] = mocks.confirm.mock.calls[0]
    expect(message).toBe('删除后不可恢复')
    expect(title).toBe('确认删除')
    expect(options).toMatchObject({
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
  })

  it('普通确认：自定义确认按钮文案', async () => {
    mocks.confirm.mockResolvedValue('confirm')
    const { confirmDanger } = useDangerConfirm()

    await confirmDanger({ title: 'T', message: 'M', confirmButtonText: '确认恢复' })

    expect(mocks.confirm.mock.calls[0][2].confirmButtonText).toBe('确认恢复')
  })

  it('普通确认：取消/关闭 → false', async () => {
    for (const reason of ['cancel', 'close']) {
      mocks.confirm.mockRejectedValue(reason)
      const { confirmDanger } = useDangerConfirm()
      await expect(confirmDanger({ title: 'T', message: 'M' })).resolves.toBe(false)
    }
  })

  it('普通确认：非预期异常也不向上抛（返回 false）', async () => {
    mocks.confirm.mockRejectedValue(new Error('boom'))
    const { confirmDanger } = useDangerConfirm()

    await expect(confirmDanger({ title: 'T', message: 'M' })).resolves.toBe(false)
  })

  it('高危确认：需要手工输入指定文本，匹配时返回 true', async () => {
    mocks.prompt.mockResolvedValue({ value: 'admin' })
    const { confirmDanger } = useDangerConfirm()

    const result = await confirmDanger({
      title: '确认重置密码',
      message: 'M',
      confirmButtonText: '确认重置',
      typedConfirmation: 'admin',
    })

    expect(result).toBe(true)
    const [, title, options] = mocks.prompt.mock.calls[0]
    expect(title).toBe('确认重置密码')
    expect(options.confirmButtonText).toBe('确认重置')
    expect(options.inputPlaceholder).toBe('请输入「admin」以确认')
  })

  it('高危确认：inputValidator 对匹配/不匹配分别返回 true 与错误文案', async () => {
    mocks.prompt.mockResolvedValue({ value: 'admin' })
    const { confirmDanger } = useDangerConfirm()

    await confirmDanger({ title: 'T', message: 'M', typedConfirmation: 'admin' })

    const validator = mocks.prompt.mock.calls[0][2].inputValidator as (v: string) => unknown
    expect(validator('admin')).toBe(true)
    expect(validator('adm')).toContain('输入不匹配')
  })

  it('高危确认：取消（输入不匹配/关闭）→ false', async () => {
    mocks.prompt.mockRejectedValue('cancel')
    const { confirmDanger } = useDangerConfirm()

    await expect(
      confirmDanger({ title: 'T', message: 'M', typedConfirmation: 'admin' })
    ).resolves.toBe(false)
  })

  it('高危确认：空字符串作为待输入文本时仍走录入分支', async () => {
    mocks.prompt.mockResolvedValue({ value: '' })
    const { confirmDanger } = useDangerConfirm()

    const result = await confirmDanger({ title: 'T', message: 'M', typedConfirmation: '' })

    expect(result).toBe(true)
    expect(mocks.prompt).toHaveBeenCalledTimes(1)
    expect(mocks.confirm).not.toHaveBeenCalled()
  })
})
