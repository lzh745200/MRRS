import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import FirstUseGuide from '@/components/guide/FirstUseGuide.vue'
import { FIRST_USE_GUIDE_PENDING_KEY, firstUseGuideDoneKey, useAuthStore } from '@/stores/auth'

function makeTarget(name: string, rect = { left: 100, right: 300, top: 100, bottom: 150 }) {
  const el = document.createElement('div')
  el.dataset.guide = name
  el.getBoundingClientRect = () =>
    ({
      ...rect,
      width: rect.right - rect.left,
      height: rect.bottom - rect.top,
      x: rect.left,
      y: rect.top,
      toJSON: () => ({}),
    }) as DOMRect
  document.body.appendChild(el)
  return el
}

async function mountGuide(user: { id: number } | null = { id: 7 }) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.user = user as never
  const wrapper = mount(FirstUseGuide, { global: { plugins: [pinia] } })
  await flushPromises()
  await nextTick()
  return wrapper
}

describe('FirstUseGuide.vue', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    document.body.innerHTML = ''
    vi.restoreAllMocks()
  })

  it('没有首登挂起标记时不展示，也不影响页面', async () => {
    const wrapper = await mountGuide()
    expect(wrapper.find('.first-use-guide').exists()).toBe(false)
  })

  it('首登展示第一步，下一步/上一步顺序正确，完成后写入完成标记', async () => {
    sessionStorage.setItem(FIRST_USE_GUIDE_PENDING_KEY, '7')
    makeTarget('dashboard-header')
    const wrapper = await mountGuide()

    expect(wrapper.find('.first-use-guide').exists()).toBe(true)
    expect(wrapper.text()).toContain('第 1 / 4 步')
    expect(wrapper.text()).toContain('欢迎使用工作台')
    // 第一步调用“上一步”是安全空操作
    ;(wrapper.vm as any).goPrev()
    expect(wrapper.text()).toContain('第 1 / 4 步')

    await wrapper.findAll('.guide-btn-primary')[0].trigger('click')
    await nextTick()
    expect(wrapper.text()).toContain('第 2 / 4 步')

    await wrapper
      .findAll('.guide-btn-text')
      .find((b) => b.text() === '上一步')!
      .trigger('click')
    await nextTick()
    expect(wrapper.text()).toContain('第 1 / 4 步')

    // 依次走完 4 步，最后一步按钮为“完成”
    for (let i = 0; i < 3; i++) {
      await wrapper.findAll('.guide-btn-primary')[0].trigger('click')
      await nextTick()
    }
    expect(wrapper.find('.guide-btn-primary').text()).toBe('完成')
    await wrapper.find('.guide-btn-primary').trigger('click')
    expect(wrapper.find('.first-use-guide').exists()).toBe(false)
    expect(localStorage.getItem(firstUseGuideDoneKey(7))).toBe('done')
    expect(sessionStorage.getItem(FIRST_USE_GUIDE_PENDING_KEY)).toBeNull()
  })

  it('跳过指引直接写入完成标记并关闭', async () => {
    sessionStorage.setItem(FIRST_USE_GUIDE_PENDING_KEY, '7')
    const wrapper = await mountGuide()

    await wrapper
      .findAll('.guide-btn-text')
      .find((b) => b.text() === '跳过指引')!
      .trigger('click')
    expect(wrapper.find('.first-use-guide').exists()).toBe(false)
    expect(localStorage.getItem(firstUseGuideDoneKey(7))).toBe('done')
  })

  it('关闭按钮与跳过等效，且不会重新出现', async () => {
    sessionStorage.setItem(FIRST_USE_GUIDE_PENDING_KEY, '7')
    const wrapper = await mountGuide()

    await wrapper.find('.guide-close').trigger('click')
    expect(wrapper.find('.first-use-guide').exists()).toBe(false)
    expect(localStorage.getItem(firstUseGuideDoneKey(7))).toBe('done')

    sessionStorage.setItem(FIRST_USE_GUIDE_PENDING_KEY, '7')
    const second = await mountGuide()
    expect(second.find('.first-use-guide').exists()).toBe(false)
    expect(sessionStorage.getItem(FIRST_USE_GUIDE_PENDING_KEY)).toBeNull()
  })

  it('按锚点定位并高亮目标，覆盖 right/top/bottom 三种位置', async () => {
    const originalWidth = window.innerWidth
    const originalHeight = window.innerHeight
    Object.defineProperty(window, 'innerWidth', { value: 0, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: 0, configurable: true })
    sessionStorage.setItem(FIRST_USE_GUIDE_PENDING_KEY, '7')
    const header = makeTarget('dashboard-header')
    const sidebar = makeTarget('sidebar', { left: 0, right: 240, top: 80, bottom: 700 })
    const quick = makeTarget('dashboard-quick-actions', {
      left: 300,
      right: 900,
      top: 500,
      bottom: 650,
    })
    makeTarget('help-menu', { left: 0, right: 240, top: 400, bottom: 440 })

    const wrapper = await mountGuide()
    expect(header.classList.contains('first-use-guide-target')).toBe(true)
    expect(wrapper.find('.first-use-guide').attributes('style')).toContain('left')

    await wrapper.find('.guide-close').trigger('click')
    // 重新挂载后逐步走到第 2/3 步，确认目标切换与位置计算
    sessionStorage.setItem(FIRST_USE_GUIDE_PENDING_KEY, '7')
    localStorage.removeItem(firstUseGuideDoneKey(7))
    const second = await mountGuide()
    await second.findAll('.guide-btn-primary')[0].trigger('click')
    await nextTick()
    expect(sidebar.classList.contains('first-use-guide-target')).toBe(true)

    await second.findAll('.guide-btn-primary')[0].trigger('click')
    await nextTick()
    expect(quick.classList.contains('first-use-guide-target')).toBe(true)

    window.dispatchEvent(new Event('resize'))
    window.dispatchEvent(new Event('scroll'))
    second.unmount()
    expect(sidebar.classList.contains('first-use-guide-target')).toBe(false)
    Object.defineProperty(window, 'innerWidth', { value: originalWidth, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: originalHeight, configurable: true })
  })

  it('目标不存在时居中展示，且未登录用户不展示', async () => {
    sessionStorage.setItem(FIRST_USE_GUIDE_PENDING_KEY, '7')
    const wrapper = await mountGuide()
    expect(wrapper.find('.first-use-guide').attributes('style')).toContain('translate(-50%, -50%)')

    sessionStorage.setItem(FIRST_USE_GUIDE_PENDING_KEY, '7')
    const anonymous = await mountGuide(null)
    expect(anonymous.find('.first-use-guide').exists()).toBe(false)
  })

  it('关闭时写完成标记失败也不影响关闭', async () => {
    sessionStorage.setItem(FIRST_USE_GUIDE_PENDING_KEY, '7')
    const wrapper = await mountGuide()
    vi.spyOn(window.localStorage, 'setItem').mockImplementation(() => {
      throw new Error('quota exceeded')
    })
    await wrapper.find('.guide-close').trigger('click')
    expect(wrapper.find('.first-use-guide').exists()).toBe(false)
  })

  it('存储不可用时静默降级，登录与页面不受影响', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const auth = useAuthStore()
    auth.user = { id: 7 } as never
    vi.spyOn(window.sessionStorage, 'getItem').mockImplementation(() => {
      throw new Error('storage disabled')
    })
    const wrapper = mount(FirstUseGuide, { global: { plugins: [pinia] } })
    await flushPromises()
    expect(wrapper.find('.first-use-guide').exists()).toBe(false)
  })
})
