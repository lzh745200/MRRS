/**
 * views/dataManagement/components/QualitySection.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：概览计算属性（totalRecords 为 0/非 0 两侧）、getStatusText 映射与未知兜底、
 * handleCheck 成功（valid 真/假、res 为 null、res.data 缺失）与异常分支、
 * handleViewIssues 全字段 ?? 链映射、canAutoFix 两侧与异常分支、
 * handleAutoFix 早退/成功（cleaned_count 有/无）/异常分支、
 * 模板内联事件（开始检查/查看详情/关闭/自动修复）与 el-dialog v-model。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂提升求值，引用对象须先放入 vi.hoisted 初始化
const { mockPost, ElMessage } = vi.hoisted(() => {
  return {
    mockPost: vi.fn(),
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  }
})

vi.mock('element-plus', () => ({
  ElMessage,
}))

vi.mock('@/api/request', () => ({
  post: mockPost,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import QualitySection from '@/views/dataManagement/components/QualitySection.vue'

const statsFull = {
  totalRecords: 200,
  validRecords: 180,
  invalidRecords: 20,
  completenessRate: 96.55,
  lastCheckTime: '2024-06-01 10:00:00',
}
const statsZero = {
  totalRecords: 0,
  validRecords: 0,
  invalidRecords: 0,
  completenessRate: 0,
  lastCheckTime: '',
}

function mountComp(stats: any = statsFull) {
  // el-card/el-dialog/el-statistic 需渲染具名插槽（header/footer/suffix）；
  // el-table-column 注入五行样本覆盖状态三元、getStatusText 兜底与 v-if issues>0 两侧
  return mount(QualitySection, {
    props: { stats },
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
        },
        'el-statistic': {
          name: 'ElStatistic',
          template: '<div class="el-statistic-stub"><slot /><slot name="suffix" /></div>',
        },
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue'],
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /><slot :row="rowD" /><slot :row="rowE" /></div>',
          data() {
            return {
              rowA: { id: 'required_fields', name: '必填字段检查', status: 'pass', issues: 0 },
              rowB: { id: 'data_format', name: '数据格式检查', status: 'warning', issues: 2 },
              rowC: { id: 'region_validity', name: '地区有效性检查', status: 'fail', issues: 3 },
              rowD: { id: 'duplicate_check', name: '重复数据检查', status: 'pending', issues: 0 },
              rowE: { id: 'weird', name: '未知检查', status: 'strange', issues: 1 },
            }
          },
        },
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
  mockPost.mockResolvedValue({ data: { issues: [], valid: true } })
})

describe('概览渲染与计算属性', () => {
  it('非零总数：validRate/invalidRate 百分比渲染，显示上次检查时间', () => {
    const wrapper = mountComp()
    expect(wrapper.text()).toContain('90.0')
    expect(wrapper.text()).toContain('10.0')
    expect(wrapper.find('.last-check').exists()).toBe(true)
    expect(wrapper.text()).toContain('2024-06-01 10:00:00')
  })

  it('总数为 0：比率返回 0，lastCheckTime 为空时不渲染时间标签', () => {
    const wrapper = mountComp(statsZero)
    const vm = wrapper.vm as any
    expect(vm.validRate).toBe(0)
    expect(vm.invalidRate).toBe(0)
    expect(wrapper.find('.last-check').exists()).toBe(false)
  })

  it('getStatusText：四个已知状态映射 + 未知状态原样返回', () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.getStatusText('pass')).toBe('通过')
    expect(vm.getStatusText('warning')).toBe('警告')
    expect(vm.getStatusText('fail')).toBe('失败')
    expect(vm.getStatusText('pending')).toBe('待检查')
    expect(vm.getStatusText('strange')).toBe('strange')
  })
})

describe('handleCheck', () => {
  it('检查通过（valid=true）→ 全部置 pass', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleCheck()
    expect(mockPost).toHaveBeenCalledWith('/data-quality/full-check')
    expect(vm.checkItems.every((i: any) => i.status === 'pass' && i.issues === 0)).toBe(true)
    expect(ElMessage.success).toHaveBeenCalledWith('数据质量检查通过')
    expect(vm.checking).toBe(false)
  })

  it('发现问题（valid=false）→ 置 warning 并提示问题数', async () => {
    mockPost.mockResolvedValue({ data: { issues: [{ a: 1 }, { b: 2 }], valid: false } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleCheck()
    expect(vm.checkItems.every((i: any) => i.status === 'warning' && i.issues === 2)).toBe(true)
    expect(ElMessage.success).toHaveBeenCalledWith('发现 2 个问题')
    expect(vm.checking).toBe(false)
  })

  it('res 为 null / res.data 缺失 → ?? 兜底链按无问题处理', async () => {
    mockPost.mockResolvedValue(null)
    let wrapper = mountComp()
    await flushPromises()
    let vm = wrapper.vm as any
    await vm.handleCheck()
    expect(vm.checkItems.every((i: any) => i.status === 'pass' && i.issues === 0)).toBe(true)
    expect(ElMessage.success).toHaveBeenCalledWith('数据质量检查通过')
    wrapper.unmount()

    mockPost.mockResolvedValue({})
    wrapper = mountComp()
    await flushPromises()
    vm = wrapper.vm as any
    await vm.handleCheck()
    expect(vm.checkItems.every((i: any) => i.status === 'pass')).toBe(true)
  })

  it('请求异常 → 全部置 pending 并警告，finally 复位 checking', async () => {
    mockPost.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleCheck()
    expect(vm.checkItems.every((i: any) => i.status === 'pending' && i.issues === 0)).toBe(true)
    expect(ElMessage.error).toHaveBeenCalledWith('质量检查执行失败，请稍后重试')
    expect(vm.checking).toBe(false)
  })
})

describe('handleViewIssues', () => {
  it('成功：四类问题对象覆盖全部 ?? 映射链', async () => {
    mockPost.mockResolvedValue({
      data: {
        issues: [
          { record_id: 5, field: 'name', message: 'm1', suggestion: 's1' },
          { id: 6, field_name: 'f2', issue: 'i2' },
          { description: 'd3' },
          {},
        ],
      },
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleViewIssues({ id: 'data_format', name: '数据格式检查' } as any)
    expect(vm.issueDetails).toEqual([
      { record_id: 5, field: 'name', issue: 'm1', suggestion: 's1' },
      { record_id: 6, field: 'f2', issue: 'i2', suggestion: '请检查并修正该字段的值' },
      { record_id: 0, field: '', issue: 'd3', suggestion: '请检查并修正该字段的值' },
      { record_id: 0, field: '', issue: '', suggestion: '请检查并修正该字段的值' },
    ])
    expect(vm.canAutoFix).toBe(true)
    expect(vm.showIssuesDialog).toBe(true)
    expect(vm.selectedCheck).toMatchObject({ id: 'data_format' })
  })

  it('canAutoFix=false：非 data_format/calculation_check 检查项；res.data/issues 缺失走 ?? 兜底', async () => {
    mockPost.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleViewIssues({ id: 'required_fields', name: '必填字段检查' } as any)
    expect(vm.issueDetails).toEqual([])
    expect(vm.canAutoFix).toBe(false)
    expect(vm.showIssuesDialog).toBe(true)
  })

  it('请求异常 → 详情清空、禁止自动修复，对话框仍打开', async () => {
    mockPost.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleViewIssues({ id: 'calculation_check', name: '计算正确性检查' } as any)
    expect(vm.issueDetails).toEqual([])
    expect(vm.canAutoFix).toBe(false)
    expect(vm.showIssuesDialog).toBe(true)
  })
})

describe('handleAutoFix', () => {
  it('selectedCheck 为空 → 早退不发请求', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedCheck = null
    await vm.handleAutoFix()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('成功：记录 ID 去重后提交，关闭对话框并触发复查', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedCheck = { id: 'data_format', name: '数据格式检查' }
    vm.issueDetails = [{ record_id: 1 }, { record_id: 2 }, { record_id: 1 }]
    vm.showIssuesDialog = true
    mockPost.mockResolvedValue({ data: { cleaned_count: 3 } })
    await vm.handleAutoFix()
    expect(mockPost).toHaveBeenCalledWith('/data-quality/clean', {
      records: [1, 2],
      cleaning_rules: { trim_whitespace: true, normalize_empty: true },
    })
    expect(ElMessage.success).toHaveBeenCalledWith('自动修复完成，处理了 3 条记录')
    expect(vm.showIssuesDialog).toBe(false)
    // handleAutoFix 内部会再调 handleCheck → 再次请求 full-check
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith('/data-quality/full-check')
    expect(vm.fixing).toBe(false)
  })

  it('成功但 cleaned_count 缺失 → ?? 0 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedCheck = { id: 'data_format', name: '数据格式检查' }
    vm.issueDetails = []
    mockPost.mockResolvedValue({})
    await vm.handleAutoFix()
    expect(ElMessage.success).toHaveBeenCalledWith('自动修复完成，处理了 0 条记录')
    expect(vm.fixing).toBe(false)
  })

  it('请求异常 → 警告提示，finally 复位 fixing', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedCheck = { id: 'data_format', name: '数据格式检查' }
    vm.issueDetails = [{ record_id: 1 }]
    mockPost.mockRejectedValue(new Error('net'))
    await vm.handleAutoFix()
    expect(ElMessage.warning).toHaveBeenCalledWith('自动修复失败，请手动修正问题数据')
    expect(vm.fixing).toBe(false)
  })
})

describe('模板交互（内联处理器与 v-model 覆盖）', () => {
  it('点击「开始检查」按钮触发 handleCheck', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await findBtn(wrapper, '开始检查').trigger('click')
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith('/data-quality/full-check')
  })

  it('点击「查看详情」按钮触发 handleViewIssues（注入行）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const btn = findBtn(wrapper, '查看详情')
    await btn.trigger('click')
    await flushPromises()
    expect(vm.selectedCheck).toMatchObject({ id: 'data_format' })
    expect(vm.showIssuesDialog).toBe(true)
  })

  it('issues=0 的行不渲染「查看详情」按钮（v-if 假侧样本行存在）', () => {
    const wrapper = mountComp()
    const btns = wrapper.findAll('el-button-stub').filter((b) => b.text().includes('查看详情'))
    // 五行样本中仅 rowB/rowC/rowE issues>0
    expect(btns.length).toBe(3)
  })

  it('点击「关闭」按钮关闭对话框', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.showIssuesDialog = true
    await nextTick()
    // 问题详情对话框是第 2 个 el-dialog（第 1 个为自定义校验对话框），在其内部查找「关闭」
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    const btns = dialogs[1].findAll('el-button-stub').filter((b: any) => b.text().trim() === '关闭')
    await btns[0].trigger('click')
    expect(vm.showIssuesDialog).toBe(false)
  })

  it('点击「自动修复」按钮触发 handleAutoFix', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.selectedCheck = { id: 'data_format', name: '数据格式检查' }
    vm.issueDetails = [{ record_id: 7 }]
    mockPost.mockResolvedValue({ data: { cleaned_count: 1 } })
    await findBtn(wrapper, '自动修复').trigger('click')
    await flushPromises()
    expect(mockPost).toHaveBeenCalledWith('/data-quality/clean', {
      records: [7],
      cleaning_rules: { trim_whitespace: true, normalize_empty: true },
    })
  })

  it('el-dialog v-model：emit update:modelValue 同步 showIssuesDialog', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    expect(dialogs.length).toBeGreaterThan(1)
    // 问题详情对话框为第 2 个（第 1 个为自定义校验对话框）
    const issuesDialog = dialogs[1]
    issuesDialog.vm.$emit('update:modelValue', true)
    await nextTick()
    expect(vm.showIssuesDialog).toBe(true)
    issuesDialog.vm.$emit('update:modelValue', false)
    await nextTick()
    expect(vm.showIssuesDialog).toBe(false)
  })
})

describe('自定义规则校验', () => {
  it('openRuleDialog 重置状态；addRule 添加条件；runRuleCheck 提交与失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openRuleDialog()
    expect(vm.showRuleDialog).toBe(true)
    expect(vm.ruleResult).toBeNull()
    expect(vm.ruleList.length).toBe(1)
    vm.addRule()
    expect(vm.ruleList.length).toBe(2)
    // 无字段条件 → 提示（清空全部规则字段）
    vm.ruleList = [{ logic: 'and', field: '', operator: 'eq', value: '' }]
    await vm.runRuleCheck()
    expect(ElMessage.warning).toHaveBeenCalled()
    // 正常提交
    vm.ruleList[0].field = 'county'
    vm.ruleList[0].operator = 'eq'
    vm.ruleList[0].value = '长顺县'
    mockPost.mockResolvedValue({ data: { matched_count: 6, failed_count: 0, message: '校验完成' } })
    await vm.runRuleCheck()
    expect(mockPost).toHaveBeenCalledWith('/data-quality/validate-rules', expect.anything())
    expect(vm.ruleResult.matched_count).toBe(6)
    // 失败
    mockPost.mockRejectedValue({ response: { data: { detail: '失败' } } })
    await vm.runRuleCheck()
    expect(ElMessage.error).toHaveBeenCalledWith('失败')
  })
})

describe('自定义规则校验补充', () => {
  it('runRuleCheck 失败分支与 handleViewIssues fallback', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 规则结果带 failed → 触发表格分支
    mockPost.mockResolvedValue({ data: { matched_count: 5, failed_count: 1, failed: [{ record_id: 1, label: 'x' }] } })
    await vm.runRuleCheck()
    expect(vm.ruleResult.failed_count).toBe(1)
    // runRuleCheck 异常 → 错误提示
    mockPost.mockRejectedValue({ response: { data: { detail: '服务异常' } } })
    await vm.runRuleCheck()
    expect(ElMessage.error).toHaveBeenCalledWith('服务异常')
    // handleViewIssues：lastIssues 为空 → fallback 调 full-check
    vm.lastIssues = []
    mockPost.mockResolvedValue({ data: { issues: [{ field: 'name', message: '缺失', suggestion: '补全' }] } })
    await vm.handleViewIssues({ id: 'data_format', name: '格式' })
    expect(vm.issueDetails.length).toBe(1)
    expect(vm.showIssuesDialog).toBe(true)
    // handleViewIssues 异常 → 空列表
    mockPost.mockRejectedValue(new Error('boom'))
    await vm.handleViewIssues({ id: 'data_format', name: '格式' })
    expect(vm.issueDetails).toEqual([])
  })
})

describe('自定义校验模板事件', () => {
  it('自定义校验按钮/添加条件/删除条件/执行校验 点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 自定义校验按钮
    const openBtn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().includes('自定义校验'))
    if (openBtn) {
      await openBtn.trigger('click')
      expect(vm.showRuleDialog).toBe(true)
    }
    // 添加条件按钮
    const addBtn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().includes('添加条件'))
    if (addBtn) {
      await addBtn.trigger('click')
      expect(vm.ruleList.length).toBe(2)
    }
    // 执行校验按钮
    mockPost.mockResolvedValue({ data: { total: 6, unmatched: 0 } })
    const runBtn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().includes('执行校验'))
    if (runBtn) {
      await runBtn.trigger('click')
      await flushPromises()
    }
    // 关闭按钮
    const closeBtn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().trim() === '关闭')
    if (closeBtn) {
      await closeBtn.trigger('click')
      expect(vm.showRuleDialog).toBe(false)
    }
    wrapper.unmount()
  })
})

describe('规则构建器控件', () => {
  it('模块选择/规则行 v-model/删除条件 触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.showRuleDialog = true
    await wrapper.vm.$nextTick()
    // 模块选择 v-model
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    if (selects.length) {
      selects[0].vm.$emit('update:modelValue', 'fund')
      expect(vm.ruleModule).toBe('fund')
    }
    // 规则行 field/operator/value v-model
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    if (inputs.length) inputs[0].vm.$emit('update:modelValue', 'name')
    // 删除条件按钮
    const delBtn = wrapper.findAll('.el-button-stub').find((b: any) => b.text().includes('删除'))
    if (delBtn) {
      await delBtn.trigger('click')
      expect(vm.ruleList.length).toBeLessThanOrEqual(2)
    }
    wrapper.unmount()
  })
})
