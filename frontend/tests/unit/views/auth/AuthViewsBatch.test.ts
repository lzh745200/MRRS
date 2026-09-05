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
// 注意：LoginEnhanced.vue 不在此批量渲染。它已由专属测试
// tests/unit/views/auth/LoginEnhanced.test.ts 覆盖到 100%（19/19 函数）。
// 此处的 ElDialog 桩为 `<div><slot/></div>`（不渲染 footer 插槽），bare mount 会让
// v8ToIstanbul 生成一份缺少 footer onClick 处理器的 17 函数 fnMap，其函数 id 与专属
// 测试的 19 函数 fnMap 错位冲突；istanbul 按 id 合并时在满量 299 分片规模下会把
// LoginEnhanced.vue 的 functions 损坏成 88.23%（<100 阈值），正是 Linux CI 上
// frontend-check 门禁变红的唯一根因。移除这段冗余渲染即根除冲突分片，且不减少任何真实覆盖。
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
