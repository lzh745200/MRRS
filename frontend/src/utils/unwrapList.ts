/** API 响应解包工具 — 处理后端多种响应格式 */

import type { ListResponse } from '@/types/api'

export interface UnwrappedList<T = unknown> {
  items: T[]
  total: number
}

/**
 * 从 axios 解包后的 data 中提取 items + total
 *
 * 兼容格式（覆盖各调用点在收敛前手写容忍过的全部形态）:
 *   [...list]                     — 裸数组直返
 *   { items, total }              — 直接分页格式（Pattern B 自动解包后）
 *   { data: [...list] }           — data 字段为数组（历史裸返回形态）
 *   { code, data: { items, total } } — 标准 API 响应（Pattern A 原始响应）
 *
 * 备注：数组分支的 total 取数组长度；`{ data: [...] }` 形态没有分页总数可用，
 * 同样以长度兜底（与各手写点 `items.length` 的兜底口径一致）。
 */
export function unwrapList<T = unknown>(res: any): UnwrappedList<T> {
  if (Array.isArray(res)) return { items: res as T[], total: res.length }
  if (res?.items) return { items: res.items as T[], total: res.total ?? res.items.length }
  if (Array.isArray(res?.data)) {
    return { items: res.data as T[], total: res.total ?? res.data.length }
  }
  if (res?.data?.items)
    return {
      items: res.data.items as T[],
      total: res.data.total ?? res.data.items.length,
    }
  return { items: [] as T[], total: 0 }
}

/**
 * 类型安全的列表响应解包
 * 适用于已通过 apiRequest/get/post 自动解包的响应
 */
export function unwrapListTyped<T>(res: ListResponse<T> | any): UnwrappedList<T> {
  return unwrapList<T>(res)
}
