import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AppEmpty from '@/components/common/AppEmpty.vue'

describe('common/AppEmpty 空态', () => {
  it('默认文案为「暂无数据」，无说明、无操作', () => {
    const w = mount(AppEmpty)
    expect(w.classes()).toContain('app-empty')
    expect(w.find('.app-empty__text').text()).toBe('暂无数据')
    expect(w.find('.app-empty__desc').exists()).toBe(false)
    expect(w.find('.app-empty__actions').exists()).toBe(false)
    expect(w.find('.app-empty__icon').attributes('aria-hidden')).toBe('true')
  })

  it('自定义主文案与补充说明', () => {
    const w = mount(AppEmpty, {
      props: { text: '暂无影像资料', description: '可按帮扶村筛选或上传新照片' },
    })
    expect(w.find('.app-empty__text').text()).toBe('暂无影像资料')
    expect(w.find('.app-empty__desc').text()).toBe('可按帮扶村筛选或上传新照片')
  })

  it('default 插槽渲染引导操作', () => {
    const w = mount(AppEmpty, {
      slots: { default: '<button class="probe-action">新增一户一档</button>' },
    })
    expect(w.find('.app-empty__action .probe-action').text()).toBe('新增一户一档')
  })
})
