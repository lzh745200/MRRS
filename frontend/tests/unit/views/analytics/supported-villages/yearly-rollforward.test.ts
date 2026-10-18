/**
 * YearlyRollforwardDialog.vue —— 年度数据滚动填报弹窗覆盖率攻坚
 *
 * 覆盖：加载中/加载失败/无上年数据/正常预填渲染、逐字段差异（沿用/保留/需重填）、
 * 批量选择（全选/单选）、只填空 vs 覆盖二选一、二次确认、提交成功/失败/取消、
 * 影响面提示与取消关闭。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const mocks = vi.hoisted(() => ({
  getYearlyPrefill: vi.fn(),
  rollforwardYearlyData: vi.fn(),
  confirm: vi.fn(),
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  logError: vi.fn(),
}))

vi.mock('@/api/supportedVillage', () => ({
  getYearlyPrefill: (...args: any[]) => mocks.getYearlyPrefill(...args),
  rollforwardYearlyData: (...args: any[]) => mocks.rollforwardYearlyData(...args),
}))

vi.mock('element-plus', () => ({
  ElMessage: mocks.ElMessage,
  ElMessageBox: { confirm: mocks.confirm },
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: mocks.logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() },
}))

import YearlyRollforwardDialog from '@/views/analytics/supported-villages/components/YearlyRollforwardDialog.vue'

function field(name: string, over: Record<string, any> = {}) {
  return {
    field: name,
    label: name,
    previousValue: 1,
    currentValue: 0,
    hasPreviousValue: true,
    hasCurrentValue: false,
    status: 'copy',
    ...over,
  }
}

function prefillData(over: Record<string, any> = {}) {
  return {
    villageId: 1,
    year: 2026,
    fromYear: 2025,
    hasPreviousData: true,
    sections: [
      {
        key: 'population',
        title: '人口数据',
        hasPreviousData: true,
        fields: [
          field('total_households', { label: '总户数', previousValue: 100, status: 'copy' }),
          field('total_population', {
            label: '总人数',
            previousValue: 300,
            currentValue: 280,
            hasCurrentValue: true,
            status: 'keep',
          }),
          field('labor_force', {
            label: '劳动力',
            previousValue: 0,
            hasPreviousValue: false,
            status: 'blank',
          }),
          field('members', {
            label: '村委会成员',
            previousValue: [{ name: '张三' }, { name: '王五' }],
            currentValue: [],
            status: 'copy',
          }),
        ],
        copyableCount: 2,
        keptCount: 1,
        blankCount: 1,
      },
      {
        key: 'income',
        title: '收入数据',
        hasPreviousData: false,
        fields: [],
        copyableCount: 0,
        keptCount: 0,
        blankCount: 0,
      },
    ],
    summary: {
      sectionCount: 2,
      availableSectionCount: 1,
      copyableFieldCount: 2,
      keptFieldCount: 1,
      blankFieldCount: 1,
    },
    message: '可从 2025 年沿用 2 项字段到 2026 年（1 个板块有上年数据）',
    ...over,
  }
}

function emptyPrefill() {
  return prefillData({
    hasPreviousData: false,
    sections: [
      {
        key: 'income',
        title: '收入数据',
        hasPreviousData: false,
        fields: [],
        copyableCount: 0,
        keptCount: 0,
        blankCount: 0,
      },
    ],
    message: '2025 年没有可沿用的年度数据，所有板块需手工填写',
  })
}

// Element Plus 组件在单测中不注册插件：以轻量桩渲染插槽（真实 UI 中由全局组件提供），
// 否则未解析的 <el-checkbox> 等会被当成原生元素、插槽文本不渲染
const globalStubs = {
  'el-checkbox': {
    name: 'StubCheckbox',
    props: ['modelValue', 'disabled'],
    emits: ['change'],
    template:
      '<label class="checkbox-stub" :data-checked="String(modelValue)">' +
      '<button type="button" class="checkbox-on" @click="$emit(\'change\', true)">on</button>' +
      '<button type="button" class="checkbox-off" @click="$emit(\'change\', false)">off</button>' +
      '<slot /></label>',
  },
  'el-radio-group': {
    name: 'StubRadioGroup',
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<div class="radio-group-stub">' +
      '<button type="button" class="radio-on" @click="$emit(\'update:modelValue\', true)">on</button>' +
      '<button type="button" class="radio-off" @click="$emit(\'update:modelValue\', false)">off</button>' +
      '<slot /></div>',
  },
  'el-radio': { template: '<label class="radio-stub"><slot /></label>' },
  'el-tag': { template: '<span class="tag-stub"><slot /></span>' },
  'el-alert': {
    props: ['title', 'type'],
    template: '<div class="alert-stub" :title="title"><slot /></div>',
  },
  'el-button': {
    props: ['disabled', 'loading', 'type'],
    emits: ['click'],
    template:
      '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  },
}

function mountDialog(props: Record<string, any> = {}) {
  return mount(YearlyRollforwardDialog as any, {
    props: { villageId: 1, year: 2026, ...props },
    global: { stubs: globalStubs },
  })
}

function st(wrapper: ReturnType<typeof mountDialog>) {
  return (wrapper.vm as any).$.setupState
}

const submitResult = {
  villageId: 1,
  year: 2026,
  fromYear: 2025,
  mode: 'fill_empty',
  hasPreviousData: true,
  appliedFields: 2,
  keptFields: 1,
  createdSections: ['population'],
  appliedSections: ['population'],
  skippedSections: [],
  sections: {},
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getYearlyPrefill.mockResolvedValue(prefillData())
  mocks.rollforwardYearlyData.mockResolvedValue(submitResult)
  mocks.confirm.mockResolvedValue(undefined)
})

describe('YearlyRollforwardDialog 加载与差异展示', () => {
  it('加载中展示提示，成功后按板块与逐字段差异渲染', async () => {
    const wrapper = mountDialog()
    await nextTick()
    expect(wrapper.find('.rollforward-loading').exists()).toBe(true)
    await flushPromises()
    expect(wrapper.find('.rollforward-loading').exists()).toBe(false)
    expect(mocks.getYearlyPrefill).toHaveBeenCalledWith(1, 2026)

    const items = wrapper.findAll('.section-item')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toContain('人口数据')
    expect(items[0].text()).toContain('可沿用 2')
    expect(items[1].classes()).toContain('section-item-disabled')
    expect(items[1].text()).toContain('无上年数据')

    const rows = wrapper.findAll('.diff-row')
    expect(rows).toHaveLength(4)
    expect(rows[0].text()).toContain('总户数')
    expect(rows[0].text()).toContain('上年：100')
    expect(rows[0].classes()).toContain('status-copy')
    expect(rows[1].classes()).toContain('status-keep')
    expect(rows[2].classes()).toContain('status-blank')
    // 数组值（村委会成员）格式化：2 项
    expect(rows[3].text()).toContain('上年：2 项')

    expect(wrapper.find('.select-summary').text()).toContain('已选 1 / 1 个板块')
    expect(wrapper.find('.impact-tip').attributes('title')).toContain('将沿用 2 项字段')
    expect(st(wrapper).selectedKeys).toEqual(['population'])
    expect(st(wrapper).allSelected).toBe(true)
    expect(st(wrapper).canSubmit).toBe(true)
  })

  it('无上年数据：展示友好提示且禁用提交', async () => {
    mocks.getYearlyPrefill.mockResolvedValue(emptyPrefill())
    const wrapper = mountDialog()
    await flushPromises()
    const empty = wrapper.find('.rollforward-empty')
    expect(empty.exists()).toBe(true)
    expect(empty.attributes('title')).toContain('没有可沿用')
    expect(wrapper.find('.section-list').exists()).toBe(false)
    expect((wrapper.find('.btn-submit').element as HTMLElement).hasAttribute('disabled')).toBe(true)
    expect(st(wrapper).allSelected).toBe(false)
  })

  it('预填数据为空时使用兜底空态文案', async () => {
    mocks.getYearlyPrefill.mockResolvedValue(null)
    const wrapper = mountDialog()
    await flushPromises()
    expect(wrapper.find('.rollforward-empty').attributes('title')).toBe(
      '2025 年没有可沿用的年度数据，请手工填写'
    )
    // sections computed 的空值兜底分支（模板空态路径不渲染板块列表，直接求值覆盖）
    expect(st(wrapper).sections).toEqual([])
    expect(st(wrapper).hasPreviousData).toBe(false)
  })

  it('加载失败：展示后端 detail 文案', async () => {
    mocks.getYearlyPrefill.mockRejectedValue({ response: { data: { detail: '网络异常' } } })
    const wrapper = mountDialog()
    await flushPromises()
    expect(wrapper.find('.rollforward-error').attributes('title')).toBe('网络异常')
    expect(mocks.logError).toHaveBeenCalled()
  })

  it('加载失败：无可用信息时展示兜底文案', async () => {
    mocks.getYearlyPrefill.mockRejectedValue({})
    const wrapper = mountDialog()
    await flushPromises()
    expect(wrapper.find('.rollforward-error').attributes('title')).toBe(
      '加载上年数据失败，请稍后重试'
    )
  })
})

describe('YearlyRollforwardDialog 批量选择', () => {
  it('全选/清空切换并联动差异面板与提交可用性', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    const vm = st(wrapper)

    vm.handleToggleAll(false)
    await nextTick()
    expect(vm.selectedKeys).toEqual([])
    expect(wrapper.find('.diff-panel').exists()).toBe(false)
    expect(vm.canSubmit).toBe(false)
    expect((wrapper.find('.btn-submit').element as HTMLElement).hasAttribute('disabled')).toBe(true)

    vm.handleToggleAll(true)
    await nextTick()
    expect(vm.selectedKeys).toEqual(['population'])
    expect(vm.selectedSections).toHaveLength(1)
    expect(wrapper.find('.diff-panel').exists()).toBe(true)
    expect(vm.canSubmit).toBe(true)
  })

  it('单板块勾选/取消（去重、移除、未知板块也仅影响选择集合）', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    const vm = st(wrapper)
    vm.handleToggleSection('population', true)
    expect(vm.selectedKeys).toEqual(['population'])
    vm.handleToggleSection('income', true)
    expect(vm.selectedKeys).toEqual(['population', 'income'])
    vm.handleToggleSection('income', false)
    expect(vm.selectedKeys).toEqual(['population'])
    vm.handleToggleSection('population', false)
    expect(vm.selectedKeys).toEqual([])
  })

  it('模板事件：勾选/取消勾选板块与写入方式 v-model 更新', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    const vm = st(wrapper)
    // 模板 @change="handleSectionChange(section.key)" 生成的处理器：
    // 第 0 个 .section-item 即人口板块，第 1 个收入板块无上年数据
    await wrapper.findAll('.section-item .checkbox-on')[0].trigger('click')
    await nextTick()
    expect(vm.selectedKeys).toEqual(['population'])
    await wrapper.findAll('.section-item .checkbox-off')[0].trigger('click')
    await nextTick()
    expect(vm.selectedKeys).toEqual([])
    // el-radio-group v-model 生成的 update:modelValue 处理器
    expect(vm.overwrite).toBe(false)
    await wrapper.find('.radio-on').trigger('click')
    await nextTick()
    expect(vm.overwrite).toBe(true)
    await wrapper.find('.radio-off').trigger('click')
    await nextTick()
    expect(vm.overwrite).toBe(false)
  })

  it('canSubmit 在加载中/提交中为 false', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    const vm = st(wrapper)
    vm.loading = true
    expect(vm.canSubmit).toBe(false)
    vm.loading = false
    vm.submitting = true
    expect(vm.canSubmit).toBe(false)
    vm.submitting = false
    expect(vm.canSubmit).toBe(true)
  })

  it('格式化与状态标签辅助函数', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    const vm = st(wrapper)
    expect(vm.formatValue(null)).toBe('—')
    expect(vm.formatValue(undefined)).toBe('—')
    expect(vm.formatValue('')).toBe('—')
    expect(vm.formatValue([1, 2])).toBe('2 项')
    expect(vm.formatValue(true)).toBe('是')
    expect(vm.formatValue(false)).toBe('否')
    expect(vm.formatValue(12)).toBe('12')
    expect(vm.statusLabel('copy')).toBe('可沿用')
    expect(vm.statusLabel('keep')).toBe('保留本年度')
    expect(vm.statusLabel('blank')).toBe('需重填')
    expect(vm.statusLabel('unknown')).toBe('unknown')
    expect(vm.statusTagType('copy')).toBe('success')
    expect(vm.statusTagType('keep')).toBe('info')
    expect(vm.statusTagType('blank')).toBe('warning')
    expect(vm.statusTagType('unknown')).toBe('info')
  })
})

describe('YearlyRollforwardDialog 提交', () => {
  it('二次确认后按只填空语义提交并关闭', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    await wrapper.find('.btn-submit').trigger('click')
    await flushPromises()

    expect(mocks.confirm).toHaveBeenCalledTimes(1)
    const confirmMessage = mocks.confirm.mock.calls[0][0]
    expect(confirmMessage).toContain('将沿用 2 项字段')
    expect(mocks.confirm.mock.calls[0][1]).toBe('确认从上年复制')
    expect(mocks.rollforwardYearlyData).toHaveBeenCalledWith(1, 2026, {
      sectionKeys: ['population'],
      overwrite: false,
    })
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('已从 2025 年沿用 2 项字段（1 个板块）')
    expect(wrapper.emitted('applied')).toHaveLength(1)
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('覆盖模式：影响面提示与确认文案切换，提交 overwrite=true', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    st(wrapper).overwrite = true
    await nextTick()
    expect(wrapper.find('.impact-tip').attributes('title')).toContain('覆盖')
    await wrapper.find('.btn-submit').trigger('click')
    await flushPromises()
    expect(mocks.confirm.mock.calls[0][0]).toContain('覆盖')
    expect(mocks.confirm.mock.calls[0][2].type).toBe('warning')
    expect(mocks.rollforwardYearlyData).toHaveBeenCalledWith(1, 2026, {
      sectionKeys: ['population'],
      overwrite: true,
    })
  })

  it('后端返回 0 沿用项：提示未做修改但正常关闭', async () => {
    mocks.rollforwardYearlyData.mockResolvedValue({
      ...submitResult,
      appliedFields: 0,
      appliedSections: [],
    })
    const wrapper = mountDialog()
    await flushPromises()
    await wrapper.find('.btn-submit').trigger('click')
    await flushPromises()
    expect(mocks.ElMessage.success.mock.calls[0][0]).toContain('未做修改')
    expect(wrapper.emitted('applied')).toHaveLength(1)
  })

  it('后端返回 null / 缺少 appliedSections 时兜底计数为 0', async () => {
    mocks.rollforwardYearlyData.mockResolvedValueOnce(null)
    const wrapper = mountDialog()
    await flushPromises()
    await wrapper.find('.btn-submit').trigger('click')
    await flushPromises()
    expect(mocks.ElMessage.success.mock.calls[0][0]).toContain('未做修改')

    mocks.rollforwardYearlyData.mockResolvedValueOnce({ appliedFields: 1 })
    const wrapper2 = mountDialog()
    await flushPromises()
    await wrapper2.find('.btn-submit').trigger('click')
    await flushPromises()
    expect(mocks.ElMessage.success.mock.calls[1][0]).toContain('（0 个板块）')
  })

  it('二次确认取消：不调用沿用接口、不关闭', async () => {
    mocks.confirm.mockRejectedValue(new Error('cancel'))
    const wrapper = mountDialog()
    await flushPromises()
    await wrapper.find('.btn-submit').trigger('click')
    await flushPromises()
    expect(mocks.rollforwardYearlyData).not.toHaveBeenCalled()
    expect(wrapper.emitted('applied')).toBeUndefined()
    expect(wrapper.emitted('close')).toBeUndefined()
  })

  it('未选择板块：提示且不调用接口', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    st(wrapper).handleToggleAll(false)
    await nextTick()
    await st(wrapper).handleSubmit()
    await flushPromises()
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('请先选择要沿用的板块')
    expect(mocks.rollforwardYearlyData).not.toHaveBeenCalled()
  })

  it('提交失败：展示后端 detail 文案', async () => {
    mocks.rollforwardYearlyData.mockRejectedValue({
      response: { data: { detail: '年度数据不存在' } },
    })
    const wrapper = mountDialog()
    await flushPromises()
    await wrapper.find('.btn-submit').trigger('click')
    await flushPromises()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('年度数据不存在')
    expect(wrapper.emitted('applied')).toBeUndefined()
  })

  it('提交失败：无可用信息时展示兜底文案', async () => {
    mocks.rollforwardYearlyData.mockRejectedValue({})
    const wrapper = mountDialog()
    await flushPromises()
    await wrapper.find('.btn-submit').trigger('click')
    await flushPromises()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('沿用失败，请稍后重试')
  })

  it('取消按钮直接关闭弹窗', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    await wrapper.find('.btn-cancel').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
