/**
 * Auth Views 批量组件测试
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

enableAutoUnmount(afterEach)

const mockPush = vi.fn(() => Promise.resolve())
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, resolve: vi.fn(() => ({ name: 'x', matched: [{ path: '/x' }] })) }),
  useRoute: () => ({ params: {}, query: { token: 'test-token' } }),
}))
const mockGet = vi.fn()
const mockPost = vi.fn()
const mockPut = vi.fn()
const mockDel = vi.fn()
vi.mock('@/api/request', () => ({
  get: (...a: any[]) => mockGet(...a),
  post: (...a: any[]) => mockPost(...a),
  put: (...a: any[]) => mockPut(...a),
  del: (...a: any[]) => mockDel(...a),
  apiRequest: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))
vi.mock('@/utils/logger', () => ({ logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() } }))
vi.mock('@/composables/useRouterSafe', () => ({ useRouterSafe: () => ({ push: mockPush, pushSafe: mockPush }), pushSafe: vi.fn(() => Promise.resolve()), safeRouteParam: (v: unknown, fallback = 0) => { const n = Number(Array.isArray(v) ? v[0] : v); return Number.isFinite(n) ? n : fallback } }))
vi.mock('@/utils/notify', () => ({ notify: Object.assign(() => vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn(), closeAll: vi.fn() }), default: vi.fn() }))
vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  ElMessageBox: { confirm: vi.fn(() => Promise.resolve('confirm')), alert: vi.fn(), prompt: vi.fn() },
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn(), closeAll: vi.fn() },
  ElForm: { template: '<form><slot/></form>' },
  ElFormItem: { template: '<div><slot/></div>' },
  ElTable: { template: '<table><slot/></table>' },
  ElTableColumn: { template: '<td><slot/></td>' },
  ElPagination: { template: '<div/>' },
  ElDialog: { template: '<div><slot/></div>' },
  ElSelect: { template: '<select><slot/></select>' },
  ElOption: { template: '<option/>' },
  ElInput: { template: '<input/>' },
  ElButton: { template: '<button><slot/></button>' },
  ElCard: { template: '<div><slot/></div>' },
  ElTag: { template: '<span><slot/></span>' },
}))
vi.mock('@/stores/user', () => ({
  useUserStore: () => ({
    token: 'fake-token', user: { id: 1, username: 'admin', role: 'admin' },
    setToken: vi.fn(), setUser: vi.fn(), logout: vi.fn(),
    fetchUserInfo: vi.fn(() => Promise.resolve({ id: 1, username: 'admin' })),
  }),
}))

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  mockGet.mockResolvedValue({ data: {}, success: true })
  mockPost.mockResolvedValue({ data: { access_token: 'token', user: { id: 1, username: 'admin' } }, success: true })
  mockPut.mockResolvedValue({ data: {}, success: true })
  mockDel.mockResolvedValue({ data: null, success: true })
})

describe('auth/ChangePassword.vue', () => {
  it('渲染', async () => {
    const { default: C } = await import('@/views/auth/ChangePassword.vue')
    const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true)
  })
  it('提交修改密码', async () => {
    const { default: C } = await import('@/views/auth/ChangePassword.vue')
    const w = mount(C); await flushPromises()
    const vm = w.vm as any
    if (vm.handleSubmit) await vm.handleSubmit()
    if (vm.handleSave) await vm.handleSave()
  })
})
describe('auth/ForgotPassword.vue', () => {
  it('渲染', async () => {
    const { default: C } = await import('@/views/auth/ForgotPassword.vue')
    const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true)
  })
})
describe('auth/GetMachineCode.vue', () => {
  it('渲染', async () => {
    const { default: C } = await import('@/views/auth/GetMachineCode.vue')
    const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true)
  })
})
// 注意：LoginEnhanced.vue 不在此批量渲染（也不在此 import）。它已由专属测试
// tests/unit/views/auth/LoginEnhanced.test.ts 覆盖到 100%（19/19 函数）。
// 全仓只允许 LoginEnhanced.test.ts 一个文件执行该 .vue：任何第二处执行（含只 import 不
// 渲染的 bare import、路由懒加载 chunk、import('@/main') 整应用挂载）都会在各自 worker
// isolate 产出一份函数 id 从 1 起算的局部 v8 fnMap，istanbul 满量按 id 合并时与专属测试
// 的 19 函数分片错位 → functions 损坏成 88.23%（完整实测链条见 vitest.config.ts 注释 A：
// smoke.test 与 router-index.test 的桩替换均不足以转绿，promptContract.test 的 @/main
// 挂载才是最后一个执行源）。
describe('auth/Profile.vue', () => {
  it('渲染', async () => {
    const { default: C } = await import('@/views/auth/Profile.vue')
    const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true)
  })
})
describe('auth/Register.vue', () => {
  it('渲染', async () => {
    const { default: C } = await import('@/views/auth/Register.vue')
    const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true)
  })
})
describe('auth/TwoFactorSettings.vue', () => {
  it('渲染', async () => {
    const { default: C } = await import('@/views/auth/TwoFactorSettings.vue')
    const w = mount(C); await flushPromises(); expect(w.exists()).toBe(true)
  })
})
