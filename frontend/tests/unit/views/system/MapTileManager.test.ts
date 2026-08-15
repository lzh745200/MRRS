/**
 * views/system/MapTileManager.vue 覆盖率攻坚
 * 覆盖：状态加载、下载/清理确认、预设区域、缩放级别数据
 *
 * 后端契约（backend/app/api/v1/offline_map.py）：
 * - GET  /offline-map/status   → { success, data: { total_tiles, total_size_mb, zoom_levels } }
 * - POST /offline-map/download → { success, data: { region } }  （无 downloaded/failed 计数）
 * - DELETE /offline-map/clear  → { success, message }           （整体清理，无 data 键）
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const { ElMessage, ElMessageBox, mockGetMapStatus, mockDownloadTiles, mockClearTiles } =
  vi.hoisted(() => ({
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
    ElMessageBox: { confirm: vi.fn(), alert: vi.fn() },
    mockGetMapStatus: vi.fn(),
    mockDownloadTiles: vi.fn(),
    mockClearTiles: vi.fn(),
  }))

vi.mock('@/api/offlineMap', () => ({
  getMapStatus: mockGetMapStatus,
  downloadTiles: mockDownloadTiles,
  clearTiles: mockClearTiles,
  offlineMapApi: { getTiles: vi.fn(), getStatus: vi.fn() },
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox,
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

import MapTileManager from '@/views/system/MapTileManager.vue'

const coverageData = {
  total_tiles: 1000,
  total_size_mb: 500,
  zoom_levels: { '4': 100, '8': 300, '12': 600 },
}

// 与后端 download 端点 region 构造一致（默认表单值）
const DEFAULT_REGION = '24.5,103.6-29.2,109.5@4-12'
// 与后端 clear 端点返回的 message 一致
const CLEAR_MESSAGE = '瓦片缓存已清理'

async function mountComp() {
  const w = mount(MapTileManager, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-card': {
          name: 'ElCard',
          template: '<div class="el-card-stub"><slot /><slot name="header" /></div>',
        },
        'el-descriptions': { name: 'ElDescriptions', template: '<dl><slot /></dl>' },
        'el-descriptions-item': {
          name: 'ElDescriptionsItem',
          template: '<div class="el-desc-item-stub"><slot /></div>',
        },
        'el-alert': {
          name: 'ElAlert',
          template: '<div class="el-alert-stub"><slot /><slot name="title" /></div>',
        },
        'el-table': { name: 'ElTable', template: '<table class="el-table-stub"><slot /></table>' },
        'el-table-column': {
          name: 'ElTableColumn',
          template: '<div class="el-table-column-stub"><slot :row="row" /></div>',
          data() {
            return { row: { level: 8, count: 300 } }
          },
        },
        'el-button': {
          name: 'ElButton',
          template: '<button class="el-button-stub"><slot /></button>',
        },
        'el-form': { name: 'ElForm', template: '<form><slot /></form>' },
        'el-form-item': { name: 'ElFormItem', template: '<div><slot /></div>' },
        'el-row': { name: 'ElRow', template: '<div class="el-row-stub"><slot /></div>' },
        'el-col': { name: 'ElCol', template: '<div class="el-col-stub"><slot /></div>' },
        'el-input-number': {
          name: 'ElInputNumber',
          props: ['modelValue'],
          emits: ['update:modelValue'],
          template:
            '<input class="el-input-number-stub" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />',
        },
      },
    },
  })
  await flushPromises()
  await nextTick()
  return w
}

beforeEach(() => {
  vi.clearAllMocks()
  mockGetMapStatus.mockResolvedValue({ success: true, data: coverageData })
  mockDownloadTiles.mockResolvedValue({ success: true, data: { region: DEFAULT_REGION } })
  mockClearTiles.mockResolvedValue({ success: true, message: CLEAR_MESSAGE })
  ElMessageBox.confirm.mockResolvedValue('confirm')
})

describe('MapTileManager.vue', () => {
  it('渲染并加载瓦片状态', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    expect(mockGetMapStatus).toHaveBeenCalled()
    expect(vm.coverage.total_tiles).toBe(1000)
    expect(vm.zoomLevelData).toEqual([
      { level: 4, count: 100 },
      { level: 8, count: 300 },
      { level: 12, count: 600 },
    ])
  })

  it('加载状态失败 → 错误提示', async () => {
    mockGetMapStatus.mockRejectedValue(new Error('status failed'))
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('status failed')
  })

  it('加载状态失败无 message → 默认文案', async () => {
    mockGetMapStatus.mockRejectedValue({})
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('加载状态失败')
  })

  it('加载状态 success=false → 不更新', async () => {
    mockGetMapStatus.mockResolvedValue({ success: false })
    const w = await mountComp()
    expect((w.vm as any).coverage.total_tiles).toBe(0)
  })
  // 注：`coverage.value = response.data || {}` 的 falsy 分支不可达——
  // 后端始终返回包含 total_tiles/zoom_levels 的对象；data 为 null/undefined
  // 时模板 Object.keys(zoom_levels) 会抛错，属防御性代码（v8 分支计数归 0）。

  it('handleDownload：确认 → 下载成功', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleDownload()
    expect(ElMessageBox.confirm).toHaveBeenCalledWith(
      '下载瓦片可能需要较长时间,确定要继续吗?',
      '确认下载',
      expect.objectContaining({ type: 'warning' })
    )
    expect(mockDownloadTiles).toHaveBeenCalledWith(vm.downloadForm)
    expect(ElMessage.success).toHaveBeenCalledWith(`下载完成! 区域 ${DEFAULT_REGION}`)
    expect(vm.downloading).toBe(false)
  })

  it('handleDownload：成功但 data 无 region → 默认区域文案', async () => {
    mockDownloadTiles.mockResolvedValue({ success: true })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleDownload()
    expect(ElMessage.success).toHaveBeenCalledWith('下载完成! 区域 已记录')
    expect(vm.downloading).toBe(false)
  })

  it('handleDownload：success=false → 不提示成功', async () => {
    mockDownloadTiles.mockResolvedValue({ success: false })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleDownload()
    expect(ElMessage.success).not.toHaveBeenCalled()
    expect(vm.downloading).toBe(false)
  })

  it('handleDownload：用户取消 → 无操作', async () => {
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleDownload()
    expect(mockDownloadTiles).not.toHaveBeenCalled()
    expect(vm.downloading).toBe(false)
  })

  it('handleDownload：失败 → 错误提示', async () => {
    mockDownloadTiles.mockRejectedValue(new Error('download failed'))
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleDownload()
    expect(ElMessage.error).toHaveBeenCalledWith('download failed')
  })

  it('handleDownload：失败无 message → 默认文案', async () => {
    mockDownloadTiles.mockRejectedValue({})
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleDownload()
    expect(ElMessage.error).toHaveBeenCalledWith('下载失败')
  })

  it('handleClearLevel：确认 → 清理成功', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleClearLevel(8)
    expect(ElMessageBox.confirm).toHaveBeenCalledWith(
      '系统当前为整体瓦片缓存清理（不区分缩放级别）。确定要继续吗?',
      '确认清理',
      expect.objectContaining({ type: 'warning' })
    )
    expect(mockClearTiles).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith(CLEAR_MESSAGE)
  })

  it('handleClearLevel：成功但无 message → 默认清理文案', async () => {
    mockClearTiles.mockResolvedValue({ success: true })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleClearLevel(8)
    expect(ElMessage.success).toHaveBeenCalledWith(CLEAR_MESSAGE)
  })

  it('handleClearLevel：success=false → 不提示成功', async () => {
    mockClearTiles.mockResolvedValue({ success: false })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleClearLevel(8)
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('handleClearLevel：用户取消 → 无操作', async () => {
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleClearLevel(8)
    expect(mockClearTiles).not.toHaveBeenCalled()
  })

  it('handleClearLevel：失败 → 错误提示', async () => {
    mockClearTiles.mockRejectedValue(new Error('clear failed'))
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleClearLevel(8)
    expect(ElMessage.error).toHaveBeenCalledWith('clear failed')
  })

  it('handleClearLevel：失败无 message → 默认文案', async () => {
    mockClearTiles.mockRejectedValue({})
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleClearLevel(8)
    expect(ElMessage.error).toHaveBeenCalledWith('清理失败')
  })

  it('handleClearAll：确认 → 清理成功', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleClearAll()
    expect(ElMessageBox.confirm).toHaveBeenCalledWith(
      '确定要清理所有瓦片吗?',
      '确认清理',
      expect.objectContaining({ type: 'warning' })
    )
    expect(mockClearTiles).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith(CLEAR_MESSAGE)
  })

  it('handleClearAll：成功但无 message → 默认清理文案', async () => {
    mockClearTiles.mockResolvedValue({ success: true })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleClearAll()
    expect(ElMessage.success).toHaveBeenCalledWith(CLEAR_MESSAGE)
  })

  it('handleClearAll：success=false → 不提示成功', async () => {
    mockClearTiles.mockResolvedValue({ success: false })
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleClearAll()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('handleClearAll：用户取消 → 无操作', async () => {
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleClearAll()
    expect(mockClearTiles).not.toHaveBeenCalled()
  })

  it('handleClearAll：失败 → 错误提示', async () => {
    mockClearTiles.mockRejectedValue(new Error('clear all failed'))
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleClearAll()
    expect(ElMessage.error).toHaveBeenCalledWith('clear all failed')
  })

  it('handleClearAll：失败无 message → 默认文案', async () => {
    mockClearTiles.mockRejectedValue({})
    const w = await mountComp()
    const vm = w.vm as any
    await vm.handleClearAll()
    expect(ElMessage.error).toHaveBeenCalledWith('清理失败')
  })

  it('usePresetRegion：贵州省 / 毕节市', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    vm.usePresetRegion('guizhou')
    expect(vm.downloadForm.min_lat).toBe(24.5)
    expect(vm.downloadForm.max_zoom).toBe(8)
    vm.usePresetRegion('bijie')
    expect(vm.downloadForm.min_lat).toBe(26.5)
    expect(vm.downloadForm.max_zoom).toBe(12)
    vm.usePresetRegion('unknown')
    expect(vm.downloadForm.min_lat).toBe(26.5)
  })

  it('空缩放级别：不渲染级别表格', async () => {
    mockGetMapStatus.mockResolvedValue({ success: true, data: { total_tiles: 0, total_size_mb: 0, zoom_levels: {} } })
    const w = await mountComp()
    expect(w.text()).not.toContain('各级别瓦片数量')
    expect((w.vm as any).zoomLevelData).toEqual([])
  })

  it('下载表单输入（经纬度/缩放）', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const inputs = w.findAll('.el-input-number-stub')
    expect(inputs.length).toBeGreaterThanOrEqual(6)
    await inputs[0].setValue(25)
    expect(vm.downloadForm.min_lat).toBe(25)
    await inputs[1].setValue(28)
    expect(vm.downloadForm.max_lat).toBe(28)
    await inputs[2].setValue(104)
    expect(vm.downloadForm.min_lon).toBe(104)
    await inputs[3].setValue(108)
    expect(vm.downloadForm.max_lon).toBe(108)
    await inputs[4].setValue(3)
    expect(vm.downloadForm.min_zoom).toBe(3)
    await inputs[5].setValue(13)
    expect(vm.downloadForm.max_zoom).toBe(13)
  })

  it('模板按钮：刷新状态 / 清理所有瓦片', async () => {
    const w = await mountComp()
    const refreshBtn = w
      .findAll('button')
      .find((b) => b.text().includes('刷新状态'))
    await refreshBtn!.trigger('click')
    expect(mockGetMapStatus).toHaveBeenCalled()
    const clearBtn = w
      .findAll('button')
      .find((b) => b.text().includes('清理所有瓦片'))
    await clearBtn!.trigger('click')
    expect(mockClearTiles).toHaveBeenCalled()
  })

  it('模板按钮：使用贵州省/毕节市预设', async () => {
    const w = await mountComp()
    const vm = w.vm as any
    const guizhouBtn = w
      .findAll('button')
      .find((b) => b.text().includes('使用贵州省预设'))
    await guizhouBtn!.trigger('click')
    expect(vm.downloadForm.max_zoom).toBe(8)
    const bijieBtn = w
      .findAll('button')
      .find((b) => b.text().includes('使用毕节市预设'))
    await bijieBtn!.trigger('click')
    expect(vm.downloadForm.min_zoom).toBe(9)
  })

  it('表格行清理按钮 → handleClearLevel', async () => {
    const w = await mountComp()
    const rowBtns = w.findAll('button').filter((b) => b.text().trim() === '清理')
    expect(rowBtns.length).toBeGreaterThan(0)
    await rowBtns[0].trigger('click')
    expect(mockClearTiles).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith(CLEAR_MESSAGE)
  })
})
