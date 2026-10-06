/**
 * views/work-calendar/Index.vue —— 全量覆盖 + localStorage 健壮性守护。
 *
 * 背景：该视图此前只被 smoke.test.ts「导入」而**从未挂载**，Vue SFC 未被 instrumentation
 * 覆盖 → 覆盖率报告里呈现"假 100%"。本文件真正挂载它，因此必须把 setup 内所有
 * 函数与模板分支覆盖到 100%（否则 `src/views/**\/*.vue` 门禁会红）。
 *
 * 历史缺陷（本文件守护）：setup 顶层裸 `JSON.parse` 且不校验形态 —— 脏数据会让整条
 * 路由渲染失败（SyntaxError）或后续 filter 抛 TypeError。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { ElMessage } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('element-plus', () => ({ ElMessage }))

import WorkCalendar from '@/views/work-calendar/Index.vue'

const STORAGE_KEY = 'work_calendar_events'

function mountComp() {
  return mount(WorkCalendar, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        // el-calendar 的 #date-cell 作用域插槽承载了本视图全部模板内联函数
        // （isToday/getEvents/selectDate/editEvent）。不渲染该插槽 → 函数覆盖率
        // 只有 61%（v8 按函数统计，内联处理器未创建）。这里注入「今天」的单元格。
        'el-calendar': {
          name: 'ElCalendar',
          template: '<div class="el-calendar-stub"><slot name="date-cell" :data="cell" /></div>',
          computed: {
            cell() {
              const d = new Date()
              const day = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
                d.getDate()
              ).padStart(2, '0')}`
              return { date: d, day }
            },
          },
        },
        'el-tag': {
          name: 'ElTag',
          template: '<span class="el-tag-stub" @click="$emit(\'click\')"><slot /></span>',
          emits: ['click'],
        },
        'el-form': { name: 'ElForm', template: '<form class="el-form-stub"><slot /></form>' },
        'el-form-item': {
          name: 'ElFormItem',
          template: '<div class="el-form-item-stub"><slot /></div>',
        },
        'el-dialog': {
          name: 'ElDialog',
          props: ['modelValue'],
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
        },
        'el-select': {
          name: 'ElSelect',
          template: '<div class="el-select-stub"><slot /></div>',
        },
        'el-option': { name: 'ElOption', template: '<div class="el-option-stub" />' },
        'el-input': { name: 'ElInput', template: '<input class="el-input-stub" />' },
        'el-button': {
          name: 'ElButton',
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-date-picker': {
          name: 'ElDatePicker',
          template: '<input class="el-date-picker-stub" />',
        },
      },
    },
  })
}

beforeEach(() => {
  localStorage.clear()
  ElMessage.success.mockClear()
  ElMessage.warning.mockClear()
})

afterEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

describe('本地事件读取（健壮性）', () => {
  it('无缓存 → 空列表', async () => {
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
    expect((wrapper.vm as any).getEvents(new Date('2026-10-06'))).toEqual([])
  })
})

describe('日期与查询', () => {
  it('isToday / getEvents / formatDate 两侧分支', async () => {
    const today = new Date()
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.isToday(today)).toBe(true)
    expect(vm.isToday(new Date(2000, 0, 1))).toBe(false)
    expect(vm.formatDate(null)).toBe('-')

    const ds = vm.formatDate(today)
    vm.events = [{ id: 1, date: ds, title: 't', type: 'primary' }]
    expect(vm.getEvents(today)).toHaveLength(1)
    expect(vm.getEvents(new Date(2000, 0, 1))).toHaveLength(0)
  })
})

describe('弹窗与增删改', () => {
  it('selectDate → 打开弹窗并预填选中日期', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const d = new Date('2026-10-06')
    vm.selectDate(d)
    expect(vm.selectedDate).toBe(vm.formatDate(d))
    expect(vm.dialogVisible).toBe(true)
    expect(vm.editingId).toBeNull()
    expect(vm.form.date).toBe(vm.formatDate(d))
  })

  it('openDialog：无实参（走 selectedDate/今天 与默认值）与有实参（回填）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 无 selectedDate → 回落到今天
    vm.selectedDate = ''
    vm.openDialog()
    expect(vm.form.title).toBe('')
    expect(vm.form.type).toBe('primary')
    expect(vm.form.date).toBe(vm.formatDate(new Date()))

    // 有实参 → 全字段回填
    vm.editEvent({
      id: 7,
      date: '2026-10-06',
      title: '标题',
      type: 'info',
      description: '描述',
      location: '地点',
    })
    expect(vm.editingId).toBe(7)
    expect(vm.form).toMatchObject({
      date: '2026-10-06',
      title: '标题',
      type: 'info',
      description: '描述',
      location: '地点',
    })
  })

  it('saveEvent：缺日期或标题 → warning 且不落库', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.form.date = ''
    vm.form.title = '标题'
    vm.saveEvent()
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写日期和标题')
    expect(vm.events).toHaveLength(0)

    vm.form.date = '2026-10-06'
    vm.form.title = ''
    vm.saveEvent()
    expect(vm.events).toHaveLength(0)
  })

  it('saveEvent：新增 → 落库并写 localStorage', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.form = { date: '2026-10-06', title: '新增', type: 'primary', description: '', location: '' }
    vm.saveEvent()
    expect(ElMessage.success).toHaveBeenCalledWith('已添加')
    expect(vm.events).toHaveLength(1)
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')).toHaveLength(1)
    expect(vm.dialogVisible).toBe(false)
  })

  it('saveEvent：编辑已存在项 → 覆盖更新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.events = [{ id: 1, date: '2026-10-01', title: '旧', type: 'primary' }]
    vm.editingId = 1
    vm.form = { date: '2026-10-02', title: '新', type: 'primary', description: '', location: '' }
    vm.saveEvent()
    expect(ElMessage.success).toHaveBeenCalledWith('已更新')
    expect(vm.events[0].title).toBe('新')
  })

  it('saveEvent：编辑目标已不存在（idx<0）→ 不新增也不报错', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.events = []
    vm.editingId = 99
    vm.form = { date: '2026-10-02', title: 'x', type: 'primary', description: '', location: '' }
    vm.saveEvent()
    expect(ElMessage.success).toHaveBeenCalledWith('已更新')
    expect(vm.events).toHaveLength(0)
  })

  it('deleteEvent：有 editingId 删除；无 editingId 早退', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.editingId = null
    vm.deleteEvent()
    expect(ElMessage.success).not.toHaveBeenCalled()

    vm.events = [{ id: 2, date: '2026-10-06', title: 't', type: 'primary' }]
    vm.editingId = 2
    vm.deleteEvent()
    expect(ElMessage.success).toHaveBeenCalledWith('已删除')
    expect(vm.events).toHaveLength(0)
    expect(vm.dialogVisible).toBe(false)
  })

  it('closeDialog 复位', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.dialogVisible = true
    vm.editingId = 3
    vm.closeDialog()
    expect(vm.dialogVisible).toBe(false)
    expect(vm.editingId).toBeNull()
  })
})

describe('模板内联处理器（函数覆盖率）', () => {
  it('头部新增按钮 / 日历单元格 / 事件标签 / 表单 v-model / 取消按钮全部触发', async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([
        {
          id: 1,
          date: new Date().toISOString().slice(0, 10),
          title: '事件',
          type: 'primary',
        },
        // type 缺失 → 覆盖模板 :type="(evt.type || 'primary')" 的兜底分支
        { id: 2, date: new Date().toISOString().slice(0, 10), title: '无类型事件' },
      ])
    )
    const wrapper = mountComp()
    await flushPromises()

    // 头部「添加工作安排」（@click="openDialog()"）
    const addBtn = wrapper
      .findAll('.el-button-stub')
      .find((b) => b.text().includes('添加工作安排'))
    expect(addBtn).toBeTruthy()
    await addBtn!.trigger('click')

    // el-calendar v-model（onUpdate:modelValue）
    wrapper.findComponent({ name: 'ElCalendar' }).vm.$emit('update:modelValue', new Date())

    // 日历单元格点击 → selectDate
    const cell = wrapper.find('.calendar-day')
    expect(cell.exists()).toBe(true)
    await cell.trigger('click')

    // 事件标签点击 → editEvent（@click.stop）
    const tag = wrapper.find('.el-tag-stub')
    if (tag.exists()) await tag.trigger('click')

    // 表单 v-model：date-picker / input（标题、地点）/ select（类型）
    wrapper
      .findAllComponents({ name: 'ElDatePicker' })
      .forEach((c) => c.vm.$emit('update:modelValue', '2026-10-06'))
    wrapper
      .findAllComponents({ name: 'ElInput' })
      .forEach((c) => c.vm.$emit('update:modelValue', '文本'))
    wrapper
      .findAllComponents({ name: 'ElSelect' })
      .forEach((c) => c.vm.$emit('update:modelValue', 'info'))

    // 底部「取消」（@click="closeDialog"）
    const cancelBtn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('取消'))
    expect(cancelBtn).toBeTruthy()
    await cancelBtn!.trigger('click')
    expect((wrapper.vm as any).dialogVisible).toBe(false)
  })
})

describe('模板分支', () => {
  it('打开弹窗且带编辑目标 → 渲染删除按钮（v-if editingId）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.editEvent({ id: 5, date: '2026-10-06', title: 't', type: 'primary' })
    await nextTick()
    expect(wrapper.findAll('.el-button-stub').some((b) => b.text().includes('删除'))).toBe(true)
  })

  it('渲染今日与有事件的日期（isToday / getEvents.length 两侧）', async () => {
    const today = new Date()
    const ds = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(
      today.getDate()
    ).padStart(2, '0')}`
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([{ id: 1, date: ds, title: '今日事项', type: 'primary' }])
    )
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.text()).toContain('今日事项')
  })
})
