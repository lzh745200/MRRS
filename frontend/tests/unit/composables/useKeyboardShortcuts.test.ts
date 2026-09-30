import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useKeyboardShortcuts, formatShortcut } from '@/composables/useKeyboardShortcuts'
import type { Shortcut } from '@/composables/useKeyboardShortcuts'

const vueHooks = vi.hoisted(() => ({
  mounted: [] as Array<() => void>,
  unmounted: [] as Array<() => void>,
}))

vi.mock('vue', async () => {
  const actual = await vi.importActual<any>('vue')
  return {
    ...actual,
    onMounted: (cb: () => void) => vueHooks.mounted.push(cb),
    onUnmounted: (cb: () => void) => vueHooks.unmounted.push(cb),
  }
})

const lastMounted = () => vueHooks.mounted[vueHooks.mounted.length - 1]
const lastUnmounted = () => vueHooks.unmounted[vueHooks.unmounted.length - 1]

describe('formatShortcut', () => {
  it('formats Ctrl+S', () => {
    expect(formatShortcut({ key: 's', ctrl: true, handler: () => {} })).toBe('Ctrl+S')
  })

  it('formats Shift+Alt+Escape', () => {
    expect(formatShortcut({ key: 'Escape', shift: true, alt: true, handler: () => {} })).toBe(
      'Shift+Alt+Escape'
    )
  })

  it('formats plain Enter', () => {
    expect(formatShortcut({ key: 'Enter', handler: () => {} })).toBe('Enter')
  })

  it('formats F5', () => {
    expect(formatShortcut({ key: 'F5', handler: () => {} })).toBe('F5')
  })

  it('uppercases single-char keys', () => {
    expect(formatShortcut({ key: 'a', ctrl: true, handler: () => {} })).toBe('Ctrl+A')
  })

  it('formats Shift+1 by physical key（与事件侧归一化口径一致）', () => {
    expect(formatShortcut({ key: '1', shift: true, handler: () => {} })).toBe('Shift+1')
  })
})

describe('useKeyboardShortcuts', () => {
  let handler: ReturnType<typeof vi.fn>

  beforeEach(() => {
    handler = vi.fn()
    document.body.innerHTML = ''
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  function createTestShortcut(overrides: Partial<Shortcut> = {}): Shortcut {
    return {
      key: 's',
      ctrl: true,
      handler,
      description: 'Save',
      group: 'File',
      ...overrides,
    }
  }

  it('returns registered shortcuts', () => {
    const shortcut = createTestShortcut()
    const { registered } = useKeyboardShortcuts([shortcut])
    expect(registered.value).toHaveLength(1)
    expect(registered.value[0].key).toBe('s')
    expect(registered.value[0].ctrl).toBe(true)
  })

  it('register adds a new shortcut', () => {
    const shortcut = createTestShortcut()
    const { registered, register } = useKeyboardShortcuts([])
    register(shortcut)
    expect(registered.value).toHaveLength(1)
  })

  it('register 覆盖同组合键并告警', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const h1 = vi.fn()
    const h2 = vi.fn()
    const { registered, register } = useKeyboardShortcuts([createTestShortcut({ handler: h1 })])
    register(createTestShortcut({ handler: h2 }))
    expect(warnSpy).toHaveBeenCalled()
    expect(registered.value).toHaveLength(1)
    expect(registered.value[0].handler).toBe(h2)
  })

  it('unregister removes a shortcut', () => {
    const shortcut = createTestShortcut()
    const { registered, unregister } = useKeyboardShortcuts([shortcut])
    expect(registered.value).toHaveLength(1)
    unregister(shortcut)
    expect(registered.value).toHaveLength(0)
  })

  it('unregister 部分字段也能移除', () => {
    const { registered, unregister } = useKeyboardShortcuts([createTestShortcut()])
    unregister({ key: 's', ctrl: true })
    expect(registered.value).toHaveLength(0)
  })

  it('conflicts detects duplicate combos', () => {
    const h1 = vi.fn()
    const h2 = vi.fn()
    const s1 = createTestShortcut({ handler: h1 })
    const s2 = createTestShortcut({ handler: h2 })
    const { conflicts } = useKeyboardShortcuts([s1, s2])
    expect(conflicts.value).toHaveLength(1)
    expect(conflicts.value[0].combo).toBe('Ctrl+S')
  })

  it('conflicts 只列出重复组合', () => {
    const { conflicts } = useKeyboardShortcuts([
      createTestShortcut(),
      createTestShortcut(),
      createTestShortcut({ key: 'o', ctrl: true }),
    ])
    expect(conflicts.value).toHaveLength(1)
    expect(conflicts.value[0].combo).toBe('Ctrl+S')
  })

  it('groupedShortcuts groups by group', () => {
    const h1 = vi.fn()
    const h2 = vi.fn()
    const h3 = vi.fn()
    const s1 = createTestShortcut({ group: 'File', handler: h1 })
    const s2 = createTestShortcut({ key: 'o', ctrl: true, group: 'File', handler: h2 })
    const s3 = createTestShortcut({ key: 'h', group: 'Help', handler: h3 })
    const { groupedShortcuts } = useKeyboardShortcuts([s1, s2, s3])
    expect(groupedShortcuts.value.has('File')).toBe(true)
    expect(groupedShortcuts.value.has('Help')).toBe(true)
    expect(groupedShortcuts.value.get('File')!.length).toBe(2)
  })

  it('groupedShortcuts 无 group 归入 其他', () => {
    const { groupedShortcuts } = useKeyboardShortcuts([createTestShortcut({ group: undefined })])
    expect(groupedShortcuts.value.has('其他')).toBe(true)
  })

  it('showHelp defaults to false', () => {
    const { showHelp } = useKeyboardShortcuts([])
    expect(showHelp.value).toBe(false)
  })
})

describe('handleKeydown（window 事件驱动）', () => {
  let handler: ReturnType<typeof vi.fn>

  beforeEach(() => {
    handler = vi.fn()
    document.body.innerHTML = ''
    vueHooks.mounted.length = 0
    vueHooks.unmounted.length = 0
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  function attachShortcut(overrides: Partial<Shortcut> = {}): Shortcut[] {
    const shortcuts = [
      {
        key: 's',
        ctrl: true,
        handler,
        ...overrides,
      },
    ]
    useKeyboardShortcuts(shortcuts)
    lastMounted()()
    return shortcuts
  }

  const keyEvent = (init: KeyboardEventInit) =>
    new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...init })

  it('Ctrl+S 触发 handler 且 preventDefault/stopPropagation', () => {
    attachShortcut()
    const ev = keyEvent({ key: 's', ctrlKey: true })
    window.dispatchEvent(ev)
    expect(handler).toHaveBeenCalledTimes(1)
    expect(ev.defaultPrevented).toBe(true)
  })

  it('metaKey 等同 Ctrl', () => {
    attachShortcut()
    window.dispatchEvent(keyEvent({ key: 's', metaKey: true }))
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('未注册的组合键不触发', () => {
    attachShortcut()
    window.dispatchEvent(keyEvent({ key: 'x', ctrlKey: true }))
    expect(handler).not.toHaveBeenCalled()
  })

  it('Shift+Alt+Escape 组合触发', () => {
    attachShortcut({ key: 'Escape', shift: true, alt: true, ctrl: false })
    window.dispatchEvent(keyEvent({ key: 'Escape', shiftKey: true, altKey: true }))
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('输入框内默认禁用', () => {
    attachShortcut()
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.dispatchEvent(keyEvent({ key: 's', ctrlKey: true }))
    expect(handler).not.toHaveBeenCalled()
  })

  it('disabledInInput=false 时输入框内也触发', () => {
    attachShortcut({ disabledInInput: false })
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.dispatchEvent(keyEvent({ key: 's', ctrlKey: true }))
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('contentEditable 元素内禁用', () => {
    attachShortcut()
    const div = document.createElement('div')
    // jsdom 未实现 isContentEditable，实例上覆盖以模拟可编辑元素
    Object.defineProperty(div, 'isContentEditable', { value: true })
    document.body.appendChild(div)
    div.dispatchEvent(keyEvent({ key: 's', ctrlKey: true }))
    expect(handler).not.toHaveBeenCalled()
  })

  it('handler 抛错被捕获并 console.error', () => {
    const errHandler = vi.fn(() => {
      throw new Error('boom')
    })
    const errorSpy = vi.fn()
    const origError = console.error
    console.error = errorSpy as any
    try {
      useKeyboardShortcuts([{ key: 's', ctrl: true, handler: errHandler }])
      lastMounted()()
      window.dispatchEvent(keyEvent({ key: 's', ctrlKey: true }))
      expect(errHandler).toHaveBeenCalledTimes(1)
      expect(errorSpy).toHaveBeenCalledWith('[快捷键] Ctrl+S 执行失败:', expect.any(Error))
    } finally {
      console.error = origError
    }
  })

  it('unmount 后移除监听器不再触发', () => {
    attachShortcut()
    lastUnmounted()()
    window.dispatchEvent(keyEvent({ key: 's', ctrlKey: true }))
    expect(handler).not.toHaveBeenCalled()
  })

  it('register 覆盖后新 handler 生效、旧 handler 失效', () => {
    const h1 = vi.fn()
    const h2 = vi.fn()
    const { register } = useKeyboardShortcuts([
      { key: 's', ctrl: true, handler: h1, group: 'File' },
    ])
    lastMounted()()
    register({ key: 's', ctrl: true, handler: h2, group: 'File' })
    window.dispatchEvent(keyEvent({ key: 's', ctrlKey: true }))
    expect(h1).not.toHaveBeenCalled()
    expect(h2).toHaveBeenCalledTimes(1)
  })

  // ── Shift 组合（e.key 为上档字符）──

  it('Shift+数字：e.key 为 "!" 也能命中注册的 { key: "1", shift: true }', () => {
    attachShortcut({ key: '1', ctrl: false, shift: true })
    window.dispatchEvent(keyEvent({ key: '!', code: 'Digit1', shiftKey: true }))
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('缺少 e.code 时用上档字符还原表命中 Shift+数字', () => {
    attachShortcut({ key: '2', ctrl: false, shift: true })
    window.dispatchEvent(keyEvent({ key: '@', shiftKey: true }))
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('Numpad 数字的 code 同样可反解', () => {
    attachShortcut({ key: '3', ctrl: false, shift: true })
    window.dispatchEvent(keyEvent({ key: '#', code: 'Numpad3', shiftKey: true }))
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('直接注册上档字符 { key: "?", shift: true } 仍可命中（不因归一化丢匹配）', () => {
    attachShortcut({ key: '?', ctrl: false, shift: true })
    window.dispatchEvent(keyEvent({ key: '?', code: 'Slash', shiftKey: true }))
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('Shift+字母：大小写归一化仍然匹配且不重复触发', () => {
    attachShortcut({ key: 's', ctrl: false, shift: true })
    window.dispatchEvent(keyEvent({ key: 'S', code: 'KeyS', shiftKey: true }))
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('未按 Shift 时不得误触发 Shift 组合', () => {
    attachShortcut({ key: '1', ctrl: false, shift: true })
    window.dispatchEvent(keyEvent({ key: '1', code: 'Digit1' }))
    expect(handler).not.toHaveBeenCalled()
  })

  it('Shift + 未知上档字符（无 code、还原表未收录）不触发也不抛错', () => {
    attachShortcut({ key: '1', ctrl: false, shift: true })
    window.dispatchEvent(keyEvent({ key: 'Ω', shiftKey: true }))
    expect(handler).not.toHaveBeenCalled()
  })

  it('Shift+数字与 Ctrl+Shift+数字 互不串扰', () => {
    attachShortcut({ key: '1', ctrl: true, shift: true })
    window.dispatchEvent(keyEvent({ key: '!', code: 'Digit1', shiftKey: true }))
    expect(handler).not.toHaveBeenCalled()
    window.dispatchEvent(keyEvent({ key: '!', code: 'Digit1', ctrlKey: true, shiftKey: true }))
    expect(handler).toHaveBeenCalledTimes(1)
  })
})
