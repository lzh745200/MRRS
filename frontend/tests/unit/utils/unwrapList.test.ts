import { describe, it, expect } from 'vitest'
import { unwrapList, unwrapListTyped } from '@/utils/unwrapList'

describe('utils/unwrapList', () => {
  it('format 1: { items, total }', () => {
    const r = unwrapList({ items: [1, 2, 3], total: 3 })
    expect(r).toEqual({ items: [1, 2, 3], total: 3 })
  })

  it('format 1: { items } no total -> total = items.length', () => {
    const r = unwrapList({ items: [1, 2] })
    expect(r).toEqual({ items: [1, 2], total: 2 })
  })

  it('format 2: { code, data: { items, total } }', () => {
    const r = unwrapList({ code: 200, data: { items: ['a', 'b'], total: 10 } })
    expect(r).toEqual({ items: ['a', 'b'], total: 10 })
  })

  it('format 2: data.items no total -> total = items.length', () => {
    const r = unwrapList({ code: 200, data: { items: ['x'] } })
    expect(r).toEqual({ items: ['x'], total: 1 })
  })

  it('format 0: 裸数组直返 -> total = 数组长度', () => {
    expect(unwrapList([1, 2])).toEqual({ items: [1, 2], total: 2 })
    expect(unwrapList([])).toEqual({ items: [], total: 0 })
  })

  it('format 1b: { data: [...] }（data 字段为数组）', () => {
    expect(unwrapList({ data: [1, 2, 3] })).toEqual({ items: [1, 2, 3], total: 3 })
    // 分页 total 存在时优先使用（数组仅作 items 载体）
    expect(unwrapList({ data: [1], total: 9 })).toEqual({ items: [1], total: 9 })
  })

  it('null res -> { items: [], total: 0 }', () => {
    expect(unwrapList(null)).toEqual({ items: [], total: 0 })
  })

  it('undefined res -> { items: [], total: 0 }', () => {
    expect(unwrapList(undefined)).toEqual({ items: [], total: 0 })
  })

  it('empty object -> { items: [], total: 0 }', () => {
    expect(unwrapList({})).toEqual({ items: [], total: 0 })
  })

  it('only data without items -> empty', () => {
    expect(unwrapList({ data: {} })).toEqual({ items: [], total: 0 })
  })

  describe('unwrapListTyped', () => {
    it('直接分页格式', () => {
      const r = unwrapListTyped({ items: [1, 2, 3], total: 3 })
      expect(r).toEqual({ items: [1, 2, 3], total: 3 })
    })

    it('标准 API 响应格式', () => {
      const r = unwrapListTyped({ code: 200, data: { items: ['a'], total: 1 } })
      expect(r).toEqual({ items: ['a'], total: 1 })
    })

    it('空响应', () => {
      expect(unwrapListTyped(null)).toEqual({ items: [], total: 0 })
    })
  })
})
