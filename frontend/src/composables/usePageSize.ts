/**
 * 每页条数偏好（2026-10-26 / ⑥ 表格性能）
 *
 * ## 背景与取舍
 * 排查发现：全站列表**都已分页**，且 `page_size` 有 200 的硬上限
 * （`backend/app/core/constants.py` 的 `MAX_PAGE_SIZE`，由 `check_pagination_cap.py` 门禁守住）。
 * 也就是说单页最多 200 行 —— `el-table` 在这个量级没有性能问题，
 * 强行给分页表加虚拟滚动属于"为架构而架构"，只会增加状态同步的坑。
 *
 * 真正缺的是**用户可控的每页条数**：现在 55 处硬编码 `page_size`，用户在第 2 页想看更多
 * 只能一页页翻。本模块提供统一入口：
 * - 选项固定 `[20, 50, 100, 200]`，**200 与后端硬上限一致**，超出会被夹回；
 * - 按业务域记忆（`ui:pageSize:<scope>`），列表页之间互不干扰；
 * - 存储不可用/损坏 JSON/非法值 一律回退默认 20，绝不抛错（模块在渲染热路径上）。
 */
import { computed, ref } from 'vue'
import { safeGetItem, safeSetItem } from '@/utils/safeStorage'

export const PAGE_SIZE_OPTIONS: readonly number[] = [20, 50, 100, 200]
export const DEFAULT_PAGE_SIZE = 20
/** 与后端 `MAX_PAGE_SIZE` 保持一致（后端另有门禁，这里只是前端兜底）。 */
export const MAX_PAGE_SIZE = 200

export const PAGE_SIZE_STORAGE_PREFIX = 'ui:pageSize:'

export function pageSizeStorageKey(scope: string): string {
  return `${PAGE_SIZE_STORAGE_PREFIX}${scope}`
}

/** 归一化：只接受选项内的值（不做"就近取整"，避免 37 这种值造成困惑）。 */
export function normalizePageSize(raw: unknown): number {
  return PAGE_SIZE_OPTIONS.includes(Number(raw)) ? Number(raw) : DEFAULT_PAGE_SIZE
}

export function readPageSize(scope: string): number {
  return normalizePageSize(safeGetItem(pageSizeStorageKey(scope), 'local'))
}

export function writePageSize(scope: string, size: number): void {
  safeSetItem(pageSizeStorageKey(scope), String(normalizePageSize(size)), 'local')
}

export function usePageSize(scope: string) {
  const pageSize = ref(readPageSize(scope))
  // 以可变数组副本暴露：el-pagination 的 page-sizes 要求 number[]（readonly 会类型冲突）
  const options = computed<number[]>(() => [...PAGE_SIZE_OPTIONS])

  function setPageSize(next: number): number {
    const normalized = normalizePageSize(next)
    pageSize.value = normalized
    writePageSize(scope, normalized)
    return normalized
  }

  return { pageSize, options, setPageSize }
}
