import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

import BulkPasteDialog from '@/components/common/BulkPasteDialog.vue'

const COLUMNS = [
  { key: 'village', label: '帮扶村', required: true },
  { key: 'year', label: '年度', required: true },
  { key: 'amount', label: '金额' },
]

function mountDialog(props: Record<string, unknown> = {}) {
  return mount(BulkPasteDialog, {
    props: { visible: true, columns: COLUMNS, ...props },
    global: {
      stubs: {
        'el-dialog': {
          template:
            '<div class="el-dialog-stub"><button class="dlg-close" @click="$emit(\'update:model-value\', false)">x</button><slot /><slot name="footer" /></div>',
        },
        'el-input': {
          props: ['modelValue'],
          template:
            '<textarea class="el-input-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        'el-button': {
          props: ['disabled'],
          template:
            '<button class="el-button-stub" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
        },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-alert': {
          props: ['title'],
          template: '<div class="el-alert-stub">{{ title }}</div>',
        },
        'el-table': { props: ['data'], template: '<div class="el-table-stub" />' },
        'el-table-column': { template: '<div />' },
      },
    },
  })
}

async function typeText(wrapper: ReturnType<typeof mountDialog>, text: string) {
  const input = wrapper.find('.el-input-stub')
  await input.setValue(text)
  await nextTick()
}

describe('BulkPasteDialog', () => {
  it('默认提示与表头列含义可见（含必填星标）', () => {
    const wrapper = mountDialog()
    expect(wrapper.find('[data-testid="bulk-paste-hint"]').text()).toContain('Excel')
    expect(wrapper.find('[data-testid="bulk-paste-columns"]').text()).toContain('帮扶村')
    expect(wrapper.text()).toContain('*')
  })

  it('自定义 hint 覆盖默认提示', () => {
    const wrapper = mountDialog({ hint: '自定义说明' })
    expect(wrapper.find('[data-testid="bulk-paste-hint"]').text()).toBe('自定义说明')
  })

  it('解析出多行后展示汇总与预览', async () => {
    const wrapper = mountDialog()
    await typeText(wrapper, '甲村\t2024\t100\n乙村\t2024\t200')
    expect(wrapper.find('[data-testid="bulk-paste-summary"]').text()).toContain('2')
    expect(wrapper.find('[data-testid="bulk-paste-preview"]').exists()).toBe(true)
  })

  it('行**多**于目标列 → 警告且禁止确认（错位必须人工核对）', async () => {
    const wrapper = mountDialog()
    await typeText(wrapper, '甲村\t2024\t100\t多余列')
    expect(wrapper.find('[data-testid="bulk-paste-mismatch"]').text()).toContain('第 1 行')
    const confirm = wrapper.find('[data-testid="bulk-paste-confirm"]')
    expect(confirm.attributes('disabled')).toBeDefined()
  })

  it('超行数上限 → 错误提示且禁止确认（不静默截断）', async () => {
    const wrapper = mountDialog({ maxRows: 2 })
    await typeText(wrapper, '甲\t1\t1\n乙\t2\t2\n丙\t3\t3')
    expect(wrapper.find('[data-testid="bulk-paste-exceeded"]').text()).toContain('行数超过上限')
    expect(wrapper.find('[data-testid="bulk-paste-preview"]').exists()).toBe(false)
  })

  it('超列数上限 → 错误提示指向列数', async () => {
    const wrapper = mountDialog({ maxCols: 2 })
    await typeText(wrapper, 'a\tb\tc')
    expect(wrapper.find('[data-testid="bulk-paste-exceeded"]').text()).toContain('列数超过上限')
  })

  it('空输入 → 无汇总、确认禁用', async () => {
    const wrapper = mountDialog()
    await typeText(wrapper, '   ')
    expect(wrapper.find('[data-testid="bulk-paste-summary"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="bulk-paste-confirm"]').attributes('disabled')).toBeDefined()
  })

  it('列数一致 → 确认回传二维数组并关闭', async () => {
    const wrapper = mountDialog()
    await typeText(wrapper, '甲村\t2024\t100\n乙村\t2024\t')
    const confirm = wrapper.find('[data-testid="bulk-paste-confirm"]')
    expect(confirm.attributes('disabled')).toBeUndefined()
    await confirm.trigger('click')

    const events = wrapper.emitted('confirm')
    expect(events).toBeTruthy()
    expect(events?.[0][0]).toEqual([
      ['甲村', '2024', '100'],
      // 行尾空单元格被 Excel 省略 → 自动补空到 3 列（常态，不算错位）
      ['乙村', '2024', ''],
    ])
    expect(wrapper.emitted('update:visible')?.[0]).toEqual([false])
  })

  it('行尾缺列自动补空 → 不报错、允许确认', async () => {
    const wrapper = mountDialog()
    await typeText(wrapper, '甲村\t2024')
    expect(wrapper.find('[data-testid="bulk-paste-mismatch"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="bulk-paste-confirm"]').attributes('disabled')).toBeUndefined()
  })

  it('取消 → 抛 cancel 并关闭', async () => {
    const wrapper = mountDialog()
    await wrapper.find('[data-testid="bulk-paste-cancel"]').trigger('click')
    expect(wrapper.emitted('cancel')).toBeTruthy()
    expect(wrapper.emitted('update:visible')?.[0]).toEqual([false])
  })

  it('关闭（onVisibleChange false / visible 变 false）会清空残留文本', async () => {
    const wrapper = mountDialog()
    await typeText(wrapper, '甲村\t2024\t100')
    expect((wrapper.find('.el-input-stub').element as HTMLTextAreaElement).value).toContain('甲村')

    // 外部关闭：visible 由 true → false
    await wrapper.setProps({ visible: false })
    await nextTick()
    expect((wrapper.find('.el-input-stub').element as HTMLTextAreaElement).value).toBe('')
  })

  it('弹窗自身触发的关闭（update:model-value）→ 转成 update:visible 并清空', async () => {
    const wrapper = mountDialog()
    await typeText(wrapper, '甲村\t2024\t100')
    await wrapper.find('.dlg-close').trigger('click')
    expect(wrapper.emitted('update:visible')?.[0]).toEqual([false])
    await nextTick()
    expect((wrapper.find('.el-input-stub').element as HTMLTextAreaElement).value).toBe('')
  })

  it('空单元格在预览矩阵里显式标为 —（判定放在脚本里，可被直接断言）', async () => {
    const wrapper = mountDialog()
    await typeText(wrapper, '甲村\t2024')
    const vm = wrapper.vm as unknown as {
      previewMatrix: { cells: { text: string; empty: boolean }[] }[]
    }
    expect(vm.previewMatrix[0].cells[2]).toEqual({ text: '—', empty: true })
    expect(vm.previewMatrix[0].cells[0]).toEqual({ text: '甲村', empty: false })
  })

  it('超过预览行数时提示"仅预览前 N 行"（数据仍全量回传）', async () => {
    const wrapper = mountDialog()
    const nine = Array.from({ length: 9 }, (_, i) => `村${i}\t2024\t${i}`).join('\n')
    await typeText(wrapper, nine)
    expect(wrapper.find('[data-testid="bulk-paste-summary"]').text()).toContain('仅预览前')
  })

  it('确认后清空，避免下次打开带入旧数据', async () => {
    const wrapper = mountDialog()
    await typeText(wrapper, '甲村\t2024\t100')
    await wrapper.find('[data-testid="bulk-paste-confirm"]').trigger('click')
    await nextTick()
    expect((wrapper.find('.el-input-stub').element as HTMLTextAreaElement).value).toBe('')
  })

  it('确认按钮在不可确认时点击不产生 confirm 事件', async () => {
    const wrapper = mountDialog()
    await typeText(wrapper, '甲村\t2024\t100\t多余列') // 列数过多
    const spy = vi.fn()
    wrapper.vm.$.emit = spy
    await wrapper.find('[data-testid="bulk-paste-confirm"]').trigger('click')
    expect(wrapper.emitted('confirm')).toBeFalsy()
  })
})
