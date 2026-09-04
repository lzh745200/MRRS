/**
 * components/common/ChangeHistoryDialog.vue 覆盖补齐
 * 目标：formatValue 四分支（null / undefined / 空串 / 对象 / 标量）
 *      + el-dialog 关闭事件回写 update:visible（双向绑定契约）
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import ChangeHistoryDialog from '@/components/common/ChangeHistoryDialog.vue'

function mountDialog() {
  return mount(ChangeHistoryDialog, {
    props: { visible: true, history: [] },
  })
}

describe('ChangeHistoryDialog.formatValue', () => {
  it('null / undefined / 空串 → （空）', () => {
    const w = mountDialog()
    const vm = w.vm as any
    expect(vm.formatValue(null)).toBe('（空）')
    expect(vm.formatValue(undefined)).toBe('（空）')
    expect(vm.formatValue('')).toBe('（空）')
    w.unmount()
  })

  it('对象 → JSON 字符串', () => {
    const w = mountDialog()
    const vm = w.vm as any
    expect(vm.formatValue({ a: 1 })).toBe('{"a":1}')
    expect(vm.formatValue([1, 2])).toBe('[1,2]')
    w.unmount()
  })

  it('标量 → String 化', () => {
    const w = mountDialog()
    const vm = w.vm as any
    expect(vm.formatValue(0)).toBe('0')
    expect(vm.formatValue('x')).toBe('x')
    expect(vm.formatValue(false)).toBe('false')
    w.unmount()
  })
})

/**
 * el-dialog 的 `@update:model-value="$emit('update:visible', $event)"` 转发链。
 *
 * 全局默认桩（stubs: {'el-dialog': true}）不会发出 update:modelValue，
 * 所以该内联处理器此前从未被执行（函数覆盖率缺口）。
 * 这里用能主动 emit 的自定义桩驱动，验证：
 *   关闭（false）与开启（true）两个方向都如实转发给父级，
 *   不会把事件名误写成 modelValue 而让父级 v-model:visible 失效。
 */
const ElDialogStub = {
  name: 'ElDialog',
  props: {
    modelValue: { type: Boolean, default: false },
    title: { type: String, default: '' },
    width: { type: String, default: '' },
    appendToBody: { type: Boolean, default: false },
  },
  emits: ['update:modelValue'],
  template:
    '<div class="el-dialog-stub" :data-title="title" :data-open="String(modelValue)"><slot /></div>',
}

function mountWithDialogStub(props: Record<string, unknown>) {
  return mount(ChangeHistoryDialog, {
    props,
    global: {
      stubs: {
        'el-dialog': ElDialogStub,
        'el-empty': { template: '<div class="el-empty-stub" />' },
        'el-timeline': { template: '<div class="el-timeline-stub"><slot /></div>' },
        'el-timeline-item': {
          props: ['timestamp', 'type'],
          template:
            '<div class="el-timeline-item-stub" :data-ts="timestamp" :data-type="String(type)"><slot /></div>',
        },
      },
    },
  })
}

describe('ChangeHistoryDialog update:visible 转发', () => {
  it('对话框关闭（false）→ 向父级发 update:visible false', async () => {
    const w = mountWithDialogStub({ visible: true, history: [] })
    const dialog = w.findComponent(ElDialogStub)
    expect(dialog.exists()).toBe(true)

    dialog.vm.$emit('update:modelValue', false)
    expect(w.emitted('update:visible')).toEqual([[false]])
    w.unmount()
  })

  it('对话框开启（true）→ 同样如实转发', async () => {
    const w = mountWithDialogStub({ visible: false, history: [] })
    w.findComponent(ElDialogStub).vm.$emit('update:modelValue', true)
    expect(w.emitted('update:visible')).toEqual([[true]])
    w.unmount()
  })

  it('多次开关 → 事件按序全部转发（不去重不丢帧）', async () => {
    const w = mountWithDialogStub({ visible: true, history: [] })
    const dialog = w.findComponent(ElDialogStub)
    dialog.vm.$emit('update:modelValue', false)
    dialog.vm.$emit('update:modelValue', true)
    dialog.vm.$emit('update:modelValue', false)
    expect(w.emitted('update:visible')).toEqual([[false], [true], [false]])
    w.unmount()
  })

  it('title/append-to-body 按契约透传，visible 映射为 model-value', () => {
    const w = mountWithDialogStub({ visible: true, history: [] })
    const dialog = w.findComponent(ElDialogStub)
    expect(dialog.props('title')).toBe('变更历史')
    expect(dialog.props('width')).toBe('680px')
    expect(dialog.props('appendToBody')).toBe(true)
    expect(dialog.props('modelValue')).toBe(true)
    w.unmount()
  })

  it('history 缺失 → el-empty 空态；有 changes 的节点 type=primary', () => {
    const empty = mountWithDialogStub({ visible: true })
    expect(empty.find('.el-empty-stub').exists()).toBe(true)
    expect(empty.find('.el-timeline-stub').exists()).toBe(false)
    empty.unmount()

    const w = mountWithDialogStub({
      visible: true,
      history: [
        { time: '2024-01-01', action: '修改', user: '张三', changes: [{ field: '金额', old_value: 1, new_value: 2 }] },
        { time: '2024-01-02', action: '查看', user: '李四' },
      ],
    })
    const items = w.findAll('.el-timeline-item-stub')
    expect(items).toHaveLength(2)
    // 有字段变更 → primary；无变更 → undefined（桩渲染为 'undefined'）
    expect(items[0].attributes('data-type')).toBe('primary')
    expect(items[1].attributes('data-type')).toBe('undefined')
    expect(w.findAll('.change-field-row')).toHaveLength(1)
    expect(w.text()).toContain('修改 by 张三')
    w.unmount()
  })
})
