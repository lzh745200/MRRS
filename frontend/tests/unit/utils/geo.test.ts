import { describe, it, expect } from 'vitest'
import { haversineDistance, calculateRoute, parseCoordinate } from '@/utils/geo'

describe('utils/geo', () => {
  describe('haversineDistance', () => {
    it('相同点距离为 0', () => {
      const p = { lat: 26.5, lng: 107.5 }
      expect(haversineDistance(p, p)).toBe(0)
    })
    it('北京 -> 上海 ~ 1067 km', () => {
      const bj = { lat: 39.9042, lng: 116.4074 }
      const sh = { lat: 31.2304, lng: 121.4737 }
      const d = haversineDistance(bj, sh)
      expect(d).toBeGreaterThan(1050)
      expect(d).toBeLessThan(1100)
    })
    it('南北极 1° 距离约 111 km', () => {
      const a = { lat: 0, lng: 0 }
      const b = { lat: 1, lng: 0 }
      const d = haversineDistance(a, b)
      expect(d).toBeGreaterThan(110)
      expect(d).toBeLessThan(112)
    })
    it('东西距离在赤道 1° 约 111 km', () => {
      const a = { lat: 0, lng: 0 }
      const b = { lat: 0, lng: 1 }
      expect(haversineDistance(a, b)).toBeGreaterThan(110)
      expect(haversineDistance(a, b)).toBeLessThan(112)
    })
    it('对称性', () => {
      const a = { lat: 30, lng: 110 }
      const b = { lat: 25, lng: 105 }
      expect(haversineDistance(a, b)).toBeCloseTo(haversineDistance(b, a), 6)
    })
  })

  describe('calculateRoute', () => {
    it('近距离 (< 1 分钟)', () => {
      const a = { lat: 26.5, lng: 107.5 }
      const b = { lat: 26.5001, lng: 107.5001 }
      const r = calculateRoute(a, b)
      expect(r.straightDistanceKm).toBe(0)
      expect(r.formattedTime).toBe('< 1 分钟')
    })
    it('中距离 (1-60 分钟)', () => {
      const a = { lat: 26.5, lng: 107.5 }
      const b = { lat: 26.6, lng: 107.5 }
      const r = calculateRoute(a, b)
      expect(r.formattedTime).toMatch(/^约 \d+ 分钟$/)
    })
    it('远距离 (>= 60 分钟)', () => {
      const a = { lat: 26.5, lng: 107.5 }
      const b = { lat: 28.5, lng: 107.5 }
      const r = calculateRoute(a, b)
      expect(r.formattedTime).toMatch(/^约 \d+ 小时 \d+ 分钟$/)
    })
    it('道路距离 ≈ 直线距离 * 1.5', () => {
      const a = { lat: 26.5, lng: 107.5 }
      const b = { lat: 26.6, lng: 107.5 }
      const r = calculateRoute(a, b)
      // 1.5x curvature factor, 但因为 toFixed 0.1 取整, 允许 0.1 误差
      expect(Math.abs(r.estimatedRoadDistanceKm - r.straightDistanceKm * 1.5)).toBeLessThanOrEqual(0.1)
    })
    it('返回值字段完整', () => {
      const a = { lat: 26.5, lng: 107.5 }
      const b = { lat: 27.5, lng: 108.5 }
      const r = calculateRoute(a, b)
      expect(r.origin).toEqual(a)
      expect(r.destination).toEqual(b)
      expect(typeof r.straightDistanceKm).toBe('number')
      expect(typeof r.estimatedRoadDistanceKm).toBe('number')
      expect(typeof r.estimatedDriveMinutes).toBe('number')
      expect(typeof r.formattedTime).toBe('string')
    })
  })

  describe('parseCoordinate', () => {
    it('标准 "26.5,107.5"', () => {
      expect(parseCoordinate('26.5,107.5')).toEqual({ lat: 26.5, lng: 107.5 })
    })
    it('带空格 "26.5, 107.5"', () => {
      expect(parseCoordinate('26.5, 107.5')).toEqual({ lat: 26.5, lng: 107.5 })
    })
    it('中文逗号', () => {
      expect(parseCoordinate('26.5，107.5')).toEqual({ lat: 26.5, lng: 107.5 })
    })
    it('整数', () => {
      expect(parseCoordinate('26,107')).toEqual({ lat: 26, lng: 107 })
    })
    it('负坐标', () => {
      expect(parseCoordinate('-23.5,-46.5')).toEqual({ lat: -23.5, lng: -46.5 })
    })
    it('lat > 90 无效', () => {
      expect(parseCoordinate('95,107.5')).toBeNull()
    })
    it('lng > 180 无效', () => {
      expect(parseCoordinate('26.5,200')).toBeNull()
    })
    it('空字符串', () => {
      expect(parseCoordinate('')).toBeNull()
    })
    it('单值', () => {
      expect(parseCoordinate('26.5')).toBeNull()
    })
    it('三个值', () => {
      expect(parseCoordinate('1,2,3')).toBeNull()
    })
  })

  describe('parseCoordinate 补充', () => {
    it('经度,纬度 顺序自动识别（互换分支）', () => {
      expect(parseCoordinate('107.5,26.5')).toEqual({ lat: 26.5, lng: 107.5 })
    })
    it('中文逗号分隔', () => {
      expect(parseCoordinate('26.5，107.5')).toEqual({ lat: 26.5, lng: 107.5 })
    })
    it('负数坐标', () => {
      expect(parseCoordinate('-30,-110')).toEqual({ lat: -30, lng: -110 })
    })
    it('非法输入返回 null', () => {
      expect(parseCoordinate('abc')).toBeNull()
      expect(parseCoordinate('')).toBeNull()
      expect(parseCoordinate('1000,2000')).toBeNull()
      expect(parseCoordinate('90,1000')).toBeNull()
    })
  })
})
