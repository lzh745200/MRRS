import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { computed, nextTick, reactive } from 'vue'

import {
  DRAFT_STORAGE_PREFIX,
  DRAFT_TTL_DAYS,
  clearDraft,
  draftStorageKey,
  isBlankForm,
  readDraft,
  useFormDraft,
  writeDraft,
} from '@/composables/useFormDraft'

const KEY = 'policies:edit:new'

function seed(key: string, data: Record<string, unknown>, savedAt = Date.now()) {
  localStorage.setItem(draftStorageKey(key), JSON.stringify({ data, savedAt }))
}

beforeEach(() => {
  localStorage.clear()
  vi.useRealTimers()
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('draftStorageKey / 存取', () => {
  it('键带统一前缀（便于一次性清理）', () => {
    expect(draftStorageKey(KEY)).toBe(`${DRAFT_STORAGE_PREFIX}${KEY}`)
  })

  it('写入后可读回，且带 savedAt', () => {
    writeDraft(KEY, { title: '示范村' }, 1000)
    const record = readDraft<{ title: string }>(KEY, 1000)
    expect(record).toEqual({ data: { title: '示范村' }, savedAt: 1000 })
  })

  it('无草稿返回 null', () => {
    expect(readDraft(KEY)).toBeNull()
  })

  it('损坏 JSON 返回 null 不抛错', () => {
    localStorage.setItem(draftStorageKey(KEY), '{oops')
    expect(readDraft(KEY)).toBeNull()
  })

  it('结构不符（缺 data/savedAt）返回 null', () => {
    localStorage.setItem(draftStorageKey(KEY), JSON.stringify({ data: { a: 1 } }))
    expect(readDraft(KEY)).toBeNull()
    localStorage.setItem(draftStorageKey(KEY), JSON.stringify({ savedAt: 1 }))
    expect(readDraft(KEY)).toBeNull()
  })

  it('超过 TTL 自动丢弃并删除存储（不复活半年前的脏数据）', () => {
    const ttlMs = DRAFT_TTL_DAYS * 24 * 60 * 60 * 1000
    seed(KEY, { title: '旧草稿' }, 1000)
    expect(readDraft(KEY, 1000 + ttlMs + 1)).toBeNull()
    expect(localStorage.getItem(draftStorageKey(KEY))).toBeNull()
  })

  it('存储抛错（隐私模式/配额）时静默降级', () => {
    vi.spyOn(localStorage, 'getItem').mockImplementation(() => {
      throw new Error('denied')
    })
    expect(readDraft(KEY)).toBeNull()
    vi.restoreAllMocks()

    vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    expect(() => writeDraft(KEY, { a: 1 })).not.toThrow()
    expect(() => clearDraft(KEY)).not.toThrow()
  })
})

describe('isBlankForm', () => {
  it('全空视为空（空串/纯空格/null/undefined/空数组）', () => {
    expect(isBlankForm({ a: '', b: '   ', c: null, d: undefined, e: [] })).toBe(true)
  })

  it('任一有值即非空（含数字 0 与 false —— 它们是有效输入）', () => {
    expect(isBlankForm({ a: '', b: 0 })).toBe(false)
    expect(isBlankForm({ a: false })).toBe(false)
    expect(isBlankForm({ a: ['x'] })).toBe(false)
  })
})

describe('useFormDraft', () => {
  it('挂载时识别已有草稿并 restore 合并回表单', () => {
    seed(KEY, { title: '已存标题', category: 'industrial' })
    const form = reactive<Record<string, unknown>>({ title: '', category: '' })
    const { hasDraft, restore } = useFormDraft(form, { key: KEY })
    expect(hasDraft.value).toBe(true)
    expect(restore()).toBe(true)
    expect(form.title).toBe('已存标题')
    expect(form.category).toBe('industrial')
  })

  it('无草稿时 restore 返回 false 且不覆盖表单', () => {
    const form = reactive<Record<string, unknown>>({ title: '手输内容' })
    const { hasDraft, restore } = useFormDraft(form, { key: KEY })
    expect(hasDraft.value).toBe(false)
    expect(restore()).toBe(false)
    expect(form.title).toBe('手输内容')
  })

  it('输入后防抖落盘', async () => {
    vi.useFakeTimers()
    const form = reactive<Record<string, unknown>>({ title: '' })
    useFormDraft(form, { key: KEY, debounceMs: 300 })

    form.title = '新增内容'
    await nextTick()
    expect(readDraft(KEY)).toBeNull() // 防抖未到

    vi.advanceTimersByTime(300)
    expect(
      (readDraft<Record<string, unknown>>(KEY) as { data: Record<string, unknown> }).data.title
    ).toBe('新增内容')
  })

  it('清空表单后草稿被移除（不落垃圾）', async () => {
    vi.useFakeTimers()
    const form = reactive<Record<string, unknown>>({ title: 'x' })
    const { flush } = useFormDraft(form, { key: KEY, debounceMs: 10 })
    flush()
    expect(readDraft(KEY)).not.toBeNull()

    form.title = ''
    flush()
    expect(readDraft(KEY)).toBeNull()
  })

  it('clear 清除草稿并重置 hasDraft（提交成功后调用）', () => {
    seed(KEY, { title: 'x' })
    const form = reactive<Record<string, unknown>>({ title: '' })
    const { hasDraft, clear } = useFormDraft(form, { key: KEY })
    expect(hasDraft.value).toBe(true)
    clear()
    expect(hasDraft.value).toBe(false)
    expect(readDraft(KEY)).toBeNull()
  })

  it('flush 立刻落盘（离开页面前兜底）', () => {
    const form = reactive<Record<string, unknown>>({ title: '马上保存' })
    const { flush } = useFormDraft(form, { key: KEY })
    flush()
    expect(
      (readDraft<Record<string, unknown>>(KEY) as { data: Record<string, unknown> }).data.title
    ).toBe('马上保存')
  })

  it('不同业务键互不污染（新建 vs 编辑）', () => {
    writeDraft('policies:edit:new', { title: '新建草稿' })
    writeDraft('policies:edit:42', { title: '编辑草稿' })
    expect(
      (readDraft<Record<string, unknown>>('policies:edit:new') as { data: { title: string } }).data
        .title
    ).toBe('新建草稿')
    expect(
      (readDraft<Record<string, unknown>>('policies:edit:42') as { data: { title: string } }).data
        .title
    ).toBe('编辑草稿')
  })

  it('computed 派生值变化同样触发落盘（deep watch）', async () => {
    vi.useFakeTimers()
    const form = reactive<Record<string, unknown>>({ budget: 1, isRich: computed(() => true) })
    const { flush } = useFormDraft(form, { key: KEY })
    flush()
    const stored = readDraft<Record<string, unknown>>(KEY) as { data: Record<string, unknown> }
    expect(stored.data.budget).toBe(1)
  })

  it('有未触发的防抖定时器时 clear 会取消它（不出手评上留下残影）', async () => {
    vi.useFakeTimers()
    const form = reactive<Record<string, unknown>>({ title: '' })
    const { clear } = useFormDraft(form, { key: KEY, debounceMs: 500 })

    form.title = '被放弃的输入'
    await nextTick()
    clear()
    vi.advanceTimersByTime(500)
    expect(readDraft(KEY)).toBeNull()
  })

  it('组件内使用：卸载时清掉定时器与监听（不留悬挂任务）', async () => {
    vi.useFakeTimers()
    const { mount } = await import('@vue/test-utils')
    const { defineComponent, h } = await import('vue')
    const form = reactive<Record<string, unknown>>({ title: '' })

    const Host = defineComponent({
      setup() {
        useFormDraft(form, { key: KEY, debounceMs: 300 })
        return () => h('div', 'host')
      },
    })
    const wrapper = mount(Host)
    form.title = '组件内输入'
    await nextTick()
    wrapper.unmount()
    vi.advanceTimersByTime(300)
    // 卸载时已取消定时器 → 不应落盘
    expect(readDraft(KEY)).toBeNull()
  })

  it('storage 访问本身抛错时一律降级为 null（隐私模式）', () => {
    const original = Object.getOwnPropertyDescriptor(window, 'localStorage')
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get() {
        throw new Error('SecurityError')
      },
    })
    try {
      expect(readDraft(KEY)).toBeNull()
      expect(() => writeDraft(KEY, { a: 1 })).not.toThrow()
      expect(() => clearDraft(KEY)).not.toThrow()
    } finally {
      if (original) Object.defineProperty(window, 'localStorage', original)
    }
  })

  it('removeItem 抛错时 clearDraft 静默忽略', () => {
    vi.spyOn(localStorage, 'removeItem').mockImplementation(() => {
      throw new Error('denied')
    })
    expect(() => clearDraft(KEY)).not.toThrow()
    vi.restoreAllMocks()
  })

  it('localStorage 不存在（非浏览器环境）时全部降级为 null/no-op', () => {
    vi.stubGlobal('localStorage', undefined)
    try {
      expect(readDraft(KEY)).toBeNull()
      expect(() => writeDraft(KEY, { a: 1 })).not.toThrow()
      expect(() => clearDraft(KEY)).not.toThrow()
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('连续输入只落最后一次（防抖反复取消上一个定时器）', async () => {
    vi.useFakeTimers()
    const form = reactive<Record<string, unknown>>({ title: '' })
    useFormDraft(form, { key: KEY, debounceMs: 200 })

    form.title = 'a'
    await nextTick()
    vi.advanceTimersByTime(100)
    form.title = 'ab'
    await nextTick()
    vi.advanceTimersByTime(200)

    const stored = readDraft<Record<string, unknown>>(KEY) as { data: Record<string, unknown> }
    expect(stored.data.title).toBe('ab')
  })
})
