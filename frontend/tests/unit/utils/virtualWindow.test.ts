import { describe, expect, it } from 'vitest'

import { computeWindow, sliceWindow } from '@/utils/virtualWindow'

const BASE = { viewportHeight: 400, itemHeight: 40, total: 1000, buffer: 3 }

describe('computeWindow', () => {
  it('顶部：起点被缓冲夹到 0，终点覆盖可视行数 + 缓冲', () => {
    const w = computeWindow({ ...BASE, scrollTop: 0 })
    expect(w.start).toBe(0)
    // 可视 400/40 = 10 行 + 1 + 缓冲 3
    expect(w.end).toBe(14)
    expect(w.offsetTop).toBe(0)
    expect(w.totalHeight).toBe(40000)
  })

  it('中部：按 scrollTop 换算首行，并上下各留缓冲', () => {
    const w = computeWindow({ ...BASE, scrollTop: 4000 }) // 第 100 行
    expect(w.start).toBe(97)
    expect(w.end).toBe(114)
    expect(w.offsetTop).toBe(3880)
  })

  it('底部：end 必须被 total 截断（否则渲染 undefined 行）', () => {
    const w = computeWindow({ ...BASE, scrollTop: 40000 })
    expect(w.end).toBe(1000)
    // scrollTop 被夹到 totalHeight-1 → 首行 999，再减缓冲 3
    expect(w.start).toBe(996)
  })

  it('超出底部（过度滚动）也不越界', () => {
    const w = computeWindow({ ...BASE, scrollTop: 999999 })
    expect(w.end).toBe(1000)
    expect(w.start).toBeLessThan(1000)
  })

  it('负 scrollTop（橡皮筋/回弹）按 0 处理', () => {
    const w = computeWindow({ ...BASE, scrollTop: -500 })
    expect(w.start).toBe(0)
    expect(w.offsetTop).toBe(0)
  })

  it('空数据 → 空区间且总高 0', () => {
    expect(computeWindow({ ...BASE, scrollTop: 0, total: 0 })).toEqual({
      start: 0,
      end: 0,
      offsetTop: 0,
      totalHeight: 0,
    })
  })

  it('负数 total 视为 0（不产生负高度）', () => {
    const w = computeWindow({ ...BASE, scrollTop: 0, total: -5 })
    expect(w).toEqual({ start: 0, end: 0, offsetTop: 0, totalHeight: 0 })
  })

  it('itemHeight <= 0 时退化为 1，不产出 Infinity/NaN', () => {
    const w = computeWindow({ ...BASE, scrollTop: 0, itemHeight: 0 })
    expect(Number.isFinite(w.end)).toBe(true)
    expect(w.totalHeight).toBe(1000)
    expect(w.end).toBeLessThanOrEqual(1000)
  })

  it('视口高度为 0 时仍渲染缓冲行（不至于全空）', () => {
    const w = computeWindow({ ...BASE, scrollTop: 0, viewportHeight: 0 })
    // 视口 0 行时仍渲染 1 行 + 上下缓冲 3
    expect(w.end).toBe(1 + 3)
  })

  it('缓冲为 0 / 未传时按 3 处理', () => {
    const zero = computeWindow({ ...BASE, scrollTop: 4000, buffer: 0 })
    expect(zero.start).toBe(100)
    const fallback = computeWindow({
      scrollTop: 4000,
      viewportHeight: 400,
      itemHeight: 40,
      total: 1000,
    })
    expect(fallback.start).toBe(97)
  })

  it('数据量小于一屏时窗口就是全量', () => {
    const w = computeWindow({ ...BASE, scrollTop: 0, total: 5 })
    expect(w.start).toBe(0)
    expect(w.end).toBe(5)
    expect(w.totalHeight).toBe(200)
  })
})

describe('sliceWindow', () => {
  const items = Array.from({ length: 100 }, (_, i) => i)

  it('按区间切片', () => {
    expect(sliceWindow(items, { start: 2, end: 5, offsetTop: 0, totalHeight: 4000 })).toEqual([2, 3, 4])
  })

  it('空区间返回空数组（end <= start）', () => {
    expect(sliceWindow(items, { start: 5, end: 5, offsetTop: 0, totalHeight: 4000 })).toEqual([])
  })

  it('区间超出数据长度时按实际长度截断', () => {
    expect(sliceWindow([1, 2], { start: 1, end: 10, offsetTop: 0, totalHeight: 80 })).toEqual([2])
  })
})
