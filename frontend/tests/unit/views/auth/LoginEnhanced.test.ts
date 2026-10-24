/**
 * views/auth/LoginEnhanced.vue 覆盖率攻坚
 * 覆盖：登录成功/失败/2FA、权限包导入全分支、导航逻辑、背景轮播生命周期
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const {
  mockPush,
  mockPushSafe,
  mockLogin,
  mockVerify2FA,
  ElMessage,
  mockApiRequest,
  mockPost,
  mockGet,
  promptMock,
  logError,
} = vi.hoisted(() => ({
  mockPush: vi.fn(() => Promise.resolve()),
  mockPushSafe: vi.fn(() => Promise.resolve()),
  mockLogin: vi.fn(),
  mockVerify2FA: vi.fn(),
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockApiRequest: vi.fn(),
  mockPost: vi.fn(),
  mockGet: vi.fn(),
  // 默认实现内置，beforeEach 的 clearAllMocks 不会抹除（仅 clear 调用记录）
  promptMock: vi.fn(() => Promise.resolve({ value: 'pw' })),
  logError: vi.fn(),
}))
let redirectQuery: string | undefined = undefined

const authState = vi.hoisted(() => ({ error: '', mustChangePassword: false }))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush,
    currentRoute: { value: { query: { redirect: redirectQuery } } },
    resolve: vi.fn(() => ({ name: 'x', matched: [{ path: '/x' }] })),
  }),
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ push: mockPush, pushSafe: mockPushSafe }),
  pushSafe: mockPushSafe,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    login: mockLogin,
    verifyTwoFactorLogin: mockVerify2FA,
    error: authState.error,
    mustChangePassword: authState.mustChangePassword,
    logout: vi.fn(),
    getAuthData: () => ({ token: 't', user: { id: 1, username: 'admin', role: 'admin' } }),
  }),
}))

vi.mock('@/api/request', () => ({
  apiRequest: mockApiRequest,
  get: mockGet,
  post: mockPost,
  put: vi.fn(),
  del: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() },
}))

const authStorageMock = vi.hoisted(() => ({
  persistForAutoLogin: vi.fn(),
  clearPersisted: vi.fn(),
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: authStorageMock,
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: {
    confirm: vi.fn(() => Promise.resolve('confirm')),
    alert: vi.fn(),
    prompt: promptMock,
  },
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

import LoginEnhanced from '@/views/auth/LoginEnhanced.vue'

async function mountComp() {
  const w = mount(LoginEnhanced)
  await flushPromises()
  await nextTick()
  return w
}

beforeEach(() => {
  vi.clearAllMocks()
  redirectQuery = undefined
  authState.error = ''
  authState.mustChangePassword = false
  mockLogin.mockResolvedValue({ status: 'success' })
  mockVerify2FA.mockResolvedValue(true)
  mockApiRequest.mockResolvedValue({ success: true })
  mockPost.mockResolvedValue({ success: true })
  // 默认：未开启自助注册 + 锁定 15 分钟（模拟生产默认 SELF_REGISTER_MODE=off）
  mockGet.mockResolvedValue({
    data: {
      self_register_enabled: false,
      lockout_minutes: 15,
      max_failed_attempts: 5,
      two_factor_required: false,
    },
  })
})

describe('LoginEnhanced.vue', () => {
  it('渲染登录表单', async () => {
    const w = await mountComp()
    expect(w.exists()).toBe(true)
    expect(w.find('.login-page').exists()).toBe(true)
  })

  it('空用户名密码 → 提示错误', async () => {
    const w = await mountComp()
    await (w.vm as any).handleLogin()
    expect((w.vm as any).errorMsg).toBe('请输入用户名和密码')
    expect(mockLogin).not.toHaveBeenCalled()
  })

  it('登录成功 → 跳转 dashboard', async () => {
    const w = await mountComp()
    ;(w.vm as any).username = 'admin'
    ;(w.vm as any).password = 'pass123'
    await (w.vm as any).handleLogin()
    expect(mockLogin).toHaveBeenCalledWith('admin', 'pass123')
    expect(mockPushSafe).toHaveBeenCalledWith('/dashboard')
  })

  it('登录成功 + redirect 站内路径 → 跳转 redirect', async () => {
    redirectQuery = '/funds/list'
    const w = await mountComp()
    ;(w.vm as any).username = 'admin'
    ;(w.vm as any).password = 'pass123'
    await (w.vm as any).handleLogin()
    expect(mockPushSafe).toHaveBeenCalledWith('/funds/list')
  })

  it('登录成功 + redirect 外部路径 → 跳转 dashboard（防开放重定向）', async () => {
    redirectQuery = 'https://evil.com'
    const w = await mountComp()
    ;(w.vm as any).username = 'admin'
    ;(w.vm as any).password = 'pass123'
    await (w.vm as any).handleLogin()
    expect(mockPushSafe).toHaveBeenCalledWith('/dashboard')
  })

  it('登录成功 + mustChangePassword → 跳转改密页', async () => {
    authState.mustChangePassword = true
    const w = await mountComp()
    ;(w.vm as any).username = 'admin'
    ;(w.vm as any).password = 'pass123'
    await (w.vm as any).handleLogin()
    expect(mockPushSafe).toHaveBeenCalledWith('/change-password')
  })

  it('登录成功 + mustChangePassword + redirect → 带参数跳转改密页', async () => {
    authState.mustChangePassword = true
    redirectQuery = '/funds/list'
    const w = await mountComp()
    ;(w.vm as any).username = 'admin'
    ;(w.vm as any).password = 'pass123'
    await (w.vm as any).handleLogin()
    expect(mockPushSafe).toHaveBeenCalledWith(
      `/change-password?redirect=${encodeURIComponent('/funds/list')}`
    )
  })

  it('登录失败 → 展示服务端错误信息', async () => {
    mockLogin.mockResolvedValue({ status: 'error', message: '账号或密码错误' })
    const w = await mountComp()
    ;(w.vm as any).username = 'admin'
    ;(w.vm as any).password = 'wrong'
    await (w.vm as any).handleLogin()
    expect((w.vm as any).errorMsg).toBe('账号或密码错误')
  })

  it('登录失败（无 message）→ 回退 store.error', async () => {
    mockLogin.mockResolvedValue({ status: 'error' })
    authState.error = '系统错误'
    const w = await mountComp()
    ;(w.vm as any).username = 'admin'
    ;(w.vm as any).password = 'wrong'
    await (w.vm as any).handleLogin()
    expect((w.vm as any).errorMsg).toBe('系统错误')
  })

  it('登录异常（reject）→ 展示异常信息', async () => {
    mockLogin.mockRejectedValue(new Error('network down'))
    const w = await mountComp()
    ;(w.vm as any).username = 'admin'
    ;(w.vm as any).password = 'wrong'
    await (w.vm as any).handleLogin()
    expect((w.vm as any).errorMsg).toContain('登录系统异常')
  })

  it('登录要求 2FA → 切换到验证码模式', async () => {
    mockLogin.mockResolvedValue({ status: 'two_factor_required', tempToken: 'tt-1' })
    const w = await mountComp()
    ;(w.vm as any).username = 'admin'
    ;(w.vm as any).password = 'pass123'
    await (w.vm as any).handleLogin()
    expect((w.vm as any).twoFactorRequired).toBe(true)
    expect((w.vm as any).tempToken).toBe('tt-1')
  })

  it('2FA 验证码输入框真实 DOM input 事件 → v-model 更新 totpCode', async () => {
    // 覆盖 v-model 编译出的 onUpdate:modelValue 缓存 handler（fnMap id 13/14，行
    // 38/81）。既有 2FA 用例全部直接赋值 vm.totpCode，绕过了该 handler，导致其
    // 满量合并后恒 count-0 → functions 99.91% < 100 阈值（99.99% 之谜的另一半）。
    const w = await mountComp()
    ;(w.vm as any).twoFactorRequired = true
    await nextTick()
    const input = w.find('input.custom-input')
    expect(input.exists()).toBe(true)
    await input.setValue('654321')
    expect((w.vm as any).totpCode).toBe('654321')
  })

  it('2FA 验证码不足6位 → 提示', async () => {
    const w = await mountComp()
    ;(w.vm as any).twoFactorRequired = true
    ;(w.vm as any).totpCode = '123'
    await (w.vm as any).handleLogin()
    expect((w.vm as any).errorMsg).toBe('请输入 6 位 TOTP 验证码')
    expect(mockVerify2FA).not.toHaveBeenCalled()
  })

  it('2FA 验证成功 → 跳转首页', async () => {
    const w = await mountComp()
    ;(w.vm as any).twoFactorRequired = true
    ;(w.vm as any).tempToken = 'tt-1'
    ;(w.vm as any).totpCode = '123456'
    await (w.vm as any).handleLogin()
    expect(mockVerify2FA).toHaveBeenCalledWith('tt-1', '123456')
    expect(mockPushSafe).toHaveBeenCalledWith('/dashboard')
  })

  it('2FA 验证失败 → 展示 store.error', async () => {
    mockVerify2FA.mockResolvedValue(false)
    authState.error = '验证码错误'
    const w = await mountComp()
    ;(w.vm as any).twoFactorRequired = true
    ;(w.vm as any).totpCode = '123456'
    await (w.vm as any).handleLogin()
    expect((w.vm as any).errorMsg).toBe('验证码错误')
  })

  it('2FA 验证失败（无 error）→ 默认文案', async () => {
    mockVerify2FA.mockResolvedValue(false)
    const w = await mountComp()
    ;(w.vm as any).twoFactorRequired = true
    ;(w.vm as any).totpCode = '123456'
    await (w.vm as any).handleLogin()
    expect((w.vm as any).errorMsg).toBe('2FA 验证失败，请检查验证码后重试')
  })

  it('2FA 验证异常 → 展示异常信息', async () => {
    mockVerify2FA.mockRejectedValue(new Error('boom'))
    const w = await mountComp()
    ;(w.vm as any).twoFactorRequired = true
    ;(w.vm as any).totpCode = '123456'
    await (w.vm as any).handleLogin()
    expect((w.vm as any).errorMsg).toContain('2FA 验证异常')
  })

  it('2FA 验证异常（无 message）→ 默认文案', async () => {
    mockVerify2FA.mockRejectedValue({})
    const w = await mountComp()
    ;(w.vm as any).twoFactorRequired = true
    ;(w.vm as any).totpCode = '123456'
    await (w.vm as any).handleLogin()
    expect((w.vm as any).errorMsg).toBe('2FA 验证异常: 未知错误')
  })

  it('登录失败（无任何提示）→ 默认"登录失败"', async () => {
    mockLogin.mockResolvedValue({ status: 'error' })
    const w = await mountComp()
    ;(w.vm as any).username = 'admin'
    ;(w.vm as any).password = 'wrong'
    await (w.vm as any).handleLogin()
    expect((w.vm as any).errorMsg).toBe('登录失败')
  })

  it('登录异常（无 message）→ 默认文案', async () => {
    mockLogin.mockRejectedValue({})
    const w = await mountComp()
    ;(w.vm as any).username = 'admin'
    ;(w.vm as any).password = 'wrong'
    await (w.vm as any).handleLogin()
    expect((w.vm as any).errorMsg).toBe('登录系统异常: 未知错误')
  })

  it('静态单背景：只有一张图，且没有轮播定时器', async () => {
    // W27 UI 优化：原 12 张 JPG（3.51MB）全量预加载 + 5s 轮播已移除，
    // 改为单张静态图（background-image 内联样式）+ 深绿渐变叠加。
    const w = await mountComp()
    const vm = w.vm as any
    const bg = w.find('.login-bg')
    expect(bg.exists()).toBe(true)
    expect(bg.attributes('style') || '').toContain('/images/login-bg/bg1.jpg')
    // 轮播相关状态与 API 必须彻底消失，防止有人把轮播加回来
    expect(vm.currentBgIndex).toBeUndefined()
    expect(vm.backgroundImages).toBeUndefined()
    expect(vm.startCarousel).toBeUndefined()
    expect(vm.imagesPreloaded).toBeUndefined()
    // 只有一层叠加，不再有 .bg-slide / .background-carousel
    expect(w.find('.bg-slide').exists()).toBe(false)
    expect(w.find('.background-carousel').exists()).toBe(false)
  })

  it('resetTwoFactor 清空状态', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.twoFactorRequired = true
    vm.tempToken = 'tt'
    vm.totpCode = '123456'
    vm.errorMsg = 'err'
    vm.resetTwoFactor()
    expect(vm.twoFactorRequired).toBe(false)
    expect(vm.tempToken).toBe('')
    expect(vm.totpCode).toBe('')
    expect(vm.errorMsg).toBe('')
  })

  it('显示/隐藏密码切换', async () => {
    const w = mount(LoginEnhanced)
    await flushPromises()
    const vm = w.vm as any
    expect(vm.showPassword).toBe(false)
    await w.find('.toggle-password').trigger('click')
    expect(vm.showPassword).toBe(true)
    await w.find('.toggle-password').trigger('click')
    expect(vm.showPassword).toBe(false)
  })

  it('可访问性：label 通过 for/id 关联输入框，密码切换是原生 button', async () => {
    const w = await mountComp()
    // 常驻输入框：账号 / 密码
    expect(w.find('input#login-username').exists()).toBe(true)
    expect(w.find('input#login-password').exists()).toBe(true)
    expect(w.find('label[for="login-username"]').exists()).toBe(true)
    expect(w.find('label[for="login-password"]').exists()).toBe(true)

    // 密码切换：原生 button（可聚焦、可键盘触发、不提交表单）+ 动态 aria
    const toggle = w.find('.toggle-password')
    expect(toggle.element.tagName).toBe('BUTTON')
    expect(toggle.attributes('type')).toBe('button')
    expect(toggle.attributes('aria-label')).toBe('显示密码')
    expect(toggle.attributes('aria-pressed')).toBe('false')
    await toggle.trigger('click')
    expect(toggle.attributes('aria-label')).toBe('隐藏密码')
    expect(toggle.attributes('aria-pressed')).toBe('true')

    // 2FA 验证码输入框
    ;(w.vm as any).twoFactorRequired = true
    await nextTick()
    expect(w.find('input#login-totp-code').exists()).toBe(true)
    expect(w.find('label[for="login-totp-code"]').exists()).toBe(true)

    // 机器码校验输入框
    ;(w.vm as any).twoFactorRequired = false
    ;(w.vm as any).showMachineCodeInput = true
    await nextTick()
    expect(w.find('input#login-machine-code').exists()).toBe(true)
    expect(w.find('label[for="login-machine-code"]').exists()).toBe(true)
    w.unmount()
  })

  it('输入框 v-model 双向绑定：账号 / 密码 / 机器码输入都写回表单状态', async () => {
    // 覆盖率门禁回归：v-model 为原生 input 生成 onInput 内联处理器，
    // 若测试只用 vm 赋值、不触发真实输入事件，三个处理器会落在未覆盖行
    // （LoginEnhanced.vue 66/81/109）→ functions 86.95%。此处逐一点击输入。
    const w = await mountComp()
    const vm = w.vm as any

    await w.find('input#login-username').setValue('admin')
    expect(vm.username).toBe('admin')

    await w.find('input#login-password').setValue('Secret#2026')
    expect(vm.password).toBe('Secret#2026')

    vm.showMachineCodeInput = true
    await nextTick()
    await w.find('input#login-machine-code').setValue('1234')
    expect(vm.verificationCode).toBe('1234')
    w.unmount()
  })

  it('el-dialog 关闭（update:modelValue）→ 关闭导入对话框', async () => {
    const w = mount(LoginEnhanced, {
      global: {
        stubs: {
          'el-dialog': {
            name: 'ElDialog',
            template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
            emits: ['update:modelValue'],
          },
          'el-button': {
            name: 'ElButton',
            template: '<button @click="$emit(\'click\')"><slot /></button>',
            emits: ['click'],
          },
        },
      },
    })
    await flushPromises()
    const vm = w.vm as any
    vm.permissionImportVisible = true
    await nextTick()
    const dialog = w.findComponent({ name: 'ElDialog' })
    dialog.vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.permissionImportVisible).toBe(false)
  })

  it('导入对话框：点击取消按钮关闭', async () => {
    const w = mount(LoginEnhanced, {
      global: {
        stubs: {
          'el-dialog': {
            name: 'ElDialog',
            template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
            emits: ['update:modelValue'],
          },
          'el-button': {
            name: 'ElButton',
            template: '<button @click="$emit(\'click\')"><slot /></button>',
            emits: ['click'],
          },
        },
      },
    })
    await flushPromises()
    const vm = w.vm as any
    vm.permissionImportVisible = true
    await nextTick()
    const cancelBtn = w.findAll('button').find((b) => b.text().includes('取消'))
    expect(cancelBtn).toBeTruthy()
    await cancelBtn!.trigger('click')
    await nextTick()
    expect(vm.permissionImportVisible).toBe(false)
  })

  it('跳转辅助函数', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.goToForgotPassword()
    expect(mockPushSafe).toHaveBeenCalledWith('/forgot-password')
    vm.goToRegister()
    expect(mockPushSafe).toHaveBeenCalledWith('/register')
    vm.goToMachineCode()
    expect(mockPushSafe).toHaveBeenCalledWith('/get-machine-code')
  })

  it('openPermissionImport 打开对话框', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.openPermissionImport()
    expect(vm.permissionImportVisible).toBe(true)
  })

  it('权限包文件：非zip → 报错并清空', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.onPermissionFileChange({ raw: { name: 'pkg.txt', type: 'text/plain' } })
    expect(ElMessage.error).toHaveBeenCalledWith('仅支持 .zip 格式的权限配置包')
    expect(vm.permissionFile).toBeNull()
  })

  it('权限包文件：无 raw → 直接返回', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.onPermissionFileChange({ raw: undefined })
    expect(vm.permissionFile).toBeNull()
  })

  it('权限包文件：zip → 记录文件', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const file = { name: 'pkg.zip', type: 'application/zip' }
    vm.onPermissionFileChange({ raw: file })
    expect(vm.permissionFile?.name).toBe('pkg.zip')
    expect(vm.permissionFile?.type).toBe('application/zip')
  })

  it('权限包移除 → 清空文件', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    vm.onPermissionFileRemove()
    expect(vm.permissionFile).toBeNull()
  })

  it('权限包导入：无文件 → 直接返回', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handlePermissionImport()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('权限包导入：预览成功（saved_file_name 契约字段）+ 确认成功', async () => {
    mockPost
      .mockResolvedValueOnce({
        success: true,
        saved_file_name: 'pkg_saved.zip',
        message: '预览通过',
      })
      .mockResolvedValueOnce({ success: true, message: '应用完成' })
    const w = await mountComp()
    const vm = w.vm as any
    const file = new File(['zip-bytes'], 'pkg.zip', { type: 'application/zip' })
    vm.permissionFile = file
    await vm.handlePermissionImport()
    // 导入调用：post('/permission-packages/import', formData) — FormData 原样作为第 2 参，无手动 multipart Content-Type
    expect(mockPost).toHaveBeenCalledWith('/permission-packages/import', expect.any(FormData))
    const importCall = mockPost.mock.calls[0]
    expect(importCall).toHaveLength(2) // (url, formData) — 没有额外的 headers 参数
    expect((importCall[1] as FormData).get('file')).toBe(file)
    // 确认调用：post('/permission-packages/confirm/{file_name}', { overwrite_existing: true })
    expect(mockPost).toHaveBeenCalledWith('/permission-packages/confirm/pkg_saved.zip', {
      overwrite_existing: true,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('权限包已导入,请重新登录查看权限')
    expect(vm.permissionImportVisible).toBe(false)
    expect(vm.permissionFile).toBeNull()
    expect(vm.permissionImporting).toBe(false)
  })

  it('权限包导入：后端未返回文件名时回退本地文件名执行确认（T08 回归）', async () => {
    mockPost
      .mockResolvedValueOnce({ success: true, message: '预览通过' }) // 无 saved_file_name/file_name
      .mockResolvedValueOnce({ success: true, message: '应用完成' })
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'local-fallback.zip' }
    await vm.handlePermissionImport()
    expect(mockPost).toHaveBeenNthCalledWith(2, '/permission-packages/confirm/local-fallback.zip', {
      overwrite_existing: true,
    })
    expect(ElMessage.success).toHaveBeenCalled()
  })

  it('权限包导入：预览成功（code=200，file_name 别名）但确认失败', async () => {
    mockPost
      .mockResolvedValueOnce({ code: 200, file_name: 'pkg.zip' })
      .mockResolvedValueOnce({ success: false, message: '覆盖失败' })
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    await vm.handlePermissionImport()
    expect(ElMessage.error).toHaveBeenCalledWith('覆盖失败')
  })

  it('权限包导入：预览失败 → 展示预览错误', async () => {
    mockPost.mockResolvedValueOnce({ success: false, message: '文件损坏' })
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    await vm.handlePermissionImport()
    expect(ElMessage.error).toHaveBeenCalledWith('文件损坏')
  })

  it('权限包导入：预览失败仅带 detail → 展示 detail', async () => {
    mockPost.mockResolvedValueOnce({ success: false, detail: '压缩包结构不合法' })
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    await vm.handlePermissionImport()
    expect(ElMessage.error).toHaveBeenCalledWith('压缩包结构不合法')
  })

  it('权限包导入：无后端文件名 → 回退本地文件名继续确认（T08 修复语义）', async () => {
    mockPost
      .mockResolvedValueOnce({ success: true, message: '预览通过' })
      .mockResolvedValueOnce({ success: true, message: '应用完成' })
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    await vm.handlePermissionImport()
    // 回退本地文件名执行确认，不再停留在预览
    expect(mockPost).toHaveBeenNthCalledWith(2, '/permission-packages/confirm/pkg.zip', {
      overwrite_existing: true,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('权限包已导入,请重新登录查看权限')
  })

  it('权限包导入：接口异常 → 记录日志并提示', async () => {
    mockPost.mockRejectedValue({ message: 'timeout' })
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    await vm.handlePermissionImport()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('timeout')
  })

  it('权限包导入：接口异常带 detail → 优先 detail', async () => {
    mockPost.mockRejectedValue({ response: { data: { detail: '服务端拒绝' } } })
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    await vm.handlePermissionImport()
    expect(ElMessage.error).toHaveBeenCalledWith('服务端拒绝')
  })

  it('权限包导入：预览响应为 undefined → 默认失败分支', async () => {
    mockPost.mockResolvedValueOnce(undefined)
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    await vm.handlePermissionImport()
    expect(ElMessage.error).toHaveBeenCalledWith('权限包验证失败')
  })

  it('权限包导入：确认接口 code=200 → 导入成功', async () => {
    mockPost
      .mockResolvedValueOnce({ success: true, file_name: 'pkg.zip' })
      .mockResolvedValueOnce({ code: 200, message: 'ok' })
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    await vm.handlePermissionImport()
    expect(ElMessage.success).toHaveBeenCalledWith('权限包已导入,请重新登录查看权限')
  })

  it('权限包导入：确认响应为空 → 默认失败文案', async () => {
    mockPost
      .mockResolvedValueOnce({ success: true, file_name: 'pkg.zip' })
      .mockResolvedValueOnce(undefined)
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    await vm.handlePermissionImport()
    expect(ElMessage.error).toHaveBeenCalledWith('权限包应用失败')
  })

  it('权限包导入：确认失败仅带 detail → 展示 detail', async () => {
    mockPost
      .mockResolvedValueOnce({ success: true, file_name: 'pkg.zip' })
      .mockResolvedValueOnce({ success: false, detail: '版本冲突' })
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    await vm.handlePermissionImport()
    expect(ElMessage.error).toHaveBeenCalledWith('版本冲突')
  })

  it('权限包导入：异常无 message → 默认文案', async () => {
    mockPost.mockRejectedValue({})
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    await vm.handlePermissionImport()
    expect(ElMessage.error).toHaveBeenCalledWith('导入权限包失败,请检查文件')
  })

  // ---- Phase E：加密包密码重试（stmts@253-268 / funcs@257 / branch@252,@271）----

  it('加密包：提示输密 → 重传带 password → 确认导入成功（含 inputValidator 两侧）', async () => {
    mockPost
      .mockResolvedValueOnce({ success: false, message: '该权限包已加密' })
      .mockResolvedValueOnce({ success: true, saved_file_name: 'dec.zip' })
      .mockResolvedValueOnce({ success: true, message: '应用完成' })
    const w = await mountComp()
    const vm = w.vm as any
    const file = new File(['zip'], 'pkg.zip', { type: 'application/zip' })
    vm.permissionFile = file
    await vm.handlePermissionImport()

    expect(promptMock).toHaveBeenCalledWith(
      '该权限包已加密，请输入导出时设置的密码：',
      '解密密码',
      { inputType: 'password', inputValidator: expect.any(Function) }
    )
    // funcs@257：inputValidator 非空 → true，空串 → 错误文案
    const validator = promptMock.mock.calls[0][2].inputValidator as (v: string) => true | string
    expect(validator('abc')).toBe(true)
    expect(validator('')).toBe('密码不能为空')

    // 重传：同一接口第二次调用，FormData 同时携带 file 与 password
    expect(mockPost).toHaveBeenNthCalledWith(2, '/permission-packages/import', expect.any(FormData))
    const fd2 = mockPost.mock.calls[1][1] as FormData
    expect(fd2.get('file')).toBe(file)
    expect(fd2.get('password')).toBe('pw')
    expect(mockPost).toHaveBeenNthCalledWith(3, '/permission-packages/confirm/dec.zip', {
      overwrite_existing: true,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('权限包已导入,请重新登录查看权限')
    expect(vm.permissionImporting).toBe(false)
  })

  it('加密包：prompt 取消 → 「已取消导入」并提前返回（不重传、finally 复位）', async () => {
    promptMock.mockRejectedValueOnce('cancel')
    // branch@252 另一侧：success 缺省但 code !== 200，且仅带 detail
    mockPost.mockResolvedValueOnce({ code: 500, detail: '加密包需要密码' })
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    await vm.handlePermissionImport()
    expect(ElMessage.error).toHaveBeenCalledWith('已取消导入')
    expect(mockPost).toHaveBeenCalledTimes(1)
    expect(vm.permissionImporting).toBe(false)
  })

  it('加密包：prompt 返回空 value → password 以空串上传（branch@261 || 假侧），重传仍失败则提示', async () => {
    promptMock.mockResolvedValueOnce({ value: undefined })
    mockPost
      .mockResolvedValueOnce({ success: false, message: '已加密' })
      .mockResolvedValueOnce({ success: false, message: '密码错误' })
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    await vm.handlePermissionImport()
    expect((mockPost.mock.calls[1][1] as FormData).get('password')).toBe('')
    // 任务#28 缺陷1修复：else 分支改读 _body（加密包重传后的响应），
    // 因此展示的是重传返回的真实错误「密码错误」，而不再误显首次的「已加密」。
    expect(ElMessage.error).toHaveBeenCalledWith('密码错误')
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('加密包：重传响应为 null → _body 走 `r2 || {}` 右侧兜底（branch@263）', async () => {
    mockPost
      .mockResolvedValueOnce({ success: false, message: '已加密' })
      .mockResolvedValueOnce(null) // r2 为 falsy → _body = {}
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    await vm.handlePermissionImport()
    // _body = {} → success2 为假，即使 savedFileName 有值也不发确认请求
    expect(mockPost).toHaveBeenCalledTimes(2)
    expect(ElMessage.success).not.toHaveBeenCalled()
    // 任务#28 缺陷1修复：else 分支读重传后的 _body；此处 _body = {}（r2 为 null 的兜底），
    // message/detail 均缺，故落到第三操作数「权限包验证失败」（不再误显首次的「已加密」）。
    expect(ElMessage.error).toHaveBeenCalledWith('权限包验证失败')
    expect(vm.permissionImporting).toBe(false)
  })

  it('branch@271 末尾兜底：无 saved_file_name/file_name 且 permissionFile 无 name → 空串走验证失败分支', async () => {
    mockPost.mockResolvedValueOnce({ success: true }) // 无任何文件名字段
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = {} // name 缺省 → ?. 后为 undefined → || '' 兜底
    await vm.handlePermissionImport()
    // savedFileName 为空 → success2 && savedFileName 假侧，不发确认请求
    expect(mockPost).toHaveBeenCalledTimes(1)
    expect(ElMessage.error).toHaveBeenCalledWith('权限包验证失败')
  })

  it('机器码验证输入框渲染（showMachineCodeInput）', async () => {
    const w = mount(LoginEnhanced, {
      global: { renderStubDefaultSlot: true },
    })
    await flushPromises()
    const vm = w.vm as any
    expect(w.find('.login-page').exists()).toBe(true)
    vm.showMachineCodeInput = true
    await nextTick()
    expect(w.text()).toContain('机器码验证')
    expect(w.text()).toContain('本机尚未授权登录')
  })

  describe('登录页公开配置（P0：修注册死链）', () => {
    it('未开启自助注册 → 不渲染注册入口，改为提示联系管理员', async () => {
      mockGet.mockResolvedValue({ data: { self_register_enabled: false } })
      const w = await mountComp()
      const vm = w.vm as any
      expect(vm.canSelfRegister).toBe(false)
      // 展开首次使用引导后：第三步没有注册按钮，只有说明
      vm.firstUseOpen = true
      await nextTick()
      expect(w.find('.register-link').exists()).toBe(false)
      expect(w.text()).toContain('本机未开启自助注册，请联系管理员开通账号')
      expect(mockGet).toHaveBeenCalledWith('/auth/public-config')
    })

    it('开启自助注册 → 渲染注册入口', async () => {
      mockGet.mockResolvedValue({
        data: { self_register_enabled: true, lockout_minutes: 10, max_failed_attempts: 3 },
      })
      const w = await mountComp()
      const vm = w.vm as any
      expect(vm.canSelfRegister).toBe(true)
      expect(vm.publicConfig.lockout_minutes).toBe(10)
      expect(vm.publicConfig.max_failed_attempts).toBe(3)
      vm.firstUseOpen = true
      await nextTick()
      const btn = w.findAll('.step-btn').find((b) => b.text().includes('注册账户'))
      expect(btn).toBeTruthy()
      await btn!.trigger('click')
      expect(mockPushSafe).toHaveBeenCalledWith('/register')
    })

    it('配置请求失败 → fail-closed：隐藏注册入口且不阻塞登录', async () => {
      mockGet.mockRejectedValue(new Error('backend down'))
      const w = await mountComp()
      const vm = w.vm as any
      expect(vm.canSelfRegister).toBe(false)
      vm.firstUseOpen = true
      await nextTick()
      expect(w.findAll('.step-btn').some((b) => b.text().includes('注册账户'))).toBe(false)
      // 登录功能本身不受影响
      ;(vm as any).username = 'admin'
      ;(vm as any).password = 'pw'
      await (vm as any).handleLogin()
      expect(mockPushSafe).toHaveBeenCalledWith('/dashboard')
    })

    it('响应为裸对象（无 envelope）也能解析', async () => {
      mockGet.mockResolvedValue({ self_register_enabled: true })
      const w = await mountComp()
      expect((w.vm as any).canSelfRegister).toBe(true)
    })

    it('字段缺失/类型异常 → 回落到最保守默认值', async () => {
      mockGet.mockResolvedValue({
        data: {
          self_register_enabled: 'yes',
          lockout_minutes: 'abc',
          max_failed_attempts: null,
        },
      })
      const w = await mountComp()
      const cfg = (w.vm as any).publicConfig
      expect(cfg.self_register_enabled).toBe(false)
      expect(cfg.lockout_minutes).toBe(0)
      expect(cfg.max_failed_attempts).toBe(0)
    })
  })

  describe('失败分类与倒计时（P0）', () => {
    it('423 锁定 → 琥珀提示 + 按 lockout_minutes 倒计时 + 按钮禁用', async () => {
      vi.useFakeTimers()
      mockGet.mockResolvedValue({ data: { lockout_minutes: 2 } })
      mockLogin.mockResolvedValue({ status: 'error', message: '账户已锁定，请2分钟后再试' })
      const w = mount(LoginEnhanced)
      await vi.advanceTimersByTimeAsync(1)
      const vm = w.vm as any
      vm.username = 'admin'
      vm.password = 'pw'
      await vm.handleLogin()
      expect(vm.errorMsg).toContain('账户已锁定')
      expect(vm.lockRemaining).toBe(120)
      expect(vm.busy).toBe(true)
      await nextTick()
      expect(w.find('.alert--warn').exists()).toBe(true)
      expect(w.find('.login-btn').attributes('disabled')).toBeDefined()
      expect(w.find('.login-btn').text()).toContain('请稍候')
      // 倒计时递减并在归零后恢复可点
      await vi.advanceTimersByTimeAsync(1000)
      expect(vm.lockRemaining).toBe(119)
      await vi.advanceTimersByTimeAsync(119000)
      expect(vm.lockRemaining).toBe(0)
      expect(vm.busy).toBe(false)
      await nextTick()
      expect(w.find('.login-btn').text()).toContain('立即登录')
      w.unmount()
      vi.useRealTimers()
    })

    it('423 但未拿到 lockout_minutes → 只提示，不倒计时（不假定解锁时间）', async () => {
      mockGet.mockResolvedValue({ data: { lockout_minutes: 0 } })
      mockLogin.mockResolvedValue({ status: 'error', message: '账户已锁定，请15分钟后再试' })
      const w = await mountComp()
      const vm = w.vm as any
      vm.username = 'admin'
      vm.password = 'pw'
      await vm.handleLogin()
      expect(vm.lockRemaining).toBe(0)
      expect(vm.errorMsg).toContain('账户已锁定')
    })

    it('429 限流 → 60s 倒计时', async () => {
      vi.useFakeTimers()
      mockLogin.mockResolvedValue({ status: 'error', message: '登录尝试过于频繁，请稍后再试' })
      const w = mount(LoginEnhanced)
      await vi.advanceTimersByTimeAsync(1)
      const vm = w.vm as any
      vm.username = 'admin'
      vm.password = 'pw'
      await vm.handleLogin()
      expect(vm.lockRemaining).toBe(60)
      w.unmount()
      vi.useRealTimers()
    })

    it('403 未激活 → 危险色提示，无直达动作', async () => {
      mockLogin.mockResolvedValue({
        status: 'error',
        message: '您的账户尚未激活，请联系管理员进行审核',
      })
      const w = await mountComp()
      const vm = w.vm as any
      vm.username = 'admin'
      vm.password = 'pw'
      await vm.handleLogin()
      await nextTick()
      expect(vm.errorMsg).toContain('尚未激活')
      expect(w.find('.alert--danger').exists()).toBe(true)
      expect(w.find('.alert-action').exists()).toBe(false)
    })

    it('403 未授权本机 → 信息色提示 + 「去获取机器码」直达', async () => {
      mockLogin.mockResolvedValue({
        status: 'error',
        message: '您的账户未授权在此机器上登录，请联系管理员',
      })
      const w = await mountComp()
      const vm = w.vm as any
      vm.username = 'admin'
      vm.password = 'pw'
      await vm.handleLogin()
      await nextTick()
      expect(w.find('.alert--info').exists()).toBe(true)
      const action = w.find('.alert-action')
      expect(action.exists()).toBe(true)
      await action.trigger('click')
      expect(mockPushSafe).toHaveBeenCalledWith('/get-machine-code')
    })

    it('普通 401 → 危险色提示，无倒计时', async () => {
      mockLogin.mockResolvedValue({ status: 'error', message: '用户名或密码错误' })
      const w = await mountComp()
      const vm = w.vm as any
      vm.username = 'admin'
      vm.password = 'pw'
      await vm.handleLogin()
      await nextTick()
      expect(w.find('.alert--danger').exists()).toBe(true)
      expect(vm.lockRemaining).toBe(0)
    })

    it('classifyLoginFailure：状态码优先于文案', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      // 文案像锁定，但状态码是 401 → 仍以状态码为准判为普通认证失败
      expect(vm.classifyLoginFailure({ httpStatus: 401, message: '账户已锁定' })).toBe('locked')
      expect(vm.classifyLoginFailure({ httpStatus: 423, message: '' })).toBe('locked')
      expect(vm.classifyLoginFailure({ httpStatus: 429, message: '' })).toBe('rate-limited')
      expect(vm.classifyLoginFailure({ httpStatus: 401, message: '密码错误' })).toBe('auth')
      expect(vm.classifyLoginFailure({ message: '您的账户尚未激活' })).toBe('inactive')
      expect(vm.classifyLoginFailure({ message: '您的账户未授权在此机器上登录' })).toBe(
        'machine-unauthorized'
      )
      expect(vm.classifyLoginFailure({})).toBe('system')
      expect(vm.classifyLoginFailure(undefined)).toBe('system')
    })
  })

  describe('安全与交互细节（P1）', () => {
    it('登录失败 → 清空密码并聚焦密码框', async () => {
      mockLogin.mockResolvedValue({ status: 'error', message: '用户名或密码错误' })
      const w = await mountComp()
      const vm = w.vm as any
      const pwdInput = w.find('#login-password').element as HTMLInputElement
      const focusSpy = vi.spyOn(pwdInput, 'focus')
      vm.username = 'admin'
      vm.password = 'wrong'
      await vm.handleLogin()
      expect(vm.password).toBe('')
      expect(focusSpy).toHaveBeenCalled()
    })

    it('2FA 失败 → 清空验证码并聚焦', async () => {
      mockVerify2FA.mockResolvedValue(false)
      const w = await mountComp()
      const vm = w.vm as any
      vm.twoFactorRequired = true
      await nextTick()
      vm.totpCode = '123456'
      const totpInput = w.find('#login-totp-code').element as HTMLInputElement
      const focusSpy = vi.spyOn(totpInput, 'focus')
      await vm.handleLogin()
      expect(vm.totpCode).toBe('')
      expect(focusSpy).toHaveBeenCalled()
    })

    it('CapsLock 开启 → 显示提示；关闭 → 隐藏', async () => {
      const w = await mountComp()
      const input = w.find('#login-password')
      // 用真实 KeyboardEvent + 注入 getModifierState（VTU 的 trigger 选项无法伪造该方法）
      const fire = async (on: boolean) => {
        const evt = new KeyboardEvent('keyup', { key: 'A' })
        Object.defineProperty(evt, 'getModifierState', { value: () => on })
        input.element.dispatchEvent(evt)
        await nextTick()
      }
      await fire(true)
      expect(w.text()).toContain('大写锁定已开启')
      expect(w.find('.field-hint--warn').exists()).toBe(true)
      await fire(false)
      expect(w.find('.field-hint--warn').exists()).toBe(false)
    })

    it('环境不支持 getModifierState → 静默不提示', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      vm.onPasswordKeyup({})
      await nextTick()
      expect(vm.capsLockOn).toBe(false)
      expect(w.find('.field-hint--warn').exists()).toBe(false)
    })

    it('2FA 输满 6 位 → 自动提交一次（不重复）', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      vm.twoFactorRequired = true
      mockVerify2FA.mockResolvedValue(true)
      vm.totpCode = '123456'
      vm.onTotpInput()
      await flushPromises()
      expect(mockVerify2FA).toHaveBeenCalledTimes(1)
      expect(mockPushSafe).toHaveBeenCalledWith('/dashboard')
    })

    it('2FA 输入含非数字 → 过滤为纯数字；不足 6 位不提交', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      vm.twoFactorRequired = true
      vm.totpCode = '12a3'
      vm.onTotpInput()
      expect(vm.totpCode).toBe('123')
      expect(mockVerify2FA).not.toHaveBeenCalled()
    })

    it('2FA 正在提交时再次输满 → 忽略（不并发请求）', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      vm.twoFactorRequired = true
      vm.loading = true
      vm.totpCode = '123456'
      vm.onTotpInput()
      expect(mockVerify2FA).not.toHaveBeenCalled()
    })

    it('首次使用引导：默认折叠，点击可展开/收起', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      expect(vm.firstUseOpen).toBe(false)
      const toggle = w.find('.first-use-toggle')
      expect(toggle.attributes('aria-expanded')).toBe('false')
      await toggle.trigger('click')
      expect(vm.firstUseOpen).toBe(true)
      await nextTick()
      expect(w.find('.first-use-toggle').attributes('aria-expanded')).toBe('true')
      expect(w.findAll('.first-use-steps li').length).toBe(3)
      await toggle.trigger('click')
      expect(vm.firstUseOpen).toBe(false)
    })

    it('首次使用引导：机器码与权限包两步按钮可达', async () => {
      const w = await mountComp()
      ;(w.vm as any).firstUseOpen = true
      await nextTick()
      const btns = w.findAll('.step-btn')
      const machineBtn = btns.find((b) => b.text().includes('打开机器码页'))!
      await machineBtn.trigger('click')
      expect(mockPushSafe).toHaveBeenCalledWith('/get-machine-code')
      const importBtn = btns.find((b) => b.text().includes('导入权限包'))!
      await importBtn.trigger('click')
      expect((w.vm as any).permissionImportVisible).toBe(true)
    })

    it('提示条清空后不渲染', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      vm.setAlert({ type: 'danger', text: 'x' })
      await nextTick()
      expect(w.find('.alert').exists()).toBe(true)
      vm.setAlert(null)
      await nextTick()
      expect(w.find('.alert').exists()).toBe(false)
      expect(vm.errorMsg).toBe('')
    })

    it('用户名已填、密码为空 → 聚焦密码框', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      const pwdInput = w.find('#login-password').element as HTMLInputElement
      const focusSpy = vi.spyOn(pwdInput, 'focus')
      vm.username = 'admin'
      vm.password = ''
      await vm.handleLogin()
      expect(vm.errorMsg).toBe('请输入用户名和密码')
      expect(focusSpy).toHaveBeenCalled()
      expect(mockLogin).not.toHaveBeenCalled()
    })

    it('公开配置返回 undefined → 走空对象兜底，注册入口隐藏', async () => {
      mockGet.mockResolvedValue(undefined)
      const w = await mountComp()
      const vm = w.vm as any
      expect(vm.canSelfRegister).toBe(false)
      expect(vm.publicConfig.lockout_minutes).toBe(0)
    })

    it('组件已卸载后再触发登录 → 空引用安全（可选链兜底）', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      w.unmount()
      vm.username = 'admin'
      vm.password = 'pw'
      mockLogin.mockResolvedValue({ status: 'error', message: '用户名或密码错误' })
      // 不应抛错：所有 `input?.focus?.()` 在引用为 null 时安全跳过
      await expect(vm.handleLogin()).resolves.toBeUndefined()
      expect(vm.errorMsg).toBe('用户名或密码错误')
    })

    it('failureText：六种类型在无文案时都给出可读兜底', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      expect(vm.failureText('locked', '')).toContain('锁定')
      expect(vm.failureText('rate-limited', '')).toContain('频繁')
      expect(vm.failureText('inactive', '')).toContain('激活')
      expect(vm.failureText('machine-unauthorized', '')).toContain('机器码')
      expect(vm.failureText('auth', '')).toContain('密码')
      expect(vm.failureText('system', '')).toBe('登录失败')
      // 有原文时优先原文
      expect(vm.failureText('locked', '后端原文')).toBe('后端原文')
    })

    it('冷却期内再次提交 → 直接早退，不重复请求', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      vm.startLockCountdown(30)
      vm.username = 'admin'
      vm.password = 'pw'
      await vm.handleLogin()
      expect(mockLogin).not.toHaveBeenCalled()
    })

    it('2FA 挑战缺少 temp_token → 空串兜底（不写 undefined）', async () => {
      mockLogin.mockResolvedValue({ status: 'two_factor_required' })
      const w = await mountComp()
      const vm = w.vm as any
      vm.username = 'admin'
      vm.password = 'pw'
      await vm.handleLogin()
      expect(vm.twoFactorRequired).toBe(true)
      expect(vm.tempToken).toBe('')
    })

    it('lockLabel：不足 1 分钟显示秒，≥1 分钟显示分秒', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      vm.startLockCountdown(30)
      expect(vm.lockLabel).toBe('30 秒')
      vm.startLockCountdown(125)
      expect(vm.lockLabel).toBe('2 分 05 秒')
      vm.lockRemaining = 0
      expect(vm.lockLabel).toBe('')
    })

    it('卸载时清理倒计时定时器', async () => {
      vi.useFakeTimers()
      const clearSpy = vi.spyOn(globalThis, 'clearInterval')
      const w = mount(LoginEnhanced)
      await vi.advanceTimersByTimeAsync(1)
      ;(w.vm as any).startLockCountdown(30)
      w.unmount()
      expect(clearSpy).toHaveBeenCalled()
      vi.useRealTimers()
    })

    it('startLockCountdown 传入非法/非正秒数 → 不倒计时', async () => {
      const w = await mountComp()
      const vm = w.vm as any
      vm.startLockCountdown(Number.NaN)
      expect(vm.lockRemaining).toBe(0)
      vm.startLockCountdown(-5)
      expect(vm.lockRemaining).toBe(0)
    })
  })

  describe('记住登录（自动登录持久化）', () => {
    beforeEach(() => {
      authStorageMock.persistForAutoLogin.mockClear()
      authStorageMock.clearPersisted.mockClear()
    })

    it('勾选记住登录 → 持久化令牌', async () => {
      mockLogin.mockResolvedValue({ status: 'success' })
      const w = await mountComp()
      const vm = w.vm as any
      vm.username = 'admin'
      vm.password = 'pass123'
      vm.rememberMe = true
      await vm.handleLogin()
      expect(authStorageMock.persistForAutoLogin).toHaveBeenCalledWith(
        expect.objectContaining({ token: 't' })
      )
      expect(authStorageMock.clearPersisted).not.toHaveBeenCalled()
    })

    it('未勾选记住登录 → 清除持久数据', async () => {
      mockLogin.mockResolvedValue({ status: 'success' })
      const w = await mountComp()
      const vm = w.vm as any
      vm.username = 'admin'
      vm.password = 'pass123'
      vm.rememberMe = false
      await vm.handleLogin()
      expect(authStorageMock.clearPersisted).toHaveBeenCalled()
      expect(authStorageMock.persistForAutoLogin).not.toHaveBeenCalled()
    })
  })
})

describe('LoginEnhanced.vue 权限包导入兜底分支', () => {
  it('文件无名称 → 提示仅支持 .zip（空名兜底）', async () => {
    const w = await mountComp()
    const st = (w.vm as any).$.setupState
    st.onPermissionFileChange({ raw: { name: '' } })
    expect(ElMessage.error).toHaveBeenCalledWith('仅支持 .zip 格式的权限配置包')
  })
})
