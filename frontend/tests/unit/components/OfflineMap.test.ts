/**
 * OfflineMap.vue 测试
 * mock @/utils/echarts 与 GeoJSON 动态导入，覆盖：
 * - init / registerMap / setOption 渲染流程
 * - region-click / marker-click 事件（series 点击 + zr 背景点击）
 * - watch 重渲染、resize、unmount 清理
 * - 动态导入失败回退空地图
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import OfflineMap from '@/components/map/OfflineMap.vue'

enableAutoUnmount(afterEach)

const mocks = vi.hoisted(() => {
  let seriesClickHandler: any = null
  let zrClickHandler: any = null

  const zrOn = vi.fn((_e: string, cb: any) => {
    zrClickHandler = cb
  })

  const mockChart = {
    on: vi.fn((_e: string, _type: string, cb: any) => {
      seriesClickHandler = cb
    }),
    getZr: vi.fn(() => ({ on: zrOn })),
    setOption: vi.fn((option: any) => {
      const fmt = option?.tooltip?.formatter
      if (typeof fmt === 'function') {
        fmt({ seriesType: 'scatter', name: '南明区' })
        fmt({ seriesType: 'scatter', name: 'no-pref' })
        fmt({ seriesType: 'map', name: '南明区' })
        fmt({ seriesType: 'map', name: 'no-pref' })
      }
      for (const s of option?.series || []) {
        if (typeof s?.symbolSize === 'function') {
          s.symbolSize([1, 2, 3])
          s.symbolSize([1, 2, 0])
        }
        if (typeof s?.label?.formatter === 'function') {
          s.label.formatter({ name: 'point' })
        }
      }
    }),
    resize: vi.fn(),
    dispose: vi.fn(),
    convertFromPixel: vi.fn(() => [107.5, 26.5]),
  }

  const mockEcharts = {
    init: vi.fn(() => mockChart),
    registerMap: vi.fn(),
  }

  return { mockChart, mockEcharts, get seriesClickHandler() { return seriesClickHandler }, set seriesClickHandler(v: any) { seriesClickHandler = v }, get zrClickHandler() { return zrClickHandler }, set zrClickHandler(v: any) { zrClickHandler = v } }
})

const { mockChart, mockEcharts } = mocks

vi.mock('@/utils/echarts', () => ({ default: mocks.mockEcharts }))

/** 10 个地州市：覆盖 prefColors 的 hues[i] 与 i*40 回退分支 */
const geo = {
  type: 'FeatureCollection',
  features: [
    { properties: { prefecture: '贵阳', name: '南明区' } },
    { properties: { prefecture: '贵阳', name: '云岩区' } },
    { properties: { prefecture: '遵义', name: '红花岗区' } },
    { properties: { prefecture: '毕节', name: '七星关区' } },
    { properties: { prefecture: '六盘水', name: '钟山区' } },
    { properties: { prefecture: '安顺', name: '西秀区' } },
    { properties: { prefecture: '铜仁', name: '碧江区' } },
    { properties: { prefecture: '黔东南', name: '凯里市' } },
    { properties: { prefecture: '黔南', name: '都匀市' } },
    { properties: { prefecture: '黔西南', name: '兴义市' } },
    { properties: { prefecture: '无属性结构' } },
    { name: '无县区' },
    {},
  ],
}

/** 覆盖 getMarkerColor 全部类型分支 */
const markers = [
  { lng: 106.7, lat: 26.6, name: 'm-village', type: 'village' },
  { lng: 106.8, lat: 26.7, name: 'm-school', type: 'school' },
  { lng: 106.9, lat: 26.8, name: 'm-project', type: 'project', value: 5 },
  { lng: 107.0, lat: 26.9, name: 'm-hospital', type: 'hospital' },
  { lng: 107.1, lat: 27.0, name: 'm-other', type: 'unknown' },
  { lng: 107.2, lat: 27.1, name: 'm-novalue', type: 'village' },
]

const routeLines = [
  { coords: [[106.7, 26.6], [107.2, 27.1]], label: '路线A' },
  { coords: [[106.8, 26.7], [107.0, 26.9]], label: '路线B' },
]

const originMarker = { lng: 106.71, lat: 26.65 }

function mountMap(props: Record<string, unknown> = {}) {
  return mount(OfflineMap, { props })
}

describe('OfflineMap.vue', () => {
  beforeEach(() => {
    mocks.seriesClickHandler = null
    mocks.zrClickHandler = null
    vi.clearAllMocks()
    mockChart.convertFromPixel.mockReturnValue([107.5, 26.5])
  })

  it('使用 geoJsonData prop 初始化地图并渲染（含标记/路线/出发点）', async () => {
    const wrapper = mountMap({
      geoJsonData: geo,
      markers,
      regionData: [{ name: '南明区', value: 5 }],
      routeLines,
      originMarker,
      width: '600px',
      height: '400px',
    })
    await flushPromises()

    expect(mockEcharts.init).toHaveBeenCalled()
    expect(mockEcharts.registerMap).toHaveBeenCalledWith('guizhou', geo)
    expect(mockChart.setOption).toHaveBeenCalledTimes(1)
    const container = wrapper.find('.offline-map-container')
    expect(container.attributes('style')).toContain('600px')
    expect(container.attributes('style')).toContain('400px')

    // series 点击: scatter 命中标记 → marker-click
    mocks.seriesClickHandler({ seriesType: 'scatter', name: 'm-village' })
    expect(wrapper.emitted('marker-click')![0][0]).toMatchObject({ name: 'm-village' })

    // scatter 未命中
    mocks.seriesClickHandler({ seriesType: 'scatter', name: 'nope' })
    expect(wrapper.emitted('marker-click')).toHaveLength(1)

    // effectScatter 命中 → marker-click
    mocks.seriesClickHandler({ seriesType: 'effectScatter', name: 'm-school' })
    expect(wrapper.emitted('marker-click')).toHaveLength(2)

    // map + cp 有效 → region-click
    mocks.seriesClickHandler({ seriesType: 'map', name: '南明区', data: { cp: [106.5, 26.5] } })
    expect(wrapper.emitted('region-click')!.at(-1)![0]).toMatchObject({ name: '南明区', lng: 106.5, lat: 26.5 })

    // map + cp 无效 → 像素转换
    mockChart.convertFromPixel.mockReturnValueOnce([9.1, 8.2])
    mocks.seriesClickHandler({ seriesType: 'map', name: '云岩区', data: { cp: [null, null] }, event: { offsetX: 1, offsetY: 2 } })
    expect(wrapper.emitted('region-click')!.at(-1)![0]).toMatchObject({ name: '云岩区', lng: 9.1, lat: 8.2 })

    // map + 转换出 NaN → 不 emit
    mockChart.convertFromPixel.mockReturnValueOnce([NaN, 8.2])
    mocks.seriesClickHandler({ seriesType: 'map', name: '云岩区', data: { cp: null }, event: { offsetX: 1, offsetY: 2 } })
    expect(wrapper.emitted('region-click')).toHaveLength(2)

    // 其他 seriesType → 无操作
    mocks.seriesClickHandler({ seriesType: 'lines', name: 'x' })
    expect(wrapper.emitted('region-click')).toHaveLength(2)

    // zr 背景点击: target 存在 → 跳过
    mocks.zrClickHandler({ target: {}, offsetX: 0, offsetY: 0 })
    expect(wrapper.emitted('region-click')).toHaveLength(2)

    // zr 背景点击: 有效坐标 → region-click(name='')
    mockChart.convertFromPixel.mockReturnValueOnce([3.3, 4.4])
    mocks.zrClickHandler({ target: null, offsetX: 5, offsetY: 6 })
    expect(wrapper.emitted('region-click')!.at(-1)![0]).toMatchObject({ name: '', lng: 3.3, lat: 4.4 })

    // zr 背景点击: NaN → 不 emit
    mockChart.convertFromPixel.mockReturnValueOnce([NaN, 4.4])
    mocks.zrClickHandler({ target: null, offsetX: 5, offsetY: 6 })
    expect(wrapper.emitted('region-click')).toHaveLength(3)
  })

  it('无 geoJsonData 时动态导入真实 guizhou.json', async () => {
    const wrapper = mountMap({ markers, routeLines })
    await vi.waitFor(() => expect(mockEcharts.init).toHaveBeenCalled(), { timeout: 10000 })

    expect(mockEcharts.registerMap).toHaveBeenCalled()
    const mapArg = mockEcharts.registerMap.mock.calls[0][1] as any
    expect(mapArg.features.length).toBeGreaterThan(0)
    expect(mockChart.setOption).toHaveBeenCalledTimes(1)
    void wrapper
  })

  it('GeoJSON 动态导入失败时回退空地图并告警', async () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.doMock('@/assets/geo/guizhou.json', () => {
      throw new Error('load failed')
    })
    const wrapper = mountMap()
    await vi.waitFor(() => expect(warnSpy).toHaveBeenCalled(), { timeout: 10000 })

    expect(mockEcharts.registerMap).toHaveBeenCalledWith(
      'guizhou',
      expect.objectContaining({ type: 'FeatureCollection', features: [] })
    )
    expect(mockChart.setOption).toHaveBeenCalledTimes(1)
    warnSpy.mockRestore()
    vi.doUnmock('@/assets/geo/guizhou.json')
    void wrapper
  })

  it('空 GeoJSON（无 features）与空 routeLines 的防御分支', async () => {
    const wrapper = mountMap({ geoJsonData: {}, routeLines: null as any })
    await flushPromises()

    expect(mockChart.setOption).toHaveBeenCalledTimes(1)
    const option = mockChart.setOption.mock.calls[0][0]
    const linesSeries = option.series.filter((s: any) => s.type === 'lines')
    expect(linesSeries).toHaveLength(0)
  })

  it('GeoJSON default 为 falsy 时回退到模块本体', async () => {
    vi.doMock('@/assets/geo/guizhou.json', () => ({ default: null, features: [] }))
    const wrapper = mountMap()
    await vi.waitFor(() => expect(mockEcharts.registerMap).toHaveBeenCalled(), { timeout: 10000 })

    expect(mockChart.setOption).toHaveBeenCalledTimes(1)
    vi.doUnmock('@/assets/geo/guizhou.json')
    void wrapper
  })

  it('图表初始化前触发 watch 时 renderMap 走 chart 为空防御分支', async () => {
    // 让 GeoJSON 动态导入永不 resolve → initChart 不会执行 → chart 保持 null
    vi.doMock('@/assets/geo/guizhou.json', () => new Promise(() => {}))
    const wrapper = mountMap({
      markers: [{ lng: 1, lat: 2, name: 'm1', type: 'village' }],
    })
    await nextTick()
    await wrapper.setProps({
      markers: [
        { lng: 1, lat: 2, name: 'm1', type: 'village' },
        { lng: 3, lat: 4, name: 'm2', type: 'school' },
      ],
    })
    await flushPromises()
    expect(mockEcharts.init).not.toHaveBeenCalled()
    vi.doUnmock('@/assets/geo/guizhou.json')
    void wrapper
  })

  it('props 变化时 watch 重渲染；geoJsonData 变化时重新注册地图', async () => {
    const wrapper = mountMap({ geoJsonData: geo })
    await flushPromises()
    expect(mockChart.setOption).toHaveBeenCalledTimes(1)

    await wrapper.setProps({ markers: [...markers] })
    await flushPromises()
    expect(mockChart.setOption).toHaveBeenCalledTimes(2)
    expect(mockEcharts.registerMap).toHaveBeenCalledTimes(1)

    const newGeo = { type: 'FeatureCollection', features: [{ properties: { prefecture: '贵阳', name: '南明区' } }] }
    await wrapper.setProps({ geoJsonData: newGeo, regionData: [], routeLines: [], originMarker: null })
    await flushPromises()
    expect(mockEcharts.registerMap).toHaveBeenCalledTimes(2)
    expect(mockChart.setOption).toHaveBeenCalledTimes(3)
  })

  it('resize 事件触发 chart.resize；unmount 时 dispose 并移除监听', async () => {
    const addSpy = vi.spyOn(window, 'addEventListener')
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const wrapper = mountMap({ geoJsonData: geo })
    await flushPromises()
    const zrHandler = mocks.zrClickHandler

    window.dispatchEvent(new Event('resize'))
    expect(mockChart.resize).toHaveBeenCalledTimes(1)

    wrapper.unmount()
    expect(mockChart.dispose).toHaveBeenCalled()
    expect(removeSpy).toHaveBeenCalledWith('resize', expect.any(Function))
    expect(addSpy).toHaveBeenCalledWith('resize', expect.any(Function))

    // chart 置空后 zr 背景点击 → if (!chart) return 防御分支
    zrHandler({ target: null })
    expect(mockChart.convertFromPixel).not.toHaveBeenCalled()
  })

  /**
   * `initChart()` 开头的 `if (!chartRef.value || !geoJson) return` 守卫真侧。
   *
   * onMounted 里先赋值 geoJson、再 `await nextTick()`、最后才 initChart。
   * 若用户在该 await 窗口内就导航离开（快速切页/关闭弹窗），
   * 组件已卸载且模板 ref 被 Vue 置 null，此时必须早退：
   * 否则会给已脱离文档的 DOM 创建 echarts 实例（内存泄漏 + resize 监听泄漏）。
   */
  it('挂载后立即卸载 → initChart 守卫早退，不创建 echarts 实例', async () => {
    const wrapper = mountMap({ geoJsonData: geo })
    // 不 await 任何微任务，直接卸载：onMounted 仍挂在 `await nextTick()` 上
    wrapper.unmount()
    await flushPromises()

    expect(mockEcharts.init).not.toHaveBeenCalled()
    expect(mockEcharts.registerMap).not.toHaveBeenCalled()
    expect(mockChart.setOption).not.toHaveBeenCalled()
  })

  it('未传 geoJsonData 时在动态导入期间卸载 → 同样早退（geoJson 已赋值但 ref 已置 null）', async () => {
    const wrapper = mountMap()
    wrapper.unmount()
    await flushPromises()
    expect(mockEcharts.init).not.toHaveBeenCalled()
  })
})
