/**
 * views/dataVerify/Index.vue 测试（W22 数据校验合并页，唯一执行者）
 *
 * 覆盖：Tab 路由 query 同步与 watch、字段说明加载（成功/扁平/缺失/失败/加载中）、
 * 条件增删与运算符联动、一键校验（无条件/成功/空响应/null 响应/失败）、
 * 问题列表定位修复（含缺失 id）、CSV 导出（空/有数据/单元格转义）。
 * 页面内嵌 RulesPanel 以 vi.mock 桩掉（其真实执行者为 RulesPanel.test.ts）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'

const mocks = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  get: vi.fn(),
  post: vi.fn(),
  pushSafe: vi.fn(),
  replace: vi.fn(),
  route: { query: {} as Record<string, unknown> },
}))

vi.mock('element-plus', () => ({ ElMessage: mocks.ElMessage }))
vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mocks.get(...args),
  post: (...args: any[]) => mocks.post(...args),
}))
vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: mocks.pushSafe }),
}))
vi.mock('vue-router', async () => {
  // 真实 vue-router 的 route 是响应式的：用 reactive 包装以驱动组件内 watch
  const { reactive } = await import('vue')
  mocks.route = reactive({ query: {} as Record<string, unknown> })
  return {
    useRoute: () => mocks.route,
    useRouter: () => ({ replace: mocks.replace }),
  }
})
vi.mock('@/views/dataVerify/components/RulesPanel.vue', () => ({
  default: { name: 'RulesPanelStub', template: '<div class="rules-panel-stub" />' },
}))

import DataVerify from '@/views/dataVerify/Index.vue'

const FIELD_RESPONSE = {
  data: {
    module: 'village',
    fields: [
      { key: 'village_name', label: '帮扶村名称' },
      { key: 'population', label: '人口数' },
    ],
  },
}

function mountPage(): VueWrapper {
  return mount(DataVerify)
}

/** 读取当前激活的 tab 文本 */
function activeTabText(wrapper: VueWrapper): string {
  return wrapper.find('.dv-tab.is-active').text()
}

/** 写入第一个条件的字段/运算符（原生 select 可写入任意值以覆盖回退分支） */
async function setCondField(wrapper: VueWrapper, value: string): Promise<void> {
  const select = wrapper.findAll('.dv-field-select')[0]
  ;(select.element as HTMLSelectElement).value = value
  await select.trigger('change')
  await nextTick()
}

async function setCondOperator(wrapper: VueWrapper, value: string): Promise<void> {
  await wrapper.findAll('.dv-op-select')[0].setValue(value)
  await nextTick()
}

async function clickButton(wrapper: VueWrapper, text: string): Promise<void> {
  const btn = wrapper.findAll('button').find((b) => b.text().trim() === text)
  expect(btn, `按钮「${text}」`).toBeTruthy()
  await btn!.trigger('click')
  await flushPromises()
}

/** 触发一次成功校验（返回问题行样本） */
async function runSuccessfulCheck(wrapper: VueWrapper): Promise<void> {
  await setCondField(wrapper, 'village_name')
  mocks.post.mockResolvedValueOnce({
    data: {
      module: 'village',
      logic: 'and',
      total: 3,
      matched: 1,
      unmatched: 2,
      message: '共 3 条记录，满足条件 1 条，不满足 2 条',
      results: [
        { id: 1, matched: true, values: { village_name: '已填村' } },
        { id: 2, matched: false, values: { village_name: '' } },
        { id: null, values: {} },
      ],
    },
  })
  await clickButton(wrapper, '一键校验')
}

describe('views/dataVerify/Index.vue（数据校验合并页）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.query = {}
    mocks.get.mockResolvedValue(FIELD_RESPONSE)
    mocks.post.mockResolvedValue({ data: { results: [] } })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('默认展示「校验执行」并加载字段清单', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(activeTabText(wrapper)).toBe('校验执行')
    expect(mocks.get).toHaveBeenCalledWith('/validation/fields', { module: 'village' })
    // 条件行的字段下拉含后端返回的中文标签
    expect(wrapper.find('.dv-field-select').text()).toContain('帮扶村名称')
    expect(wrapper.text()).toContain('尚未执行校验')
  })

  it('路由 tab=rules 直达规则管理（内嵌 RulesPanel）', async () => {
    mocks.route.query = { tab: 'rules' }
    const wrapper = mountPage()
    await flushPromises()
    expect(activeTabText(wrapper)).toBe('规则管理')
    expect(wrapper.find('.rules-panel-stub').exists()).toBe(true)
  })

  it('路由 tab 非法值回退校验执行；query 变化由 watch 同步', async () => {
    mocks.route.query = { tab: 'unknown' }
    const wrapper = mountPage()
    await flushPromises()
    expect(activeTabText(wrapper)).toBe('校验执行')

    mocks.route.query = { tab: 'fields' }
    await nextTick()
    expect(activeTabText(wrapper)).toBe('字段说明')

    mocks.route.query = { tab: 'nope' }
    await nextTick()
    expect(activeTabText(wrapper)).toBe('校验执行')
  })

  it('切换 Tab 同步 activeTab 并 router.replace 写入 query', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await clickButton(wrapper, '规则管理')
    expect(activeTabText(wrapper)).toBe('规则管理')
    expect(mocks.replace).toHaveBeenCalledWith({ query: { tab: 'rules' } })

    await clickButton(wrapper, '字段说明')
    expect(activeTabText(wrapper)).toBe('字段说明')

    await clickButton(wrapper, '校验执行')
    expect(activeTabText(wrapper)).toBe('校验执行')
  })

  it('字段说明：渲染字段中文映射与规则类型说明表', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await clickButton(wrapper, '字段说明')
    expect(wrapper.find('.dv-table').text()).toContain('village_name')
    expect(wrapper.text()).toContain('帮扶村名称')
    expect(wrapper.text()).toContain('非空检查')
    expect(wrapper.text()).toContain('数值范围')
  })

  it('字段说明：加载中态与加载失败态', async () => {
    let resolveFields!: (value: unknown) => void
    mocks.get.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveFields = resolve
        })
    )
    const wrapper = mountPage()
    await clickButton(wrapper, '字段说明')
    expect(wrapper.text()).toContain('字段加载中…')

    resolveFields(FIELD_RESPONSE)
    await flushPromises()
    expect(wrapper.find('.dv-table').text()).toContain('人口数')

    // 切模块后加载失败 → 错误提示 + 空态
    mocks.get.mockReset()
    mocks.get.mockRejectedValueOnce(new Error('boom'))
    await wrapper.find('.dv-panel .dv-input').setValue('school')
    await flushPromises()
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('字段说明加载失败')
    expect(wrapper.text()).toContain('该模块暂无字段说明')
  })

  it('字段说明：扁平数组 / fields 缺失 / null 响应 / fields 非数组均安全降级', async () => {
    mocks.get.mockResolvedValueOnce([{ key: 'fund_name', label: '经费名称' }])
    let wrapper = mountPage()
    await flushPromises()
    await clickButton(wrapper, '字段说明')
    expect(wrapper.text()).toContain('经费名称')

    mocks.get.mockResolvedValueOnce({ data: {} })
    wrapper = mountPage()
    await flushPromises()
    await clickButton(wrapper, '字段说明')
    expect(wrapper.text()).toContain('该模块暂无字段说明')

    // null 响应 → ?? {} 兜底
    mocks.get.mockResolvedValueOnce(null)
    wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findAll('.dv-field-select option')).toHaveLength(1) // 仅占位项

    // fields 非数组 → 空列表
    mocks.get.mockResolvedValueOnce({ data: { fields: 'oops' } })
    wrapper = mountPage()
    await flushPromises()
    await clickButton(wrapper, '字段说明')
    expect(wrapper.text()).toContain('该模块暂无字段说明')
  })

  it('条件增删与运算符联动（empty/not_empty 隐藏比较值输入）', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.findAll('.dv-condition-row')).toHaveLength(1)

    await clickButton(wrapper, '+ 添加条件')
    expect(wrapper.findAll('.dv-condition-row')).toHaveLength(2)

    await clickButton(wrapper, '删除')
    expect(wrapper.findAll('.dv-condition-row')).toHaveLength(1)

    // 默认 not_empty → 不显示比较值
    expect(wrapper.find('.dv-value-input').exists()).toBe(false)
    await setCondOperator(wrapper, 'contains')
    expect(wrapper.find('.dv-value-input').exists()).toBe(true)
    // 比较值输入（原生 input v-model）
    await wrapper.find('.dv-value-input').setValue('甲')
    expect((wrapper.find('.dv-value-input').element as HTMLInputElement).value).toBe('甲')
    await setCondOperator(wrapper, 'empty')
    expect(wrapper.find('.dv-value-input').exists()).toBe(false)

    // 删除到 0 行 → 展示「请先添加条件」提示
    await clickButton(wrapper, '删除')
    expect(wrapper.findAll('.dv-condition-row')).toHaveLength(0)
    expect(wrapper.text()).toContain('请先添加至少一个校验条件')
  })

  it('切换模块：重置条件/结果并重新加载字段', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await clickButton(wrapper, '+ 添加条件')
    expect(wrapper.findAll('.dv-condition-row')).toHaveLength(2)

    await wrapper.findAll('select')[0].setValue('school')
    await flushPromises()
    expect(mocks.get).toHaveBeenLastCalledWith('/validation/fields', { module: 'school' })
    expect(wrapper.findAll('.dv-condition-row')).toHaveLength(1)
    expect(wrapper.text()).toContain('尚未执行校验')
  })

  it('一键校验：无有效条件时提示且不发请求', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await clickButton(wrapper, '一键校验')
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('请至少添加一个有效条件（字段 + 运算符）')
    expect(mocks.post).not.toHaveBeenCalled()
  })

  it('一键校验：成功渲染摘要与问题列表（定位修复 + 缺失值/缺失 id 展示）', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await runSuccessfulCheck(wrapper)

    expect(mocks.post).toHaveBeenCalledWith('/validation/query-check', {
      module: 'village',
      conditions: [{ field: 'village_name', operator: 'not_empty', value: '' }],
      logic: 'and',
      limit: 200,
    })
    const summary = wrapper.find('.dv-summary').text()
    expect(summary).toContain('共校验 3 条')
    expect(summary).toContain('问题记录 2 条')
    expect(summary).toContain('共 3 条记录，满足条件 1 条，不满足 2 条')

    const rows = wrapper.findAll('.dv-issue-row')
    expect(rows).toHaveLength(2)
    // 缺失 id / 缺失 values 的行显示占位符
    expect(rows[1].text()).toContain('-')

    // 定位修复：正常 id → 对应模块详情路由
    await rows[0].find('.dv-link').trigger('click')
    expect(mocks.pushSafe).toHaveBeenCalledWith('/supported-villages/2')

    // 缺失 id → 提示无法定位
    await rows[1].find('.dv-link').trigger('click')
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('该记录缺少唯一标识，无法定位')
  })

  it('一键校验：问题列表表头字段名不在当前字段清单时回退字段 key', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await runSuccessfulCheck(wrapper)
    // 切到「字段说明」换模块 → 字段清单被替换为 school 字段（不再包含 village_name）
    await clickButton(wrapper, '字段说明')
    mocks.get.mockResolvedValueOnce({
      data: { fields: [{ key: 'school_name', label: '学校名称' }] },
    })
    await wrapper.find('.dv-panel .dv-input').setValue('school')
    await flushPromises()
    await clickButton(wrapper, '校验执行')
    // 校验结果仍保留，表头用 fieldLabel 回退显示原始字段 key
    expect(wrapper.find('.dv-table thead').text()).toContain('village_name')
  })

  it('一键校验：空响应 / null 响应按 0 条与空问题列表处理', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await setCondField(wrapper, 'village_name')

    mocks.post.mockResolvedValueOnce({})
    await clickButton(wrapper, '一键校验')
    expect(wrapper.find('.dv-summary').text()).toContain('共校验 0 条')
    expect(wrapper.text()).toContain('未发现问题记录')

    mocks.post.mockResolvedValueOnce(null)
    await clickButton(wrapper, '一键校验')
    expect(wrapper.find('.dv-summary').text()).toContain('共校验 0 条')
    // 无 message 字段时不渲染括号说明
    expect(wrapper.find('.dv-message').exists()).toBe(false)
  })

  it('一键校验：失败时展示后端详情或兜底文案', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await setCondField(wrapper, 'village_name')

    mocks.post.mockRejectedValueOnce({ response: { data: { detail: '模块不支持' } } })
    await clickButton(wrapper, '一键校验')
    expect(mocks.ElMessage.error).toHaveBeenCalledWith('模块不支持')
    expect(wrapper.text()).toContain('尚未执行校验')

    mocks.post.mockRejectedValueOnce(new Error('network'))
    await clickButton(wrapper, '一键校验')
    expect(mocks.ElMessage.error).toHaveBeenLastCalledWith('校验执行失败')
  })

  it('一键校验：运行中按钮文案切换', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await setCondField(wrapper, 'village_name')
    let resolvePost!: (value: unknown) => void
    mocks.post.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolvePost = resolve
        })
    )
    const btn = wrapper.findAll('button').find((b) => b.text().trim() === '一键校验')!
    await btn.trigger('click')
    await nextTick()
    expect(wrapper.text()).toContain('校验中…')
    resolvePost({ data: { results: [] } })
    await flushPromises()
    expect(wrapper.text()).toContain('一键校验')
  })

  it('导出问题清单：无问题记录时提示', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await clickButton(wrapper, '导出问题清单')
    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('当前没有问题记录可导出')
  })

  it('导出问题清单：有记录时生成 CSV（含 BOM 与单元格转义）', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await runSuccessfulCheck(wrapper)

    const createSpy = vi.spyOn(URL, 'createObjectURL')
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL')
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    await clickButton(wrapper, '导出问题清单')
    expect(createSpy).toHaveBeenCalled()
    expect(anchorClick).toHaveBeenCalled()
    expect(revokeSpy).toHaveBeenCalled()
    expect(mocks.ElMessage.success).toHaveBeenCalledWith('已导出 2 条问题记录')
  })

  it('重置校验：清空条件与结果', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await runSuccessfulCheck(wrapper)
    expect(wrapper.find('.dv-result').exists()).toBe(true)

    await clickButton(wrapper, '重置')
    expect(wrapper.find('.dv-result').exists()).toBe(false)
    expect(wrapper.findAll('.dv-condition-row')).toHaveLength(1)
    expect(wrapper.text()).toContain('尚未执行校验')
  })
})
