import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AppError from '@/components/common/AppError.vue'

describe('common/AppError 错误态', () => {
  it('默认渲染统一错误文案与重试按钮', () => {
    const w = mount(AppError)
    expect(w.classes()).toContain('app-error')
    expect(w.attributes('role')).toBe('alert')
    expect(w.find('.app-error__message').text()).toBe('加载失败，请稍后重试')
    expect(w.find('.app-error__retry').attributes('type')).toBe('button')
    expect(w.find('.app-error__icon').attributes('aria-hidden')).toBe('true')
  })

  it('自定义错误文案', () => {
    const w = mount(AppError, { props: { message: '数据加载超时，请检查服务连接' } })
    expect(w.find('.app-error__message').text()).toBe('数据加载超时，请检查服务连接')
  })

  it('点击重试按钮触发 retry 事件', async () => {
    const w = mount(AppError)
    await w.find('.app-error__retry').trigger('click')
    expect(w.emitted('retry')).toHaveLength(1)
  })
})
