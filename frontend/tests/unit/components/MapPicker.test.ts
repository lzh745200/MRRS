/**
 * MapPicker.vue 测试
 * stub el-dialog / el-input / el-button / OfflineMap，覆盖：
 * - 初始值（modelValue / longitude / latitude / 默认值）
 * - 输入 change → 双向 emit
 * - 地图选取主流程：打开弹窗 → 点击地图 → 确认选择 / 取消
 * - disabled、watcher 同步、resize 派发
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import MapPicker from '@/components/MapPicker.vue'

enableAutoUnmount(afterEach)

vi.mock('@element-plus/icons-vue', () => ({
  Location: { template: '<i class="icon-location" />' },
}))

const ElDialogStub = {
  props: ['modelValue', 'title'],
  emits: ['update:modelValue', 'opened'],
  mounted() {
    if (this.modelValue) this.$emit('opened')
  },
  updated() {
    if (this.modelValue) this.$emit('opened')
  },
  template:
    '<div class="stub-dialog" v-if="modelValue"><button class="dialog-close" @click="$emit(\'update:modelValue\', false)">x</button><slot /><div class="stub-dialog-footer"><slot name="footer" /></div></div>',
}

const ElInputStub = {
  props: ['modelValue', 'disabled', 'placeholder'],
  emits: ['update:modelValue', 'change'],
  methods: {
    onInput(e: Event) {
      const val = (e.target as HTMLInputElement).value
      this.$emit('update:modelValue', val)
      this.$emit('change', val)
    },
  },
  template:
    '<input class="stub-input" :value="modelValue" :disabled="disabled" :placeholder="placeholder" @change="onInput" />',
}

const ElButtonStub = {
  props: ['disabled', 'loading', 'type', 'icon'],
  emits: ['click'],
  template: '<button class="stub-btn" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
}

const OfflineMapStub = {
  emits: ['marker-click', 'region-click'],
  template:
    '<div class="stub-map"><button class="map-region" @click="$emit(\'region-click\', { name: \'南明区\', lng: 108.5, lat: 27.5 })">region</button><button class="map-marker" @click="$emit(\'marker-click\', { name: \'m1\', lng: 109.1, lat: 28.2, type: \'village\' })">marker</button></div>',
}

function mountPicker(props: Record<string, unknown> = {}) {
  return mount(MapPicker, {
    props,
    global: {
      stubs: {
        'el-dialog': ElDialogStub,
        'el-input': ElInputStub,
        'el-button': ElButtonStub,
        OfflineMap: OfflineMapStub,
        'el-row': { template: '<div class="stub-row"><slot /></div>' },
        'el-col': { template: '<div class="stub-col"><slot /></div>' },
        'el-tag': { template: '<span class="stub-tag"><slot /></span>' },
      },
    },
  })
}

describe('MapPicker.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('无 props 时使用默认经纬度', () => {
    const wrapper = mountPicker()
    const inputs = wrapper.findAll('input.stub-input')
    expect((inputs[0].element as HTMLInputElement).value).toBe('107.52')
    expect((inputs[1].element as HTMLInputElement).value).toBe('26.26')
  })

  it('从 modelValue / longitude / latitude 初始化', () => {
    const wrapper = mountPicker({
      modelValue: { lng: 111.1, lat: 22.2 },
    })
    const inputs = wrapper.findAll('input.stub-input')
    expect((inputs[0].element as HTMLInputElement).value).toBe('111.1')
    expect((inputs[1].element as HTMLInputElement).value).toBe('22.2')

    const wrapper2 = mountPicker({ longitude: 105.5, latitude: 25.5 })
    const inputs2 = wrapper2.findAll('input.stub-input')
    expect((inputs2[0].element as HTMLInputElement).value).toBe('105.5')
    expect((inputs2[1].element as HTMLInputElement).value).toBe('25.5')
  })

  it('修改输入触发 update:modelValue / latitude / longitude', async () => {
    const wrapper = mountPicker()
    const inputs = wrapper.findAll('input.stub-input')
    await inputs[0].setValue('106.7')
    await inputs[1].setValue('26.9')

    expect(wrapper.emitted('update:modelValue')!.at(-1)![0]).toEqual({ lng: 106.7, lat: 26.9 })
    expect(wrapper.emitted('update:latitude')!.at(-1)![0]).toBe(26.9)
    expect(wrapper.emitted('update:longitude')!.at(-1)![0]).toBe(106.7)
  })

  it('disabled 时输入与按钮禁用', () => {
    const wrapper = mountPicker({ disabled: true })
    const inputs = wrapper.findAll('input.stub-input')
    expect(inputs[0].attributes('disabled')).toBeDefined()
    expect(inputs[1].attributes('disabled')).toBeDefined()
    expect(wrapper.find('button.stub-btn').attributes('disabled')).toBeDefined()
  })

  it('地图选取主流程：打开 → 点击地图 → 确认选择 → 关闭并 emit', async () => {
    const wrapper = mountPicker()
    await wrapper.find('button.stub-btn').trigger('click')
    expect(wrapper.find('.stub-dialog').exists()).toBe(true)
    const footerButtons = () => wrapper.findAll('.stub-dialog-footer .stub-btn')
    const confirmBtn = () => footerButtons()[1]

    // 未选择时确认按钮禁用
    expect(confirmBtn().attributes('disabled')).toBeDefined()

    // 点击地图区域 → 显示已选坐标
    await wrapper.find('button.map-region').trigger('click')
    expect(wrapper.text()).toContain('已选坐标: 108.500000, 27.500000')

    // 点击地图标记点 → 更新为标记坐标
    await wrapper.find('button.map-marker').trigger('click')
    expect(wrapper.text()).toContain('已选坐标: 109.100000, 28.200000')

    // 确认选择
    await confirmBtn().trigger('click')
    expect(wrapper.emitted('update:modelValue')!.at(-1)![0]).toEqual({ lng: 109.1, lat: 28.2 })
    expect(wrapper.emitted('update:latitude')!.at(-1)![0]).toBe(28.2)
    expect(wrapper.emitted('update:longitude')!.at(-1)![0]).toBe(109.1)
    expect(wrapper.find('.stub-dialog').exists()).toBe(false)
    // 输入框同步为已选坐标
    const inputs = wrapper.findAll('input.stub-input')
    expect((inputs[0].element as HTMLInputElement).value).toBe('109.1')
  })

  it('未选择坐标时确认选择不 emit 且保持打开', async () => {
    const wrapper = mountPicker()
    await wrapper.find('button.stub-btn').trigger('click')
    const confirm = wrapper.findAll('.stub-dialog-footer .stub-btn')[1]
    await confirm.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.find('.stub-dialog').exists()).toBe(true)
  })

  it('取消按钮直接关闭弹窗（dialogVisible 为内部状态，不 emit）', async () => {
    const wrapper = mountPicker()
    await wrapper.find('button.stub-btn').trigger('click')
    const buttons = wrapper.findAll('.stub-dialog-footer .stub-btn')
    await buttons[0].trigger('click')
    expect(wrapper.find('.stub-dialog').exists()).toBe(false)
  })

  it('el-dialog v-model 关闭路径（update:modelValue → dialogVisible）', async () => {
    const wrapper = mountPicker()
    await wrapper.find('button.stub-btn').trigger('click')
    expect(wrapper.find('.stub-dialog').exists()).toBe(true)
    await wrapper.find('button.dialog-close').trigger('click')
    expect(wrapper.find('.stub-dialog').exists()).toBe(false)
  })

  // 2026-09-30 深审修复：原先 modelValue/latitude/longitude 被父组件置空时
  // 内部坐标保留旧值（"if (val) 才写入"），输入框仍显示上一个对象的坐标且
  // 下一次 change 会把旧坐标原样发回。现改为同步清空，断言随之改写。
  it('watcher 同步 modelValue / latitude / longitude（置空即清空）', async () => {
    const wrapper = mountPicker()
    await wrapper.setProps({ modelValue: { lng: 99.9, lat: 88.8 } })
    let inputs = wrapper.findAll('input.stub-input')
    expect((inputs[0].element as HTMLInputElement).value).toBe('99.9')
    expect((inputs[1].element as HTMLInputElement).value).toBe('88.8')

    // modelValue 为 null → 同步清空（不再保留旧坐标）
    await wrapper.setProps({ modelValue: null })
    inputs = wrapper.findAll('input.stub-input')
    expect((inputs[0].element as HTMLInputElement).value).toBe('')
    expect((inputs[1].element as HTMLInputElement).value).toBe('')

    await wrapper.setProps({ modelValue: { lng: 99.9, lat: 88.8 } })
    // latitude / longitude 为 null → 同样清空
    await wrapper.setProps({ latitude: null, longitude: null })
    inputs = wrapper.findAll('input.stub-input')
    expect((inputs[0].element as HTMLInputElement).value).toBe('')
    expect((inputs[1].element as HTMLInputElement).value).toBe('')

    await wrapper.setProps({ latitude: 30.3, longitude: 120.2 })
    inputs = wrapper.findAll('input.stub-input')
    expect((inputs[0].element as HTMLInputElement).value).toBe('120.2')
    expect((inputs[1].element as HTMLInputElement).value).toBe('30.3')
  })

  // ── 2026-09-30 深审修复：脏坐标不外发 ──

  it('经度为空 / 非数字 / 越界 → 不 emit 并提示', async () => {
    const warnSpy = vi.spyOn(ElMessage, 'warning').mockImplementation((() => ({})) as any)
    try {
      const wrapper = mountPicker()
      const inputs = wrapper.findAll('input.stub-input')
      const emits = () => (wrapper.emitted('update:modelValue') || []).length

      await inputs[1].setValue('26.9') // 纬度合法 → 正常外发一次
      const baseline = emits()
      expect(baseline).toBe(1)

      await inputs[0].setValue('')
      expect(emits()).toBe(baseline)

      await inputs[0].setValue('abc')
      expect(emits()).toBe(baseline)

      await inputs[0].setValue('999')
      expect(emits()).toBe(baseline)

      expect(warnSpy).toHaveBeenCalledWith('经纬度格式不正确：经度 -180~180，纬度 -90~90')
    } finally {
      warnSpy.mockRestore()
    }
  })

  it('纬度为空 / 越界 → 不 emit；恢复合法后照常外发', async () => {
    const warnSpy = vi.spyOn(ElMessage, 'warning').mockImplementation((() => ({})) as any)
    try {
      const wrapper = mountPicker()
      const inputs = wrapper.findAll('input.stub-input')
      const emits = () => (wrapper.emitted('update:modelValue') || []).length

      await inputs[0].setValue('106.7')
      const baseline = emits()

      await inputs[1].setValue('')
      expect(emits()).toBe(baseline)

      await inputs[1].setValue('100')
      expect(emits()).toBe(baseline)

      await inputs[1].setValue('26.9')
      expect(emits()).toBe(baseline + 1)
      expect(wrapper.emitted('update:modelValue')!.at(-1)![0]).toEqual({ lng: 106.7, lat: 26.9 })
    } finally {
      warnSpy.mockRestore()
    }
  })

  it('地图返回 NaN 坐标时确认选择不外发、不关闭弹窗', async () => {
    const wrapper = mountPicker()
    await wrapper.find('button.stub-btn').trigger('click')
    const state = (wrapper.vm as any).$.setupState
    state.pickedLng = NaN
    state.pickedLat = 27.5
    await nextTick()

    const confirm = wrapper.findAll('.stub-dialog-footer .stub-btn')[1]
    await confirm.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.find('.stub-dialog').exists()).toBe(true)
  })

  it('弹窗打开后派发 window resize（200ms 后）', async () => {
    const resizeSpy = vi.spyOn(window, 'dispatchEvent')
    const wrapper = mountPicker()
    await wrapper.find('button.stub-btn').trigger('click')
    await nextTick()
    vi.advanceTimersByTime(300)
    expect(resizeSpy).toHaveBeenCalledWith(expect.any(Event))
    resizeSpy.mockRestore()
    await flushPromises()
  })
})
