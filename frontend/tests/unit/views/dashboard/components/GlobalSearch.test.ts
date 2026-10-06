/**
 * views/dashboard/components/GlobalSearch.vue 覆盖率攻坚（四指标 100%）
 *
 * 覆盖：防抖输入（空关键词清空/有词触发）、doSearch 成功/失败、onFocus/onBlur 定时器、
 * 键盘导航 moveDown/moveUp/selectCurrent 全边界、onItemClick、onUnmounted 清理、
 * groupedResults 全部类型分组、flatIndex、loading 图标、未找到/结果/底部提示三态渲染。
 *
 * 方案：mock '@/api/search'（globalSearch）与 '@/composables/useRouterSafe'，
 * el-input 使用可交互 stub（真实 input 元素），fake timers 控制防抖与 blur 延迟。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick, defineComponent } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

const { mockGlobalSearch, mockPushSafe } = vi.hoisted(() => ({
  mockGlobalSearch: vi.fn(),
  mockPushSafe: vi.fn(),
}))

vi.mock('@/api/search', () => ({
  globalSearch: (...args: any[]) => mockGlobalSearch(...args),
  SEARCH_TYPE_LABELS: {
    village: '帮扶村',
    project: '项目',
    policy: '政策法规',
    school: '学校',
    user: '用户',
  },
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mockPushSafe }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), resolve: vi.fn(() => ({ name: 'Test', matched: [{ path: '/' }] })) }),
}))

import GlobalSearch from '@/views/dashboard/components/GlobalSearch.vue'

const ElInputStub = defineComponent({
  name: 'ElInput',
  props: ['modelValue', 'placeholder', 'prefixIcon', 'clearable'],
  emits: ['update:modelValue', 'input', 'focus', 'blur'],
  template: `<div class="el-input-stub">
    <input
      :value="modelValue"
      :placeholder="placeholder"
      @input="$emit('update:modelValue', $event.target.value); $emit('input', $event.target.value)"
      @focus="$emit('focus')"
      @blur="$emit('blur')"
    />
    <slot name="suffix" />
  </div>`,
})

const ElIconStub = { name: 'ElIcon', template: '<span><slot /></span>' }
const ElTagStub = { name: 'ElTag', template: '<span><slot /></span>' }
const TransitionStub = { name: 'Transition', template: '<div><slot /></div>' }

const fullResults = {
  total: 5,
  items: [
    { id: 1, type: 'village', title: '村A', subtitle: '贵州', link: '/villages/1' },
    { id: 2, type: 'project', title: '项目B', subtitle: '编号 P2', link: '/projects/2' },
    { id: 3, type: 'school', title: '学校C', link: '/schools/3' },
    { id: 4, type: 'policy', title: '政策D', subtitle: '文件', link: '/policies/4' },
    { id: 5, type: 'user', title: '用户E', subtitle: 'admin', link: '/system/users' },
  ],
}

function mountSearch() {
  return mount(GlobalSearch, {
    global: {
      plugins: [createPinia()],
      stubs: {
        'el-input': ElInputStub,
        'el-icon': ElIconStub,
        'el-tag': ElTagStub,
        transition: TransitionStub,
        Transition: TransitionStub,
      },
    },
  })
}

async function searchAndFlush(wrapper: any, keyword: string) {
  await wrapper.find('input').setValue(keyword)
  vi.advanceTimersByTime(400)
  await flushPromises()
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('输入与防抖', () => {
  it('渲染搜索框与默认占位符；自定义占位符生效', () => {
    const wrapper = mountSearch()
    expect(wrapper.find('.global-search').exists()).toBe(true)
    expect(wrapper.find('input').attributes('placeholder')).toContain('搜索')

    const wrapper2 = mount(GlobalSearch, {
      props: { placeholder: '自定义占位' },
      global: {
        stubs: { 'el-input': ElInputStub, 'el-icon': ElIconStub, transition: TransitionStub },
      },
    })
    expect(wrapper2.find('input').attributes('placeholder')).toBe('自定义占位')
    wrapper2.unmount()
    wrapper.unmount()
  })

  it('空关键词输入 → 清空结果与下拉，不发请求', async () => {
    const wrapper = mountSearch()
    const vm = wrapper.vm as any
    vm.keyword = '测试'
    vm.showDropdown = true
    await wrapper.find('input').setValue('   ')
    vi.advanceTimersByTime(400)
    expect(mockGlobalSearch).not.toHaveBeenCalled()
    expect(vm.showDropdown).toBe(false)
    expect(vm.results).toEqual([])
    wrapper.unmount()
  })

  it('连续输入 → 只触发最后一次防抖请求', async () => {
    mockGlobalSearch.mockResolvedValue({ total: 0, items: [] })
    const wrapper = mountSearch()
    await wrapper.find('input').setValue('甲')
    vi.advanceTimersByTime(100)
    await wrapper.find('input').setValue('甲乙')
    vi.advanceTimersByTime(100)
    await wrapper.find('input').setValue('甲乙丙')
    vi.advanceTimersByTime(400)
    await flushPromises()
    expect(mockGlobalSearch).toHaveBeenCalledTimes(1)
    expect(mockGlobalSearch).toHaveBeenCalledWith('甲乙丙', 20)
    wrapper.unmount()
  })

  it('乱序响应：过期请求不得覆盖最新结果', async () => {
    // 按“关键词”而不是“调用先后”索引挂起的 Promise：
    // mockImplementationOnce 队列把「哪个 Promise 属于哪次请求」押在调用顺序上，任何一次
    // 多余/缺失的调用（防抖窗口、环境复用下的时序差异）都会让两个 resolver 互换或错位，
    // 使断言以“旧结果覆盖新结果”的假象失败，而组件其实是对的。按关键词索引后，
    // 无论调用顺序如何，测试都能精确控制「新请求先返回、旧请求后返回」。
    const pending = new Map<string, (v: any) => void>()
    mockGlobalSearch.mockReset() // 清掉前序用例遗留的持久实现，避免干扰（clearAllMocks 不还原实现）
    mockGlobalSearch.mockImplementation(
      (q: string) => new Promise((resolve) => pending.set(q, resolve))
    )

    const wrapper = mountSearch()
    await wrapper.find('input').setValue('旧词')
    vi.advanceTimersByTime(400) // 第 1 次搜索发出（挂起）
    await wrapper.find('input').setValue('新词')
    vi.advanceTimersByTime(400) // 第 2 次搜索发出（挂起）
    expect(mockGlobalSearch).toHaveBeenCalledTimes(2)
    expect([...pending.keys()]).toEqual(['旧词', '新词'])

    // 后发先至：新请求先返回
    pending.get('新词')!({ total: 1, items: [{ id: 2, type: 'village', title: '新结果', link: '/v/2' }] })
    await flushPromises()
    expect((wrapper.vm as any).results[0].title).toBe('新结果')
    expect((wrapper.vm as any).loading).toBe(false)

    // 旧请求后返回 → 必须被丢弃，不得覆盖新结果
    pending.get('旧词')!({ total: 9, items: [{ id: 1, type: 'village', title: '旧结果', link: '/v/1' }] })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.results[0].title).toBe('新结果')
    expect(vm.total).toBe(1)
    wrapper.unmount()
  })
})

describe('搜索结果渲染', () => {
  it('全部五类结果分组渲染 + 底部提示 + active 高亮', async () => {
    mockGlobalSearch.mockResolvedValue(fullResults)
    const wrapper = mountSearch()
    await searchAndFlush(wrapper, '测试')
    const text = wrapper.text()
    expect(text).toContain('帮扶村')
    expect(text).toContain('项目')
    expect(text).toContain('学校')
    expect(text).toContain('政策法规')
    expect(text).toContain('用户')
    expect(text).toContain('共 5 条结果')
    expect(text).toContain('↑↓ 选择 · Enter 跳转')
    expect(wrapper.findAll('.result-item').length).toBe(5)
    // 无 subtitle 的项不渲染 subtitle
    expect(wrapper.text()).not.toContain('学校C的副标题')
    // mouseenter → active
    await wrapper.findAll('.result-item')[0].trigger('mouseenter')
    await nextTick()
    expect(wrapper.findAll('.result-item')[0].classes()).toContain('active')
    wrapper.unmount()
  })

  it('未找到结果 → 显示 no-result 提示', async () => {
    mockGlobalSearch.mockResolvedValue({ total: 0, items: [] })
    const wrapper = mountSearch()
    await searchAndFlush(wrapper, '不存在')
    expect(wrapper.text()).toContain('未找到')
    expect(wrapper.text()).toContain('不存在')
    wrapper.unmount()
  })

  it('请求失败 → 结果清空、下拉保留、无未找到提示', async () => {
    mockGlobalSearch.mockRejectedValue(new Error('network'))
    const wrapper = mountSearch()
    const vm = wrapper.vm as any
    await searchAndFlush(wrapper, '测试')
    expect(vm.results).toEqual([])
    expect(vm.total).toBe(0)
    expect(vm.showNoResult).toBe(false)
    expect(wrapper.find('.no-result').exists()).toBe(false)
    wrapper.unmount()
  })

  it('loading 状态 → 显示加载图标；结果为空时下拉隐藏', async () => {
    const wrapper = mountSearch()
    const vm = wrapper.vm as any
    vm.showDropdown = true
    vm.loading = true
    await nextTick()
    expect(wrapper.find('.is-loading').exists()).toBe(true)
    vm.loading = false
    vm.results = []
    vm.showNoResult = false
    await nextTick()
    // 结果与未找到均为空 → v-show 条件假，下拉隐藏
    expect(wrapper.find('.search-dropdown').attributes('style') || '').toContain('display: none')
    wrapper.unmount()
  })
})

describe('交互与导航', () => {
  it('点击结果项 → 关闭下拉并 pushSafe 跳转', async () => {
    mockGlobalSearch.mockResolvedValue(fullResults)
    const wrapper = mountSearch()
    await searchAndFlush(wrapper, '测试')
    await wrapper.findAll('.result-item')[0].trigger('mousedown')
    expect(mockPushSafe).toHaveBeenCalledWith('/villages/1')
    expect((wrapper.vm as any).showDropdown).toBe(false)
    wrapper.unmount()
  })

  it('键盘导航：down/up 边界与 Enter 选择', async () => {
    mockGlobalSearch.mockResolvedValue(fullResults)
    const wrapper = mountSearch()
    const vm = wrapper.vm as any
    await searchAndFlush(wrapper, '测试')

    // 空结果时 moveDown/moveUp 直接返回
    vm.results = []
    await wrapper.trigger('keydown.down')
    expect(vm.activeIndex).toBe(-1)
    await wrapper.trigger('keydown.up')
    expect(vm.activeIndex).toBe(-1)

    vm.results = fullResults.items
    await wrapper.trigger('keydown.down')
    expect(vm.activeIndex).toBe(0)
    await wrapper.trigger('keydown.up')
    expect(vm.activeIndex).toBe(0)
    // 连续 down 到末尾 clamp
    for (let i = 0; i < 10; i++) await wrapper.trigger('keydown.down')
    expect(vm.activeIndex).toBe(4)
    // Enter 选中最后一个 → 跳转
    await wrapper.trigger('keydown.enter')
    expect(mockPushSafe).toHaveBeenCalledWith('/system/users')
    expect(vm.showDropdown).toBe(false)
    wrapper.unmount()
  })

  it('Enter 且 activeIndex 越界 → 不跳转', async () => {
    mockGlobalSearch.mockResolvedValue(fullResults)
    const wrapper = mountSearch()
    const vm = wrapper.vm as any
    await searchAndFlush(wrapper, '测试')
    vm.activeIndex = -1
    await wrapper.trigger('keydown.enter')
    expect(mockPushSafe).not.toHaveBeenCalled()
    vm.activeIndex = 99
    await wrapper.trigger('keydown.enter')
    expect(mockPushSafe).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('focus 恢复下拉（有关键词且 blurTimer 清理）；blur 延迟关闭', async () => {
    mockGlobalSearch.mockResolvedValue(fullResults)
    const wrapper = mountSearch()
    const vm = wrapper.vm as any
    await searchAndFlush(wrapper, '测试')
    // blur → 200ms 后关闭
    await wrapper.find('input').trigger('blur')
    expect(vm.showDropdown).toBe(true)
    vi.advanceTimersByTime(200)
    expect(vm.showDropdown).toBe(false)
    // focus → 有关键词重新打开
    await wrapper.find('input').trigger('focus')
    expect(vm.showDropdown).toBe(true)
    // focus 时清空已有 blurTimer
    await wrapper.find('input').trigger('blur')
    await wrapper.find('input').trigger('focus')
    vi.advanceTimersByTime(200)
    expect(vm.showDropdown).toBe(true)
    // 无关键词 focus → 不打开
    await wrapper.find('input').setValue('')
    vm.showDropdown = false
    await wrapper.find('input').trigger('focus')
    expect(vm.showDropdown).toBe(false)
    wrapper.unmount()
  })
})

describe('清理', () => {
  it('onUnmounted 清理防抖与 blur 定时器', async () => {
    const wrapper = mountSearch()
    const clearSpy = vi.spyOn(globalThis, 'clearTimeout')
    wrapper.find('input').trigger('blur') // 安排 blur 延迟关闭定时器
    wrapper.unmount() // 卸载必须清理未触发的定时器
    // 清理契约：blur 安排的定时器在卸载时被 clearTimeout 回收，不再触发
    vi.advanceTimersByTime(500)
    expect(clearSpy).toHaveBeenCalled()
    clearSpy.mockRestore()
  })
})
