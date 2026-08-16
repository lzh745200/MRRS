import { describe, it, expect, vi, afterEach } from 'vitest'
import { getYearOptions, DEFAULT_START_YEAR, FUTURE_YEAR_SPAN } from '@/utils/yearOptions'

describe('utils/yearOptions', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('默认：降序，范围 2000 ~ 当前年+10', () => {
    const cur = new Date().getFullYear()
    const list = getYearOptions()
    expect(list[0]).toBe(cur + FUTURE_YEAR_SPAN)
    expect(list[list.length - 1]).toBe(DEFAULT_START_YEAR)
    expect(list).toHaveLength(cur + FUTURE_YEAR_SPAN - DEFAULT_START_YEAR + 1)
  })

  it('ascending：升序返回', () => {
    const list = getYearOptions({ descending: false })
    expect(list[0]).toBe(DEFAULT_START_YEAR)
    expect(list[list.length - 1]).toBe(new Date().getFullYear() + FUTURE_YEAR_SPAN)
  })

  it('自定义 start：帮扶村年度数据从 2017 起', () => {
    const cur = new Date().getFullYear()
    const list = getYearOptions({ start: 2017 })
    expect(list[list.length - 1]).toBe(2017)
    expect(list[0]).toBe(cur + FUTURE_YEAR_SPAN)
    expect(list).toHaveLength(cur + FUTURE_YEAR_SPAN - 2017 + 1)
  })

  it('自定义 futureSpan', () => {
    const cur = new Date().getFullYear()
    const list = getYearOptions({ start: 2021, futureSpan: 1 })
    expect(list[0]).toBe(cur + 1)
    expect(list[list.length - 1]).toBe(2021)
  })

  it('start 大于上限时退化为单元素，不产生空列表', () => {
    const cur = new Date().getFullYear()
    const list = getYearOptions({ start: cur + FUTURE_YEAR_SPAN + 5 })
    expect(list).toEqual([cur + FUTURE_YEAR_SPAN])
  })

  it('滚动窗口：系统时钟推进后上限随后移（模拟 2031 年）', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2031, 5, 1))
    const list = getYearOptions({ start: 2017 })
    expect(list[0]).toBe(2041)
    expect(list).toContain(2031)
  })

  it('相邻年份连续无空洞', () => {
    const list = getYearOptions({ descending: false })
    for (let i = 1; i < list.length; i++) {
      expect(list[i] - list[i - 1]).toBe(1)
    }
  })
})
