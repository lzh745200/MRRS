import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import KpiCard from '@/components/business/KpiCard.vue'

const pushMock = vi.fn()
vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushMock }),
}))

describe('business/KpiCard 统计卡标准件', () => {
  beforeEach(() => pushMock.mockClear())

  it('渲染标签/数值/单位，数值千分位', () => {
    const w = mount(KpiCard, {
      props: { label: '经费总额', value: 1234567.5, unit: '万元' },
    })
    expect(w.find('.kpi-card__label').text()).toBe('经费总额')
    expect(w.find('.kpi-card__number').text()).toBe('1,234,567.5')
    expect(w.find('.kpi-card__unit').text()).toBe('万元')
  })

  it('null 值显示 -- 占位', () => {
    const w = mount(KpiCard, { props: { label: '待定' } })
    expect(w.find('.kpi-card__number').text()).toBe('--')
  })

  it('趋势>0 显示上升绿箭头；<0 红色下降', () => {
    const up = mount(KpiCard, { props: { label: 'a', value: 1, trend: 5 } })
    expect(up.find('.kpi-card__trend').classes()).toContain('is-up')
    expect(up.text()).toContain('5%')

    const down = mount(KpiCard, { props: { label: 'b', value: 1, trend: -3 } })
    expect(down.find('.kpi-card__trend').classes()).toContain('is-down')
    expect(down.text()).toContain('3%')
  })

  it('trend=0 显示持平（info 色）且无百分比', () => {
    const w = mount(KpiCard, { props: { label: 'c', value: 1, trend: 0 } })
    expect(w.find('.kpi-card__trend').classes()).toContain('is-flat')
    expect(w.text()).toContain('持平')
    expect(w.text()).not.toContain('%')
  })

  it('invertTrend 反转语义：负向指标下降为绿', () => {
    // 异常数下降(-10)是好事 → is-up 绿色
    const w = mount(KpiCard, {
      props: { label: '异常数', value: 2, trend: -10, invertTrend: true },
    })
    expect(w.find('.kpi-card__trend').classes()).toContain('is-up')
  })

  it('to 路由点击跳转；无 to 不可点击', async () => {
    const clickable = mount(KpiCard, {
      props: { label: 'd', value: 1, to: '/funds' },
    })
    expect(clickable.find('.kpi-card').classes()).toContain('is-clickable')
    await clickable.find('.kpi-card').trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/funds')

    pushMock.mockClear()
    const plain = mount(KpiCard, { props: { label: 'e', value: 1 } })
    await plain.find('.kpi-card').trigger('click')
    expect(pushMock).not.toHaveBeenCalled()
  })

  it('theme 变体类名生效', () => {
    const w = mount(KpiCard, {
      props: { label: 'f', value: 1, theme: 'danger' },
    })
    expect(w.find('.kpi-card').classes()).toContain('theme-danger')
  })
})
