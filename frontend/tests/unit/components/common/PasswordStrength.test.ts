import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PasswordStrength from '@/components/common/PasswordStrength.vue'

describe('common/PasswordStrength.vue', () => {
  it.each([
    ['weak', 'weak', '弱'],
    ['弱', 'weak', '弱'],
    ['medium', 'medium', '中'],
    ['中', 'medium', '中'],
    ['strong', 'strong', '强'],
    ['强', 'strong', '强'],
  ])('passwordStrength=%s -> level %s, text %s', (input, level, text) => {
    const wrapper = mount(PasswordStrength, { props: { passwordStrength: input } })
    expect(wrapper.find('.strength-badge').classes()).toContain(`strength-${level}`)
    expect(wrapper.text()).toBe(text)
  })

  it('handles uppercase strength and unknown value -> none', () => {
    const wrapper = mount(PasswordStrength, { props: { passwordStrength: 'WEAK' } })
    expect(wrapper.find('.strength-badge').classes()).toContain('strength-weak')

    const unknown = mount(PasswordStrength, { props: { passwordStrength: 'random' } })
    expect(unknown.find('.strength-badge').classes()).toContain('strength-none')
    expect(unknown.text()).toBe('未设置')
  })

  it('handles empty string -> none', () => {
    const wrapper = mount(PasswordStrength, { props: { passwordStrength: '' } })
    expect(wrapper.find('.strength-badge').classes()).toContain('strength-none')
    expect(wrapper.text()).toBe('未设置')
  })

  it('handles missing prop -> none (nullish fallback)', () => {
    const wrapper = mount(PasswordStrength)
    expect(wrapper.find('.strength-badge').classes()).toContain('strength-none')
    expect(wrapper.text()).toBe('未设置')
  })
})
