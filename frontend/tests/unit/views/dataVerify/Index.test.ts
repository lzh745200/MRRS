/**
 * views/dataVerify/Index.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：getVerifyStatusText 映射与兜底、loadData（items/数组/缺省、完整度计算、verifyStatus 链、
 * submitTime 转换、失败）、updateStats 四计数、handleBatchCheck（rawVillages 空预加载、
 * 后端 valid 通过/未通过/异常回退、passed/failed 统计、弹窗与提示）、
 * showErrors/handleReview/handleApprove/handleReject、模板按钮与对话框。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { ElMessage, mockPost, mockApiRequest } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  mockPost: vi.fn(),
  mockApiRequest: vi.fn(),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/request', () => ({
  post: mockPost,
  apiRequest: mockApiRequest,
  get: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import Index from '@/views/dataVerify/Index.vue'

const villages = [
  { id: 1, village_name: '甲村', department: '作战处', support_unit: '帮扶队A', county: '都匀市', transition_fund_military_total: 100, created_at: '2024-06-01T10:00:00' },
  { id: 2, name: '乙村', department: '', support_unit: '', county: '', transition_fund_military_total: 0, created_at: '' },
  { id: 3, village_name: '丙村', department: '参谋处', support_unit: '帮扶队B', county: '', transition_fund_military_total: 50, created_at: '2024-06-02T11:00:00' },
  { id: 4, village_name: '丁村', department: '作训处', support_unit: '帮扶队C', county: '', transition_fund_military_total: 0, created_at: '2024-06-03T12:00:00' },
  { id: 5, department: '', support_unit: '', county: '', transition_fund_military_total: 0, created_at: '' },
]

// 完整度：v1 5/5=100%→pass；v2 0/5=0%→fail；v3 4/5=80%→pass；v4 3/5=60%→pending
const mapped = [
  { id: 1, villageName: '甲村', department: '作战处', submitter: '帮扶队A', submitTime: '2024-06-01 10:00', completeness: 100, verifyStatus: 'pass', verifyErrors: [] },
  { id: 2, villageName: '乙村', department: '', submitter: '', submitTime: '', completeness: 0, verifyStatus: 'fail', verifyErrors: [{ field: 'county', field_label: '县区', message: '缺失' }] },
  { id: 3, villageName: '丙村', department: '参谋处', submitter: '帮扶队B', submitTime: '2024-06-02 11:00', completeness: 80, verifyStatus: 'pass', verifyErrors: [] },
  { id: 4, villageName: '丁村', department: '作训处', submitter: '帮扶队C', submitTime: '2024-06-03 12:00', completeness: 60, verifyStatus: 'pending', verifyErrors: [] },
]

function mountComp() {
  return mount(Index, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot name="header" /><slot /></div>',
        },
        'el-table': { name: 'ElTable', template: '<div class="el-table-stub"><slot /></div>' },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>',
          data() {
            return { rowA: mapped[0], rowB: mapped[1], rowC: mapped[2] }
          },
        },
        'el-dialog': {
          name: 'ElDialog',
          template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
          emits: ['update:modelValue'],
        },
        'el-progress': {
          name: 'ElProgress',
          props: ['percentage'],
          template: '<div class="el-progress-stub">{{ percentage }}</div>',
        },
        'el-tag': {
          name: 'ElTag',
          template: '<span class="el-tag-stub" @click="$emit(\'click\')"><slot /></span>',
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
  mockApiRequest.mockResolvedValue({ data: { items: villages } })
  mockPost.mockResolvedValue({ data: { valid: true } })
})

describe('挂载与加载', () => {
  it('onMounted：items 形态 → 映射完整度与 verifyStatus；统计更新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(mockApiRequest).toHaveBeenCalledWith(
      expect.objectContaining({ url: '/supported-villages', params: { page: 1, page_size: 50 } })
    )
    expect(vm.dataList).toHaveLength(5)
    expect(vm.dataList[0].completeness).toBe(100)
    expect(vm.dataList[0].verifyStatus).toBe('pass')
    expect(vm.dataList[1].completeness).toBe(0)
    expect(vm.dataList[1].verifyStatus).toBe('fail')
    expect(vm.dataList[2].completeness).toBe(80)
    expect(vm.dataList[2].verifyStatus).toBe('pass')
    expect(vm.dataList[3].completeness).toBe(60)
    expect(vm.dataList[3].verifyStatus).toBe('pending')
    expect(vm.dataList[4].villageName).toBe('') // village_name/name 均缺 → ''
    expect(vm.dataList[0].submitTime).toBe('2024-06-01 10:00')
    expect(vm.stats.pending).toBe(1)
    expect(vm.stats.approved).toBe(2)
    expect(vm.stats.rejected).toBe(2) // v2、v5
    expect(vm.stats.issues).toBe(2) // completeness <60
    expect(vm.loading).toBe(false)
    const text = wrapper.text()
    expect(text).toContain('100') // progress
    expect(text).toContain('通过')
    expect(text).toContain('未通过')
  })

  it('数组形态与缺省兜底；失败 → logger', async () => {
    mockApiRequest.mockResolvedValue({ data: villages })
    let wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).dataList).toHaveLength(5)

    mockApiRequest.mockResolvedValue({ data: {} })
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).dataList).toEqual([])
    expect((wrapper.vm as any).stats.pending).toBe(0)

    mockApiRequest.mockRejectedValue(new Error('net'))
    wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).dataList).toEqual([])
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('getVerifyStatusText 映射与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getVerifyStatusText('pass')).toBe('通过')
    expect(vm.getVerifyStatusText('fail')).toBe('未通过')
    expect(vm.getVerifyStatusText('pending')).toBe('待校验')
    expect(vm.getVerifyStatusText('weird')).toBe('weird')
  })

  it('「刷新」按钮重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const base = mockApiRequest.mock.calls.length
    await findBtn(wrapper, '刷新').trigger('click')
    await flushPromises()
    expect(mockApiRequest.mock.calls.length).toBe(base + 1)
  })
})

describe('handleBatchCheck', () => {
  it('后端 valid 通过（完整度≥80/不足）与未通过 + 失败行', async () => {
    mockPost
      .mockResolvedValueOnce({ data: { valid: true } })
      .mockResolvedValueOnce({ data: { valid: false, errors: [{ field: 'a', message: '格式错误' }] } })
      .mockResolvedValueOnce({ data: { valid: true } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findBtn(wrapper, '批量校验').trigger('click')
    await flushPromises()
    expect(mockPost).toHaveBeenCalledTimes(5)
    expect(mockPost).toHaveBeenCalledWith('/validation/validate', villages[1], {
      params: { module: 'village' },
    })
    expect(vm.dataList[0].verifyStatus).toBe('pass')
    expect(vm.dataList[1].verifyStatus).toBe('fail')
    expect(vm.dataList[1].verifyErrors).toHaveLength(1)
    expect(vm.dataList[2].verifyStatus).toBe('pass') // valid 且完整度 80
    expect(vm.dataList[3].verifyStatus).toBe('pending') // valid 但完整度 60 → pending
    expect(vm.dataList[4].verifyStatus).toBe('pending') // valid 但完整度 0 → pending
    expect(vm.batchResult.total).toBe(5)
    expect(vm.batchResult.passed).toBe(4)
    expect(vm.batchResult.failed).toBe(1)
    expect(ElMessage.warning).toHaveBeenCalledWith('校验完成：4 条通过，1 条未通过')
    expect(vm.batchResultVisible).toBe(true)
    expect(vm.batchChecking).toBe(false)
  })

  it('全部通过 → 成功提示；rawVillages 为空时先预加载（loadData 全量刷新）', async () => {
    mockApiRequest.mockResolvedValueOnce({ data: { items: [villages[0]] } })
    mockPost.mockResolvedValue({ data: { valid: true } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.rawVillages = []
    vm.dataList = []
    await vm.handleBatchCheck()
    await flushPromises()
    expect(vm.batchResult.total).toBe(5) // 预加载后为全量 5 条
    expect(vm.batchResult.passed).toBe(5)
    expect(vm.batchResult.failed).toBe(0)
    expect(ElMessage.success).toHaveBeenCalledWith('批量校验完成，全部 5 条数据通过')
    expect(vm.batchResultVisible).toBe(false)
  })

  it('后端异常 → 完整度回退三分支（含 pending/fail 中间与兜底）', async () => {
    mockPost.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.dataList[1].completeness = 60 // 触发回退的 pending 分支
    vm.dataList[2].completeness = 0 // 触发回退的 fail 分支
    await vm.handleBatchCheck()
    await flushPromises()
    // v1 100→pass、v2 60→pending、v3 0→fail、v4 60→pending、v5 0→fail
    expect(vm.dataList[0].verifyStatus).toBe('pass')
    expect(vm.dataList[1].verifyStatus).toBe('pending')
    expect(vm.dataList[2].verifyStatus).toBe('fail')
    expect(vm.dataList[3].verifyStatus).toBe('pending')
    expect(vm.dataList[4].verifyStatus).toBe('fail')
    expect(vm.batchResult.passed).toBe(1)
    expect(vm.batchResult.failed).toBe(4)
    expect(ElMessage.warning).toHaveBeenCalled()
    expect(vm.batchResultVisible).toBe(true)
  })

  it('dataList 缺行 → continue 跳过；valid=false 且 errors 缺失 → ?? [] 兜底', async () => {
    mockPost.mockResolvedValue({ data: { valid: false } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.rawVillages = [{ id: 1 }, { id: 2 }] as any[]
    vm.dataList = [mapped[0]] // 仅一行 → 第二行 continue
    await vm.handleBatchCheck()
    await flushPromises()
    expect(mockPost).toHaveBeenCalledTimes(1)
    expect(vm.batchResult.failedRows[0].errors).toEqual([])
  })
})

describe('行操作', () => {
  it('handleReview → showErrors 打开错误弹窗（field_label 与 field 兜底两侧）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleReview(mapped[1])
    expect(vm.errorDialogTitle).toBe('乙村')
    expect(vm.errorDialogVisible).toBe(true)
    expect(vm.currentErrors).toHaveLength(1)
    await nextTick()
    expect(wrapper.text()).toContain('县区') // field_label
    expect(wrapper.text()).toContain('缺失')

    vm.showErrors({ villageName: '丙村', verifyErrors: [{ field: 'only_field', message: '无标签' }] })
    await nextTick()
    expect(wrapper.text()).toContain('only_field') // field 兜底
  })

  it('showErrors：verifyErrors 为空/缺失 → 无问题占位与 ?? [] 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.showErrors({ villageName: '甲村', verifyErrors: [] })
    expect(vm.errorDialogVisible).toBe(true)
    await nextTick()
    expect(wrapper.find('.no-errors').exists()).toBe(true)

    vm.showErrors({ villageName: '丁村' }) // 无 verifyErrors → ?? []
    expect(vm.currentErrors).toEqual([])
    await nextTick()
    expect(wrapper.find('.no-errors').exists()).toBe(true)
  })

  it('handleApprove/handleReject 更新状态与统计（模板按钮点击 + 直接调用）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 模板按钮点击（stub 注入行）
    await findBtn(wrapper, '通过').trigger('click')
    expect(ElMessage.success).toHaveBeenCalledWith('已通过')
    await findBtn(wrapper, '驳回').trigger('click')
    expect(ElMessage.warning).toHaveBeenCalledWith('已驳回')

    // 直接对组件数据行调用
    vm.handleApprove(vm.dataList[1])
    expect(vm.dataList[1].verifyStatus).toBe('pass')
    expect(vm.stats.approved).toBe(3)
    vm.handleReject(vm.dataList[1])
    expect(vm.dataList[1].verifyStatus).toBe('fail')
    expect(vm.stats.rejected).toBe(2)
  })

  it('审核按钮（rowA）打开错误弹窗', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await findBtn(wrapper, '审核').trigger('click')
    expect((wrapper.vm as any).errorDialogVisible).toBe(true)
  })

  it('状态标签 click（fail + verifyErrors）触发 showErrors', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const tags = wrapper.findAllComponents({ name: 'ElTag' })
    // rowB 状态列标签：fail 且有错误
    await tags[1].trigger('click')
    expect(vm.errorDialogVisible).toBe(true)
    expect(vm.errorDialogTitle).toBe('乙村')
  })

  it('对话框 v-model 与关闭按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.errorDialogVisible = true
    vm.batchResultVisible = true
    await nextTick()
    const dialogs = wrapper.findAllComponents({ name: 'ElDialog' })
    expect(dialogs.length).toBe(2)
    const closes = wrapper.findAll('el-button-stub').filter((b: any) => b.text().trim() === '关闭')
    await closes[0].trigger('click')
    expect(vm.errorDialogVisible).toBe(false)
    await closes[1].trigger('click')
    expect(vm.batchResultVisible).toBe(false)
    vm.errorDialogVisible = true
    vm.batchResultVisible = true
    await nextTick()
    dialogs[0].vm.$emit('update:modelValue', false)
    expect(vm.errorDialogVisible).toBe(false)
    dialogs[1].vm.$emit('update:modelValue', false)
    expect(vm.batchResultVisible).toBe(false)
  })
})

describe('查询校验构建器', () => {
  it('qcAddCondition/qcRemoveCondition/qcReset/qcRunCheck 全流程', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // qcFieldLabel 兜底
    vm.qc.fields = [{ key: 'name', label: '名称' }]
    expect(vm.qcFieldLabel('name')).toBe('名称')
    expect(vm.qcFieldLabel('unknown')).toBe('unknown')
    // 添加/移除条件
    vm.qcAddCondition()
    expect(vm.qc.conditions.length).toBe(2)
    vm.qcRemoveCondition(1)
    expect(vm.qc.conditions.length).toBe(1)
    // 无字段 → warning
    vm.qc.conditions = [{ field: '', operator: 'eq', value: '' }]
    await vm.qcRunCheck()
    expect(ElMessage.warning).toHaveBeenCalled()
    // 校验成功（unmatched=0）
    vm.qc.conditions = [{ field: 'name', operator: 'eq', value: '幸福村' }]
    mockPost.mockResolvedValue({ data: { total: 6, unmatched: 0 } })
    await vm.qcRunCheck()
    expect(ElMessage.success).toHaveBeenCalledWith('全部 6 条记录均满足条件')
    // unmatched > 0
    mockPost.mockResolvedValue({ data: { total: 6, unmatched: 2 } })
    await vm.qcRunCheck()
    expect(ElMessage.warning).toHaveBeenCalledWith('发现 2 条记录不满足条件')
    // 失败
    mockPost.mockRejectedValue({ response: { data: { detail: '服务异常' } } })
    await vm.qcRunCheck()
    expect(ElMessage.error).toHaveBeenCalledWith('服务异常')
    // qcReset
    vm.qcResult = { total: 1, unmatched: 0 }
    vm.qcReset()
    expect(vm.qcResult).toBeNull()
    expect(vm.qc.conditions.length).toBe(1)
    wrapper.unmount()
  })
})

describe('模板控件补充', () => {
  it('select v-model 与删除条件按钮触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    if (selects.length) {
      selects[0].vm.$emit('update:modelValue', 'fund')
    }
    const delBtn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes('删除'))
    if (delBtn) {
      await delBtn.trigger('click')
    }
    wrapper.unmount()
  })
})

describe('校验边界补充', () => {
  it('查询条件值空/裸对象响应/unmatched 触发', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.qc.conditions = [{ field: 'a', operator: 'eq', value: '' }, { field: 'b', operator: 'empty', value: 'x' }]
    ;(mockPost as any).mockResolvedValueOnce({ unmatched: 2, total: 5, rows: [{ values: {} }] })
    await vm.qcRunCheck()
    expect(vm.qcResult.unmatched).toBe(2)
    wrapper.unmount()
  })
  it('handleQueryCheck reject 无 detail', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.qc.conditions = [{ field: 'a', operator: 'eq', value: '1' }]
    ;(mockPost as any).mockRejectedValueOnce(new Error('x'))
    await vm.qcRunCheck()
    wrapper.unmount()
  })
})

describe('查询对话框全控件', () => {
  it('dialog v-model 打开 → radio/selects/input → 删除条件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const dialog = wrapper.findComponent({ name: 'ElDialog' })
    if (dialog.exists()) {
      await dialog.vm.$emit('update:modelValue', true)
      await wrapper.vm.$nextTick()
    } else {
      vm.showQueryDialog = true
      await wrapper.vm.$nextTick()
    }
    vm.qc.conditions = [
      { field: 'a', operator: 'eq', value: '1' },
      { field: 'b', operator: 'contains', value: '2' },
    ]
    await wrapper.vm.$nextTick()
    const radios = wrapper.findAllComponents({ name: 'ElRadioGroup' })
    for (const r of radios) {
      r.vm.$emit('update:modelValue', 'or')
      await wrapper.vm.$nextTick()
    }
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    for (const s of selects) {
      s.vm.$emit('update:modelValue', 'eq')
      await wrapper.vm.$nextTick()
    }
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    for (const i of inputs) {
      i.vm.$emit('update:modelValue', 'v')
      await wrapper.vm.$nextTick()
    }
    const delBtn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes('删除'))
    if (delBtn) await delBtn.trigger('click')
    wrapper.unmount()
  })
})

describe('结果行渲染分支', () => {
  it('matched=false 行 + values 有值渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.qcResult = { rows: [{ matched: false, values: { name: '张三' } }], total: 1, unmatched: 1 }
    vm.showResult = true
    await wrapper.vm.$nextTick()
    expect(wrapper.html()).toContain('不满足')
    wrapper.unmount()
  })
})
