/**
 * views/schools/Detail.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 加载学校/附件/项目/资助学生、teacherStudentRatio、
 * getTypeDisplay/getStatusDisplay/getStatusTagType/formatDate/getFileIcon/formatFileSize、
 * 删除（取消/成功/失败）、导航、模板分支。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

const { ElMessage, confirmMock, getMock, delMock, schoolApiMock, pushSafeMock, routeBox, logError } =
  vi.hoisted(() => ({
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
    confirmMock: vi.fn(),
    getMock: vi.fn(),
    delMock: vi.fn(),
    schoolApiMock: {
      listProjects: vi.fn(),
      listScholarshipStudents: vi.fn(),
    },
    pushSafeMock: vi.fn(),
    routeBox: { params: { id: '3' } as Record<string, any> },
    logError: vi.fn(),
  }))

vi.mock('vue-router', () => ({ useRoute: () => routeBox }))

vi.mock('element-plus', () => ({ ElMessage, ElMessageBox: { confirm: confirmMock } }))

vi.mock('@/api/request', () => ({
  get: getMock,
  del: delMock,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/api/schools', () => ({ schoolApi: schoolApiMock }))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
}))

vi.mock('@/composables/useDesensitize', () => ({
  useDesensitize: () => ({ ds: (v: any) => String(v ?? ''), role: 'viewer' }),
}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { getToken: () => 't' },
}))

import Detail from '@/views/schools/Detail.vue'

const school = {
  id: 3,
  name: '第一小学',
  code: 'SCH-001',
  type: 'primary',
  province: '贵州省',
  city: '都匀市',
  district: 'X区',
  address: '街道1号',
  student_count: 500,
  teacher_count: 20,
  class_count: 10,
  support_status: 'active',
  support_unit: '帮扶单位',
  principal: '王校长',
  contact_phone: '13800138000',
  email: 'a@b.com',
  description: '简介',
  remarks: '备注',
  created_at: '2024-01-01T00:00:00',
}

const project = { id: 1, name: '教学楼', category: '教学', phase: 'completed', budget: 100 }
const student = { id: 1, student_name: '张三', grade: '三年级', year: 2024, amount: 500, status: 'approved', reason: '家庭困难' }
const att = { id: 1, file_name: '报告.pdf', file_size: 2048, uploaded_by: '李四', created_at: '2024-01-02T00:00:00' }

const fetchMock = vi.hoisted(() => vi.fn())

function mountComp() {
  return mount(Detail, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-table': {
          template:
            '<div class="el-table-stub"><slot name="empty" /><slot name="default" /></div>',
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /></div>',
          data() {
            return {
              rowA: { ...project },
              rowB: { ...student },
            }
          },
        },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-descriptions': { template: '<div class="el-descriptions-stub"><slot /></div>' },
        'el-descriptions-item': { template: '<div class="el-desc-item-stub"><slot /></div>' },
        'el-empty': {
          template: '<div class="el-empty-stub">{{ description }}<slot /></div>',
          props: ['description'],
        },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-icon': { template: '<span class="el-icon-stub"><slot /></span>' },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  routeBox.params = { id: '3' }
  getMock.mockImplementation((url: string) => {
    if (url.includes('/attachments')) return Promise.resolve({ data: { items: [att] } })
    return Promise.resolve({ data: school })
  })
  schoolApiMock.listProjects.mockResolvedValue({ items: [project] })
  schoolApiMock.listScholarshipStudents.mockResolvedValue({ items: [student] })
  delMock.mockResolvedValue({})
  confirmMock.mockResolvedValue(undefined)
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockResolvedValue({ ok: true, blob: vi.fn().mockResolvedValue(new Blob(['x'])) })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('挂载与加载', () => {
  it('onMounted 并行加载 4 路数据', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(getMock).toHaveBeenCalledWith('/schools/3')
    expect(getMock).toHaveBeenCalledWith('/schools/3/attachments')
    expect(schoolApiMock.listProjects).toHaveBeenCalledWith(3)
    expect(schoolApiMock.listScholarshipStudents).toHaveBeenCalledWith(3)
    expect(vm.school.name).toBe('第一小学')
    expect(vm.attachments).toHaveLength(1)
    expect(vm.relatedProjects).toHaveLength(1)
    expect(vm.scholarshipStudents).toHaveLength(1)
    expect(vm.loading).toBe(false)
  })

  it('无 id → 错误 + 返回', async () => {
    routeBox.params = {}
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('无效的学校ID')
    expect(pushSafeMock).toHaveBeenCalledWith('/schools')
  })

  it('加载失败 → logger + 错误提示', async () => {
    getMock.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('加载学校信息失败')
  })

  it('学校响应为 falsy 原始值 → 错误提示并返回', async () => {
    getMock.mockImplementation((url: string) => {
      if (url.includes('/attachments')) return Promise.resolve({ data: { items: [] } })
      return Promise.resolve(0)
    })
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('加载学校信息失败')
    expect(pushSafeMock).toHaveBeenCalledWith('/schools')
  })

  it('无数据 → 错误提示（result 为 null 触发 catch）', async () => {
    getMock.mockResolvedValue(null)
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('加载学校信息失败')
  })

  it('字段缺失走兜底（students/teachers 别名）', async () => {
    getMock.mockResolvedValue({
      data: { id: 3, name: 'N', students: 10, teachers: 2 },
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.school.student_count).toBe(10)
    expect(vm.school.teacher_count).toBe(2)
  })

  it('字段全部缺失 → || 兜底', async () => {
    getMock.mockResolvedValue({ data: { id: 3, name: 'N' } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.school.name).toBe('N')
    expect(vm.school.code).toBe('')
    expect(vm.school.student_count).toBe(0)
    expect(vm.school.teacher_count).toBe(0)
    expect(vm.school.support_status).toBe('inactive')
  })

  it('学校响应 data 为空对象 → 全部 || 兜底', async () => {
    getMock.mockImplementation((url: string) => {
      if (url.includes('/attachments')) return Promise.resolve({ data: { items: [] } })
      return Promise.resolve({ data: undefined })
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.school.name).toBe('')
    expect(vm.school.student_count).toBe(0)
    expect(vm.school.teacher_count).toBe(0)
  })

  it('子数据加载失败 → logger 不阻塞', async () => {
    schoolApiMock.listProjects.mockRejectedValue(new Error('p'))
    schoolApiMock.listScholarshipStudents.mockRejectedValue(new Error('s'))
    getMock.mockRejectedValue(new Error('a'))
    const wrapper = mountComp()
    await flushPromises()
    expect(logError).toHaveBeenCalled()
  })

  it('项目/资助学生空响应 → 空数组', async () => {
    schoolApiMock.listProjects.mockResolvedValue({})
    schoolApiMock.listScholarshipStudents.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).relatedProjects).toEqual([])
    expect((wrapper.vm as any).scholarshipStudents).toEqual([])
  })

  it('附件直返数组格式', async () => {
    getMock.mockImplementation((url: string) => {
      if (url.includes('/attachments')) return Promise.resolve({ data: [att] })
      return Promise.resolve({ data: school })
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).attachments).toHaveLength(1)
  })

  it('附件响应无 data → || 兜底', async () => {
    getMock.mockImplementation((url: string) => {
      if (url.includes('/attachments')) return Promise.resolve({ data: undefined })
      return Promise.resolve({ data: school })
    })
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).attachments).toEqual([])
  })

  it('附件缺上传人/日期 → v-if 假侧', async () => {
    getMock.mockImplementation((url: string) => {
      if (url.includes('/attachments')) {
        return Promise.resolve({ data: { items: [{ id: 2, file_name: 'x.pdf', file_size: 10 }] } })
      }
      return Promise.resolve({ data: school })
    })
    const wrapper = mountComp()
    await flushPromises()
    await nextTick()
    expect(wrapper.text()).toContain('x.pdf')
  })
})

describe('computed 与字典函数', () => {
  it('teacherStudentRatio 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.teacherStudentRatio).toBe('1:25')

    vm.school.teacher_count = 0
    await nextTick()
    expect(vm.teacherStudentRatio).toBe('-')
  })

  it('getTypeDisplay 全映射与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getTypeDisplay('primary')).toBe('小学')
    expect(vm.getTypeDisplay('middle')).toBe('初中')
    expect(vm.getTypeDisplay('high')).toBe('高中')
    expect(vm.getTypeDisplay('vocational')).toBe('职业学校')
    expect(vm.getTypeDisplay('other')).toBe('其他')
    expect(vm.getTypeDisplay('x')).toBe('x')
    expect(vm.getTypeDisplay('')).toBe('-')
  })

  it('getStatusDisplay/getStatusTagType 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getStatusDisplay('active')).toBe('帮扶中')
    expect(vm.getStatusDisplay('inactive')).toBe('未帮扶')
    expect(vm.getStatusDisplay('completed')).toBe('已完成')
    expect(vm.getStatusDisplay('x')).toBe('未帮扶')
    expect(vm.getStatusTagType('active')).toBe('success')
    expect(vm.getStatusTagType('completed')).toBe('primary')
    expect(vm.getStatusTagType('inactive')).toBe('info')
  })

  it('formatDate 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatDate('2024-01-01T00:00:00')).toBe('2024-01-01')
    expect(vm.formatDate('')).toBe('-')
    expect(vm.formatDate(undefined)).toBe('-')
  })

  it('getFileIcon 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.getFileIcon('a.pdf')).toBeTruthy()
    expect(vm.getFileIcon('a.doc')).toBeTruthy()
    expect(vm.getFileIcon('a.xlsx')).toBeTruthy()
    expect(vm.getFileIcon('a.pptx')).toBeTruthy()
    expect(vm.getFileIcon('a.png')).toBeTruthy()
    expect(vm.getFileIcon('a.zip')).toBeTruthy()
    expect(vm.getFileIcon('a.unknown')).toBeTruthy()
    expect(vm.getFileIcon('')).toBeTruthy()
  })

  it('formatFileSize 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.formatFileSize(0)).toBe('0B')
    expect(vm.formatFileSize(500)).toBe('500B')
    expect(vm.formatFileSize(2048)).toBe('2.0KB')
    expect(vm.formatFileSize(2 * 1048576)).toBe('2.0MB')
  })

  it('phaseTagType 全分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.phaseTagType('completed')).toBe('success')
    expect(vm.phaseTagType('implementation')).toBe('primary')
    expect(vm.phaseTagType('acceptance')).toBe('warning')
    expect(vm.phaseTagType('x')).toBe('info')
  })
})

describe('导航与删除', () => {
  it('handleEdit/handleBack/管理项目/管理资助学生按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.handleEdit()
    expect(pushSafeMock).toHaveBeenCalledWith('/schools/3/edit')

    pushSafeMock.mockClear()
    vm.handleBack()
    expect(pushSafeMock).toHaveBeenCalledWith('/schools')

    pushSafeMock.mockClear()
    const proj = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('管理项目'))
    await proj!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/schools/3/projects')

    pushSafeMock.mockClear()
    const stu = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('管理资助学生'))
    await stu!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/schools/3/scholarship')

    // 结对帮扶台账入口：跳转按对象聚合的结对/走访台账（深链筛选）
    pushSafeMock.mockClear()
    const pairing = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('结对帮扶台账'))
    await pairing!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/pairings?partner_type=school&partner_id=3')
  })

  it('handleDelete 确认后成功', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleDelete()
    expect(confirmMock).toHaveBeenCalledWith('确定要删除这所学校吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    expect(delMock).toHaveBeenCalledWith('/schools/3')
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    expect(pushSafeMock).toHaveBeenCalledWith('/schools')
  })

  it('handleDelete 取消 → 静默', async () => {
    const wrapper = mountComp()
    await flushPromises()
    confirmMock.mockRejectedValueOnce('cancel')
    await (wrapper.vm as any).handleDelete()
    expect(delMock).not.toHaveBeenCalled()
  })

  it('handleDelete 失败 → logger', async () => {
    const wrapper = mountComp()
    await flushPromises()
    delMock.mockRejectedValueOnce(new Error('net'))
    await (wrapper.vm as any).handleDelete()
    expect(logError).toHaveBeenCalled()
  })

  it('删除/编辑按钮点击', async () => {
    const wrapper = mountComp()
    await flushPromises()
    pushSafeMock.mockClear()
    const edit = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('编辑'))
    await edit!.trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/schools/3/edit')

    const del = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('删除'))
    await del!.trigger('click')
    await flushPromises()
    expect(delMock).toHaveBeenCalled()
  })
})

describe('附件下载与模板', () => {
  it('downloadAttachment 成功/失败', async () => {
    const clickSpy = vi.spyOn(HTMLElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).downloadAttachment(att)
    expect(fetchMock).toHaveBeenCalled()

    fetchMock.mockRejectedValue(new Error('net'))
    await (wrapper.vm as any).downloadAttachment(att)
    await flushPromises()
    expect(logError).toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('下载失败，请重试')
    clickSpy.mockRestore()
  })

  it('downloadAttachment 无 token → 空 Authorization', async () => {
    const clickSpy = vi.spyOn(HTMLElement.prototype, 'click').mockImplementation(() => {})
    vi.mocked(await import('@/utils/authStorage')).AuthStorage.getToken = () => ''
    const wrapper = mountComp()
    await flushPromises()
    await (wrapper.vm as any).downloadAttachment(att)
    const arg = fetchMock.mock.calls[0][1]
    expect(arg.headers.Authorization).toBe('')
    clickSpy.mockRestore()
  })

  it('附件下载按钮点击', async () => {
    const clickSpy = vi.spyOn(HTMLElement.prototype, 'click').mockImplementation(() => {})
    const wrapper = mountComp()
    await flushPromises()
    const dl = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('下载'))
    await dl!.trigger('click')
    await flushPromises()
    expect(fetchMock).toHaveBeenCalled()
    clickSpy.mockRestore()
  })

  it('空态渲染：无项目/无学生/无附件', async () => {
    schoolApiMock.listProjects.mockResolvedValue({ items: [] })
    schoolApiMock.listScholarshipStudents.mockResolvedValue({ items: [] })
    getMock.mockImplementation((url: string) => {
      if (url.includes('/attachments')) return Promise.resolve({ data: { items: [] } })
      return Promise.resolve({ data: school })
    })
    const wrapper = mountComp()
    await flushPromises()
    await nextTick()
    expect(wrapper.text()).toContain('暂无助学兴教项目')
    expect(wrapper.text()).toContain('暂无资助学生')
    expect(wrapper.text()).toContain('暂无电子资料')
  })

  it('附件元信息渲染（上传人/日期）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await nextTick()
    expect(wrapper.text()).toContain('报告.pdf')
    expect(wrapper.text()).toContain('李四')
  })
})
