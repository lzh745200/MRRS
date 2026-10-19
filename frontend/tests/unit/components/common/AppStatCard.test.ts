import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AppStatCard from '@/components/common/AppStatCard.vue'

describe('common/AppStatCard 统计卡', () => {
  it('默认渲染：主色 tone、无单位、无趋势、无图标', () => {
    const w = mount(AppStatCard, { props: { label: '帮扶村', value: 18 } })
    expect(w.classes()).toContain('app-stat-card')
    expect(w.classes()).toContain('app-stat-card--primary')
    expect(w.find('.app-stat-card__label').text()).toBe('帮扶村')
    expect(w.find('.app-stat-card__body').exists()).toBe(true)
    expect(w.find('.kpi-value').text()).toBe('18')
    expect(w.find('.app-stat-card__unit').exists()).toBe(false)
    expect(w.find('.stat-trend').exists()).toBe(false)
    expect(w.find('.app-stat-card__icon').exists()).toBe(false)
  })

  it('渲染单位与图标插槽', () => {
    const w = mount(AppStatCard, {
      props: { label: '经费总额', value: '2,360.50', unit: '万元' },
      slots: { icon: '<svg class="probe-icon" />' },
    })
    expect(w.find('.app-stat-card__unit').text()).toBe('万元')
    expect(w.find('.app-stat-card__icon .probe-icon').exists()).toBe(true)
  })

  it('trend=up 渲染上升趋势并带可访问文案', () => {
    const w = mount(AppStatCard, {
      props: { label: '项目数', value: 42, trend: 'up' },
    })
    const trend = w.find('.stat-trend')
    expect(trend.classes()).toContain('is-up')
    expect(trend.text()).toBe('↑ 上升')
    expect(trend.attributes('title')).toBe('↑ 上升')
    expect(trend.attributes('aria-label')).toBe('↑ 上升')
  })

  it('trend=down 渲染下降趋势', () => {
    const w = mount(AppStatCard, {
      props: { label: '待办', value: 3, trend: 'down' },
    })
    const trend = w.find('.stat-trend')
    expect(trend.classes()).toContain('is-down')
    expect(trend.text()).toBe('↓ 下降')
  })

  it.each(['success', 'warning', 'danger'] as const)('tone=%s 映射到对应语义色 class', (tone) => {
    const w = mount(AppStatCard, { props: { label: '指标', value: 1, tone } })
    expect(w.classes()).toContain(`app-stat-card--${tone}`)
  })
})
