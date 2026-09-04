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

  /**
   * `props.text || DEFAULT_TEXT[props.type] || '暂无数据'` 的最后一档兜底。
   * 上方四种 type 均能命中字典，末位 `|| '暂无数据'` 永不执行。
   * 真实场景：调用方传入未来新增的 type 枚举值（前后端枚举漂移），
   * 字典缺键时必须回落通用文案而不是渲染 undefined。
   */
  it('字典缺键的未知 type → 回落最终兜底文案', () => {
    const w = mountComp({ type: 'not-in-dict' })
    expect(w.find('.el-empty-stub').attributes('data-desc')).toBe('暂无数据')
    // data-type 仍如实透传，便于样式/埋点按原始 type 区分
    expect(w.find('.empty-state').attributes('data-type')).toBe('not-in-dict')
  })

  it('未知 type 但显式传 text → text 优先于兜底', () => {
    const w = mountComp({ type: 'not-in-dict', text: '自定义' })
    expect(w.find('.el-empty-stub').attributes('data-desc')).toBe('自定义')
  })

  it('size 透传 el-empty image-size，缺省 96', () => {
    expect(mountComp({ size: 160 }).findComponent({ name: 'ElEmpty' }).props('imageSize')).toBe(160)
    expect(mountComp().findComponent({ name: 'ElEmpty' }).props('imageSize')).toBe(96)
  })
})
