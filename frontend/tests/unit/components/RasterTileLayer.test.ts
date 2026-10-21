/**
 * components/map/RasterTileLayer.vue 单测
 *
 * Leaflet 在 jsdom 下无法真实渲染（需要布局尺寸 / 真实 DOM 测量），因此把 leaflet 模块
 * 整体替换为可断言的桩：只验证组件的行为契约（离线 URL、缩放范围、标注点、失败提示、
 * 事件与卸载清理），不验证 Leaflet 内部渲染。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'
import type { TileInfo } from '@/api/map'

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
    const instance: any = {
      el,
      opts,
      remove: vi.fn(),
      setView: vi.fn(),
      invalidateSize: vi.fn(),
    }
    state.maps.push(instance)
    return instance
  }

  const tileLayer = (url: string, opts: any) => {
    const handlers: Record<string, Function[]> = {}
    const instance: any = {
      url,
      opts,
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

  return { state, map, tileLayer, layerGroup, circleMarker }
})

vi.mock('leaflet', () => ({
  map: hoisted.map,
  tileLayer: hoisted.tileLayer,
  layerGroup: hoisted.layerGroup,
  circleMarker: hoisted.circleMarker,
}))

import RasterTileLayer from '@/components/map/RasterTileLayer.vue'

const { state } = hoisted

function makeInfo(overrides: Partial<TileInfo> = {}): TileInfo {
  return {
    available: true,
    tileCount: 12,
    zoomLevels: [4, 5, 8],
    totalBytes: 1024,
    dir: '/app/data/map_tiles',
    manifest: null,
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
    props: { tileInfo: makeInfo(), markers, ...props } as any,
  })
  await flushPromises()
  await nextTick()
  return wrapper
}

beforeEach(() => {
  state.maps.length = 0
  state.tileLayers.length = 0
  state.groups.length = 0
  state.circles.length = 0
})

describe('RasterTileLayer.vue — 离线瓦片加载', () => {
  it('tile-info 可用 → 创建地图与本地瓦片层（URL 不含外网 scheme）', async () => {
    const wrapper = await mountLayer()

    expect(state.maps).toHaveLength(1)
    expect(state.maps[0].el).toBe(wrapper.find('.map-raster-canvas').element)
    expect(state.maps[0].opts).toMatchObject({
      center: [26.65, 106.71],
      zoom: 7,
      minZoom: 4,
      maxZoom: 8,
    })
    expect(state.maps[0].invalidateSize).toHaveBeenCalled()

    const layer = state.tileLayers[0]
    expect(layer.url).toBe('/api/v1/map/tiles/{z}/{x}/{y}.png')
    expect(layer.url.startsWith('/api/v1/')).toBe(true)
    expect(layer.opts).toMatchObject({
      minZoom: 4,
      maxZoom: 8,
      noWrap: true,
      attribution: '离线瓦片',
    })
    expect(layer.addTo).toHaveBeenCalledWith(state.maps[0])
    expect(wrapper.find('.map-raster-notice').exists()).toBe(false)
    expect(wrapper.find('.map-raster-gcj02').exists()).toBe(false)
  })

  it('标注点按类型着色并绑定 tooltip，点击 emit marker-click', async () => {
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

  it('tileerror → 只 emit 一次 + 显示中文失败说明 + 可回退矢量视图', async () => {
    const wrapper = await mountLayer()
    const layer = state.tileLayers[0]

    layer.handlers.tileerror[0]()
    await nextTick()
    expect(wrapper.emitted('tile-error')).toHaveLength(1)
    const notice = wrapper.find('.map-raster-notice')
    expect(notice.exists()).toBe(true)
    expect(notice.text()).toContain('瓦片加载失败')

    // 连续多张瓦片 404 不应重复 emit / 刷屏
    layer.handlers.tileerror[0]()
    await nextTick()
    expect(wrapper.emitted('tile-error')).toHaveLength(1)

    await wrapper.find('.map-raster-fallback').trigger('click')
    expect(wrapper.emitted('fallback')).toHaveLength(1)
  })

  it('tile-info 不可用 → 不创建地图，显示中文说明并可回退', async () => {
    const wrapper = await mountLayer({ tileInfo: null, markers: [] })

    expect(state.maps).toHaveLength(0)
    expect(state.tileLayers).toHaveLength(0)
    const notice = wrapper.find('.map-raster-notice')
    expect(notice.text()).toContain('尚未预置离线瓦片')

    await wrapper.find('.map-raster-fallback').trigger('click')
    expect(wrapper.emitted('fallback')).toHaveLength(1)
  })

  it('available=false / 瓦片数与缩放级别为空 → 提示具体原因且不建图', async () => {
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
})

describe('RasterTileLayer.vue — GCJ-02 底图', () => {
  it('manifest.provider=amap → 显示偏移提示且标注点做 GCJ-02 修正', async () => {
    const wrapper = await mountLayer({
      tileInfo: makeInfo({ manifest: { provider: 'amap' } }),
    })

    expect(wrapper.find('.map-raster-gcj02').text()).toContain('GCJ-02')
    // 标注点已偏移（不再是 WGS-84 原值）
    expect(state.circles[0].latlng[0]).not.toBe(26.65)
    expect(state.circles[0].latlng[1]).not.toBe(106.71)
    // 入参不被修改
    expect(markers[0].lat).toBe(26.65)
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

  it('GCJ-02 底图时地图中心与 setView 同样做 WGS-84 → GCJ-02 修正（避免底图与标注整体错位）', async () => {
    const wrapper = await mountLayer({
      tileInfo: makeInfo({ manifest: { provider: 'amap' } }),
      center: { lng: 106.71, lat: 26.65 },
    })

    // 初始化中心已偏移（不再是 WGS-84 原值）
    expect(state.maps[0].opts.center[0]).not.toBe(26.65)
    expect(state.maps[0].opts.center[1]).not.toBe(106.71)
    // 与标注点使用同一转换结果
    expect(state.maps[0].opts.center).toEqual(state.circles[0].latlng)

    // 后续 setView 也必须走同一转换
    await wrapper.setProps({ center: { lng: 107.2, lat: 27.1 } })
    const view = state.maps[0].setView.mock.calls.at(-1)![0]
    expect(view[0]).not.toBe(27.1)
    expect(view[1]).not.toBe(107.2)
    expect(Math.abs(view[0] - 27.1)).toBeLessThan(0.01)
  })

  it('WGS-84 底图时地图中心保持原值', async () => {
    await mountLayer({ center: { lng: 106.71, lat: 26.65 } })
    expect(state.maps[0].opts.center).toEqual([26.65, 106.71])
  })
})

describe('RasterTileLayer.vue — 生命周期与响应式', () => {
  it('visible=false 不建图；切 true 建图；再切 false 销毁', async () => {
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
  })

  it('地图已存在时再次触发 syncMap 不会重建地图', async () => {
    const wrapper = await mountLayer()
    expect(state.maps).toHaveLength(1)

    await wrapper.setProps({ tileInfo: makeInfo({ zoomLevels: [6, 10], tileCount: 30 }) })
    await nextTick()
    expect(state.maps).toHaveLength(1)
    expect(state.tileLayers).toHaveLength(1)
  })

  it('center / zoom 变化 → 调用 setView', async () => {
    const wrapper = await mountLayer()
    const map = state.maps[0]

    await wrapper.setProps({ center: { lng: 110.5, lat: 30.2 } })
    expect(map.setView).toHaveBeenLastCalledWith([30.2, 110.5], 7)

    await wrapper.setProps({ zoom: 9 })
    expect(map.setView).toHaveBeenLastCalledWith([30.2, 110.5], 9)
  })

  it('markers 变化 → 清空并重绘标注点', async () => {
    const wrapper = await mountLayer()
    const group = state.groups[0]
    expect(group.clearLayers).toHaveBeenCalledTimes(1)

    await wrapper.setProps({ markers: [markers[0]] })
    await nextTick()
    expect(group.clearLayers).toHaveBeenCalledTimes(2)
    expect(state.circles).toHaveLength(4) // 3 + 1（旧桩不移除，仅清空）
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
