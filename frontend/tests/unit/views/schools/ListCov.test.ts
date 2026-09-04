/**
 * views/schools/List.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：数据加载全响应形态、服务端/本地统计回退、echarts 图表构建与重绘、
 * 搜索/重置/分页/状态卡筛选、查看/编辑/删除、模板下载、导入校验与回调、
 * 导出（含 DOM 下载）、KeepAlive 激活、onUnmounted 清理、env baseUrl 分支，
 * 以及 el-table-column 三行样本覆盖列模板全部 v-if/v-else/|| 分支。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick, KeepAlive, h, defineComponent } from 'vue'
import { ElMessageBox } from 'element-plus'

// vi.mock 工厂提升求值，引用对象须先放入 vi.hoisted 初始化（TDZ）
const {
  pushSafeMock,
  dsMock,
  ElMessage,
  logError,
  apiRequestMock,
  delMock,
  getStatsMock,
  downloadTplMock,
  getTokenMock,
  fetchMock,
  downloadBlobAsFileMock,
  requestGetMock,
  chartSetOption,
  chartDispose,
  chartResize,
  echartsInit,
  confirmMock,
  promptMock,
  alertMock,
  restoreSchoolMock,
  previewPurgeSchoolMock,
  purgeSchoolMock,
} = vi.hoisted(() => {
  const chartSetOption = vi.fn()
  const chartDispose = vi.fn()
  const chartResize = vi.fn()
  return {
    pushSafeMock: vi.fn(),
    dsMock: vi.fn(),
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
    logError: vi.fn(),
    apiRequestMock: vi.fn(),
    delMock: vi.fn(),
    getStatsMock: vi.fn(),
    downloadTplMock: vi.fn(),
    getTokenMock: vi.fn(),
    fetchMock: vi.fn(),
    downloadBlobAsFileMock: vi.fn(),
    requestGetMock: vi.fn(),
    chartSetOption,
    chartDispose,
    chartResize,
    echartsInit: vi.fn(),
    confirmMock: vi.fn(),
    promptMock: vi.fn(),
    alertMock: vi.fn(),
    restoreSchoolMock: vi.fn(),
    previewPurgeSchoolMock: vi.fn(),
    purgeSchoolMock: vi.fn(),
  }
})

const authStateRB = { user: { role: 'admin', id: 1 }, canViewDeleted: true }
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authStateRB,
}))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
}))

vi.mock('@/composables/useDesensitize', () => ({
  useDesensitize: () => ({ ds: dsMock }),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { alert: alertMock, confirm: confirmMock, prompt: promptMock },
}))

// 回收站（Phase C）三接口：恢复 / 彻底删除预览 / 彻底删除
vi.mock('@/api/schoolsRecycle', () => ({
  restoreSchool: restoreSchoolMock,
  previewPurgeSchool: previewPurgeSchoolMock,
  purgeSchool: purgeSchoolMock,
  request: { get: requestGetMock },
}))

vi.mock('@/api/request', () => ({
  default: { get: requestGetMock },
  del: delMock,
  apiRequest: apiRequestMock,
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

// handleExport 已收敛为 downloadBlobAsFile（L3 修复），mock 该 helper 以断言新契约
vi.mock('@/api/helpers/blobDownload', () => ({
  downloadBlobAsFile: downloadBlobAsFileMock,
  parseFileName: vi.fn(),
  getFileNameFromResponse: vi.fn(),
}))

vi.mock('@/api/schools', () => ({
  schoolApi: { getStatistics: getStatsMock },
}))

vi.mock('@/api/import', () => ({
  downloadImportTemplateAndSave: downloadTplMock,
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { getToken: getTokenMock },
}))

vi.mock('@/utils/echarts', () => ({
  default: {
    init: echartsInit,
    graphic: { LinearGradient: class {} },
  },
}))

import List from '@/views/schools/List.vue'

// fetchData 表格数据（驱动 stats/charts）
const schoolA = {
  id: 1,
  name: '阳光小学',
  type: 'primary',
  support_unit: '某部队',
  student_count: 120,
  teacher_count: 30,
  support_status: 'active',
  address: '贵州省贵阳市',
  created_at: '2024-01-01T10:00:00',
}
const schoolB = {
  id: 2,
  name: '希望中学',
  type: 'middle',
  support_unit: '某单位',
  students: 80,
  teachers: 20,
  support_status: 'completed',
  address: '遵义市',
  created_at: '2024-02-01T10:00:00',
}

const fullStats = {
  total_schools: 8,
  active: 3,
  completed: 2,
  total_students: 500,
  total_teachers: 60,
  project_count: 4,
  project_total_budget: 1000,
  scholarship_count: 12,
  scholarship_total_amount: 300,
}

// el-table-column 注入的三行样本：
// colRowA 全字段；colRowB 无 id/未知类型/students 回退/未知状态/无创建时间；colRowC 空类型/长名/无计数
const colRowA = { ...schoolA }
const colRowB = {
  name: '无ID学校',
  type: 'alien',
  support_unit: '',
  students: 5,
  teachers: 2,
  support_status: 'weird',
  address: '',
  created_at: '',
}
const colRowC = {
  id: 3,
  name: '非常长名字的学校超过八个字',
  type: '',
  support_status: 'completed',
  address: '凯里市',
  created_at: '2024-03-01T10:00:00',
}

const mountOptions = {
  global: {
    renderStubDefaultSlot: true,
    stubs: {
      // el-table 需渲染 empty 具名插槽；el-result 需 extra；el-dialog 需 footer；
      // el-upload 需 tip；el-popconfirm 需 reference
      'el-table': {
        name: 'ElTable',
        template: '<div class="el-table-stub"><slot name="empty" /><slot /></div>',
      },
      'el-result': {
        name: 'ElResult',
        template: '<div class="el-result-stub"><slot name="extra" /></div>',
      },
      'el-dialog': {
        name: 'ElDialog',
        template: '<div class="el-dialog-stub"><slot /><slot name="footer" /></div>',
        emits: ['update:modelValue'],
      },
      'el-upload': {
        name: 'ElUpload',
        template: '<div class="el-upload-stub"><slot /><slot name="tip" /></div>',
      },
      'el-popconfirm': {
        name: 'ElPopconfirm',
        template: '<div class="el-popconfirm-stub"><slot name="reference" /><slot /></div>',
        emits: ['confirm'],
      },
      // 默认桩不会 emit update:modelValue，导致 v-model 编译产物
      // onUpdate:modelValue@144 永远不被执行；此处提供可 emit 的桩。
      'el-switch': {
        name: 'ElSwitch',
        props: { modelValue: { type: Boolean, default: false } },
        emits: ['update:modelValue', 'change'],
        template:
          '<button type="button" class="el-switch-stub" :data-on="String(modelValue)"' +
          ' @click="$emit(\'update:modelValue\', !modelValue); $emit(\'change\', !modelValue)"><slot /></button>',
      },
      // 三行样本注入每个列默认插槽，覆盖列模板两侧分支
      'el-table-column': {
        name: 'ElTableColumn',
        template:
          '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>',
        data() {
          return { rowA: { ...colRowA }, rowB: { ...colRowB }, rowC: { ...colRowC } }
        },
      },
    },
  },
}

function mountComp(target: any = List) {
  return mount(target, mountOptions)
}

beforeEach(() => {
  vi.resetAllMocks()
  apiRequestMock.mockResolvedValue({ data: { items: [schoolA, schoolB], total: 2 } })
  getStatsMock.mockResolvedValue(fullStats)
  delMock.mockResolvedValue({})
  downloadTplMock.mockResolvedValue(undefined)
  getTokenMock.mockReturnValue('tok')
  fetchMock.mockResolvedValue({ ok: true, blob: () => Promise.resolve(new Blob(['x'])) })
  downloadBlobAsFileMock.mockResolvedValue(undefined)
  echartsInit.mockImplementation(() => ({
    setOption: chartSetOption,
    dispose: chartDispose,
    resize: chartResize,
  }))
  dsMock.mockImplementation((v: any) => v)
  restoreSchoolMock.mockResolvedValue({})
  previewPurgeSchoolMock.mockResolvedValue({ data: { total_references: 0 } })
  purgeSchoolMock.mockResolvedValue({ data: { deleted_records: 0 } })
  confirmMock.mockResolvedValue({ value: undefined })
  promptMock.mockResolvedValue({ value: 'pw' })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('挂载与初始化', () => {
  it('onMounted：加载数据/统计/图表，注册 resize，卸载销毁图表', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(apiRequestMock).toHaveBeenCalledWith({
      method: 'GET',
      url: '/schools',
      params: {
        page: 1,
        page_size: 20,
        keyword: undefined,
        type: undefined,
        support_status: undefined,
      },
    })
    expect(vm.tableData).toHaveLength(2)
    expect(vm.total).toBe(2)
    expect(vm.loading).toBe(false)
    expect(getStatsMock).toHaveBeenCalled()
    expect(vm.apiStats.project_count).toBe(4)
    // 服务端统计优先
    expect(vm.stats).toEqual({
      total: 8,
      active: 3,
      completed: 2,
      totalStudents: 500,
      totalTeachers: 60,
    })
    // 上传头携带 token
    expect(vm.uploadHeaders).toMatchObject({ Authorization: 'Bearer tok', 'X-CSRF-Token': 'test-csrf' })
    // 图表已初始化并 setOption
    expect(echartsInit).toHaveBeenCalledTimes(2)
    expect(chartSetOption).toHaveBeenCalled()
    // resize 监听 → 两个图表实例共享 resize mock
    window.dispatchEvent(new Event('resize'))
    expect(chartResize).toHaveBeenCalled()
    // 卸载 → 移除监听 + 销毁图表
    wrapper.unmount()
    expect(chartDispose).toHaveBeenCalledTimes(2)
  })

  it('fetchData：无 .data 包装 / 内层数组 / 内层非数组 三种形态', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    apiRequestMock.mockResolvedValueOnce({ items: [schoolA], total: 5 }) // res.data || res → res
    await vm.fetchData()
    expect(vm.tableData).toHaveLength(1)
    expect(vm.total).toBe(5)

    apiRequestMock.mockResolvedValueOnce({ data: [schoolA] }) // 内层数组 → 直接用
    await vm.fetchData()
    expect(vm.tableData).toHaveLength(1)
    expect(vm.total).toBe(1) // inner.total 缺失 → 以长度兜底

    apiRequestMock.mockResolvedValueOnce({ data: { foo: 1 } }) // 非数组无 items → 空表
    await vm.fetchData()
    expect(vm.tableData).toEqual([])
    expect(vm.total).toBe(0)
  })

  it('fetchData 失败：el-result 错误态与重试恢复；loadError 且有数据仍走表格', async () => {
    apiRequestMock.mockRejectedValueOnce(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(logError).toHaveBeenCalled()
    expect(vm.loadErrorMsg).toBe('net')
    expect(ElMessage.error).not.toHaveBeenCalled()
    expect(vm.loadError).toBe(true)
    expect(vm.tableData).toEqual([])
    await nextTick()
    expect(wrapper.find('.el-result-stub').exists()).toBe(true)

    // 点击“重试”→ 恢复成功
    apiRequestMock.mockResolvedValue({ data: { items: [schoolA], total: 1 } })
    const retry = wrapper.findAll('el-button-stub').find((b) => b.text().includes('重试'))
    expect(retry).toBeTruthy()
    await retry!.trigger('click')
    await flushPromises()
    expect(vm.tableData).toHaveLength(1)
    expect(wrapper.find('.el-result-stub').exists()).toBe(false)

    // loadError=true 但表格有数据 → v-if 第二操作数为假 → 仍渲染表格
    vm.loadError = true
    await nextTick()
    expect(wrapper.find('.el-table-stub').exists()).toBe(true)
  })

  it('el-result：loadErrorMsg 为空 → sub-title 兜底「请稍后重试」', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.tableData = []
    vm.loadError = true
    vm.loadErrorMsg = ''
    await nextTick()
    const result = wrapper.find('.el-result-stub')
    expect(result.exists()).toBe(true)
    expect(result.attributes('sub-title')).toBe('请稍后重试')
  })

  it('stats computed：服务端字段 ?? 回退与本地兜底全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 服务端字段缺失 → ?? 各级回退
    vm.serverSchoolStats = { total_schools: null, total_students: null, total_teachers: null }
    vm.tableData = [{ student_count: 10 }, { students: 5 }, {}]
    vm.total = 7
    expect(vm.stats).toEqual({
      total: 7,
      active: 0,
      completed: 0,
      totalStudents: 15,
      totalTeachers: 0,
    })
    vm.total = 0 // total.value falsy → tableData.length
    expect(vm.stats.total).toBe(3)

    // 无服务端统计 → 本地计算
    vm.serverSchoolStats = null
    vm.tableData = [
      { support_status: 'active', student_count: 10 },
      { support_status: 'completed', students: 3, teachers: 1 },
      {},
    ]
    expect(vm.stats).toEqual({
      total: 3,
      active: 1,
      completed: 1,
      totalStudents: 13,
      totalTeachers: 1,
    })
    vm.total = 9
    expect(vm.stats.total).toBe(9) // total.value || list.length → total
  })

  it('loadApiStats：异常提示；data 为 null → 不更新服务端统计', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    getStatsMock.mockRejectedValueOnce(new Error('net'))
    await vm.loadApiStats()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('统计数据加载失败')

    const before = vm.serverSchoolStats
    wrapper.unmount() // 卸载后渲染效应停止，apiStats 置 null 不会触发模板空指针
    getStatsMock.mockResolvedValueOnce(null)
    await vm.loadApiStats()
    expect(vm.serverSchoolStats).toBe(before) // data falsy → 不更新服务端统计
  })
})

describe('搜索 / 重置 / 分页 / 状态卡', () => {
  it('筛选 v-model、搜索带参、重置清空', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    const keywordInput = wrapper.findComponent({ name: 'ElInput' })
    keywordInput.vm.$emit('update:modelValue', '阳光')
    expect(vm.filterForm.keyword).toBe('阳光')
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(selects.length).toBe(2)
    selects[0].vm.$emit('update:modelValue', 'primary')
    selects[1].vm.$emit('update:modelValue', 'active')
    expect(vm.filterForm.type).toBe('primary')
    expect(vm.filterForm.status).toBe('active')

    vm.currentPage = 3
    apiRequestMock.mockClear()
    const searchBtn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('搜索'))
    await searchBtn!.trigger('click')
    expect(vm.currentPage).toBe(1)
    expect(apiRequestMock).toHaveBeenCalledWith(
      expect.objectContaining({
        params: {
          page: 1,
          page_size: 20,
          keyword: '阳光',
          type: 'primary',
          support_status: 'active',
        },
      })
    )

    // 输入框回车也触发搜索（withKeys 真实链路）
    keywordInput.vm.$emit('keyup', { key: 'enter' })

    const resetBtn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '重置')
    await resetBtn!.trigger('click')
    expect(vm.filterForm).toEqual({ keyword: '', type: '', status: '' })
    expect(vm.currentPage).toBe(1)
  })

  it('状态卡：点击与 enter/space 键盘触发 filterByStatus', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const items = wrapper.findAll('.stat-item.clickable')
    expect(items.length).toBe(3)

    apiRequestMock.mockClear()
    await items[0].trigger('click')
    expect(vm.filterForm.status).toBe('')
    await items[1].trigger('click')
    expect(vm.filterForm.status).toBe('active')
    await items[2].trigger('click')
    expect(vm.filterForm.status).toBe('completed')
    expect(apiRequestMock).toHaveBeenCalledTimes(3)

    // 键盘 enter / space 触发同组内联处理器（每项的 enter 与 space 均覆盖）
    await items[0].trigger('keydown', { key: 'enter' })
    expect(vm.filterForm.status).toBe('')
    await items[1].trigger('keydown', { key: ' ' })
    expect(vm.filterForm.status).toBe('active')
    await items[2].trigger('keydown', { key: 'enter' })
    expect(vm.filterForm.status).toBe('completed')
    await items[0].trigger('keydown', { key: ' ' })
    expect(vm.filterForm.status).toBe('')
    await items[2].trigger('keydown', { key: ' ' })
    expect(vm.filterForm.status).toBe('completed')
    expect(apiRequestMock).toHaveBeenCalledTimes(8)
  })

  it('分页：v-model 更新与 size-change/current-change 事件', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const pager = wrapper.findComponent({ name: 'ElPagination' })
    expect(pager.exists()).toBe(true)

    pager.vm.$emit('update:currentPage', 2)
    expect(vm.currentPage).toBe(2)
    pager.vm.$emit('update:pageSize', 50)
    expect(vm.pageSize).toBe(50)

    apiRequestMock.mockClear()
    vm.currentPage = 4
    pager.vm.$emit('size-change')
    expect(vm.currentPage).toBe(1)
    expect(apiRequestMock).toHaveBeenCalledTimes(1)
    pager.vm.$emit('current-change')
    expect(apiRequestMock).toHaveBeenCalledTimes(2)
  })
})

describe('查看 / 编辑 / 删除 / 新增', () => {
  it('新增学校按钮跳转创建页', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('新增学校'))
    await btn!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/schools/create')
  })

  it('行内查看/编辑/删除（含无 id 早退）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    // 学校名称列 el-link → handleView
    const link = wrapper.findAll('el-link-stub').find((l) => l.text().includes('阳光小学'))
    expect(link).toBeTruthy()
    await link!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/schools/1')

    // 操作列 查看/编辑 按钮（取第一个有 id 行）
    const viewBtn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '查看')
    await viewBtn!.trigger('click')
    const editBtn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '编辑')
    await editBtn!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/schools/1/edit')

    // popconfirm 确认删除第一个样本行（id=1）
    apiRequestMock.mockClear()
    const pops = wrapper.findAllComponents({ name: 'ElPopconfirm' })
    expect(pops.length).toBe(3)
    pops[0].vm.$emit('confirm')
    await flushPromises()
    expect(delMock).toHaveBeenCalledWith('/schools/1')
    // 成功静默：删除成功不弹提示
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(vm.currentPage).toBe(1)
    expect(apiRequestMock).toHaveBeenCalled()

    // 无 id 行（第二个样本）→ 查看/编辑/删除均早退
    pushSafeMock.mockClear()
    delMock.mockClear()
    const viewBtns = wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '查看')
    const editBtns = wrapper.findAll('el-button-stub').filter((b) => b.text().trim() === '编辑')
    await viewBtns[1].trigger('click') // colRowB 无 id
    await editBtns[1].trigger('click')
    pops[1].vm.$emit('confirm')
    await flushPromises()
    expect(pushSafeMock).not.toHaveBeenCalled()
    expect(delMock).not.toHaveBeenCalled()

    // 直接调用：null/缺 id 早退；删除失败记录日志
    await vm.handleView(null)
    await vm.handleEdit(undefined)
    await vm.handleDelete({})
    expect(delMock).not.toHaveBeenCalled()
    delMock.mockRejectedValueOnce(new Error('fk'))
    await vm.handleDelete({ id: 5 })
    expect(logError).toHaveBeenCalled()
  })

  it('列模板：类型/状态/计数/时间/脱敏全分支渲染', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const text = wrapper.text()
    expect(text).toContain('小学') // typeMap 命中
    expect(text).toContain('alien') // typeMap 未命中 → 原始值
    expect(text).toContain('未帮扶') // statusMap 未命中兜底
    expect(text).toContain('帮扶中')
    expect(text).toContain('已完成')
    expect(text).toContain('2024-01-01') // created_at 切分
    expect(dsMock).toHaveBeenCalledWith('贵州省贵阳市', 'address')
    const vm = wrapper.vm as any
    expect(vm.getStatusTagType('active')).toBe('success')
    expect(vm.getStatusTagType('completed')).toBe('primary')
    expect(vm.getStatusTagType('other')).toBe('info')
  })
})

describe('统计图表', () => {
  it('buildStudentBarOption：名称截断/缺省、计数字段回退、排序反转', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.tableData = [
      { name: '非常长名字的学校超过八个字', student_count: 50 },
      { name: '短名', students: 30 },
      { id: 9 }, // name 缺失 → '-'，计数缺失 → 0
    ]
    const opt = vm.buildStudentBarOption()
    expect(opt.yAxis.data).toContain('非常长名字的学校…')
    expect(opt.yAxis.data).toContain('短名')
    expect(opt.yAxis.data).toContain('-')
    expect(opt.series[0].data[opt.series[0].data.length - 1]).toBe(50) // 降序后反转 → 最大在末位
  })

  it('buildTypePieOption：类型计数/映射/兜底与 tooltip formatter', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.tableData = [{ type: 'primary' }, { type: 'primary' }, { type: 'alien' }, {}]
    const opt = vm.buildTypePieOption()
    expect(opt.series[0].data[0]).toEqual({ value: 2, name: '小学' })
    const names = opt.series[0].data.map((d: any) => d.name)
    expect(names).toContain('alien') // typeMap 未命中 → 原 key
    expect(names).toContain('其他') // type 缺失 → other → 映射
    const tip = opt.tooltip.formatter({ marker: 'M', name: '小学', value: 2, percent: 50 })
    expect(tip).toContain('小学')
    expect(tip).toContain('2所')
  })

  it('renderCharts：二次渲染先销毁旧实例；refs 缺失时跳过初始化', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(echartsInit).toHaveBeenCalledTimes(2)

    apiRequestMock.mockResolvedValueOnce({ data: { items: [schoolA], total: 1 } }) // 新数组引用 → watch 才触发
    await vm.fetchData() // tableData 变更 → watch → 重绘
    await flushPromises()
    expect(chartDispose).toHaveBeenCalledTimes(2) // 销毁首批实例
    expect(echartsInit).toHaveBeenCalledTimes(4)

    const initCount = echartsInit.mock.calls.length
    vm.studentBarRef = undefined
    vm.typePieRef = undefined
    vm.renderCharts() // refs 缺失 → 只销毁不初始化
    expect(echartsInit.mock.calls.length).toBe(initCount)
  })
})

describe('导入 / 模板下载', () => {
  it('导入按钮内联赋值打开对话框；v-model 与关闭按钮关闭', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const importBtn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '导入')
    await importBtn!.trigger('click') // @click="showImportDialog = true" 内联箭头
    expect(vm.showImportDialog).toBe(true)

    const dialog = wrapper.findComponent({ name: 'ElDialog' })
    dialog.vm.$emit('update:modelValue', true)
    expect(vm.showImportDialog).toBe(true)

    const closeBtn = wrapper.findAll('el-button-stub').find((b) => b.text().trim() === '关闭')
    await closeBtn!.trigger('click') // @click="showImportDialog = false" 内联箭头
    expect(vm.showImportDialog).toBe(false)
  })

  it('下载模板：成功与失败提示', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('下载模板'))
    await btn!.trigger('click')
    await flushPromises()
    expect(downloadTplMock).toHaveBeenCalledWith('school', '学校')
    expect(ElMessage.error).not.toHaveBeenCalled()

    downloadTplMock.mockRejectedValueOnce(new Error('net'))
    await btn!.trigger('click')
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('模板下载失败，请重试')
  })

  it('beforeImportUpload：扩展名与大小校验四分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.beforeImportUpload({ name: 'a.xlsx', size: 100 })).toBe(true)
    expect(vm.beforeImportUpload({ name: 'a.xls', size: 100 })).toBe(true)
    expect(vm.beforeImportUpload({ name: 'a.txt', size: 100 })).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('只能上传 Excel 文件')
    expect(vm.beforeImportUpload({ name: 'a.xlsx', size: 11 * 1024 * 1024 })).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('文件大小不能超过 10MB')
  })

  it('onImportSuccess：message/缺省/errors/null 变体；onImportError', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.showImportDialog = true
    apiRequestMock.mockClear()

    vm.onImportSuccess({ message: '定制成功消息' })
    expect(ElMessage.success).toHaveBeenCalledWith('定制成功消息')
    expect(vm.showImportDialog).toBe(false)

    vm.onImportSuccess({ imported: 3 }) // message 缺失 → 缺省文案
    expect(ElMessage.success).toHaveBeenCalledWith('成功导入 3 所学校')

    vm.onImportSuccess({ errors: ['a', 'b'] }) // errors → 明细弹窗（ElMessageBox.alert）；imported 缺失 → 0
    expect(ElMessageBox.alert).toHaveBeenCalledTimes(1)
    expect(ElMessage.success).toHaveBeenCalledWith('成功导入 0 所学校')

    vm.onImportSuccess(null) // 全 ?. 兜底
    expect(ElMessage.success).toHaveBeenCalledWith('成功导入 0 所学校')
    expect(apiRequestMock).toHaveBeenCalledTimes(4)
    expect(vm.currentPage).toBe(1)

    vm.onImportError()
    expect(ElMessage.error).toHaveBeenCalledWith('导入失败，请检查文件格式')
  })
})

describe('导出', () => {
  // L3 修复后 handleExport 收敛为 downloadBlobAsFile(() => request.get(...), {fallbackFileName})，
  // 不再触碰全局 fetch / 锚点 click。SchoolsViewsBatch 已覆盖“调用一次 + options”，
  // 此处聚焦补充：requestFn 内部的 blob 请求契约 与 异常处理路径。
  it('handleExport 成功：走 downloadBlobAsFile，requestFn 请求 blob 端点', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleExport()
    expect(ElMessage.success).toHaveBeenCalledWith('正在导出学校数据...')
    // 收敛到统一 helper：downloadBlobAsFile 收到 (requestFn, options)
    expect(downloadBlobAsFileMock).toHaveBeenCalledTimes(1)
    const [requestFn, options] = downloadBlobAsFileMock.mock.calls[0]
    expect(typeof requestFn).toBe('function')
    expect(options).toEqual({ fallbackFileName: 'schools.xlsx' })
    // 执行 requestFn → 裸 axios 实例 GET blob 端点（用于解析 Content-Disposition 真实文件名）
    requestGetMock.mockResolvedValueOnce({ data: new Blob(['x']), headers: {} })
    await requestFn()
    expect(requestGetMock).toHaveBeenCalledWith('/schools/export/excel', { responseType: 'blob' })
    // 成功路径不报错
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('handleExport 异常：downloadBlobAsFile reject → 错误提示；不再触碰全局 fetch', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    downloadBlobAsFileMock.mockRejectedValueOnce(new Error('net'))
    await vm.handleExport()
    expect(ElMessage.error).toHaveBeenCalledWith('导出失败')
    // 旧契约已废弃：新代码路径不调用全局 fetch
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('特殊挂载路径', () => {
  it('uploadHeaders：空 token → 空 Authorization', async () => {
    getTokenMock.mockReturnValue('')
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).uploadHeaders).toMatchObject({ 'X-CSRF-Token': 'test-csrf' })
  })

  it('KeepAlive 包裹：onActivated 刷新数据并重绘图表', async () => {
    const Wrapper = defineComponent({
      render() {
        return h(KeepAlive, () => h(List))
      },
    })
    mountComp(Wrapper)
    await flushPromises()
    // onMounted + onActivated 各触发一次 fetchData / loadApiStats
    expect(apiRequestMock.mock.calls.length).toBe(2)
    expect(getStatsMock.mock.calls.length).toBe(2)
    // 注：onActivated 的 nextTick(handleChartResize) 先于图表初始化执行，resize 为空跳过分支
  })

  it('数据未返回时卸载：图表为空的清理分支不报错', async () => {
    apiRequestMock.mockReturnValue(new Promise(() => {}))
    getStatsMock.mockReturnValue(new Promise(() => {}))
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.handleChartResize() // 图表均为 null → ?. 跳过
    wrapper.unmount() // onUnmounted 中 ?.dispose 空分支
    expect(chartDispose).not.toHaveBeenCalled()
  })

  it('env：VITE_API_BASE_URL 生效（|| 左侧分支）', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://api.test')
    vi.resetModules()
    const { default: FreshList } = await import('@/views/schools/List.vue')
    const wrapper = mountComp(FreshList)
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.baseUrl).toBe('http://api.test')
    expect(vm.importUrl).toBe('http://api.test/schools/import/excel')
    wrapper.unmount()
    vi.unstubAllEnvs()
  })

  it('onImportSuccess：失败明细超过 10 条 → 追加「共 N 条失败」汇总行', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 11 条错误：slice(0,10) 只展示前 10 条，length > 10 命中 more 拼接真侧
    const errors = Array.from({ length: 11 }, (_, i) => ({ row: i + 1, error: `err-${i + 1}` }))
    vm.onImportSuccess({ data: { imported: 0, errors } })
    expect(alertMock).toHaveBeenCalledTimes(1)
    const [detail, title, opts] = alertMock.mock.calls[0]
    expect(title).toBe('导入失败明细')
    expect(opts).toMatchObject({ dangerouslyUseHTMLString: true, type: 'warning' })
    expect(detail).toContain('共 11 条失败')
    expect(detail).toContain('1. 第 1 行：err-1')
    expect(detail).toContain('10. 第 10 行：err-10')
    // 第 11 条被 slice 截断，不出现在明细正文中
    expect(detail).not.toContain('err-11')
    wrapper.unmount()
  })

  it('onImportSuccess：恰好 10 条 → more 为空串（length > 10 假侧）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const errors = Array.from({ length: 10 }, (_, i) => ({ row_index: i + 1, message: `m-${i + 1}` }))
    vm.onImportSuccess({ data: { errors } })
    const [detail] = alertMock.mock.calls[0]
    expect(detail).not.toContain('条失败')
    expect(detail).toContain('10. 第 10 行：m-10')
    wrapper.unmount()
  })
})

// ─────────────────────────────────────────────────────────────
// 回收站（Phase C 推广）：showDeletedOnly 开关 / 恢复 / 彻底删除
// 对应缺口 funcs handleToggleDeleted@702、handleRestore@707、handlePurge@727、
// onUpdate:modelValue@144、onClick@219、onClick@222；stmts@219-225,702-769；
// branch@218（v-if="showDeletedOnly"）
// ─────────────────────────────────────────────────────────────
describe('回收站（Phase C）', () => {
  it('canViewDeleted 为真 → 渲染 el-switch；点击开关回写 v-model 并触发 handleToggleDeleted', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.canViewDeleted).toBe(true)

    const sw = wrapper.find('.el-switch-stub')
    expect(sw.exists()).toBe(true)
    expect(sw.attributes('data-on')).toBe('false')

    const before = apiRequestMock.mock.calls.length
    vm.currentPage = 7 // 验证 toggle 会重置到第 1 页
    await sw.trigger('click')
    await flushPromises()

    // onUpdate:modelValue@144 编译产物被执行 → showDeletedOnly 翻转
    expect(vm.showDeletedOnly).toBe(true)
    expect(wrapper.find('.el-switch-stub').attributes('data-on')).toBe('true')
    // @change → handleToggleDeleted：页码归 1 + 重新拉取
    expect(vm.currentPage).toBe(1)
    expect(apiRequestMock.mock.calls.length).toBeGreaterThan(before)
    wrapper.unmount()
  })

  it('showDeletedOnly=true → 操作列渲染「恢复/彻底删除」而非 el-popconfirm（v-if 真侧）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    // 默认（假侧）：只有 el-popconfirm，没有恢复按钮
    expect(wrapper.find('.el-popconfirm-stub').exists()).toBe(true)
    expect(wrapper.findAll('el-button-stub').some((b) => b.text().includes('彻底删除'))).toBe(false)

    vm.showDeletedOnly = true
    await nextTick()
    // 真侧：恢复 / 彻底删除 出现，el-popconfirm 被 v-else 排除
    const texts = wrapper.findAll('el-button-stub').map((b) => b.text())
    expect(texts.filter((t) => t.includes('恢复')).length).toBeGreaterThan(0)
    expect(texts.filter((t) => t.includes('彻底删除')).length).toBeGreaterThan(0)
    expect(wrapper.find('.el-popconfirm-stub').exists()).toBe(false)
    wrapper.unmount()
  })

  it('模板内联 onClick@219/@222：点击「恢复」「彻底删除」按钮转发到对应 handler', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.showDeletedOnly = true
    await nextTick()
    // 不用 vi.spyOn(vm, ...)：script setup 的 setupState 代理不允许重定义属性；
    // 改为直接断言两个 handler 内部的第一手副作用（弹窗文案与 API 入参）。
    const restoreBtn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('恢复'))
    const purgeBtn = wrapper.findAll('el-button-stub').find((b) => b.text().includes('彻底删除'))
    expect(restoreBtn).toBeTruthy()
    expect(purgeBtn).toBeTruthy()

    await restoreBtn!.trigger('click')
    await flushPromises()
    // handleRestore 已被调用，且拿到的是列桩注入的第一行样本（rowA = schoolA）
    expect(confirmMock).toHaveBeenCalledWith('确定恢复学校【阳光小学】吗？', '恢复确认', expect.anything())
    expect(restoreSchoolMock).toHaveBeenCalledWith(1)

    await purgeBtn!.trigger('click')
    await flushPromises()
    // handlePurge 已被调用：先走预览，再以行名拼接警告文案
    expect(previewPurgeSchoolMock).toHaveBeenCalledWith(1)
    expect(confirmMock).toHaveBeenCalledWith(
      '彻底删除后【阳光小学】及其关联的 0 条数据将无法恢复！不可撤销。',
      '彻底删除警告',
      expect.anything()
    )
    wrapper.unmount()
  })

  describe('handleRestore', () => {
    it('确认 → restoreSchool(id) + 成功提示 + 页码归 1 + 刷新', async () => {
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      vm.currentPage = 3
      const before = apiRequestMock.mock.calls.length
      await vm.handleRestore({ id: 9, name: '希望中学' })
      await flushPromises()

      expect(confirmMock).toHaveBeenCalledWith(
        '确定恢复学校【希望中学】吗？',
        '恢复确认',
        expect.objectContaining({ confirmButtonText: '确认恢复', cancelButtonText: '取消', type: 'info' })
      )
      expect(restoreSchoolMock).toHaveBeenCalledWith(9)
      expect(ElMessage.success).toHaveBeenCalledWith('恢复成功')
      expect(vm.currentPage).toBe(1)
      expect(apiRequestMock.mock.calls.length).toBeGreaterThan(before)
      expect(ElMessage.error).not.toHaveBeenCalled()
      wrapper.unmount()
    })

    it('取消确认 → 直接 return，不调用 restoreSchool', async () => {
      confirmMock.mockRejectedValueOnce('cancel')
      const wrapper = mountComp()
      await flushPromises()
      await (wrapper.vm as any).handleRestore({ id: 9, name: 'X' })
      await flushPromises()
      expect(restoreSchoolMock).not.toHaveBeenCalled()
      expect(ElMessage.success).not.toHaveBeenCalled()
      expect(ElMessage.error).not.toHaveBeenCalled()
      wrapper.unmount()
    })

    it('restoreSchool 失败 → 错误提示「恢复失败」且不刷新页码', async () => {
      restoreSchoolMock.mockRejectedValueOnce(new Error('boom'))
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      vm.currentPage = 4
      const before = apiRequestMock.mock.calls.length
      await vm.handleRestore({ id: 9, name: 'X' })
      await flushPromises()
      expect(ElMessage.error).toHaveBeenCalledWith('恢复失败')
      expect(vm.currentPage).toBe(4) // 失败路径未执行重置
      expect(apiRequestMock.mock.calls.length).toBe(before)
      wrapper.unmount()
    })
  })

  describe('handlePurge', () => {
    it('预览取 data.total_references → 警告文案含引用条数 → purge 携带密码', async () => {
      previewPurgeSchoolMock.mockResolvedValueOnce({ data: { total_references: 7 } })
      purgeSchoolMock.mockResolvedValueOnce({ data: { message: '已彻底删除学校', deleted_records: 7 } })
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      vm.currentPage = 2
      const before = apiRequestMock.mock.calls.length

      await vm.handlePurge({ id: 5, name: '阳光小学' })
      await flushPromises()

      expect(previewPurgeSchoolMock).toHaveBeenCalledWith(5)
      expect(confirmMock).toHaveBeenCalledWith(
        '彻底删除后【阳光小学】及其关联的 7 条数据将无法恢复！不可撤销。',
        '彻底删除警告',
        expect.objectContaining({ confirmButtonText: '继续', type: 'warning' })
      )
      expect(promptMock).toHaveBeenCalledWith(
        '彻底删除【阳光小学】需二次确认，请输入登录密码：',
        '二次确认',
        expect.objectContaining({ confirmButtonText: '确认彻底删除', inputType: 'password' })
      )
      expect(purgeSchoolMock).toHaveBeenCalledWith(5, 'pw')
      // res.data.message 存在 → 优先使用（|| 左侧）
      expect(ElMessage.success).toHaveBeenCalledWith('已彻底删除学校')
      expect(vm.currentPage).toBe(1)
      expect(apiRequestMock.mock.calls.length).toBeGreaterThan(before)
      // finally 释放 loading
      expect(vm.loading).toBe(false)
      wrapper.unmount()
    })

    it('res 无 message → 回退「已清理 N 条关联数据」；deleted_records 缺失 → ?? 0', async () => {
      previewPurgeSchoolMock.mockResolvedValueOnce({ total_references: 0 }) // 无 data 包装 → pv 本身
      purgeSchoolMock.mockResolvedValueOnce({ data: { deleted_records: 3 } })
      const wrapper = mountComp()
      await flushPromises()
      await (wrapper.vm as any).handlePurge({ id: 5, name: 'A' })
      await flushPromises()
      expect(confirmMock).toHaveBeenCalledWith(
        expect.stringContaining('关联的 0 条数据'),
        '彻底删除警告',
        expect.anything()
      )
      expect(ElMessage.success).toHaveBeenCalledWith('已清理 3 条关联数据')
      wrapper.unmount()

      purgeSchoolMock.mockResolvedValueOnce({}) // data 缺失 → 全链路 ?. 短路 → ?? 0
      const w2 = mountComp()
      await flushPromises()
      await (w2.vm as any).handlePurge({ id: 6, name: 'B' })
      await flushPromises()
      expect(ElMessage.success).toHaveBeenCalledWith('已清理 0 条关联数据')
      w2.unmount()
    })

    it('prompt 返回 value 为空 → confirmPassword 回退空串（r.value || ""）', async () => {
      promptMock.mockResolvedValueOnce({ value: undefined })
      const wrapper = mountComp()
      await flushPromises()
      await (wrapper.vm as any).handlePurge({ id: 5, name: 'A' })
      await flushPromises()
      expect(purgeSchoolMock).toHaveBeenCalledWith(5, '')
      wrapper.unmount()
    })

    it('inputValidator：空密码 → 返回错误文案；非空 → 返回 true', async () => {
      const wrapper = mountComp()
      await flushPromises()
      await (wrapper.vm as any).handlePurge({ id: 5, name: 'A' })
      await flushPromises()
      const opts = promptMock.mock.calls[0][2]
      expect(typeof opts.inputValidator).toBe('function')
      expect(opts.inputValidator('')).toBe('密码不能为空')
      expect(opts.inputValidator('   ')).toBe(true) // 仅判空串/falsy，空白串视为已输入
      expect(opts.inputValidator('pw')).toBe(true)
      wrapper.unmount()
    })

    it('预览失败 → 静默吞掉异常，totalRefs 保持 0 并继续后续确认', async () => {
      previewPurgeSchoolMock.mockRejectedValueOnce(new Error('preview down'))
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      await vm.handlePurge({ id: 5, name: 'A' })
      await flushPromises()
      expect(confirmMock).toHaveBeenCalledWith(
        '彻底删除后【A】及其关联的 0 条数据将无法恢复！不可撤销。',
        '彻底删除警告',
        expect.anything()
      )
      expect(purgeSchoolMock).toHaveBeenCalledWith(5, 'pw')
      expect(vm.loading).toBe(false)
      wrapper.unmount()
    })

    it('警告确认取消 → 不调用 prompt / purgeSchool', async () => {
      confirmMock.mockRejectedValueOnce('cancel')
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      await vm.handlePurge({ id: 5, name: 'A' })
      await flushPromises()
      expect(previewPurgeSchoolMock).toHaveBeenCalledWith(5)
      expect(promptMock).not.toHaveBeenCalled()
      expect(purgeSchoolMock).not.toHaveBeenCalled()
      expect(vm.loading).toBe(false) // 未进入 loading 段
      wrapper.unmount()
    })

    it('密码二次确认取消 → 不调用 purgeSchool，loading 未被置起', async () => {
      promptMock.mockRejectedValueOnce('cancel')
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      await vm.handlePurge({ id: 5, name: 'A' })
      await flushPromises()
      expect(confirmMock).toHaveBeenCalledTimes(1)
      expect(purgeSchoolMock).not.toHaveBeenCalled()
      expect(vm.loading).toBe(false)
      wrapper.unmount()
    })

    it('purgeSchool 失败 → 错误提示「彻底删除失败」，finally 仍释放 loading', async () => {
      purgeSchoolMock.mockRejectedValueOnce(new Error('purge down'))
      const wrapper = mountComp()
      await flushPromises()
      const vm = wrapper.vm as any
      vm.currentPage = 3
      const before = apiRequestMock.mock.calls.length
      await vm.handlePurge({ id: 5, name: 'A' })
      await flushPromises()
      expect(ElMessage.error).toHaveBeenCalledWith('彻底删除失败')
      expect(vm.loading).toBe(false)
      expect(vm.currentPage).toBe(3) // 失败路径不重置页码、不刷新
      expect(apiRequestMock.mock.calls.length).toBe(before)
      wrapper.unmount()
    })
  })
})
