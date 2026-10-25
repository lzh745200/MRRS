/**
 * AppearanceSettings（外观设置面板）单元测试 —— v1.15.0 / W23
 *
 * 唯一执行者：本文件是 `src/components/settings/AppearanceSettings.vue` 的唯一真实执行测试。
 * Element Plus 组件以 stub 替换（项目测试不全局注册 EP），并通过 props/emit 驱动 handler。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

enableAutoUnmount(afterEach)

// vi.mock 工厂会被提升到 import 之前：被工厂引用的变量必须用 vi.hoisted 声明，
// 否则会命中 "Cannot access before initialization"（AppearanceSettings.vue 加载即失败）。
const { elMessageSuccess } = vi.hoisted(() => ({ elMessageSuccess: vi.fn() }))
vi.mock('element-plus', () => ({
  ElMessage: { success: elMessageSuccess },
}))

import AppearanceSettings from '@/components/settings/AppearanceSettings.vue'
import { DEFAULT_UI_PREFS, UI_PREFS_STORAGE_KEY } from '@/composables/useUiPrefs'
import { useConfigStore } from '@/stores/config'

const StubSelect = defineComponent({
  name: 'ElSelectStub',
  props: { modelValue: { type: [String, Number], default: '' } },
  emits: ['update:modelValue'],
  setup(props, { slots }) {
    return () =>
      h('div', { class: 'stub-select', 'data-value': String(props.modelValue) }, slots.default?.())
  },
})
const StubOption = defineComponent({
  name: 'ElOptionStub',
  props: { label: String, value: String },
  setup(props) {
    return () => h('span', { class: 'stub-option' }, `${props.label}:${props.value}`)
  },
})
const StubRadioGroup = defineComponent({
  name: 'ElRadioGroupStub',
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue'],
  setup(_props, { slots }) {
    return () => h('div', { class: 'stub-radio-group' }, slots.default?.())
  },
})
const StubRadioButton = defineComponent({
  name: 'ElRadioButtonStub',
  props: { value: String },
  setup(props, { slots }) {
    return () => h('button', { class: `stub-radio-${props.value}` }, slots.default?.())
  },
})
const StubSwitch = defineComponent({
  name: 'ElSwitchStub',
  props: { modelValue: { type: Boolean, default: false } },
  emits: ['change'],
  setup(props, { emit }) {
    return () =>
      h('button', {
        class: 'stub-switch',
        'data-on': String(props.modelValue),
        onClick: () => emit('change', !props.modelValue),
      })
  },
})
const StubButton = defineComponent({
  name: 'ElButtonStub',
  setup(_props, { slots, attrs }) {
    return () => h('button', { class: 'stub-button', ...attrs }, slots.default?.())
  },
})

const STUBS = {
  'el-select': StubSelect,
  'el-option': StubOption,
  'el-radio-group': StubRadioGroup,
  'el-radio-button': StubRadioButton,
  'el-switch': StubSwitch,
  'el-button': StubButton,
}

function mountPanel() {
  return mount(AppearanceSettings, {
    global: {
      stubs: STUBS,
      mocks: { $t: (k: string) => k },
    },
  })
}

function findRadioGroup(wrapper: ReturnType<typeof mount>, testid: string) {
  return wrapper.find(`[data-testid="${testid}"]`)
}

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
  setActivePinia(createPinia())
})

describe('AppearanceSettings', () => {
  it('渲染主题/字号/密度/高对比/简化/重置控件', () => {
    const wrapper = mountPanel()
    expect(wrapper.find('[data-testid="appearance-settings"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="appearance-theme"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="appearance-font-size"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="appearance-density"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="appearance-contrast"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="appearance-simplify"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="appearance-reset"]').exists()).toBe(true)
  })

  it('主题选择调用 configStore.setTheme', async () => {
    const wrapper = mountPanel()
    const store = useConfigStore()
    const spy = vi.spyOn(store, 'setTheme')
    const select = wrapper.findComponent(StubSelect)
    await select.vm.$emit('update:modelValue', 'outdoor')
    expect(spy).toHaveBeenCalledWith('outdoor')
  })

  it('字号档切换写入偏好 localStorage 与 DOM', async () => {
    const wrapper = mountPanel()
    // 三个 radio-group 顺序：场景预设[0]、字号[1]、密度[2]
    const fontGroup = wrapper.findAllComponents(StubRadioGroup)[1]
    await fontGroup.vm.$emit('update:modelValue', 'large')
    expect(JSON.parse(localStorage.getItem(UI_PREFS_STORAGE_KEY) as string).fontSize).toBe('large')
    expect(document.documentElement.dataset.fontSize).toBe('large')
  })

  // ② 场景预设：一次点击覆盖四个字段，不留"大字 + 舒适行高"这类叠加残余
  it('选择"演示"场景 → 四个字段一次性覆盖', async () => {
    const wrapper = mountPanel()
    const presetGroup = wrapper.findAllComponents(StubRadioGroup)[0]
    await presetGroup.vm.$emit('change', 'presentation')

    const stored = JSON.parse(localStorage.getItem(UI_PREFS_STORAGE_KEY) as string)
    expect(stored).toEqual({
      fontSize: 'large',
      density: 'compact',
      contrast: 'normal',
      simplify: true,
    })
    expect(document.documentElement.dataset.fontSize).toBe('large')
    expect(document.documentElement.dataset.density).toBe('compact')
  })

  it('选择"紧凑"场景 → 小字号 + 紧凑行高 + 简化模式', async () => {
    const wrapper = mountPanel()
    const presetGroup = wrapper.findAllComponents(StubRadioGroup)[0]
    await presetGroup.vm.$emit('change', 'compact')

    const stored = JSON.parse(localStorage.getItem(UI_PREFS_STORAGE_KEY) as string)
    expect(stored.fontSize).toBe('compact')
    expect(stored.density).toBe('compact')
    expect(stored.simplify).toBe(true)
  })

  it('密度档切换写入偏好', async () => {
    const wrapper = mountPanel()
    const densityGroup = wrapper.findAllComponents(StubRadioGroup)[2] // 预设[0]、字号[1]、密度[2]
    await densityGroup.vm.$emit('update:modelValue', 'compact')
    expect(JSON.parse(localStorage.getItem(UI_PREFS_STORAGE_KEY) as string).density).toBe('compact')
  })

  it('高对比开关切换 contrast', async () => {
    const wrapper = mountPanel()
    const contrastSwitch = wrapper.findAllComponents(StubSwitch)[0]
    await contrastSwitch.vm.$emit('change', true)
    expect(JSON.parse(localStorage.getItem(UI_PREFS_STORAGE_KEY) as string).contrast).toBe('high')
    await contrastSwitch.vm.$emit('change', false)
    expect(JSON.parse(localStorage.getItem(UI_PREFS_STORAGE_KEY) as string).contrast).toBe('normal')
  })

  it('简化模式开关切换 simplify', async () => {
    const wrapper = mountPanel()
    const simplifySwitch = wrapper.findAllComponents(StubSwitch)[1]
    await simplifySwitch.vm.$emit('change', true)
    expect(JSON.parse(localStorage.getItem(UI_PREFS_STORAGE_KEY) as string).simplify).toBe(true)
    expect(document.documentElement.dataset.simplify).toBe('true')
  })

  it('重置按钮恢复默认偏好与默认主题并提示', async () => {
    const wrapper = mountPanel()
    const fontGroup = wrapper.findAllComponents(StubRadioGroup)[1] // [0] 是 ② 的场景预设组，字号档在其后
    await fontGroup.vm.$emit('update:modelValue', 'large')
    await wrapper.find('[data-testid="appearance-reset"]').trigger('click')
    const stored = JSON.parse(localStorage.getItem(UI_PREFS_STORAGE_KEY) as string)
    expect(stored).toEqual(DEFAULT_UI_PREFS)
    expect(elMessageSuccess).toHaveBeenCalledWith('已恢复默认外观')
    expect(useConfigStore().theme).toBe('default')
  })

  it('当前主题从 configStore 读取（getter 生效）', () => {
    const store = useConfigStore()
    store.setTheme('outdoor')
    const wrapper = mountPanel()
    const select = wrapper.findComponent(StubSelect)
    expect(select.props('modelValue')).toBe('outdoor')
  })

  it('主题选项来自 THEME_OPTIONS（3 项）', () => {
    const wrapper = mountPanel()
    expect(wrapper.findAllComponents(StubOption).length).toBe(3)
  })

  // ② 场景预设行在 DOM 上可定位（供人工排查/后续 E2E 用；组件内是 el-radio-group 桩）
  it('预设行与字号行都能按 data-testid 定位', () => {
    const wrapper = mountPanel()
    expect(findRadioGroup(wrapper, 'appearance-preset-row').exists()).toBe(true)
    expect(findRadioGroup(wrapper, 'appearance-font-row').exists()).toBe(true)
    expect(findRadioGroup(wrapper, 'appearance-density-row').exists()).toBe(true)
  })
})
