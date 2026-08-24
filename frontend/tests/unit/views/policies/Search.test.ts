/**
 * views/policies/Search.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 加载分类与数据、loadCategories 数组/对象/失败、
 * loadData 成功/失败、searchStr 组装、handleSearch/handleReset、
 * handleViewDetail/handleSelectionChange、分页 size/current、
 * 模板列插槽与 v-model。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { ElMessage, getMock, apiRequestMock, pushSafeMock, logError } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  getMock: vi.fn(),
  apiRequestMock: vi.fn(),
  pushSafeMock: vi.fn(),
  logError: vi.fn(),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/request', () => ({
  get: getMock,
  apiRequest: apiRequestMock,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import Search from '@/views/policies/Search.vue'

const rows = [
  {
    id: '1',
    title: '政策A',
    category: 'military',
    category_name: '专项政策',
    department: '军委',
    issuing_authority: '',
    publish_date: '2024-01-01T00:00:00',
    status: 'active',
    created_at: '2024-01-02',
    updated_at: '',
  },
  {
    id: '2',
    title: '政策B',
    category: 'local',
    category_name: '',
    department: '',
    issuing_authority: '省政府',
    publish_date: '',
    status: 'invalid',
  },
]

function mountComp() {
  return mount(Search, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
        'el-form': { template: '<div class="el-form-stub"><slot /></div>' },
        'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
        'el-row': { template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { template: '<div class="el-col-stub"><slot /></div>' },
        'el-input': {
          template:
            '<div class="el-input-stub" @click="$emit(\'update:modelValue\', \'V\')" />',
        },
        'el-select': {
          template:
            '<div class="el-select-stub" @click="$emit(\'update:modelValue\', \'x\')"><slot /></div>',
        },
        'el-option': { template: '<div class="el-option-stub" />' },
        'el-date-picker': {
          template:
            '<div class="el-date-picker-stub" @click="$emit(\'update:modelValue\', [\'a\', \'b\'])" />',
        },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-table': {
          template:
            '<div class="el-table-stub" @click="$emit(\'selection-change\', [rowA])"><slot name="default" /></div>',
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
          data() {
            return { rowA: { ...rows[0] }, rowB: { ...rows[1] } }
          },
        },
        'el-link': {
          template: '<a class="el-link-stub" @click="$emit(\'click\')"><slot /></a>',
          emits: ['click'],
        },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-pagination': {
          template:
            '<div class="el-pagination-stub" @click="$emit(\'size-change\', 20); $emit(\'current-change\', 3); $emit(\'update:currentPage\', 3); $emit(\'update:pageSize\', 20)" />',
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  getMock.mockResolvedValue({
    data: [
      { id: 'military', name: '专项政策' },
      { id: 'local', name: '地方政策' },
    ],
  })
  apiRequestMock.mockResolvedValue({
    data: { items: rows, total: 2 },
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与数据加载', () => {
  it('onMounted 加载分类与列表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(getMock).toHaveBeenCalledWith('/policies/categories')
    expect(vm.categoryOptions).toHaveLength(2)
    expect(apiRequestMock).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'GET', url: '/policies' })
    )
    expect(vm.tableData).toHaveLength(2)
    expect(vm.pagination.total).toBe(2)
    expect(vm.tableData[0]).toEqual({
      id: '1',
      title: '政策A',
      snippet: '',
      category: 'military',
      categoryName: '专项政策',
      department: '军委',
      publishDate: '2024-01-01',
      status: 'active',
      createTime: '2024-01-02',
      updateTime: '',
    })
    expect(vm.tableData[1].department).toBe('省政府')
    expect(vm.tableData[1].publishDate).toBe('')
  })

  it('loadCategories 对象配置格式', async () => {
    getMock.mockResolvedValue({
      data: { military: { label: '专项' }, local: {} },
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).categoryOptions).toEqual([
      { id: 'military', name: '专项' },
      { id: 'local', name: 'local' },
    ])
  })

  it('loadCategories 直返数组格式', async () => {
    getMock.mockResolvedValue([{ id: 'military', name: '专项' }])
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).categoryOptions).toEqual([{ id: 'military', name: '专项' }])
  })

  it('loadCategories data 为 null → 空列表', async () => {
    getMock.mockResolvedValue({ data: null })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).categoryOptions).toEqual([])
  })

  it('loadCategories 失败 → logger', async () => {
    getMock.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
  })

  it('loadData 失败 → 错误提示', async () => {
    apiRequestMock.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('加载政策数据失败')
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('loadData 直返数组格式', async () => {
    apiRequestMock.mockResolvedValue({ data: rows })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).tableData).toHaveLength(2)
    expect((wrapper.vm as any).pagination.total).toBe(2)
  })

  it('loadData res 无 data 直返数组', async () => {
    apiRequestMock.mockResolvedValue(rows)
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).tableData).toHaveLength(2)
  })

  it('loadData 空对象 → 空列表', async () => {
    apiRequestMock.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).tableData).toEqual([])
    expect((wrapper.vm as any).pagination.total).toBe(0)
  })

  it('部门与发布单位均缺失 → || 兜底', async () => {
    apiRequestMock.mockResolvedValue({
      data: { items: [{ id: '3', title: 'C', category: 'military', status: 'draft' }], total: 1 },
    })
    const wrapper = mountComp()
    await flushPromises()
    const row = (wrapper.vm as any).tableData[0]
    expect(row.department).toBe('')
    expect(row.publishDate).toBe('')
  })
})

describe('搜索/重置/分页', () => {
  it('handleSearch 回第 1 页', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.pagination.currentPage = 5
    apiRequestMock.mockClear()
    vm.handleSearch()
    await flushPromises()
    expect(vm.pagination.currentPage).toBe(1)
    expect(apiRequestMock).toHaveBeenCalled()
  })

  it('handleReset 清空筛选', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchForm.title = 't'
    vm.searchForm.category = 'c'
    vm.searchForm.department = 'd'
    vm.searchForm.publishDate = ['x', 'y']
    vm.searchForm.status = 's'
    vm.searchForm.keyword = 'k'
    vm.handleReset()
    expect(vm.searchForm).toEqual({
      title: '',
      category: '',
      department: '',
      publishDate: [],
      status: '',
      keyword: '',
    })
    expect(vm.pagination.currentPage).toBe(1)
  })

  it('搜索参数组装（FTS 契约：q + 分页）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchForm.title = '标题'
    vm.searchForm.department = '部门'
    vm.searchForm.keyword = '关键词'
    vm.searchForm.category = 'military'
    vm.searchForm.status = 'active'
    apiRequestMock.mockClear()
    await vm.loadData()
    // W7-023 政策 FTS 检索：统一走 /policies/search，q 为多字段拼接
    expect(apiRequestMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'GET',
        url: '/policies/search',
        params: expect.objectContaining({
          q: '标题 部门 关键词',
          limit: 10,
          offset: 0,
        }),
      })
    )
  })

  it('handleSizeChange/handleCurrentChange', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    apiRequestMock.mockClear()
    vm.handleSizeChange(50)
    await flushPromises()
    expect(vm.pagination.pageSize).toBe(50)
    expect(vm.pagination.currentPage).toBe(1)
    expect(apiRequestMock).toHaveBeenCalled()

    apiRequestMock.mockClear()
    vm.handleCurrentChange(3)
    await flushPromises()
    expect(vm.pagination.currentPage).toBe(3)
    expect(apiRequestMock).toHaveBeenCalled()
  })

  it('搜索/重置按钮 + 分页事件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    apiRequestMock.mockClear()
    const search = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('搜索'))
    await search!.trigger('click')
    await flushPromises()
    expect(apiRequestMock).toHaveBeenCalled()

    apiRequestMock.mockClear()
    const reset = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('重置'))
    await reset!.trigger('click')
    await flushPromises()
    expect(apiRequestMock).toHaveBeenCalled()

    apiRequestMock.mockClear()
    await wrapper.find('.el-pagination-stub').trigger('click')
    await flushPromises()
    expect(vm.pagination.pageSize).toBe(20)
    expect(vm.pagination.currentPage).toBe(3)
  })

  it('筛选表单 v-model 更新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    for (const el of wrapper.findAll('.el-input-stub')) {
      await el.trigger('click')
    }
    for (const sel of wrapper.findAll('.el-select-stub')) {
      await sel.trigger('click')
    }
    await wrapper.find('.el-date-picker-stub').trigger('click')
    await flushPromises()
    expect(vm.searchForm.title).toBe('V')
    expect(vm.searchForm.department).toBe('V')
    expect(vm.searchForm.keyword).toBe('V')
    expect(vm.searchForm.category).toBe('x')
    expect(vm.searchForm.status).toBe('x')
    expect(vm.searchForm.publishDate).toEqual(['a', 'b'])
  })
})

describe('表格交互', () => {
  it('handleViewDetail → pushSafe', async () => {
    const wrapper = mountComp()
    await flushPromises()
    ;(wrapper.vm as any).handleViewDetail('9')
    expect(pushSafeMock).toHaveBeenCalledWith('/policies/9')
  })

  it('handleSelectionChange', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleSelectionChange(rows)
    expect(vm.selectedRows).toHaveLength(2)
  })

  it('标题链接与查看详情按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    pushSafeMock.mockClear()
    const link = wrapper.find('.el-link-stub')
    await link.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/policies/1')

    pushSafeMock.mockClear()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('查看详情'))
    await btn!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/policies/1')
  })

  it('表格 selection-change 事件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.find('.el-table-stub').trigger('click')
    expect((wrapper.vm as any).selectedRows.length).toBeGreaterThan(0)
  })

  it('状态标签两种渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('启用')
    expect(wrapper.text()).toContain('禁用')
  })
})
