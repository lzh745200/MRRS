/**
 * views/handover/Index.vue 覆盖率攻坚（四指标 100%）
 *
 * 覆盖：清单加载（成功/空/null/失败）、接任人加载（成功/null/失败）、
 * 勾选（逐项/整组/半选/取消）、执行校验、取消确认、执行成功（含备注/无备注）、
 * 执行失败（带 userMessage / 兜底文案）、交接单导出（即时/历史行/空值兜底）、
 * 历史加载（成功/空/null/失败）、切页签与分页、全部 v-model 与事件处理器。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  getHandoverInventory: vi.fn(),
  getHandoverCandidates: vi.fn(),
  getHandoverHistory: vi.fn(),
  executeHandover: vi.fn(),
  exportToPDF: vi.fn(),
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  messageBox: { confirm: vi.fn() },
}))

vi.mock('@/api/handover', () => ({
  ASSET_TYPE_LABELS: {
    village: '帮扶村',
    project: '帮扶项目',
    todo: '待办事项',
    approval: '审批中申请',
  },
  ASSET_ROLE_LABELS: {
    owner: '责任人',
    approver: '待我审批',
    submitter: '我发起',
    both: '我发起且待我审批',
  },
  getHandoverInventory: mocks.getHandoverInventory,
  getHandoverCandidates: mocks.getHandoverCandidates,
  getHandoverHistory: mocks.getHandoverHistory,
  executeHandover: mocks.executeHandover,
}))

vi.mock('@/utils/exportUtil', () => ({
  default: { exportToPDF: mocks.exportToPDF },
}))

vi.mock('element-plus', () => ({
  ElMessage: mocks.message,
  ElMessageBox: mocks.messageBox,
}))

import HandoverIndex from '@/views/handover/Index.vue'

const INVENTORY = {
  total: 5,
  generated_at: '2026-10-17T00:00:00Z',
  groups: [
    {
      type: 'village',
      label: '帮扶村',
      count: 2,
      items: [
        { type: 'village', id: 1, title: '幸福村', subtitle: '贵州省 / 贵阳市', role: 'owner' },
        { type: 'village', id: 2, title: '无地区村', subtitle: null, role: 'owner' },
      ],
    },
    {
      type: 'project',
      label: '帮扶项目',
      count: 1,
      items: [
        { type: 'project', id: 3, title: '道路硬化', subtitle: '状态：进行中', role: 'owner' },
      ],
    },
    {
      type: 'todo',
      label: '待办事项',
      count: 1,
      items: [
        { type: 'todo', id: 4, title: '走访农户', subtitle: '截止 2026-11-01', role: 'owner' },
      ],
    },
    {
      type: 'approval',
      label: '审批中申请',
      count: 1,
      items: [{ type: 'approval', id: 5, title: '项目变更', subtitle: '待审批', role: 'both' }],
    },
  ],
}

const CANDIDATES = {
  items: [
    { id: 9, username: 'lisi', full_name: '李四' },
    { id: 10, username: 'wangwu', full_name: null },
  ],
  total: 2,
}

const RECEIPT = {
  record_id: 10,
  record_no: 'HO-20261017-100000-ABCD1234',
  from_user: { id: 7, username: 'zhangsan' },
  to_user: { id: 9, username: 'lisi' },
  created_at: '2026-10-17T10:00:00+08:00',
  note: '轮岗交接',
  items: [{ type: 'village', id: 1, title: '幸福村', role: 'owner' }],
  counts: { village: 1, project: 0, todo: 0, approval: 0 },
  total: 1,
}

// 表格列桩注入的三行样本：A 全字段；B 空值；C 空串 + 未知类型/角色（覆盖回退分支）
const ROW_A = {
  id: 10,
  record_no: 'HO-1',
  from_username: 'zhangsan',
  to_username: 'lisi',
  total: 2,
  log_date: '2026-10-17',
  type: 'village',
  title: '幸福村',
  role: 'owner',
  items: [{ type: 'village', id: 1, title: '幸福村', role: 'owner' }],
}
const ROW_B = {
  id: 11,
  record_no: null,
  from_username: null,
  to_username: null,
  total: 0,
  log_date: null,
  type: 'project',
  title: '道路硬化',
  role: null,
  items: null,
}
const ROW_C = {
  id: 12,
  record_no: '',
  from_username: '',
  to_username: '',
  total: 1,
  log_date: '',
  type: 'alien',
  title: '历史项',
  role: 'supervisor',
}

function modelStub(tag: string) {
  return {
    name: tag,
    props: { modelValue: { default: '' } },
    emits: ['update:modelValue', 'change'],
    template: `<div class="${tag}-stub"><input class="${tag}-input" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" /><slot /></div>`,
  }
}

const mountOptions = {
  global: {
    renderStubDefaultSlot: true,
    stubs: {
      EmptyState: {
        name: 'EmptyState',
        props: ['description'],
        template: `<div class="empty-stub">{{ description }}</div>`,
      },
      'el-tabs': {
        name: 'ElTabs',
        props: ['modelValue'],
        emits: ['update:modelValue', 'tab-change'],
        template: `<div class="el-tabs-stub"><button class="tab-history" @click="$emit('update:modelValue', 'history');$emit('tab-change', 'history')" /><button class="tab-execute" @click="$emit('update:modelValue', 'execute');$emit('tab-change', 'execute')" /><slot /></div>`,
      },
      'el-tab-pane': {
        name: 'ElTabPane',
        template: `<div class="el-tab-pane-stub"><slot /></div>`,
      },
      'el-checkbox': {
        name: 'ElCheckbox',
        props: { modelValue: { default: false }, indeterminate: { default: false } },
        emits: ['update:modelValue', 'change'],
        template: `<label class="el-checkbox-stub"><input type="checkbox" :checked="modelValue" @change="$emit('change', $event.target.checked)" /><slot /></label>`,
      },
      'el-select': {
        name: 'ElSelect',
        props: ['modelValue'],
        emits: ['update:modelValue', 'change'],
        template: `<div class="el-select-stub"><button class="select-pick" @click="$emit('update:modelValue', 9)" /><slot /></div>`,
      },
      'el-input': modelStub('el-input'),
      'el-pagination': {
        name: 'ElPagination',
        props: ['total', 'currentPage', 'pageSize'],
        emits: ['current-change', 'update:currentPage'],
        template: `<div class="el-pagination-stub"><button class="pg-next" @click="$emit('current-change', 2)" /></div>`,
      },
      'el-dialog': {
        name: 'ElDialog',
        props: ['modelValue', 'title'],
        emits: ['update:modelValue'],
        template: `<div class="el-dialog-stub"><div class="dialog-title">{{ title }}</div><button class="dialog-x" @click="$emit('update:modelValue', false)" /><slot /><slot name="footer" /></div>`,
      },
      'el-table': {
        name: 'ElTable',
        template: `<div class="el-table-stub"><slot /></div>`,
      },
      'el-table-column': {
        name: 'ElTableColumn',
        template: `<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>`,
        data() {
          return { rowA: { ...ROW_A }, rowB: { ...ROW_B }, rowC: { ...ROW_C } }
        },
      },
    },
  },
}

function mountComp() {
  return mount(HandoverIndex, mountOptions as any)
}

async function mountAndFlush() {
  const w = mountComp()
  await flushPromises()
  return w
}

function buttonByText(w: any, text: string) {
  return w.findAll('el-button-stub').find((b: any) => b.text().trim() === text)
}

function dialogButtons(w: any) {
  return w.findAll('.el-dialog-stub el-button-stub')
}

function historyButtons(w: any) {
  return w
    .findAll('.el-table-stub el-button-stub')
    .filter((b: any) => b.text().trim() === '导出交接单')
}

async function selectFirstItem(w: any) {
  const checkbox = w.find('.asset-item .el-checkbox-stub input')
  await checkbox.setValue(true)
  return w.vm as any
}

describe('views/handover/Index.vue（工作移交）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getHandoverInventory.mockResolvedValue(INVENTORY)
    mocks.getHandoverCandidates.mockResolvedValue(CANDIDATES)
    mocks.getHandoverHistory.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 })
    mocks.executeHandover.mockResolvedValue(RECEIPT)
    mocks.messageBox.confirm.mockResolvedValue('confirm')
  })

  it('挂载加载：清单/接任人 + 分组与条目渲染（含 subtitle 有无分支）', async () => {
    const w = await mountAndFlush()
    const vm = w.vm as any

    expect(mocks.getHandoverInventory).toHaveBeenCalledTimes(1)
    expect(mocks.getHandoverCandidates).toHaveBeenCalledWith({ limit: 200 })
    expect(vm.inventory.total).toBe(5)
    expect(vm.candidates).toHaveLength(2)
    expect(vm.inventoryLoading).toBe(false)

    expect(w.text()).toContain('可移交工作共')
    expect(w.text()).toContain('已勾选 0 项')
    expect(w.text()).toContain('帮扶村（2）')
    expect(w.text()).toContain('贵州省 / 贵阳市')
    expect(w.findAll('.asset-item')).toHaveLength(5)
    // subtitle 为空时不渲染副标题 span（分支覆盖）
    expect(w.findAll('.asset-subtitle')).toHaveLength(4)
    // 接任人下拉两项（有姓名/无姓名两种文案）
    expect(w.findAll('el-option-stub')).toHaveLength(2)

    // 展示辅助函数全分支
    expect(vm.assetTypeLabel('village')).toBe('帮扶村')
    expect(vm.assetTypeLabel('alien')).toBe('alien')
    expect(vm.roleLabel('owner')).toBe('责任人')
    expect(vm.roleLabel('supervisor')).toBe('supervisor')
    expect(vm.roleLabel('')).toBe('-')
    expect(vm.candidateLabel({ id: 9, username: 'lisi', full_name: '李四' })).toBe('李四（lisi）')
    expect(vm.candidateLabel({ id: 10, username: 'wangwu', full_name: null })).toBe('wangwu')
  })

  it('空清单显示 EmptyState 且总数为 0', async () => {
    mocks.getHandoverInventory.mockResolvedValue({ groups: [], total: 0 })
    const w = await mountAndFlush()
    expect(w.find('.empty-stub').text()).toBe('当前没有可移交的工作')
    expect(w.text()).toContain('可移交工作共')
    expect((w.vm as any).inventory.total).toBe(0)
  })

  it('清单接口返回 null 时回落空清单', async () => {
    mocks.getHandoverInventory.mockResolvedValue(null)
    const w = await mountAndFlush()
    expect((w.vm as any).inventory.total).toBe(0)
  })

  it('清单加载失败提示（服务端文案 / 兜底文案两分支）', async () => {
    mocks.getHandoverInventory.mockRejectedValueOnce({ userMessage: '网络异常' })
    const w = await mountAndFlush()
    expect(mocks.message.error).toHaveBeenCalledWith('网络异常')

    mocks.getHandoverInventory.mockRejectedValueOnce(new Error('boom'))
    await (w.vm as any).loadInventory()
    expect(mocks.message.error).toHaveBeenCalledWith('加载可移交清单失败')
    expect((w.vm as any).inventoryLoading).toBe(false)
  })

  it('接任人 null 兜底与加载失败提示', async () => {
    mocks.getHandoverCandidates.mockResolvedValueOnce(null).mockRejectedValueOnce(new Error('x'))
    const w = await mountAndFlush()
    expect((w.vm as any).candidates).toEqual([])
    await (w.vm as any).loadCandidates()
    expect(mocks.message.error).toHaveBeenCalledWith('加载接任人列表失败')
  })

  it('逐项勾选 / 整组勾选 / 半选状态', async () => {
    const w = await mountAndFlush()
    const vm = w.vm as any
    const villageGroup = vm.inventory.groups[0]

    // 初始：未选
    expect(vm.isGroupChecked(villageGroup)).toBe(false)
    expect(vm.isGroupIndeterminate(villageGroup)).toBe(false)
    expect(vm.selectedTotal).toBe(0)

    // 逐项勾选第一项
    const firstCheckbox = w.findAll('.asset-item .el-checkbox-stub input')[0]
    await firstCheckbox.setValue(true)
    expect(vm.selection.village).toEqual([1])
    expect(vm.isGroupIndeterminate(villageGroup)).toBe(true)
    expect(vm.selectedTotal).toBe(1)

    // 再勾第二项 → 整组全选（isGroupChecked true / indeterminate false）
    const secondCheckbox = w.findAll('.asset-item .el-checkbox-stub input')[1]
    await secondCheckbox.setValue(true)
    expect(vm.selection.village).toEqual([1, 2])
    expect(vm.isGroupChecked(villageGroup)).toBe(true)
    expect(vm.isGroupIndeterminate(villageGroup)).toBe(false)
    expect(vm.selectedTotal).toBe(2)

    // 取消第二项 → 半选
    await secondCheckbox.setValue(false)
    expect(vm.selection.village).toEqual([1])
    expect(vm.isGroupIndeterminate(villageGroup)).toBe(true)

    // 整组勾选（change 事件 true → 全选）
    const groupCheckbox = w.find('.group-checkbox input')
    await groupCheckbox.setValue(true)
    expect(vm.selection.village).toEqual([1, 2])
    expect(vm.selectedTotal).toBe(2)

    // 整组取消（change 事件 false → 清空）
    await groupCheckbox.setValue(false)
    expect(vm.selection.village).toEqual([])
    expect(vm.selectedTotal).toBe(0)
  })

  it('执行校验：未勾选 / 未选接任人', async () => {
    const w = await mountAndFlush()
    await buttonByText(w, '确认移交').trigger('click')
    expect(mocks.message.warning).toHaveBeenCalledWith('请先勾选要移交的工作项')

    const checkbox = w.find('.asset-item .el-checkbox-stub input')
    await checkbox.setValue(true)
    await buttonByText(w, '确认移交').trigger('click')
    expect(mocks.message.warning).toHaveBeenCalledWith('请选择接任人')
    expect(mocks.executeHandover).not.toHaveBeenCalled()
  })

  it('确认框取消则不执行移交', async () => {
    const w = await mountAndFlush()
    const vm = w.vm as any
    const checkbox = w.find('.asset-item .el-checkbox-stub input')
    await checkbox.setValue(true)
    await w.find('.select-pick').trigger('click')
    mocks.messageBox.confirm.mockRejectedValueOnce('cancel')

    await buttonByText(w, '确认移交').trigger('click')
    await flushPromises()
    expect(mocks.executeHandover).not.toHaveBeenCalled()
    expect(vm.submitting).toBe(false)
  })

  it('执行成功：载荷/交接单弹窗/导出/重置/刷新', async () => {
    const w = await mountAndFlush()
    const vm = w.vm as any

    const checkbox = w.find('.asset-item .el-checkbox-stub input')
    await checkbox.setValue(true)
    await w.find('.select-pick').trigger('click')
    await w.find('.el-input-input').setValue('轮岗交接')

    await buttonByText(w, '确认移交').trigger('click')
    await flushPromises()

    expect(mocks.messageBox.confirm).toHaveBeenCalledTimes(1)
    expect(mocks.executeHandover).toHaveBeenCalledWith({
      to_user_id: 9,
      scope: ['village'],
      item_ids: { village: [1] },
      note: '轮岗交接',
    })
    expect(vm.receipt.record_no).toBe(RECEIPT.record_no)
    expect(vm.receiptVisible).toBe(true)
    expect(mocks.message.success).toHaveBeenCalledWith('工作移交完成')
    // 执行后重置输入并刷新清单/历史
    expect(vm.selection.village).toEqual([])
    expect(vm.note).toBe('')
    expect(vm.toUserId).toBeNull()
    expect(mocks.getHandoverInventory).toHaveBeenCalledTimes(2)
    expect(mocks.getHandoverHistory).toHaveBeenCalled()
    // 弹窗内容
    expect(w.find('.el-dialog-stub').text()).toContain(RECEIPT.record_no)
    expect(w.find('.el-dialog-stub').text()).toContain('备注：轮岗交接')
    expect(w.find('.el-dialog-stub').text()).toContain('移交人：zhangsan')
    // 交接单表格列模板：已知类型/角色 + 空角色 '-' + 未知类型/角色回退
    expect(w.find('.el-dialog-stub').text()).toContain('帮扶村')
    expect(w.find('.el-dialog-stub').text()).toContain('责任人')
    expect(w.find('.el-dialog-stub').text()).toContain('alien')
    expect(w.find('.el-dialog-stub').text()).toContain('supervisor')

    // 导出交接单（PDF）
    const dialogExport = dialogButtons(w).find((b: any) => b.text().trim() === '导出交接单')
    await dialogExport.trigger('click')
    expect(mocks.exportToPDF).toHaveBeenCalledTimes(1)
    const [title, rows, headers] = mocks.exportToPDF.mock.calls[0]
    expect(title).toContain(RECEIPT.record_no)
    expect(title).toContain('zhangsan → lisi')
    expect(rows).toEqual([{ type: '帮扶村', title: '幸福村', role: '责任人' }])
    expect(headers).toEqual({ type: '资产类型', title: '名称', role: '归属角色' })
    expect(mocks.message.success).toHaveBeenCalledWith('交接单已生成')

    // 关闭弹窗（v-model 处理器）
    const closeBtn = dialogButtons(w).find((b: any) => b.text().trim() === '关闭')
    await closeBtn.trigger('click')
    expect(vm.receiptVisible).toBe(false)
    // 对话框自身 close 事件（dialog stub 的 update:modelValue）
    await w.find('.dialog-x').trigger('click')
    expect(vm.receiptVisible).toBe(false)
  })

  it('执行成功（无备注 → note 传 null / 不渲染备注行）', async () => {
    const receiptWithoutNote = { ...RECEIPT, note: null }
    mocks.executeHandover.mockResolvedValueOnce(receiptWithoutNote)
    const w = await mountAndFlush()
    const vm = w.vm as any
    const checkbox = w.find('.asset-item .el-checkbox-stub input')
    await checkbox.setValue(true)
    await w.find('.select-pick').trigger('click')

    await buttonByText(w, '确认移交').trigger('click')
    await flushPromises()

    expect(mocks.executeHandover).toHaveBeenCalledWith(expect.objectContaining({ note: null }))
    expect(vm.receipt.note).toBeNull()
    expect(w.findAll('.receipt-note')).toHaveLength(0)
  })

  it('执行失败：服务端文案 / 兜底文案两分支', async () => {
    mocks.executeHandover.mockRejectedValueOnce({ userMessage: '跨组织移交被拒绝' })
    const w = await mountAndFlush()
    const vm = w.vm as any
    await selectFirstItem(w)
    vm.toUserId = 9
    await buttonByText(w, '确认移交').trigger('click')
    await flushPromises()
    expect(mocks.message.error).toHaveBeenCalledWith('跨组织移交被拒绝')
    expect(vm.submitting).toBe(false)

    mocks.executeHandover.mockRejectedValueOnce(new Error('boom'))
    await buttonByText(w, '确认移交').trigger('click')
    await flushPromises()
    expect(mocks.message.error).toHaveBeenCalledWith('工作移交失败')
  })

  it('交接单导出空值兜底：null 目标 / 历史行缺字段', async () => {
    const w = await mountAndFlush()
    const vm = w.vm as any

    vm.exportReceipt(null)
    expect(mocks.exportToPDF).not.toHaveBeenCalled()

    // 历史行缺 from/to/record_no/items → 全部回退
    vm.exportReceipt({ id: 1, total: 0, counts: {} })
    expect(mocks.exportToPDF).toHaveBeenCalledTimes(1)
    const [title, rows] = mocks.exportToPDF.mock.calls[0]
    expect(title).toBe('工作交接单 未编号（- → -）')
    expect(rows).toEqual([])

    // 即时交接单缺 from_user/to_user（可选链 false 分支）
    vm.receipt = {
      record_no: '',
      items: [{ type: 'project', id: 3, title: '道路硬化', role: 'approver' }],
      counts: { village: 0, project: 1, todo: 0, approval: 0 },
      total: 1,
    }
    vm.receiptVisible = true
    await flushPromises()
    expect(w.find('.receipt-meta').text()).toContain('移交人：')
  })

  it('历史：切页签加载 / 空态 / 表格行导出 / 分页', async () => {
    mocks.getHandoverHistory.mockResolvedValueOnce({
      items: [ROW_A, ROW_B, ROW_C],
      total: 3,
      page: 1,
      page_size: 10,
    })
    const w = await mountAndFlush()
    const vm = w.vm as any

    // 初始历史为空 → EmptyState
    expect(w.find('.empty-stub').text()).toBe('暂无移交记录')

    // 切到历史页签（tab-change → loadHistory）
    await w.find('.tab-history').trigger('click')
    await flushPromises()
    expect(mocks.getHandoverHistory).toHaveBeenCalledWith({ page: 1, page_size: 10 })
    expect(vm.historyItems).toHaveLength(3)
    expect(vm.historyTotal).toBe(3)
    expect(w.text()).toContain('zhangsan → lisi')

    // 行内导出：A 完整 / B 空值 / C 空串与未知角色
    const buttons = historyButtons(w)
    expect(buttons).toHaveLength(3)
    await buttons[0].trigger('click')
    expect(mocks.exportToPDF.mock.calls[0][0]).toContain('HO-1')
    await buttons[1].trigger('click')
    expect(mocks.exportToPDF.mock.calls[1][0]).toContain('未编号')
    await buttons[2].trigger('click')
    expect(mocks.exportToPDF.mock.calls[2][0]).toContain('未编号')

    // 分页：current-change → page=2 重新拉取
    await w.find('.pg-next').trigger('click')
    await flushPromises()
    expect(vm.historyQuery.page).toBe(2)
    expect(mocks.getHandoverHistory).toHaveBeenLastCalledWith({ page: 2, page_size: 10 })

    // 返回执行页签不触发历史加载
    const callsBefore = mocks.getHandoverHistory.mock.calls.length
    await w.find('.tab-execute').trigger('click')
    await flushPromises()
    await vm.handleTabChange('execute')
    expect(mocks.getHandoverHistory.mock.calls.length).toBe(callsBefore)
  })

  it('历史加载：null 兜底 / 失败提示', async () => {
    mocks.getHandoverHistory.mockResolvedValueOnce(null)
    const w = await mountAndFlush()
    const vm = w.vm as any
    await vm.loadHistory()
    expect(vm.historyItems).toEqual([])
    expect(vm.historyTotal).toBe(0)

    mocks.getHandoverHistory.mockRejectedValueOnce(new Error('boom'))
    await vm.loadHistory()
    expect(mocks.message.error).toHaveBeenCalledWith('加载移交历史失败')
    expect(vm.historyLoading).toBe(false)
  })

  it('刷新按钮重新加载清单与接任人', async () => {
    const w = await mountAndFlush()
    await buttonByText(w, '刷新').trigger('click')
    await flushPromises()
    expect(mocks.getHandoverInventory).toHaveBeenCalledTimes(2)
    expect(mocks.getHandoverCandidates).toHaveBeenCalledTimes(2)
  })
})
