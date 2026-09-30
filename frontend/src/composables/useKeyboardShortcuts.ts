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
 * 按住 Shift 时 e.key 会变成上档字符（Shift+1 → '!'），
 * 注册侧写的却是物理键位（'1'）。此表把上档字符还原回物理键位，
 * 使 `{ key: '1', shift: true }` 这类快捷键能被命中。
 */
const SHIFTED_CHAR_TO_BASE: Record<string, string> = {
  '!': '1',
  '@': '2',
  '#': '3',
  $: '4',
  '%': '5',
  '^': '6',
  '&': '7',
  '*': '8',
  '(': '9',
  ')': '0',
  _: '-',
  '+': '=',
  '{': '[',
  '}': ']',
  '|': '\\',
  ':': ';',
  '"': "'",
  '<': ',',
  '>': '.',
  '?': '/',
  '~': '`',
}

/** 单字符键名统一大写，保证注册端与事件端拼出的组合串一致 */
function normalizeKey(key: string): string {
  return key.length === 1 ? key.toUpperCase() : key
}

/** 组合键字符串的唯一构造入口（formatShortcut 与 handleKeydown 共用，避免两处实现漂移） */
function buildCombo(key: string, mods: { ctrl?: boolean; shift?: boolean; alt?: boolean }): string {
  const parts: string[] = []
  if (mods.ctrl) parts.push('Ctrl')
  if (mods.shift) parts.push('Shift')
  if (mods.alt) parts.push('Alt')
  parts.push(normalizeKey(key))
  return parts.join('+')
}

/**
 * 由物理键位码反解基础键名（Shift+1 的 e.code 仍是 'Digit1'）。
 * 键盘布局差异下可能返回 null，此时仅依赖 e.key 与上档字符还原表。
 */
function baseKeyFromCode(code: string | undefined): string | null {
  if (!code) return null
  if (/^Key[A-Z]$/.test(code)) return code.slice(3)
  if (/^Digit[0-9]$/.test(code)) return code.slice(5)
  if (/^Numpad[0-9]$/.test(code)) return code.slice(6)
  return null
}

/**
 * 获取快捷键的字符串表示
 */
export function formatShortcut(s: Shortcut): string {
  return buildCombo(s.key, { ctrl: s.ctrl, shift: s.shift, alt: s.alt })
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

    const mods = { ctrl: e.ctrlKey || e.metaKey, shift: e.shiftKey, alt: e.altKey }

    // 候选组合串（O(1) 查表）：
    // ① e.key 原样 —— 覆盖 'Escape'、'F5'、以及直接注册上档字符（{ key: '!', shift: true }）的情形；
    // ② Shift 生效时的物理键位 —— Shift+1 的 e.key 是 '!'，仅靠 ① 永远匹配不到注册的 { key: '1', shift: true }。
    //    物理键位优先由 e.code 反解（布局无关），退化时用上档字符还原表。
    const candidates = [buildCombo(e.key, mods)]
    if (mods.shift && e.key.length === 1) {
      const physical = baseKeyFromCode(e.code) || SHIFTED_CHAR_TO_BASE[e.key] || null
      if (physical && normalizeKey(physical) !== normalizeKey(e.key)) {
        candidates.push(buildCombo(physical, mods))
      }
    }

    let combo = ''
    let s: Shortcut | undefined
    for (const candidate of candidates) {
      const hit = shortcutMap.value.get(candidate)
      if (hit) {
        combo = candidate
        s = hit
        break
      }
    }
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
