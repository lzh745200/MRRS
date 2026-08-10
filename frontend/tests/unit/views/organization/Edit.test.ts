/**
 * views/organization/Edit.vue 覆盖率攻坚（四指标 100%）
 *
 * 覆盖：创建模式（无 id）/编辑模式（有 id）标题、loadParentOptions 成功失败
 * （含排除当前 id）、loadData 成功（全字段赋值/is_active 两形态）失败（跳转列表页）、
 * handleSubmit 创建/编辑成功失败、校验失败不请求、handleBack、模板（返回/保存/取消按钮、
 * 编码禁用、切换开关）。
 *
 * 方案：mock vue-router useRoute（params.id 可变）、@/api/organization、useRouterSafe、
 * element-plus；el-form stub 提供 validate 回调；el-switch 可 emit。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const {
  ElMessage,
  mockGetOrganization,
  mockGetOrganizations,
  mockCreateOrganization,
  mockUpdateOrganization,
  mockPushSafe,
  routeBox,
  logError,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockGetOrganization: vi.fn(),
  mockGetOrganizations: vi.fn(),
  mockCreateOrganization: vi.fn(),
  mockUpdateOrganization: vi.fn(),
  mockPushSafe: vi.fn(),
  routeBox: { params: {} as Record<string, any> },
  logError: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeBox,
}))

vi.mock('element-plus', () => ({
  ElMessage,
  type: {},
}))

vi.mock('@/api/organization', () => ({
  getOrganization: (...a: any[]) => mockGetOrganization(...a),
  getOrganizations: (...a: any[]) => mockGetOrganizations(...a),
  createOrganization: (...a: any[]) => mockCreateOrganization(...a),
  updateOrganization: (...a: any[]) => mockUpdateOrganization(...a),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mockPushSafe }),
  safeRouteParam: (value: unknown, fallback = 0) => {
    if (value === undefined || value === null) return fallback
    if (Array.isArray(value)) value = value[0]
    const num = Number(value)
    return Number.isFinite(num) ? num : fallback
  },
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import Edit from '@/views/organization/Edit.vue'

const orgData = {
  id: 5,
  name: '总部',
  code: 'HQ',
  parent_id: 3,
  org_type: 'support_unit',
  is_active: false,
  contact_person: '张三',
  contact_phone: '13800138000',
  contact_email: 'a@b.com',
  address: '地址',
  description: '描述',
}
const parentOrgs = [
  { id: 3, name: '上级单位' },
  { id: 5, name: '总部' },
  { id: 9, name: '兄弟单位' },
]

const stubs = {
  'el-card': { name: 'ElCard', template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
  'el-button': { name: 'ElButton', props: ['disabled', 'loading'], template: '<button class="el-button-stub"><slot /></button>' },
  'el-form': {
    name: 'ElForm',
    template: '<div class="el-form-stub"><slot /></div>',
    methods: {
      validate(cb?: any) {
        const v = validateResult.value
        if (cb) {
          cb(v)
          return Promise.resolve(v)
        }
        return Promise.resolve(v)
      },
    },
  },
  'el-form-item': { name: 'ElFormItem', template: '<div class="el-form-item-stub"><slot /></div>' },
  'el-row': { name: 'ElRow', template: '<div class="el-row-stub"><slot /></div>' },
  'el-col': { name: 'ElCol', template: '<div class="el-col-stub"><slot /></div>' },
  'el-input': { name: 'ElInput', props: ['modelValue', 'disabled'], template: '<div class="el-input-stub"><slot /></div>', emits: ['update:modelValue'] },
  'el-select': { name: 'ElSelect', props: ['modelValue'], template: '<div class="el-select-stub"><slot /></div>', emits: ['update:modelValue', 'change'] },
  'el-option': { name: 'ElOption', template: '<div />' },
  'el-switch': {
    name: 'ElSwitch',
    props: ['modelValue'],
    template: '<div class="el-switch-stub" />',
    emits: ['update:modelValue', 'change'],
  },
}

const validateResult = { value: true }

function mountComp() {
  return mount(Edit, {
    global: { renderStubDefaultSlot: true, stubs },
  })
}

async function clickBtn(wrapper: any, text: string) {
  const btn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().trim().includes(text))
  expect(btn, `按钮「${text}」`).toBeTruthy()
  await btn!.trigger('click')
  await flushPromises()
}

beforeEach(() => {
  vi.resetAllMocks()
  routeBox.params = {}
  validateResult.value = true
  mockGetOrganizations.mockResolvedValue({ items: parentOrgs })
  mockGetOrganization.mockResolvedValue(orgData)
  mockCreateOrganization.mockResolvedValue({})
  mockUpdateOrganization.mockResolvedValue({})
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('创建模式', () => {
  it('无路由 id → 新增组织标题；loadParentOptions 成功并排除自身 id（无 id 不排除）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(wrapper.text()).toContain('新增组织')
    expect(vm.isEdit).toBe(false)
    expect(mockGetOrganizations).toHaveBeenCalledWith({ page_size: 200, is_active: true })
    expect(vm.parentOptions).toEqual(parentOrgs)
    expect(mockGetOrganization).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('loadParentOptions 失败 → logger + 错误提示', async () => {
    mockGetOrganizations.mockRejectedValue(new Error('down'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalledWith('加载上级组织失败:', expect.any(Error))
    expect(ElMessage.error).toHaveBeenCalledWith('加载上级组织失败，请稍后重试')
    wrapper.unmount()
  })

  it('handleSubmit 创建成功 → createOrganization 携带表单 + 成功提示 + 跳转列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    Object.assign(vm.formData, {
      name: '新单位',
      org_type: 'department',
      description: '说明',
      contact_person: '李四',
      contact_phone: '13900139000',
      contact_email: 'b@c.com',
      address: '某地',
    })
    await clickBtn(wrapper, '保存')
    expect(mockCreateOrganization).toHaveBeenCalledWith({
      name: '新单位',
      code: undefined, // code 为空 → undefined
      parent_id: null,
      org_type: 'department',
      description: '说明',
      contact_person: '李四',
      contact_phone: '13900139000',
      contact_email: 'b@c.com',
      address: '某地',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('创建成功')
    expect(mockPushSafe).toHaveBeenCalledWith('/organizations')
    expect(vm.submitLoading).toBe(false)
    wrapper.unmount()
  })

  it('handleSubmit 创建：code 有值 → 透传；校验失败 → 不请求', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.name = '新单位'
    vm.formData.code = 'CODE-1'
    await clickBtn(wrapper, '保存')
    const call = mockCreateOrganization.mock.calls[0]
    expect(call[0].code).toBe('CODE-1')

    mockCreateOrganization.mockClear()
    validateResult.value = false
    await vm.handleSubmit()
    expect(mockCreateOrganization).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('handleSubmit 创建失败 → logger + 错误提示；loading 复位', async () => {
    mockCreateOrganization.mockRejectedValue(new Error('boom'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.name = '新单位'
    await vm.handleSubmit()
    expect(logError).toHaveBeenCalledWith('保存失败:', expect.any(Error))
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
    expect(vm.submitLoading).toBe(false)
    wrapper.unmount()
  })

  it('handleBack → pushSafe(/organizations)；「取消」按钮同样返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await clickBtn(wrapper, '返回')
    expect(mockPushSafe).toHaveBeenCalledWith('/organizations')
    await clickBtn(wrapper, '取消')
    expect(mockPushSafe).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })
})

describe('编辑模式', () => {
  it('有路由 id → 编辑组织标题 + loadData 填充表单 + 编码禁用 + 上级排除自身', async () => {
    routeBox.params = { id: '5' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(wrapper.text()).toContain('编辑组织')
    expect(vm.isEdit).toBe(true)
    expect(mockGetOrganization).toHaveBeenCalledWith(5)
    expect(vm.formData).toMatchObject({
      name: '总部',
      code: 'HQ',
      parent_id: 3,
      org_type: 'support_unit',
      is_active: false,
      contact_person: '张三',
      contact_phone: '13800138000',
      contact_email: 'a@b.com',
      address: '地址',
      description: '描述',
    })
    // parentOptions 排除当前 id=5
    expect(vm.parentOptions.map((o: any) => o.id)).toEqual([3, 9])
    // 编码输入框 disabled
    const codeInput = wrapper.findAllComponents({ name: 'ElInput' }).find((i: any) => i.props('disabled'))
    expect(codeInput).toBeTruthy()
    wrapper.unmount()
  })

  it('loadData 失败 → logger + 错误提示 + 跳转列表页', async () => {
    routeBox.params = { id: '5' }
    mockGetOrganization.mockRejectedValue(new Error('down'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalledWith('加载组织信息失败:', expect.any(Error))
    expect(ElMessage.error).toHaveBeenCalledWith('加载组织信息失败')
    expect(mockPushSafe).toHaveBeenCalledWith('/organizations')
    expect((wrapper.vm as any).loading).toBe(false)
    wrapper.unmount()
  })

  it('loadData：无 id → 直接返回；字段缺失 → 全兜底；is_active 未定义 → true', async () => {
    routeBox.params = {}
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.loadData() // 无 id → return
    expect(mockGetOrganization).not.toHaveBeenCalled()

    routeBox.params = { id: '8' }
    mockGetOrganization.mockResolvedValue({ id: 8 })
    await vm.loadData()
    expect(vm.formData).toMatchObject({
      name: '',
      code: '',
      parent_id: null,
      org_type: 'department',
      is_active: true,
      contact_person: '',
      contact_phone: '',
      contact_email: '',
      address: '',
      description: '',
    })
    wrapper.unmount()
  })

  it('parentOptions：res 无 items → [] 兜底', async () => {
    mockGetOrganizations.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).parentOptions).toEqual([])
    wrapper.unmount()
  })

  it('handleSubmit：formRef 为 null → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formRef = null
    await vm.handleSubmit()
    expect(mockCreateOrganization).not.toHaveBeenCalled()
    expect(mockUpdateOrganization).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('模板 v-model 内联处理器：名称/编码/上级/类型/联系人等输入', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    const set = (i: number, key: string, val: any) => {
      inputs[i].vm.$emit('update:modelValue', val)
      expect(vm.formData[key]).toBe(val)
    }
    set(0, 'name', '新名称')
    set(1, 'code', 'CODE-X')
    set(2, 'contact_person', '王五')
    set(3, 'contact_phone', '13700137000')
    set(4, 'contact_email', 'c@d.com')
    set(5, 'address', '新地址')
    inputs[6].vm.$emit('update:modelValue', '新描述')
    await nextTick()
    expect(vm.formData.description).toBe('新描述')
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 9)
    selects[1].vm.$emit('update:modelValue', 'department')
    await nextTick()
    expect(vm.formData.parent_id).toBe(9)
    expect(vm.formData.org_type).toBe('department')
    wrapper.unmount()
  })

  it('handleSubmit 编辑成功 → updateOrganization(id, 表单) + 成功提示 + 跳转', async () => {
    routeBox.params = { id: '5' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.name = '改名后的总部'
    await clickBtn(wrapper, '保存')
    expect(mockUpdateOrganization).toHaveBeenCalledWith(5, {
      name: '改名后的总部',
      parent_id: 3, // 编辑也提交上级组织（修复：此前被丢弃）
      org_type: 'support_unit',
      description: '描述',
      contact_person: '张三',
      contact_phone: '13800138000',
      contact_email: 'a@b.com',
      address: '地址',
      is_active: false,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('更新成功')
    expect(mockPushSafe).toHaveBeenCalledWith('/organizations')
    expect(mockCreateOrganization).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('编辑时 parent_id 为 null → 提交 undefined', async () => {
    routeBox.params = { id: '5' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.parent_id = null
    await clickBtn(wrapper, '保存')
    expect(mockUpdateOrganization).toHaveBeenCalledWith(5, expect.objectContaining({ parent_id: undefined }))
    wrapper.unmount()
  })


  it('handleSubmit 编辑失败 → 错误提示；空字段 → undefined', async () => {
    routeBox.params = { id: '7' }
    mockUpdateOrganization.mockRejectedValue(new Error('boom'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formData.name = 'X'
    await clickBtn(wrapper, '保存')
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
    // 空字段 → undefined 分支
    mockUpdateOrganization.mockClear()
    Object.assign(vm.formData, {
      name: 'Y',
      description: '',
      contact_person: '',
      contact_phone: '',
      contact_email: '',
      address: '',
    })
    await clickBtn(wrapper, '保存')
    const call = mockUpdateOrganization.mock.calls[0]
    expect(call[1].description).toBeUndefined()
    expect(call[1].contact_phone).toBeUndefined()
    expect(call[1].address).toBeUndefined()
    wrapper.unmount()
  })

  it('无 id 且 params 为数组 → safeRouteParam 兜底', async () => {
    routeBox.params = { id: ['9'] }
    const wrapper = mountComp()
    await flushPromises()
    expect(mockGetOrganization).toHaveBeenCalledWith(9)
    wrapper.unmount()
  })

  it('模板 v-model：状态开关切换 is_active', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const switchStub = wrapper.findComponent({ name: 'ElSwitch' })
    switchStub.vm.$emit('update:modelValue', false)
    switchStub.vm.$emit('change', false)
    await nextTick()
    expect((wrapper.vm as any).formData.is_active).toBe(false)
    wrapper.unmount()
  })
})
