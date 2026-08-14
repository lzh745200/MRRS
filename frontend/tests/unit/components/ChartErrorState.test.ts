/**
 * ChartErrorState 组件测试：内联错误状态 + 重试（防重复点击）
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ChartErrorState from '@/components/common/ChartErrorState.vue'

const ElButtonStub = {
  name: 'ElButton',
  template: '<button class="el-button-stub" :data-loading="loading" @click="$emit(\'click\')"><slot /></button>',
  props: ['loading'],
}
const ElAlertStub = {
  name: 'ElAlert',
  template: '<div class="el-alert-stub">{{ title }}</div>',
  props: ['title'],
}

function mountComp(props: any = {}) {
  return mount(ChartErrorState, {
    props,
    global: {
      stubs: {
        'el-alert': ElAlertStub,
        'el-button': ElButtonStub,
        'el-icon': true,
        RefreshRight: true,
      },
    },
  })
}

describe('components/common/ChartErrorState', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('默认提示文案为「数据加载失败」', () => {
    const wrapper = mountComp()
    expect(wrapper.text()).toContain('数据加载失败')
  })

  it('自定义 message 透传给 el-alert', () => {
    const wrapper = mountComp({ message: '年度指标加载失败' })
    expect(wrapper.text()).toContain('年度指标加载失败')
  })

  it('点击重试 → 发出 retry 事件，结束后 loading 复位', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    const btn = wrapper.find('.el-button-stub')
    await btn.trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
    // 重试进行中按钮处于 loading
    expect(btn.attributes('data-loading')).toBe('true')
    await vi.advanceTimersByTimeAsync(400)
    expect(btn.attributes('data-loading')).toBe('false')
  })

  it('重试进行中重复点击被忽略（防抖）', async () => {
    vi.useFakeTimers()
    const wrapper = mountComp()
    const btn = wrapper.find('.el-button-stub')
    await btn.trigger('click')
    await btn.trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(400)
  })
})
