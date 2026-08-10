/**
 * views/help/HelpCenter.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：分类/文章/系统信息加载成败、selectCategory/backToList/doSearch/clearSearch 全流程、
 * viewArticle（无 id 早退/成功/失败）、highlightKeyword 全分支、sanitizedContent 两侧、
 * 搜索区/正文区/详情区/系统信息区模板显隐、分页显隐与翻页、表格 row-click、空态占位。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const {
  ElMessage,
  mockGetCategories,
  mockGetArticles,
  mockGetArticle,
  mockSearch,
  mockGetSystemInfo,
  mockSanitize,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockGetCategories: vi.fn(),
  mockGetArticles: vi.fn(),
  mockGetArticle: vi.fn(),
  mockSearch: vi.fn(),
  mockGetSystemInfo: vi.fn(),
  mockSanitize: vi.fn((s: any) => (typeof s === 'string' ? s : '')),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/help', () => ({
  helpApi: {
    getCategories: mockGetCategories,
    getArticles: mockGetArticles,
    getArticle: mockGetArticle,
    search: mockSearch,
    getSystemInfo: mockGetSystemInfo,
  },
}))

vi.mock('@/utils/sanitize', () => ({ sanitizeHtml: mockSanitize }))

import HelpCenter from '@/views/help/HelpCenter.vue'

const categories = [
  { key: 'guide', name: '使用指南', count: 5 },
  { key: 'faq', name: '常见问题', count: 3 },
]

const articleRows = [
  { id: 1, title: '如何导入数据', category: '使用指南', tags: ['导入', '数据'], summary: '导入步骤' },
  { id: 2, title: '常见问题解答', category: 'FAQ', tags: [], summary: 'FAQ' },
  { id: 3, title: '无标签文章', category: '', tags: undefined, summary: '' },
]

const systemInfo = {
  name: '帮扶系统',
  short_name: '帮扶',
  version: '1.5.0',
  description: '测试',
  features: ['AI', '导入'],
  contact: { technical_support: '010-000', feedback: 'feedback@x.com' },
}

const stubs = {
  'el-button': {
    name: 'ElButton',
    props: ['disabled', 'loading'],
    template: '<button class="el-button-stub" :disabled="disabled"><slot /></button>',
  },
  'el-card': {
    name: 'ElCard',
    template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
  },
  'el-input': {
    name: 'ElInput',
    props: ['modelValue'],
    template: '<div class="el-input-stub"><slot /><slot name="append" /></div>',
    emits: ['update:modelValue', 'change'],
  },
  'el-table': {
    name: 'ElTable',
    template: '<div class="el-table-stub"><slot /></div>',
    emits: ['row-click', 'current-change'],
  },
  'el-table-column': {
    name: 'ElTableColumn',
    template:
      '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>',
    data() {
      return { rowA: articleRows[0], rowB: articleRows[1], rowC: articleRows[2] }
    },
  },
  'el-pagination': {
    name: 'ElPagination',
    props: ['total', 'pageSize', 'currentPage'],
    emits: ['current-change', 'update:currentPage'],
    template: '<div class="el-pagination-stub" />',
  },
  'el-empty': {
    name: 'ElEmpty',
    props: ['description', 'imageSize'],
    template: '<div class="el-empty-stub">{{ description }}</div>',
  },
  'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
  'el-descriptions': {
    name: 'ElDescriptions',
    template: '<dl class="el-descriptions-stub"><slot /></dl>',
  },
  'el-descriptions-item': {
    name: 'ElDescriptionsItem',
    template: '<div class="el-desc-item-stub"><slot /></div>',
  },
  'el-link': { name: 'ElLink', template: '<span class="el-link-stub"><slot /></span>' },
}

function mountComp() {
  return mount(HelpCenter, {
    global: { renderStubDefaultSlot: true, stubs },
  })
}

const findBtn = (wrapper: any, text: string) => {
  const btn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().trim().includes(text))
  expect(btn, `按钮「${text}」`).toBeTruthy()
  return btn!
}

beforeEach(() => {
  vi.resetAllMocks()
  mockSanitize.mockImplementation((s: any) => (typeof s === 'string' ? s : ''))
  mockGetCategories.mockResolvedValue({ data: { categories } })
  mockGetArticles.mockResolvedValue({ data: { items: articleRows, total: 3 } })
  mockGetArticle.mockResolvedValue({
    data: { id: 1, title: '如何导入数据', category: '使用指南', content: '<p>正文内容</p>', tags: ['导入'] },
  })
  mockSearch.mockResolvedValue({ data: { items: [{ id: 9, title: '命中', snippet: '搜索片段', category: 'guide' }], total: 1 } })
  mockGetSystemInfo.mockResolvedValue({ data: systemInfo })
})

describe('挂载加载', () => {
  it('onMounted 加载分类/文章/系统信息并渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGetCategories).toHaveBeenCalled()
    expect(mockGetArticles).toHaveBeenCalledWith({ page: 1, page_size: 20 })
    expect(mockGetSystemInfo).toHaveBeenCalled()
    expect(vm.categories).toHaveLength(2)
    expect(vm.articles).toHaveLength(3)
    expect(vm.articlesTotal).toBe(3)
    expect(vm.systemInfo).toEqual(systemInfo)
    expect(vm.activeCategoryName).toBe('') // 未选择 → 兜底
    const text = wrapper.text()
    expect(text).toContain('帮助中心')
    expect(text).toContain('使用指南')
    expect(text).toContain('常见问题')
    expect(text).toContain('如何导入数据')
    expect(text).toContain('导入') // tags 渲染
    expect(text).toContain('帮扶系统')
    expect(text).toContain('1.5.0')
    expect(text).toContain('010-000')
    expect(text).toContain('feedback@x.com')
    expect(text).toContain('AI')
    expect(wrapper.find('.el-pagination-stub').exists()).toBe(false) // total<=pageSize
  })

  it('空态：分类/文章为空 → el-empty 占位；分页在 total>pageSize 时显示并翻页', async () => {
    mockGetCategories.mockResolvedValueOnce({ data: {} }) // res.data?.categories || [] 兜底
    mockGetArticles.mockResolvedValueOnce({ data: {} }) // res.data?.items || [] / total || 0 兜底
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(wrapper.find('.el-empty-stub').text()).toContain('暂无分类')
    expect(wrapper.text()).toContain('暂无文档')
    expect(vm.articles).toEqual([])
    expect(vm.articlesTotal).toBe(0)

    mockGetArticles.mockResolvedValueOnce({ data: { items: articleRows, total: 25 } })
    vm.articlesTotal = 25
    await nextTick()
    const pagination = wrapper.findComponent({ name: 'ElPagination' })
    expect(pagination.exists()).toBe(true)
    const before = mockGetArticles.mock.calls.length
    pagination.vm.$emit('update:currentPage', 2)
    pagination.vm.$emit('current-change', 2)
    await flushPromises()
    expect(mockGetArticles.mock.calls.length).toBe(before + 1)
    expect(vm.currentPage).toBe(2)
  })

  it('分类加载失败 → 提示「加载分类列表失败」；文章加载失败 → 提示', async () => {
    mockGetCategories.mockRejectedValueOnce(new Error('net'))
    mockGetArticles.mockRejectedValueOnce(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('加载分类列表失败')
    expect(ElMessage.error).toHaveBeenCalledWith('加载文档列表失败')
    expect((wrapper.vm as any).articles).toEqual([])
  })

  it('系统信息无 contact → contact 可选链空侧；失败静默', async () => {
    mockGetSystemInfo.mockResolvedValueOnce({ data: { name: 'x', short_name: 'x', version: '1', description: 'd', features: [] } })
    let wrapper = mountComp()
    await flushPromises()
    expect(wrapper.find('.system-info-card').exists()).toBe(true)

    mockGetSystemInfo.mockRejectedValueOnce(new Error('x'))
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).systemInfo).toBeNull()
    expect(ElMessage.error).not.toHaveBeenCalled()

    mockGetSystemInfo.mockResolvedValueOnce({ data: undefined }) // res.data || null 兜底
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).systemInfo).toBeNull()
  })

  it('详情视图下无文章详情 → 「文档加载失败」占位', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.viewMode = 'detail'
    vm.articleDetail = null
    await nextTick()
    expect(wrapper.find('.el-empty-stub').text()).toContain('文档加载失败')
  })
})

describe('分类选择与列表', () => {
  it('点击分类 → selectCategory：activeCategory/currentPage/viewMode 复位并带参数加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const catItem = wrapper.findAll('.category-item').find((c: any) => c.text().includes('使用指南'))
    await catItem.trigger('click')
    await flushPromises()
    expect(vm.activeCategory).toBe('guide')
    expect(vm.activeCategoryName).toBe('使用指南')
    expect(vm.currentPage).toBe(1)
    expect(vm.viewMode).toBe('list')
    expect(mockGetArticles).toHaveBeenLastCalledWith({ page: 1, page_size: 20, category: 'guide' })
  })

  it('表格 row-click 触发 viewArticle（有 id）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const table = wrapper.findComponent({ name: 'ElTable' })
    table.vm.$emit('row-click', articleRows[0])
    await flushPromises()
    expect(mockGetArticle).toHaveBeenCalledWith(1)
    expect(vm.viewMode).toBe('detail')
    expect(vm.articleDetail.title).toBe('如何导入数据')
    await nextTick()
    expect(wrapper.text()).toContain('正文内容') // sanitizedContent 渲染
  })

  it('viewArticle：无 id 早退；文章无内容 → (无内容)；失败 → 提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.viewArticle({})
    expect(mockGetArticle).not.toHaveBeenCalled()

    mockGetArticle.mockResolvedValueOnce({ data: { id: 2, title: '无内容', category: 'FAQ', content: '', tags: [] } })
    await vm.viewArticle({ id: 2 })
    expect(vm.viewMode).toBe('detail')
    await nextTick()
    expect(wrapper.text()).toContain('(无内容)')

    mockGetArticle.mockRejectedValueOnce(new Error('x'))
    await vm.viewArticle({ id: 3 })
    expect(ElMessage.error).toHaveBeenCalledWith('加载文档详情失败')

    mockGetArticle.mockResolvedValueOnce({ data: undefined }) // res.data || null 兜底
    await vm.viewArticle({ id: 4 })
    expect(vm.articleDetail).toBeNull()
    expect(vm.viewMode).toBe('detail')
  })

  it('返回列表按钮 → backToList 复位视图', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.articleDetail = { id: 1, title: 't', category: 'c', content: 'x', tags: [] }
    vm.viewMode = 'detail'
    await nextTick()
    await findBtn(wrapper, '返回列表').trigger('click')
    expect(vm.viewMode).toBe('list')
    expect(vm.articleDetail).toBeNull()
  })
})

describe('搜索', () => {
  it('doSearch：空查询重置结果', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchQuery = '   '
    await vm.doSearch()
    expect(vm.searchResults).toEqual([])
    expect(vm.searchTotal).toBe(0)
    expect(mockSearch).not.toHaveBeenCalled()
  })

  it('搜索成功：命中项渲染搜索区（含高亮）、total>0 无空占位；点击结果项打开文章', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchQuery = '命中'
    await findBtn(wrapper, '搜索').trigger('click')
    await flushPromises()
    expect(mockSearch).toHaveBeenCalledWith('命中', 20)
    expect(vm.searchResults).toHaveLength(1)
    expect(vm.searching).toBe(false)
    await nextTick()
    const text = wrapper.text()
    expect(text).toContain('搜索结果 (1 条)')
    expect(text).toContain('搜索片段')
    expect(wrapper.find('.help-body').exists()).toBe(false) // searchQuery 且结果非空 → 正文区隐藏
    expect(wrapper.find('.search-results-section').exists()).toBe(true)

    // 搜索结果项 @click → viewArticle
    await wrapper.find('.search-result-item').trigger('click')
    await flushPromises()
    expect(mockGetArticle).toHaveBeenCalledWith(9)
    expect(vm.viewMode).toBe('detail')
  })

  it('响应无 items/total → 搜索结果显示兜底空数组', async () => {
    mockSearch.mockResolvedValueOnce({ data: {} }) // items || [] 兜底
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchQuery = 'x'
    await vm.doSearch()
    expect(vm.searchResults).toEqual([])
    expect(vm.searchTotal).toBe(0)
  })

  it('items 命中但 total=0 → 「未找到相关文档」空态', async () => {
    mockSearch.mockResolvedValueOnce({ data: { items: [{ id: 8, title: 't', snippet: 's', category: 'c' }], total: 0 } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchQuery = 'x'
    await vm.doSearch()
    await nextTick()
    expect(wrapper.find('.el-empty-stub').text()).toContain('未找到相关文档')
  })

  it('搜索失败 → 「搜索失败」；「清除」按钮清空查询', async () => {
    mockSearch.mockRejectedValueOnce(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.searchQuery = 'a'
    await vm.doSearch()
    expect(ElMessage.error).toHaveBeenCalledWith('搜索失败')

    vm.searchQuery = 'a'
    vm.searchResults = [{ id: 1, title: 't', snippet: 's', category: 'c' }]
    vm.searchTotal = 1
    await nextTick()
    await findBtn(wrapper, '清除').trigger('click')
    expect(vm.searchQuery).toBe('')
    expect(vm.searchResults).toEqual([])
    expect(vm.searchTotal).toBe(0)
    await nextTick()
    expect(wrapper.find('.help-body').exists()).toBe(true)
  })

  it('搜索输入 v-model 同步', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    wrapper.findComponent({ name: 'ElInput' }).vm.$emit('update:modelValue', '查询词')
    expect(vm.searchQuery).toBe('查询词')
  })
})

describe('工具函数', () => {
  it('highlightKeyword：无查询 → 仅 sanitize；有查询 → 转义替换；snippet 空兜底', () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.searchQuery = ''
    expect(vm.highlightKeyword('<b>片段</b>')).toContain('<b>片段</b>')
    expect(vm.highlightKeyword('')).toBe('')
    vm.searchQuery = '导入'
    const out = vm.highlightKeyword('如何导入数据')
    expect(out).toContain('<span style="background:#fff3cd')
    expect(out).toContain('导入')
    expect(vm.highlightKeyword('')).toBe('') // 有查询 + snippet 空 → sanitize('') 兜底
    vm.searchQuery = 'a.b' // 正则特殊字符转义
    expect(vm.highlightKeyword('x a.b y')).toContain('a.b')
  })
})

describe('文章解析补充', () => {
  it('parseArticleSections 全分支；sanitizedContent 空内容', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 空内容 → []
    expect(vm.parseArticleSections('')).toEqual([])
    // 标题+正文 / 独立行 / 标题后同行内容
    const out = vm.parseArticleSections('【一】标题\n正文1\n正文2\n无标题行')
    expect(out.length).toBe(1)
    expect(out[0].heading).toBe('一')
    expect(out[0].lines).toEqual(['标题', '正文1', '正文2', '无标题行'])
    // 【二】标题带同行内容
    const out2 = vm.parseArticleSections('【二】标题 同段内容')
    expect(out2[0].heading).toBe('二')
    expect(out2[0].lines).toContain('标题 同段内容')
    // sanitizedContent 空 → 占位
    vm.articleDetail = { content: '' }
    expect(vm.sanitizedContent).toBe('(无内容)')
    wrapper.unmount()
  })
})

describe('解析边界补充', () => {
  it('parseArticleSections 空行跳过/无内容占位', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const parsed = vm.parseArticleSections('【标题】\n\n正文')
    expect(parsed[0].heading).toBe('标题')
    vm.articleDetail = { content: '' }
    await wrapper.vm.$nextTick()
    expect(vm.sanitizedContent).toBe('(无内容)')
    wrapper.unmount()
  })
  it('无 heading 的 section 渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.articleDetail = { content: '无标题段落' }
    await wrapper.vm.$nextTick()
    const headings = wrapper.findAll('.article-section-title')
    expect(headings.length).toBe(0)
    wrapper.unmount()
  })
})

describe('内容渲染分支', () => {
  it('sanitizedContent 有值 / 有 heading section 渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.articleDetail = { content: '【说明】一些内容' }
    await flushPromises()
    await wrapper.vm.$nextTick()
    expect(wrapper.html()).toContain('说明')
    wrapper.unmount()
  })
})

describe('空白与目录渲染', () => {
  it('空白内容 → sanitizedContent 渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.articleDetail = { content: '   ' }
    await flushPromises()
    expect((wrapper.vm as any).sanitizedContent).toBe('   ')
    wrapper.unmount()
  })
  it('多 section → 目录 + 标题渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.articleDetail = { content: '【一】甲\n【二】乙' }
    await flushPromises()
    expect((wrapper.vm as any).articleSections.length).toBeGreaterThan(1)
    wrapper.unmount()
  })
})

describe('标题元素渲染', () => {
  it('有 heading 的 section → h3 渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.articleDetail = { content: '【说明】内容' }
    vm.viewMode = 'detail'
    await flushPromises()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('h3.article-section-title').exists()).toBe(true)
    wrapper.unmount()
  })
})
