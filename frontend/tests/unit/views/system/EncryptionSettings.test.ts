/**
 * views/system/EncryptionSettings.vue 覆盖率攻坚
 * 覆盖：状态加载、启用/修改/禁用加密全分支、校验器
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick, defineComponent, h } from 'vue'

enableAutoUnmount(afterEach)

const { ElMessage, ElMessageBox, mockGet, mockPost } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  ElMessageBox: { confirm: vi.fn(), alert: vi.fn() },
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: mockGet,
  post: mockPost,
  put: vi.fn(),
  del: vi.fn(),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox,
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

import EncryptionSettings from '@/views/system/EncryptionSettings.vue'

const formState = vi.hoisted(() => ({
  validateFn: (cb: (valid: boolean) => void) => cb(true),
}))

const ElFormStub = defineComponent({
  name: 'ElForm',
  props: ['model', 'rules'],
  emits: ['update:modelValue'],
  setup(_props, { expose, slots }) {
    const validate = (cb: (valid: boolean) => void) => formState.validateFn(cb)
    expose({ validate })
    return () => h('form', { class: 'el-form-stub' }, [slots.default?.()])
  },
})

async function mountComp() {
  const w = mount(EncryptionSettings, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot /><slot name="header" /></div>',
        },
        'el-descriptions': { name: 'ElDescriptions', template: '<dl><slot /></dl>' },
        'el-descriptions-item': {
          name: 'ElDescriptionsItem',
          template: '<div class="el-desc-item-stub"><slot /></div>',
        },
        'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
        'el-alert': {
          name: 'ElAlert',
          template: '<div class="el-alert-stub"><slot /><slot name="title" /></div>',
        },
        'el-form': ElFormStub,
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
          template: '<button class="el-button-stub"><slot /></button>',
        },
      },
    },
  })
  await flushPromises()
  await nextTick()
  return w
}

/** 后端 `/encryption/status` 的真实返回（仅 is_enabled / has_salt） */
const statusDisabled = { is_enabled: false, has_salt: false }
const statusEnabled = { is_enabled: true, has_salt: true }

beforeEach(() => {
  vi.clearAllMocks()
  formState.validateFn = (cb) => cb(true)
  mockGet.mockResolvedValue({ success: true, data: statusDisabled })
  mockPost.mockResolvedValue({ success: true, message: '操作成功' })
  ElMessageBox.confirm.mockResolvedValue('confirm')
})

describe('EncryptionSettings.vue', () => {
  it('渲染并加载未启用状态', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(mockGet).toHaveBeenCalledWith('/encryption/status')
    expect(vm.encryptionStatus.enabled).toBe(false)
    expect(vm.encryptionStatus.has_salt).toBe(false)
    expect(w.text()).toContain('启用数据库加密')
    expect(w.text()).toContain('未生成')
  })

  it('渲染已启用状态', async () => {
    mockGet.mockResolvedValue({ success: true, data: statusEnabled })
    const w = await mountComp()
    const vm = w.vm as any
    // 回归：后端字段是 is_enabled；旧实现读 `enabled` → 恒 undefined → 恒“未启用”
    expect(vm.encryptionStatus.enabled).toBe(true)
    expect(vm.encryptionStatus.has_salt).toBe(true)
    expect(w.text()).toContain('已启用')
    expect(w.text()).toContain('已生成')
    expect(w.text()).toContain('修改加密密码')
    expect(w.text()).toContain('禁用数据库加密')
  })

  it('状态字段缺失时按未启用处理（不渲染真值）', async () => {
    mockGet.mockResolvedValue({ success: true, data: {} })
    const w = await mountComp()
    expect((w.vm as any).encryptionStatus.enabled).toBe(false)
  })

  it('加载状态失败 → 错误提示', async () => {
    mockGet.mockRejectedValue(new Error('密钥状态读取异常'))
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('密钥状态读取异常')
  })

  it('加载状态失败无 message → 默认文案', async () => {
    mockGet.mockRejectedValue({})
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('加载状态失败')
  })

  it('校验器：密码长度 / 两次密码一致', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const cb = vi.fn()
    vm.validatePassword(null, '123', cb)
    expect(cb).toHaveBeenCalledWith(new Error('密码长度至少为8位'))
    cb.mockClear()
    vm.validatePassword(null, '12345678', cb)
    expect(cb).toHaveBeenCalledWith()
    vm.validateConfirmPassword(null, 'x', cb)
    expect(cb).toHaveBeenCalledWith(new Error('两次输入的密码不一致'))
    cb.mockClear()
    vm.initForm.password = '12345678'
    vm.validateConfirmPassword(null, '12345678', cb)
    expect(cb).toHaveBeenCalledWith()
    vm.validateNewConfirmPassword(null, 'y', cb)
    expect(cb).toHaveBeenCalledWith(new Error('两次输入的密码不一致'))
    cb.mockClear()
    vm.changeForm.newPassword = '12345678'
    vm.validateNewConfirmPassword(null, '12345678', cb)
    expect(cb).toHaveBeenCalledWith()
  })

  it('handleInitialize：无表单引用 → 返回', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.initFormRef = null
    await vm.handleInitialize()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('handleInitialize：校验失败 → 返回', async () => {
    formState.validateFn = (cb) => cb(false)
    const w = await mountComp()
    await (w.vm as any).handleInitialize()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('handleInitialize：确认 → 启用成功', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.initForm.password = '12345678'
    vm.initForm.confirmPassword = '12345678'
    await vm.handleInitialize()
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(mockPost).toHaveBeenCalledWith('/encryption/initialize', {
      password: '12345678',
      confirm_password: '12345678',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('操作成功')
    expect(vm.initForm.password).toBe('')
  })

  it('handleInitialize：确认取消 → 无提示', async () => {
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const w = await mountComp()
    await (w.vm as any).handleInitialize()
    expect(mockPost).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('handleInitialize：失败 → 错误提示', async () => {
    mockPost.mockRejectedValue(new Error('init failed'))
    const w = await mountComp()
    await (w.vm as any).handleInitialize()
    expect(ElMessage.error).toHaveBeenCalledWith('init failed')
  })

  it('handleInitialize：失败（非 cancel）→ 默认文案', async () => {
    mockPost.mockRejectedValue({})
    const w = await mountComp()
    await (w.vm as any).handleInitialize()
    expect(ElMessage.error).toHaveBeenCalledWith('启用加密失败')
  })

  it('handleChangePassword：无表单引用 → 返回', async () => {
    mockGet.mockResolvedValue({ success: true, data: statusEnabled })
    const w = await mountComp()
    const vm = w.vm as any
    vm.changeFormRef = null
    await vm.handleChangePassword()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('handleChangePassword：校验失败 → 返回', async () => {
    mockGet.mockResolvedValue({ success: true, data: statusEnabled })
    formState.validateFn = (cb) => cb(false)
    const w = await mountComp()
    await (w.vm as any).handleChangePassword()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('handleChangePassword：修改成功', async () => {
    mockGet.mockResolvedValue({ success: true, data: statusEnabled })
    const w = await mountComp()
    const vm = w.vm as any
    vm.changeForm.oldPassword = 'old1'
    vm.changeForm.newPassword = 'new1'
    vm.changeForm.confirmPassword = 'new1'
    await vm.handleChangePassword()
    expect(mockPost).toHaveBeenCalledWith('/encryption/change-password', {
      old_password: 'old1',
      new_password: 'new1',
      confirm_password: 'new1',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('操作成功')
    expect(vm.changeForm.newPassword).toBe('')
  })

  it('handleChangePassword：失败 → 错误提示', async () => {
    mockGet.mockResolvedValue({ success: true, data: statusEnabled })
    mockPost.mockRejectedValue(new Error('change failed'))
    const w = await mountComp()
    await (w.vm as any).handleChangePassword()
    expect(ElMessage.error).toHaveBeenCalledWith('change failed')
  })

  it('handleChangePassword：失败无 message → 默认文案', async () => {
    mockGet.mockResolvedValue({ success: true, data: statusEnabled })
    mockPost.mockRejectedValue({})
    const w = await mountComp()
    await (w.vm as any).handleChangePassword()
    expect(ElMessage.error).toHaveBeenCalledWith('修改密码失败')
  })

  it('handleDisable：无密码 → 警告', async () => {
    const w = await mountComp()
    await (w.vm as any).handleDisable()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入密码')
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('handleDisable：确认 → 禁用成功', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.disableForm.password = 'pw123456'
    await vm.handleDisable()
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(mockPost).toHaveBeenCalledWith('/encryption/disable', { password: 'pw123456' })
    expect(ElMessage.success).toHaveBeenCalledWith('操作成功')
    expect(vm.disableForm.password).toBe('')
  })

  it('handleDisable：确认取消 → 无提示', async () => {
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const w = await mountComp()
    const vm = w.vm as any
    vm.disableForm.password = 'pw123456'
    await vm.handleDisable()
    expect(mockPost).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('handleDisable：失败 → 错误提示', async () => {
    mockPost.mockRejectedValue(new Error('disable failed'))
    const w = await mountComp()
    const vm = w.vm as any
    vm.disableForm.password = 'pw123456'
    await vm.handleDisable()
    expect(ElMessage.error).toHaveBeenCalledWith('disable failed')
  })

  it('handleDisable：失败（非 cancel）→ 默认文案', async () => {
    mockPost.mockRejectedValue({})
    const w = await mountComp()
    const vm = w.vm as any
    vm.disableForm.password = 'pw123456'
    await vm.handleDisable()
    expect(ElMessage.error).toHaveBeenCalledWith('禁用加密失败')
  })

  it('启用表单 v-model（密码/确认密码）', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const inputs = w.findAll('input')
    await inputs[0].setValue('pw123456')
    expect(vm.initForm.password).toBe('pw123456')
    await inputs[1].setValue('pw123456')
    expect(vm.initForm.confirmPassword).toBe('pw123456')
  })

  it('修改密码表单 v-model（旧/新/确认）', async () => {
    mockGet.mockResolvedValue({ success: true, data: statusEnabled })
    const w = await mountComp()
    const vm = w.vm as any
    const inputs = w.findAll('input')
    // inputs[0]/[1] 为旧密码/新密码（disable 表单在后）
    await inputs[0].setValue('old1')
    expect(vm.changeForm.oldPassword).toBe('old1')
    await inputs[1].setValue('new1')
    expect(vm.changeForm.newPassword).toBe('new1')
    await inputs[2].setValue('new1')
    expect(vm.changeForm.confirmPassword).toBe('new1')
    // disable 表单密码
    await inputs[3].setValue('pw123456')
    expect(vm.disableForm.password).toBe('pw123456')
  })
})
