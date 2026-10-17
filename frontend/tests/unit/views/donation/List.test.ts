/**
 * views/donation/List.vue 覆盖率攻坚（四指标 100%）
 *
 * 覆盖：加载成功/空/失败、统计兜底、选项加载（三种名称回退 + null 兜底 + 失败）、
 * 展示辅助函数全分支、筛选/回车/重置/分页、新建/编辑（三种去向映射、附件回填）、
 * 校验全分支、提交成功/失败、删除三态、去向切换清空、全部 v-model 处理器。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  getDonations: vi.fn(),
  getDonationStats: vi.fn(),
  getDonation: vi.fn(),
  createDonation: vi.fn(),
  updateDonation: vi.fn(),
  deleteDonation: vi.fn(),
  getSupportedVillages: vi.fn(),
  schoolList: vi.fn(),
  projectList: vi.fn(),
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  messageBox: { confirm: vi.fn() },
}))

vi.mock('@/api/donations', () => ({
  DONATION_CATEGORIES: [
    { value: 'book', label: '图书' },
    { value: 'equipment', label: '设备' },
    { value: 'material', label: '物资' },
  ],
  DONATION_DESTINATIONS: [
    { value: 'village', label: '帮扶村' },
    { value: 'school', label: '帮扶学校' },
    { value: 'project', label: '项目' },
  ],
  getDonations: mocks.getDonations,
  getDonationStats: mocks.getDonationStats,
  getDonation: mocks.getDonation,
  createDonation: mocks.createDonation,
  updateDonation: mocks.updateDonation,
  deleteDonation: mocks.deleteDonation,
}))

vi.mock('@/api/supportedVillage', () => ({
  getSupportedVillages: mocks.getSupportedVillages,
}))

vi.mock('@/api/schools', () => ({
  schoolsApi: { list: mocks.schoolList },
}))

vi.mock('@/api/projects', () => ({
  projectsApi: { list: mocks.projectList },
}))

vi.mock('element-plus', () => ({
  ElMessage: mocks.message,
  ElMessageBox: mocks.messageBox,
}))

import DonationList from '@/views/donation/List.vue'

const ROW_A = {
  id: 1,
  name: '课外图书',
  category: 'book',
  quantity: 120,
  unit: '本',
  valuation: 3.5,
  source_unit: '某单位',
  destination_type: 'village',
  village_id: 11,
  school_id: null,
  project_id: null,
  destination_name: '幸福村',
  delivery_date: '2026-03-01',
  receiver: '张三',
  attachments: [{ url: 'https://x/a.pdf', file_name: 'a.pdf' }],
  remark: '备注A',
}
const ROW_B = {
  id: 2,
  name: '教学设备',
  category: 'unknown-cat',
  quantity: 2,
  unit: null,
  valuation: 10,
  source_unit: null,
  destination_type: 'school',
  village_id: null,
  school_id: 22,
  project_id: null,
  destination_name: null,
  delivery_date: null,
  receiver: null,
  attachments: null,
  remark: null,
}
const ROW_C = {
  id: 3,
  name: '项目物资',
  category: 'material',
  quantity: 5,
  unit: '件',
  valuation: 1,
  source_unit: '某会',
  destination_type: 'project',
  village_id: null,
  school_id: null,
  project_id: 33,
  destination_name: '项目甲',
  delivery_date: '2026-04-01',
  receiver: '李四',
  attachments: [],
  remark: 'r',
}

function modelStub(tag: string) {
  return {
    name: tag,
    props: { modelValue: { default: '' } },
    emits: ['update:modelValue', 'change'],
    template:
      `<div class="${tag}-wrapper">` +
      `<input class="${tag}-input" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" @change="$emit('change')" />` +
      `<slot /></div>`,
  }
}

const mountOptions = {
  global: {
    renderStubDefaultSlot: true,
    stubs: {
      EmptyState: { name: 'EmptyState', template: '<div class="empty-stub" />' },
      'el-form': { name: 'ElForm', template: '<form class="form-stub"><slot /></form>' },
      'el-form-item': {
        name: 'ElFormItem',
        template: '<div class="form-item-stub"><slot /></div>',
      },
      'el-input': modelStub('el-input'),
      'el-select': modelStub('el-select'),
      'el-date-picker': modelStub('el-date-picker'),
      'el-input-number': modelStub('el-input-number'),
      'el-dialog': {
        name: 'ElDialog',
        props: ['modelValue', 'title'],
        emits: ['update:modelValue'],
        template:
          '<div class="el-dialog-stub">' +
          '<div class="dialog-title">{{ title }}</div>' +
          '<button class="dialog-close" @click="$emit(\'update:modelValue\', false)">x</button>' +
          '<slot /><slot name="footer" /></div>',
      },
      'el-table': {
        name: 'ElTable',
        template: '<div class="el-table-stub"><slot name="empty" /><slot /></div>',
      },
      'el-table-column': {
        name: 'ElTableColumn',
        template:
          '<div class="el-table-column-stub">' +
          '<slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" />' +
          '</div>',
        data() {
          return { rowA: { ...ROW_A }, rowB: { ...ROW_B }, rowC: { ...ROW_C } }
        },
      },
      'el-pagination': {
        name: 'ElPagination',
        emits: ['current-change', 'size-change'],
        template:
          '<div class="el-pagination-stub">' +
          '<button class="pg-page" @click="$emit(\'current-change\', 3)" />' +
          '<button class="pg-size" @click="$emit(\'size-change\', 50)" />' +
          '</div>',
      },
    },
  },
}

function mountComp() {
  return mount(DonationList, mountOptions as any)
}

function buttonByText(w: any, text: string) {
  return w.findAll('el-button-stub').find((b: any) => b.text().trim() === text)
}

function statsFixture() {
  return {
    total: 3,
    villages: 1,
    schools: 1,
    projects: 1,
    books: 1,
    equipment: 1,
    materials: 1,
    quantity: 127,
    valuation: 14.5,
  }
}

async function mountAndFlush() {
  const w = mountComp()
  await flushPromises()
  return w
}

describe('views/donation/List.vue（捐赠物资台账）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getDonations.mockResolvedValue({
      items: [ROW_A, ROW_B, ROW_C],
      total: 3,
      page: 1,
      page_size: 20,
    })
    mocks.getDonationStats.mockResolvedValue(statsFixture())
    mocks.getSupportedVillages.mockResolvedValue({
      items: [{ id: 11, village_name: '幸福村' }, { id: 12, name: '乙村' }, { id: 13 }],
    })
    mocks.schoolList.mockResolvedValue({
      items: [{ id: 22, name: '实验小学' }, { id: 23, school_name: '第二小学' }, { id: 24 }],
    })
    mocks.projectList.mockResolvedValue({
      items: [{ id: 33, name: '项目甲' }, { id: 34, project_name: '项目乙' }, { id: 35 }],
    })
    mocks.createDonation.mockResolvedValue({ id: 100 })
    mocks.updateDonation.mockResolvedValue({ id: 100 })
    mocks.deleteDonation.mockResolvedValue({ id: 1 })
    mocks.messageBox.confirm.mockResolvedValue('confirm')
  })

  it('挂载即加载：渲染统计 / 表格 / 选项映射回退', async () => {
    const w = await mountAndFlush()
    expect(mocks.getDonations).toHaveBeenCalledTimes(1)
    const vm = w.vm as any
    expect(vm.stats.total).toBe(3)
    expect(w.text()).toContain('图书 1')
    expect(w.text()).toContain('折价合计 14.5 万元')
    // 表格行模板（经济/设备/物资三行）
    expect(w.findAll('.el-table-column-stub').length).toBeGreaterThan(0)
    expect(w.text()).toContain('帮扶村：幸福村') // destination_name 存在
    expect(w.text()).toContain('帮扶学校') // 无 destination_name
    expect(w.text()).toContain('unknown-cat') // 未知类别回退原值
    // 选项名称三级回退
    expect(vm.villages).toEqual([
      { id: 11, label: '幸福村' },
      { id: 12, label: '乙村' },
      { id: 13, label: '村#13' },
    ])
    expect(vm.schools).toEqual([
      { id: 22, label: '实验小学' },
      { id: 23, label: '第二小学' },
      { id: 24, label: '学校#24' },
    ])
    expect(vm.projects).toEqual([
      { id: 33, label: '项目甲' },
      { id: 34, label: '项目乙' },
      { id: 35, label: '项目#35' },
    ])
  })

  it('空列表显示 EmptyState；统计为 null 时回落零值', async () => {
    mocks.getDonations.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
    mocks.getDonationStats.mockResolvedValue(null)
    const w = await mountAndFlush()
    expect(w.find('.empty-stub').exists()).toBe(true)
    expect((w.vm as any).stats.total).toBe(0)
    expect((w.vm as any).items).toEqual([])
    expect((w.vm as any).total).toBe(0)
  })

  it('列表接口返回 null 时字段兜底', async () => {
    mocks.getDonations.mockResolvedValue(null)
    const w = await mountAndFlush()
    expect((w.vm as any).items).toEqual([])
    expect((w.vm as any).total).toBe(0)
  })

  it('加载失败提示', async () => {
    mocks.getDonations.mockRejectedValue(new Error('boom'))
    await mountAndFlush()
    expect(mocks.message.error).toHaveBeenCalledWith('加载捐赠物资台账失败')
  })

  it('选项为空时回落空数组', async () => {
    mocks.getSupportedVillages.mockResolvedValue(null)
    mocks.schoolList.mockResolvedValue(null)
    mocks.projectList.mockResolvedValue(null)
    const w = await mountAndFlush()
    const vm = w.vm as any
    expect(vm.villages).toEqual([])
    expect(vm.schools).toEqual([])
    expect(vm.projects).toEqual([])
  })

  it('选项加载失败提示', async () => {
    mocks.projectList.mockRejectedValue(new Error('boom'))
    await mountAndFlush()
    expect(mocks.message.error).toHaveBeenCalledWith('加载去向对象选项失败')
  })

  it('展示辅助函数全分支（未知值 / 空值回退）', async () => {
    const w = await mountAndFlush()
    const vm = w.vm as any
    expect(vm.destinationText(ROW_A)).toBe('帮扶村：幸福村')
    expect(vm.destinationText(ROW_B)).toBe('帮扶学校')
    expect(vm.categoryLabel('book')).toBe('图书')
    expect(vm.categoryLabel('xyz')).toBe('xyz')
    expect(vm.categoryLabel('')).toBe('-')
    expect(vm.destinationTypeLabel('project')).toBe('项目')
    expect(vm.destinationTypeLabel('')).toBe('-')
    expect(vm.destinationTypeLabel('nope')).toBe('nope')
  })

  it('筛选（含回车）/ 重置 / 分页 / 每页条数', async () => {
    const w = await mountAndFlush()
    const vm = w.vm as any
    // 输入关键字 + 回车
    const keywordInput = w.findAll('.el-input-input')[0]
    await keywordInput.setValue('图书')
    await keywordInput.trigger('keyup.enter')
    await flushPromises()
    expect(mocks.getDonations).toHaveBeenLastCalledWith(
      expect.objectContaining({ keyword: '图书', page: 1 }),
    )
    // 查询按钮
    await buttonByText(w, '查询')!.trigger('click')
    await flushPromises()
    expect(mocks.getDonations).toHaveBeenCalledTimes(3)
    // 重置
    vm.query.keyword = 'x'
    vm.query.category = 'book'
    vm.query.destination_type = 'village'
    await buttonByText(w, '重置')!.trigger('click')
    await flushPromises()
    expect(vm.query.keyword).toBe('')
    expect(vm.query.page).toBe(1)
    // 分页
    await w.find('.pg-page').trigger('click')
    await flushPromises()
    expect(vm.query.page).toBe(3)
    await w.find('.pg-size').trigger('click')
    await flushPromises()
    expect(vm.query.page_size).toBe(50)
    expect(vm.query.page).toBe(1)
    // 刷新
    await buttonByText(w, '刷新')!.trigger('click')
    await flushPromises()
  })

  it('校验全分支：逐项错误文案（含区间与空值子分支）', async () => {
    const w = await mountAndFlush()
    const vm = w.vm as any
    await buttonByText(w, '登记物资')!.trigger('click')
    await buttonByText(w, '保存')!.trigger('click')
    expect(mocks.message.error).toHaveBeenCalledWith('请填写名称')
    vm.form.name = '图书'
    vm.form.category = ''
    await buttonByText(w, '保存')!.trigger('click')
    expect(mocks.message.error).toHaveBeenCalledWith('请选择类别')
    vm.form.category = 'book'
    // 数量：非数（NaN）→ 负数（两个子分支）
    vm.form.quantity = Number.NaN
    await buttonByText(w, '保存')!.trigger('click')
    expect(mocks.message.error).toHaveBeenCalledWith('数量不能为负数')
    vm.form.quantity = -1
    await buttonByText(w, '保存')!.trigger('click')
    expect(mocks.message.error).toHaveBeenCalledWith('数量不能为负数')
    vm.form.quantity = 1
    // 折价：非数 → 负数
    vm.form.valuation = Number.NaN
    await buttonByText(w, '保存')!.trigger('click')
    expect(mocks.message.error).toHaveBeenCalledWith('折价不能为负数')
    vm.form.valuation = -2
    await buttonByText(w, '保存')!.trigger('click')
    expect(mocks.message.error).toHaveBeenCalledWith('折价不能为负数')
    vm.form.valuation = 1
    vm.form.destination_type = ''
    await buttonByText(w, '保存')!.trigger('click')
    expect(mocks.message.error).toHaveBeenCalledWith('请选择去向类型')
    vm.form.destination_type = 'village'
    vm.form.destination_id = null
    await buttonByText(w, '保存')!.trigger('click')
    expect(mocks.message.error).toHaveBeenCalledWith('请选择去向对象')
    expect(mocks.createDonation).not.toHaveBeenCalled()
  })

  it('编辑不一致数据：去向 id 为空时回落 null', async () => {
    const w = await mountAndFlush()
    const vm = w.vm as any
    vm.openEdit({ ...ROW_B, destination_type: 'village', village_id: null })
    expect(vm.form.destination_id).toBe(null)
    expect(vm.dialogVisible).toBe(true)
  })

  it('新建成功：payload 映射（空字段转 null、附件按行解析）', async () => {
    const w = await mountAndFlush()
    const vm = w.vm as any
    await buttonByText(w, '登记物资')!.trigger('click')
    Object.assign(vm.form, {
      name: '图书',
      category: 'book',
      quantity: 3,
      unit: '',
      valuation: 1.5,
      source_unit: '',
      destination_type: 'village',
      destination_id: 11,
      delivery_date: '',
      receiver: '',
      attachment_text: 'https://x/a.pdf\n/',
      remark: '',
    })
    await buttonByText(w, '保存')!.trigger('click')
    await flushPromises()
    expect(mocks.createDonation).toHaveBeenCalledWith({
      name: '图书',
      category: 'book',
      quantity: 3,
      unit: null,
      valuation: 1.5,
      source_unit: null,
      destination_type: 'village',
      delivery_date: null,
      receiver: null,
      attachments: [
        { url: 'https://x/a.pdf', file_name: 'a.pdf' },
        { url: '/', file_name: null },
      ],
      remark: null,
      village_id: 11,
    })
    expect(mocks.message.success).toHaveBeenCalledWith('已登记')
    expect(vm.dialogVisible).toBe(false)
  })

  it('新建失败提示', async () => {
    mocks.createDonation.mockRejectedValue(new Error('boom'))
    const w = await mountAndFlush()
    const vm = w.vm as any
    await buttonByText(w, '登记物资')!.trigger('click')
    Object.assign(vm.form, {
      name: '图书',
      category: 'book',
      quantity: 1,
      valuation: 0,
      destination_type: 'school',
      destination_id: 22,
      attachment_text: '',
    })
    await buttonByText(w, '保存')!.trigger('click')
    await flushPromises()
    expect(mocks.message.error).toHaveBeenCalledWith('保存失败，请检查填写内容')
    expect(vm.saving).toBe(false)
  })

  it('编辑回填三种去向；保存走更新（school / project 映射）', async () => {
    const w = await mountAndFlush()
    const vm = w.vm as any
    const editButtons = w.findAll('el-button-stub').filter((b: any) => b.text().trim() === '编辑')
    expect(editButtons.length).toBeGreaterThanOrEqual(3)
    // school 行：无附件、空字段
    await editButtons[1].trigger('click')
    expect(vm.form.destination_type).toBe('school')
    expect(vm.form.destination_id).toBe(22)
    expect(vm.form.unit).toBe('')
    expect(vm.form.delivery_date).toBe('')
    expect(vm.form.attachment_text).toBe('')
    Object.assign(vm.form, { unit: '台', source_unit: '某处', receiver: '王五', delivery_date: '2026-05-01' })
    await buttonByText(w, '保存')!.trigger('click')
    await flushPromises()
    expect(mocks.updateDonation).toHaveBeenCalledWith(
      2,
      expect.objectContaining({ school_id: 22, unit: '台', source_unit: '某处', receiver: '王五' }),
    )
    expect(mocks.message.success).toHaveBeenCalledWith('已更新')
    // project 行
    await editButtons[2].trigger('click')
    expect(vm.form.destination_id).toBe(33)
    await buttonByText(w, '保存')!.trigger('click')
    await flushPromises()
    expect(mocks.updateDonation).toHaveBeenLastCalledWith(
      3,
      expect.objectContaining({ project_id: 33 }),
    )
    // village 行：附件回填为多行文本
    await editButtons[0].trigger('click')
    expect(vm.form.destination_id).toBe(11)
    expect(vm.form.attachment_text).toBe('https://x/a.pdf')
  })

  it('更新失败提示', async () => {
    mocks.updateDonation.mockRejectedValue(new Error('boom'))
    const w = await mountAndFlush()
    const vm = w.vm as any
    const editButtons = w.findAll('el-button-stub').filter((b: any) => b.text().trim() === '编辑')
    await editButtons[0].trigger('click')
    await buttonByText(w, '保存')!.trigger('click')
    await flushPromises()
    expect(mocks.message.error).toHaveBeenCalledWith('保存失败，请检查填写内容')
    expect(vm.saving).toBe(false)
  })

  it('去向类型切换清空已选对象', async () => {
    const w = await mountAndFlush()
    const vm = w.vm as any
    await buttonByText(w, '登记物资')!.trigger('click')
    vm.form.destination_id = 11
    vm.handleDestinationTypeChange()
    expect(vm.form.destination_id).toBe(null)
    // 触发模板 @change（el-select 桩）
    const selectInputs = w.findAll('.el-select-input')
    await selectInputs[selectInputs.length - 1].trigger('change')
    await flushPromises()
    expect(vm.form.destination_id).toBe(null)
  })

  it('删除：取消确认不删除', async () => {
    mocks.messageBox.confirm.mockRejectedValue(new Error('cancel'))
    const w = await mountAndFlush()
    const delButtons = w.findAll('el-button-stub').filter((b: any) => b.text().trim() === '删除')
    await delButtons[0].trigger('click')
    await flushPromises()
    expect(mocks.deleteDonation).not.toHaveBeenCalled()
  })

  it('删除成功提示', async () => {
    const w = await mountAndFlush()
    const delButtons = w.findAll('el-button-stub').filter((b: any) => b.text().trim() === '删除')
    await delButtons[0].trigger('click')
    await flushPromises()
    expect(mocks.messageBox.confirm).toHaveBeenCalled()
    expect(mocks.deleteDonation).toHaveBeenCalledWith(1)
    expect(mocks.message.success).toHaveBeenCalledWith('已删除')
  })

  it('删除失败提示', async () => {
    mocks.deleteDonation.mockRejectedValue(new Error('boom'))
    const w = await mountAndFlush()
    const delButtons = w.findAll('el-button-stub').filter((b: any) => b.text().trim() === '删除')
    await delButtons[0].trigger('click')
    await flushPromises()
    expect(mocks.message.error).toHaveBeenCalledWith('删除失败')
  })

  it('对话框关闭按钮与取消按钮', async () => {
    const w = await mountAndFlush()
    await buttonByText(w, '登记物资')!.trigger('click')
    expect((w.vm as any).dialogVisible).toBe(true)
    await w.find('.dialog-close').trigger('click')
    expect((w.vm as any).dialogVisible).toBe(false)
    await buttonByText(w, '登记物资')!.trigger('click')
    await buttonByText(w, '取消')!.trigger('click')
    expect((w.vm as any).dialogVisible).toBe(false)
  })

  it('全部 v-model 处理器可触发（输入/选择/日期/数字）', async () => {
    const w = await mountAndFlush()
    await buttonByText(w, '登记物资')!.trigger('click')
    for (const sel of ['.el-input-input', '.el-select-input', '.el-date-picker-input', '.el-input-number-input']) {
      const nodes = w.findAll(sel)
      for (const n of nodes) {
        await n.trigger('input')
        await n.trigger('change')
      }
    }
    await flushPromises()
    expect((w.vm as any).dialogVisible).toBe(true)
  })

  it('空附件文本提交时 attachments 为 null', async () => {
    const w = await mountAndFlush()
    const vm = w.vm as any
    await buttonByText(w, '登记物资')!.trigger('click')
    Object.assign(vm.form, {
      name: '物资',
      category: 'material',
      quantity: 1,
      valuation: 1,
      destination_type: 'project',
      destination_id: 33,
      attachment_text: '   ',
    })
    await buttonByText(w, '保存')!.trigger('click')
    await flushPromises()
    expect(mocks.createDonation).toHaveBeenCalledWith(
      expect.objectContaining({ attachments: null, project_id: 33 }),
    )
  })
})
