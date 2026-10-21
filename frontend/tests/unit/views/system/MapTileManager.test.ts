/**
 * views/system/MapTileManager.vue 单测（覆盖查看 + 导入瓦片包）
 *
 * 后端契约（F 区）：
 * - GET  /map/tile-info        → { available, tileCount, zoomLevels, totalBytes, dir, manifest }
 * - POST /map/tiles/import     → multipart .zip（管理员），响应含 message/tileCount
 * - DELETE /offline-map/clear  → { success, message }（整体清理，不支持按级别）
 *
 * 旧「下载瓦片（需要网络连接）」已下线：本页不再调用 POST /offline-map/download。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'

enableAutoUnmount(afterEach)

const {
  ElMessage,
  ElMessageBox,
  mockGetTileInfo,
  mockImportTiles,
  mockClearTiles,
  mockClearFiles,
} = vi.hoisted(() => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  ElMessageBox: { confirm: vi.fn() },
  mockGetTileInfo: vi.fn(),
  mockImportTiles: vi.fn(),
  mockClearTiles: vi.fn(),
  mockClearFiles: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox,
  ElNotification: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('@/api/map', () => ({
  getTileInfo: mockGetTileInfo,
}))

vi.mock('@/api/offlineMap', () => ({
  importTiles: mockImportTiles,
  clearTiles: mockClearTiles,
}))

import MapTileManager from '@/views/system/MapTileManager.vue'

const TILE_INFO = {
  available: true,
  tileCount: 1200,
  zoomLevels: [4, 8, 12],
  totalBytes: 157286400, // 150 MB
  dir: '/app/data/map_tiles',
  manifest: { provider: 'osm', generatedAt: '2026-10-01 10:00' },
}

const stubClearFiles = mockClearFiles

const stubs = {
  'el-card': {
    name: 'ElCard',
    template: '<div class="el-card-stub"><slot /><slot name="header" /></div>',
  },
  'el-descriptions': { name: 'ElDescriptions', template: '<dl><slot /></dl>' },
  'el-descriptions-item': {
    name: 'ElDescriptionsItem',
    props: ['label'],
    template: '<div class="el-desc-item-stub"><slot /></div>',
  },
  'el-alert': {
    name: 'ElAlert',
    props: ['title', 'type'],
    template: '<div class="el-alert-stub">{{ title }}</div>',
  },
  'el-tag': {
    name: 'ElTag',
    props: ['type'],
    template: '<span class="el-tag-stub"><slot /></span>',
  },
  'el-button': {
    name: 'ElButton',
    template: '<button class="el-button-stub"><slot /></button>',
  },
  'el-upload': {
    name: 'ElUpload',
    props: ['accept', 'autoUpload', 'limit', 'onChange', 'onRemove', 'onExceed'],
    methods: { clearFiles: stubClearFiles },
    template: '<div class="el-upload-stub"><slot /><slot name="tip" /></div>',
  },
}

async function mountComp() {
  const w = mount(MapTileManager, {
    global: { renderStubDefaultSlot: true, stubs },
  })
  await flushPromises()
  await nextTick()
  return w
}

function uploadStub(wrapper: ReturnType<typeof mount>) {
  return wrapper.findComponent({ name: 'ElUpload' })
}

function findByText(wrapper: ReturnType<typeof mount>, text: string) {
  return wrapper.findAll('button').find((b) => b.text().includes(text))
}

beforeEach(() => {
  vi.clearAllMocks()
  mockGetTileInfo.mockResolvedValue({ success: true, data: TILE_INFO })
  mockImportTiles.mockResolvedValue({ success: true, message: '瓦片包已导入 1200 张', tileCount: 1200 })
  mockClearTiles.mockResolvedValue({ success: true, message: '瓦片缓存已清理' })
  ElMessageBox.confirm.mockResolvedValue('confirm')
})

describe('MapTileManager.vue — 覆盖情况', () => {
  it('挂载即读取 tile-info 并如实展示覆盖情况', async () => {
    const w = await mountComp()
    const text = w.text()

    expect(mockGetTileInfo).toHaveBeenCalledTimes(1)
    expect(text).toContain('已预置')
    expect(text).toContain('1200')
    expect(text).toContain('150 MB')
    expect(text).toContain('4 – 12 级')
    expect(text).toContain('/app/data/map_tiles')
    expect(text).toContain('2026-10-01 10:00')
    // 已预置时不出现"未预置"说明
    expect(text).not.toContain('尚未预置离线瓦片')
    // 3 个缩放级别标签
    expect(w.findAll('.el-tag-stub').length).toBeGreaterThanOrEqual(4)
  })

  it('页面顶部使用如实文案：默认矢量地图 + 运维导入瓦片包', async () => {
    const w = await mountComp()
    expect(w.text()).toContain(
      '地图默认使用内置矢量地图；如需栅格瓦片底图，请由运维生成瓦片包后在此导入。'
    )
  })

  it('tile-info 不可用 → 未预置 + 中文原因提示', async () => {
    mockGetTileInfo.mockResolvedValue({
      available: false,
      tileCount: 0,
      zoomLevels: [],
      dir: '',
      manifest: null,
    })
    const w = await mountComp()
    expect(w.text()).toContain('未预置')
    expect(w.text()).toContain('尚未预置离线瓦片')
    // 无缩放级别 → 不渲染级别标签区
    expect(w.text()).not.toContain('已预置的缩放级别')
  })

  it('available=true 但 zoomLevels 为空 → 提示缺少缩放级别信息', async () => {
    mockGetTileInfo.mockResolvedValue({ available: true, tileCount: 5, zoomLevels: [] })
    const w = await mountComp()
    expect(w.text()).toContain('缺少缩放级别信息')
    expect(w.text()).not.toContain('已预置的缩放级别')
  })

  it('manifest.provider=amap → 展示 GCJ-02 偏移提示', async () => {
    mockGetTileInfo.mockResolvedValue({
      ...TILE_INFO,
      manifest: { provider: 'amap', generatedAt: '2026-10-01' },
    })
    const w = await mountComp()
    expect(w.text()).toContain('底图为 GCJ-02 坐标系，标记点可能存在偏移')
  })

  it('manifest 缺失 → 生成时间展示占位符', async () => {
    mockGetTileInfo.mockResolvedValue({ ...TILE_INFO, manifest: null })
    const w = await mountComp()
    expect(w.text()).toContain('—')
    expect(w.text()).not.toContain('GCJ-02')
  })

  it('读取失败 → 错误提示（中文原因优先）且仍展示未预置说明', async () => {
    mockGetTileInfo.mockRejectedValue(new Error('tile-info failed'))
    const w = await mountComp()
    expect(ElMessage.error).toHaveBeenCalledWith('tile-info failed')
    expect(w.text()).toContain('尚未预置离线瓦片')
    expect((w.vm as any).loading).toBe(false)
  })

  it('刷新状态按钮 → 重新读取', async () => {
    const w = await mountComp()
    await findByText(w, '刷新状态')!.trigger('click')
    await flushPromises()
    expect(mockGetTileInfo).toHaveBeenCalledTimes(2)
  })
})

describe('MapTileManager.vue — 导入瓦片包', () => {
  it('未选择文件就导入 → 警告且不调用接口', async () => {
    const w = await mountComp()
    await (w.vm as any).handleImportTiles()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择 .zip 瓦片包')
    expect(mockImportTiles).not.toHaveBeenCalled()
  })

  it('选择合法 .zip → 导入成功并刷新状态', async () => {
    const w = await mountComp()
    const file = new File(['tiles'], 'guizhou.zip', { type: 'application/zip' })
    uploadStub(w).props('onChange')({ name: 'guizhou.zip', raw: file })
    await nextTick()

    await (w.vm as any).handleImportTiles()
    await flushPromises()

    expect(mockImportTiles).toHaveBeenCalledWith(file)
    expect(ElMessage.success).toHaveBeenCalledWith('瓦片包已导入 1200 张')
    expect(mockClearFiles).toHaveBeenCalled()
    expect(mockGetTileInfo).toHaveBeenCalledTimes(2) // 挂载 + 导入后刷新
    expect((w.vm as any).importing).toBe(false)
  })

  it('导入响应 success=false → 展示后端中文失败原因且不刷新', async () => {
    mockImportTiles.mockResolvedValue({ success: false, message: '压缩包结构不合法' })
    const w = await mountComp()
    uploadStub(w).props('onChange')({
      name: 'tiles.zip',
      raw: new File(['x'], 'tiles.zip'),
    })
    await (w.vm as any).handleImportTiles()

    expect(ElMessage.error).toHaveBeenCalledWith('压缩包结构不合法')
    expect(mockGetTileInfo).toHaveBeenCalledTimes(1)
  })

  it('导入抛错 → 使用拦截器挂载的 userMessage（中文原因）', async () => {
    const error = Object.assign(new Error('Request failed'), {
      userMessage: '瓦片包解压失败：缺少 z/x/y 目录',
    })
    mockImportTiles.mockRejectedValue(error)
    const w = await mountComp()
    uploadStub(w).props('onChange')({ name: 'tiles.zip', raw: new File(['x'], 'tiles.zip') })
    await (w.vm as any).handleImportTiles()

    expect(ElMessage.error).toHaveBeenCalledWith('瓦片包解压失败：缺少 z/x/y 目录')
    expect((w.vm as any).importing).toBe(false)
  })

  it('非 .zip 文件 → 前端前置拦截并清空选择', async () => {
    const w = await mountComp()
    uploadStub(w).props('onChange')({
      name: 'tiles.rar',
      raw: new File(['x'], 'tiles.rar'),
    })
    await nextTick()

    expect(ElMessage.error).toHaveBeenCalledWith('仅支持 .zip 格式的瓦片包')
    expect((w.vm as any).pendingFile).toBeNull()
    expect(mockClearFiles).toHaveBeenCalled()
  })

  it('选择文件但没有 raw 内容 → 视为未选择并提示', async () => {
    const w = await mountComp()
    uploadStub(w).props('onChange')({ name: 'tiles.zip' })
    await nextTick()

    expect(ElMessage.error).toHaveBeenCalledWith('未选择瓦片包文件')
    expect((w.vm as any).pendingFile).toBeNull()
  })

  it('移除已选文件 → 清空待上传文件', async () => {
    const w = await mountComp()
    uploadStub(w).props('onChange')({ name: 'tiles.zip', raw: new File(['x'], 'tiles.zip') })
    uploadStub(w).props('onRemove')()
    await nextTick()
    expect((w.vm as any).pendingFile).toBeNull()
    await (w.vm as any).handleImportTiles()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择 .zip 瓦片包')
  })

  it('超过数量上限 → 提示先移除已选文件', async () => {
    const w = await mountComp()
    uploadStub(w).props('onExceed')()
    expect(ElMessage.warning).toHaveBeenCalledWith('一次只能导入一个瓦片包，请先移除已选择的文件')
  })

  it('模板「导入瓦片包」按钮可触发导入流程', async () => {
    const w = await mountComp()
    uploadStub(w).props('onChange')({ name: 'tiles.zip', raw: new File(['x'], 'tiles.zip') })
    await findByText(w, '导入瓦片包')!.trigger('click')
    await flushPromises()
    expect(mockImportTiles).toHaveBeenCalled()
  })
})

describe('MapTileManager.vue — 清空瓦片缓存', () => {
  it('确认后清空并刷新，展示后端 message', async () => {
    const w = await mountComp()
    await (w.vm as any).handleClearTiles()
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(mockClearTiles).toHaveBeenCalledTimes(1)
    expect(ElMessage.success).toHaveBeenCalledWith('瓦片缓存已清理')
    expect(mockGetTileInfo).toHaveBeenCalledTimes(2)
  })

  it('后端未返回 message → 默认成功文案', async () => {
    mockClearTiles.mockResolvedValue({ success: true })
    const w = await mountComp()
    await (w.vm as any).handleClearTiles()
    expect(ElMessage.success).toHaveBeenCalledWith('瓦片缓存已清空')
  })

  it('用户取消 → 不调用清理接口', async () => {
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const w = await mountComp()
    await (w.vm as any).handleClearTiles()
    expect(mockClearTiles).not.toHaveBeenCalled()
  })

  it('清理失败 → 错误提示', async () => {
    mockClearTiles.mockRejectedValue(new Error('clear failed'))
    const w = await mountComp()
    await (w.vm as any).handleClearTiles()
    expect(ElMessage.error).toHaveBeenCalledWith('clear failed')
  })

  it('模板「清空瓦片缓存」按钮可触发清理流程', async () => {
    const w = await mountComp()
    await findByText(w, '清空瓦片缓存')!.trigger('click')
    await flushPromises()
    expect(mockClearTiles).toHaveBeenCalled()
  })

  it('页面不再提供「下载瓦片」入口（假下载已下线）', async () => {
    const w = await mountComp()
    expect(w.text()).not.toContain('下载瓦片')
    expect(w.text()).not.toContain('需要网络连接')
  })
})
