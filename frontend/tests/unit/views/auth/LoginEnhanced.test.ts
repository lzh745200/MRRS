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
  logError,
} = vi.hoisted(() => ({
  mockPush: vi.fn(() => Promise.resolve()),
  mockPushSafe: vi.fn(() => Promise.resolve()),
  mockLogin: vi.fn(),
  mockVerify2FA: vi.fn(),
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockApiRequest: vi.fn(),
  mockPost: vi.fn(),
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
  get: vi.fn(),
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
  ElMessageBox: { confirm: vi.fn(() => Promise.resolve('confirm')), alert: vi.fn() },
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

  it('2FA 验证码不足6位 → 提示', async () => {
    const w = await mountComp()
    ;(w.vm as any).twoFactorRequired = true
    ;(w.vm as any).totpCode = '123'
    await (w.vm as any).handleLogin()
    expect((w.vm as any).errorMsg).toBe('请输入6位TOTP验证码')
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
    expect((w.vm as any).errorMsg).toBe('2FA验证失败')
  })

  it('2FA 验证异常 → 展示异常信息', async () => {
    mockVerify2FA.mockRejectedValue(new Error('boom'))
    const w = await mountComp()
    ;(w.vm as any).twoFactorRequired = true
    ;(w.vm as any).totpCode = '123456'
    await (w.vm as any).handleLogin()
    expect((w.vm as any).errorMsg).toContain('2FA验证异常')
  })

  it('2FA 验证异常（无 message）→ 默认文案', async () => {
    mockVerify2FA.mockRejectedValue({})
    const w = await mountComp()
    ;(w.vm as any).twoFactorRequired = true
    ;(w.vm as any).totpCode = '123456'
    await (w.vm as any).handleLogin()
    expect((w.vm as any).errorMsg).toBe('2FA验证异常: 未知错误')
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

  it('startCarousel 重复调用安全（幂等）', async () => {
    vi.useFakeTimers()
    const origImage = (globalThis as any).Image
    class FakeImage {
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      src = ''
      constructor() {
        setTimeout(() => {
          if (this.onload) this.onload()
        }, 0)
      }
    }
    ;(globalThis as any).Image = FakeImage
    const w = mount(LoginEnhanced)
    await vi.advanceTimersByTimeAsync(10)
    const vm = w.vm as any
    vm.startCarousel()
    await vi.advanceTimersByTimeAsync(5000)
    expect(vm.currentBgIndex).toBe(1)
    w.unmount()
    ;(globalThis as any).Image = origImage
    vi.useRealTimers()
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

  it('权限包导入：预览成功 + 确认成功', async () => {
    mockPost
      .mockResolvedValueOnce({ success: true, file_name: 'pkg.zip', message: '预览通过' })
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
    expect(mockPost).toHaveBeenCalledWith('/permission-packages/confirm/pkg.zip', {
      overwrite_existing: true,
    })
    expect(ElMessage.success).toHaveBeenCalledWith('权限包已导入,请重新登录查看权限')
    expect(vm.permissionImportVisible).toBe(false)
    expect(vm.permissionFile).toBeNull()
    expect(vm.permissionImporting).toBe(false)
  })

  it('权限包导入：预览成功（code=200）但确认失败', async () => {
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

  it('权限包导入：无 file_name → 展示默认成功信息分支', async () => {
    mockPost.mockResolvedValueOnce({ success: true, message: '预览通过' })
    const w = await mountComp()
    const vm = w.vm as any
    vm.permissionFile = { name: 'pkg.zip' }
    await vm.handlePermissionImport()
    expect(ElMessage.error).toHaveBeenCalledWith('预览通过')
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
    expect(ElMessage.error).toHaveBeenCalledWith('权限包导入完成')
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
    expect(w.text()).toContain('首次登录需要验证机器码')
  })

  it('背景图预加载成功 + 轮播切换 + 卸载清理 interval', async () => {
    vi.useFakeTimers()
    const origImage = (globalThis as any).Image
    class FakeImage {
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      src = ''
      constructor() {
        setTimeout(() => {
          if (this.onload) this.onload()
        }, 0)
      }
    }
    ;(globalThis as any).Image = FakeImage

    const w = mount(LoginEnhanced)
    await vi.advanceTimersByTimeAsync(10)
    const vm = w.vm as any
    expect(vm.imagesPreloaded).toBe(true)
    expect(vm.currentBgIndex).toBe(0)
    // 轮播推进 2 次（5000ms 间隔）
    await vi.advanceTimersByTimeAsync(10000)
    expect(vm.currentBgIndex).toBe(2)
    w.unmount()
    await vi.advanceTimersByTimeAsync(20000)
    expect(vm.currentBgIndex).toBe(2)
    ;(globalThis as any).Image = origImage
    vi.useRealTimers()
  })

  it('背景图加载失败（onerror）不阻塞', async () => {
    vi.useFakeTimers()
    const origImage = (globalThis as any).Image
    class FakeImageError {
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      src = ''
      constructor() {
        setTimeout(() => {
          if (this.onerror) this.onerror()
        }, 0)
      }
    }
    ;(globalThis as any).Image = FakeImageError
    const w = mount(LoginEnhanced)
    await vi.advanceTimersByTimeAsync(10)
    const vm = w.vm as any
    expect(vm.imagesPreloaded).toBe(true)
    w.unmount()
    ;(globalThis as any).Image = origImage
    vi.useRealTimers()
  })

  it('轮播：currentBg 计算与卸载清理', async () => {
    const w = mount(LoginEnhanced)
    await flushPromises()
    const vm = w.vm as any
    expect(vm.currentBg).toBe('/images/login-bg/bg1.jpg')
    vm.currentBgIndex = 3
    await nextTick()
    expect(vm.currentBg).toBe('/images/login-bg/bg4.jpg')
    w.unmount()
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
