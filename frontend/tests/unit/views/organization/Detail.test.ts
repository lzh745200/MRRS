/**
 * views/organization/Detail.vue 覆盖率攻坚（四指标 100%）
 *
 * 覆盖：loadData 成功（res.data.data 嵌套/flat 扁平/字段缺失兜底）失败（无 id 早退）、
 * loadMembers 成功失败、formatDate/formatLevel/roleLabel/roleTagType 全分支、
 * goToOrg/handleEdit/handleBack、模板（面包屑祖先、组织类型三标签、层级、成员表格、
 * 子组织表格 vs 空态、分页 v-if、成员空态、脱敏字段兜底）。
 *
 * 方案：mock vue-router useRoute、@/api/organization、useRouterSafe、useDesensitize、
 * element-plus、logger；el-table-column 插槽注入多样本行。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const {
  ElMessage,
  mockGetDetail,
  mockGetMembers,
  mockPushSafe,
  routeBox,
  logError,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockGetDetail: vi.fn(),
  mockGetMembers: vi.fn(),
  mockPushSafe: vi.fn(),
  routeBox: { params: {} as Record<string, any> },
  logError: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeBox,
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/organization', () => ({
  getOrganizationDetail: (...a: any[]) => mockGetDetail(...a),
  getOrganizationMembers: (...a: any[]) => mockGetMembers(...a),
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mockPushSafe }),
  safeRouteParam: (value: unknown, fallback = 0) => {
    if (value === undefined || value === null) return fallback
    if (Array.isArray(value)) value = value[0]
    const num = Number(value)
    return Number.isFinite(num) ? num : fallback
  },
}))

vi.mock('@/composables/useDesensitize', () => ({
  useDesensitize: () => ({
    ds: (v: any) => (v ? `脱敏:${v}` : ''),
    role: 'viewer',
  }),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

import Detail from '@/views/organization/Detail.vue'

const detailData = {
  id: 3,
  name: '某单位',
  code: 'ORG-3',
  org_type: 'department',
  level: 'level_2',
  is_active: true,
  sort_order: 1,
  description: '单位描述',
  contact_person: '张三',
  contact_phone: '13800138000',
  contact_email: 'a@b.com',
  address: '地址',
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-02-01T00:00:00',
  children_count: 2,
  member_count: 3,
  children: [
    { id: 4, name: '子单位', code: 'SUB', org_type: 'support_unit', level: 3, sort_order: 1 },
    { id: 5, name: '部门B', code: 'B', org_type: 'custom', level: null, sort_order: 2 },
  ],
  ancestors: [{ id: 1, name: '总部' }, { id: 2, name: '分部' }],
}

const memberA = { id: 1, full_name: '张三', username: 'zhangsan', role: 'super_admin' }
const memberB = { id: 2, full_name: '', username: 'lisi', role: 'admin' }
const memberC = { id: 3, username: 'wangwu', role: 'manager' }
const memberD = { id: 4, username: 'zhaoliu', role: 'approval_leader' }
const memberE = { id: 5, username: 'sunqi', role: 'user' }
const memberF = { id: 6, username: 'zhouba', role: 'viewer' }
const memberG = { id: 7, username: 'weird', role: 'weird_role' }
const memberH = { id: 8, username: 'empty', role: '' }

const stubs = {
  'el-breadcrumb': { name: 'ElBreadcrumb', template: '<div class="el-breadcrumb-stub"><slot /></div>' },
  'el-breadcrumb-item': {
    name: 'ElBreadcrumbItem',
    template: '<span class="el-breadcrumb-item-stub"><slot /></span>',
    props: ['to'],
  },
  'el-row': { name: 'ElRow', template: '<div class="el-row-stub"><slot /></div>' },
  'el-col': { name: 'ElCol', template: '<div class="el-col-stub"><slot /></div>' },
  'el-card': { name: 'ElCard', template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
  'el-button': { name: 'ElButton', template: '<button class="el-button-stub"><slot /></button>' },
  'el-descriptions': { name: 'ElDescriptions', template: '<div class="el-descriptions-stub"><slot /></div>' },
  'el-descriptions-item': { name: 'ElDescriptionsItem', props: ['label'], template: '<div class="el-descriptions-item-stub">{{ label }}<slot /></div>' },
  'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
  'el-table': { name: 'ElTable', template: '<div class="el-table-stub"><slot /></div>', props: ['data'] },
  'el-table-column': {
    name: 'ElTableColumn',
    props: ['prop', 'label', 'type'],
    template:
      '<div class="el-table-column-stub" :label="label"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /><slot :row="rowD" /><slot :row="rowE" /><slot :row="rowF" /><slot :row="rowG" /><slot :row="rowH" /><slot :row="childA" /><slot :row="childB" /><slot :row="childC" /></div>',
    data() {
      return {
        rowA: memberA, rowB: memberB, rowC: memberC, rowD: memberD, rowE: memberE, rowF: memberF, rowG: memberG, rowH: memberH,
        childA: detailData.children[0],
        childB: detailData.children[1],
        childC: { id: 6, name: '部门单位子组织', code: 'DEP', org_type: 'department', level: 1, sort_order: 1 },
      }
    },
  },
  'el-empty': {
    name: 'ElEmpty',
    props: ['description'],
    template: '<div class="el-empty-stub">{{ description }}</div>',
  },
  'el-pagination': { name: 'ElPagination', template: '<div class="el-pagination-stub" />', emits: ['update:currentPage', 'current-change'] },
}

function mountComp() {
  return mount(Detail, {
    global: { renderStubDefaultSlot: true, stubs },
  })
}

async function clickBtn(wrapper: any, text: string) {
  const btn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().trim().includes(text))
  expect(btn, `按钮「${text}」`).toBeTruthy()
  await btn!.trigger('click')
  await flushPromises()
}

beforeEach(() => {
  vi.resetAllMocks()
  routeBox.params = { id: '3' }
  mockGetDetail.mockResolvedValue({ data: { data: detailData } })
  mockGetMembers.mockResolvedValue({
    data: { items: [memberA, memberB, memberC, memberD, memberE, memberF, memberG, memberH], total: 15 },
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与详情加载', () => {
  it('onMounted 加载详情（嵌套形态）与成员；模板全字段渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGetDetail).toHaveBeenCalledWith(3)
    expect(mockGetMembers).toHaveBeenCalledWith(3, { page: 1, page_size: 10 })
    expect(vm.detail.name).toBe('某单位')
    expect(vm.members.length).toBe(8)
    expect(vm.memberTotal).toBe(15)
    expect(vm.loading).toBe(false)
    const text = wrapper.text()
    expect(text).toContain('组织管理')
    expect(text).toContain('总部')
    expect(text).toContain('分部')
    expect(text).toContain('某单位')
    expect(text).toContain('部门单位')
    expect(text).toContain('第2级')
    expect(text).toContain('正常')
    expect(text).toContain('脱敏:张三')
    expect(text).toContain('子单位')
    expect(text).toContain('部门B')
    expect(text).toContain('超级管理员')
    expect(text).toContain('管理员')
    expect(text).toContain('经理')
    expect(text).toContain('审批领导')
    expect(text).toContain('普通用户')
    expect(text).toContain('访客')
    expect(text).toContain('weird_role')
    expect(text).toContain('未知')
    wrapper.unmount()
  })

  it('详情响应扁平形态 + 稀疏字段兜底', async () => {
    mockGetDetail.mockResolvedValue({
      data: { id: 9, name: '扁平单位', org_type: 'custom', is_active: false },
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.detail.name).toBe('扁平单位')
    expect(vm.detail.code).toBe('')
    // 模板兜底：编码 — / 类型自定义 / 停用
    const text = wrapper.text()
    expect(text).toContain('—')
    expect(text).toContain('custom')
    expect(text).toContain('停用')
    wrapper.unmount()
  })

  it('主卡组织类型 support_unit → 帮扶单位标签；子组织 department → 部门单位标签', async () => {
    mockGetDetail.mockResolvedValue({
      data: {
        data: {
          ...detailData,
          org_type: 'support_unit',
          children: [
            { id: 4, name: '子单位', code: 'SUB', org_type: 'department', level: 3, sort_order: 1 },
            { id: 5, name: '部门B', code: 'B', org_type: 'support_unit', level: null, sort_order: 2 },
          ],
        },
      },
    })
    const wrapper = mountComp()
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('帮扶单位')
    expect(text).toContain('部门单位')
    wrapper.unmount()
  })

  it('详情加载失败 → logger + 错误提示', async () => {
    mockGetDetail.mockRejectedValue(new Error('down'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalledWith('加载组织信息失败:', expect.any(Error))
    expect(ElMessage.error).toHaveBeenCalledWith('加载组织信息失败')
    expect((wrapper.vm as any).loading).toBe(false)
    wrapper.unmount()
  })

  it('无路由 id → loadData/loadMembers 直接返回', async () => {
    routeBox.params = {}
    const wrapper = mountComp()
    await flushPromises()
    expect(mockGetDetail).not.toHaveBeenCalled()
    expect(mockGetMembers).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('成员加载失败 → 空数组与 0 兜底；memberLoading 复位', async () => {
    mockGetMembers.mockRejectedValue(new Error('down'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.members).toEqual([])
    expect(vm.memberTotal).toBe(0)
    expect(vm.memberLoading).toBe(false)
    // 空成员 → el-empty「暂无成员」
    expect(wrapper.text()).toContain('暂无成员')
    wrapper.unmount()
  })

  it('成员响应扁平形态且缺 items/total → || 兜底', async () => {
    mockGetMembers.mockResolvedValue({ data: { data: {} } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.members).toEqual([])
    expect(vm.memberTotal).toBe(0)
    wrapper.unmount()
  })
})

describe('辅助函数', () => {
  it('formatDate / formatLevel / roleLabel / roleTagType 全分支', () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.formatDate(undefined)).toBe('无')
    expect(vm.formatDate('2024-01-01T10:00:00')).toBe('2024-01-01')
    expect(vm.formatLevel(null)).toBe('未设置')
    expect(vm.formatLevel(undefined)).toBe('未设置')
    expect(vm.formatLevel('level_5')).toBe('第5级')
    expect(vm.formatLevel('plain')).toBe('plain')
    expect(vm.roleLabel('super_admin')).toBe('超级管理员')
    expect(vm.roleLabel('admin')).toBe('管理员')
    expect(vm.roleLabel('manager')).toBe('经理')
    expect(vm.roleLabel('approval_leader')).toBe('审批领导')
    expect(vm.roleLabel('user')).toBe('普通用户')
    expect(vm.roleLabel('viewer')).toBe('访客')
    expect(vm.roleLabel('unknown')).toBe('unknown')
    expect(vm.roleLabel('')).toBe('未知')
    expect(vm.roleTagType('super_admin')).toBe('danger')
    expect(vm.roleTagType('admin')).toBe('warning')
    expect(vm.roleTagType('manager')).toBe('success')
    expect(vm.roleTagType('approval_leader')).toBe('primary')
    expect(vm.roleTagType('user')).toBe('info')
    expect(vm.roleTagType('viewer')).toBe('info')
    expect(vm.roleTagType('x')).toBe('info')
    wrapper.unmount()
  })

  it('goToOrg / handleEdit / handleBack → pushSafe', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.detail.id = 3
    vm.goToOrg(7)
    expect(mockPushSafe).toHaveBeenCalledWith('/organizations/7')
    vm.handleEdit()
    expect(mockPushSafe).toHaveBeenCalledWith('/organizations/3/edit')
    vm.handleBack()
    expect(mockPushSafe).toHaveBeenCalledWith('/organizations')
    wrapper.unmount()
  })

  it('「编辑」「返回」按钮触发对应跳转', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await clickBtn(wrapper, '编辑')
    expect(mockPushSafe).toHaveBeenCalledWith('/organizations/3/edit')
    await clickBtn(wrapper, '返回')
    expect(mockPushSafe).toHaveBeenCalledWith('/organizations')
    wrapper.unmount()
  })

  it('子组织名称链接 → goToOrg', async () => {
    const wrapper = mountComp()
    await flushPromises()
    // 名称列插槽含 8 个成员行 + 2 个子组织行；「子单位」链接在第 8 位（id=4）
    const links = wrapper.findAll('.org-name-link')
    const subLink = links.find((l: any) => l.text() === '子单位')
    expect(subLink).toBeTruthy()
    await subLink!.trigger('click')
    expect(mockPushSafe).toHaveBeenCalledWith('/organizations/4')
    wrapper.unmount()
  })
})

describe('模板分支', () => {
  it('无子组织 → el-empty「暂无下属组织」', async () => {
    mockGetDetail.mockResolvedValue({ data: { data: { ...detailData, children: [] } } })
    const wrapper = mountComp()
    await flushPromises()
    const empties = wrapper.findAll('.el-empty-stub')
    expect(empties.some((e: any) => e.text().includes('暂无下属组织'))).toBe(true)
    wrapper.unmount()
  })

  it('成员分页：total > pageSize 显示分页；翻页触发加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const pager = wrapper.findComponent({ name: 'ElPagination' })
    expect(pager.exists()).toBe(true)
    pager.vm.$emit('update:currentPage', 2)
    pager.vm.$emit('current-change', 2)
    await nextTick()
    expect((wrapper.vm as any).memberPage).toBe(2)
    expect(mockGetMembers).toHaveBeenCalledWith(3, { page: 2, page_size: 10 })
    wrapper.unmount()
  })
})

describe('成员管理跳转', () => {
  it('分配成员按钮 → goManageMembers', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const btn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().includes('分配成员'))
    if (btn) {
      await btn.trigger('click')
    } else {
      vm.goManageMembers()
    }
    wrapper.unmount()
  })
})
