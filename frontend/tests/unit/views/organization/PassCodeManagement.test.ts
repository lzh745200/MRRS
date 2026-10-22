/**
 * views/organization/PassCodeManagement.vue 覆盖率攻坚（四指标 100%）
 *
 * 覆盖：loadOrganizations 响应三形态（数组/嵌套 data/空）+ 失败、flattenTree 嵌套展开、
 * handleOrganizationChange 全分支（无 id/顶层 code/嵌套 code/无 code/失败）、
 * handleGenerateMachinePassCode 全分支（无 formRef/校验失败/成功 passCode/无 passCode/失败）、
 * handleResetMachineForm、handleGenerate 全分支、handleResetForm、handleCopyPassCode/handleCopy、
 * handleQuery 成功失败、handleResetQuery、handleExport 成功失败、handleDelete 全分支、
 * formatDateTime 两分支、模板（状态标签三分支、允许下级标签、删除按钮 v-if、生成结果展示）。
 *
 * 方案：mock '@/api/organizationPassCode'、'@/api/machineCode'、'@/api/organization'、
 * '@/utils/clipboard'、useRouterSafe、element-plus；el-form stub 提供 validate 回调。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const {
  ElMessage,
  confirmMock,
  mockVerificationCode,
  mockCreatePassCode,
  mockPassCodeList,
  mockExportPassCodes,
  mockDeletePassCode,
  mockCreateMachineCode,
  mockGetOrgTree,
  mockCopy,
  logError,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  mockVerificationCode: vi.fn(),
  mockCreatePassCode: vi.fn(),
  mockPassCodeList: vi.fn(),
  mockExportPassCodes: vi.fn(),
  mockDeletePassCode: vi.fn(),
  mockCreateMachineCode: vi.fn(),
  mockGetOrgTree: vi.fn(),
  mockCopy: vi.fn(),
  logError: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
  type: {},
}))

vi.mock('@/api/organizationPassCode', () => ({
  getOrganizationVerificationCode: (...a: any[]) => mockVerificationCode(...a),
  createOrganizationPassCode: (...a: any[]) => mockCreatePassCode(...a),
  getOrganizationPassCodeList: (...a: any[]) => mockPassCodeList(...a),
  exportOrganizationPassCodes: (...a: any[]) => mockExportPassCodes(...a),
  deleteOrganizationPassCode: (...a: any[]) => mockDeletePassCode(...a),
}))

vi.mock('@/api/machineCode', () => ({
  createMachineCode: (...a: any[]) => mockCreateMachineCode(...a),
}))

vi.mock('@/api/organization', () => ({
  getOrganizationTree: (...a: any[]) => mockGetOrgTree(...a),
}))

vi.mock('@/utils/clipboard', () => ({
  copyToClipboard: (...a: any[]) => mockCopy(...a),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import PassCodeManagement from '@/views/organization/PassCodeManagement.vue'

const orgTree = [
  {
    id: 1,
    name: '总部',
    children: [
      { id: 2, name: '分部' },
      { id: 3, name: '小队', children: [{ id: 4, name: '小组' }] },
    ],
  },
  { id: 5, name: '独立单位' },
]

const passRowA = {
  id: 10,
  organization_id: 1,
  organization_name: '总部',
  verification_code: '1234',
  pass_code: 'PASS-AAAA',
  allow_subordinate_generation: true,
  status: 'active',
  created_at: '2024-01-01T10:00:00',
}
const passRowB = {
  id: 11,
  organization_id: 2,
  organization_name: '分部',
  verification_code: '5678',
  pass_code: 'PASS-BBBB',
  allow_subordinate_generation: false,
  status: 'pending',
  created_at: '2024-02-01T10:00:00',
}
const passRowC = {
  id: 12,
  organization_id: 5,
  organization_name: '独立单位',
  verification_code: '0000',
  pass_code: 'PASS-CCCC',
  status: 'revoked',
}
const passRowD = { id: 13, pass_code: 'PASS-DDDD', status: 'weird' }

const stubs = {
  'el-card': {
    name: 'ElCard',
    template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
  },
  'el-alert': { name: 'ElAlert', template: '<div class="el-alert-stub"><slot /></div>' },
  'el-form': {
    name: 'ElForm',
    template: '<div class="el-form-stub"><slot /></div>',
    methods: {
      validate(cb?: any) {
        if (cb) {
          cb(validateResult.value)
          return Promise.resolve(validateResult.value)
        }
        return Promise.resolve(validateResult.value)
      },
      resetFields() {
        // 无操作；测试直接断言表单值
      },
    },
  },
  'el-form-item': { name: 'ElFormItem', template: '<div class="el-form-item-stub"><slot /></div>' },
  'el-input': {
    name: 'ElInput',
    props: ['modelValue'],
    template: '<div class="el-input-stub"><slot /></div>',
    emits: ['update:modelValue'],
  },
  'el-select': {
    name: 'ElSelect',
    props: ['modelValue'],
    template: '<div class="el-select-stub"><slot /></div>',
    emits: ['update:modelValue', 'change'],
  },
  'el-option': { name: 'ElOption', template: '<div />' },
  'el-switch': {
    name: 'ElSwitch',
    props: ['modelValue'],
    template: '<div class="el-switch-stub" />',
    emits: ['update:modelValue', 'change'],
  },
  'el-button': {
    name: 'ElButton',
    props: ['disabled', 'loading', 'icon'],
    template: '<button class="el-button-stub"><slot /></button>',
  },
  'el-icon': { name: 'ElIcon', template: '<span class="el-icon-stub"><slot /></span>' },
  'el-table': {
    name: 'ElTable',
    template: '<div class="el-table-stub"><slot /></div>',
    props: ['data'],
  },
  'el-table-column': {
    name: 'ElTableColumn',
    props: ['prop', 'label', 'type'],
    template:
      '<div class="el-table-column-stub" :label="label"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /><slot :row="rowD" /></div>',
    data() {
      return { rowA: passRowA, rowB: passRowB, rowC: passRowC, rowD: passRowD }
    },
  },
  'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
  'el-pagination': {
    name: 'ElPagination',
    template: '<div class="el-pagination-stub" />',
    emits: ['update:currentPage', 'update:pageSize', 'size-change', 'current-change'],
  },
}

const validateResult = { value: true }

function mountComp() {
  return mount(PassCodeManagement, {
    global: { renderStubDefaultSlot: true, stubs },
  })
}

async function clickBtn(wrapper: any, text: string, index = 0) {
  const btns = wrapper.findAll('.el-button-stub').filter((b: any) => b.text().trim().includes(text))
  expect(btns.length, `按钮「${text}」`).toBeGreaterThan(index)
  await btns[index].trigger('click')
  await flushPromises()
}

beforeEach(() => {
  vi.resetAllMocks()
  validateResult.value = true
  mockGetOrgTree.mockResolvedValue(orgTree)
  mockVerificationCode.mockResolvedValue({ verification_code: '8888', organization_id: 1 })
  mockCreatePassCode.mockResolvedValue({ pass_code: 'PASS-NEW', id: 99, organization_id: 1 })
  mockCreateMachineCode.mockResolvedValue({ pass_code: 'MACHINE-PASS' })
  mockPassCodeList.mockResolvedValue({ items: [passRowA, passRowB, passRowC, passRowD], total: 4 })
  mockExportPassCodes.mockResolvedValue(undefined)
  mockDeletePassCode.mockResolvedValue({})
  mockCopy.mockResolvedValue(true)
  confirmMock.mockResolvedValue('confirm')
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与组织列表', () => {
  it('onMounted 加载组织树（扁平化）与通行证码列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGetOrgTree).toHaveBeenCalled()
    expect(vm.organizationList.map((o: any) => o.id)).toEqual([1, 2, 3, 4, 5])
    expect(mockPassCodeList).toHaveBeenCalledWith({
      organization_id: undefined,
      status: undefined,
      page: 1,
      page_size: 20,
    })
    expect(vm.tableData.length).toBe(4)
    expect(vm.pagination.total).toBe(4)
    const text = wrapper.text()
    expect(text).toContain('PASS-AAAA')
    expect(text).toContain('已激活')
    expect(text).toContain('待使用')
    expect(text).toContain('已撤销')
    expect(text).toContain('是')
    expect(text).toContain('否')
    wrapper.unmount()
  })

  it('组织响应嵌套 data 形态 / 空 / 失败', async () => {
    mockGetOrgTree.mockResolvedValue({ data: orgTree })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).organizationList.length).toBe(5)
    wrapper.unmount()

    mockGetOrgTree.mockResolvedValue({ data: 'not-array' })
    const wrapper2 = mountComp()
    await flushPromises()
    expect((wrapper2.vm as any).organizationList).toEqual([])
    wrapper2.unmount()

    mockGetOrgTree.mockRejectedValue(new Error('tree down'))
    const wrapper3 = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('加载组织列表失败')
    wrapper3.unmount()
  })

  it('handleQuery 失败 → logger + 错误提示；loading 复位', async () => {
    mockPassCodeList.mockRejectedValue(new Error('list down'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalledWith('查询列表失败', expect.any(Error))
    expect(ElMessage.error).toHaveBeenCalledWith('查询列表失败')
    expect((wrapper.vm as any).loading).toBe(false)
    wrapper.unmount()
  })

  it('handleQuery 空响应 → items/total 兜底为空与 0', async () => {
    mockPassCodeList.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.tableData).toEqual([])
    expect(vm.pagination.total).toBe(0)
    wrapper.unmount()
  })

  it('查询与重置：携带筛选参数；重置清空并回第 1 页', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    // selects[0]=生成表单组织, [1]=查询组织, [2]=查询状态
    selects[1].vm.$emit('update:modelValue', 1)
    selects[2].vm.$emit('update:modelValue', 'active')
    await nextTick()
    mockPassCodeList.mockClear()
    await clickBtn(wrapper, '查询')
    const call = mockPassCodeList.mock.calls[mockPassCodeList.mock.calls.length - 1]
    expect(call[0]).toMatchObject({ organization_id: 1, status: 'active' })

    vm.pagination.page = 3
    mockPassCodeList.mockClear()
    await clickBtn(wrapper, '重置', 2) // 查询区「重置」（0=机器码 1=生成 2=查询）
    expect(vm.queryForm.organization_id).toBeUndefined()
    expect(vm.queryForm.status).toBeUndefined()
    expect(vm.pagination.page).toBe(1)
    expect(mockPassCodeList).toHaveBeenCalled()
    wrapper.unmount()
  })

  it('分页 size-change / current-change 触发查询', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const pager = wrapper.findComponent({ name: 'ElPagination' })
    pager.vm.$emit('update:currentPage', 2)
    pager.vm.$emit('update:pageSize', 50)
    await nextTick()
    expect(vm.pagination.page).toBe(2)
    expect(vm.pagination.page_size).toBe(50)
    mockPassCodeList.mockClear()
    pager.vm.$emit('size-change', 50)
    await flushPromises()
    pager.vm.$emit('current-change', 3)
    await flushPromises()
    expect(mockPassCodeList.mock.calls.length).toBe(2)
    wrapper.unmount()
  })
})

describe('生成机器通行码', () => {
  it('校验通过 + passCode → 展示结果 + 成功提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.machineForm.machine_code = 'a'.repeat(64)
    vm.machineForm.description = '备注'
    await clickBtn(wrapper, '生成通行码')
    expect(mockCreateMachineCode).toHaveBeenCalledWith({
      machine_code: 'a'.repeat(64),
      description: '备注',
    })
    expect(vm.machineGeneratedPassCode).toBe('MACHINE-PASS')
    expect(ElMessage.success).toHaveBeenCalledWith('通行码生成成功')
    expect(vm.machineGenerating).toBe(false)
    await nextTick()
    expect(wrapper.text()).toContain('MACHINE-PASS')
    expect(wrapper.text()).toContain('复制')
    wrapper.unmount()
  })

  it('生成成功但无 passCode → 警告提示', async () => {
    mockCreateMachineCode.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.machineForm.machine_code = 'a'.repeat(64)
    await vm.handleGenerateMachinePassCode()
    expect(ElMessage.warning).toHaveBeenCalledWith(
      '生成成功但未获取到通行码，请稍后刷新机器码管理页查看'
    )
    wrapper.unmount()
  })

  it('校验失败 → 不请求；接口失败 → logger + detail/message/兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    validateResult.value = false
    await vm.handleGenerateMachinePassCode()
    expect(mockCreateMachineCode).not.toHaveBeenCalled()
    validateResult.value = true

    mockCreateMachineCode.mockRejectedValue({ response: { data: { detail: '机器码无效' } } })
    await vm.handleGenerateMachinePassCode()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('机器码无效')

    mockCreateMachineCode.mockRejectedValue({ message: '网络错误' })
    await vm.handleGenerateMachinePassCode()
    expect(ElMessage.error).toHaveBeenCalledWith('网络错误')

    mockCreateMachineCode.mockRejectedValue({})
    await vm.handleGenerateMachinePassCode()
    expect(ElMessage.error).toHaveBeenCalledWith('生成通行码失败')
    wrapper.unmount()
  })

  it('handleResetMachineForm → 清空结果', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.machineGeneratedPassCode = 'X'
    vm.handleResetMachineForm()
    expect(vm.machineGeneratedPassCode).toBe('')
    wrapper.unmount()
  })

  it('表单 ref 为 null → handleGenerateMachinePassCode / handleGenerate 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.machineFormRef = null
    await vm.handleGenerateMachinePassCode()
    expect(mockCreateMachineCode).not.toHaveBeenCalled()
    vm.generateFormRef = null
    await vm.handleGenerate()
    expect(mockCreatePassCode).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})

describe('生成组织通行证码', () => {
  it('组织变更：顶层 code / 嵌套 data code 自动填充；无 code → 警告', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const select = wrapper.findAllComponents({ name: 'ElSelect' })[0]
    select.vm.$emit('update:modelValue', 1)
    select.vm.$emit('change', 1)
    await flushPromises()
    expect(mockVerificationCode).toHaveBeenCalledWith(1)
    expect(vm.generateForm.verification_code).toBe('8888')

    mockVerificationCode.mockResolvedValue({ data: { verification_code: '7777' } })
    await vm.handleOrganizationChange(2)
    expect(vm.generateForm.verification_code).toBe('7777')

    mockVerificationCode.mockResolvedValue({})
    await vm.handleOrganizationChange(3)
    expect(ElMessage.warning).toHaveBeenCalledWith('未能获取校验码，请手动输入')
    wrapper.unmount()
  })

  it('组织变更失败 → 警告；orgId 为空 → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleOrganizationChange(0 as any)
    expect(mockVerificationCode).not.toHaveBeenCalled()
    mockVerificationCode.mockRejectedValue(new Error('code down'))
    await vm.handleOrganizationChange(1)
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.warning).toHaveBeenCalledWith(
      '自动获取校验码失败，请手动输入下级单位提供的校验码'
    )
    wrapper.unmount()
  })

  it('handleGenerate 成功 → 展示通行码 + 成功提示 + 回第 1 页刷新；无 passCode → 警告', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.generateForm.organization_id = 1
    vm.generateForm.verification_code = '8888'
    vm.pagination.page = 3
    await clickBtn(wrapper, '生成通行证码')
    expect(mockCreatePassCode).toHaveBeenCalledWith(expect.objectContaining({ organization_id: 1 }))
    expect(vm.generatedPassCode).toBe('PASS-NEW')
    expect(ElMessage.success).toHaveBeenCalledWith('通行证码生成成功')
    expect(vm.pagination.page).toBe(1)
    expect(mockPassCodeList).toHaveBeenCalled()
    expect(vm.generating).toBe(false)
    await nextTick()
    expect(wrapper.text()).toContain('PASS-NEW')

    mockCreatePassCode.mockResolvedValue({})
    await vm.handleGenerate()
    expect(ElMessage.warning).toHaveBeenCalledWith('生成成功但未获取到通行码，请刷新列表查看')
    wrapper.unmount()
  })

  it('passCode 嵌套在 data 中的响应形态（机器码/组织两处 ?? 兜底）', async () => {
    mockCreateMachineCode.mockResolvedValue({ data: { pass_code: 'MACHINE-NESTED' } })
    mockCreatePassCode.mockResolvedValue({ data: { pass_code: 'PASS-NESTED' } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.machineForm.machine_code = 'a'.repeat(64)
    await vm.handleGenerateMachinePassCode()
    expect(vm.machineGeneratedPassCode).toBe('MACHINE-NESTED')

    vm.generateForm.organization_id = 1
    vm.generateForm.verification_code = '8888'
    await vm.handleGenerate()
    expect(vm.generatedPassCode).toBe('PASS-NESTED')
    wrapper.unmount()
  })

  it('handleGenerate：校验失败不请求；失败 detail/message/兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    validateResult.value = false
    await vm.handleGenerate()
    expect(mockCreatePassCode).not.toHaveBeenCalled()
    validateResult.value = true

    mockCreatePassCode.mockRejectedValue({ response: { data: { detail: '组织不存在' } } })
    await vm.handleGenerate()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('组织不存在')

    mockCreatePassCode.mockRejectedValue({ response: { data: { message: '禁止生成' } } })
    await vm.handleGenerate()
    expect(ElMessage.error).toHaveBeenCalledWith('禁止生成')

    mockCreatePassCode.mockRejectedValue({ message: '网络错误' })
    await vm.handleGenerate()
    expect(ElMessage.error).toHaveBeenCalledWith('网络错误')

    mockCreatePassCode.mockRejectedValue({})
    await vm.handleGenerate()
    expect(ElMessage.error).toHaveBeenCalledWith('生成通行证码失败')
    wrapper.unmount()
  })

  it('handleResetForm / handleCopyPassCode / handleCopy', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.generatedPassCode = 'PASS-X'
    vm.handleResetForm()
    expect(vm.generatedPassCode).toBe('')

    vm.generatedPassCode = 'PASS-Y'
    vm.handleCopyPassCode()
    expect(mockCopy).toHaveBeenCalledWith('PASS-Y', '通行证码')

    await vm.handleCopy('TEXT-Z')
    expect(mockCopy).toHaveBeenCalledWith('TEXT-Z', '通行证码')
    wrapper.unmount()
  })
})

describe('删除与导出', () => {
  it('handleDelete：确认 → 删除 + 成功 + 刷新；cancel/close 静默；其他失败 detail 与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await clickBtn(wrapper, '删除', 0) // passRowA pending → 有删除按钮
    expect(confirmMock).toHaveBeenCalledWith(
      '确定删除该通行证码记录吗？删除后该通行证码将无法再用于注册。',
      '删除确认',
      expect.anything()
    )
    expect(mockDeletePassCode).toHaveBeenCalledWith(11)
    expect(ElMessage.success).toHaveBeenCalledWith('通行证码记录已删除')
    expect(mockPassCodeList).toHaveBeenCalled()

    confirmMock.mockRejectedValueOnce('cancel')
    await vm.handleDelete(passRowA as any)
    expect(mockDeletePassCode).toHaveBeenCalledTimes(1)

    confirmMock.mockRejectedValueOnce('close')
    await vm.handleDelete(passRowA as any)
    expect(mockDeletePassCode).toHaveBeenCalledTimes(1)

    mockDeletePassCode.mockRejectedValue({ response: { data: { detail: '已使用不可删' } } })
    await vm.handleDelete(passRowA as any)
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('已使用不可删')

    mockDeletePassCode.mockRejectedValue({})
    await vm.handleDelete(passRowA as any)
    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
    wrapper.unmount()
  })

  it('handleExport 成功与失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await clickBtn(wrapper, '导出')
    expect(mockExportPassCodes).toHaveBeenCalledWith({
      organization_id: undefined,
      status: undefined,
    })
    expect(vm.exporting).toBe(false)

    mockExportPassCodes.mockRejectedValue(new Error('export down'))
    await vm.handleExport()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('导出失败')
    expect(vm.exporting).toBe(false)
    wrapper.unmount()
  })
})

describe('格式化与模板', () => {
  it('formatDateTime 两分支', () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.formatDateTime('')).toBe('-')
    expect(vm.formatDateTime(undefined as any)).toBe('-')
    expect(vm.formatDateTime('2024-01-01T10:30:00')).toContain('2024')
    wrapper.unmount()
  })

  it('表格：复制按钮 → handleCopy；非 pending 状态显示 -', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('-') // revoked/weird 行操作列
    // 复制按钮点击（pass_code 列）
    const copyBtns = wrapper
      .findAll('.el-button-stub')
      .filter((b: any) => b.find('.el-icon-stub').exists() && b.text().trim() === '')
    if (copyBtns.length) {
      await copyBtns[0].trigger('click')
      expect(mockCopy).toHaveBeenCalledWith('PASS-AAAA', '通行证码')
    }
    wrapper.unmount()
  })

  it('模板 v-model 内联处理器：机器码/两处描述输入、机器通行码复制、行内复制', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    // [0]=machine_code [1]=machine description [2]=verification_code [3]=generate description
    inputs[0].vm.$emit('update:modelValue', 'm'.repeat(64))
    inputs[1].vm.$emit('update:modelValue', '机器备注')
    await nextTick()
    expect(vm.machineForm.machine_code).toBe('m'.repeat(64))
    expect(vm.machineForm.description).toBe('机器备注')

    inputs[2].vm.$emit('update:modelValue', '5555')
    inputs[3].vm.$emit('update:modelValue', '生成备注')
    await nextTick()
    expect(vm.generateForm.verification_code).toBe('5555')
    expect(vm.generateForm.description).toBe('生成备注')

    const switches = wrapper.findAllComponents({ name: 'ElSwitch' })
    switches[0].vm.$emit('update:modelValue', true)
    switches[0].vm.$emit('change', true)
    await nextTick()
    expect(vm.generateForm.allow_subordinate_generation).toBe(true)

    // 机器通行码生成结果「复制」按钮 → copyToClipboard(机器通行码)
    vm.machineGeneratedPassCode = 'MACHINE-X'
    await nextTick()
    const copyBtns = wrapper
      .findAll('.el-button-stub')
      .filter((b: any) => b.text().trim() === '复制')
    expect(copyBtns.length).toBeGreaterThanOrEqual(1)
    await copyBtns[0].trigger('click')
    expect(mockCopy).toHaveBeenCalledWith('MACHINE-X', '通行码')
    wrapper.unmount()
  })

  it('表格行内复制按钮 → handleCopy(row.pass_code)', async () => {
    const wrapper = mountComp()
    await flushPromises()
    // pass_code 列的纯图标复制按钮（icon 经 prop 传入，stub 不渲染 → 空文本按钮）
    const iconBtns = wrapper.findAll('.el-button-stub').filter((b: any) => b.text().trim() === '')
    expect(iconBtns.length).toBeGreaterThan(0)
    await iconBtns[0].trigger('click')
    expect(mockCopy).toHaveBeenCalledWith('PASS-AAAA', '通行证码')
    wrapper.unmount()
  })
})
