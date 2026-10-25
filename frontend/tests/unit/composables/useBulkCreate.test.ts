import { describe, expect, it, vi } from 'vitest'

import { extractErrorMessage, useBulkCreate } from '@/composables/useBulkCreate'

describe('extractErrorMessage', () => {
  it('字符串原样返回', () => {
    expect(extractErrorMessage('编码重复')).toBe('编码重复')
  })

  it('对象优先取 message / detail / msg', () => {
    expect(extractErrorMessage({ message: 'A' })).toBe('A')
    expect(extractErrorMessage({ detail: 'B' })).toBe('B')
    expect(extractErrorMessage({ msg: 'C' })).toBe('C')
  })

  it('Error 实例取 message', () => {
    expect(extractErrorMessage(new Error('网络中断'))).toBe('网络中断')
  })

  it('空串/空对象/未知类型回退默认文案', () => {
    expect(extractErrorMessage('   ')).toBe('新增失败')
    expect(extractErrorMessage({})).toBe('新增失败')
    expect(extractErrorMessage(null)).toBe('新增失败')
    expect(extractErrorMessage(undefined, '自定义兜底')).toBe('自定义兜底')
  })
})

describe('useBulkCreate', () => {
  const toPayload = (row: string[]) => ({ name: row[0], year: row[1] })

  it('全部成功：串行调用、计数正确', async () => {
    const createOne = vi.fn().mockResolvedValue({ code: 200 })
    const { run, running } = useBulkCreate<string[], { name: string; year: string }>(
      createOne,
      toPayload
    )

    const pending = run([['甲村', '2024'], ['乙村', '2024']])
    expect(running.value).toBe(true)
    const result = await pending

    expect(result).toEqual({ total: 2, success: 2, failures: [] })
    expect(createOne).toHaveBeenCalledTimes(2)
    expect(createOne).toHaveBeenNthCalledWith(1, { name: '甲村', year: '2024' })
    expect(running.value).toBe(false)
  })

  it('串行执行（不是 Promise.all 一把打出去）', async () => {
    const order: string[] = []
    const createOne = vi.fn(async (payload: { name: string }) => {
      order.push(`start-${payload.name}`)
      await new Promise((resolve) => setTimeout(resolve, 1))
      order.push(`end-${payload.name}`)
    })
    const { run } = useBulkCreate<string[], { name: string }>(createOne, (row) => ({ name: row[0] }))

    await run([['A'], ['B']])

    // 串行时一定是 start-A → end-A → start-B → end-B
    expect(order).toEqual(['start-A', 'end-A', 'start-B', 'end-B'])
  })

  it('单条失败不中断整批，并给出行号与原因（可对照 Excel 补录）', async () => {
    const createOne = vi
      .fn()
      .mockResolvedValueOnce({ code: 200 })
      .mockRejectedValueOnce(new Error('编码重复'))
      .mockResolvedValueOnce({ code: 200 })
    const { run } = useBulkCreate<string[], { name: string }>(createOne, toPayload)

    const result = await run([['甲村', '2024'], ['乙村', '2024'], ['丙村', '2024']])

    expect(result.total).toBe(3)
    expect(result.success).toBe(2)
    expect(result.failures).toHaveLength(1)
    expect(result.failures[0].index).toBe(2)
    expect(result.failures[0].message).toBe('编码重复')
    expect(result.failures[0].row).toEqual(['乙村', '2024'])
  })

  it('全部失败也把明细逐条收集（不是只报第一条）', async () => {
    const createOne = vi.fn().mockRejectedValue({ detail: '参数校验失败' })
    const { run } = useBulkCreate<string[], { name: string }>(createOne, toPayload)

    const result = await run([['甲'], ['乙']])

    expect(result.success).toBe(0)
    expect(result.failures.map((f) => f.message)).toEqual(['参数校验失败', '参数校验失败'])
  })

  it('空输入 → 直接返回空结果（不发请求）', async () => {
    const createOne = vi.fn()
    const { run, summarize } = useBulkCreate<string[], unknown>(createOne, (row) => row)

    const result = await run([])
    expect(result).toEqual({ total: 0, success: 0, failures: [] })
    expect(createOne).not.toHaveBeenCalled()
    expect(summarize(result)).toBe('没有需要新增的数据')
  })

  it('异常抛出后 running 也复位（finally 保证）', async () => {
    const createOne = vi.fn(async () => {
      throw new Error('boom')
    })
    const { run, running } = useBulkCreate<string[], unknown>(createOne, (row) => row)

    await run([['x']])
    expect(running.value).toBe(false)
  })

  it('summarize：全成功 / 混合失败 两种话术', async () => {
    const createOne = vi.fn()
    const { run, summarize } = useBulkCreate<string[], unknown>(createOne, (row) => row)

    createOne.mockResolvedValue(1)
    expect(summarize(await run([['a']]))).toBe('已新增 1 条')

    createOne.mockReset()
    createOne.mockResolvedValueOnce(1).mockRejectedValueOnce(new Error('重复'))
    expect(summarize(await run([['a'], ['b']]))).toBe('已新增 1 条，失败 1 条（第 2 行）')
  })
})
