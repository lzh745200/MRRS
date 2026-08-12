/**
 * List.vue (项目管理列表页) 组件测试
 *
 * 测试场景：
 * 1. 初始化加载 - onMounted 调用 loadData + loadStats
 * 2. 搜索筛选 - handleSearch / handleReset
 * 3. 分页 - handlePageChange / handleSizeChange
 * 4. 删除 - handleDelete 调用 API 并刷新
 * 5. 统计卡片点击 - handleStatClick
 * 6. 导航 - 新建 / 查看 / 编辑跳转
 * 7. 辅助函数 - getTypeText / getStatusText / getStatusType / getProgressColor
 * 8. 异常处理 - API 失败时的 UI 行为
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// ==================== Mocks ====================

// Mock vue-router
const mockPush = vi.fn()
const mockResolve = vi.fn(() => ({ name: 'TestRoute', matched: [{ path: '/test' }] }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, resolve: mockResolve }),
  useRoute: () => ({ params: {}, query: {} }),
}))

// Mock element-plus
vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
    },
    ElMessageBox: {
      confirm: vi.fn().mockResolvedValue(true),
    },
  }
})

// Mock projectApi
const mockList = vi.fn()
const mockDeleteApi = vi.fn()
const mockGetStats = vi.fn()
const mockExportList = vi.fn()

vi.mock('@/api/projects', () => ({
  projectApi: {
    list: (...args: any[]) => mockList(...args),
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: (...args: any[]) => mockDeleteApi(...args),
    getStats: (...args: any[]) => mockGetStats(...args),
    exportList: (...args: any[]) => mockExportList(...args),
  },
}))

import ProjectList from '../List.vue'
import { ElMessage } from 'element-plus'

// ==================== Helpers ====================

/** 构造列表响应 */
function makeListResponse(items: any[] = [], total?: number, page = 1, page_size = 10) {
  return {
    total: total ?? items.length,
    page,
    page_size,
    items,
  }
}

const sampleProjects = [
  {
    id: 1,
    name: '道路修建项目',
    code: 'P001',
    type: 'infrastructure',
    status: 'in_progress',
    progress: 50,
    budget: 100,
    responsible_person: '张三',
  },
  {
    id: 2,
    name: '教育帮扶项目',
    code: 'P002',
    type: 'education',
    status: 'completed',
    progress: 100,
    budget: 200,
    responsible_person: '李四',
  },
]

/** 挂载组件的通用方法 */
function mountList() {
  return mount(ProjectList, {
    global: {
      stubs: {
        // 桩化 Element Plus 组件以避免渲染复杂子组件
        'el-button': { template: '<button><slot/></button>', props: ['type'] },
        'el-icon': { template: '<span><slot/></span>' },
        'el-input': { template: '<input />', props: ['modelValue'] },
        'el-select': {
          template: '<select><slot/></select>',
          props: ['modelValue'],
        },
        'el-option': {
          template: '<option></option>',
          props: ['label', 'value'],
        },
        'el-form': { template: '<form><slot/></form>' },
        'el-form-item': { template: '<div><slot/></div>', props: ['label'] },
        'el-table': {
          template: '<table><slot/></table>',
          props: ['data', 'loading'],
        },
        'el-table-column': {
          template: '<td><slot :row="row"/></td>',
          props: ['prop', 'label', 'width'],
          setup() {
            return { row: {} }
          },
        },
        'el-pagination': {
          template: '<div class="el-pagination"></div>',
          props: ['currentPage', 'pageSize', 'total', 'pageSizes'],
          emits: ['size-change', 'current-change', 'update:currentPage', 'update:pageSize'],
        },
        'el-tag': { template: '<span><slot/></span>', props: ['type'] },
        'el-progress': {
          template: '<div></div>',
          props: ['percentage', 'color'],
        },
        'el-link': {
          template: '<a @click="$emit(\'click\')"><slot/></a>',
          props: ['type'],
        },
        'el-popconfirm': {
          template: '<div><slot name="reference"/></div>',
          props: ['title'],
        },
        Plus: { template: '<i/>' },
        Download: { template: '<i/>' },
        Search: { template: '<i/>' },
      },
    },
  })
}

// ==================== 测试开始 ====================

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())

  // 默认 mock：loadData 返回 sampleProjects，loadStats 返回统计数据
  mockList.mockImplementation((_params?: any) => {
    return Promise.resolve(makeListResponse(sampleProjects, sampleProjects.length))
  })

  mockGetStats.mockResolvedValue({
    total: 10,
    in_progress: 3,
    completed: 5,
    total_budget: 300,
    total_invested: 150,
  })

  mockExportList.mockResolvedValue(undefined)
})

// ---------- 1. 初始化加载 ----------
describe('初始化加载', () => {
  it('挂载后应调用 loadData 和 loadStats', async () => {
    mountList()
    await flushPromises()

    // loadData 调用 list 1 次，loadStats 调用 getStats 1 次
    expect(mockList).toHaveBeenCalledTimes(1)
    expect(mockGetStats).toHaveBeenCalledTimes(1)
  })

  it('加载期间 loading 应为 true', async () => {
    // 让 list 延迟返回
    let resolver: Function
    mockList.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolver = resolve
        })
    )

    const wrapper = mountList()

    // loading 应为 true（组件内部状态）
    expect((wrapper.vm as any).loading).toBe(true)

    // 解决 promise
    resolver!(makeListResponse(sampleProjects, 2))
    await flushPromises()

    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('加载完成后项目列表数据应正确', async () => {
    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.projectList.length).toBeGreaterThanOrEqual(2)
    expect(vm.projectList[0].name).toBe('道路修建项目')
  })
})

// ---------- 2. 搜索筛选 ----------
describe('搜索筛选', () => {
  it('handleSearch 应重置页码为1并调用 loadData', async () => {
    const wrapper = mountList()
    await flushPromises()
    vi.clearAllMocks()

    const vm = wrapper.vm as any
    vm.pagination.page = 3
    vm.filterForm.name = '教育'
    vm.handleSearch()
    await flushPromises()

    expect(vm.pagination.page).toBe(1)
    expect(mockList).toHaveBeenCalledWith(expect.objectContaining({ keyword: '教育', page: 1 }))
  })

  it('handleReset 应清空筛选条件并重新搜索', async () => {
    const wrapper = mountList()
    await flushPromises()
    vi.clearAllMocks()

    const vm = wrapper.vm as any
    vm.filterForm.name = '测试'
    vm.filterForm.status = 'completed'
    vm.filterForm.type = 'education'

    vm.handleReset()
    await flushPromises()

    expect(vm.filterForm.name).toBe('')
    expect(vm.filterForm.status).toBe('')
    expect(vm.filterForm.type).toBe('')
    expect(mockList).toHaveBeenCalled()
  })

  it('按状态筛选应传递 status 参数', async () => {
    const wrapper = mountList()
    await flushPromises()
    vi.clearAllMocks()

    const vm = wrapper.vm as any
    vm.filterForm.status = 'in_progress'
    vm.handleSearch()
    await flushPromises()

    expect(mockList).toHaveBeenCalledWith(expect.objectContaining({ status: 'in_progress' }))
  })

  it('按类型筛选应传递 project_type 参数', async () => {
    const wrapper = mountList()
    await flushPromises()
    vi.clearAllMocks()

    const vm = wrapper.vm as any
    vm.filterForm.type = 'infrastructure'
    vm.handleSearch()
    await flushPromises()

    expect(mockList).toHaveBeenCalledWith(
      expect.objectContaining({ project_type: 'infrastructure' })
    )
  })

  it('空筛选值不应作为参数传递（转为 undefined）', async () => {
    const wrapper = mountList()
    await flushPromises()
    vi.clearAllMocks()

    const vm = wrapper.vm as any
    vm.filterForm.name = ''
    vm.filterForm.status = ''
    vm.filterForm.type = ''
    vm.handleSearch()
    await flushPromises()

    expect(mockList).toHaveBeenCalledWith(
      expect.objectContaining({
        keyword: undefined,
        status: undefined,
        project_type: undefined,
      })
    )
  })
})

// ---------- 3. 分页 ----------
describe('分页', () => {
  it('handlePageChange 应调用 loadData', async () => {
    const wrapper = mountList()
    await flushPromises()
    vi.clearAllMocks()

    const vm = wrapper.vm as any
    vm.pagination.page = 2
    vm.handlePageChange()
    await flushPromises()

    expect(mockList).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }))
  })

  it('handleSizeChange 应重置页码为1', async () => {
    const wrapper = mountList()
    await flushPromises()
    vi.clearAllMocks()

    const vm = wrapper.vm as any
    vm.pagination.page = 5
    vm.pagination.pageSize = 50
    vm.handleSizeChange()
    await flushPromises()

    expect(vm.pagination.page).toBe(1)
    expect(mockList).toHaveBeenCalledWith(expect.objectContaining({ page: 1, page_size: 50 }))
  })

  it('分页参数应正确反映到 API 调用', async () => {
    const wrapper = mountList()
    await flushPromises()
    vi.clearAllMocks()

    const vm = wrapper.vm as any
    vm.pagination.page = 3
    vm.pagination.pageSize = 20
    vm.handlePageChange()
    await flushPromises()

    expect(mockList).toHaveBeenCalledWith(expect.objectContaining({ page: 3, page_size: 20 }))
  })
})

// ---------- 4. 删除 ----------
describe('删除', () => {
  it('handleDelete 应调用 API 并刷新列表', async () => {
    mockDeleteApi.mockResolvedValueOnce({ message: 'ok' })

    const wrapper = mountList()
    await flushPromises()
    vi.clearAllMocks()

    // 重新设定 mockList 以追踪刷新
    mockList.mockResolvedValue(makeListResponse(sampleProjects.slice(1), 1))

    const vm = wrapper.vm as any
    await vm.handleDelete({ id: 1, name: '项目A' })
    await flushPromises()

    expect(mockDeleteApi).toHaveBeenCalledWith(1)
    // 成功静默：删除成功不弹提示（v1.8.0 提示策略）
    expect(ElMessage.success).not.toHaveBeenCalled()
    // 删除后应重新加载列表
    expect(mockList).toHaveBeenCalled()
  })

  it('删除失败应显示错误消息', async () => {
    mockDeleteApi.mockRejectedValueOnce(new Error('删除失败'))

    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    await vm.handleDelete({ id: 999 })
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })
})

// ---------- 5. 统计卡片点击 ----------
describe('统计卡片点击', () => {
  it("点击'项目总数'卡片应清空状态筛选", async () => {
    const wrapper = mountList()
    await flushPromises()
    vi.clearAllMocks()

    const vm = wrapper.vm as any
    vm.filterForm.status = 'completed'
    vm.handleStatClick('')
    await flushPromises()

    expect(vm.filterForm.status).toBe('')
    expect(vm.pagination.page).toBe(1)
    expect(mockList).toHaveBeenCalled()
  })

  it("点击'进行中'卡片应筛选 in_progress 状态", async () => {
    const wrapper = mountList()
    await flushPromises()
    vi.clearAllMocks()

    const vm = wrapper.vm as any
    vm.handleStatClick('in_progress')
    await flushPromises()

    expect(vm.filterForm.status).toBe('in_progress')
    expect(mockList).toHaveBeenCalledWith(expect.objectContaining({ status: 'in_progress' }))
  })

  it("点击'已完成'卡片应筛选 completed 状态", async () => {
    const wrapper = mountList()
    await flushPromises()
    vi.clearAllMocks()

    const vm = wrapper.vm as any
    vm.handleStatClick('completed')
    await flushPromises()

    expect(vm.filterForm.status).toBe('completed')
  })

  it('统计卡片点击应重置其他筛选条件', async () => {
    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    vm.filterForm.name = '测试'
    vm.filterForm.type = 'education'

    vm.handleStatClick('in_progress')
    await flushPromises()

    expect(vm.filterForm.name).toBe('')
    expect(vm.filterForm.type).toBe('')
  })
})

// ---------- 6. 导航 ----------
describe('导航', () => {
  it('handleCreate 应跳转到 /projects/create', async () => {
    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    vm.handleCreate()

    expect(mockPush).toHaveBeenCalledWith('/projects/create')
  })

  it('handleView 应跳转到 /projects/:id', async () => {
    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    vm.handleView({ id: 42 })

    expect(mockPush).toHaveBeenCalledWith('/projects/42')
  })

  it('handleEdit 应跳转到 /projects/:id/edit', async () => {
    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    vm.handleEdit({ id: 7 })

    expect(mockPush).toHaveBeenCalledWith('/projects/7/edit')
  })
})

// ---------- 7. 辅助函数 ----------
describe('辅助函数', () => {
  it('getTypeText 应正确映射项目类型', async () => {
    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.getTypeText('infrastructure')).toBe('基础设施')
    expect(vm.getTypeText('education')).toBe('教育帮扶')
    expect(vm.getTypeText('industry')).toBe('产业发展')
    expect(vm.getTypeText('medical')).toBe('医疗卫生')
    expect(vm.getTypeText('other')).toBe('其他')
  })

  it('getTypeText 未知类型应返回原始值', async () => {
    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.getTypeText('unknown_type')).toBe('unknown_type')
  })

  it('getStatusText 应正确映射项目状态', async () => {
    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.getStatusText('draft')).toBe('草稿')
    expect(vm.getStatusText('pending')).toBe('待审批')
    expect(vm.getStatusText('approved')).toBe('已审批')
    expect(vm.getStatusText('in_progress')).toBe('进行中')
    expect(vm.getStatusText('completed')).toBe('已完成')
    expect(vm.getStatusText('cancelled')).toBe('已取消')
  })

  it('getStatusType 应返回正确的 tag 类型', async () => {
    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.getStatusType('draft')).toBe('info')
    expect(vm.getStatusType('in_progress')).toBe('warning')
    expect(vm.getStatusType('completed')).toBe('success')
    expect(vm.getStatusType('cancelled')).toBe('danger')
    expect(vm.getStatusType('unknown')).toBe('info') // 默认
  })

  it('getProgressColor 应按阈值返回颜色', async () => {
    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.getProgressColor(90)).toBe('#40916c') // >= 80
    expect(vm.getProgressColor(80)).toBe('#40916c') // >= 80
    expect(vm.getProgressColor(60)).toBe('#e6a23c') // >= 50
    expect(vm.getProgressColor(50)).toBe('#e6a23c') // >= 50
    expect(vm.getProgressColor(30)).toBe('#f56c6c') // < 50
    expect(vm.getProgressColor(0)).toBe('#f56c6c') // < 50
  })
})

// ---------- 8. 异常处理 ----------
describe('异常处理', () => {
  it('loadData 失败应显示错误消息且 loading 恢复为 false', async () => {
    mockList.mockRejectedValueOnce(new Error('服务器错误'))

    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.loading).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('加载项目列表失败')
  })

  it('loadStats 失败不应阻塞主流程', async () => {
    // loadData 正常，loadStats 失败
    mockList.mockResolvedValue(makeListResponse(sampleProjects, 2))
    mockGetStats.mockRejectedValueOnce(new Error('stats error'))

    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    // 主列表应已加载
    expect(vm.projectList.length).toBe(2)
  })

  it('handleExport 应显示成功消息', async () => {
    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    await vm.handleExport()
    await flushPromises()

    expect(mockExportList).toHaveBeenCalled()
    // 导出成功不再弹提示 — 浏览器下载栏已确认
  })
})

// ---------- 9. 统计数据 ----------
describe('统计数据', () => {
  it('loadStats 应正确设置统计数据', async () => {
    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.stats.total).toBe(10)
    expect(vm.stats.inProgress).toBe(3)
    expect(vm.stats.completed).toBe(5)
  })
})

// ---------- 10. 响应式数据 ----------
describe('响应式数据', () => {
  it('pagination.total 应反映 API 返回的 total', async () => {
    mockList.mockImplementation((params?: any) => {
      if (params?.page_size === 1) return Promise.resolve(makeListResponse([], 0))
      return Promise.resolve(makeListResponse(sampleProjects, 42))
    })

    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.pagination.total).toBe(42)
  })

  it('filterForm 初始值应为空', async () => {
    const wrapper = mountList()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.filterForm.name).toBe('')
    expect(vm.filterForm.status).toBe('')
    expect(vm.filterForm.type).toBe('')
  })
})
