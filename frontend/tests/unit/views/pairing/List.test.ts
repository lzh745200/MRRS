/**
 * views/pairing/List.vue 覆盖率攻坚（四指标 100%）
 *
 * 覆盖：加载（含 null 响应兜底 / 失败）、选项加载（null / 失败）、
 * 展示辅助函数全分支、筛选/重置/分页、新建/编辑校验与提交（含失败）、
 * 删除三态（确认/取消/失败）、走访台账（登记/编辑/取消编辑/删除/失败）、
 * 两处 v-model 全量触发、抽屉/对话框关闭。
 *
 * 说明：本文件是 views/pairing/List.vue 的唯一执行者
 * （router-index.test.ts 已以桩替换懒加载，避免覆盖率 fnMap 分片错位）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const mocks = vi.hoisted(() => ({
  getPairings: vi.fn(),
  getPairingStats: vi.fn(),
  getPairing: vi.fn(),
  createPairing: vi.fn(),
  updatePairing: vi.fn(),
  deletePairing: vi.fn(),
  getVisits: vi.fn(),
  createVisit: vi.fn(),
  updateVisit: vi.fn(),
  deleteVisit: vi.fn(),
  getSupportedVillages: vi.fn(),
  schoolList: vi.fn(),
  message: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  messageBox: { confirm: vi.fn() },
  route: { query: {} as Record<string, unknown> },
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  // PageHeader 标准件的返回按钮依赖 useRouter；页面已接入 PageHeader（R34 精细化）
  useRouter: () => ({ back: vi.fn() }),
}))

vi.mock('@/api/pairings', () => ({
  getPairings: mocks.getPairings,
  getPairingStats: mocks.getPairingStats,
  getPairing: mocks.getPairing,
  createPairing: mocks.createPairing,
  updatePairing: mocks.updatePairing,
  deletePairing: mocks.deletePairing,
  getVisits: mocks.getVisits,
  createVisit: mocks.createVisit,
  updateVisit: mocks.updateVisit,
  deleteVisit: mocks.deleteVisit,
}))

vi.mock('@/api/supportedVillage', () => ({
  getSupportedVillages: mocks.getSupportedVillages,
}))

vi.mock('@/api/schools', () => ({
  schoolsApi: { list: mocks.schoolList },
}))

vi.mock('element-plus', () => ({
  ElMessage: mocks.message,
  ElMessageBox: mocks.messageBox,
}))

import PairingList from '@/views/pairing/List.vue'

// el-table-column 注入的三行样本：A 全字段；B 未知主体/无对象名/无日期/已结束；C 学生回退名
const ROW_A = {
  id: 101,
  subject_type: 'unit',
  subject_name: '某单位',
  partner_type: 'village',
  village_id: 1,
  school_id: null,
  student_name: null,
  title: '对口帮扶一',
  partner_name: '幸福村',
  content: 'c1',
  note: 'n1',
  start_date: '2026-01-01',
  end_date: '2026-12-31',
  status: 'active',
}
const ROW_B = {
  id: 102,
  subject_type: 'alien',
  subject_name: '未知主体',
  partner_type: 'school',
  village_id: null,
  school_id: 2,
  student_name: null,
  title: '助学',
  partner_name: null,
  status: 'ended',
  // 走访字段：同时驱动走访编辑预填的“有值”分支（列模板不使用这些字段）
  visit_date: '2026-02-02',
  visitors: '乙',
  purpose: '走访事项B',
  content: '内容B',
  materials: '物资B',
}
const ROW_C = {
  id: 103,
  subject_type: 'person',
  subject_name: '张三',
  partner_type: 'student',
  village_id: null,
  school_id: null,
  student_name: '李四',
  title: '学生帮扶',
  partner_name: null,
  status: '',
}

/** 带原生 input 的 v-model 组件桩：让全部 update:modelValue 编译处理器被执行 */
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
      EmptyState: {
        name: 'EmptyState',
        props: ['text'],
        template: '<div class="empty-stub">{{ text }}</div>',
      },
      'el-input': modelStub('el-input'),
      'el-select': modelStub('el-select'),
      'el-date-picker': modelStub('el-date-picker'),
      'el-radio-group': modelStub('el-radio-group'),
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
      'el-drawer': {
        name: 'ElDrawer',
        props: ['modelValue', 'title'],
        emits: ['update:modelValue'],
        template:
          '<div class="el-drawer-stub">' +
          '<div class="drawer-title">{{ title }}</div>' +
          '<button class="drawer-close" @click="$emit(\'update:modelValue\', false)">x</button>' +
          '<slot /></div>',
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
      'el-pagination': { name: 'ElPagination', template: '<div class="el-pagination-stub" />' },
    },
  },
}

function mountComp() {
  return mount(PairingList, mountOptions)
}

function buttonByText(w: ReturnType<typeof mountComp>, text: string) {
  return w.findAll('el-button-stub').find((b) => b.text().trim() === text)
}

/** 行内操作按钮（结对表在前，走访表在抽屉内） */
function rowButtons(w: ReturnType<typeof mountComp>, scope: 'page' | 'drawer', text: string) {
  const root: any = scope === 'drawer' ? w.find('.el-drawer-stub') : w
  return root.findAll('el-button-stub').filter((b: any) => b.text().trim() === text)
}

function statsFixture() {
  return { total: 2, active: 1, ended: 1, villages: 1, schools: 1, students: 0, visits: 3 }
}

describe('views/pairing/List.vue（结对帮扶台账）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.route.query = {}
    mocks.getPairings.mockResolvedValue({ items: [ROW_A, ROW_B], total: 2, page: 1, page_size: 20 })
    mocks.getPairingStats.mockResolvedValue(statsFixture())
    mocks.createPairing.mockResolvedValue({ id: 200 })
    mocks.updatePairing.mockResolvedValue({ id: 101 })
    mocks.deletePairing.mockResolvedValue({ id: 101 })
    mocks.getVisits.mockResolvedValue({
      items: [
        {
          id: 301,
          pairing_id: 101,
          visit_date: '2026-03-01',
          visitors: '甲',
          purpose: '助学',
          materials: '书包',
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    })
    mocks.createVisit.mockResolvedValue({ id: 302 })
    mocks.updateVisit.mockResolvedValue({ id: 301 })
    mocks.deleteVisit.mockResolvedValue({ id: 301 })
    mocks.getSupportedVillages.mockResolvedValue({
      items: [{ id: 1, village_name: '幸福村' }],
      total: 1,
    })
    mocks.schoolList.mockResolvedValue({ items: [{ id: 2, name: '希望小学' }], total: 1 })
    mocks.messageBox.confirm.mockResolvedValue('confirm')
  })

  it('挂载加载：列表 + 统计 + 选项 + 列模板三行样本全渲染', async () => {
    const w = mountComp()
    await flushPromises()

    expect(mocks.getPairings).toHaveBeenCalledWith({ page: 1, page_size: 20 })
    expect(mocks.getPairingStats).toHaveBeenCalled()
    expect(mocks.getSupportedVillages).toHaveBeenCalledWith({ page: 1, page_size: 200 })
    expect(mocks.schoolList).toHaveBeenCalledWith({ page: 1, page_size: 200 })

    const vm = w.vm as any
    expect(vm.items).toHaveLength(2)
    expect(vm.total).toBe(2)
    expect(vm.villages).toHaveLength(1)
    expect(vm.schools).toHaveLength(1)
    expect(vm.loading).toBe(false)

    // 统计行
    expect(w.text()).toContain('结对总数 2')
    expect(w.text()).toContain('在帮 1')
    expect(w.text()).toContain('已结束 1')
    expect(w.text()).toContain('走访 3 次')
    // 三行样本：主体/对象标签（含未知主体回退与未关联兜底）
    expect(w.text()).toContain('单位 · 某单位')
    expect(w.text()).toContain('帮扶村 · 幸福村')
    expect(w.text()).toContain('alien · 未知主体')
    expect(w.text()).toContain('帮扶学校 · 未关联')
    expect(w.text()).toContain('困难学生 · 李四')
    // 日期区间两分支 + 状态两分支
    expect(w.text()).toContain('2026-01-01 ~ 2026-12-31')
    expect(w.text()).toContain('-')
    expect(w.text()).toContain('帮扶中')
    expect(w.text()).toContain('已结束')
    // 空态插槽
    expect(w.text()).toContain('暂无结对记录')
    expect(w.text()).toContain('暂无走访记录')
    // 抽屉/对话框标题初始态
    expect(w.text()).toContain('走访台账')
    expect(w.text()).toContain('新建结对记录')
    w.unmount()
  })

  it('展示辅助函数全分支', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any

    expect(vm.subjectLabel({ subject_type: 'unit', subject_name: 'A' })).toBe('单位 · A')
    expect(vm.subjectLabel({ subject_type: 'alien', subject_name: 'B' })).toBe('alien · B')

    expect(
      vm.partnerLabel({ partner_type: 'village', partner_name: '村', student_name: '李' })
    ).toBe('帮扶村 · 村')
    expect(
      vm.partnerLabel({ partner_type: 'student', partner_name: null, student_name: '李四' })
    ).toBe('困难学生 · 李四')
    expect(vm.partnerLabel({ partner_type: 'student', partner_name: '', student_name: null })).toBe(
      '困难学生 · 未关联'
    )

    expect(vm.dateRange({ start_date: '2026-01-01', end_date: '' })).toBe('2026-01-01')
    expect(vm.dateRange({ start_date: null, end_date: null })).toBe('-')

    expect(vm.statusText({ status: 'active' })).toBe('帮扶中')
    expect(vm.statusText({ status: 'ended' })).toBe('已结束')
    expect(vm.statusTagType({ status: 'active' })).toBe('success')
    expect(vm.statusTagType({ status: 'ended' })).toBe('info')
    w.unmount()
  })

  it('筛选/回车/重置/分页/刷新：参数构造与分页重置', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any

    await w.find('.f-keyword input').setValue('帮扶')
    const selects = w.findAll('.f-select input')
    await selects[0].setValue('person')
    // 对象筛选控件三态：未选类型不渲染 → village / school 渲染（v-if 两操作数分支）
    expect(w.find('.f-partner').exists()).toBe(false)
    await selects[1].setValue('village')
    expect(w.find('.f-partner').exists()).toBe(true)
    await selects[1].setValue('school')
    expect(w.find('.f-partner').exists()).toBe(true)
    // 对象选择 v-model 编译处理器（桩输入为字符串）
    await w.find('.f-partner input').setValue('2')
    expect(vm.query.partner_id).toBe('2')
    // 选项未命中（字符串 ≠ number）→ #id 兜底
    expect(vm.partnerScopeText).toBe('#2')
    // 命中选项 label 分支（真实 Select 选中项为 number）
    vm.query.partner_id = 2
    await nextTick()
    expect(vm.partnerScopeText).toBe('希望小学')
    expect(w.text()).toContain('对象：希望小学')
    // 清除对象筛选按钮
    await w.find('.btn-clear-partner').trigger('click')
    expect(vm.query.partner_type).toBe('')
    expect(vm.query.partner_id).toBeNull()
    await selects[1].setValue('school')
    await selects[2].setValue('ended')
    await w.find('.f-keyword input').trigger('keyup.enter')
    await flushPromises()
    expect(mocks.getPairings).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 20,
      keyword: '帮扶',
      subject_type: 'person',
      partner_type: 'school',
      status: 'ended',
    })

    await buttonByText(w, '重置')!.trigger('click')
    await flushPromises()
    expect(mocks.getPairings).toHaveBeenLastCalledWith({ page: 1, page_size: 20 })
    expect(vm.query.keyword).toBe('')
    expect(vm.query.page).toBe(1)

    await vm.handlePageChange(3)
    expect(mocks.getPairings).toHaveBeenLastCalledWith({ page: 3, page_size: 20 })

    await vm.handleSizeChange(50)
    expect(mocks.getPairings).toHaveBeenLastCalledWith({ page: 1, page_size: 50 })

    const calls = mocks.getPairings.mock.calls.length
    await buttonByText(w, '刷新')!.trigger('click')
    await flushPromises()
    expect(mocks.getPairings.mock.calls.length).toBe(calls + 1)
    w.unmount()
  })

  it('深链预填：按对象聚合（村/校入口）+ 清除对象筛选', async () => {
    mocks.route.query = { partner_type: 'village', partner_id: '1' }
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any

    expect(vm.query.partner_type).toBe('village')
    expect(vm.query.partner_id).toBe(1)
    expect(mocks.getPairings).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
      partner_type: 'village',
      partner_id: 1,
    })
    // village 分支选项 + 命中 label
    expect(vm.partnerOptions).toEqual([{ id: 1, label: '幸福村' }])
    expect(vm.partnerScopeText).toBe('幸福村')
    // school 分支选项
    vm.query.partner_type = 'school'
    expect(vm.partnerOptions).toEqual([{ id: 2, label: '希望小学' }])
    // student → 空选项（学生按关键字搜索，不做 id 过滤）
    vm.query.partner_type = 'student'
    expect(vm.partnerOptions).toEqual([])
    // 清除对象筛选
    vm.query.partner_type = 'village'
    vm.query.partner_id = 1
    vm.clearPartnerScope()
    expect(vm.query.partner_type).toBe('')
    expect(vm.query.partner_id).toBeNull()
    expect(vm.partnerScopeText).toBe('')
    w.unmount()
  })

  it('深链非法值忽略：未知对象类型 / 非数字 id / id=0', async () => {
    mocks.route.query = { partner_type: 'alien', partner_id: 'abc' }
    const w1 = mountComp()
    await flushPromises()
    const vm1 = w1.vm as any
    expect(vm1.query.partner_type).toBe('')
    expect(vm1.query.partner_id).toBeNull()
    expect(mocks.getPairings).toHaveBeenLastCalledWith({ page: 1, page_size: 20 })
    w1.unmount()

    mocks.route.query = { partner_id: '0' }
    const w2 = mountComp()
    await flushPromises()
    expect((w2.vm as any).query.partner_id).toBeNull()
    w2.unmount()
  })

  it('加载响应为 null → 空列表 / 零统计兜底；统计为 null → EMPTY_STATS', async () => {
    mocks.getPairings.mockResolvedValue(null)
    mocks.getPairingStats.mockResolvedValue(null)
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    expect(vm.items).toEqual([])
    expect(vm.total).toBe(0)
    expect(vm.stats).toEqual({
      total: 0,
      active: 0,
      ended: 0,
      villages: 0,
      schools: 0,
      students: 0,
      visits: 0,
    })
    w.unmount()
  })

  it('加载失败提示', async () => {
    mocks.getPairings.mockRejectedValue(new Error('net'))
    const w = mountComp()
    await flushPromises()
    expect(mocks.message.error).toHaveBeenCalledWith('加载台账失败')
    w.unmount()
  })

  it('选项加载 null → 空数组兜底；失败 → 提示', async () => {
    mocks.getSupportedVillages.mockResolvedValue(null)
    mocks.schoolList.mockResolvedValue(null)
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    expect(vm.villages).toEqual([])
    expect(vm.schools).toEqual([])
    w.unmount()

    mocks.getSupportedVillages.mockRejectedValue(new Error('net'))
    mocks.schoolList.mockResolvedValue({ items: [], total: 0 })
    const w2 = mountComp()
    await flushPromises()
    expect(mocks.message.error).toHaveBeenCalledWith('加载帮扶村 / 学校选项失败')
    w2.unmount()
  })

  it('新建：校验全分支 + 校验失败拦截 + 提交成功 + 对话框关闭', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any

    await buttonByText(w, '新建结对')!.trigger('click')
    expect(vm.dialogVisible).toBe(true)
    expect(vm.dialogTitle).toBe('新建结对记录')
    expect(vm.editingId).toBeNull()

    // 空表单直接保存 → 校验拦截
    await buttonByText(w, '保存')!.trigger('click')
    await flushPromises()
    expect(mocks.message.warning).toHaveBeenCalledWith('请填写帮扶主体名称')
    expect(mocks.createPairing).not.toHaveBeenCalled()

    // validateForm 全分支
    expect(vm.validateForm()).toBe('请填写帮扶主体名称')
    vm.form.subject_name = '某单位'
    expect(vm.validateForm()).toBe('请填写帮扶事项')
    vm.form.title = '对口帮扶'
    expect(vm.validateForm()).toBe('请选择帮扶村')
    vm.form.village_id = 1
    expect(vm.validateForm()).toBeNull()
    vm.form.partner_type = 'school'
    expect(vm.validateForm()).toBe('请选择帮扶学校')
    vm.form.school_id = 2
    expect(vm.validateForm()).toBeNull()
    vm.form.partner_type = 'student'
    expect(vm.validateForm()).toBe('请填写学生姓名')
    vm.form.student_name = '李四'
    expect(vm.validateForm()).toBeNull()
    vm.form.start_date = '2026-05-01'
    vm.form.end_date = '2026-04-30'
    expect(vm.validateForm()).toBe('结束日期不能早于起始日期')
    vm.form.end_date = '2026-06-01'
    expect(vm.validateForm()).toBeNull()

    // v-model 覆盖：对话框内主体/对象/状态与文本字段
    await w.find('.form-subject-type input').setValue('branch')
    await w.find('.form-subject-name input').setValue('某单位')
    await w.find('.form-partner-type input').setValue('village')
    await w.find('.el-radio-group-wrapper input').setValue('active')
    await w.find('.form-village input').setValue(1)
    await w.find('.form-start input').setValue('2026-01-01')
    await w.find('.form-end input').setValue('2026-12-31')
    await w.find('.form-note input').setValue('n')
    expect(vm.form.status).toBe('active')

    vm.form.partner_type = 'village'
    vm.form.village_id = 1
    await buttonByText(w, '保存')!.trigger('click')
    await flushPromises()
    expect(mocks.createPairing).toHaveBeenCalledWith(
      expect.objectContaining({
        subject_name: '某单位',
        title: '对口帮扶',
        partner_type: 'village',
        village_id: 1,
      })
    )
    expect(mocks.message.success).toHaveBeenCalledWith('创建成功')
    expect(vm.dialogVisible).toBe(false)

    // 对话框关闭按钮（v-model 编译产物）与页脚“取消”
    await w.find('.dialog-close').trigger('click')
    expect(vm.dialogVisible).toBe(false)
    await buttonByText(w, '取消')!.trigger('click')
    expect(vm.dialogVisible).toBe(false)
    w.unmount()
  })

  it('编辑：预填（含空值兜底）+ 表单分支切换 + 更新成功/失败', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any

    // 第二行（ROW_B）覆盖有值侧与 ?? null 兜底
    await rowButtons(w, 'page', '编辑')[1].trigger('click')
    expect(vm.editingId).toBe(102)
    expect(vm.dialogTitle).toBe('编辑结对记录')
    expect(vm.form.content).toBe('内容B')
    expect(vm.form.note).toBe('')
    expect(vm.form.start_date).toBe('')
    expect(vm.form.student_name).toBe('')
    expect(vm.form.village_id).toBeNull()

    // 第三行（ROW_C）覆盖 content / note 的 ?? '' 兜底
    await rowButtons(w, 'page', '编辑')[2].trigger('click')
    expect(vm.editingId).toBe(103)
    expect(vm.form.content).toBe('')
    expect(vm.form.note).toBe('')

    // 第一行（ROW_A）覆盖字段齐全预填
    await rowButtons(w, 'page', '编辑')[0].trigger('click')
    expect(vm.editingId).toBe(101)
    expect(vm.form.note).toBe('n1')
    expect(vm.form.village_id).toBe(1)
    expect(vm.form.school_id).toBeNull()

    // 对象类型 v-if 分支切换（含各分支 v-model 触发）
    expect(w.find('.form-village').exists()).toBe(true)
    vm.form.partner_type = 'school'
    await nextTick()
    expect(w.find('.form-school').exists()).toBe(true)
    await w.find('.form-school input').setValue(2)
    expect(vm.form.school_id).toBe('2')
    vm.form.partner_type = 'student'
    await nextTick()
    expect(w.find('.form-student').exists()).toBe(true)
    await w.find('.form-student input').setValue('李四')
    await w.find('.form-title input').setValue('对口帮扶')
    await w.find('.form-content input').setValue('帮扶措施')
    expect(vm.form.student_name).toBe('李四')
    vm.handlePartnerTypeChange()
    expect(vm.form.student_name).toBe('')

    // 更新成功
    vm.form.partner_type = 'village'
    vm.form.village_id = 1
    vm.form.subject_name = '某单位'
    vm.form.title = '对口帮扶一'
    await buttonByText(w, '保存')!.trigger('click')
    await flushPromises()
    expect(mocks.updatePairing).toHaveBeenCalledWith(
      101,
      expect.objectContaining({ title: '对口帮扶一' })
    )
    expect(mocks.message.success).toHaveBeenCalledWith('更新成功')

    // 更新失败
    await rowButtons(w, 'page', '编辑')[0].trigger('click')
    vm.form.subject_name = '某单位'
    vm.form.title = '对口帮扶一'
    vm.form.partner_type = 'village'
    vm.form.village_id = 1
    mocks.updatePairing.mockRejectedValueOnce(new Error('net'))
    await buttonByText(w, '保存')!.trigger('click')
    await flushPromises()
    expect(mocks.message.error).toHaveBeenCalledWith('保存失败，请稍后重试')
    w.unmount()
  })

  it('创建失败提示', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    await buttonByText(w, '新建结对')!.trigger('click')
    vm.form.subject_name = '某单位'
    vm.form.title = '对口帮扶'
    vm.form.partner_type = 'village'
    vm.form.village_id = 1
    mocks.createPairing.mockRejectedValueOnce(new Error('net'))
    await buttonByText(w, '保存')!.trigger('click')
    await flushPromises()
    expect(mocks.message.error).toHaveBeenCalledWith('保存失败，请稍后重试')
    w.unmount()
  })

  it('删除：确认 / 取消 / 失败三态', async () => {
    const w = mountComp()
    await flushPromises()

    mocks.messageBox.confirm.mockResolvedValue('ok')
    await rowButtons(w, 'page', '删除')[0].trigger('click')
    await flushPromises()
    expect(mocks.deletePairing).toHaveBeenCalledWith(101)
    expect(mocks.message.success).toHaveBeenCalledWith('删除成功')

    mocks.messageBox.confirm.mockRejectedValueOnce(new Error('cancel'))
    await rowButtons(w, 'page', '删除')[0].trigger('click')
    await flushPromises()
    expect(mocks.deletePairing).toHaveBeenCalledTimes(1)

    mocks.messageBox.confirm.mockResolvedValue('ok')
    mocks.deletePairing.mockRejectedValueOnce(new Error('net'))
    await rowButtons(w, 'page', '删除')[0].trigger('click')
    await flushPromises()
    expect(mocks.message.error).toHaveBeenCalledWith('操作失败，请稍后重试')
    w.unmount()
  })

  it('走访：提前返回分支 + 打开台账 + 登记 + 抽屉关闭', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any

    // 未打开台账：loadVisits / handleVisitDelete 提前返回
    await vm.loadVisits()
    expect(mocks.getVisits).not.toHaveBeenCalled()
    await vm.handleVisitDelete({ id: 9 })
    expect(mocks.messageBox.confirm).not.toHaveBeenCalled()

    // 表单校验分支（直接调用 + handleVisitSubmit 拦截路径）
    expect(vm.validateVisitForm()).toBe('请选择走访日期')
    await vm.handleVisitSubmit()
    expect(mocks.message.warning).toHaveBeenCalledWith('请选择走访日期')
    expect(mocks.createVisit).not.toHaveBeenCalled()
    vm.visitForm.visit_date = '2026-03-01'
    expect(vm.validateVisitForm()).toBe('请填写走访人员')
    vm.visitForm.visitors = '甲'
    expect(vm.validateVisitForm()).toBeNull()
    // 未选结对记录 → 提前返回
    await vm.handleVisitSubmit()
    expect(mocks.createVisit).not.toHaveBeenCalled()

    expect(vm.visitsTitle).toBe('走访台账')
    await rowButtons(w, 'page', '走访台账')[0].trigger('click')
    await flushPromises()
    expect(vm.currentPairing.id).toBe(101)
    expect(vm.visits).toHaveLength(1)
    expect(vm.visitsTitle).toBe('走访台账 · 对口帮扶一')
    expect(vm.visitSubmitText).toBe('登记走访')

    // 登记（vf-* 的 v-model 编译产物）
    await w.find('.vf-date input').setValue('2026-04-01')
    await w.find('.vf-visitors input').setValue('甲、乙')
    await w.find('.vf-purpose input').setValue('助学走访')
    await w.find('.vf-materials input').setValue('书包 20 个')
    await buttonByText(w, '登记走访')!.trigger('click')
    await flushPromises()
    expect(mocks.createVisit).toHaveBeenCalledWith(
      101,
      expect.objectContaining({
        visit_date: '2026-04-01',
        visitors: '甲、乙',
        materials: '书包 20 个',
      })
    )
    expect(mocks.message.success).toHaveBeenCalledWith('登记成功')
    // 提交后重置 + 刷新（走访列表 + 统计）
    expect(vm.visitForm.visit_date).toBe('')
    expect(mocks.getVisits).toHaveBeenCalledTimes(2)
    expect(mocks.getPairingStats).toHaveBeenCalledTimes(2)

    // 抽屉关闭
    await w.find('.drawer-close').trigger('click')
    expect(vm.visitsVisible).toBe(false)
    w.unmount()
  })

  it('走访：编辑预填 + 更新 + 取消编辑', async () => {
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    await rowButtons(w, 'page', '走访台账')[0].trigger('click')
    await flushPromises()

    await rowButtons(w, 'drawer', '编辑')[1].trigger('click')
    expect(vm.editingVisitId).toBe(102)
    expect(vm.visitSubmitText).toBe('保存修改')
    expect(vm.visitForm.visit_date).toBe('2026-02-02')
    expect(vm.visitForm.visitors).toBe('乙')
    expect(vm.visitForm.purpose).toBe('走访事项B')
    expect(vm.visitForm.content).toBe('内容B')
    expect(vm.visitForm.materials).toBe('物资B')

    await w.find('.vf-date input').setValue('2026-05-01')
    await w.find('.vf-visitors input').setValue('丙')
    await buttonByText(w, '保存修改')!.trigger('click')
    await flushPromises()
    expect(mocks.updateVisit).toHaveBeenCalledWith(
      101,
      102,
      expect.objectContaining({ visitors: '丙', visit_date: '2026-05-01' })
    )
    expect(mocks.message.success).toHaveBeenCalledWith('更新成功')

    // 第一行（ROW_A）：content 有值（c1 来自结对记录）；visit_date 等无值 → ?? 兜底
    await rowButtons(w, 'drawer', '编辑')[0].trigger('click')
    expect(vm.editingVisitId).toBe(101)
    expect(vm.visitForm.content).toBe('c1')
    expect(vm.visitForm.visit_date).toBe('')
    expect(vm.visitForm.visitors).toBe('')
    expect(vm.visitForm.purpose).toBe('')
    expect(vm.visitForm.materials).toBe('')
    // 第三行（ROW_C）：content 也无值 → 兜底
    await rowButtons(w, 'drawer', '编辑')[2].trigger('click')
    expect(vm.editingVisitId).toBe(103)
    expect(vm.visitForm.content).toBe('')
    expect(vm.visitForm.visit_date).toBe('')
    await w.find('.btn-visit-cancel').trigger('click')
    expect(vm.editingVisitId).toBeNull()
    expect(vm.visitForm.visit_date).toBe('')
    w.unmount()
  })

  it('走访：删除确认 / 取消 / 失败', async () => {
    const w = mountComp()
    await flushPromises()
    await rowButtons(w, 'page', '走访台账')[0].trigger('click')
    await flushPromises()

    mocks.messageBox.confirm.mockResolvedValue('ok')
    await rowButtons(w, 'drawer', '删除')[0].trigger('click')
    await flushPromises()
    expect(mocks.deleteVisit).toHaveBeenCalledWith(101, 101)
    expect(mocks.message.success).toHaveBeenCalledWith('删除成功')

    mocks.messageBox.confirm.mockRejectedValueOnce(new Error('cancel'))
    await rowButtons(w, 'drawer', '删除')[0].trigger('click')
    await flushPromises()
    expect(mocks.deleteVisit).toHaveBeenCalledTimes(1)

    mocks.messageBox.confirm.mockResolvedValue('ok')
    mocks.deleteVisit.mockRejectedValueOnce(new Error('net'))
    await rowButtons(w, 'drawer', '删除')[0].trigger('click')
    await flushPromises()
    expect(mocks.message.error).toHaveBeenCalledWith('操作失败，请稍后重试')
    w.unmount()
  })

  it('走访：加载失败 / 登记失败提示', async () => {
    mocks.getVisits.mockRejectedValue(new Error('net'))
    const w = mountComp()
    await flushPromises()
    const vm = w.vm as any
    await rowButtons(w, 'page', '走访台账')[0].trigger('click')
    await flushPromises()
    expect(mocks.message.error).toHaveBeenCalledWith('加载走访记录失败')

    mocks.getVisits.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 })
    await w.find('.vf-date input').setValue('2026-04-01')
    await w.find('.vf-visitors input').setValue('甲')
    mocks.createVisit.mockRejectedValueOnce(new Error('net'))
    await buttonByText(w, '登记走访')!.trigger('click')
    await flushPromises()
    expect(mocks.message.error).toHaveBeenCalledWith('操作失败，请稍后重试')

    // getVisits 返回 null → 空数组兜底
    mocks.getVisits.mockResolvedValue(null)
    await vm.loadVisits()
    expect(vm.visits).toEqual([])
    w.unmount()
  })
})
