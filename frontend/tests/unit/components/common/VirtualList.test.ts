import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import VirtualList from '@/components/common/VirtualList.vue'

function makeItems(n: number): string[] {
  return Array.from({ length: n }, (_, i) => `row-${i}`)
}

function mountList(props: Record<string, unknown> = {}) {
  return mount(VirtualList, {
    props: { items: makeItems(1000), itemHeight: 40, viewportHeight: 400, ...props },
    slots: {
      default: '<span class="cell">{{ params.item }}</span>',
    },
    global: {
      // 用函数式 slot 拿到作用域参数
      stubs: {},
    },
  })
}

/** 让 scoped slot 收到 { item, index } */
function mountWithScopedSlot(props: Record<string, unknown> = {}) {
  return mount(VirtualList, {
    props: { items: makeItems(1000), itemHeight: 40, viewportHeight: 400, ...props },
    slots: {
      default: `<template #default="{ item, index }"><span class="cell" :data-index="index">{{ item }}</span></template>`,
    },
  })
}

describe('VirtualList', () => {
  it('只渲染可视区 + 缓冲行（DOM 行数远小于数据量）', () => {
    const wrapper = mountWithScopedSlot()
    const rows = wrapper.findAll('[data-testid="virtual-list-item"]')
    // viewport 400 / itemHeight 40 = 10 行 + 1 + 缓冲 3 = 14
    expect(rows).toHaveLength(14)
    expect(rows[0].text()).toBe('row-0')
    expect(wrapper.find('.virtual-list__spacer').attributes('style')).toContain('height: 40000px')
  })

  it('滚动后只换窗口内容（首行索引随 scrollTop 变化）', async () => {
    const wrapper = mountWithScopedSlot()
    const container = wrapper.find('[data-testid="virtual-list"]')
    Object.defineProperty(container.element, 'scrollTop', { value: 4000, writable: true })
    await container.trigger('scroll')

    const rows = wrapper.findAll('[data-testid="virtual-list-item"]')
    expect(rows[0].text()).toBe('row-97')
    expect(rows[0].find('.cell').attributes('data-index')).toBe('97')
    // 窗口位移 = start * itemHeight
    expect(wrapper.find('.virtual-list__window').attributes('style')).toContain('translateY(3880px)')
  })

  it('滚到底部不会渲染出 undefined 行', async () => {
    const wrapper = mountWithScopedSlot()
    const container = wrapper.find('[data-testid="virtual-list"]')
    Object.defineProperty(container.element, 'scrollTop', { value: 999999, writable: true })
    await container.trigger('scroll')

    const rows = wrapper.findAll('[data-testid="virtual-list-item"]')
    expect(rows.at(-1)!.text()).toBe('row-999')
  })

  it('空数据 → 不渲染行，总高 0', () => {
    const wrapper = mountWithScopedSlot({ items: [] })
    expect(wrapper.findAll('[data-testid="virtual-list-item"]')).toHaveLength(0)
    expect(wrapper.find('.virtual-list__spacer').attributes('style')).toContain('height: 0px')
  })

  it('height 支持数字与字符串两种写法', () => {
    const numeric = mountWithScopedSlot({ height: 300 })
    expect(numeric.attributes('style')).toContain('height: 300px')

    const css = mountWithScopedSlot({ height: '50vh' })
    expect(css.attributes('style')).toContain('height: 50vh')
  })

  it('未传 viewportHeight 时用容器实测高度（jsdom 为 0 → 仍渲染缓冲行）', () => {
    const wrapper = mountWithScopedSlot({ viewportHeight: undefined })
    // clientHeight 为 0 → 可视 0 行，但仍有 1 + 缓冲 3 行，不至于全白
    expect(wrapper.findAll('[data-testid="virtual-list-item"]').length).toBeGreaterThan(0)
  })

  it('scroll 事件的 target 为空时按 0 处理（不抛错）', async () => {
    const wrapper = mountWithScopedSlot()
    const container = wrapper.find('[data-testid="virtual-list"]')
    // 直接派发无 target 语义的事件
    container.element.dispatchEvent(new Event('scroll'))
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('[data-testid="virtual-list-item"]')[0].text()).toBe('row-0')
  })

  it('scoped slot 收到 index（绝对索引，不是窗口内索引）', () => {
    const wrapper = mountWithScopedSlot()
    const cells = wrapper.findAll('.cell')
    expect(cells[0].attributes('data-index')).toBe('0')
    expect(cells[1].attributes('data-index')).toBe('1')
  })
})
