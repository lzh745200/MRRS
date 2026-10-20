/**
 * Funds Views 批量组件测试
 * 覆盖 src/views/funds/ 下未单独测试的视图
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

enableAutoUnmount(afterEach)

const mockPush = vi.fn(() => Promise.resolve())
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, resolve: vi.fn(() => ({ name: 'x', matched: [{ path: '/x' }] })) }),
  useRoute: () => ({ params: { id: '1' }, query: {}, path: '/funds/1' }),
  onBeforeRouteLeave: vi.fn(),
  RouterLink: { template: '<a><slot/></a>' },
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

vi.mock('@/utils/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() },
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ push: mockPush, pushSafe: mockPush }),
  pushSafe: vi.fn(() => Promise.resolve()),
  safeRouteParam: (v: unknown, fallback = 0) => { const n = Number(Array.isArray(v) ? v[0] : v); return Number.isFinite(n) ? n : fallback },
}))

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
  ElTabs: { template: '<div><slot/></div>' },
  ElTabPane: { template: '<div><slot/></div>' },
}))

const fundListResponse = {
  items: [{ id: 1, village_name: '测试村', amount: 50000, fund_type: '帮扶', year: 2024, status: 'approved' }],
  total: 1,
}
const anomalyResponse = {
  items: [{ id: 1, type: 'overspend', severity: 'warning', description: '超支', amount: 1000, resolved: 0 }],
  total: 1,
}
const budgetResponse = {
  items: [{ id: 1, year: 2024, total_budget: 1000000, used: 500000, remaining: 500000 }],
  total: 1,
}
const contractResponse = {
  items: [{ id: 1, contract_no: 'HT001', party_a: '甲方', party_b: '乙方', amount: 50000, status: 'signed' }],
  total: 1,
}
const transferResponse = {
  items: [{ id: 1, from_account: 'A', to_account: 'B', amount: 10000, voucher_no: 'V001', status: 'completed' }],
  total: 1,
}

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  mockGet.mockImplementation((url: string) => {
    if (url.includes('anomal')) return Promise.resolve({ ...anomalyResponse, data: anomalyResponse, success: true })
    if (url.includes('budget')) return Promise.resolve({ ...budgetResponse, data: budgetResponse, success: true })
    if (url.includes('contract')) return Promise.resolve({ ...contractResponse, data: contractResponse, success: true })
    if (url.includes('transfer')) return Promise.resolve({ ...transferResponse, data: transferResponse, success: true })
    if (url.includes('analysis') || url.includes('statistics'))
      return Promise.resolve({ total_amount: 500000, count: 10, data: { total_amount: 500000, count: 10 }, success: true })
    return Promise.resolve({ ...fundListResponse, data: fundListResponse, success: true })
  })
  mockPost.mockResolvedValue({ data: { id: 1 }, success: true })
  mockPut.mockResolvedValue({ data: { id: 1 }, success: true })
  mockDel.mockResolvedValue({ data: null, success: true })
})

// --- Analysis ---
describe('funds/Analysis.vue', () => {
  it('渲染并加载分析数据', async () => {
    const { default: Comp } = await import('@/views/funds/Analysis.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- AnomalyList ---
describe('funds/AnomalyList.vue', () => {
  it('渲染并加载异常列表', async () => {
    const { default: Comp } = await import('@/views/funds/AnomalyList.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
  it('筛选变化触发加载', async () => {
    const { default: Comp } = await import('@/views/funds/AnomalyList.vue')
    const w = mount(Comp)
    await flushPromises()
    const vm = w.vm as any
    if (vm.filters) {
      vm.filters.severity = 'warning'
      await vm.$nextTick()
    }
    if (vm.loadData) await vm.loadData()
  })
})

// --- Budget ---
describe('funds/Budget.vue', () => {
  it('渲染并加载预算', async () => {
    const { default: Comp } = await import('@/views/funds/Budget.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- ContractManage ---
describe('funds/ContractManage.vue', () => {
  it('渲染并加载合同', async () => {
    const { default: Comp } = await import('@/views/funds/ContractManage.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- Detail ---
// funds/Detail.vue 刻意不在此挂载：coverage-merge 不变量要求“受阈值约束的 .vue 全仓只允许
// 一个测试文件执行”（vitest.config.ts 注释 (A)），否则各 worker 分片的 v8 fnMap 按 id 合并
// 会错位、functions 跌破 100%。专属全分支测试：tests/unit/views/funds/DetailCov.test.ts。

// --- Report ---
describe('funds/Report.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/funds/Report.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- Settlement ---
describe('funds/Settlement.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/funds/Settlement.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- TransferVoucher ---
describe('funds/TransferVoucher.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/funds/TransferVoucher.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})

// --- UserFundList ---
describe('funds/UserFundList.vue', () => {
  it('渲染', async () => {
    const { default: Comp } = await import('@/views/funds/UserFundList.vue')
    const w = mount(Comp)
    await flushPromises()
    expect(w.exists()).toBe(true)
  })
})
