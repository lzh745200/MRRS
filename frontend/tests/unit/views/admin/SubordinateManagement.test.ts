/**
 * views/admin/SubordinateManagement.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：列表加载（envelope/裸响应/失败三态）、分页、注册校验/成功/失败、
 * 授权/撤销（确认取消静默 + 请求失败必须提示，M45）、生成管控包、上报包导入、
 * 字典函数与模板内联处理器、v-model 真实 DOM 输入。
 *
 * 覆盖率合并不变量：本文件是该组件的唯一执行者（router-index.test.ts 已桩替换），
 * 不要再从其它测试文件 import/mount 本组件。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'

enableAutoUnmount(afterEach)

const { ElMessage, confirmMock, mockGet, mockPost, mockPut } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  confirmMock: vi.fn(),
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  mockPut: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/request', () => ({
  get: (...a: any[]) => mockGet(...a),
  post: (...a: any[]) => mockPost(...a),
  put: (...a: any[]) => mockPut(...a),
}))

import SubordinateManagement from '@/views/admin/SubordinateManagement.vue'

const rowActive = {
  id: 1,
  instanceCode: 'INST-0001',
  organizationId: 10,
  systemVersion: '1.0.0',
  licenseStatus: 'active',
  status: 'online',
  userCount: 5,
  lastReportAt: '2026-01-01 10:00',
}

const rowRevoked = {
  ...rowActive,
  id: 2,
  licenseStatus: 'revoked',
  status: 'offline',
}

function makeStubs(row: Record<string, any>) {
  return {
    'el-button': {
      name: 'ElButton',
      props: ['disabled', 'loading'],
      template: '<button class="el-button-stub" :disabled="disabled"><slot /></button>',
    },
    'el-card': {
      name: 'ElCard',
      template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
    },
    'el-table': { name: 'ElTable', template: '<table class="el-table-stub"><slot /></table>' },
    'el-table-column': {
      name: 'ElTableColumn',
      // 注入固定行数据，让操作列按钮与 tag 文本真实渲染
      template: '<div class="el-table-column-stub"><slot :row="row" /></div>',
      data: () => ({ row }),
    },
    'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
    'el-pagination': {
      name: 'ElPagination',
      emits: ['current-change'],
      template: '<div class="el-pagination-stub" />',
    },
    'el-dialog': {
      name: 'ElDialog',
      props: ['modelValue'],
      emits: ['update:modelValue'],
      template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
    },
    'el-form': { name: 'ElForm', template: '<form><slot /></form>' },
    'el-form-item': { name: 'ElFormItem', template: '<div class="el-form-item-stub"><slot /></div>' },
    'el-input': {
      name: 'ElInput',
      props: ['modelValue'],
      emits: ['update:modelValue'],
      template:
        '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    },
    'el-input-number': {
      name: 'ElInputNumber',
      props: ['modelValue'],
      emits: ['update:modelValue'],
      template:
        '<input class="el-input-number-stub" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
    },
    'el-date-picker': {
      name: 'ElDatePicker',
      props: ['modelValue'],
      emits: ['update:modelValue'],
      template:
        '<div class="el-date-stub" @click="$emit(\'update:modelValue\', \'2026-06-30\')" />',
    },
  }
}

async function mountComp(row: Record<string, any> = rowActive) {
  const wrapper = mount(SubordinateManagement, {
    global: { renderStubDefaultSlot: true, stubs: makeStubs(row) },
  })
  await flushPromises()
  return wrapper
}

function findBtn(wrapper: any, text: string) {
  const btn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().includes(text))
  expect(btn, `按钮「${text}」`).toBeTruthy()
  return btn!
}

beforeEach(() => {
  vi.clearAllMocks()
  mockGet.mockResolvedValue({ data: { items: [rowActive], total: 25 } })
  mockPost.mockResolvedValue({})
  mockPut.mockResolvedValue({})
  confirmMock.mockResolvedValue('confirm')
})

describe('SubordinateManagement.vue 列表加载', () => {
  it('加载成功（envelope）：填充实例/总数，渲染分页与行内按钮', async () => {
    const wrapper = await mountComp(rowActive)
    const vm = wrapper.vm as any
    expect(mockGet).toHaveBeenCalledWith('/subordinates', { page: 1, page_size: 20 })
    expect(vm.instances).toHaveLength(1)
    expect(vm.total).toBe(25)
    expect(vm.loading).toBe(false)
    // 模板分支：licenseStatus=active → 「撤销」；status=online → 「在线」；tag 已授权
    expect(wrapper.text()).toContain('撤销')
    expect(wrapper.text()).toContain('在线')
    expect(wrapper.text()).toContain('已授权')
    expect(wrapper.find('.el-pagination-stub').exists()).toBe(true)

    // 分页切换 → page 更新并重新加载
    mockGet.mockClear()
    wrapper.findComponent({ name: 'ElPagination' }).vm.$emit('current-change', 2)
    await flushPromises()
    expect(vm.page).toBe(2)
    expect(mockGet).toHaveBeenCalledWith('/subordinates', { page: 2, page_size: 20 })
  })

  it('加载成功（裸响应）且缺 items/total → [] 与 0 兜底，分页隐藏', async () => {
    mockGet.mockResolvedValue({})
    const wrapper = await mountComp(rowRevoked)
    const vm = wrapper.vm as any
    expect(vm.instances).toEqual([])
    expect(vm.total).toBe(0)
    expect(wrapper.find('.el-pagination-stub').exists()).toBe(false)
    // row licenseStatus=revoked → 「授权」；status=offline → 「离线」；tag 已撤销
    expect(wrapper.text()).toContain('授权')
    expect(wrapper.text()).toContain('离线')
    expect(wrapper.text()).toContain('已撤销')
  })

  it('加载失败：优先服务端 detail，其次 error.message，最后兜底', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any

    mockGet.mockRejectedValueOnce({ response: { data: { detail: '权限不足' } } })
    await vm.loadData()
    expect(ElMessage.error).toHaveBeenCalledWith('权限不足')

    mockGet.mockRejectedValueOnce(new Error('网络错误'))
    await vm.loadData()
    expect(ElMessage.error).toHaveBeenCalledWith('网络错误')

    mockGet.mockRejectedValueOnce({})
    await vm.loadData()
    expect(ElMessage.error).toHaveBeenCalledWith('加载失败')
    expect(vm.loading).toBe(false)
  })

  it('字典函数：全映射与未知透传', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    expect(vm.licenseTagType('active')).toBe('success')
    expect(vm.licenseTagType('pending')).toBe('warning')
    expect(vm.licenseTagType('expired')).toBe('danger')
    expect(vm.licenseTagType('revoked')).toBe('info')
    expect(vm.licenseTagType('unknown')).toBe('info')
    expect(vm.licenseLabel('active')).toBe('已授权')
    expect(vm.licenseLabel('pending')).toBe('待授权')
    expect(vm.licenseLabel('expired')).toBe('已过期')
    expect(vm.licenseLabel('revoked')).toBe('已撤销')
    expect(vm.licenseLabel('unknown')).toBe('unknown')
  })
})

describe('SubordinateManagement.vue 注册', () => {
  it('实例标识为空/过短 → 警告且不发请求', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    await vm.handleRegister()
    expect(ElMessage.warning).toHaveBeenCalledWith('实例标识至少8位')
    vm.registerForm.instance_code = 'abc'
    await vm.handleRegister()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('注册成功：提交表单、关闭弹窗、重置表单并回到第 1 页刷新', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.page = 3
    vm.registerForm = {
      organization_id: 9,
      instance_code: 'INST-0002',
      machine_code: 'MC-1',
      license_expiry: '2026-12-31',
      remark: '测试',
    }
    mockPost.mockResolvedValueOnce({})
    await vm.handleRegister()
    expect(mockPost).toHaveBeenCalledWith('/subordinates', {
      organization_id: 9,
      instance_code: 'INST-0002',
      machine_code: 'MC-1',
      license_expiry: '2026-12-31',
      remark: '测试',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('注册成功')
    expect(vm.showRegisterDialog).toBe(false)
    expect(vm.registerForm.instance_code).toBe('')
    expect(vm.page).toBe(1)
    expect(mockGet).toHaveBeenCalled()
    expect(vm.registering).toBe(false)
  })

  it('注册失败：提示服务端原因或兜底文案', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    vm.registerForm.instance_code = 'INST-0003'

    mockPost.mockRejectedValueOnce(new Error('实例标识已存在'))
    await vm.handleRegister()
    expect(ElMessage.error).toHaveBeenCalledWith('实例标识已存在')

    mockPost.mockRejectedValueOnce({})
    await vm.handleRegister()
    expect(ElMessage.error).toHaveBeenCalledWith('注册失败')
  })

  it('弹窗交互：注册按钮打开、取消关闭、dialog v-model、确认注册按钮转发', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    expect(vm.showRegisterDialog).toBe(false)

    await findBtn(wrapper, '注册下级单位').trigger('click')
    expect(vm.showRegisterDialog).toBe(true)

    // 弹窗 v-model：$emit update:modelValue 同步状态
    wrapper.findComponent({ name: 'ElDialog' }).vm.$emit('update:modelValue', false)
    expect(vm.showRegisterDialog).toBe(false)

    await findBtn(wrapper, '取消').trigger('click')
    expect(vm.showRegisterDialog).toBe(false)

    await findBtn(wrapper, '注册下级单位').trigger('click')
    mockPost.mockClear()
    await findBtn(wrapper, '确认注册').trigger('click')
    await flushPromises()
    expect(ElMessage.warning).toHaveBeenCalledWith('实例标识至少8位')
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('注册表单 v-model：真实 DOM 输入同步 organization_id/instance_code/machine_code/日期/备注', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    const numberInput = wrapper.find('.el-input-number-stub')
    await numberInput.setValue('9')
    expect(vm.registerForm.organization_id).toBe(9)

    const inputs = wrapper.findAll('input:not(.el-input-number-stub)')
    await inputs[0].setValue('INST-9999')
    await inputs[1].setValue('MC-999')
    await inputs[2].setValue('备注内容')
    expect(vm.registerForm.instance_code).toBe('INST-9999')
    expect(vm.registerForm.machine_code).toBe('MC-999')
    expect(vm.registerForm.remark).toBe('备注内容')

    await wrapper.find('.el-date-stub').trigger('click')
    expect(vm.registerForm.license_expiry).toBe('2026-06-30')
  })
})

describe('SubordinateManagement.vue 授权/撤销（M45）', () => {
  it('确认框取消 → 静默返回，不发请求不提示', async () => {
    confirmMock.mockRejectedValueOnce('cancel')
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    await vm.handleToggleLicense(rowActive)
    expect(confirmMock).toHaveBeenCalledWith('确认撤销授权该下级单位？', '提示', {
      type: 'warning',
    })
    expect(mockPut).not.toHaveBeenCalled()
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('确认后撤销成功 → PUT 正确载荷、提示并刷新', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    mockGet.mockClear()
    await vm.handleToggleLicense(rowActive)
    expect(mockPut).toHaveBeenCalledWith('/subordinates/1', { license_status: 'revoked' })
    expect(ElMessage.success).toHaveBeenCalledWith('撤销授权成功')
    expect(vm.page).toBe(1)
    expect(mockGet).toHaveBeenCalled()
  })

  it('确认后授权成功（非 active → active）', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    await vm.handleToggleLicense(rowRevoked)
    expect(mockPut).toHaveBeenCalledWith('/subordinates/2', { license_status: 'active' })
    expect(ElMessage.success).toHaveBeenCalledWith('授权成功')
  })

  it('请求失败不再被吞：提示服务端原因/兜底文案（原先静默）', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any

    mockPut.mockRejectedValueOnce(new Error('网络错误'))
    await vm.handleToggleLicense(rowActive)
    expect(ElMessage.error).toHaveBeenCalledWith('网络错误')

    mockPut.mockRejectedValueOnce({ response: { data: { detail: '无权操作' } } })
    await vm.handleToggleLicense(rowRevoked)
    expect(ElMessage.error).toHaveBeenCalledWith('无权操作')

    mockPut.mockRejectedValueOnce({})
    await vm.handleToggleLicense(rowActive)
    expect(ElMessage.error).toHaveBeenCalledWith('撤销授权失败')

    mockPut.mockRejectedValueOnce({})
    await vm.handleToggleLicense(rowRevoked)
    expect(ElMessage.error).toHaveBeenCalledWith('授权失败')
  })

  it('操作列按钮点击 → 转发 handleToggleLicense（模板内联箭头）', async () => {
    const wrapper = await mountComp(rowActive)
    await findBtn(wrapper, '撤销').trigger('click')
    await flushPromises()
    expect(confirmMock).toHaveBeenCalled()
  })
})

describe('SubordinateManagement.vue 管控包/上报包导入', () => {
  it('生成管控包成功与失败', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    await vm.handleGeneratePackage(rowActive)
    expect(mockPost).toHaveBeenCalledWith('/control-packages/generate', { organization_id: 10 })
    expect(ElMessage.success).toHaveBeenCalledWith('管控配置包已生成，请下载')

    mockPost.mockRejectedValueOnce(new Error('生成服务不可用'))
    await vm.handleGeneratePackage(rowActive)
    expect(ElMessage.error).toHaveBeenCalledWith('生成服务不可用')

    mockPost.mockRejectedValueOnce({})
    await vm.handleGeneratePackage(rowActive)
    expect(ElMessage.error).toHaveBeenCalledWith('生成失败')
  })

  it('生成管控包按钮点击（模板内联箭头）', async () => {
    const wrapper = await mountComp()
    await findBtn(wrapper, '生成管控包').trigger('click')
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith('/control-packages/generate', { organization_id: 10 })
  })

  it('点击「导入上报包」触发隐藏文件输入', async () => {
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = await mountComp()
    await findBtn(wrapper, '导入上报包').trigger('click')
    expect(clickSpy).toHaveBeenCalled()
    clickSpy.mockRestore()
  })

  it('handleFileSelected：无文件直接返回', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    await vm.handleFileSelected({ target: {} })
    await vm.handleFileSelected({ target: { files: [] } })
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('handleFileSelected：导入成功（含 message）并刷新、清空 input', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    mockGet.mockClear()
    mockPost.mockResolvedValueOnce({ data: { message: '导入成功 5 条' } })
    const target = { files: [new File(['x'], 'report.zip')], value: 'C:\\fakepath\\report.zip' }
    await vm.handleFileSelected({ target })
    expect(mockPost.mock.calls[0][0]).toBe('/subordinate-reports/import')
    expect(mockPost.mock.calls[0][1]).toBeInstanceOf(FormData)
    expect(ElMessage.success).toHaveBeenCalledWith('导入成功 5 条')
    expect(vm.page).toBe(1)
    expect(mockGet).toHaveBeenCalled()
    expect(target.value).toBe('')
  })

  it('handleFileSelected：成功但无 message → 默认文案；失败 → 服务端原因/兜底', async () => {
    const wrapper = await mountComp()
    const vm = wrapper.vm as any
    mockPost.mockResolvedValueOnce({})
    await vm.handleFileSelected({ target: { files: [new File(['x'], 'a.zip')] } })
    expect(ElMessage.success).toHaveBeenCalledWith('上报包导入成功')

    mockPost.mockRejectedValueOnce(new Error('格式错误'))
    await vm.handleFileSelected({ target: { files: [new File(['x'], 'b.zip')] } })
    expect(ElMessage.error).toHaveBeenCalledWith('格式错误')

    mockPost.mockRejectedValueOnce({})
    await vm.handleFileSelected({ target: { files: [new File(['x'], 'c.zip')] } })
    expect(ElMessage.error).toHaveBeenCalledWith('导入失败')
  })
})
