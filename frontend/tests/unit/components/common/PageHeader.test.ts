import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import PageHeader from '@/components/common/PageHeader.vue'

const pushMock = vi.fn()
const backMock = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock, back: backMock }),
}))
vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushMock }),
}))

describe('common/PageHeader 页头标准件', () => {
  it('渲染标题与副标题', () => {
    const w = mount(PageHeader, {
      props: { title: '经费管理', subtitle: '管理帮扶经费记录' },
    })
    expect(w.find('.header-title').text()).toBe('经费管理')
    expect(w.find('.header-subtitle').text()).toBe('管理帮扶经费记录')
  })

  it('无副标题时不渲染 subtitle 节点', () => {
    const w = mount(PageHeader, { props: { title: '工作台' } })
    expect(w.find('.header-subtitle').exists()).toBe(false)
  })

  it('extra 插槽内容渲染在右侧操作区', () => {
    const w = mount(PageHeader, {
      props: { title: '列表' },
      slots: { extra: '<button class="probe-btn">新增</button>' },
    })
    expect(w.find('.header-extra .probe-btn').exists()).toBe(true)
  })

  it('showBack 显示返回按钮，backTo 优先跳转', async () => {
    const w = mount(PageHeader, {
      props: { title: '详情', showBack: true, backTo: '/funds' },
    })
    expect(w.find('.back-btn').exists()).toBe(true)
    await w.find('.back-btn').trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/funds')
  })

  it('无 backTo 时走 router.back()', async () => {
    pushMock.mockClear()
    backMock.mockClear()
    // jsdom 全新会话 history.length===1，组件有 >1 守卫；模拟已有历史
    Object.defineProperty(window.history, 'length', { value: 3, configurable: true })
    const w = mount(PageHeader, {
      props: { title: '详情', showBack: true },
    })
    await w.find('.back-btn').trigger('click')
    expect(backMock).toHaveBeenCalled()
    expect(pushMock).not.toHaveBeenCalled()
    Object.defineProperty(window.history, 'length', { value: 1, configurable: true })
  })

  it('metrics 插槽按需渲染', () => {
    const w = mount(PageHeader, {
      props: { title: '总览' },
      slots: { metrics: '<span class="metric">共12条</span>' },
    })
    expect(w.find('.header-metrics .metric').text()).toContain('共12条')
  })
})
