/**
 * views/policies/Category.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 加载统计（成功/失败）、层级选项初始化、handleLevelClick、
 * handleViewAll/handleViewMilitary/handleViewLocal、模板渲染。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { pushSafeMock, policyStore, logError, mockGetLevelOptions } = vi.hoisted(() => ({
  pushSafeMock: vi.fn(),
  policyStore: {
    fetchStatistics: vi.fn(),
  },
  logError: vi.fn(),
  mockGetLevelOptions: vi.fn(),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
}))

vi.mock('@/stores/policy', () => ({ usePolicyStore: () => policyStore }))

// 真实接口形态：返回全部层级（Promise），前端按「专项/地方」拆分
vi.mock('@/api/policy', () => ({
  getLevelOptions: mockGetLevelOptions,
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import Category from '@/views/policies/Category.vue'

const allLevels = [
  { value: 'national', label: '国家级' },
  { value: 'provincial', label: '省级' },
  { value: 'municipal', label: '市级' },
  { value: 'county', label: '县级' },
  { value: 'military', label: '专项' },
]

const stats = {
  military: {
    total: 3,
    levels: { national: 1, province: 2, city: 0 },
  },
  local: {
    total: 1,
    levels: { county: 1 },
  },
}

function mountComp() {
  return mount(Category, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
        'el-icon': { template: '<span class="el-icon-stub"><slot /></span>' },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-row': { template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { template: '<div class="el-col-stub"><slot /></div>' },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  policyStore.fetchStatistics.mockResolvedValue(stats)
  mockGetLevelOptions.mockResolvedValue(allLevels)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与统计', () => {
  it('onMounted 加载统计', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(policyStore.fetchStatistics).toHaveBeenCalled()
    expect(vm.statistics.military.total).toBe(3)
    expect(vm.statistics.local.levels.county).toBe(1)
    expect(vm.loading).toBe(false)
  })

  it('统计加载失败 → logger 静默', async () => {
    policyStore.fetchStatistics.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('层级配置初始化（全部层级按专项/地方拆分）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.militaryLevels).toHaveLength(1)
    expect(vm.militaryLevels[0].value).toBe('military')
    expect(vm.localLevels).toHaveLength(4)
    expect(vm.localLevels[0].value).toBe('national')
    expect(vm.localLevels[3].value).toBe('county')
  })

  it('层级响应形态：信封 items / data 数组 / 加载失败空列表', async () => {
    // 信封 items 形态
    mockGetLevelOptions.mockResolvedValueOnce({ items: [{ value: 'military', label: '专项' }] })
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).militaryLevels).toHaveLength(1)

    // data 数组形态
    mockGetLevelOptions.mockResolvedValueOnce({ data: [{ value: 'county', label: '县级' }] })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).localLevels).toHaveLength(1)

    // 加载失败 → 空列表
    mockGetLevelOptions.mockRejectedValueOnce(new Error('net'))
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).militaryLevels).toEqual([])
    expect((wrapper.vm as any).localLevels).toEqual([])
  })
})

describe('导航操作', () => {
  it('handleLevelClick → pushSafe 带 query', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleLevelClick('military', 'national')
    expect(pushSafeMock).toHaveBeenCalledWith({
      path: '/policies',
      query: { category: 'military', level: 'national' },
    })
  })

  it('handleViewAll / handleViewMilitary / handleViewLocal', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleViewAll()
    expect(pushSafeMock).toHaveBeenCalledWith('/policies')
    vm.handleViewMilitary()
    expect(pushSafeMock).toHaveBeenCalledWith({
      path: '/policies',
      query: { category: 'military' },
    })
    vm.handleViewLocal()
    expect(pushSafeMock).toHaveBeenCalledWith({
      path: '/policies',
      query: { category: 'local' },
    })
  })

  it('层级卡片点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    pushSafeMock.mockClear()
    const cards = wrapper.findAll('.level-card')
    await cards[0].trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith({
      path: '/policies',
      query: { category: 'military', level: 'military' },
    })

    pushSafeMock.mockClear()
    await cards[cards.length - 1].trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith({
      path: '/policies',
      query: { category: 'local', level: 'county' },
    })
  })

  it('快捷操作按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    pushSafeMock.mockClear()
    const btns = wrapper.findAll('.el-button-stub')
    const all = btns.find((b) => b.text().includes('查看全部政策'))
    await all!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/policies')

    const mil = btns.find((b) => b.text().includes('查看专项政策'))
    await mil!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith({ path: '/policies', query: { category: 'military' } })

    const loc = btns.find((b) => b.text().includes('查看地方政策'))
    await loc!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith({ path: '/policies', query: { category: 'local' } })
  })
})

describe('模板渲染', () => {
  it('统计数字与层级计数渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('专项政策')
    expect(wrapper.text()).toContain('地方政策')
    expect(wrapper.text()).toContain('3 条')
    expect(wrapper.text()).toContain('国家级')
    expect(wrapper.text()).toContain('县级')
  })
})
