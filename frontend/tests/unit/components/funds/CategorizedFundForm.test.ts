import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, enableAutoUnmount, flushPromises } from '@vue/test-utils'
import CategorizedFundForm from '@/components/funds/CategorizedFundForm.vue'

enableAutoUnmount(afterEach)

const formValidateMock = vi.hoisted(() => vi.fn())
const formResetMock = vi.hoisted(() => vi.fn())
const stubs = {
  'el-form': {
    name: 'ElForm',
    props: ['model', 'rules', 'labelWidth', 'labelPosition'],
    methods: {
      validate: (cb?: (valid: boolean) => void) => formValidateMock(cb),
      resetFields: () => formResetMock(),
    },
    template: '<form class="el-form"><slot /></form>',
  },
  'el-form-item': {
    name: 'ElFormItem',
    props: ['label', 'prop'],
    template: '<div class="el-form-item"><slot /></div>',
  },
  'el-select': {
    name: 'ElSelect',
    props: ['modelValue', 'placeholder'],
    emits: ['update:modelValue'],
    template:
      '<select class="el-select" :value="modelValue" @change="$emit(\'update:modelValue\', Number($event.target.value))"><slot /></select>',
  },
  'el-option': {
    name: 'ElOption',
    props: ['label', 'value'],
    template: '<option :value="value" />',
  },
  'el-divider': {
    name: 'ElDivider',
    props: ['contentPosition'],
    template: '<div class="el-divider"><slot /></div>',
  },
  'el-row': { name: 'ElRow', props: ['gutter'], template: '<div class="el-row"><slot /></div>' },
  'el-col': { name: 'ElCol', props: ['span'], template: '<div class="el-col"><slot /></div>' },
  'el-input-number': {
    name: 'ElInputNumber',
    props: ['modelValue', 'min', 'precision', 'disabled'],
    emits: ['update:modelValue'],
    template:
      '<input class="el-input-number" :value="modelValue" :disabled="disabled" type="number" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
  },
  'el-input': {
    name: 'ElInput',
    props: ['modelValue', 'type', 'rows', 'placeholder'],
    emits: ['update:modelValue'],
    template:
      '<textarea class="el-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  'el-button': {
    name: 'ElButton',
    props: ['type'],
    emits: ['click'],
    template: '<button class="el-btn" @click="$emit(\'click\')"><slot /></button>',
  },
}

describe('funds/CategorizedFundForm.vue', () => {
  beforeEach(() => {
    formValidateMock.mockReset().mockImplementation((cb?: (valid: boolean) => void) => {
      if (cb) cb(true)
      return Promise.resolve(true)
    })
    formResetMock.mockReset()
  })

  it('initializes form from defaults and renders year options', () => {
    const currentYear = new Date().getFullYear()
    const wrapper = mount(CategorizedFundForm, { global: { stubs } })
    const options = wrapper.findAll('option')
    // 滚动窗口：当前年-10 ~ 当前年+10，共 21 项，降序
    expect(options.length).toBe(21)
    expect(options[0].attributes('value')).toBe(String(currentYear + 10))
    expect(options[10].attributes('value')).toBe(String(currentYear))
    expect(options[20].attributes('value')).toBe(String(currentYear - 10))

    const inputs = wrapper.findAll('.el-input-number')
    expect((inputs[0].element as HTMLInputElement).value).toBe('0')
    expect((inputs[2].element as HTMLInputElement).disabled).toBe(true)
  })

  it('initializes form from initialData and computes remainingAmount', () => {
    const wrapper = mount(CategorizedFundForm, {
      props: { initialData: { year: 2020, totalAmount: 100, usedAmount: 30, remark: '备注' } },
      global: { stubs },
    })
    const inputs = wrapper.findAll('.el-input-number')
    expect((inputs[0].element as HTMLInputElement).value).toBe('100')
    expect((inputs[1].element as HTMLInputElement).value).toBe('30')
    expect((inputs[2].element as HTMLInputElement).value).toBe('70')
    expect((wrapper.find('textarea.el-input').element as HTMLTextAreaElement).value).toBe('备注')
  })

  it('recomputes remainingAmount when total or used changes', async () => {
    const wrapper = mount(CategorizedFundForm, {
      props: { initialData: { totalAmount: 100, usedAmount: 30 } },
      global: { stubs },
    })
    const inputs = wrapper.findAll('.el-input-number')
    await inputs[0].setValue(200)
    await flushPromises()
    expect((inputs[2].element as HTMLInputElement).value).toBe('170')

    await inputs[1].setValue(50)
    await flushPromises()
    expect((inputs[2].element as HTMLInputElement).value).toBe('150')
  })

  it('year select v-model updates formData.year', async () => {
    const currentYear = new Date().getFullYear()
    const wrapper = mount(CategorizedFundForm, { global: { stubs } })
    const select = wrapper.find('select.el-select')
    await select.setValue(currentYear - 1)
    await flushPromises()
    expect((select.element as HTMLSelectElement).value).toBe(String(currentYear - 1))
  })

  it('remaining amount input v-model handler updates formData', async () => {
    const wrapper = mount(CategorizedFundForm, { global: { stubs } })
    const inputs = wrapper.findAll('.el-input-number')
    const remaining = inputs[2].element as HTMLInputElement
    remaining.value = '42'
    remaining.dispatchEvent(new Event('input'))
    await flushPromises()
    expect(remaining.value).toBe('42')
  })

  it('submits form data when validation passes', async () => {
    const wrapper = mount(CategorizedFundForm, {
      props: { initialData: { totalAmount: 100, usedAmount: 40 } },
      global: { stubs },
    })
    const inputs = wrapper.findAll('.el-input-number')
    await inputs[0].setValue(500)
    await flushPromises()
    await (wrapper.find('textarea.el-input') as any).setValue('年度资金')

    const buttons = wrapper.findAll('button.el-btn')
    await buttons[0].trigger('click')
    await flushPromises()

    expect(formValidateMock).toHaveBeenCalled()
    expect(wrapper.emitted('submit')).toBeTruthy()
    const submitted = wrapper.emitted('submit')![0][0] as any
    expect(submitted).toMatchObject({
      totalAmount: 500,
      usedAmount: 40,
      remainingAmount: 460,
      remark: '年度资金',
    })
  })

  it('does not submit when validation fails', async () => {
    formValidateMock.mockImplementation((cb?: (valid: boolean) => void) => {
      if (cb) cb(false)
      return Promise.resolve(false)
    })
    const wrapper = mount(CategorizedFundForm, { global: { stubs } })
    const buttons = wrapper.findAll('button.el-btn')
    await buttons[0].trigger('click')
    await flushPromises()
    expect(wrapper.emitted('submit')).toBeFalsy()
  })

  it('reset button calls form resetFields', async () => {
    const wrapper = mount(CategorizedFundForm, { global: { stubs } })
    const buttons = wrapper.findAll('button.el-btn')
    await buttons[1].trigger('click')
    await flushPromises()
    expect(formResetMock).toHaveBeenCalled()
  })
})
