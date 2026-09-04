/**
 * views/auth/Register.vue 覆盖率攻坚
 * 覆盖：密码强度校验器、确认密码校验器、注册成功/失败/校验失败、通行码帮助
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick, defineComponent, h } from 'vue'

enableAutoUnmount(afterEach)

const { ElMessage, mockPushSafe, mockApiRequest, logError } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockPushSafe: vi.fn(() => Promise.resolve()),
  mockApiRequest: vi.fn(),
  logError: vi.fn(),
}))

const formState = vi.hoisted(() => ({
  validateFn: () => Promise.resolve(true),
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
  apiRequest: mockApiRequest,
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() },
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: vi.fn(() => Promise.resolve('confirm')), alert: vi.fn() },
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

import Register from '@/views/auth/Register.vue'

const ElFormStub = defineComponent({
  name: 'ElForm',
  props: ['model', 'rules'],
  emits: ['update:modelValue'],
  setup(_props, { expose, slots }) {
    const validate = () => formState.validateFn()
    expose({ validate })
    return () => h('form', { class: 'el-form-stub' }, [slots.default?.()])
  },
})

async function mountComp() {
  const w = mount(Register, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot /><slot name="header" /></div>',
        },
        'el-form': ElFormStub,
        'el-form-item': { name: 'ElFormItem', template: '<div class="el-form-item-stub"><slot /></div>' },
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
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue'],
        },
        'el-steps': { name: 'ElSteps', template: '<div><slot /></div>' },
        'el-step': { name: 'ElStep', template: '<div><slot /><slot name="description" /></div>' },
        'el-icon': { name: 'ElIcon', template: '<span><slot /></span>' },
      },
    },
  })
  await flushPromises()
  await nextTick()
  return w
}

beforeEach(() => {
  vi.clearAllMocks()
  formState.validateFn = () => Promise.resolve(true)
  mockApiRequest.mockResolvedValue({})
})

describe('Register.vue', () => {
  it('渲染表单', async () => {
    const w = await mountComp()
    expect(w.find('.register-container').exists()).toBe(true)
    expect(w.text()).toContain('用户注册')
  })

  it('validatePassword 校验器：各分支', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const cb = vi.fn()
    vm.validatePassword(null, '', cb)
    expect(cb).toHaveBeenCalledWith(new Error('请输入密码'))
    cb.mockClear()
    // 长度不足
    vm.validatePassword(null, 'Ab1!x', cb)
    expect(cb).toHaveBeenCalledWith(new Error('密码需要：至少12个字符'))
    cb.mockClear()
    // 缺大写
    vm.validatePassword(null, 'ab1!abcdefghijk', cb)
    expect(cb).toHaveBeenCalledWith(new Error('密码需要：包含大写字母'))
    cb.mockClear()
    // 缺小写
    vm.validatePassword(null, 'AB1!ABCDEFGHIJK', cb)
    expect(cb).toHaveBeenCalledWith(new Error('密码需要：包含小写字母'))
    cb.mockClear()
    // 缺数字
    vm.validatePassword(null, 'Ab!abcdefghijk', cb)
    expect(cb).toHaveBeenCalledWith(new Error('密码需要：包含数字'))
    cb.mockClear()
    // 缺特殊字符
    vm.validatePassword(null, 'Ab1abcdefghijk', cb)
    expect(cb).toHaveBeenCalledWith(new Error('密码需要：包含特殊字符'))
    cb.mockClear()
    // 全部满足
    vm.validatePassword(null, 'Ab1!abcdefghijk', cb)
    expect(cb).toHaveBeenCalledWith()
  })

  it('validatePassword：密码包含用户名 → 拒绝（与后端 PasswordPolicy 末条一致）', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    // 复现截图场景：强度全过，但密码 Ptrw7221137@ 含用户名 PTRW
    vm.registerForm.username = 'PTRW'
    const cb = vi.fn()
    vm.validatePassword(null, 'Ptrw7221137@', cb)
    expect(cb).toHaveBeenCalledWith(new Error('密码不能包含用户名'))
    cb.mockClear()
    // 反向：不含用户名 → 通过
    vm.registerForm.username = 'zhangsan'
    vm.validatePassword(null, 'Ab1!abcdefghijk', cb)
    expect(cb).toHaveBeenCalledWith()
  })

  it('validateConfirmPassword 校验器：各分支', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const cb = vi.fn()
    vm.validateConfirmPassword(null, '', cb)
    expect(cb).toHaveBeenCalledWith(new Error('请再次输入密码'))
    cb.mockClear()
    vm.registerForm.password = 'Ab1!abcdefghijk'
    vm.validateConfirmPassword(null, 'Different1!', cb)
    expect(cb).toHaveBeenCalledWith(new Error('两次输入的密码不一致'))
    cb.mockClear()
    vm.validateConfirmPassword(null, 'Ab1!abcdefghijk', cb)
    expect(cb).toHaveBeenCalledWith()
  })

  it('handleRegister：表单引用为空 → 直接返回', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.registerFormRef = null
    await vm.handleRegister()
    expect(mockApiRequest).not.toHaveBeenCalled()
  })

  it('handleRegister：校验失败 → 展示默认错误', async () => {
    formState.validateFn = () => Promise.reject(new Error('校验未通过'))
    const w = await mountComp()
    await (w.vm as any).handleRegister()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('校验未通过')
    expect(mockApiRequest).not.toHaveBeenCalled()
  })

  it('handleRegister：校验失败无 message → 默认文案', async () => {
    formState.validateFn = () => Promise.reject({})
    const w = await mountComp()
    await (w.vm as any).handleRegister()
    expect(ElMessage.error).toHaveBeenCalledWith('注册失败，请稍后重试')
  })

  it('handleRegister：注册成功 → 提示并跳转登录', async () => {
    vi.useFakeTimers()
    const w = await mountComp()
    const vm = w.vm as any
    vm.registerForm.username = 'zhangsan'
    vm.registerForm.password = 'Ab1!abcdefghijk'
    vm.registerForm.confirmPassword = 'Ab1!abcdefghijk'
    vm.registerForm.passCode = 'PASS123'
    vm.registerForm.fullName = '张三'
    vm.registerForm.email = 'a@b.c'
    await vm.handleRegister()
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        url: '/auth/register',
        method: 'post',
        data: expect.objectContaining({
          username: 'zhangsan',
          pass_code: 'PASS123',
          full_name: '张三',
          email: 'a@b.c',
        }),
      })
    )
    expect(ElMessage.success).toHaveBeenCalledWith('注册成功！正在跳转到登录页面...')
    expect(vm.loading).toBe(false)
    await vi.advanceTimersByTimeAsync(1600)
    expect(mockPushSafe).toHaveBeenCalledWith('/login')
    vi.useRealTimers()
  })

  it('handleRegister：无姓名/邮箱 → full_name 用用户名', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.registerForm.username = 'zhangsan'
    await vm.handleRegister()
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        data: expect.objectContaining({ full_name: 'zhangsan', email: undefined }),
      })
    )
  })

  it('handleRegister：接口失败带 detail → 展示 detail', async () => {
    mockApiRequest.mockRejectedValue({ response: { data: { detail: '通行码无效' } } })
    const w = await mountComp()
    await (w.vm as any).handleRegister()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('通行码无效')
  })

  it('handleRegister：400 信封只有 message（BizValidationError）→ 展示后端文案，不暴露 axios 原文', async () => {
    // 复现截图缺陷：AppError handler 返回 {code,message,success}（无 detail），
    // error.message 是 axios 默认英文原文，旧代码会把它直接抛给用户。
    mockApiRequest.mockRejectedValue({
      response: { status: 400, data: { code: 400, message: '密码不能包含用户名', success: false } },
      message: 'Request failed with status code 400',
    })
    const w = await mountComp()
    await (w.vm as any).handleRegister()
    expect(ElMessage.error).toHaveBeenCalledWith('密码不能包含用户名')
    expect(ElMessage.error).not.toHaveBeenCalledWith('Request failed with status code 400')
  })

  it('handleRegister：拦截器已算好 userMessage → 优先展示 userMessage', async () => {
    mockApiRequest.mockRejectedValue({
      userMessage: '通行码无效或已被使用',
      response: { status: 400, data: { code: 400, message: '原始信封文案', success: false } },
      message: 'Request failed with status code 400',
    })
    const w = await mountComp()
    await (w.vm as any).handleRegister()
    expect(ElMessage.error).toHaveBeenCalledWith('通行码无效或已被使用')
  })

  it('handleRegister：接口失败 → 默认文案', async () => {
    mockApiRequest.mockRejectedValue({})
    const w = await mountComp()
    await (w.vm as any).handleRegister()
    expect(ElMessage.error).toHaveBeenCalledWith('注册失败，请稍后重试')
  })

  it('showPassCodeHelp 打开帮助对话框', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.showPassCodeHelp()
    expect(vm.helpDialogVisible).toBe(true)
    await nextTick()
    expect(w.find('.el-dialog-stub').exists()).toBe(true)
  })

  it('帮助对话框关闭（update:modelValue）', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.helpDialogVisible = true
    await nextTick()
    const dialog = w.findComponent({ name: 'ElDialog' })
    dialog.vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.helpDialogVisible).toBe(false)
  })

  it('v-model 双向绑定（表单输入）', async () => {
    const w = await mountComp()
    const inputs = w.findAll('input')
    const vm = w.vm as any
    await inputs[0].setValue('zhangsan')
    expect(vm.registerForm.username).toBe('zhangsan')
    await inputs[1].setValue('Ab1!abcdefghijk')
    expect(vm.registerForm.password).toBe('Ab1!abcdefghijk')
    await inputs[2].setValue('Ab1!abcdefghijk')
    expect(vm.registerForm.confirmPassword).toBe('Ab1!abcdefghijk')
    await inputs[3].setValue('PASS-CODE-1')
    expect(vm.registerForm.passCode).toBe('PASS-CODE-1')
    await inputs[4].setValue('张三')
    expect(vm.registerForm.fullName).toBe('张三')
    await inputs[5].setValue('a@b.c')
    expect(vm.registerForm.email).toBe('a@b.c')
  })

  it('帮助对话框：点击"我知道了"关闭', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.helpDialogVisible = true
    await nextTick()
    const btn = w
      .findAll('button')
      .find((b) => b.text().includes('我知道了'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    await nextTick()
    expect(vm.helpDialogVisible).toBe(false)
  })
})
