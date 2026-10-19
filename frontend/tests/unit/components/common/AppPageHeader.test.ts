import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AppPageHeader from '@/components/common/AppPageHeader.vue'

describe('common/AppPageHeader 页头标准件', () => {
  it('渲染标题与副标题', () => {
    const w = mount(AppPageHeader, {
      props: { title: '帮扶村管理', subtitle: '维护受援行政村基础信息' },
    })
    expect(w.find('.page-header__title').text()).toBe('帮扶村管理')
    expect(w.find('h2.page-header__title').exists()).toBe(true)
    expect(w.find('.page-header__subtitle').text()).toBe('维护受援行政村基础信息')
  })

  it('无副标题时不渲染副标题节点', () => {
    const w = mount(AppPageHeader, { props: { title: '工作台' } })
    expect(w.find('.page-header__subtitle').exists()).toBe(false)
  })

  it('仅 default 插槽时渲染操作区并可容纳多个操作', () => {
    const w = mount(AppPageHeader, {
      props: { title: '项目列表' },
      slots: {
        default: '<button class="op-main">新增</button><button class="op-sub">导出</button>',
      },
    })
    const actions = w.find('.page-header__actions')
    expect(actions.exists()).toBe(true)
    expect(actions.findAll('button')).toHaveLength(2)
    expect(w.find('.op-main').text()).toBe('新增')
  })

  it('仅 extra 插槽时同样渲染操作区', () => {
    const w = mount(AppPageHeader, {
      props: { title: '经费列表' },
      slots: { extra: '<span class="probe-extra">统计口径说明</span>' },
    })
    expect(w.find('.page-header__actions .probe-extra').text()).toBe('统计口径说明')
  })

  it('default 与 extra 同时存在时并列渲染', () => {
    const w = mount(AppPageHeader, {
      props: { title: '总览' },
      slots: {
        default: '<button class="probe-default">主操作</button>',
        extra: '<button class="probe-extra">次操作</button>',
      },
    })
    expect(w.find('.page-header__actions .probe-default').exists()).toBe(true)
    expect(w.find('.page-header__actions .probe-extra').exists()).toBe(true)
  })

  it('无任何插槽时不渲染操作区（保留纯标题页头）', () => {
    const w = mount(AppPageHeader, { props: { title: '关于系统' } })
    expect(w.find('.page-header__actions').exists()).toBe(false)
  })
})
