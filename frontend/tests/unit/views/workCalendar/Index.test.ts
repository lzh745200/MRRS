/**
 * views/work-calendar/Index.vue —— localStorage 事件读取的健壮性守护。
 *
 * 历史缺陷：setup 顶层裸 `JSON.parse` 且不校验形态 —— 脏数据会让整条路由
 * 渲染失败（SyntaxError）或后续 filter 抛 TypeError。本用例锁住"任何脏值都
 * 回退空数组、组件仍可挂载"这一不变量。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

import WorkCalendar from '@/views/work-calendar/Index.vue'

const STORAGE_KEY = 'work_calendar_events'

function mountComp() {
  return mount(WorkCalendar, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-dialog': {
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          props: ['modelValue'],
        },
        'el-select': { template: '<div class="el-select-stub"><slot /></div>' },
        'el-option': { template: '<div class="el-option-stub" />' },
      },
    },
  })
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

describe('work-calendar 本地事件读取', () => {
  it('无缓存 → 空列表，组件正常挂载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).events).toEqual([])
  })

  it('合法数组 → 原样载入', async () => {
    const stored = [{ id: 1, date: '2026-10-06', title: '走访', type: 'primary' }]
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stored))
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).events).toEqual(stored)
  })

  it('JSON 损坏 → 回退空数组且不抛异常', async () => {
    localStorage.setItem(STORAGE_KEY, '{broken-json')
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).events).toEqual([])
  })

  it('合法 JSON 但非数组 → 回退空数组（避免后续 filter 抛 TypeError）', async () => {
    localStorage.setItem(STORAGE_KEY, '{"not": "an array"}')
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).events).toEqual([])
    // 非数组形态下仍能安全调用依赖 events.filter 的方法
    expect((wrapper.vm as any).getEvents(new Date('2026-10-06'))).toEqual([])
  })
})
