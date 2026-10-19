import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AppLoading from '@/components/common/AppLoading.vue'

describe('common/AppLoading 加载态', () => {
  it('默认渲染 3 行骨架与加载文案', () => {
    const w = mount(AppLoading)
    expect(w.classes()).toContain('app-loading')
    expect(w.findAll('.app-loading__row')).toHaveLength(3)
    expect(w.find('.app-loading__text').text()).toBe('加载中…')
    expect(w.attributes('role')).toBe('status')
    expect(w.attributes('aria-busy')).toBe('true')
  })

  it('rows 可自定义骨架行数', () => {
    const w = mount(AppLoading, { props: { rows: 2 } })
    expect(w.findAll('.app-loading__row')).toHaveLength(2)
  })

  it('rows=0 时仅保留加载文案（不渲染骨架行）', () => {
    const w = mount(AppLoading, { props: { rows: 0 } })
    expect(w.findAll('.app-loading__row')).toHaveLength(0)
    expect(w.find('.app-loading__text').exists()).toBe(true)
  })
})
