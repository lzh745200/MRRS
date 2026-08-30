/**
 * views/auth/ForgotPassword.vue 覆盖率攻坚
 * 覆盖：canSubmit、机器码自动填充、密码重置三分支、复制密码、导航
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const { mockPushSafe, ElMessage, logError, mockGet, mockPost, clipWrite } = vi.hoisted(() => ({
  mockPushSafe: vi.fn(() => Promise.resolve()),
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  logError: vi.fn(),
  mockGet: vi.fn(),
  mockPost: vi.fn(),
  clipWrite: vi.fn(() => Promise.resolve()),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(() => Promise.resolve()),
    resolve: vi.fn(() => ({ name: 'x', matched: [{ path: '/x' }] })),
  }),
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ push: mockPushSafe, pushSafe: mockPushSafe }),
  pushSafe: mockPushSafe,
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() },
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: vi.fn(() => Promise.resolve('confirm')), alert: vi.fn() },
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

import ForgotPassword from '@/views/auth/ForgotPassword.vue'

async function mountComp() {
  const w = mount(ForgotPassword, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-steps': { name: 'ElSteps', template: '<div class="el-steps-stub"><slot /></div>' },
        'el-step': { name: 'ElStep', template: '<div class="el-step-stub"><slot /></div>' },
        'el-form': { name: 'ElForm', template: '<form class="el-form-stub"><slot /></form>' },
        'el-form-item': { name: 'ElFormItem', template: '<div><slot /></div>' },
        'el-input': {
          name: 'ElInput',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        'el-button': {
          name: 'ElButton',
          template: '<button @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-alert': {
          name: 'ElAlert',
          template: '<div class="el-alert-stub"><slot /><slot name="title" /></div>',
        },
        'el-icon': { name: 'ElIcon', template: '<span><slot /></span>' },
        'el-radio-group': {
          name: 'ElRadioGroup',
          template: '<div class="el-radio-group-stub"><slot /></div>',
        },
        'el-radio': { name: 'ElRadio', template: '<label class="el-radio-stub"><slot /></label>' },
      },
    },
  })
  await flushPromises()
  await nextTick()
  return w
}

beforeEach(() => {
  vi.clearAllMocks()
  mockGet.mockResolvedValue({ data: { machine_code: 'MC-1234', verification_code: '5678' } })
  mockPost.mockResolvedValue({ code: 200, data: { new_password: 'New#Pass1' } })
  Object.defineProperty(window.navigator, 'clipboard', {
    value: { writeText: clipWrite },
    configurable: true,
  })
})

describe('ForgotPassword.vue', () => {
  it('渲染表单 + v-model 双向绑定', async () => {
    const w = await mountComp()
    expect(w.find('.forgot-password-page').exists()).toBe(true)
    expect((w.vm as any).currentStep).toBe(0)
    const inputs = w.findAll('input')
    expect(inputs.length).toBeGreaterThanOrEqual(2)
    await inputs[0].setValue('zhangsan')
    expect((w.vm as any).resetForm.username).toBe('zhangsan')
    await inputs[1].setValue('MC-TEST-1')
    expect((w.vm as any).resetForm.machine_code).toBe('MC-TEST-1')
    if (inputs.length > 2) {
      await inputs[2].setValue('1234')
      expect((w.vm as any).resetForm.verification_code).toBe('1234')
    }
  })

  it('canSubmit 计算属性全条件', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(vm.canSubmit).toBe(false)
    vm.resetForm.username = 'u'
    expect(vm.canSubmit).toBe(false)
    vm.resetForm.machine_code = 'mc'
    expect(vm.canSubmit).toBe(false)
    vm.resetForm.verification_code = '123'
    expect(vm.canSubmit).toBe(false)
    vm.resetForm.verification_code = '1234'
    expect(vm.canSubmit).toBe(true)
    vm.resetForm.username = ''
    expect(vm.canSubmit).toBe(false)
  })

  it('使用当前机器码：成功自动填充', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.useCurrentMachineCode()
    expect(mockGet).toHaveBeenCalledWith('/machine-code/get-machine-code')
    expect(vm.resetForm.machine_code).toBe('MC-1234')
    expect(vm.resetForm.verification_code).toBe('5678')
    expect(ElMessage.success).toHaveBeenCalledWith('已自动填入当前机器码和校验码')
    expect(vm.loadingMachineCode).toBe(false)
  })

  it('使用当前机器码：payload 无 machine_code → 报错', async () => {
    mockGet.mockResolvedValue({ data: {}, message: '查询失败' })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.useCurrentMachineCode()
    expect(ElMessage.error).toHaveBeenCalledWith('查询失败')
  })

  it('使用当前机器码：响应为空 → 默认报错', async () => {
    mockGet.mockResolvedValue(undefined)
    const w = await mountComp()
    const vm = w.vm as any
    await vm.useCurrentMachineCode()
    expect(ElMessage.error).toHaveBeenCalledWith('获取机器码失败，请重试')
  })

  it('使用当前机器码：无校验码 → 校验码为空', async () => {
    mockGet.mockResolvedValue({ data: { machine_code: 'MC-1' } })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.useCurrentMachineCode()
    expect(vm.resetForm.machine_code).toBe('MC-1')
    expect(vm.resetForm.verification_code).toBe('')
  })

  it('使用当前机器码：无 message → 默认报错', async () => {
    mockGet.mockResolvedValue({ data: {} })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.useCurrentMachineCode()
    expect(ElMessage.error).toHaveBeenCalledWith('获取机器码失败，请重试')
  })

  it('使用当前机器码：请求失败 → 日志 + detail 优先', async () => {
    mockGet.mockRejectedValue({ response: { data: { detail: '服务不可用' } } })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.useCurrentMachineCode()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('服务不可用')
  })

  it('使用当前机器码：请求失败 → message 分支', async () => {
    mockGet.mockRejectedValue({ response: { data: { message: '机器码服务异常' } } })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.useCurrentMachineCode()
    expect(ElMessage.error).toHaveBeenCalledWith('机器码服务异常')
  })

  it('使用当前机器码：请求失败且无任何信息 → 默认文案', async () => {
    mockGet.mockRejectedValue({})
    const w = await mountComp()
    const vm = w.vm as any
    await vm.useCurrentMachineCode()
    expect(ElMessage.error).toHaveBeenCalledWith('获取机器码失败，请检查系统服务是否正常')
  })

  it('重置密码：信息不完整 → 警告', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleResetPassword()
    expect(ElMessage.warning).toHaveBeenCalledWith('请填写完整信息')
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('重置密码：成功且携带新密码', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.resetForm.username = 'u'
    vm.resetForm.machine_code = 'mc'
    vm.resetForm.verification_code = '1234'
    await vm.handleResetPassword()
    expect(mockPost).toHaveBeenCalledWith(
      '/machine-code/reset-password-with-machine-code',
      undefined,
      {
        params: vm.resetForm,
      }
    )
    expect(vm.newPassword).toBe('New#Pass1')
    expect(vm.currentStep).toBe(1)
    expect(ElMessage.success).toHaveBeenCalledWith('密码重置成功')
  })

  it('重置密码：code 200 但无新密码 → 兼容旧版', async () => {
    mockPost.mockResolvedValue({ code: 200, message: '已重置' })
    const w = await mountComp()
    const vm = w.vm as any
    vm.resetForm.username = 'u'
    vm.resetForm.machine_code = 'mc'
    vm.resetForm.verification_code = '1234'
    await vm.handleResetPassword()
    expect(vm.currentStep).toBe(1)
    expect(vm.newPassword).toBe('(请查看系统临时文件)')
    expect(ElMessage.success).toHaveBeenCalledWith('已重置')
  })

  it('重置密码：code 200 无 message → 默认成功文案', async () => {
    mockPost.mockResolvedValue({ code: 200 })
    const w = await mountComp()
    const vm = w.vm as any
    vm.resetForm.username = 'u'
    vm.resetForm.machine_code = 'mc'
    vm.resetForm.verification_code = '1234'
    await vm.handleResetPassword()
    expect(ElMessage.success).toHaveBeenCalledWith('密码重置成功')
  })

  it('重置密码：业务失败无任何信息 → 默认文案', async () => {
    mockPost.mockResolvedValue({ code: 400 })
    const w = await mountComp()
    const vm = w.vm as any
    vm.resetForm.username = 'u'
    vm.resetForm.machine_code = 'mc'
    vm.resetForm.verification_code = '1234'
    await vm.handleResetPassword()
    expect(ElMessage.error).toHaveBeenCalledWith('重置密码失败，请检查填写信息')
  })

  it('重置密码：业务失败 → 展示 message', async () => {
    mockPost.mockResolvedValue({ code: 400, message: '机器码不匹配' })
    const w = await mountComp()
    const vm = w.vm as any
    vm.resetForm.username = 'u'
    vm.resetForm.machine_code = 'mc'
    vm.resetForm.verification_code = '1234'
    await vm.handleResetPassword()
    expect(ElMessage.error).toHaveBeenCalledWith('机器码不匹配')
  })

  it('重置密码：业务失败无 message → detail 兜底', async () => {
    mockPost.mockResolvedValue({ code: 400, detail: '校验码错误' })
    const w = await mountComp()
    const vm = w.vm as any
    vm.resetForm.username = 'u'
    vm.resetForm.machine_code = 'mc'
    vm.resetForm.verification_code = '1234'
    await vm.handleResetPassword()
    expect(ElMessage.error).toHaveBeenCalledWith('校验码错误')
  })

  it('重置密码：请求异常 → 日志 + 错误提示', async () => {
    mockPost.mockRejectedValue({ response: { data: { message: '网络错误' } } })
    const w = await mountComp()
    const vm = w.vm as any
    vm.resetForm.username = 'u'
    vm.resetForm.machine_code = 'mc'
    vm.resetForm.verification_code = '1234'
    await vm.handleResetPassword()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('网络错误')
  })

  it('重置密码：请求异常无信息 → 默认文案', async () => {
    mockPost.mockRejectedValue({})
    const w = await mountComp()
    const vm = w.vm as any
    vm.resetForm.username = 'u'
    vm.resetForm.machine_code = 'mc'
    vm.resetForm.verification_code = '1234'
    await vm.handleResetPassword()
    expect(ElMessage.error).toHaveBeenCalledWith('重置密码失败，请检查网络连接')
  })

  it('复制密码成功', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.newPassword = 'abc'
    await vm.copyPassword()
    expect(clipWrite).toHaveBeenCalledWith('abc')
    expect(ElMessage.success).toHaveBeenCalledWith('密码已复制到剪贴板')
  })

  it('复制密码失败', async () => {
    clipWrite.mockRejectedValueOnce(new Error('denied'))
    const w = await mountComp()
    const vm = w.vm as any
    vm.newPassword = 'abc'
    await vm.copyPassword()
    expect(ElMessage.error).toHaveBeenCalledWith('复制失败，请手动复制')
  })

  it('goBack / goToLogin 跳转登录页', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.goBack()
    expect(mockPushSafe).toHaveBeenCalledWith('/login')
    vm.goToLogin()
    expect(mockPushSafe).toHaveBeenCalledWith('/login')
  })

  it('管理员出厂恢复：切换模式后请求新端点并展示出厂密码', async () => {
    mockPost.mockResolvedValue({ code: 200, data: { factory_password: 'Admin@2026' } })
    const w = await mountComp()
    const vm = w.vm as any
    vm.accountMode = 'admin'
    vm.resetForm.username = 'admin'
    vm.resetForm.machine_code = 'mc'
    vm.resetForm.verification_code = '1234'
    await vm.handleResetPassword()
    expect(mockPost).toHaveBeenCalledWith(
      '/machine-code/recover-admin-factory-password',
      undefined,
      { params: vm.resetForm }
    )
    expect(vm.newPassword).toBe('Admin@2026')
    expect(vm.currentStep).toBe(1)
    expect(ElMessage.success).toHaveBeenCalledWith('出厂密码已恢复')
  })

  it('管理员出厂恢复：请求失败 → 不附加切换提示', async () => {
    mockPost.mockRejectedValue({ response: { data: { detail: '校验码不正确' } } })
    const w = await mountComp()
    const vm = w.vm as any
    vm.accountMode = 'admin'
    vm.resetForm.username = 'admin'
    vm.resetForm.machine_code = 'mc'
    vm.resetForm.verification_code = '1234'
    await vm.handleResetPassword()
    expect(ElMessage.error).toHaveBeenCalledWith('校验码不正确')
  })

  it('普通通道被管理员拒绝 → 错误提示附带切换出厂恢复的引导', async () => {
    mockPost.mockRejectedValue({
      response: { data: { detail: '管理员账号不支持普通自助重置' } },
    })
    const w = await mountComp()
    const vm = w.vm as any
    vm.resetForm.username = 'admin'
    vm.resetForm.machine_code = 'mc'
    vm.resetForm.verification_code = '1234'
    await vm.handleResetPassword()
    expect(ElMessage.error).toHaveBeenCalledWith(expect.stringContaining('恢复出厂密码'))
  })
})
