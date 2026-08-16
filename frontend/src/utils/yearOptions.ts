/**
 * 年份（年度）选项生成工具
 *
 * 历史上各页面年份下拉框多以「当前年份 + 1」为上限硬编码生成，
 * 导致次年即可选年份"撞墙"（例如 2026 年只能选到 2027 年）。
 * 现统一采用滚动窗口：上限 = 当前年份 + futureSpan，随系统时钟自动后移，
 * 保证系统可以一直使用下去。
 */

/** 默认可选最早年份（系统历史数据起点） */
export const DEFAULT_START_YEAR = 2000

/** 默认可选未来年份跨度（当前年份 + 10） */
export const FUTURE_YEAR_SPAN = 10

export interface YearOptionsConfig {
  /** 可选最早年份，默认 DEFAULT_START_YEAR */
  start?: number
  /** 未来年份跨度（上限 = 当前年份 + futureSpan），默认 FUTURE_YEAR_SPAN */
  futureSpan?: number
  /** 是否降序排列（新年份在前），默认 true */
  descending?: boolean
}

/**
 * 生成可选年份列表（滚动窗口：start ~ 当前年份 + futureSpan）。
 * 窗口随系统时钟滚动，永不过期。
 */
export function getYearOptions(config: YearOptionsConfig = {}): number[] {
  const { start = DEFAULT_START_YEAR, futureSpan = FUTURE_YEAR_SPAN, descending = true } = config
  const end = new Date().getFullYear() + futureSpan
  const years: number[] = []
  for (let y = Math.min(start, end); y <= end; y++) {
    years.push(y)
  }
  return descending ? years.reverse() : years
}
