/**
 * views/funds/Budget.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted/watch 年份加载、loadBudgets 映射与失败、openDialog 编辑/新增、
 * handleSaveBudget 全分支（无 formRef/校验失败/编辑无 id/更新成功/新增成功/保存失败）、
 * handleDeleteBudget 全分支、summary/usageRateClass/getProgressColor/getUsageRate/gaugeOption、
 * getSummary 列分支、模板 v-model 与按钮事件。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const {
  ElMessage,
  fundApiMock,
  logError,
  pushSafeMock,
  validateMock,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  fundApiMock: {
    listBudgets: vi.fn(),
    createBudget: vi.fn(),
    updateBudget: vi.fn(),
    deleteBudget: vi.fn(),
  },
  logError: vi.fn(),
  pushSafeMock: vi.fn(),
  validateMock: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: vi.fn() },
}))

vi.mock('@/api/funds', () => ({ fundApi: fundApiMock }))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/utils/echarts', () => ({ use: vi.fn(), default: { use: vi.fn() } }))

import Budget from '@/views/funds/Budget.vue'

const budgetRow = {
  id: 1,
  year: 2024,
  category: '项目经费',
  budget_amount: 100,
  used_amount: 95,
  remaining_reason: '部分结余',
  remarks: '备注A',
  budget: 100,
  used: 95,
  remark: '备注A',
}

const budgetRow2 = {
  id: 2,
  year: 2024,
  category: '教育帮扶',
  budget_amount: 50,
  used_amount: 10,
  budget: 50,
  used: 10,
  remark: '',
}

const rawRows = [
  {
    id: 1,
    year: '2024',
    category: '项目经费',
    budget_amount: '100',
    used_amount: '95',
    remaining_reason: '部分结余',
    remarks: '备注A',
  },
  { id: 2, year: 2024, category: '教育帮扶', budget_amount: 50, used_amount: 10 },
]

function mountComp() {
  return mount(Budget, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'base-chart': {
          name: 'BaseChart',
          template: '<div class="base-chart-stub" />',
          props: ['option', 'height'],
        },
        'el-card': { template: '<div class="el-card-stub"><slot /></div>' },
        'el-table': {
          template:
            '<div class="el-table-stub"><slot name="empty" /><slot name="default" /><slot name="append" /></div>',
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>',
          data() {
            return {
              rowA: { ...budgetRow },
              rowB: { ...budgetRow2 },
              rowC: { id: 3, category: '零值行', budget: 0, used: 0, remark: '' },
            }
          },
        },
        'el-form': {
          name: 'ElForm',
          template: '<div class="el-form-stub"><slot /></div>',
          methods: {
            validate() {
              return validateMock()
            },
          },
        },
        'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>' },
        'el-input': {
          template:
            '<div class="el-input-stub" @click="$emit(\'update:modelValue\', \'V\')" />',
        },
        'el-input-number': {
          template:
            '<div class="el-input-number-stub" @click="$emit(\'update:modelValue\', 5)" />',
        },
        'el-select': {
          template:
            '<div class="el-select-stub" @click="$emit(\'update:modelValue\', 2023)"><slot /></div>',
        },
        'el-option': { template: '<div class="el-option-stub" />' },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-popconfirm': {
          template:
            '<div class="el-popconfirm-stub" @click="$emit(\'confirm\', rowA)"><slot name="reference" /></div>',
        },
        'el-progress': { template: '<div class="el-progress-stub" />' },
        'el-empty': { template: '<div class="el-empty-stub"><slot /></div>' },
        'el-dialog': {
          template:
            '<div class="el-dialog-stub" @click="$emit(\'update:modelValue\', false)"><slot /><slot name="footer" /></div>',
        },
        'el-row': { template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { template: '<div class="el-col-stub"><slot /></div>' },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  fundApiMock.listBudgets.mockResolvedValue({ items: rawRows, total: 2 })
  fundApiMock.createBudget.mockResolvedValue({})
  fundApiMock.updateBudget.mockResolvedValue({})
  fundApiMock.deleteBudget.mockResolvedValue({})
  validateMock.mockResolvedValue(true)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与加载', () => {
  it('onMounted 加载预算并映射', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(fundApiMock.listBudgets).toHaveBeenCalledWith(expect.any(Number))
    expect(vm.budgetData).toHaveLength(2)
    expect(vm.budgetData[0]).toEqual({
      id: 1,
      year: 2024,
      category: '项目经费',
      budget_amount: 100,
      used_amount: 95,
      remaining_reason: '部分结余',
      remarks: '备注A',
      budget: 100,
      used: 95,
      remark: '备注A',
    })
    expect(vm.budgetData[1].remaining_reason).toBeUndefined()
    expect(vm.budgetData[1].remark).toBe('')
  })

  it('watch selectedYear → 重新加载', async () => {
    const wrapper = mountComp()
    await flushPromises()
    fundApiMock.listBudgets.mockClear()
    ;(wrapper.vm as any).selectedYear = 2023
    await nextTick()
    await flushPromises()
    expect(fundApiMock.listBudgets).toHaveBeenCalledWith(2023)
  })

  it('loadBudgets 失败 → logger + 提示', async () => {
    fundApiMock.listBudgets.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('net')
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('listBudgets 无 items → 空数组', async () => {
    fundApiMock.listBudgets.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).budgetData).toEqual([])
  })

  it('loadBudgets 字段缺失走 || 兜底', async () => {
    fundApiMock.listBudgets.mockResolvedValue({
      items: [{ id: 9, budget_amount: null, used_amount: null }],
    })
    const wrapper = mountComp()
    await flushPromises()
    const row = (wrapper.vm as any).budgetData[0]
    expect(row.year).toBe(0)
    expect(row.category).toBe('')
    expect(row.budget_amount).toBe(0)
    expect(row.used_amount).toBe(0)
    expect(row.remaining_reason).toBeUndefined()
    expect(row.remarks).toBeUndefined()
    expect(row.remark).toBe('')
  })
})

describe('summary 与颜色函数', () => {
  it('summary 计算与 usageRateClass 三分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.summary.totalBudget).toBe('150')
    expect(vm.summary.totalUsed).toBe('105')
    expect(vm.summary.totalRemaining).toBe('45')
    expect(vm.summary.usageRate).toBe(70)
    expect(vm.usageRateClass).toBe('text-warning')

    vm.budgetData = [{ ...budgetRow, budget: 100, used: 99 }]
    await nextTick()
    expect(vm.summary.usageRate).toBe(99)
    expect(vm.usageRateClass).toBe('text-danger')

    vm.budgetData = [{ ...budgetRow, budget: 100, used: 30 }]
    await nextTick()
    expect(vm.usageRateClass).toBe('text-success')
  })

  it('summary 空数据 → 全 0', async () => {
    fundApiMock.listBudgets.mockResolvedValue({ items: [] })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.summary.totalBudget).toBe('0')
    expect(vm.summary.usageRate).toBe(0)
  })

  it('summary/gauge/getSummary 含零值行 → || 0 兜底', async () => {
    fundApiMock.listBudgets.mockResolvedValue({
      items: [{ id: 7, year: 2024, category: '零值', budget_amount: 0, used_amount: 0 }],
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.summary.totalBudget).toBe('0')
    expect(vm.summary.totalUsed).toBe('0')
    expect(vm.gaugeOption.series[0].data[0].value).toBe(0)
    const sums = vm.getSummary({ columns: [1, 2, 3, 4], data: vm.budgetData })
    expect(sums[1]).toBe('0')
    expect(sums[2]).toBe('0')
    expect(sums[3]).toBe('0')
  })

  it('getProgressColor 三分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getProgressColor(95)).toBe('#f56c6c')
    expect(vm.getProgressColor(75)).toBe('#e6a23c')
    expect(vm.getProgressColor(40)).toBe('#40916c')
  })

  it('getUsageRate：超 100 截断与 0 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getUsageRate({ budget: 10, used: 20 })).toBe(100)
    expect(vm.getUsageRate({ budget: 0, used: 5 })).toBe(0)
    expect(vm.getUsageRate({ budget: 100, used: 25 })).toBe(25)
  })

  it('gaugeOption 计算与 color 传递', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.gaugeOption.series[0].data[0].value).toBeCloseTo(70)
    expect(vm.gaugeOption.series[0].progress.itemStyle.color).toBe('#e6a23c')
  })

  it('getSummary 列分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const data = vm.budgetData
    const sums = vm.getSummary({ columns: [1, 2, 3, 4, 5], data })
    expect(sums[0]).toBe('合计')
    expect(sums[1]).toBe('150')
    expect(sums[2]).toBe('105')
    expect(sums[3]).toBe('45')
    expect(sums[4]).toBe('')
  })
})

describe('新增/编辑对话框', () => {
  it('handleAddBudget → 打开新增对话框', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleAddBudget()
    expect(vm.dialogVisible).toBe(true)
    expect(vm.editingItem).toBeNull()
    expect(vm.form.category).toBe('')
    expect(vm.form.year).toBe(vm.selectedYear)
  })

  it('openDialog(row) 编辑回填', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openDialog(budgetRow)
    expect(vm.editingItem).toEqual(budgetRow)
    expect(vm.form.category).toBe('项目经费')
    expect(vm.form.budget_amount).toBe(100)
    expect(vm.form.remaining_reason).toBe('部分结余')
    expect(vm.dialogVisible).toBe(true)
  })

  it('openDialog(row) 无 remaining_reason/remarks → || 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openDialog({ ...budgetRow2, year: 2024, budget_amount: 50, used_amount: 10 })
    expect(vm.form.remaining_reason).toBe('')
    expect(vm.form.remarks).toBe('')
  })

  it('handleSaveBudget：无 formRef → 直接返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.formRef = null
    await vm.handleSaveBudget()
    expect(fundApiMock.createBudget).not.toHaveBeenCalled()
  })

  it('handleSaveBudget：校验失败 → 返回', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    validateMock.mockResolvedValueOnce(false)
    await vm.handleSaveBudget()
    expect(fundApiMock.createBudget).not.toHaveBeenCalled()
  })

  it('handleSaveBudget：编辑无 id → 错误', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.editingItem = { ...budgetRow, id: undefined }
    await vm.handleSaveBudget()
    expect(ElMessage.error).toHaveBeenCalledWith('无法保存：记录 ID 无效')
    expect(fundApiMock.updateBudget).not.toHaveBeenCalled()
  })

  it('handleSaveBudget：更新成功', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.editingItem = budgetRow
    fundApiMock.listBudgets.mockClear()
    await vm.handleSaveBudget()
    expect(fundApiMock.updateBudget).toHaveBeenCalledWith(1, vm.form)
    expect(ElMessage.success).toHaveBeenCalledWith('更新成功')
    expect(vm.dialogVisible).toBe(false)
    expect(fundApiMock.listBudgets).toHaveBeenCalled()
  })

  it('handleSaveBudget：新增成功', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleSaveBudget()
    expect(fundApiMock.createBudget).toHaveBeenCalledWith(vm.form)
    expect(ElMessage.success).toHaveBeenCalledWith('创建成功')
    expect(vm.dialogVisible).toBe(false)
  })

  it('handleSaveBudget：保存失败', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fundApiMock.createBudget.mockRejectedValueOnce(new Error('net'))
    await vm.handleSaveBudget()
    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
    expect(vm.saving).toBe(false)
  })
})

describe('删除预算', () => {
  it('无 id → 错误', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).handleDeleteBudget({ budget: 1, used: 0, remark: '' })
    expect(ElMessage.error).toHaveBeenCalledWith('无法删除：记录 ID 无效')
  })

  it('删除成功 → 提示 + 刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fundApiMock.listBudgets.mockClear()
    await vm.handleDeleteBudget(budgetRow)
    expect(fundApiMock.deleteBudget).toHaveBeenCalledWith(1)
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    expect(fundApiMock.listBudgets).toHaveBeenCalled()
  })

  it('删除失败 → logger + 错误', async () => {
    const wrapper = mountComp()
    await flushPromises()
    fundApiMock.deleteBudget.mockRejectedValueOnce(new Error('net'))
    await (wrapper.vm as any).handleDeleteBudget(budgetRow)
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('net')
  })
})

describe('模板事件', () => {
  it('返回按钮 → pushSafe /funds', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('返回经费管理'))
    await btn!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/funds')
  })

  it('新增预算按钮 → 打开弹窗', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('新增预算'))
    await btn!.trigger('click')
    expect((wrapper.vm as any).dialogVisible).toBe(true)
  })

  it('编辑按钮 → openDialog(row)', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('编辑'))
    await btn!.trigger('click')
    expect((wrapper.vm as any).dialogVisible).toBe(true)
    expect((wrapper.vm as any).editingItem).toEqual(budgetRow)
  })

  it('删除 popconfirm confirm → handleDeleteBudget', async () => {
    const wrapper = mountComp()
    await flushPromises()
    fundApiMock.listBudgets.mockClear()
    await wrapper.find('.el-popconfirm-stub').trigger('click')
    await flushPromises()
    expect(fundApiMock.deleteBudget).toHaveBeenCalledWith(1)
  })

  it('年份选择 v-model → selectedYear 更新触发 watch', async () => {
    const wrapper = mountComp()
    await flushPromises()
    fundApiMock.listBudgets.mockClear()
    await wrapper.find('.el-select-stub').trigger('click')
    await flushPromises()
    expect((wrapper.vm as any).selectedYear).toBe(2023)
    expect(fundApiMock.listBudgets).toHaveBeenCalledWith(2023)
  })

  it('表单控件 v-model 更新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    for (const el of wrapper.findAll('.el-input-stub')) {
      await el.trigger('click')
    }
    for (const el of wrapper.findAll('.el-input-number-stub')) {
      await el.trigger('click')
    }
    await flushPromises()
    expect(vm.form.category).toBe('V')
    expect(vm.form.remaining_reason).toBe('V')
    expect(vm.form.remarks).toBe('V')
    expect(vm.form.year).toBe(5)
    expect(vm.form.budget_amount).toBe(5)
    expect(vm.form.used_amount).toBe(5)
  })

  it('保存/取消按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    fundApiMock.createBudget.mockClear()
    const save = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('保存'))
    await save!.trigger('click')
    await flushPromises()
    expect(fundApiMock.createBudget).toHaveBeenCalled()

    vm.dialogVisible = true
    const cancel = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('取消'))
    await cancel!.trigger('click')
    expect(vm.dialogVisible).toBe(false)
  })
})
