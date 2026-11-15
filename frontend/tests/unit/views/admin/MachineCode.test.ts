/**
 * views/admin/MachineCode.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：isAdmin 管理员/非管理员/超管三分支、getMachineCode 成败、
 * generatePassword/resetPassword 三个校验分支与成功/异常、复制按钮与「使用当前机器码」、
 * 六个表单 v-model、机器码/生成密码/重置结果三处模板渲染。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const { ElMessage, mockFetchMachineCode, mockGeneratePassword, mockResetPassword, mockIssueRecoveryCode, copyMock, userStoreMock } =
  vi.hoisted(() => ({
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
    mockFetchMachineCode: vi.fn(),
    mockGeneratePassword: vi.fn(),
    mockResetPassword: vi.fn(),
    mockIssueRecoveryCode: vi.fn(() => Promise.resolve({ data: { verification_code: '12345678' } })),
    copyMock: vi.fn(() => Promise.resolve(true)),
    userStoreMock: { currentUser: { role: 'admin' } },
  }))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/machineCode', () => ({
  getMachineCode: mockFetchMachineCode,
  generateInitialPassword: mockGeneratePassword,
  resetPasswordWithMachineCode: mockResetPassword,
  issueRecoveryCode: mockIssueRecoveryCode,
}))

vi.mock('@/utils/clipboard', () => ({
  copyToClipboard: copyMock,
}))

vi.mock('@/stores/user', () => ({
  useUserStore: () => userStoreMock,
}))

import MachineCode from '@/views/admin/MachineCode.vue'

const machineData = {
  machine_code: 'MC-ABCD-1234',
  verification_code: '12345678',
  machine_info: {
    system: 'Linux',
    release: '5.10',
    node: 'host1',
    processor: 'x86_64',
    machine: 'x86_64',
  },
}

const stubs = {
  'el-button': {
    name: 'ElButton',
    props: ['disabled', 'loading'],
    template: '<button class="el-button-stub" :disabled="disabled"><slot /></button>',
  },
  'el-card': {
    name: 'ElCard',
    template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
  },
  'el-input': {
    name: 'ElInput',
    props: ['modelValue'],
    template:
      '<div class="el-input-stub">{{ modelValue }}<slot /><slot name="append" /></div>',
    emits: ['update:modelValue', 'change'],
  },
  'el-descriptions': {
    name: 'ElDescriptions',
    template: '<dl class="el-descriptions-stub"><slot /></dl>',
  },
  'el-descriptions-item': {
    name: 'ElDescriptionsItem',
    template: '<div class="el-desc-item-stub"><slot /></div>',
  },
  'el-alert': {
    name: 'ElAlert',
    props: ['title', 'type'],
    template:
      '<div class="el-alert-stub"><span class="alert-title">{{ title }}</span><slot /><slot name="title" /></div>',
  },
  'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
}

function mountComp() {
  return mount(MachineCode, {
    global: { renderStubDefaultSlot: true, stubs },
  })
}

const findBtn = (wrapper: any, text: string) => {
  const btn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().trim() === text)
  expect(btn, `按钮「${text}」`).toBeTruthy()
  return btn!
}

beforeEach(() => {
  vi.resetAllMocks()
  userStoreMock.currentUser = { role: 'admin' }
  mockFetchMachineCode.mockResolvedValue(machineData)
  mockGeneratePassword.mockResolvedValue({ username: 'u1', initial_password: 'P@ss1234' })
  mockResetPassword.mockResolvedValue({ username: 'u1', new_password: 'N3w@Pass' })
})

describe('挂载与机器码', () => {
  it('管理员挂载：onMounted 获取机器码成功并渲染机器信息/校验码说明', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockFetchMachineCode).toHaveBeenCalledTimes(1)
    expect(vm.machineData).toEqual(machineData)
    expect(vm.loading).toBe(false)
    expect(ElMessage.success).toHaveBeenCalledWith('机器码获取成功')
    expect(vm.isAdmin).toBe(true)
    const text = wrapper.text()
    expect(text).toContain('机器码管理')
    expect(text).toContain('MC-ABCD-1234')
    expect(text).toContain('5678')
    expect(text).toContain('Linux')
    expect(text).toContain('5.10')
    expect(text).toContain('host1')
    expect(text).toContain('x86_64')
    expect(wrapper.find('.generate-password-card').exists()).toBe(true)
  })

  it('非管理员：生成密码卡片隐藏（isAdmin=false）', async () => {
    userStoreMock.currentUser = { role: 'guest' }
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).isAdmin).toBe(false)
    expect(wrapper.find('.generate-password-card').exists()).toBe(false)
  })

  it('超管角色 isAdmin=true（super_admin）', async () => {
    userStoreMock.currentUser = { role: 'super_admin' }
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).isAdmin).toBe(true)
  })

  it('获取机器码失败：message 与默认文案；「获取机器码」按钮重试', async () => {
    mockFetchMachineCode.mockRejectedValueOnce({ message: '未授权' })
    let wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenLastCalledWith('未授权')
    expect((wrapper.vm as any).machineData).toBeNull()

    mockFetchMachineCode.mockRejectedValueOnce({})
    wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenLastCalledWith('获取机器码失败')
    expect((wrapper.vm as any).loading).toBe(false)

    mockFetchMachineCode.mockResolvedValueOnce(machineData)
    await findBtn(wrapper, '获取机器码').trigger('click')
    await flushPromises()
    expect((wrapper.vm as any).machineData).toEqual(machineData)
  })
})

describe('生成初始密码', () => {
  it('用户名为空 → 警告且不发请求（恢复码已不再要求）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.generatePassword()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入用户名')
    expect(mockGeneratePassword).not.toHaveBeenCalled()

    vm.passwordForm.username = 'u1'
    await vm.generatePassword()
    expect(mockGeneratePassword).toHaveBeenCalledWith({ username: 'u1', verification_code: '' })
  })

  it('issueRecoveryCode 返回裸对象（无 data 包装）也能取恢复码', async () => {
    mockIssueRecoveryCode.mockResolvedValue({ verification_code: '87654321' })
    mockFetchMachineCode.mockResolvedValue({ machine_code: 'MC-1', machine_info: {} })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.getMachineCode()
    expect(vm.machineData.verification_code).toBe('87654321')
  })

  it('成功：生成密码并渲染结果区；「生成密码」按钮点击触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.passwordForm.username = 'u1'
    vm.passwordForm.verification_code = '12345678'
    await findBtn(wrapper, '生成密码').trigger('click')
    await flushPromises()
    expect(mockGeneratePassword).toHaveBeenCalledWith({ username: 'u1', verification_code: '12345678' })
    expect(ElMessage.success).toHaveBeenCalledWith('初始密码已生成')
    expect(vm.generatedPassword.initial_password).toBe('P@ss1234')
    await nextTick()
    expect(wrapper.text()).toContain('P@ss1234')
    expect(vm.generating).toBe(false)
  })

  it('异常：message 与默认「生成密码失败」', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.passwordForm.username = 'u1'
    vm.passwordForm.verification_code = '12345678'

    mockGeneratePassword.mockRejectedValueOnce({ message: '校验码无效' })
    await vm.generatePassword()
    expect(ElMessage.error).toHaveBeenLastCalledWith('校验码无效')

    mockGeneratePassword.mockRejectedValueOnce({})
    await vm.generatePassword()
    expect(ElMessage.error).toHaveBeenLastCalledWith('生成密码失败')
    expect(vm.generating).toBe(false)
  })
})

describe('重置密码', () => {
  it('三个校验分支均警告且不发请求', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.resetPassword()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入用户名')

    vm.resetForm.username = 'u1'
    await vm.resetPassword()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入机器码')

    vm.resetForm.machine_code = 'MC-X'
    await vm.resetPassword()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入恢复码')
    expect(mockResetPassword).not.toHaveBeenCalled()
  })

  it('成功：重置并渲染新密码；「重置密码」按钮点击触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.resetForm.username = 'u1'
    vm.resetForm.machine_code = 'MC-X'
    vm.resetForm.verification_code = '12345678'
    await findBtn(wrapper, '重置密码').trigger('click')
    await flushPromises()
    expect(mockResetPassword).toHaveBeenCalledWith({
      username: 'u1',
      machine_code: 'MC-X',
      verification_code: '12345678',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('密码已重置')
    expect(vm.resetResult.new_password).toBe('N3w@Pass')
    await nextTick()
    expect(wrapper.text()).toContain('N3w@Pass')
    expect(vm.resetting).toBe(false)
  })

  it('异常：message 与默认「重置密码失败」', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.resetForm.username = 'u1'
    vm.resetForm.machine_code = 'MC-X'
    vm.resetForm.verification_code = '12345678'

    mockResetPassword.mockRejectedValueOnce({ message: '机器码不存在' })
    await vm.resetPassword()
    expect(ElMessage.error).toHaveBeenLastCalledWith('机器码不存在')

    mockResetPassword.mockRejectedValueOnce({})
    await vm.resetPassword()
    expect(ElMessage.error).toHaveBeenLastCalledWith('重置密码失败')
    expect(vm.resetting).toBe(false)
  })
})

describe('复制与模板交互', () => {
  it('复制机器码 / 生成密码复制 / 重置密码复制 / 使用当前机器码', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await findBtn(wrapper, '复制').trigger('click')
    expect(copyMock).toHaveBeenLastCalledWith('MC-ABCD-1234')

    await findBtn(wrapper, '使用当前机器码').trigger('click')
    expect(vm.resetForm.machine_code).toBe('MC-ABCD-1234')

    vm.generatedPassword = { username: 'u1', initial_password: 'P@ss1234' }
    vm.resetResult = { username: 'u1', new_password: 'N3w@Pass' }
    await nextTick()
    const copyBtns = wrapper.findAll('.el-button-stub').filter((b: any) => b.text().trim() === '复制密码')
    expect(copyBtns).toHaveLength(2)
    await copyBtns[0].trigger('click')
    expect(copyMock).toHaveBeenLastCalledWith('P@ss1234')
    await copyBtns[1].trigger('click')
    expect(copyMock).toHaveBeenLastCalledWith('N3w@Pass')
  })

  it('机器码为空时「使用当前机器码」置空', async () => {
    mockFetchMachineCode.mockRejectedValueOnce(new Error('x'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.machineData).toBeNull()
    await findBtn(wrapper, '使用当前机器码').trigger('click')
    expect(vm.resetForm.machine_code).toBe('')
  })

  it('全部表单 v-model 同步（机器码与密码/重置表单共 5 个）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    expect(inputs.length).toBeGreaterThanOrEqual(5)
    inputs[0].vm.$emit('update:modelValue', 'MC-NEW') // 机器码展示框（readonly）
    expect(vm.machineData.machine_code).toBe('MC-NEW')
    inputs[1].vm.$emit('update:modelValue', 'admin')
    expect(vm.passwordForm.username).toBe('admin')
    inputs[2].vm.$emit('update:modelValue', 'ops')
    expect(vm.resetForm.username).toBe('ops')
    inputs[3].vm.$emit('update:modelValue', 'MC-OPS')
    expect(vm.resetForm.machine_code).toBe('MC-OPS')
    inputs[4].vm.$emit('update:modelValue', '12345678')

  })
})
