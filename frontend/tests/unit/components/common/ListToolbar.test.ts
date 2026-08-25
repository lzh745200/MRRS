import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import ListToolbar from '@/components/common/ListToolbar.vue'

function mountComp(props: Record<string, unknown> = {}, slots: Record<string, string> = {}) {
  return mount(ListToolbar, {
    props,
    slots,
    global: {
      stubs: {
        'el-button': {
          name: 'ElButton',
          template:
            '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          props: ['type', 'size', 'link'],
        },
        'el-icon': { name: 'ElIcon', template: '<i class="el-icon-stub" />' },
      },
    },
  })
}

describe('ListToolbar 列表工具栏标准件', () => {
  it('渲染 filters 与 tools 两个插槽区', () => {
    const w = mountComp({}, { filters: '<input class="f" />', tools: '<button class="t">新建</button>' })
    expect(w.find('.list-toolbar__filters .f').exists()).toBe(true)
    expect(w.find('.list-toolbar__tools .t').exists()).toBe(true)
  })

  it('filterCount ≤ collapseAfter 时无折叠开关', () => {
    const w = mountComp({ filterCount: 3, collapseAfter: 3 }, { filters: '<div/>' })
    expect(w.find('.el-button-stub').exists()).toBe(false)
  })

  it('filterCount > collapseAfter 时显示折叠开关并可切换', async () => {
    const w = mountComp({ filterCount: 5, collapseAfter: 3 }, { filters: '<div/>' })
    const btn = w.find('.el-button-stub')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toContain('展开全部(5)')
    ;(w.vm as any).expanded = true
    await w.vm.$nextTick()
    expect(w.find('.el-button-stub').text()).toContain('收起')
  })

  it('collapsible=false 时不显示开关', () => {
    const w = mountComp({ collapsible: false, filterCount: 9 }, { filters: '<div/>' })
    expect(w.find('.el-button-stub').exists()).toBe(false)
  })

  it('无插槽时区域不渲染', () => {
    const w = mountComp()
    expect(w.find('.list-toolbar__filters').exists()).toBe(false)
    expect(w.find('.list-toolbar__tools').exists()).toBe(false)
  })
})
