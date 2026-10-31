/**
 * components/map/RasterTileLayer.vue 单测
 *
 * Leaflet 在 jsdom 下无法真实渲染（需要布局尺寸 / 真实 DOM 测量），因此把 leaflet 模块
 * 整体替换为可断言的桩：只验证组件行为契约（离线 URL、覆盖范围 bounds/fitBounds、
 * 边缘 404 不回退、全 404 才回退、标注点、GCJ-02、生命周期与清理）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'
import type { TileInfo } from '@/api/map'
import { PARTIAL_COVERAGE_HINT, TRANSPARENT_TILE_DATA_URI } from '@/utils/mapTiles'

enableAutoUnmount(afterEach)

const hoisted = vi.hoisted(() => {
  const state = {
    maps: [] as any[],
    tileLayers: [] as any[],
    groups: [] as any[],
    circles: [] as any[],
  }

  const addHandler = (handlers: Record<string, Function[]>, event: string, handler: Function) => {
    handlers[event] = handlers[event] || []
    handlers[event].push(handler)
  }

  const map = (el: any, opts: any) => {
    const handlers: Record<string, Function[]> = {}
    const instance: any = {
      el,
      opts,
      handlers,
      zoom: opts?.zoom ?? 7,
      size: { x: 800, y: 600 },
      remove: vi.fn(),
      setView: vi.fn(),
      fitBounds: vi.fn(),
      panTo: vi.fn(),
      invalidateSize: vi.fn(),
      on: vi.fn((event: string, handler: Function) => {
        addHandler(handlers, event, handler)
        return instance
      }),
      off: vi.fn(() => instance),
      getZoom: vi.fn(() => instance.zoom),
      getSize: vi.fn(() => instance.size),
      /** 简单线性投影，便于断言标签像素位置（经度×60、纬度反向往南） */
      latLngToContainerPoint: vi.fn((latlng: [number, number]) => ({
        x: Math.round((latlng[1] - 100) * 60),
        y: Math.round((30 - latlng[0]) * 60),
      })),
    }
    state.maps.push(instance)
    return instance
  }

  const tileLayer = (url: string, opts: any) => {
    const handlers: Record<string, Function[]> = {}
    const instance: any = {
      url,
      opts,
      // Leaflet 实例属性名为 options（与构造参数 opts 对应），供子类方法读取
      options: opts,
      handlers,
      on: vi.fn((event: string, handler: Function) => {
        addHandler(handlers, event, handler)
        return instance
      }),
      off: vi.fn(() => instance),
      addTo: vi.fn(() => instance),
      remove: vi.fn(() => instance),
    }
    state.tileLayers.push(instance)
    return instance
  }

  const layerGroup = () => {
    const instance: any = {
      addTo: vi.fn(() => instance),
      clearLayers: vi.fn(),
      remove: vi.fn(),
    }
    state.groups.push(instance)
    return instance
  }

  const circleMarker = (latlng: any, opts: any) => {
    const handlers: Record<string, Function[]> = {}
    const instance: any = {
      latlng,
      opts,
      handlers,
      bindTooltip: vi.fn(() => instance),
      on: vi.fn((event: string, handler: Function) => {
        addHandler(handlers, event, handler)
        return instance
      }),
      addTo: vi.fn(() => instance),
    }
    state.circles.push(instance)
    return instance
  }

  /** 模拟 L.TileLayer.extend：生成可 new 的子类工厂，并把子类方法混入实例 */
  const TileLayer = {
    extend(props: Record<string, Function>) {
      return function (url: string, opts: any) {
        return Object.assign(tileLayer(url, opts), props)
      }
    },
  }

  /** 比例尺控件（图注的一部分） */
  const scaleControl = vi.fn(() => ({ addTo: vi.fn() }))

  return { state, map, tileLayer, TileLayer, layerGroup, circleMarker, scaleControl }
})

vi.mock('leaflet', () => ({
  map: hoisted.map,
  tileLayer: hoisted.tileLayer,
  TileLayer: hoisted.TileLayer,
  layerGroup: hoisted.layerGroup,
  circleMarker: hoisted.circleMarker,
  control: { scale: hoisted.scaleControl },
}))

import RasterTileLayer from '@/components/map/RasterTileLayer.vue'

const { state } = hoisted

/** 贵州兜底 bbox 对应的 Leaflet bounds */
const GUIZHOU_BOUNDS = [
  [24.6, 103.6],
  [29.2, 109.6],
]

/** 贵阳市单市州 bbox（用于验证视图范围仍包含全省） */
const GUIYANG_BBOX = [106.1, 26.1, 107.3, 27.4]

function makeInfo(overrides: Partial<TileInfo> = {}): TileInfo {
  return {
    available: true,
    tileCount: 12,
    zoomLevels: [4, 5, 8],
    totalBytes: 1024,
    dir: '/app/data/map_tiles',
    manifest: null,
    bbox: null,
    source: 'local',
    reason: null,
    ...overrides,
  }
}

const markers = [
  { id: 1, name: '甲村', lng: 106.71, lat: 26.65, type: 'village' },
  { id: 2, name: '乙小学', lng: 107.1, lat: 26.9, type: 'school' },
  { id: 3, name: '丙项目', lng: 107.5, lat: 27.2, type: 'project' },
]

async function mountLayer(props: Record<string, unknown> = {}) {
  const wrapper = mount(RasterTileLayer, {
    props: { tileInfo: makeInfo(), markers, watchdogMs: 20, ...props } as any,
  })
  await flushPromises()
  await nextTick()
  return wrapper
}

/** 触发 mock 瓦片层事件 n 次 */
function fire(layer: any, event: 'tileerror' | 'tileload', times: number) {
  for (let i = 0; i < times; i += 1) layer.handlers[event][0]()
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

beforeEach(() => {
  state.maps.length = 0
  state.tileLayers.length = 0
  state.groups.length = 0
  state.circles.length = 0
})

describe('RasterTileLayer.vue — 建图与覆盖范围', () => {
  it('创建地图与本地瓦片层：离线 URL、覆盖 bounds、透明错误瓦片、初始 fitBounds', async () => {
    const wrapper = await mountLayer()

    expect(state.maps).toHaveLength(1)
    expect(state.maps[0].el).toBe(wrapper.find('.map-raster-canvas').element)
    expect(state.maps[0].opts).toMatchObject({
      zoom: 7,
      minZoom: 4,
      // 原生最大 8 → 允许 2 档超采样，缩放交互不能被数据层级锁死
      maxZoom: 10,
      maxBoundsViscosity: 1.0,
      worldCopyJump: false,
      zoomControl: true,
      scrollWheelZoom: true,
      doubleClickZoom: true,
      touchZoom: true,
      boxZoom: true,
      keyboard: true,
    })
    // 未指定 center → 停在覆盖范围中心
    expect(state.maps[0].opts.center[0]).toBeCloseTo(26.9)
    expect(state.maps[0].opts.center[1]).toBeCloseTo(106.6)
    // 视野限制在覆盖范围外扩 0.05°
    expect(state.maps[0].opts.maxBounds[0][0]).toBeCloseTo(24.55)
    expect(state.maps[0].opts.maxBounds[0][1]).toBeCloseTo(103.55)
    expect(state.maps[0].opts.maxBounds[1][0]).toBeCloseTo(29.25)
    expect(state.maps[0].opts.maxBounds[1][1]).toBeCloseTo(109.65)

    const layer = state.tileLayers[0]
    expect(layer.url).toBe('/api/v1/map/tiles/{z}/{x}/{y}.png')
    expect(layer.opts).toMatchObject({
      minZoom: 4,
      maxZoom: 10,
      minNativeZoom: 4,
      maxNativeZoom: 8,
      noWrap: true,
      bounds: GUIZHOU_BOUNDS,
      errorTileUrl: TRANSPARENT_TILE_DATA_URI,
    })
    expect(layer.addTo).toHaveBeenCalledWith(state.maps[0])

    // 初始视野贴合覆盖范围（不是固定 zoom 7：1080p 下视野约 21° > 贵州 6°）
    expect(state.maps[0].fitBounds).toHaveBeenCalledWith(GUIZHOU_BOUNDS, {
      padding: [16, 16],
      maxZoom: 9,
    })
    expect(state.maps[0].invalidateSize).toHaveBeenCalled()
    // 未指定 center → 不再 panTo，避免把视野拉出 bbox
    expect(state.maps[0].panTo).not.toHaveBeenCalled()

    expect(wrapper.find('.map-raster-notice').exists()).toBe(false)
    expect(wrapper.find('.map-raster-partial').exists()).toBe(false)
    expect(wrapper.find('.map-raster-gcj02').exists()).toBe(false)
  })

  it('单层 z14 瓦片包：地图仍可放大/缩小（回归：minZoom=maxZoom=14 锁死交互）', async () => {
    const wrapper = await mountLayer({ tileInfo: makeInfo({ zoomLevels: [14] }) })

    const map = state.maps[0]
    const layer = state.tileLayers[0]
    expect(map.opts.minZoom).toBe(12)
    expect(map.opts.maxZoom).toBe(16)
    expect(map.opts.maxZoom).toBeGreaterThan(map.opts.minZoom)
    expect(layer.opts).toMatchObject({
      minZoom: 12,
      maxZoom: 16,
      minNativeZoom: 14,
      maxNativeZoom: 14,
    })
    // 原生层级 >= 显示下限，Leaflet 才能用 z14 瓦片渲染 z12~16 的显示层级
    expect(layer.opts.minNativeZoom).toBeGreaterThanOrEqual(map.opts.minZoom)

    // 程序化缩放路径同样可用（父组件可通过 :zoom 控制）
    await wrapper.setProps({ zoom: 15 })
    expect(map.setView).toHaveBeenLastCalledWith([expect.closeTo(26.9), expect.closeTo(106.6)], 15)
  })

  it('合并 z5-11 全省包与 z14 市州包（层级有空洞）：z12/z13 取最近已有瓦片', async () => {
    await mountLayer({ tileInfo: makeInfo({ zoomLevels: [5, 11, 14] }) })
    const layer = state.tileLayers[0]

    expect(layer.opts.nativeZooms).toEqual([5, 11, 14])
    // Leaflet 默认会按连续区间请求不存在的 z12/z13；自定义层必须回落到最近层级
    expect(layer._clampZoom(12)).toBe(11) // 距 11/14 同为 1 → 取较低级，请求量更小
    expect(layer._clampZoom(13)).toBe(14)
    expect(layer._clampZoom(9)).toBe(11)
    expect(layer._clampZoom(16)).toBe(14)
  })

  it('后端下发 bbox → fitBounds / tileLayer.bounds 都用后端覆盖范围', async () => {
    await mountLayer({ tileInfo: makeInfo({ bbox: [100, 20, 110, 30] }) })

    const bounds = [
      [20, 100],
      [30, 110],
    ]
    expect(state.tileLayers[0].opts.bounds).toEqual(bounds)
    expect(state.maps[0].fitBounds).toHaveBeenCalledWith(bounds, {
      padding: [16, 16],
      maxZoom: 9,
    })
    expect(state.maps[0].opts.center[0]).toBeCloseTo(25)
    expect(state.maps[0].opts.center[1]).toBeCloseTo(105)
  })

  it('指定 center 且在 bbox 内 → fitBounds 后 panTo 到中心', async () => {
    await mountLayer({ center: { lng: 106.71, lat: 26.65 } })

    expect(state.maps[0].opts.center).toEqual([26.65, 106.71])
    expect(state.maps[0].panTo).toHaveBeenCalledWith([26.65, 106.71])
  })

  it('指定 center 但在 bbox 外 → 不 panTo（视野仍被 maxBounds 约束）', async () => {
    await mountLayer({ center: { lng: 120, lat: 35 } })

    expect(state.maps[0].opts.center).toEqual([35, 120])
    expect(state.maps[0].panTo).not.toHaveBeenCalled()
    expect(state.maps[0].fitBounds).toHaveBeenCalledWith(GUIZHOU_BOUNDS, {
      padding: [16, 16],
      maxZoom: 9,
    })
  })
})

describe('RasterTileLayer.vue — 边缘 404 与全 404 的回退语义', () => {
  it('边缘少量 404 + 有成功瓦片 → 不回退，仅非阻塞提示', async () => {
    const wrapper = await mountLayer()
    const layer = state.tileLayers[0]

    fire(layer, 'tileload', 6)
    fire(layer, 'tileerror', 3)
    await nextTick()

    expect(wrapper.emitted('tile-error')).toBeUndefined()
    const partial = wrapper.find('.map-raster-partial')
    expect(partial.exists()).toBe(true)
    expect(partial.text()).toContain(PARTIAL_COVERAGE_HINT)
    // 非阻塞：不出现 blocking notice
    expect(wrapper.find('.map-raster-notice').exists()).toBe(false)
  })

  it('失败很多但已有一张成功（视口局部越界）→ 也不整体回退', async () => {
    const wrapper = await mountLayer()
    const layer = state.tileLayers[0]

    fire(layer, 'tileload', 1)
    fire(layer, 'tileerror', 20)
    await nextTick()

    expect(wrapper.emitted('tile-error')).toBeUndefined()
    expect(wrapper.find('.map-raster-partial').text()).toContain('超出预置瓦片范围')
  })

  it('全部 404（≥8 张且一张未成功）→ 回退一次 + 中文失败说明 + 手动回退按钮', async () => {
    const wrapper = await mountLayer()
    const layer = state.tileLayers[0]

    fire(layer, 'tileerror', 8)
    await nextTick()

    expect(wrapper.emitted('tile-error')).toHaveLength(1)
    const notice = wrapper.find('.map-raster-notice')
    expect(notice.exists()).toBe(true)
    expect(notice.text()).toContain('瓦片加载失败')

    // 继续 404 不重复通知
    fire(layer, 'tileerror', 10)
    await nextTick()
    expect(wrapper.emitted('tile-error')).toHaveLength(1)

    await wrapper.find('.map-raster-fallback').trigger('click')
    expect(wrapper.emitted('fallback')).toHaveLength(1)
  })

  it('少于阈值（7 张）且无成功 → 既不回退也不显示提示（等待看门狗/后续加载）', async () => {
    const wrapper = await mountLayer()
    const layer = state.tileLayers[0]

    fire(layer, 'tileerror', 7)
    await nextTick()

    expect(wrapper.emitted('tile-error')).toBeUndefined()
    expect(wrapper.find('.map-raster-notice').exists()).toBe(false)
    expect(wrapper.find('.map-raster-partial').exists()).toBe(false)
  })

  it('看门狗：超时后仍无成功瓦片且失败≥8 → 只回退一次', async () => {
    const wrapper = await mountLayer({ watchdogMs: 20 })
    const layer = state.tileLayers[0]

    // 8 张失败已触发立即回退；看门狗超时后不得再次 emit
    fire(layer, 'tileerror', 8)
    await wait(30)
    await nextTick()

    expect(wrapper.emitted('tile-error')).toHaveLength(1)
  })

  it('看门狗：窗口期内有成功瓦片 → 超时也不回退', async () => {
    const wrapper = await mountLayer({ watchdogMs: 20 })
    const layer = state.tileLayers[0]

    fire(layer, 'tileload', 1)
    fire(layer, 'tileerror', 8)
    await wait(30)
    await nextTick()

    expect(wrapper.emitted('tile-error')).toBeUndefined()
  })
})

describe('RasterTileLayer.vue — 标注点', () => {
  it('按类型着色并绑定 tooltip，点击 emit marker-click', async () => {
    const wrapper = await mountLayer()

    expect(state.circles).toHaveLength(3)
    expect(state.circles[0].latlng).toEqual([26.65, 106.71])
    expect(state.circles[0].opts.fillColor).toBe('#2d6a4f') // village → 主色
    expect(state.circles[1].opts.fillColor).toBe('#67c23a') // school → success
    expect(state.circles[2].opts.fillColor).toBe('#e6a23c') // project → warning
    expect(state.circles[0].bindTooltip).toHaveBeenCalledWith('甲村')
    expect(state.circles[0].addTo).toHaveBeenCalledWith(state.groups[0])

    state.circles[0].handlers.click[0]()
    const emitted = wrapper.emitted('marker-click')
    expect(emitted).toHaveLength(1)
    expect(emitted![0][0]).toMatchObject({ id: 1, name: '甲村' })
  })

  it('markers 变化 → 清空并重绘', async () => {
    const wrapper = await mountLayer()
    const group = state.groups[0]
    expect(group.clearLayers).toHaveBeenCalledTimes(1)

    await wrapper.setProps({ markers: [markers[0]] })
    await nextTick()
    expect(group.clearLayers).toHaveBeenCalledTimes(2)
    expect(state.circles).toHaveLength(4)
  })
})

describe('RasterTileLayer.vue — GCJ-02 底图', () => {
  it('manifest.provider=amap → 显示偏移提示且标注点做 GCJ-02 修正', async () => {
    const wrapper = await mountLayer({
      tileInfo: makeInfo({ manifest: { provider: 'amap' } }),
    })

    expect(wrapper.find('.map-raster-gcj02').text()).toContain('GCJ-02')
    expect(state.circles[0].latlng[0]).not.toBe(26.65)
    expect(state.circles[0].latlng[1]).not.toBe(106.71)
    expect(markers[0].lat).toBe(26.65) // 入参不被修改
  })

  it('GCJ-02 底图下 center 与标注点走同一转换（避免整体错位）', async () => {
    const wrapper = await mountLayer({
      tileInfo: makeInfo({ manifest: { provider: 'amap' } }),
      center: { lng: 106.71, lat: 26.65 },
    })

    expect(state.maps[0].opts.center).toEqual(state.circles[0].latlng)
    expect(state.maps[0].panTo).toHaveBeenCalledWith(state.circles[0].latlng)

    await wrapper.setProps({ center: { lng: 107.2, lat: 27.1 } })
    const view = state.maps[0].setView.mock.calls.at(-1)![0]
    expect(view[0]).not.toBe(27.1)
    expect(Math.abs(view[0] - 27.1)).toBeLessThan(0.02)
  })

  it('底图来源切换为 GCJ-02 → 重新渲染标注点', async () => {
    const wrapper = await mountLayer()
    expect(wrapper.find('.map-raster-gcj02').exists()).toBe(false)
    const clearCallsBefore = state.groups[0].clearLayers.mock.calls.length

    await wrapper.setProps({ tileInfo: makeInfo({ manifest: { provider: 'gaode' } }) })
    await nextTick()

    expect(wrapper.find('.map-raster-gcj02').exists()).toBe(true)
    expect(state.groups[0].clearLayers.mock.calls.length).toBe(clearCallsBefore + 1)
  })
})

describe('RasterTileLayer.vue — 不可用与生命周期', () => {
  it('tile-info 不可用 → 不建图，显示中文说明并可回退', async () => {
    const wrapper = await mountLayer({ tileInfo: null, markers: [] })

    expect(state.maps).toHaveLength(0)
    expect(state.tileLayers).toHaveLength(0)
    expect(wrapper.find('.map-raster-notice').text()).toContain('尚未预置离线瓦片')
    expect(wrapper.find('.map-raster-partial').exists()).toBe(false)

    await wrapper.find('.map-raster-fallback').trigger('click')
    expect(wrapper.emitted('fallback')).toHaveLength(1)
  })

  it('available=false / tileCount=0 / zoomLevels=[] → 提示具体原因且不建图', async () => {
    const cases: Array<[Partial<TileInfo>, string]> = [
      [{ available: false }, '尚未预置离线瓦片'],
      [{ tileCount: 0 }, '瓦片目录为空'],
      [{ zoomLevels: [] }, '缺少缩放级别信息'],
    ]
    for (const [override, expected] of cases) {
      state.maps.length = 0
      const wrapper = await mountLayer({ tileInfo: makeInfo(override) })
      expect(state.maps).toHaveLength(0)
      expect(wrapper.find('.map-raster-notice').text()).toContain(expected)
      wrapper.unmount()
    }
  })

  it('visible=false 不建图；切 true 建图；再切 false 销毁（含 tileload 解绑）', async () => {
    const wrapper = await mountLayer({ visible: false })
    expect(state.maps).toHaveLength(0)

    await wrapper.setProps({ visible: true })
    await nextTick()
    expect(state.maps).toHaveLength(1)
    expect(state.groups).toHaveLength(1)

    await wrapper.setProps({ visible: false })
    await nextTick()
    expect(state.maps[0].remove).toHaveBeenCalled()
    expect(state.tileLayers[0].remove).toHaveBeenCalled()
    expect(state.groups[0].remove).toHaveBeenCalled()
    expect(state.tileLayers[0].off).toHaveBeenCalledWith('tileerror', expect.any(Function))
    expect(state.tileLayers[0].off).toHaveBeenCalledWith('tileload', expect.any(Function))
  })

  it('地图已存在时 tileInfo 变更不重建地图', async () => {
    const wrapper = await mountLayer()
    await wrapper.setProps({ tileInfo: makeInfo({ zoomLevels: [6, 10], tileCount: 30 }) })
    await nextTick()
    expect(state.maps).toHaveLength(1)
    expect(state.tileLayers).toHaveLength(1)
  })

  it('center / zoom 变化 → 调用 setView（center 未指定时用覆盖范围中心）', async () => {
    const wrapper = await mountLayer()
    const map = state.maps[0]

    await wrapper.setProps({ zoom: 9 })
    expect(map.setView).toHaveBeenLastCalledWith([expect.closeTo(26.9), expect.closeTo(106.6)], 9)

    await wrapper.setProps({ center: { lng: 107.2, lat: 27.1 } })
    expect(map.setView).toHaveBeenLastCalledWith([27.1, 107.2], 9)
  })

  it('地图未创建时的 center / markers 变化安全忽略', async () => {
    const wrapper = await mountLayer({ visible: false, tileInfo: null, markers: [] })
    await wrapper.setProps({ center: { lng: 100, lat: 20 }, markers: [markers[0]] })
    await nextTick()
    expect(state.maps).toHaveLength(0)
  })

  it('卸载时清理地图与瓦片层；从未建图时清理也安全', async () => {
    const initialized = await mountLayer()
    initialized.unmount()
    expect(state.maps[0].remove).toHaveBeenCalled()
    expect(state.tileLayers[0].off).toHaveBeenCalled()

    state.maps.length = 0
    state.tileLayers.length = 0
    state.groups.length = 0
    const empty = await mountLayer({ tileInfo: null })
    expect(() => empty.unmount()).not.toThrow()
  })
})

/** 模拟地图缩放到指定级别并触发 zoomend */
function setZoom(mapInstance: any, zoom: number) {
  mapInstance.zoom = zoom
  ;(mapInstance.handlers.zoomend || []).forEach((fn: Function) => fn())
}

/** 模拟地图移动结束 */
function triggerMove(mapInstance: any) {
  ;(mapInstance.handlers.moveend || []).forEach((fn: Function) => fn())
}

describe('RasterTileLayer.vue — 常显标签（z12 村 / z13 校，方案 A）', () => {
  it('z12：村常显（白底小字、不拦截拖拽）、学校仍仅悬停', async () => {
    await mountLayer()
    const map = state.maps[0]
    setZoom(map, 12)
    await nextTick()

    expect(state.circles[0].bindTooltip).toHaveBeenLastCalledWith(
      '甲村',
      expect.objectContaining({
        permanent: true,
        interactive: false,
        direction: 'right',
        className: 'map-raster-label',
      })
    )
    // 学校阈值 13 → z12 仅悬停（无 options）
    expect(state.circles[1].bindTooltip).toHaveBeenLastCalledWith('乙小学')
    expect(state.circles[1].bindTooltip.mock.calls.at(-1)).toHaveLength(1)
    // 非村/校类型永不常显
    expect(state.circles[2].bindTooltip.mock.calls.at(-1)).toHaveLength(1)
  })

  it('z13：村与学校都常显，字号升到大档', async () => {
    await mountLayer()
    const map = state.maps[0]
    setZoom(map, 13)
    await nextTick()

    expect(state.circles[0].bindTooltip).toHaveBeenLastCalledWith(
      '甲村',
      expect.objectContaining({
        permanent: true,
        className: 'map-raster-label map-raster-label--lg',
      })
    )
    expect(state.circles[1].bindTooltip).toHaveBeenLastCalledWith(
      '乙小学',
      expect.objectContaining({
        permanent: true,
        className: 'map-raster-label map-raster-label--lg',
      })
    )
    expect(state.circles[2].bindTooltip.mock.calls.at(-1)).toHaveLength(1)
  })

  it('z11：全部退回仅悬停（无常显标签）', async () => {
    await mountLayer()
    const map = state.maps[0]
    setZoom(map, 11)
    await nextTick()

    for (const circle of state.circles) {
      const last = circle.bindTooltip.mock.calls.at(-1)
      expect(last).toHaveLength(1)
    }
  })

  it('缩放往返：z12 常显 → z11 退回悬停 → z12 再常显；同 zoom 重复 zoomend 不重复重绑', async () => {
    await mountLayer()
    const map = state.maps[0]
    const village = state.circles[0]

    setZoom(map, 12)
    await nextTick()
    expect(village.bindTooltip.mock.calls.filter(([, opts]) => opts?.permanent)).toHaveLength(1)

    setZoom(map, 11)
    await nextTick()
    expect(village.bindTooltip).toHaveBeenLastCalledWith('甲村')

    setZoom(map, 12)
    await nextTick()
    expect(village.bindTooltip.mock.calls.filter(([, opts]) => opts?.permanent)).toHaveLength(2)

    // 同 zoom 再触发 zoomend：模式未变 → 不重绑
    const callsBefore = village.bindTooltip.mock.calls.length
    setZoom(map, 12)
    await nextTick()
    expect(village.bindTooltip.mock.calls.length).toBe(callsBefore)
  })

  it('碰撞：同格两个村只常显离视野中心更近的那个', async () => {
    const crowded = [
      { id: 11, name: '远村', lng: 106.57, lat: 26.65, type: 'village' }, // x≈394
      { id: 12, name: '近村', lng: 106.68, lat: 26.65, type: 'village' }, // x≈401
    ]
    await mountLayer({ markers: crowded })
    const map = state.maps[0]
    setZoom(map, 12)
    await nextTick()

    // 两点同属 64×20 格 (6,10)，中心 (400,300)：近村胜出
    expect(state.circles[0].bindTooltip.mock.calls.at(-1)).toHaveLength(1)
    expect(state.circles[1].bindTooltip).toHaveBeenLastCalledWith(
      '近村',
      expect.objectContaining({ permanent: true })
    )
  })

  it('markers 变化（筛选村/校）后标签同步增删', async () => {
    const wrapper = await mountLayer()
    const map = state.maps[0]
    setZoom(map, 12)
    await nextTick()

    await wrapper.setProps({
      markers: [{ id: 21, name: '新小学', lng: 107.1, lat: 26.9, type: 'school' }],
    })
    await nextTick()

    const latest = state.circles.at(-1)
    // z12 学校不常显
    expect(latest.bindTooltip.mock.calls.at(-1)).toHaveLength(1)

    setZoom(map, 13)
    await nextTick()
    expect(latest.bindTooltip).toHaveBeenLastCalledWith(
      '新小学',
      expect.objectContaining({ permanent: true })
    )
  })

  it('moveend 后按新像素位置重选：移出视野的村退回悬停', async () => {
    await mountLayer({
      markers: [{ id: 31, name: '边缘村', lng: 100.1, lat: 26.65, type: 'village' }],
    })
    const map = state.maps[0]
    setZoom(map, 12)
    await nextTick()
    expect(state.circles[0].bindTooltip).toHaveBeenLastCalledWith(
      '边缘村',
      expect.objectContaining({ permanent: true })
    )

    map.latLngToContainerPoint.mockReturnValue({ x: -50, y: 200 })
    triggerMove(map)
    await nextTick()
    expect(state.circles[0].bindTooltip.mock.calls.at(-1)).toHaveLength(1)
  })

  it('空 markers / 卸载：不产生标签，且解绑 zoom/move 监听', async () => {
    const wrapper = await mountLayer({ markers: [] })
    const map = state.maps[0]
    setZoom(map, 13)
    await nextTick()
    expect(state.circles).toHaveLength(0)

    wrapper.unmount()
    expect(map.off).toHaveBeenCalledWith('zoomend', expect.any(Function))
    expect(map.off).toHaveBeenCalledWith('moveend', expect.any(Function))
  })

  it('无 id 的标注用 name 作 key（仍能常显）；卸载后迟到的 zoomend 事件安全忽略', async () => {
    const wrapper = await mountLayer({
      markers: [{ name: '无编号村', lng: 106.71, lat: 26.65, type: 'village' }],
    })
    const map = state.maps[0]
    setZoom(map, 12)
    await nextTick()
    expect(state.circles[0].bindTooltip).toHaveBeenLastCalledWith(
      '无编号村',
      expect.objectContaining({ permanent: true })
    )

    // 卸载后地图已销毁：残留事件回调不得抛错（refreshLabels 的 map 空值保护）
    const lateHandlers = [...(map.handlers.zoomend || [])]
    wrapper.unmount()
    expect(() => lateHandlers.forEach((fn) => fn())).not.toThrow()
  })
})

describe('RasterTileLayer.vue — 看全省与图例（2026-10-31）', () => {
  it('只导入市州包时，视图上限仍是全省（maxBounds 不被市州 bbox 锁死）', async () => {
    await mountLayer({ tileInfo: makeInfo({ bbox: GUIYANG_BBOX, zoomLevels: [14] }) })
    const opts = state.maps[0].opts
    expect(opts.maxBounds[0][0]).toBeCloseTo(24.55)
    expect(opts.maxBounds[0][1]).toBeCloseTo(103.55)
    expect(opts.maxBounds[1][0]).toBeCloseTo(29.25)
    expect(opts.maxBounds[1][1]).toBeCloseTo(109.65)
  })

  it('「全省视图」按钮把视野拉到全省 bbox', async () => {
    const wrapper = await mountLayer({
      tileInfo: makeInfo({ bbox: GUIYANG_BBOX, zoomLevels: [5, 6, 7, 8, 14] }),
    })
    const button = wrapper.find('.map-raster-province')
    expect(button.exists()).toBe(true)
    await button.trigger('click')
    expect(state.maps[0].fitBounds).toHaveBeenLastCalledWith(GUIZHOU_BOUNDS, {
      padding: [16, 16],
      maxZoom: 9,
    })
  })

  it('右侧图例：符号说明 + 覆盖信息 + 数据署名，可收起', async () => {
    const wrapper = await mountLayer({
      tileInfo: makeInfo({
        manifest: {
          provider: 'osm-render',
          license: 'ODbL-1.0 (© OpenStreetMap contributors)',
        } as any,
      }),
    })
    const legend = wrapper.find('.map-raster-legend')
    expect(legend.exists()).toBe(true)
    const text = legend.text()
    expect(text).toContain('图例')
    expect(text).toContain('帮扶村')
    expect(text).toContain('学校')
    expect(text).toContain('瓦片')
    expect(text).toContain('层级')
    expect(text).toContain('来源')
    expect(text).toContain('OpenStreetMap')
    await wrapper.find('.legend-toggle').trigger('click')
    expect(wrapper.find('.legend-items').exists()).toBe(false)
  })

  it('有 z5–8 概览时不提示补装；只有 z13/z14 时提示导入 guizhou-overview_z5-8.zip', async () => {
    const withOverview = await mountLayer({
      tileInfo: makeInfo({ zoomLevels: [5, 6, 7, 8, 14] }),
    })
    expect(withOverview.find('.map-raster-warn').exists()).toBe(false)

    const withoutOverview = await mountLayer({
      tileInfo: makeInfo({ zoomLevels: [13, 14], bbox: GUIYANG_BBOX }),
    })
    const warn = withoutOverview.find('.map-raster-warn')
    expect(warn.exists()).toBe(true)
    expect(warn.text()).toContain('guizhou-overview_z5-8.zip')
    expect(warn.text()).toContain('z13')
  })

  it('挂载比例尺控件（图注的一部分）', async () => {
    await mountLayer()
    expect(hoisted.scaleControl).toHaveBeenCalledWith(
      expect.objectContaining({ position: 'bottomleft', imperial: false })
    )
  })
})
