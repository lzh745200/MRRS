/**
 * views/ruralWorks/Index.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：默认标签、路由参数 tab 映射、tabLoaded 初始化、handleTabChange 懒加载标记。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { routeBox } = vi.hoisted(() => ({
  routeBox: { query: {} as Record<string, any> },
}))

vi.mock('vue-router', () => ({ useRoute: () => routeBox, useRouter: () => ({ back: vi.fn(), push: vi.fn() }) }))

vi.mock('@/views/ruralWorks/List.vue', () => ({
  default: { name: 'RuralWorkList', template: '<div class="rw-list" />' },
}))
vi.mock('@/views/ruralWorks/Task.vue', () => ({
  default: { name: 'RuralWorkTask', template: '<div class="rw-task" />' },
}))
vi.mock('@/views/ruralWorks/Analysis.vue', () => ({
  default: { name: 'RuralWorkAnalysis', template: '<div class="rw-analysis" />' },
}))
vi.mock('@/views/ruralWorks/Report.vue', () => ({
  default: { name: 'RuralWorkReport', template: '<div class="rw-report" />' },
}))

import Index from '@/views/ruralWorks/Index.vue'

function mountComp() {
  return mount(Index, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-tabs': {
          template:
            '<div class="el-tabs-stub" @click="$emit(\'tab-change\', \'analysis\'); $emit(\'update:modelValue\', \'report\')"><slot /></div>',
        },
        'el-tab-pane': { template: '<div class="el-tab-pane-stub"><slot /></div>' },
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  routeBox.query = {}
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('ruralWorks/Index.vue', () => {
  it('默认 list 标签', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.activeTab).toBe('list')
    expect(vm.tabLoaded).toEqual({ analysis: false, report: false })
    expect(wrapper.find('.rw-list').exists()).toBe(true)
    expect(wrapper.find('.rw-analysis').exists()).toBe(false)
  })

  it('路由 tab=analysis → 默认 analysis 并加载', async () => {
    routeBox.query = { tab: 'analysis' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.activeTab).toBe('analysis')
    expect(vm.tabLoaded.analysis).toBe(true)
    expect(wrapper.find('.rw-analysis').exists()).toBe(true)
  })

  it('路由 tab=report → 默认 report 并加载', async () => {
    routeBox.query = { tab: 'report' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.activeTab).toBe('report')
    expect(vm.tabLoaded.report).toBe(true)
    expect(wrapper.find('.rw-report').exists()).toBe(true)
  })

  it('路由 tab=tasks → 映射到 task', async () => {
    routeBox.query = { tab: 'tasks' }
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).activeTab).toBe('task')
  })

  it('未知 tab → 原样保留', async () => {
    routeBox.query = { tab: 'unknown' }
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).activeTab).toBe('unknown')
  })

  it('handleTabChange 懒加载标记', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleTabChange('analysis')
    expect(vm.tabLoaded.analysis).toBe(true)
    vm.handleTabChange('report')
    expect(vm.tabLoaded.report).toBe(true)
    vm.handleTabChange('list')
    expect(vm.tabLoaded.analysis).toBe(true)
  })

  it('tabs tab-change 事件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.el-tabs-stub').trigger('click')
    expect((wrapper.vm as any).tabLoaded.analysis).toBe(true)
    expect((wrapper.vm as any).activeTab).toBe('report')
  })
})
