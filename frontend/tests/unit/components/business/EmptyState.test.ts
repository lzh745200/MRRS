import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import EmptyState from '@/components/business/EmptyState/EmptyState.vue'

function mountComp(props: Record<string, unknown> = {}) {
  return mount(EmptyState, {
    props,
    global: {
      stubs: {
        'el-empty': {
          name: 'ElEmpty',
          template:
            '<div class="el-empty-stub" :data-desc="description"><slot /></div>',
          props: ['description', 'imageSize'],
        },
        'el-button': {
          name: 'ElButton',
          template:
            '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          props: ['type', 'size'],
        },
      },
    },
  })
}

describe('EmptyState 空态标准件', () => {
  it('默认 no-data 文案渲染', () => {
    const w = mountComp()
    expect(w.find('.el-empty-stub').attributes('data-desc')).toBe('暂无数据')
  })

  it('四种 type 对应默认文案', () => {
    expect(mountComp({ type: 'no-search' }).find('.el-empty-stub').attributes('data-desc')).toContain('未找到匹配结果')
    expect(mountComp({ type: 'no-permission' }).find('.el-empty-stub').attributes('data-desc')).toContain('暂无访问权限')
    expect(mountComp({ type: 'error' }).find('.el-empty-stub').attributes('data-desc')).toContain('加载失败')
    expect(mountComp({ type: 'no-data' }).find('.el-empty-stub').attributes('data-desc')).toBe('暂无数据')
  })

  it('text 覆盖默认文案', () => {
    const w = mountComp({ text: '自定义空态' })
    expect(w.find('.el-empty-stub').attributes('data-desc')).toBe('自定义空态')
  })

  it('action 按钮渲染并触发 action 事件', async () => {
    const w = mountComp({ action: '新增记录' })
    const btn = w.find('.el-button-stub')
    expect(btn.exists()).toBe(true)
    await btn.trigger('click')
    expect(w.emitted('action')).toBeTruthy()
  })

  it('无 action 时无按钮', () => {
    const w = mountComp()
    expect(w.find('.el-button-stub').exists()).toBe(false)
  })
})
