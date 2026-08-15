/**
 * views/effectiveness/Rankings.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：rankClass 四分支、scorePercent 钳制、formatScore（null/数字）、levelLabel 映射+兜底、
 * 角色显隐（admin「评估」/ viewer「查看」）、生态列渲染（后端真实契约 scores.ecological）、
 * levelTagType 全分支、goToEvaluate 跳转、fetchRankings（items/数组/失败）、handleSearch、
 * 模板：年度/数量 select @change、查询按钮、加载/错误/空三态、表格行。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { mockGetRankings, pushSafeMock, mockUserStore } = vi.hoisted(() => ({
  mockGetRankings: vi.fn(),
  pushSafeMock: vi.fn(),
  mockUserStore: { currentUser: { role: 'admin' } as any },
}))

vi.mock('@/stores/user', () => ({ useUserStore: () => mockUserStore }))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
}))

vi.mock('@/api/effectiveness', () => ({
  getRankings: mockGetRankings,
  evaluateVillage: vi.fn(),
  compareEvaluations: vi.fn(),
}))

import Rankings from '@/views/effectiveness/Rankings.vue'

const rows = [
  {
    rank: 1,
    village_id: 1,
    village_name: '甲村',
    support_unit: '单位A',
    total_score: 95.4,
    level: 'excellent',
    scores: { economic: 90, social: 80, ecological: 70 },
  },
  {
    rank: 2,
    village_id: 2,
    village_name: '乙村',
    support_unit: '单位B',
    total_score: 88.2,
    level: 'good',
    scores: { economic: 85, social: 75, ecological: 65 },
  },
  {
    rank: 3,
    village_id: 3,
    village_name: '丙村',
    support_unit: '单位C',
    total_score: 70.0,
    level: 'average',
    scores: { economic: 70, social: 60, ecological: 50 },
  },
  {
    rank: 4,
    village_id: 4,
    name: '丁村',
    support_unit: '单位D',
    total_score: 55.1,
    level: 'poor',
    scores: { economic: 50, social: 40, ecological: 30 },
  },
  {
    rank: 5,
    village_id: 5,
    village_name: '戊村',
    support_unit: '单位E',
    total_score: 45.0,
    level: 'A',
    scores: { economic: 40, social: 30, ecological: 20 },
  },
  {
    rank: 6,
    village_id: 6,
    village_name: '己村',
    support_unit: '单位F',
    total_score: 40.0,
    level: 'B',
    scores: { economic: 30, social: 20, ecological: 10 },
  },
  {
    rank: 7,
    village_id: 7,
    village_name: '庚村',
    support_unit: '单位G',
    total_score: 35.0,
    level: 'C',
    scores: { economic: 20, social: 10, ecological: 5 },
  },
  {
    rank: 8,
    village_id: 8,
    village_name: '辛村',
    support_unit: '单位H',
    total_score: 30.0,
    level: 'D',
    scores: { economic: 10, social: 5, ecological: 2 },
  },
  {
    rank: 9,
    village_id: 9,
    village_name: '壬村',
    support_unit: '单位I',
    total_score: 25.0,
    level: 'weird',
    scores: {},
  },
  {
    rank: 10,
    village_id: 10,
    village_name: '癸村',
    support_unit: '单位J',
    total_score: null,
    level: '',
    scores: {},
  },
  { rank: 11, village_id: 11, support_unit: '单位K', total_score: 15.0, level: 'poor', scores: {} },
]

function mountComp() {
  return mount(Rankings, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-form': { name: 'ElForm', template: '<div class="el-form-stub"><slot /></div>' },
        'el-form-item': {
          name: 'ElFormItem',
          template: '<div class="el-form-item-stub"><slot /></div>',
        },
        'el-select': {
          name: 'ElSelect',
          template: '<div class="el-select-stub"><slot /></div>',
          emits: ['update:modelValue', 'change'],
        },
        'el-option': { name: 'ElOption', template: '<div class="el-option-stub"><slot /></div>' },
        'el-table': { name: 'ElTable', template: '<div class="el-table-stub"><slot /></div>' },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /><slot :row="rowD" /><slot :row="rowE" /><slot :row="rowF" /><slot :row="rowG" /><slot :row="rowH" /><slot :row="rowI" /><slot :row="rowJ" /><slot :row="rowK" /></div>',
          data() {
            return {
              rowA: rows[0],
              rowB: rows[1],
              rowC: rows[2],
              rowD: rows[3],
              rowE: rows[4],
              rowF: rows[5],
              rowG: rows[6],
              rowH: rows[7],
              rowI: rows[8],
              rowJ: rows[9],
              rowK: rows[10],
            }
          },
        },
        'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
        'el-link': {
          name: 'ElLink',
          template: '<a class="el-link-stub" @click="$emit(\'click\')"><slot /></a>',
        },
        'el-empty': { name: 'ElEmpty', template: '<div class="el-empty-stub"><slot /></div>' },
        'el-icon': { name: 'ElIcon', template: '<span class="el-icon-stub"><slot /></span>' },
      },
    },
  })
}

const findBtn = (wrapper: any, text: string) => {
  const btn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes(text))
  expect(btn, text).toBeTruthy()
  return btn!
}

beforeEach(() => {
  vi.resetAllMocks()
  mockUserStore.currentUser = { role: 'admin' }
  mockGetRankings.mockResolvedValue({ data: { items: rows } })
})

describe('挂载与加载', () => {
  it('onMounted：items 形态加载；表格渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGetRankings).toHaveBeenCalledWith(vm.filterForm.year, vm.filterForm.limit)
    expect(vm.rankings).toHaveLength(11)
    expect(vm.loading).toBe(false)
    const text = wrapper.text()
    expect(text).toContain('1')
    expect(text).toContain('甲村')
    expect(text).toContain('95.4')
    expect(text).toContain('优秀')
    expect(text).toContain('良好')
    expect(text).toContain('一般')
    expect(text).toContain('较差')
    expect(text).toContain('A级')
    expect(text).toContain('B级')
    expect(text).toContain('C级')
    expect(text).toContain('D级')
    expect(text).toContain('weird') // 未知等级原样
    expect(text).toContain('-') // total_score null → formatScore '-'
    expect(text).toContain('70') // 生态列渲染 scores.ecological（后端真实契约）
  })

  it('数组形态；加载失败 → 错误态 + 重新加载按钮；非数组非 items → [] 兜底', async () => {
    mockGetRankings.mockResolvedValue(rows)
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).rankings).toHaveLength(11)

    mockGetRankings.mockResolvedValue({ data: {} })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).rankings).toEqual([])

    mockGetRankings.mockRejectedValue(new Error('net'))
    wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.loadError).toBe(true)
    expect(vm.loading).toBe(false)
    await findBtn(wrapper, '重新加载').trigger('click')
    await flushPromises()
    expect(vm.loadError).toBe(true) // 仍失败
  })

  it('空列表 → 空态', async () => {
    mockGetRankings.mockResolvedValue({ data: { items: [] } })
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.find('.el-empty-stub').exists()).toBe(true)
  })

  it('加载中 → loading 文案', async () => {
    mockGetRankings.mockImplementation(() => new Promise(() => {})) // 永不 resolve
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.text()).toContain('加载中')
    wrapper.unmount()
  })
})

describe('工具函数', () => {
  it('rankClass 四分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.rankClass(1)).toBe('rank-gold')
    expect(vm.rankClass(2)).toBe('rank-silver')
    expect(vm.rankClass(3)).toBe('rank-bronze')
    expect(vm.rankClass(4)).toBe('')
  })

  it('scorePercent 钳制上下限', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.scorePercent(50)).toBe(50)
    expect(vm.scorePercent(150)).toBe(100)
    expect(vm.scorePercent(-10)).toBe(0)
  })

  it('formatScore：null 与数字', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatScore(null)).toBe('-')
    expect(vm.formatScore(95.4)).toBe('95.4')
    expect(vm.formatScore(70)).toBe('70.0')
  })

  it('levelLabel：映射与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.levelLabel('excellent')).toBe('优秀')
    expect(vm.levelLabel('good')).toBe('良好')
    expect(vm.levelLabel('average')).toBe('一般')
    expect(vm.levelLabel('poor')).toBe('较差')
    expect(vm.levelLabel('A')).toBe('A级')
    expect(vm.levelLabel('B')).toBe('B级')
    expect(vm.levelLabel('C')).toBe('C级')
    expect(vm.levelLabel('D')).toBe('D级')
    expect(vm.levelLabel('weird')).toBe('weird')
    expect(vm.levelLabel('')).toBe('-')
    expect(vm.levelLabel(undefined)).toBe('-')
  })

  it('levelTagType 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.levelTagType('')).toBe('info')
    expect(vm.levelTagType(undefined)).toBe('info')
    expect(vm.levelTagType('excellent')).toBe('success')
    expect(vm.levelTagType('a')).toBe('success')
    expect(vm.levelTagType('good')).toBe('primary')
    expect(vm.levelTagType('b')).toBe('primary')
    expect(vm.levelTagType('average')).toBe('warning')
    expect(vm.levelTagType('c')).toBe('warning')
    expect(vm.levelTagType('poor')).toBe('danger')
    expect(vm.levelTagType('d')).toBe('danger')
  })

  it('goToEvaluate 跳转（含 year 参数）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.goToEvaluate(42)
    expect(pushSafeMock).toHaveBeenCalledWith(
      `/effectiveness/evaluate?villageId=42&year=${vm.filterForm.year}`
    )
  })
})

describe('模板交互', () => {
  it('select change 触发 handleSearch；查询按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const base = mockGetRankings.mock.calls.length
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 2023)
    selects[0].vm.$emit('change', 2023)
    await flushPromises()
    expect(vm.filterForm.year).toBe(2023)
    expect(mockGetRankings.mock.calls.length).toBe(base + 1)

    selects[1].vm.$emit('update:modelValue', 50)
    selects[1].vm.$emit('change', 50)
    await flushPromises()
    expect(vm.filterForm.limit).toBe(50)
    expect(mockGetRankings.mock.calls.length).toBe(base + 2)

    await findBtn(wrapper, '查询').trigger('click')
    await flushPromises()
    expect(mockGetRankings.mock.calls.length).toBe(base + 3)
  })

  it('村庄链接点击跳转评估（模板内联）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const links = wrapper.findAllComponents({ name: 'ElLink' })
    await links[0].trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith(
      `/effectiveness/evaluate?villageId=1&year=${vm.filterForm.year}`
    )
  })

  it('「评估」操作按钮点击跳转', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findBtn(wrapper, '评估').trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith(
      `/effectiveness/evaluate?villageId=1&year=${vm.filterForm.year}`
    )
  })

  it('viewer 角色入口降级为「查看」（不可发起评估）', async () => {
    mockUserStore.currentUser = { role: 'viewer' }
    const wrapper = mountComp()
    await flushPromises()
    // 操作列不再有「评估」按钮，仅「查看」
    const btns = wrapper.findAll('el-button-stub')
    expect(btns.some((b: any) => b.text().trim() === '评估')).toBe(false)
    expect(btns.some((b: any) => b.text().includes('查看'))).toBe(true)
  })
})

describe('isAdmin 权限计算', () => {
  it('非管理员角色 + is_superuser=true → isAdmin=true（操作列显示「评估」）', async () => {
    mockUserStore.currentUser = { role: 'user', is_superuser: true }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.isAdmin).toBe(true)
    const btns = wrapper.findAll('el-button-stub')
    expect(btns.some((b: any) => b.text().trim() === '评估')).toBe(true)
    await findBtn(wrapper, '评估').trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith(
      `/effectiveness/evaluate?villageId=1&year=${vm.filterForm.year}`
    )
  })

  it('currentUser 无 role 且非超管 → isAdmin=false（显示「查看」）', async () => {
    mockUserStore.currentUser = {} as any
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).isAdmin).toBe(false)
    const btns = wrapper.findAll('el-button-stub')
    expect(btns.some((b: any) => b.text().trim() === '评估')).toBe(false)
    expect(btns.some((b: any) => b.text().includes('查看'))).toBe(true)
  })

  it('currentUser 为 null → isAdmin=false', async () => {
    mockUserStore.currentUser = null as any
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).isAdmin).toBe(false)
    const btns = wrapper.findAll('el-button-stub')
    expect(btns.some((b: any) => b.text().trim() === '评估')).toBe(false)
  })
})

describe('排名响应别名兼容', () => {
  it('grade/support_unit_name 旧字段映射', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    mockGetRankings.mockResolvedValue({
      items: [{ id: 1, grade: 'A', support_unit_name: '某旅', scores: { x: 1 } }],
    })
    await vm.fetchRankings()
    expect(vm.rankings[0].level).toBe('A')
    expect(vm.rankings[0].support_unit).toBe('某旅')
  })
})

describe('字段缺省分支补充', () => {
  it('grade 兼容/字段缺省/非数组 data', async () => {
    ;(mockGetRankings as any).mockResolvedValueOnce({
      data: { rankings: [{ grade: 'A', support_unit_name: '镇', scores: null }] },
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.rankings[0].level).toBe('A')
    expect(vm.rankings[0].support_unit).toBe('镇')
    expect(vm.rankings[0].scores).toEqual({})
    wrapper.unmount()
  })
  it('rankings 返回非数组对象 → 空列表', async () => {
    ;(mockGetRankings as any).mockResolvedValueOnce({ data: { rankings: { x: 1 } } })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).rankings).toEqual([])
    wrapper.unmount()
  })
})

describe('字段有值分支', () => {
  it('level/support_unit 直接使用', async () => {
    ;(mockGetRankings as any).mockResolvedValueOnce({
      data: { rankings: [{ level: 'good', support_unit: '单位X', scores: { a: 1 } }] },
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.rankings[0].level).toBe('good')
    expect(vm.rankings[0].support_unit).toBe('单位X')
    wrapper.unmount()
  })
})

describe('全缺省分支', () => {
  it('level/support_unit/scores 全缺省 → null 兜底', async () => {
    ;(mockGetRankings as any).mockResolvedValueOnce({ data: { rankings: [{ rank: 9 }] } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.rankings[0].level).toBeNull()
    expect(vm.rankings[0].support_unit).toBeNull()
    wrapper.unmount()
  })
})
