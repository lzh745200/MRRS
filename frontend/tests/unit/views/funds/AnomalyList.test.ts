/**
 * views/funds/AnomalyList.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：onMounted 加载与参数组装（project_id/severity/type/resolved）、
 * 状态筛选 change、分页、openResolve、handleResolve（空说明/成功/失败）、
 * 模板分支（severity 三态/已处理未处理/操作按钮）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { ElMessage, lifecycleApi, pushSafeMock, routeBox } = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  lifecycleApi: {
    listAnomalies: vi.fn(),
    resolveAnomaly: vi.fn(),
  },
  pushSafeMock: vi.fn(),
  routeBox: { query: {} as Record<string, any> },
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeBox,
  // PageHeader 标准件的返回按钮依赖 useRouter；页面已接入 PageHeader（R34 精细化）
  useRouter: () => ({ back: vi.fn() }),
}))

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/api/fundLifecycle', () => ({ fundLifecycleApi: lifecycleApi }))

vi.mock('@/composables/useRouterSafe', () => ({
  useRouterSafe: () => ({ pushSafe: pushSafeMock }),
  safeRouteParam: (v: any) => Number(v) || v,
}))

import AnomalyList from '@/views/funds/AnomalyList.vue'

const anomalyInfo = {
  id: 1,
  anomaly_type_label: '超支',
  severity: 'info',
  severity_label: '提示',
  description: '描述A',
  detected_at: '2024-01-01T10:00:00',
  resolved: false,
  resolved_by: null,
  resolution: null,
}

const anomalyWarning = {
  id: 2,
  severity: 'warning',
  severity_label: '警告',
  resolved: false,
}

const anomalyDanger = {
  id: 3,
  severity: 'danger',
  severity_label: '严重',
  resolved: true,
  resolved_by: '王五',
  resolution: '已处理说明',
}

function mountComp() {
  return mount(AnomalyList, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-page-header': {
          name: 'ElPageHeader',
          template: '<div class="el-page-header-stub"><slot name="content" /><slot /></div>',
          emits: ['back'],
        },
        'el-card': { template: '<div class="el-card-stub"><slot /></div>' },
        'el-table': {
          template: '<div class="el-table-stub"><slot name="empty" /><slot name="default" /></div>',
        },
        'el-table-column': {
          name: 'ElTableColumn',
          template:
            '<div class="el-table-column-stub"><slot :row="rowA" /><slot :row="rowB" /><slot :row="rowC" /></div>',
          data() {
            return {
              rowA: { ...anomalyInfo },
              rowB: { ...anomalyWarning },
              rowC: { ...anomalyDanger },
            }
          },
        },
        'el-select': {
          template:
            "<div class=\"el-select-stub\" @click=\"$emit('update:modelValue', 'overspend'); $emit('change', 'overspend')\"><slot /></div>",
        },
        'el-option': { template: '<div class="el-option-stub" />' },
        'el-input': {
          template: '<div class="el-input-stub" @click="$emit(\'update:modelValue\', \'说明\')" />',
        },
        'el-button': {
          template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
          emits: ['click'],
        },
        'el-pagination': {
          template:
            '<div class="el-pagination-stub" @click="$emit(\'current-change\'); $emit(\'update:currentPage\', 2)" />',
        },
        'el-tag': { template: '<span class="el-tag-stub"><slot /></span>' },
        'el-dialog': {
          template:
            '<div class="el-dialog-stub" @click="$emit(\'update:modelValue\', false)"><slot /><slot name="footer" /></div>',
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  routeBox.query = {}
  lifecycleApi.listAnomalies.mockResolvedValue({
    items: [anomalyInfo, anomalyWarning, anomalyDanger],
    total: 3,
  })
  lifecycleApi.resolveAnomaly.mockResolvedValue({})
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('挂载与列表', () => {
  it('onMounted 加载（无 project_id/筛选）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(lifecycleApi.listAnomalies).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
    })
    expect(vm.anomalies).toHaveLength(3)
    expect(vm.total).toBe(3)
  })

  it('带 project_id 与全筛选参数组装', async () => {
    routeBox.query = { project_id: '7' }
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.filters.severity = 'danger'
    vm.filters.anomaly_type = 'overspend'
    vm.filters.resolved = 1
    lifecycleApi.listAnomalies.mockClear()
    await vm.loadData()
    expect(lifecycleApi.listAnomalies).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
      project_id: 7,
      severity: 'danger',
      anomaly_type: 'overspend',
      resolved: true,
    })

    vm.filters.resolved = 0
    lifecycleApi.listAnomalies.mockClear()
    await vm.loadData()
    expect(lifecycleApi.listAnomalies).toHaveBeenCalledWith(
      expect.objectContaining({ resolved: false })
    )
  })

  it('loadData 失败 → 错误提示', async () => {
    lifecycleApi.listAnomalies.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    expect(ElMessage.error).toHaveBeenCalledWith('加载失败')
    expect((wrapper.vm as any).loading).toBe(false)
  })

  it('loadData 缺 items/total → || 兜底', async () => {
    lifecycleApi.listAnomalies.mockResolvedValue({})
    const wrapper = mountComp()
    await flushPromises()
    expect((wrapper.vm as any).anomalies).toEqual([])
    expect((wrapper.vm as any).total).toBe(0)
  })

  it('筛选 change 与分页', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    lifecycleApi.listAnomalies.mockClear()
    await wrapper.find('.el-select-stub').trigger('click')
    await flushPromises()
    expect(lifecycleApi.listAnomalies).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'overspend' })
    )

    vm.page = 2
    lifecycleApi.listAnomalies.mockClear()
    await wrapper.find('.el-pagination-stub').trigger('click')
    await flushPromises()
    expect(lifecycleApi.listAnomalies).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }))
    expect(vm.page).toBe(2)
  })

  it('三个筛选 select v-model 更新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    for (const sel of wrapper.findAll('.el-select-stub')) {
      await sel.trigger('click')
    }
    await flushPromises()
    expect(vm.filters.severity).toBe('overspend')
    expect(vm.filters.anomaly_type).toBe('overspend')
    expect(vm.filters.resolved).toBe('overspend')
  })

  it('弹窗 v-model 关闭 + resolution 输入', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.resolveDialogVisible = true
    await wrapper.find('.el-dialog-stub').trigger('click')
    expect(vm.resolveDialogVisible).toBe(false)
    await wrapper.find('.el-input-stub').trigger('click')
    expect(vm.resolution).toBe('说明')
  })

  it('页头返回 → pushSafe /funds', async () => {
    const wrapper = mountComp()
    await flushPromises()
    // R34 精细化：页头改用共享 PageHeader 标准件（show-back + back-to），
    // 返回按钮为 .back-btn，点击后由 backTo 走 pushSafe('/funds')。
    await wrapper.find('.back-btn').trigger('click')
    expect(pushSafeMock).toHaveBeenCalledWith('/funds')
  })
})

describe('处理异常', () => {
  it('openResolve 重置并打开弹窗', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.resolution = '旧内容'
    vm.openResolve(anomalyInfo)
    expect(vm.currentAnomaly).toEqual(anomalyInfo)
    expect(vm.resolution).toBe('')
    expect(vm.resolveDialogVisible).toBe(true)
  })

  it('空处理说明 → warning', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentAnomaly = anomalyInfo
    vm.resolution = '   '
    await vm.handleResolve()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入处理说明')
    expect(lifecycleApi.resolveAnomaly).not.toHaveBeenCalled()
  })

  it('处理成功 → 提示 + 关弹窗 + 刷新', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentAnomaly = anomalyInfo
    vm.resolution = '已核实'
    lifecycleApi.listAnomalies.mockClear()
    await vm.handleResolve()
    expect(lifecycleApi.resolveAnomaly).toHaveBeenCalledWith(1, '已核实')
    expect(ElMessage.success).toHaveBeenCalledWith('已标记为已处理')
    expect(vm.resolveDialogVisible).toBe(false)
    expect(lifecycleApi.listAnomalies).toHaveBeenCalled()
  })

  it('处理失败 → detail 与兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentAnomaly = anomalyInfo
    vm.resolution = 'x'
    lifecycleApi.resolveAnomaly.mockRejectedValueOnce({ response: { data: { detail: '无权限' } } })
    await vm.handleResolve()
    expect(ElMessage.error).toHaveBeenCalledWith('无权限')

    lifecycleApi.resolveAnomaly.mockRejectedValueOnce(new Error('net'))
    await vm.handleResolve()
    expect(ElMessage.error).toHaveBeenCalledWith('处理失败')
    expect(vm.loading).toBe(false)
  })

  it('处理按钮（操作列）→ openResolve', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const btn = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('处理'))
    await btn!.trigger('click')
    expect((wrapper.vm as any).resolveDialogVisible).toBe(true)
  })

  it('确认处理按钮 + 取消按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.currentAnomaly = anomalyInfo
    vm.resolution = 'ok'
    lifecycleApi.listAnomalies.mockClear()
    const ok = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('确认处理'))
    await ok!.trigger('click')
    await flushPromises()
    expect(lifecycleApi.resolveAnomaly).toHaveBeenCalled()

    vm.resolveDialogVisible = true
    const cancel = wrapper.findAll('.el-button-stub').find((b) => b.text().includes('取消'))
    await cancel!.trigger('click')
    expect(vm.resolveDialogVisible).toBe(false)
  })
})

describe('模板分支', () => {
  it('severity 三态 / resolved 两态 / 检测时间格式化', async () => {
    const wrapper = mountComp()
    await flushPromises()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('提示')
    expect(wrapper.text()).toContain('警告')
    expect(wrapper.text()).toContain('严重')
    expect(wrapper.text()).toContain('已处理')
    expect(wrapper.text()).toContain('未处理')
    expect(wrapper.text()).toContain('2024-01-01 10:00:00')
  })
})
