/**
 * 表单草稿自动保存（2026-10-25 / ③ 录入效率包）
 *
 * ## 为什么
 * 现场录入的常态是"填到一半被打断"：接个电话、切去查台账、机器休眠。原实现里
 * 一旦离开页面或刷新，输入全丢 —— 而这类表单往往有 10+ 字段，重填一次就是几分钟。
 *
 * ## 设计取舍
 * - **只存本地**（localStorage）：本系统完全离线，草稿不外传；存储不可用（隐私模式/配额）
 *   时静默降级为内存态，绝不抛错（模块在交互热路径上）。
 * - **按 key 隔离**：`form:draft:<业务键>`，业务键由页面给（如 `policies:edit:new`、
 *   `policies:edit:42`），新建与编辑互不污染。
 * - **TTL 默认 7 天**：草稿是"救急"不是"档案"，过期自动丢弃，避免半年前的脏数据被恢复。
 * - **空表单不落盘**：全字段为空时不写存储 —— 否则每打开一个表单就留一条垃圾，
 *   localStorage 很快被塞满（配额只有 5MB 左右）。
 * - **恢复是显式动作**：`restore()` 由页面在确认后调用（配 ElMessageBox 提示），
 *   不静默覆盖用户刚输入的内容。
 */
import { getCurrentInstance, onUnmounted, ref, watch } from 'vue'
import type { Ref } from 'vue'

export const DRAFT_STORAGE_PREFIX = 'form:draft:'
export const DRAFT_TTL_DAYS = 7
export const DRAFT_DEBOUNCE_MS = 600

export interface DraftRecord<T> {
  data: T
  savedAt: number
}

export interface UseFormDraftOptions {
  /** 业务键（页面自行决定：`<模块>:<场景>:<id|new>`）。 */
  key: string
  /** 保留天数，默认 7。 */
  ttlDays?: number
  /** 防抖毫秒数，默认 600。 */
  debounceMs?: number
}

/** 草稿的存储键（对外暴露以便测试与清理）。 */
export function draftStorageKey(key: string): string {
  return `${DRAFT_STORAGE_PREFIX}${key}`
}

function storage(): Storage | null {
  try {
    // 显式取一次：隐私模式下访问本身可能抛错
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}

/** 读取草稿：损坏 JSON / 结构不符 / 过期 / 存储异常 一律返回 null。 */
export function readDraft<T>(
  key: string,
  now: number = Date.now(),
  ttlDays = DRAFT_TTL_DAYS
): DraftRecord<T> | null {
  const store = storage()
  if (!store) return null
  try {
    const raw = store.getItem(draftStorageKey(key))
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<DraftRecord<T>>
    if (
      !parsed ||
      typeof parsed !== 'object' ||
      !('data' in parsed) ||
      typeof parsed.savedAt !== 'number'
    ) {
      return null
    }
    const ttlMs = ttlDays * 24 * 60 * 60 * 1000
    if (now - parsed.savedAt > ttlMs) {
      store.removeItem(draftStorageKey(key))
      return null
    }
    return { data: parsed.data as T, savedAt: parsed.savedAt }
  } catch {
    return null
  }
}

/** 写入草稿（存储异常静默忽略）。 */
export function writeDraft<T>(key: string, data: T, now: number = Date.now()): void {
  const store = storage()
  if (!store) return
  try {
    store.setItem(draftStorageKey(key), JSON.stringify({ data, savedAt: now }))
  } catch {
    // 配额/隐私模式：静默降级
  }
}

/** 清除草稿（提交成功后必须调用，否则下次进来会"复活"已提交的数据）。 */
export function clearDraft(key: string): void {
  const store = storage()
  if (!store) return
  try {
    store.removeItem(draftStorageKey(key))
  } catch {
    // ignore
  }
}

/** 所有字段都为空/未填时视为"没内容"，不写入存储。 */
export function isBlankForm(source: Record<string, unknown>): boolean {
  return Object.values(source).every((value) => {
    if (value === null || value === undefined) return true
    if (typeof value === 'string') return value.trim() === ''
    if (Array.isArray(value)) return value.length === 0
    return false
  })
}

/**
 * 组合式入口：监听表单对象变化并自动落盘草稿。
 *
 * 返回：
 * - `hasDraft`：挂载时是否已有可用草稿（页面据此提示"发现未提交的草稿，是否恢复？"）
 * - `restore()`：把草稿内容合并回表单对象
 * - `clear()`：清除草稿（提交成功后调用）
 * - `flush()`：立刻落盘（离开页面前/调用提交前可用）
 */
export function useFormDraft<T extends Record<string, unknown>>(
  source: T,
  options: UseFormDraftOptions
): { hasDraft: Ref<boolean>; restore: () => boolean; clear: () => void; flush: () => void } {
  const ttlDays = options.ttlDays ?? DRAFT_TTL_DAYS
  const debounceMs = options.debounceMs ?? DRAFT_DEBOUNCE_MS
  const record = readDraft<T>(options.key, Date.now(), ttlDays)
  const hasDraft = ref(record !== null)

  let timer: ReturnType<typeof setTimeout> | null = null

  const flush = () => {
    if (isBlankForm(source)) {
      clearDraft(options.key)
      return
    }
    writeDraft(options.key, source as unknown as T)
  }

  const stop = watch(
    source,
    () => {
      if (timer) clearTimeout(timer)
      timer = setTimeout(() => {
        timer = null
        flush()
      }, debounceMs)
    },
    { deep: true }
  )

  const restore = (): boolean => {
    const latest = readDraft<T>(options.key, Date.now(), ttlDays)
    if (!latest) {
      hasDraft.value = false
      return false
    }
    Object.assign(source, latest.data as Record<string, unknown>)
    return true
  }

  const clear = () => {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    clearDraft(options.key)
    hasDraft.value = false
  }

  // 仅在组件实例内注册卸载清理：直接调用（单测/工具函数）时不适合挂生命周期，
  // 否则 Vue 会告警 "onUnmounted is called when there is no active component instance"。
  if (getCurrentInstance()) {
    onUnmounted(() => {
      stop()
      if (timer) {
        clearTimeout(timer)
        timer = null
      }
    })
  }

  return { hasDraft, restore, clear, flush }
}
