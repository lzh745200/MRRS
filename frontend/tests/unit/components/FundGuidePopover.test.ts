import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import FundGuidePopover from '@/components/business/FundGuidePopover.vue'

// 测试中 el-popover 被全局 stub，此处覆写为渲染引用槽与默认槽，便于断言文案
const popoverStub = {
  template: '<div class="el-popover-stub"><slot name="reference" /><slot /></div>',
}

describe('FundGuidePopover (T035)', () => {
  it('渲染问号图标与标题', () => {
    const wrapper = mount(FundGuidePopover, {
      props: {
        title: '审批通过',
        precondition: '经费处于「待审批」',
        impact: '通过后进入「已批准」',
        nextStep: '点击「拨付」',
      },
      global: { stubs: { 'el-popover': popoverStub } },
    })
    expect(wrapper.find('.guide-icon').exists()).toBe(true)
    expect(wrapper.html()).toContain('审批通过')
    expect(wrapper.html()).toContain('前置条件')
    expect(wrapper.html()).toContain('后续影响')
    expect(wrapper.html()).toContain('下一步')
  })

  it('接受四项指引属性', () => {
    const wrapper = mount(FundGuidePopover, {
      props: {
        title: '拨付',
        precondition: 'A',
        impact: 'B',
        nextStep: 'C',
      },
      global: { stubs: { 'el-popover': popoverStub } },
    })
    expect(wrapper.html()).toContain('A')
    expect(wrapper.html()).toContain('B')
    expect(wrapper.html()).toContain('C')
  })
})
