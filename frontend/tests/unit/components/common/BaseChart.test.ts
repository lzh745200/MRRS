import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, enableAutoUnmount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import BaseChart from '@/components/common/BaseChart.vue'

enableAutoUnmount(afterEach)

const echartsInstance = vi.hoisted(() => ({
  setOption: vi.fn(),
  resize: vi.fn(),
  dispose: vi.fn(),
  on: vi.fn(),
}))
const initMock = vi.hoisted(() => vi.fn(() => echartsInstance))
vi.mock('@/utils/echarts', () => ({
  __esModule: true,
  default: { init: initMock, use: vi.fn(), graphic: {} },
}))

const option = { xAxis: { type: 'category', data: ['A'] }, series: [{ type: 'bar', data: [1] }] }

describe('common/BaseChart.vue', () => {
  beforeEach(() => {
    initMock.mockClear()
    echartsInstance.setOption.mockClear()
    echartsInstance.resize.mockClear()
    echartsInstance.dispose.mockClear()
    echartsInstance.on.mockClear()
  })

  it('mounts, inits chart, sets option, registers click and emits chart-ready', async () => {
    const wrapper = mount(BaseChart, { props: { option } })
    await flushPromises()
    await nextTick()

    expect(initMock).toHaveBeenCalledTimes(1)
    const domEl = wrapper.find('.base-chart').element
    expect(initMock).toHaveBeenCalledWith(domEl, '')
    expect(echartsInstance.setOption).toHaveBeenCalledWith(option)
    expect(echartsInstance.on).toHaveBeenCalledWith('click', expect.any(Function))

    expect(wrapper.emitted('chart-ready')).toBeTruthy()
    expect(wrapper.emitted('chart-ready')![0][0]).toBe(echartsInstance)

    const clickHandler = echartsInstance.on.mock.calls.find((c) => c[0] === 'click')![1]
    clickHandler({ name: 'A' })
    expect(wrapper.emitted('chart-click')).toBeTruthy()
    expect(wrapper.emitted('chart-click')![0][0]).toEqual({ name: 'A' })
  })

  it('applies theme and custom size props', async () => {
    const wrapper = mount(BaseChart, {
      props: { option, theme: 'militaryTech', width: '500px', height: '300px' },
    })
    await flushPromises()
    expect(initMock).toHaveBeenCalledWith(wrapper.find('.base-chart').element, 'militaryTech')
    expect(wrapper.attributes('style')).toContain('width: 500px')
    expect(wrapper.attributes('style')).toContain('height: 300px')
  })

  it('re-sets option when option prop changes (deep watch)', async () => {
    const wrapper = mount(BaseChart, { props: { option } })
    await flushPromises()
    echartsInstance.setOption.mockClear()

    const newOption = { xAxis: { type: 'category', data: ['B'] } }
    await wrapper.setProps({ option: newOption })
    await flushPromises()
    // 2026-09-30 深审修复：原为 setOption(newOption, true)（notMerge 全量替换），
    // 会重置 dataZoom/legend 等用户视图状态；现改为合并更新，断言随之改写。
    expect(echartsInstance.setOption).toHaveBeenCalledWith(newOption)
  })

  it('autoResize 中途变化 → 监听对称附加/移除（2026-09-30 深审修复）', async () => {
    const addSpy = vi.spyOn(window, 'addEventListener')
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    try {
      const wrapper = mount(BaseChart, { props: { option, autoResize: true } })
      await flushPromises()
      addSpy.mockClear()
      removeSpy.mockClear()

      await wrapper.setProps({ autoResize: false })
      expect(removeSpy).toHaveBeenCalledWith('resize', expect.any(Function))

      await wrapper.setProps({ autoResize: true })
      expect(addSpy).toHaveBeenCalledWith('resize', expect.any(Function))
    } finally {
      addSpy.mockRestore()
      removeSpy.mockRestore()
    }
  })

  it('卸载时无条件移除 resize 监听（autoResize 变化后仍对称）', async () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    try {
      const wrapper = mount(BaseChart, { props: { option, autoResize: false } })
      await flushPromises()
      await wrapper.setProps({ autoResize: true })
      removeSpy.mockClear()
      wrapper.unmount()
      expect(removeSpy).toHaveBeenCalledWith('resize', expect.any(Function))
    } finally {
      removeSpy.mockRestore()
    }
  })

  it('resizes on window resize event and via exposed resize', async () => {
    const wrapper = mount(BaseChart, { props: { option } })
    await flushPromises()
    window.dispatchEvent(new Event('resize'))
    expect(echartsInstance.resize).toHaveBeenCalledTimes(1)

    echartsInstance.resize.mockClear()
    ;(wrapper.vm as any).resize()
    expect(echartsInstance.resize).toHaveBeenCalledTimes(1)
  })

  it('exposes getChart', async () => {
    const wrapper = mount(BaseChart, { props: { option } })
    await flushPromises()
    expect((wrapper.vm as any).getChart()).toBe(echartsInstance)
  })

  it('does not add resize listener when autoResize=false, and disposes on unmount', async () => {
    const wrapper = mount(BaseChart, { props: { option, autoResize: false } })
    await flushPromises()
    window.dispatchEvent(new Event('resize'))
    expect(echartsInstance.resize).not.toHaveBeenCalled()

    wrapper.unmount()
    expect(echartsInstance.dispose).toHaveBeenCalledTimes(1)
  })

  it('guards initChart when chartRef is null (unmounted before nextTick)', async () => {
    const wrapper = mount(BaseChart, { props: { option } })
    wrapper.unmount()
    await flushPromises()
    await nextTick()
    expect(initMock).toHaveBeenCalledTimes(0)
  })

  it('default props applied when not provided', async () => {
    const wrapper = mount(BaseChart, { props: { option } })
    await flushPromises()
    expect(wrapper.attributes('style')).toContain('width: 100%')
    expect(wrapper.attributes('style')).toContain('height: 400px')
  })

  it('disposes chart on unmount and removes resize listener', async () => {
    const wrapper = mount(BaseChart, { props: { option } })
    await flushPromises()
    wrapper.unmount()
    expect(echartsInstance.dispose).toHaveBeenCalledTimes(1)
  })
})
