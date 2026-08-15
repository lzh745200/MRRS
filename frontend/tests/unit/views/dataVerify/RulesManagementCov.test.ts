/**
 * views/dataVerify/RulesManagement.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：loadRules 参数链与三种响应形状、moduleLabel/ruleTypeLabel 映射与透传、
 * handleEdit 全 || 兜底、handleSubmit（无 formRef/validate 失败/创建/编辑/异常）、
 * handleDelete 全分支、runSingleValidation 成败、executeValidation 全分支（空输入/JSON 错/
 * res.data 与扁平两侧/异常）、模板 v-if/v-model/内联点击全交互。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂提升求值，引用对象须先放入 vi.hoisted 初始化（TDZ）
const {
  ElMessage,
  confirmMock,
  mockListRules,
  mockCreateRule,
  mockUpdateRule,
  mockDeleteRule,
  mockRunValidation,
} = vi.hoisted(() => {
  return {
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
    confirmMock: vi.fn(),
    mockListRules: vi.fn(),
    mockCreateRule: vi.fn(),
    mockUpdateRule: vi.fn(),
    mockDeleteRule: vi.fn(),
    mockRunValidation: vi.fn(),
  }
})

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/validationRules', () => ({
  listRules: mockListRules,
  createRule: mockCreateRule,
  updateRule: mockUpdateRule,
  deleteRule: mockDeleteRule,
  runValidation: mockRunValidation,
}))

import RulesManagement from '@/views/dataVerify/RulesManagement.vue'

// ==================== 样本数据 ====================

const rule1 = {
  id: 1,
  description: '收入不能为负',
  module: 'supported_villages',
  field: 'income',
  rule_type: 'range',
  params: '{"min": 0}',
  error_message: '收入必须 ≥ 0',
  priority: 5,
  is_active: true,
}
const rule2 = {
  id: 2,
  description: '校名必填',
  module: 'schools',
  field: 'school_name',
  rule_type: 'required',
  params: '',
  error_message: '',
  priority: 0,
  is_active: false,
}

// el-table-column 插槽样本行：is_active 两侧、module/rule_type 映射命中 + 未知透传
const slotRowA = {
  id: 1,
  description: '规则A',
  module: 'schools',
  field: 'income',
  rule_type: 'range',
  is_active: true,
}
const slotRowB = {
  id: 2,
  description: '',
  module: 'mystery',
  field: 'population',
  rule_type: 'other_type',
  is_active: false,
}

const stubs = {
  'el-card': {
    name: 'ElCard',
    template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
  },
  'el-dialog': {
    name: 'ElDialog',
    template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
    props: ['modelValue', 'title'],
    emits: ['update:modelValue', 'close'],
  },
  'el-table-column': {
    name: 'ElTableColumn',
    template: '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
    data() {
      return { rowA: slotRowA, rowB: slotRowB }
    },
  },
}

function mountComp() {
  return mount(RulesManagement, { global: { renderStubDefaultSlot: true, stubs } })
}

/** 精确文本匹配按钮（避免「执行校验」误中「校验」） */
function findBtn(wrapper: any, text: string) {
  const btn = wrapper.findAll('el-button-stub').find((b: any) => b.text().trim() === text)
  expect(btn, `按钮「${text}」`).toBeTruthy()
  return btn!
}

beforeEach(() => {
  vi.resetAllMocks()
  mockListRules.mockResolvedValue({ data: [rule1, rule2] })
  mockCreateRule.mockResolvedValue({ data: { id: 3 } })
  mockUpdateRule.mockResolvedValue({ data: {} })
  mockDeleteRule.mockResolvedValue({ data: {} })
  mockRunValidation.mockResolvedValue({ data: { valid: true, errors: [] } })
  confirmMock.mockResolvedValue(undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ==================== 测试 ====================

describe('加载与筛选', () => {
  it('onMounted 加载规则（res.data 侧），默认无筛选参数', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(mockListRules).toHaveBeenCalledWith({})
    expect(vm.rules).toHaveLength(2)
    expect(vm.loading).toBe(false)

    const text = wrapper.text()
    expect(text).toContain('校验规则管理')
    expect(text).toContain('学校') // moduleLabel 命中
    expect(text).toContain('mystery') // moduleLabel 透传
    expect(text).toContain('数值范围') // ruleTypeLabel 命中
    expect(text).toContain('other_type') // ruleTypeLabel 透传
    expect(text).toContain('启用')
    expect(text).toContain('禁用')
    expect(wrapper.findComponent({ name: 'ElEmpty' }).exists()).toBe(false) // el-empty 假侧
  })

  it('loadRules：res.items 侧与空响应 [] 侧（el-empty 真侧）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    mockListRules.mockResolvedValueOnce({ items: [rule1] })
    await vm.loadRules()
    expect(vm.rules).toHaveLength(1)

    mockListRules.mockResolvedValueOnce(null)
    await vm.loadRules()
    expect(vm.rules).toEqual([])
    await nextTick()
    expect(wrapper.findComponent({ name: 'ElEmpty' }).exists()).toBe(true) // el-empty 真侧
  })

  it('loadRules 失败 → 提示「加载校验规则失败」', async () => {
    mockListRules.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(ElMessage.error).toHaveBeenCalledWith('加载校验规则失败')
    expect(vm.loading).toBe(false)
  })

  it('筛选参数：module 与 is_active 真/假两侧；下拉 change 与刷新按钮触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 'schools')
    selects[0].vm.$emit('change')
    await flushPromises()
    expect(vm.filterModule).toBe('schools')

    selects[1].vm.$emit('update:modelValue', 'true')
    selects[1].vm.$emit('change')
    await flushPromises()
    expect(mockListRules).toHaveBeenLastCalledWith({ module: 'schools', is_active: true })

    selects[1].vm.$emit('update:modelValue', 'false')
    selects[1].vm.$emit('change')
    await flushPromises()
    expect(mockListRules).toHaveBeenLastCalledWith({ module: 'schools', is_active: false })

    const before = mockListRules.mock.calls.length
    await findBtn(wrapper, '刷新').trigger('click')
    await flushPromises()
    expect(mockListRules.mock.calls.length).toBeGreaterThan(before)
  })

  it('moduleLabel / ruleTypeLabel 直接调用（命中与透传）', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.moduleLabel('funds')).toBe('资金')
    expect(vm.moduleLabel('policies')).toBe('政策')
    expect(vm.moduleLabel('unknown')).toBe('unknown')
    expect(vm.ruleTypeLabel('regex')).toBe('正则匹配')
    // 规则类型已收敛为真实 RuleType 枚举（unique/custom 已移除，未命中透传原值）
    expect(vm.ruleTypeLabel('required')).toBe('非空检查')
    expect(vm.ruleTypeLabel('cross_field')).toBe('跨字段逻辑')
    expect(vm.ruleTypeLabel('enum_values')).toBe('枚举值')
    expect(vm.ruleTypeLabel('unique')).toBe('unique')
    expect(vm.ruleTypeLabel('custom')).toBe('custom')
    expect(vm.ruleTypeLabel('zzz')).toBe('zzz')
  })
})

describe('创建/编辑对话框', () => {
  it('「新增规则」打开对话框并复位表单；全部 v-model 同步；「取消」内联关闭', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // handleCreate 内部走 resetForm → formRef.resetFields()，先赋 mock 防 stub 缺方法
    vm.formRef = { resetFields: vi.fn(), validate: vi.fn() }
    await findBtn(wrapper, '新增规则').trigger('click')
    expect(vm.dialogVisible).toBe(true)
    expect(vm.isEditing).toBe(false)
    expect(vm.editingId).toBeNull()

    const dialog = wrapper.findAllComponents({ name: 'ElDialog' })[0]
    const inputs = dialog.findAllComponents({ name: 'ElInput' })
    // description / field / params / error_message
    inputs[0].vm.$emit('update:modelValue', '新规则描述')
    inputs[1].vm.$emit('update:modelValue', 'village_name')
    inputs[2].vm.$emit('update:modelValue', '{"max": 100}')
    inputs[3].vm.$emit('update:modelValue', '超出范围')
    expect(vm.formData).toMatchObject({
      description: '新规则描述',
      field: 'village_name',
      params: '{"max": 100}',
      error_message: '超出范围',
    })

    const selects = dialog.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 'funds') // module
    selects[1].vm.$emit('update:modelValue', 'regex') // rule_type
    expect(vm.formData.module).toBe('funds')
    expect(vm.formData.rule_type).toBe('regex')

    dialog.findAllComponents({ name: 'ElInputNumber' })[0].vm.$emit('update:modelValue', 9)
    expect(vm.formData.priority).toBe(9)
    dialog.findAllComponents({ name: 'ElSwitch' })[0].vm.$emit('update:modelValue', false)
    expect(vm.formData.is_active).toBe(false)

    // el-dialog v-model 内联 onUpdate
    dialog.vm.$emit('update:modelValue', false)
    expect(vm.dialogVisible).toBe(false)

    await findBtn(wrapper, '取消').trigger('click') // @click="dialogVisible = false"
    expect(vm.dialogVisible).toBe(false)
  })

  it('表格「编辑」按钮填充表单（值侧）；handleEdit({}) 全 || 兜底；is_active!==false 两侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await findBtn(wrapper, '编辑').trigger('click')
    expect(vm.isEditing).toBe(true)
    expect(vm.editingId).toBe(1)
    expect(vm.dialogVisible).toBe(true)
    expect(vm.formData).toMatchObject({
      description: '规则A',
      module: 'schools',
      rule_type: 'range',
    })

    vm.handleEdit({})
    expect(vm.formData).toMatchObject({
      description: '',
      module: 'supported_villages',
      field: '',
      rule_type: 'required',
      params: '',
      error_message: '',
      priority: 0,
      is_active: true,
    })

    vm.handleEdit({ is_active: false })
    expect(vm.formData.is_active).toBe(false)
  })

  it('handleSubmit：无 formRef 返回；validate invalid 不发请求', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.formRef = undefined
    await vm.handleSubmit()
    expect(mockCreateRule).not.toHaveBeenCalled()

    vm.formRef = { validate: vi.fn((cb: any) => cb(false)), resetFields: vi.fn() }
    await vm.handleSubmit()
    expect(mockCreateRule).not.toHaveBeenCalled()
  })

  it('handleSubmit 创建：params/error_message 空串 → undefined；成功后刷新列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const formRefMock = { validate: vi.fn((cb: any) => cb(true)), resetFields: vi.fn() }

    vm.formRef = formRefMock // handleCreate 内部走 resetForm，先赋 mock
    vm.handleCreate()
    vm.formData.description = '新规则'
    vm.formData.field = 'income'
    vm.formRef = formRefMock // 重渲染会把 ref 同步回 stub，调用前重新赋值
    await vm.handleSubmit()
    await flushPromises()

    expect(mockCreateRule).toHaveBeenCalledWith(
      expect.objectContaining({
        module: 'supported_villages',
        field: 'income',
        rule_type: 'required',
        params: undefined,
        error_message: undefined,
        description: '新规则',
        is_active: true,
        priority: 0,
      })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('已创建')
    expect(vm.dialogVisible).toBe(false)
    expect(vm.submitting).toBe(false)
    expect(mockListRules.mock.calls.length).toBeGreaterThan(1)
  })

  it('handleSubmit 编辑：params/error_message 值侧透传；「确定」按钮点击触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const formRefMock = { validate: vi.fn((cb: any) => cb(true)), resetFields: vi.fn() }

    vm.handleEdit(rule1)
    vm.formRef = formRefMock
    await findBtn(wrapper, '确定').trigger('click')
    await flushPromises()

    expect(mockUpdateRule).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ params: '{"min": 0}', error_message: '收入必须 ≥ 0', priority: 5 })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('已保存')
  })

  it('handleSubmit 接口异常：detail 侧与默认「操作失败」侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const formRefMock = { validate: vi.fn((cb: any) => cb(true)), resetFields: vi.fn() }

    mockCreateRule.mockRejectedValueOnce({ response: { data: { detail: '规则重复' } } })
    vm.formRef = formRefMock
    await vm.handleSubmit()
    expect(ElMessage.error).toHaveBeenCalledWith('规则重复')
    expect(vm.submitting).toBe(false)

    mockCreateRule.mockRejectedValueOnce({})
    vm.formRef = formRefMock
    await vm.handleSubmit()
    expect(ElMessage.error).toHaveBeenCalledWith('操作失败')
  })

  it('resetForm：dialog @close 触发，formRef 有/无两侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const resetFields = vi.fn()

    vm.formRef = { resetFields, validate: vi.fn() }
    const dialog = wrapper.findAllComponents({ name: 'ElDialog' })[0]
    dialog.vm.$emit('close') // 模板 @close="resetForm"
    expect(resetFields).toHaveBeenCalled()
    expect(vm.formData.description).toBe('')

    vm.formRef = undefined
    expect(() => vm.resetForm()).not.toThrow()
  })
})

describe('删除规则', () => {
  it('确认取消两态（"cancel" 字符串 / toString 对象）→ 不发请求不报错', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleDelete(rule1)
    expect(mockDeleteRule).not.toHaveBeenCalled()

    confirmMock.mockRejectedValueOnce({ toString: () => 'cancel' })
    await vm.handleDelete(rule1)
    expect(mockDeleteRule).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('「删除」按钮点击 → 确认框文案用 description；删除成功刷新列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await findBtn(wrapper, '删除').trigger('click')
    await flushPromises()
    expect(confirmMock.mock.calls[0][0]).toContain('规则A')
    expect(mockDeleteRule).toHaveBeenCalledWith(1)
    expect(ElMessage.success).toHaveBeenCalledWith('规则已删除')
    expect(mockListRules.mock.calls.length).toBeGreaterThan(1)

    // description 空 → || row.field 侧
    confirmMock.mockResolvedValueOnce(undefined)
    await vm.handleDelete({ id: 9, description: '', field: 'population' })
    expect(confirmMock.mock.calls[1][0]).toContain('population')
  })

  it('删除失败：detail 侧与默认「删除失败」侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    mockDeleteRule.mockRejectedValueOnce({ response: { data: { detail: '规则被引用' } } })
    await vm.handleDelete(rule1)
    expect(ElMessage.error).toHaveBeenCalledWith('规则被引用')

    mockDeleteRule.mockRejectedValueOnce({})
    await vm.handleDelete(rule1)
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })
})

describe('单条校验', () => {
  it('「校验」按钮 → runValidation 成功提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await findBtn(wrapper, '校验').trigger('click')
    await flushPromises()
    expect(mockRunValidation).toHaveBeenCalledWith('schools', {})
    expect(ElMessage.success).toHaveBeenCalledWith('规则 "规则A" 校验完成')
    expect(vm.runningValidation).toBe(false)
  })

  it('runSingleValidation 失败 → 错误提示', async () => {
    mockRunValidation.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.runSingleValidation(rule1)
    expect(ElMessage.error).toHaveBeenCalledWith('规则 "收入不能为负" 校验失败')
    expect(vm.runningValidation).toBe(false)
  })
})

describe('执行校验对话框', () => {
  it('「执行校验」打开对话框并复位状态；runModule/runDataInput v-model；「关闭」内联关闭', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.validationResult = { valid: true }
    await findBtn(wrapper, '执行校验').trigger('click')
    expect(vm.runDialogVisible).toBe(true)
    expect(vm.runModule).toBe('supported_villages')
    expect(vm.runDataInput).toBe('')
    expect(vm.validationResult).toBeNull()

    const runDialog = wrapper.findAllComponents({ name: 'ElDialog' })[1]
    runDialog.findAllComponents({ name: 'ElSelect' })[0].vm.$emit('update:modelValue', 'funds')
    expect(vm.runModule).toBe('funds')
    runDialog.findAllComponents({ name: 'ElInput' })[0].vm.$emit('update:modelValue', '{"a":1}')
    expect(vm.runDataInput).toBe('{"a":1}')

    runDialog.vm.$emit('update:modelValue', false)
    expect(vm.runDialogVisible).toBe(false)
    await findBtn(wrapper, '关闭').trigger('click') // @click="runDialogVisible = false"
    expect(vm.runDialogVisible).toBe(false)
  })

  it('executeValidation：空输入警告；JSON 非法报错；均不发请求', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.executeValidation()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入测试数据')

    vm.runDataInput = '{bad json'
    await vm.executeValidation()
    expect(ElMessage.error).toHaveBeenCalledWith('测试数据格式错误，请输入有效的JSON')
    expect(mockRunValidation).not.toHaveBeenCalled()
  })

  it('executeValidation 成功：res.data 侧 → 结果渲染（valid 真侧 + errors 列表）', async () => {
    mockRunValidation.mockResolvedValue({
      data: { valid: false, errors: ['收入为负', '缺少村名'] },
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.showRunDialog()
    vm.runDataInput = '{"income": -5}'
    await vm.executeValidation()
    await nextTick()

    expect(mockRunValidation).toHaveBeenCalledWith('supported_villages', { income: -5 })
    expect(vm.validationResult).toEqual({ valid: false, errors: ['收入为负', '缺少村名'] })
    expect(vm.runningValidation).toBe(false)
    const text = wrapper.text()
    expect(text).toContain('校验结果')
    expect(text).toContain('收入为负')
    expect(text).toContain('缺少村名')
  })

  it('executeValidation 成功：扁平 res 侧（|| res）+ valid 真侧 + 无 errors（?.length 假侧）', async () => {
    mockRunValidation.mockResolvedValue({ valid: true })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.runDataInput = '{"ok": 1}'
    await vm.executeValidation()
    expect(vm.validationResult).toEqual({ valid: true })
    await nextTick()
    expect(wrapper.find('.validation-result').exists()).toBe(true)
  })

  it('executeValidation 接口异常：detail 侧与默认「校验执行失败」侧', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.runDataInput = '{"a": 1}'

    mockRunValidation.mockRejectedValueOnce({ response: { data: { detail: '执行超时' } } })
    await vm.executeValidation()
    expect(ElMessage.error).toHaveBeenCalledWith('执行超时')
    expect(vm.runningValidation).toBe(false)

    mockRunValidation.mockRejectedValueOnce({})
    await vm.executeValidation()
    expect(ElMessage.error).toHaveBeenCalledWith('校验执行失败')
  })

  it('「执行」按钮点击触发 executeValidation', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.runDataInput = '{"a": 1}'

    await findBtn(wrapper, '执行').trigger('click')
    await flushPromises()
    expect(mockRunValidation).toHaveBeenCalled()
  })
})
