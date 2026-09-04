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

/**
 * FTS5 检索路径（loadData 里 `if (searchStr)` 分支）的响应解包链：
 *   const fdata  = ftsRes.data || ftsRes
 *   const fitems = fdata.items || (Array.isArray(fdata) ? fdata : [])
 *   pagination.total = fdata.total || fitems.length
 * 上方用例只走了 `{data:{items,total}}` 一种形态，三行的 `||` 兜底侧均未触达。
 *
 * 注（任务#28 死代码5）：这三行原先写作 `fdata?.items` / `fdata?.total`，其 `?.`
 * 的 nullish 短路侧经证明不可达：fdata 恒非 nullish——ftsRes 为 null/undefined 时上一行
 * `ftsRes.data` 已抛 TypeError 并被外层 catch 接住；ftsRes 为 ''/0/false 等假值时
 * `|| ftsRes` 得到的仍是该假值本身（假 ≠ nullish，且原始值取属性会自动装箱、不抛错）。
 * 因此已删除该死防御，本 describe 无需（也无法）为其编写注入用例；
 * 下面覆盖的是三处 `||` 的真实兜底侧。下方结构化列表路径（`res.data || res`）同理。
 *
 * 驱动方式：先挂载（onMounted 走结构化列表），再置 searchForm.keyword
 * 使 searchStr 非空，重调 loadData 进入 FTS 分支。
 */
describe('FTS 检索响应解包兜底', () => {
  /** 挂载 + 置关键词，返回 vm（已等 onMounted 首次加载完成） */
  async function mountFts() {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchForm.keyword = '帮扶'
    apiRequestMock.mockClear()
    return { wrapper, vm }
  }

  it('ftsRes 无 data 包装 → `|| ftsRes` 右侧生效，直接使用裸 body', async () => {
    apiRequestMock.mockResolvedValue({
      items: [{ id: '9', title: 'FTS 政策', snippet: '前<mark>命中</mark>后' }],
      total: 1,
    })
    const { vm } = await mountFts()
    await vm.loadData()

    expect(apiRequestMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'GET',
        url: '/policies/search',
        params: { q: '帮扶', limit: 10, offset: 0 },
      })
    )
    expect(vm.tableData).toHaveLength(1)
    expect(vm.tableData[0]).toEqual({
      id: '9',
      title: 'FTS 政策',
      snippet: '前<mark>命中</mark>后',
      categoryName: '',
      department: '',
      publishDate: '',
      status: '',
    })
    expect(vm.pagination.total).toBe(1)
    expect(vm.loading).toBe(false)
  })

  it('ftsRes 直返数组 → items 缺席时走 Array.isArray 真侧', async () => {
    apiRequestMock.mockResolvedValue([
      { id: '1', title: 'A', snippet: '' },
      { id: '2', title: 'B' },
    ])
    const { vm } = await mountFts()
    await vm.loadData()

    expect(vm.tableData).toHaveLength(2)
    // total 缺席 → 回退 fitems.length
    expect(vm.pagination.total).toBe(2)
    // item.snippet 缺失 → `|| ''` 兜底为空串（表格渲染“—”占位）
    expect(vm.tableData[1].snippet).toBe('')
  })

  it('ftsRes 既无 items 又非数组 → 空列表 + total 回退 0', async () => {
    // 后端异常负载（如 {detail:'...'}）不能让表格抛错
    apiRequestMock.mockResolvedValue({ data: { detail: 'Internal Error' } })
    const { vm } = await mountFts()
    await vm.loadData()

    expect(vm.tableData).toEqual([])
    expect(vm.pagination.total).toBe(0)
    expect(vm.loading).toBe(false)
  })

  it('total=0 但 items 非空 → `||` 把 0 视为假，回退 items.length', async () => {
    // 记录当前契约：FTS 未回 total 时前端以本页条数充数（分页器会偏小）
    apiRequestMock.mockResolvedValue({
      data: { items: [{ id: '1', title: 'A', snippet: '' }], total: 0 },
    })
    const { vm } = await mountFts()
    await vm.loadData()
    expect(vm.tableData).toHaveLength(1)
    expect(vm.pagination.total).toBe(1)
  })

  it('data 为 null → fdata 回退 ftsRes 本体，再走非数组兜底', async () => {
    apiRequestMock.mockResolvedValue({ data: null })
    const { vm } = await mountFts()
    await vm.loadData()
    expect(vm.tableData).toEqual([])
    expect(vm.pagination.total).toBe(0)
  })

  it('offset 随页码推算；FTS 失败 → 错误提示 + loading 释放', async () => {
    apiRequestMock.mockResolvedValue({ data: { items: [], total: 0 } })
    const { vm } = await mountFts()
    vm.pagination.currentPage = 3
    vm.pagination.pageSize = 20
    await vm.loadData()
    expect(apiRequestMock).toHaveBeenCalledWith(
      expect.objectContaining({ params: { q: '帮扶', limit: 20, offset: 40 } })
    )

    apiRequestMock.mockRejectedValue(new Error('fts down'))
    await vm.loadData()
    expect(ElMessage.error).toHaveBeenCalledWith('加载政策数据失败')
    expect(vm.loading).toBe(false)
  })

  it('sanitizeSnippet 只还原 <mark>，其余尖括号保持转义（防 XSS）', async () => {
    apiRequestMock.mockResolvedValue({
      data: {
        items: [
          {
            id: '1',
            title: 'X',
            // 后端 FTS 高亮片段里混入敌意标签，只能 <mark> 被放行
            snippet: '<mark>安全</mark><script>alert(1)</script><img src=x onerror=alert(2)>',
          },
        ],
        total: 1,
      },
    })
    const { vm } = await mountFts()
    await vm.loadData()
    const snippet = vm.tableData[0].snippet as string
    expect(snippet).toContain('<mark>安全</mark>')
    expect(snippet).toContain('&lt;script&gt;')
    expect(snippet).not.toContain('<script>')
    expect(snippet).not.toContain('<img')
    // onerror 载荷仍以转义文本形式保留（仅不可执行，不丢字）
    expect(snippet).toContain('onerror=alert(2)')
  })
})

/**
 * 命中摘要列渲染（splitSnippet）。
 *
 * 上方 mountComp 的 el-table-column 桩固定回传 rows[0]/rows[1]（无 snippet 字段），
 * 因此模板里 `v-if="scope.row.snippet"` 永远为假，splitSnippet 从未被调用
 * （函数缺口 + stmts@107-111 + branch@106）。
 * 这里用能提供带 snippet 行的桩重新挂载（VTU 局部 stubs 会覆盖 setup.ts 全局桩）。
 */
const snippetRows = [
  // 中间多处高亮：前缀/中段/后缀 三类分段均出现
  { id: '1', title: 'T1', snippet: '前缀<mark>命中</mark>中间<mark>再命中</mark>后缀', status: 'active' },
  // 空摘要 → v-else 渲染“—”
  { id: '2', title: 'T2', snippet: '', status: 'invalid' },
  // 无任何标记的纯文本 → segs 为空走末位兜底
  { id: '3', title: 'T3', snippet: '无标记纯文本', status: 'active' },
  // 整段高亮（m.index === 0 且 last === s.length）→ 无前后缀分段
  { id: '4', title: 'T4', snippet: '<mark>整段高亮</mark>', status: 'active' },
]

function mountWithSnippets() {
  return mount(Search, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>' },
        'el-table': {
          template: '<div class="el-table-stub"><slot name="default" /></div>',
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot v-for="(r, i) in stubRows" :key="i" :row="r" /></div>',
          data() {
            return { stubRows: snippetRows }
          },
        },
        'el-link': { template: '<a class="el-link-stub"><slot /></a>' },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-button': { template: '<button class="el-button-stub"><slot /></button>' },
      },
    },
  })
}

describe('splitSnippet 与命中摘要列渲染', () => {
  it('模板渲染：有摘要行拆段并用 <mark> 包裹，无摘要行回退—', async () => {
    const wrapper = mountWithSnippets()
    await flushPromises()

    const snippetBlocks = wrapper.findAll('.fts-snippet')
    // 4 行中 3 行有非空 snippet
    expect(snippetBlocks).toHaveLength(3)
    expect(wrapper.text()).toContain('—')

    // 多处高亮：2 个 <mark> + 3 段普通文本
    expect(snippetBlocks[0].findAll('mark')).toHaveLength(2)
    expect(snippetBlocks[0].findAll('mark')[0].text()).toBe('命中')
    expect(snippetBlocks[0].findAll('mark')[1].text()).toBe('再命中')
    expect(snippetBlocks[0].text()).toBe('前缀命中中间再命中后缀')

    // 无标记纯文本：不产生 <mark>，但文本完整保留
    expect(snippetBlocks[1].findAll('mark')).toHaveLength(0)
    expect(snippetBlocks[1].text()).toBe('无标记纯文本')

    // 整段高亮：只有1 个 <mark>，无前后缀
    expect(snippetBlocks[2].findAll('mark')).toHaveLength(1)
    expect(snippetBlocks[2].text()).toBe('整段高亮')

    // 安全护栏：模板按段插值（无 v-html），敌意标签不会被当 HTML 解析
    expect(wrapper.html()).not.toContain('<script>')
    wrapper.unmount()
  })

  it('splitSnippet 单测：多段/首尾高亮/无高亮/空串', async () => {
    const wrapper = mountWithSnippets()
    await flushPromises()
    const vm = wrapper.vm as any

    // 前缀 + 高亮 + 中段 + 高亮 + 后缀
    expect(vm.splitSnippet('a<mark>b</mark>c<mark>d</mark>e')).toEqual([
      { text: 'a', mark: false },
      { text: 'b', mark: true },
      { text: 'c', mark: false },
      { text: 'd', mark: true },
      { text: 'e', mark: false },
    ])

    // 首字符即高亮 → m.index === 0，不推空前缀段
    expect(vm.splitSnippet('<mark>x</mark>tail')).toEqual([
      { text: 'x', mark: true },
      { text: 'tail', mark: false },
    ])

    // 末尾高亮 → last === s.length，不推空后缀段
    expect(vm.splitSnippet('head<mark>x</mark>')).toEqual([
      { text: 'head', mark: false },
      { text: 'x', mark: true },
    ])

    // 相邻两个高亮（中间无普通文本）
    expect(vm.splitSnippet('<mark>a</mark><mark>b</mark>')).toEqual([
      { text: 'a', mark: true },
      { text: 'b', mark: true },
    ])

    // 无标记 → segs 为空，走 `segs.length > 0 ? segs : [{text:s,mark:false}]` 兜底
    expect(vm.splitSnippet('纯文本')).toEqual([{ text: '纯文本', mark: false }])

    // 空串 → 同样兜底为单个空段（不能返回空数组让模板渲染空白）
    expect(vm.splitSnippet('')).toEqual([{ text: '', mark: false }])

    // 未闭合标记不匹配正则 → 当普通文本处理（不吐半截标签）
    expect(vm.splitSnippet('a<mark>b')).toEqual([{ text: 'a<mark>b', mark: false }])

    // 非贪婪匹配：不会把两个 mark 之间的文本当成高亮内容
    expect(vm.splitSnippet('<mark>a</mark>m<mark>b</mark>')[1]).toEqual({
      text: 'm',
      mark: false,
    })
    wrapper.unmount()
  })

  it('sanitizeSnippet 与 splitSnippet 串起来：敌意标签被转义后不会被当作 mark', async () => {
    const wrapper = mountWithSnippets()
    await flushPromises()
    const vm = wrapper.vm as any
    const safe = vm.sanitizeSnippet('<mark>ok</mark><b>bold</b>')
    expect(safe).toBe('<mark>ok</mark>&lt;b&gt;bold&lt;/b&gt;')
    const segs = vm.splitSnippet(safe)
    expect(segs).toEqual([
      { text: 'ok', mark: true },
      { text: '&lt;b&gt;bold&lt;/b&gt;', mark: false },
    ])
    wrapper.unmount()
  })
})
