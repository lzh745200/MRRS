/**
 * Vitest 全局测试配置
 * 在 jsdom 环境中模拟浏览器 API
 */

// v8 coverage provider 在 Windows 上存在 .tmp 目录竞态（写入 ENOENT）。
// 每次测试文件执行前确保目录存在（幂等），避免 clean:false 下无人创建。
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'
try {
  mkdirSync(join(process.cwd(), 'coverage', '.tmp'), { recursive: true })
} catch {
  // 目录创建失败不影响测试本体
}

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = String(value)
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    },
    get length() {
      return Object.keys(store).length
    },
    key: (index: number) => Object.keys(store)[index] ?? null,
  }
})()

Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock })

// Mock sessionStorage
const sessionStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = String(value)
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    },
    get length() {
      return Object.keys(store).length
    },
    key: (index: number) => Object.keys(store)[index] ?? null,
  }
})()

Object.defineProperty(globalThis, 'sessionStorage', {
  value: sessionStorageMock,
})

// Mock matchMedia
Object.defineProperty(globalThis, 'matchMedia', {
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null as MediaQueryList['onchange'],
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})

// Mock IntersectionObserver
class MockIntersectionObserver {
  callback: Function
  options: any
  elements: Set<Element> = new Set()
  constructor(callback: Function, options?: any) {
    this.callback = callback
    this.options = options
  }
  observe(el: Element) {
    this.elements.add(el)
  }
  unobserve(el: Element) {
    this.elements.delete(el)
  }
  disconnect() {
    this.elements.clear()
  }
  // Helper to simulate intersection
  triggerIntersect(entries: any[]) {
    this.callback(entries, this)
  }
}

Object.defineProperty(globalThis, 'IntersectionObserver', {
  value: MockIntersectionObserver,
  writable: true,
  configurable: true,
})

// Mock ResizeObserver
class MockResizeObserver {
  callback: Function
  constructor(callback: Function) {
    this.callback = callback
  }
  observe() {}
  unobserve() {}
  disconnect() {}
}

Object.defineProperty(globalThis, 'ResizeObserver', {
  value: MockResizeObserver,
  writable: true,
  configurable: true,
})

// Mock requestAnimationFrame / cancelAnimationFrame
if (typeof globalThis.requestAnimationFrame === 'undefined') {
  ;(globalThis as any).requestAnimationFrame = (cb: FrameRequestCallback) => setTimeout(cb, 0)
}
if (typeof globalThis.cancelAnimationFrame === 'undefined') {
  ;(globalThis as any).cancelAnimationFrame = (id: number) => clearTimeout(id)
}

// Mock URL.createObjectURL / revokeObjectURL
if (typeof URL.createObjectURL === 'undefined') {
  URL.createObjectURL = () => 'blob:mock-url'
}
if (typeof URL.revokeObjectURL === 'undefined') {
  URL.revokeObjectURL = () => {}
}

// Mock Element Plus components/directives for testing
import { config } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'

// 全局 stub router：组件树中的 useRouter/useRoute 注入不再告警
// （2026-08-30 警告治理：此前 445 条 "injection Symbol(router) not found"）。
// 各测试如自行传入真实 router，会覆盖此 stub 的 provide，行为不变。
const stubRouter = createRouter({
  history: createWebHistory(),
  routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
})
config.global.plugins = [stubRouter]

// Stub all Element Plus components globally
config.global.stubs = {
  // 布局组件（同步导入，图片路径在 jsdom 中导致 file URL 错误）
  DefaultLayoutSafe: true,
  // Element Plus 组件
  'el-button': true,
  'el-input': true,
  'el-form': true,
  'el-form-item': true,
  'el-select': true,
  'el-option': true,
  'el-table': true,
  'el-table-column': true,
  'el-pagination': true,
  'el-dialog': true,
  'el-card': true,
  'el-tag': true,
  'el-icon': true,
  'el-row': true,
  'el-col': true,
  'el-upload': true,
  'el-tabs': true,
  'el-tab-pane': true,
  'el-switch': true,
  'el-date-picker': true,
  'el-input-number': true,
  'el-checkbox': true,
  'el-checkbox-group': true,
  'el-radio': true,
  'el-radio-group': true,
  'el-progress': true,
  'el-avatar': true,
  'el-badge': true,
  'el-breadcrumb': true,
  'el-breadcrumb-item': true,
  'el-divider': true,
  'el-descriptions': true,
  'el-descriptions-item': true,
  'el-dropdown': true,
  'el-dropdown-menu': true,
  'el-dropdown-item': true,
  'el-popconfirm': true,
  'el-tooltip': true,
  'el-tree': true,
  'el-tree-select': true,
  'el-slider': true,
  'el-link': true,
  'el-button-group': true,
  'el-menu': true,
  'el-menu-item': true,
  'el-submenu': true,
  'el-scrollbar': true,
  'el-aside': true,
  'el-container': true,
  'el-header': true,
  'el-main': true,
  'el-footer': true,
  // 保持默认布尔桩：全仓 43 处测试以 el-empty-stub 标签断言；
  // 描述文本经 attrs 透传，可用 [description="..."] 选择器断言
  'el-empty': true,
  'el-skeleton': true,
  'el-loading': true,
  'el-image': true,
  'el-timeline': true,
  'el-timeline-item': true,
  'el-steps': true,
  'el-step': true,
  'el-result': true,
  'el-collapse': true,
  'el-collapse-item': true,
  'el-popover': true,
  'router-link': true,
  'router-view': true,
}

config.global.directives = {
  loading: () => {},
}

// Reset storage before each test
import { beforeEach, vi } from 'vitest'

beforeEach(() => {
  localStorageMock.clear()
  sessionStorageMock.clear()
})

// Suppress console.warn for Vue component resolution warnings in tests
const originalWarn = console.warn
console.warn = (...args: any[]) => {
  const msg = args[0]?.toString() || ''
  if (msg.includes('Failed to resolve component') || msg.includes('Failed to resolve directive')) {
    return
  }
  originalWarn(...args)
}

// Mock HTMLCanvasElement 2d context
// jsdom 未实现 canvas;echarts/zrender 在 dispose 时调用 clearRect 等方法会抛
// TypeError(clearRect of null)。这里提供最小 2d 上下文桩:常用方法为空函数,
// 其余任意方法由 Proxy 兜底。writable+configurable 保证个别测试可自行覆盖。
const canvasNoop = () => {}
const base2dContext: Record<string, unknown> = {
  clearRect: canvasNoop,
  fillRect: canvasNoop,
  strokeRect: canvasNoop,
  beginPath: canvasNoop,
  closePath: canvasNoop,
  moveTo: canvasNoop,
  lineTo: canvasNoop,
  bezierCurveTo: canvasNoop,
  quadraticCurveTo: canvasNoop,
  arc: canvasNoop,
  arcTo: canvasNoop,
  ellipse: canvasNoop,
  rect: canvasNoop,
  fill: canvasNoop,
  stroke: canvasNoop,
  save: canvasNoop,
  restore: canvasNoop,
  translate: canvasNoop,
  scale: canvasNoop,
  rotate: canvasNoop,
  transform: canvasNoop,
  setTransform: canvasNoop,
  resetTransform: canvasNoop,
  clip: canvasNoop,
  drawImage: canvasNoop,
  fillText: canvasNoop,
  strokeText: canvasNoop,
  setLineDash: canvasNoop,
  putImageData: canvasNoop,
  measureText: () => ({ width: 0 }),
  getLineDash: () => [],
  getImageData: () => ({ data: [] }),
  createImageData: () => ({ data: [] }),
  createLinearGradient: () => ({ addColorStop: canvasNoop }),
  createRadialGradient: () => ({ addColorStop: canvasNoop }),
  createPattern: () => ({}),
}
const canvas2dContextStub = new Proxy(base2dContext, {
  get(target, prop) {
    if (prop in target) return target[prop as string]
    // symbol 属性(如 Symbol.toPrimitive)返回 undefined,避免隐式类型转换抛错
    if (typeof prop === 'symbol') return undefined
    return canvasNoop
  },
})

if (typeof HTMLCanvasElement !== 'undefined') {
  Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
    value: function getContext(this: HTMLCanvasElement, contextType: string) {
      return contextType === '2d' ? canvas2dContextStub : null
    },
    writable: true,
    configurable: true,
  })
  Object.defineProperty(HTMLCanvasElement.prototype, 'toDataURL', {
    value: () => 'data:image/png;base64,mock',
    writable: true,
    configurable: true,
  })
}

// Mock window.open for print tests
if (typeof window !== 'undefined') {
  if (!('open' in window)) {
    Object.defineProperty(window, 'open', {
      value: vi.fn(() => null),
      writable: true,
      configurable: true,
    })
  } else {
    vi.spyOn(window, 'open').mockReturnValue(null)
  }
}
