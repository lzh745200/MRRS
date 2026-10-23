/**
 * components/import/ImportPreviewDialog.vue 测试（四指标 100%）。
 *
 * 方案：stub element-plus 组件为带插槽/事件的真实标签，覆盖——
 * 信息项渲染与缺省、重复导入告警两分支、差异冲突标签两分支、
 * 策略切换 emit、确认/取消 emit、visible 双向绑定。
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ImportPreviewDialog from '@/components/import/ImportPreviewDialog.vue'

const stubs = {
  'el-dialog': {
    props: ['modelValue', 'title'],
    emits: ['update:modelValue'],
    template:
      '<div class="dialog"><div class="dialog-title">{{ title }}</div><slot /><slot name="footer" /></div>',
  },
  'el-descriptions': { template: '<div class="desc"><slot /></div>' },
  'el-descriptions-item': {
    props: ['label'],
    template: '<div class="desc-item">{{ label }}:<slot /></div>',
  },
  'el-alert': { props: ['title'], template: '<div class="alert">{{ title }}</div>' },
  'el-table': { props: ['data'], template: '<table><slot /></table>' },
  'el-table-column': {
    props: ['label'],
    template:
      '<th>{{ label }}<template v-for="row in ($parent.$props.data || [])" :key="row.label"><slot :row="row" /></template></th>',
  },
  'el-tag': { template: '<span class="tag"><slot /></span>' },
  'el-radio-group': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<div class="radios" @click="$emit(\'update:modelValue\', \'package\')"><slot /></div>',
  },
  'el-radio': { props: ['value'], template: '<span class="radio"><slot /></span>' },
  'el-button': { template: '<button><slot /></button>' },
}

function factory(props: Record<string, unknown> = {}) {
  return mount(ImportPreviewDialog, {
    props: { visible: true, ...props },
    global: { stubs },
  })
}

describe('components/import/ImportPreviewDialog', () => {
  it('渲染包信息；缺省字段回显 —', () => {
    const wrapper = factory({
      info: {
        type: '数据包',
        sourceOrgCode: '520000',
        checksum: 'abcdef1234567890',
        recordCount: 12,
        fileName: 'a.zip',
      },
    })
    const text = wrapper.text()
    expect(text).toContain('数据包')
    expect(text).toContain('520000')
    expect(text).toContain('abcdef123456')
    expect(text).toContain('12')
    expect(text).toContain('a.zip')
  })

  it('info 为空时全部回显 —', () => {
    const wrapper = factory()
    expect(wrapper.vm.infoItems.every((i) => i.value === '—')).toBe(true)
  })

  it('无重复：不显示告警，确认按钮可用', () => {
    const wrapper = factory()
    expect(wrapper.find('.alert').exists()).toBe(false)
    expect(wrapper.vm.hasDuplicate).toBe(false)
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBe(2)
  })

  it('有重复：显示告警（缺省时间/操作人兜底），且确认按钮禁用', () => {
    const wrapper = factory({ duplicate: {} })
    expect(wrapper.find('.alert').exists()).toBe(true)
    expect(wrapper.text()).toContain('未知时间')
    expect(wrapper.text()).toContain('未知操作人')
    expect(wrapper.vm.duplicateTitle).toContain('导入过')
  })

  it('有重复但 allowForce：确认按钮可用（force 放行）', () => {
    const wrapper = factory({
      duplicate: { createdAt: '2026-10-23T08:00:00', username: 'admin' },
      allowForce: true,
    })
    expect(wrapper.text()).toContain('2026-10-23T08:00:00')
    expect(wrapper.text()).toContain('admin')
    const confirmBtn = wrapper.findAll('button')[1]
    expect(confirmBtn.attributes('disabled')).toBeUndefined()
  })

  it('差异表：冲突行显示“存在冲突”，否则“无冲突”', () => {
    const wrapper = factory({
      diff: [
        { label: '帮扶村', incoming: 3, local: 2, conflict: true },
        { label: '项目', incoming: 1, local: 1, conflict: false },
      ],
    })
    expect(wrapper.text()).toContain('存在冲突')
    expect(wrapper.text()).toContain('无冲突')
  })

  it('策略切换 emit update:strategy', async () => {
    const wrapper = factory()
    await wrapper.find('.radios').trigger('click')
    expect(wrapper.emitted('update:strategy')?.[0]).toEqual(['package'])
  })

  it('确认/取消 emit 对应事件', async () => {
    const wrapper = factory()
    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    expect(wrapper.emitted('cancel')).toHaveLength(1)
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })

  it('关闭弹窗 emit update:visible=false', () => {
    const wrapper = factory()
    wrapper.vm.onVisibleChange(false)
    expect(wrapper.emitted('update:visible')?.[0]).toEqual([false])
  })

  it('暴露策略选项（3 档，默认逐条比对）', () => {
    const wrapper = factory()
    expect(wrapper.vm.STRATEGY_OPTIONS).toHaveLength(3)
    expect(wrapper.props('strategy')).toBe('compare')
  })
})
