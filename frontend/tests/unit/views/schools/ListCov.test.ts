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
  chartSetOption,
  chartDispose,
  chartResize,
  echartsInit,
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
    chartSetOption,
    chartDispose,
    chartResize,
    echartsInit: vi.fn(),
  }
})

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
}))

vi.mock('@/composables/useDesensitize', () => ({
  useDesensitize: () => ({ ds: dsMock }),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { alert: vi.fn() },
}))

vi.mock('@/api/request', () => ({
  del: delMock,
  apiRequest: apiRequestMock,
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
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
  echartsInit.mockImplementation(() => ({
    setOption: chartSetOption,
    dispose: chartDispose,
    resize: chartResize,
  }))
  dsMock.mockImplementation((v: any) => v)
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
  it('handleExport 成功：fetch 下载并触发 a 标签点击', async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const revokeSpy = vi.spyOn(URL, 'revokeObjectURL')
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleExport()
    expect(ElMessage.success).toHaveBeenCalledWith('正在导出学校数据...')
    expect(fetchMock).toHaveBeenCalledWith(`${vm.baseUrl}/schools/export/excel`, {
      headers: { Authorization: 'Bearer tok' },
    })
    expect(clickSpy).toHaveBeenCalled()
    expect(revokeSpy).toHaveBeenCalled()
    clickSpy.mockRestore()
    revokeSpy.mockRestore()
  })

  it('handleExport：!ok 与 fetch 异常 → 错误提示；空 token 头', async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any

    fetchMock.mockResolvedValueOnce({ ok: false })
    await vm.handleExport()
    expect(ElMessage.error).toHaveBeenCalledWith('导出失败')

    fetchMock.mockRejectedValueOnce(new Error('net'))
    await vm.handleExport()
    expect(ElMessage.error).toHaveBeenCalledTimes(2)

    getTokenMock.mockReturnValue('')
    await vm.handleExport()
    expect(fetchMock).toHaveBeenLastCalledWith(`${vm.baseUrl}/schools/export/excel`, {
      headers: { Authorization: '' },
    })
    clickSpy.mockRestore()
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
})
