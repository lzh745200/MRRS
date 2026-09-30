import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StatsCard from '@/components/common/StatsCard.vue'

const DummyIcon = { template: '<svg class="dummy-icon"><path /></svg>' }

const stubs = { 'el-icon': { name: 'ElIcon', template: '<i class="el-icon"><slot /></i>' } }

describe('common/StatsCard.vue', () => {
  it('renders title, numeric value with prefix/suffix, subtitle and trend up', () => {
    const wrapper = mount(StatsCard, {
      props: { title: '总经费', value: 1234, prefix: '¥', suffix: '元', subtitle: '今年', trend: 5 },
    })
    expect(wrapper.text()).toContain('总经费')
    expect(wrapper.text()).toContain('¥1,234元')
    expect(wrapper.text()).toContain('今年')
    expect(wrapper.find('.stats-card__trend--up').exists()).toBe(true)
    expect(wrapper.find('.stats-card__trend').text()).toBe('+5%')
  })

  it('renders trend down with minus sign', () => {
    const wrapper = mount(StatsCard, { props: { title: 'T', value: 1, trend: -3 } })
    expect(wrapper.find('.stats-card__trend--down').exists()).toBe(true)
    expect(wrapper.find('.stats-card__trend').text()).toBe('-3%')
  })

  it('renders no trend when trend is undefined', () => {
    const wrapper = mount(StatsCard, { props: { title: 'T', value: 1 } })
    expect(wrapper.find('.stats-card__trend').exists()).toBe(false)
  })

  // 2026-09-30 深审修复：非数字载荷（any 合并）原先直接 toLocaleString → 抛 TypeError / 渲染 NaN
  it('renders placeholder for non-finite numeric values', () => {
    expect(
      mount(StatsCard, { props: { title: 'T', value: NaN, prefix: '¥', suffix: '元' } })
        .find('.stats-card__value')
        .text()
    ).toBe('-')
    expect(
      mount(StatsCard, { props: { title: 'T', value: Infinity } }).find('.stats-card__value').text()
    ).toBe('-')
    expect(
      mount(StatsCard, { props: { title: 'T', value: null as any } }).find('.stats-card__value').text()
    ).toBe('-')
    expect(
      mount(StatsCard, { props: { title: 'T', value: undefined as any } })
        .find('.stats-card__value')
        .text()
    ).toBe('-')
  })

  it('renders string value as-is', () => {
    const wrapper = mount(StatsCard, { props: { title: 'T', value: '1,234' } })
    expect(wrapper.find('.stats-card__value').text()).toBe('1,234')
  })

  it('renders icon component and type class', () => {
    const wrapper = mount(StatsCard, {
      props: { title: 'T', value: 1, icon: DummyIcon, type: 'success' },
      global: { stubs },
    })
    expect(wrapper.find('.dummy-icon').exists()).toBe(true)
    expect(wrapper.classes()).toContain('stats-card--success')
  })

  it('renders without subtitle', () => {
    const wrapper = mount(StatsCard, { props: { title: 'T', value: 1 } })
    expect(wrapper.find('.stats-card__subtitle').exists()).toBe(false)
  })
})
