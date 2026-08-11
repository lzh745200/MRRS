/**
 * 键盘快捷键 Composable — 增强版
 *
 * 提供全局和页面级快捷键注册，支持：
 * - Ctrl/Shift/Alt 组合键
 * - 快捷键冲突检测
 * - 快捷键帮助面板
 * - 输入框内禁用（避免在表单中输入时误触发）
 */

import { logger } from '@/utils/logger'
import { onMounted, onUnmounted, ref, computed } from 'vue'

export interface Shortcut {
  /** 键名 (如 's', 'Enter', 'Escape') */
  key: string
  /** 是否需要 Ctrl/Cmd */
  ctrl?: boolean
  /** 是否需要 Shift */
  shift?: boolean
  /** 是否需要 Alt */
  alt?: boolean
  /** 触发的处理函数 */
  handler: () => void
  /** 快捷键描述（用于帮助面板） */
  description?: string
  /** 所属分组 */
  group?: string
  /** 是否在输入框中禁用（默认 true） */
  disabledInInput?: boolean
}

/** 忽略快捷键的元素类型（在输入框中） */
const INPUT_ELEMENTS = new Set(['INPUT', 'TEXTAREA', 'SELECT'])

/**
 * 获取快捷键的字符串表示
 */
export function formatShortcut(s: Shortcut): string {
  const parts: string[] = []
  if (s.ctrl) parts.push('Ctrl')
  if (s.shift) parts.push('Shift')
  if (s.alt) parts.push('Alt')
  parts.push(s.key.length === 1 ? s.key.toUpperCase() : s.key)
  return parts.join('+')
}

export function useKeyboardShortcuts(shortcuts: Shortcut[]) {
  const registered = ref<Shortcut[]>(shortcuts)
  const showHelp = ref(false)

  /** 冲突检测：检查是否有重复的快捷键组合 */
  const conflicts = computed(() => {
    const seen = new Map<string, Shortcut[]>()
    for (const s of registered.value) {
      const combo = formatShortcut(s)
      if (!seen.has(combo)) seen.set(combo, [])
      seen.get(combo)!.push(s)
    }
    const result: Array<{ combo: string; shortcuts: Shortcut[] }> = []
    for (const [combo, items] of seen) {
      if (items.length > 1) result.push({ combo, shortcuts: items })
    }
    return result
  })

  /** O(1) 快捷键查找表 — 从 combo 字符串到 Shortcut 的映射 */
  const shortcutMap = computed(() => {
    const map = new Map<string, Shortcut>()
    for (const s of registered.value) {
      map.set(formatShortcut(s), s)
    }
    return map
  })

  function handleKeydown(e: KeyboardEvent) {
    // 在输入框中禁用快捷键（除非明确设置 disabledInInput = false）
    const target = e.target as HTMLElement
    const isInput = INPUT_ELEMENTS.has(target.tagName)
    const isContentEditable = target.isContentEditable

    // Build the combo for O(1) map lookup
    const parts: string[] = []
    if (e.ctrlKey || e.metaKey) parts.push('Ctrl')
    if (e.shiftKey) parts.push('Shift')
    if (e.altKey) parts.push('Alt')
    parts.push(e.key.length === 1 ? e.key.toUpperCase() : e.key)
    const combo = parts.join('+')

    const s = shortcutMap.value.get(combo)
    if (!s) return

    // 输入框中跳过
    if ((isInput || isContentEditable) && s.disabledInInput !== false) {
      return
    }
    e.preventDefault()
    e.stopPropagation()
    try {
      s.handler()
    } catch (err) {
      console.error(`[快捷键] ${combo} 执行失败:`, err)
    }
  }

  /** 注册新快捷键 */
  function register(shortcut: Shortcut) {
    const existing = shortcutMap.value.get(formatShortcut(shortcut))
    if (existing) {
      logger.warn(`[快捷键] ${formatShortcut(shortcut)} 已注册，将被覆盖`)
      unregister(existing)
    }
    registered.value.push(shortcut)
  }

  /** 注销快捷键 */
  function unregister(shortcut: Pick<Shortcut, 'key' | 'ctrl' | 'shift' | 'alt'>) {
    const combo = formatShortcut(shortcut as Shortcut)
    registered.value = registered.value.filter((s) => formatShortcut(s) !== combo)
  }

  /** 获取分组后的快捷键列表（用于帮助面板） */
  const groupedShortcuts = computed(() => {
    const groups = new Map<string, Shortcut[]>()
    for (const s of registered.value) {
      const group = s.group || '其他'
      if (!groups.has(group)) groups.set(group, [])
      groups.get(group)!.push(s)
    }
    return groups
  })

  onMounted(() => {
    window.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
  })

  return {
    registered,
    conflicts,
    showHelp,
    groupedShortcuts,
    register,
    unregister,
    formatShortcut,
  }
}
