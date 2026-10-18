/**
 * components/common/MoneyText.vue 单元测试（四指标 100%）
 *
 * 验收口径：0 / 负数 / 空值 / 小数 / 单位 / 人民币大写 全部覆盖，
 * 非空数值与 `format.formatMoney4` 输出逐字符一致（替换处视觉不变）。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MoneyText from '@/components/common/MoneyText.vue'
import { format } from '@/utils'
import { MONEY_PLACEHOLDER } from '@/utils/money'

function mountMoney(props: Record<string, unknown> = {}) {
  return mount(MoneyText, { props })
}

function textOf(wrapper: ReturnType<typeof mountMoney>): string {
  return wrapper.find('.money-text').text()
}

describe('MoneyText', () => {
  it('默认渲染：空值显示占位符 -', () => {
    expect(textOf(mountMoney())).toBe(MONEY_PLACEHOLDER)
    expect(textOf(mountMoney({ value: null }))).toBe('-')
    expect(textOf(mountMoney({ value: undefined }))).toBe('-')
    expect(textOf(mountMoney({ value: '' }))).toBe('-')
  })

  it('0 / 负数 / 小数 与 formatMoney4 逐字符一致', () => {
    expect(textOf(mountMoney({ value: 0 }))).toBe('0')
    expect(textOf(mountMoney({ value: -1234.5678 }))).toBe('-1,234.5678')
    expect(textOf(mountMoney({ value: 100.5 }))).toBe(format.formatMoney4(100.5))
    expect(textOf(mountMoney({ value: 1234567.8 }))).toBe('1,234,567.8')
    expect(textOf(mountMoney({ value: '8888.1234' }))).toBe('8,888.1234')
  })

  it('unit 单位后缀与自定义 placeholder', () => {
    expect(textOf(mountMoney({ value: 12.5, unit: '万元' }))).toBe('12.5万元')
    expect(textOf(mountMoney({ value: null, placeholder: '暂无数据' }))).toBe('暂无数据')
    expect(textOf(mountMoney({ value: null, unit: '万元', placeholder: '--' }))).toBe('--')
  })

  it('uppercase 切换人民币大写', () => {
    expect(textOf(mountMoney({ value: 1234.56, uppercase: true }))).toBe(
      '壹仟贰佰叁拾肆元伍角陆分'
    )
    expect(textOf(mountMoney({ value: 0, uppercase: true }))).toBe('零元整')
    expect(textOf(mountMoney({ value: null, uppercase: true }))).toBe('-')
  })

  it('根元素 class 合并：调用方可追加样式类（视觉不变）', async () => {
    const wrapper = mount(MoneyText, {
      props: { value: 1 },
      attrs: { class: 'amount-text' },
    })
    expect(wrapper.classes()).toContain('money-text')
    expect(wrapper.classes()).toContain('amount-text')
    expect(wrapper.text()).toBe('1')
  })
})
