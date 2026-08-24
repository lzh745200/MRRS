/**
 * components/common/ChangeHistoryDialog.vue 覆盖补齐
 * 目标：formatValue 四分支（null / undefined / 空串 / 对象 / 标量）
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
