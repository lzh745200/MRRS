import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AppTableToolbar from '@/components/common/AppTableToolbar.vue'

describe('common/AppTableToolbar 列表工具条', () => {
  it('无标题、无 actions 时仅渲染左侧 default 插槽', () => {
    const w = mount(AppTableToolbar, {
      slots: { default: '<span class="probe-filter">筛选条件</span>' },
    })
    expect(w.classes()).toContain('app-table-toolbar')
    expect(w.find('.app-table-toolbar__title').exists()).toBe(false)
    expect(w.find('.app-table-toolbar__actions').exists()).toBe(false)
    expect(w.find('.app-table-toolbar__lead .probe-filter').text()).toBe('筛选条件')
  })

  it('渲染标题与右侧 actions 插槽', () => {
    const w = mount(AppTableToolbar, {
      props: { title: '共 12 条' },
      slots: {
        default: '<span class="probe-filter">筛选条件</span>',
        actions: '<button class="probe-batch">批量删除</button>',
      },
    })
    expect(w.find('.app-table-toolbar__title').text()).toBe('共 12 条')
    expect(w.find('.app-table-toolbar__lead .probe-filter').exists()).toBe(true)
    expect(w.find('.app-table-toolbar__actions .probe-batch').text()).toBe('批量删除')
  })
})
