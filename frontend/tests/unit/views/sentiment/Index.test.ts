/**
 * views/sentiment/Index.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 四路加载、loadStats 三种响应形状与失败、loadKeywords/loadAlerts/loadNews
 * 各数据形态与静默失败、handleCollect 定时刷新（fake timers）、handleAnalyze 成功/失败、
 * 工具函数全分支（formatDate/sentimentLabel/sentimentTagType/tagFontSize/tagType）、
 * 统计卡加载态、热词云/预警列表/新闻表模板渲染。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const {
  ElMessage,
  mockCollectNews,
  mockAnalyzeNews,
  mockGetNews,
  mockGetStatistics,
  mockGetHotKeywords,
  mockGetAlerts,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockCollectNews: vi.fn(),
  mockAnalyzeNews: vi.fn(),
  mockGetNews: vi.fn(),
  mockGetStatistics: vi.fn(),
  mockGetHotKeywords: vi.fn(),
  mockGetAlerts: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/sentiment', () => ({
  collectNews: mockCollectNews,
  analyzeNews: mockAnalyzeNews,
  getNews: mockGetNews,
  getStatistics: mockGetStatistics,
  getHotKeywords: mockGetHotKeywords,
  getAlerts: mockGetAlerts,
}))

import SentimentIndex from '@/views/sentiment/Index.vue'

const newsRows = [
  { title: '新闻A', sentiment_label: 'positive', source: '新华社', published_at: '2024-06-01T10:00:00', is_alert: true },
  { title: '新闻B', sentiment_label: '', source: '', created_at: '2024-06-02T10:00:00', is_alert: false },
  { title: '新闻C', sentiment_label: 'negative', source: 'x', is_alert: false },
]

const alertsData = [
  { id: 1, sentiment_label: 'negative', source: '', title: '预警一', published_at: '2024-06-01T10:00:00' },
  { id: 2, sentiment_label: 'positive', source: '来源X', title: '预警二', created_at: '2024-06-03T10:00:00' },
  { id: 3, sentiment_label: '', source: '', title: '预警三' },
]

const keywordsData = [
  { word: '振兴', count: 30, sentiment: 'positive' },
  { word: '预警', count: 0, sentiment: 'negative' },
  { word: '中性词', count: 100, sentiment: 'neutral' },
  { word: '无情感', count: 5 }, // sentiment 缺省 → 'neutral' 兜底
]

const stubs = {
  'el-button': {
    name: 'ElButton',
    props: ['disabled', 'loading'],
    template: '<button class="el-button-stub" :disabled="disabled"><slot /></button>',
  },
  'el-select': {
    name: 'ElSelect',
    template: '<div class="el-select-stub"><slot /></div>',
    emits: ['update:modelValue', 'change'],
  },
  'el-table-column': {
    name: 'ElTableColumn',
    props: ['prop'],
    template:
      '<div class="el-table-column-stub"><span>{{ rowA[prop] }}</span><span>{{ rowB[prop] }}</span><span>{{ rowC[prop] }}</span><slot :row="rowA" :scope="{ row: rowA }" /><slot :row="rowB" :scope="{ row: rowB }" /><slot :row="rowC" :scope="{ row: rowC }" /></div>',
    data() {
      return { rowA: newsRows[0], rowB: newsRows[1], rowC: newsRows[2] }
    },
  },
  'el-tag': { name: 'ElTag', template: '<span class="el-tag-stub"><slot /></span>' },
  'el-empty': {
    name: 'ElEmpty',
    props: ['description', 'imageSize'],
    template: '<div class="el-empty-stub">{{ description }}</div>',
  },
  'el-icon': { name: 'ElIcon', template: '<span class="el-icon-stub"><slot /></span>' },
}

function mountComp() {
  return mount(SentimentIndex, {
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
  mockGetStatistics.mockResolvedValue({
    data: { positive_count: 5, negative_count: 2, neutral_count: 3, alert_count: 1, total_count: 10 },
  })
  mockGetHotKeywords.mockResolvedValue({ data: { items: keywordsData } })
  mockGetAlerts.mockResolvedValue({ data: { items: alertsData } })
  mockGetNews.mockResolvedValue({ data: { items: newsRows } })
  mockCollectNews.mockResolvedValue({})
  mockAnalyzeNews.mockResolvedValue({ data: { processed: 99 } })
})

describe('挂载与统计', () => {
  it('onMounted 加载四路数据并渲染统计卡/热词/预警/新闻', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockGetStatistics).toHaveBeenCalledWith(7)
    expect(mockGetHotKeywords).toHaveBeenCalledWith(7, 30)
    expect(mockGetAlerts).toHaveBeenCalledWith(7, 20)
    expect(mockGetNews).toHaveBeenCalledWith({ limit: 20 })
    expect(vm.stats).toMatchObject({ positive: 5, negative: 2, neutral: 3, alerts: 1, total: 10 })
    expect(vm.statLoading).toBe(false)
    expect(vm.statsError).toBe(false)
    const text = wrapper.text()
    expect(text).toContain('舆情监测')
    expect(text).toContain('振兴') // 热词云
    expect(text).toContain('预警一')
    expect(text).toContain('未知来源')
    expect(text).toContain('来源X')
    expect(text).toContain('2024-06-01') // 预警时间 published_at
    expect(text).toContain('2024-06-03') // 预警时间 created_at
    expect(text).toContain('新闻A')
    expect(text).toContain('正面') // sentimentLabel(positive)
    expect(text).toContain('负面')
    expect(text).toContain('2024-06-02') // 新闻表 created_at
  })

  it('loadStats：裸对象与空数据 → 0 兜底；null 响应跳过；失败 → statsError', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    mockGetStatistics.mockResolvedValueOnce({ positive: 1, negative: 2, neutral: 3, alerts: 4, total: 10 })
    await vm.loadStats()
    expect(vm.stats).toMatchObject({ positive: 1, negative: 2, neutral: 3, alerts: 4, total: 10 })

    mockGetStatistics.mockResolvedValueOnce({ data: {} })
    await vm.loadStats()
    expect(vm.stats).toMatchObject({ positive: 0, negative: 0, neutral: 0, alerts: 0, total: 0 })

    mockGetStatistics.mockResolvedValueOnce(null) // response?.data ?? response → null → if(data) 假侧
    await vm.loadStats()
    expect(vm.statsError).toBe(false)

    mockGetStatistics.mockRejectedValueOnce(new Error('net'))
    await vm.loadStats()
    expect(vm.statsError).toBe(true)
    expect(vm.statLoading).toBe(false)
    await nextTick()
    expect(wrapper.find('.error-hint').exists()).toBe(true)
    expect(wrapper.find('.stats-row').exists()).toBe(false)
  })

  it('统计卡加载态 → 显示 "-"', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.statLoading = true
    await nextTick()
    expect(wrapper.text()).toContain('-')
  })
})

describe('数据加载形态', () => {
  it('loadKeywords：items / keywords / 数组 / 缺省 [] / 失败静默', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    mockGetHotKeywords.mockResolvedValueOnce({ data: { keywords: keywordsData } })
    await vm.loadKeywords()
    expect(vm.keywords).toHaveLength(4)

    mockGetHotKeywords.mockResolvedValueOnce(keywordsData) // 裸数组（?data ?? response）
    await vm.loadKeywords()
    expect(vm.keywords).toHaveLength(4)

    mockGetHotKeywords.mockResolvedValueOnce({ data: {} })
    await vm.loadKeywords()
    expect(vm.keywords).toEqual([])

    mockGetHotKeywords.mockRejectedValueOnce(new Error('x'))
    await vm.loadKeywords()
    expect(vm.keywordsLoading).toBe(false)
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('loadAlerts：items / 数组 / 缺省 [] / 失败静默', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    mockGetAlerts.mockResolvedValueOnce(alertsData) // 裸数组
    await vm.loadAlerts()
    expect(vm.alerts).toHaveLength(3)

    mockGetAlerts.mockResolvedValueOnce({ data: {} })
    await vm.loadAlerts()
    expect(vm.alerts).toEqual([])

    mockGetAlerts.mockRejectedValueOnce(new Error('x'))
    await vm.loadAlerts()
    expect(vm.alertsLoading).toBe(false)
  })

  it('loadNews：筛选分支（空/alert/具体情感）+ 数据形态 + 失败静默', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    mockGetNews.mockResolvedValueOnce(newsRows) // 裸数组
    await vm.loadNews()
    expect(mockGetNews).toHaveBeenLastCalledWith({ limit: 20 })

    vm.newsFilter = 'alert'
    await vm.loadNews()
    expect(mockGetNews).toHaveBeenLastCalledWith({ limit: 20, is_alert: true })

    vm.newsFilter = 'positive'
    await vm.loadNews()
    expect(mockGetNews).toHaveBeenLastCalledWith({ limit: 20, sentiment_label: 'positive' })

    mockGetNews.mockResolvedValueOnce({ data: {} })
    vm.newsFilter = ''
    await vm.loadNews()
    expect(vm.newsList).toEqual([])

    mockGetNews.mockRejectedValueOnce(new Error('x'))
    await vm.loadNews()
    expect(vm.newsLoading).toBe(false)
  })
})

describe('操作按钮', () => {
  it('handleCollect：成功提示并在 2 秒后刷新统计与新闻；「采集新闻」按钮触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vi.useFakeTimers()
    try {
      await findBtn(wrapper, '采集新闻').trigger('click')
      await flushPromises()
      expect(mockCollectNews).toHaveBeenCalledWith({
        keywords: ['乡村振兴', '帮扶', '助学兴教'],
      })
      expect(ElMessage.success).toHaveBeenCalledWith('新闻采集已触发')
      const statsBefore = mockGetStatistics.mock.calls.length
      const newsBefore = mockGetNews.mock.calls.length
      await vi.advanceTimersByTimeAsync(2000)
      expect(mockGetStatistics.mock.calls.length).toBe(statsBefore + 1)
      expect(mockGetNews.mock.calls.length).toBe(newsBefore + 1)
      expect(vm.collecting).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })

  it('handleCollect 失败 → 「采集失败」', async () => {
    mockCollectNews.mockRejectedValueOnce(new Error('x'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleCollect()
    expect(ElMessage.error).toHaveBeenCalledWith('采集失败')
    expect(vm.collecting).toBe(false)
  })

  it('handleAnalyze：processed 数字与缺省 N/A；触发四路刷新；失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    await findBtn(wrapper, '分析情感').trigger('click')
    await flushPromises()
    expect(mockAnalyzeNews).toHaveBeenCalledWith(100)
    expect(ElMessage.success).toHaveBeenLastCalledWith('分析完成：处理 99 条')
    expect(vm.analyzing).toBe(false)

    mockAnalyzeNews.mockResolvedValueOnce({})
    await vm.handleAnalyze()
    expect(ElMessage.success).toHaveBeenLastCalledWith('分析完成：处理 N/A 条')

    mockAnalyzeNews.mockRejectedValueOnce(new Error('x'))
    await vm.handleAnalyze()
    expect(ElMessage.error).toHaveBeenCalledWith('分析失败')
    expect(vm.analyzing).toBe(false)
  })

  it('关键词天数与新闻筛选下拉 v-model + change 触发重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 30)
    selects[0].vm.$emit('change', 30)
    await flushPromises()
    expect(vm.keywordDays).toBe(30)
    expect(mockGetHotKeywords).toHaveBeenLastCalledWith(30, 30)

    selects[1].vm.$emit('update:modelValue', 'negative')
    selects[1].vm.$emit('change', 'negative')
    await flushPromises()
    expect(vm.newsFilter).toBe('negative')
    expect(mockGetNews).toHaveBeenLastCalledWith({ limit: 20, sentiment_label: 'negative' })
  })
})

describe('工具函数', () => {
  it('formatDate / sentimentLabel / sentimentTagType / tagFontSize / tagType 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatDate('')).toBe('-')
    expect(vm.formatDate(undefined)).toBe('-')
    expect(vm.formatDate('2024-06-01T10:00:00')).toBe('2024-06-01')

    expect(vm.sentimentLabel('positive')).toBe('正面')
    expect(vm.sentimentLabel('negative')).toBe('负面')
    expect(vm.sentimentLabel('neutral')).toBe('中性')
    expect(vm.sentimentLabel('other')).toBe('other') // 未知 → 透传
    expect(vm.sentimentLabel('')).toBe('-')

    expect(vm.sentimentTagType('positive')).toBe('success')
    expect(vm.sentimentTagType('negative')).toBe('danger')
    expect(vm.sentimentTagType('x')).toBe('info')

    expect(vm.tagFontSize(0)).toBe(12.16) // clamp 下界 → 1
    expect(vm.tagFontSize(30)).toBe(12 + (30 / 50) * 8)
    expect(vm.tagFontSize(100)).toBe(20) // clamp 上界 → 50

    expect(vm.tagType('positive')).toBe('success')
    expect(vm.tagType('negative')).toBe('danger')
    expect(vm.tagType('x')).toBe('info')
  })
})
