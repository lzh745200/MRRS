import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { useAutoLock } from '@/composables/useAutoLock'
import { useDataPackageStore } from '@/stores/dataPackage'
import StatsCard from '@/components/common/StatsCard.vue'
import { sanitizeHtml, stripHtml, escapeHtml } from '@/utils/sanitize'
import sanitizeDefault from '@/utils/sanitize'

const mockGetDataPackages = vi.fn()
const mockGetDataPackage = vi.fn()
const mockExportDataPackage = vi.fn()
const mockImportDataPackage = vi.fn()
const mockPreviewDataPackage = vi.fn()
const mockConfirmImport = vi.fn()
const mockDownloadDataPackage = vi.fn()
const mockDeleteDataPackage = vi.fn()

vi.mock('@/api/dataPackage', () => ({
  getDataPackages: (...args: any[]) => mockGetDataPackages(...args),
  getDataPackage: (...args: any[]) => mockGetDataPackage(...args),
  exportDataPackage: (...args: any[]) => mockExportDataPackage(...args),
  importDataPackage: (...args: any[]) => mockImportDataPackage(...args),
  previewDataPackage: (...args: any[]) => mockPreviewDataPackage(...args),
  confirmImport: (...args: any[]) => mockConfirmImport(...args),
  downloadDataPackage: (...args: any[]) => mockDownloadDataPackage(...args),
  deleteDataPackage: (...args: any[]) => mockDeleteDataPackage(...args),
}))

const DummyIcon = { template: '<svg class="dummy-icon"><path /></svg>' }

const stubs = { 'el-icon': { name: 'ElIcon', template: '<i class="el-icon"><slot /></i>' } }

function mountHost(opts: any = {}) {
  let api: any
  const Comp = defineComponent({
    setup() {
      api = useAutoLock(opts)
      return () => h('div')
    },
  })
  const w = mount(Comp, { attachTo: document.body })
  return { w, getApi: () => api }
}

describe('zzz-final: useAutoLock（自动锁屏）', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    localStorage.clear()
  })
  afterEach(() => {
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  it('默认 15 分钟锁屏', () => {
    const onLock = vi.fn()
    const { w, getApi } = mountHost({ onLock })
    const api = getApi()
    expect(api.getMinutes()).toBe(15)
    vi.advanceTimersByTime(15 * 60 * 1000 + 100)
    expect(onLock).toHaveBeenCalledTimes(1)
    w.unmount()
  })

  it('自定义分钟数与 onLock', () => {
    const onLock = vi.fn()
    const { w, getApi } = mountHost({ getMinutes: () => 2, onLock })
    const api = getApi()
    expect(api.getMinutes()).toBe(2)
    vi.advanceTimersByTime(2 * 60 * 1000 + 100)
    expect(onLock).toHaveBeenCalledTimes(1)
    w.unmount()
  })

  it('用户操作重置计时器', () => {
    const onLock = vi.fn()
    const { w, getApi } = mountHost({ getMinutes: () => 2, onLock })
    const api = getApi()
    // 1 分钟后有操作 → 重置
    vi.advanceTimersByTime(60 * 1000)
    window.dispatchEvent(new Event('mousemove'))
    vi.advanceTimersByTime(60 * 1000 + 100)
    expect(onLock).not.toHaveBeenCalled()
    vi.advanceTimersByTime(2 * 60 * 1000)
    expect(onLock).toHaveBeenCalledTimes(1)
    w.unmount()
  })

  it('卸载时清理定时器', () => {
    const onLock = vi.fn()
    const { w, getApi } = mountHost({ getMinutes: () => 1, onLock })
    const api = getApi()
    api.unbind()
    vi.advanceTimersByTime(10 * 60 * 1000)
    expect(onLock).not.toHaveBeenCalled()
    w.unmount()
  })

  it('localStorage 配置读取', () => {
    localStorage.setItem('auto-lock-minutes', '30')
    const { w, getApi } = mountHost()
    expect(getApi().getMinutes()).toBe(30)
    w.unmount()
  })

  it('非法配置回退默认', () => {
    localStorage.setItem('auto-lock-minutes', 'abc')
    const { w, getApi } = mountHost()
    expect(getApi().getMinutes()).toBe(15)
    w.unmount()
  })

  it('配置 0/负数 回退默认', () => {
    localStorage.setItem('auto-lock-minutes', '0')
    let { w, getApi } = mountHost()
    expect(getApi().getMinutes()).toBe(15)
    w.unmount()
    localStorage.setItem('auto-lock-minutes', '-5')
    ;({ w, getApi } = mountHost())
    expect(getApi().getMinutes()).toBe(15)
    w.unmount()
  })

  it('click/keydown/touchstart 事件均重置计时器', () => {
    const onLock = vi.fn()
    const { w, getApi } = mountHost({ getMinutes: () => 1, onLock })
    const api = getApi()
    vi.advanceTimersByTime(50 * 1000)
    window.dispatchEvent(new Event('click'))
    window.dispatchEvent(new Event('keydown'))
    window.dispatchEvent(new Event('touchstart'))
    // 事件在 t=50s 重置计时器 → 下一次触发在 t=110s
    vi.advanceTimersByTime(59 * 1000 + 100)
    expect(onLock).not.toHaveBeenCalled()
    vi.advanceTimersByTime(60 * 1000)
    expect(onLock).toHaveBeenCalledTimes(1)
    w.unmount()
  })

  it('resetTimer 二次调用时清除旧定时器（timer 非空分支）', () => {
    const onLock = vi.fn()
    const { w, getApi } = mountHost({ getMinutes: () => 1, onLock })
    const api = getApi()
    const clearSpy = vi.spyOn(window, 'clearTimeout')
    api.resetTimer()
    expect(clearSpy).toHaveBeenCalledTimes(1)
    w.unmount()
  })

  it('默认 lockNow（未注入 onLock）静默执行（require 在 ESM 测试环境不可用走 catch）', () => {
    // vitest/vite-node 的模块级 require shim 无法解析 @/ 别名，
    // 且 vi.mock 不拦截 require 路径 → 必走 try 的 catch 分支（静默）
    const { w } = mountHost()
    expect(() => vi.advanceTimersByTime(15 * 60 * 1000 + 100)).not.toThrow()
    w.unmount()
  })

  it('unbind 幂等：二次调用不抛错', () => {
    const { w, getApi } = mountHost()
    const api = getApi()
    api.unbind()
    expect(() => api.unbind()).not.toThrow()
    w.unmount()
  })
})

describe('zzz-final: useDataPackageStore', () => {
  let store: ReturnType<typeof useDataPackageStore>
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    store = useDataPackageStore()
  })

  it('initial state: all empty/zero', () => {
    expect(store.packages).toEqual([])
    expect(store.currentPackage).toBeNull()
    expect(store.previewData).toEqual([])
    expect(store.importResult).toBeNull()
    expect(store.exportResult).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.exporting).toBe(false)
    expect(store.importing).toBe(false)
    expect(store.error).toBeNull()
    expect(store.total).toBe(0)
  })

  it('validatedPackages getter 过滤 status=validated', () => {
    store.packages = [
      { id: 1, status: 'validated' } as any,
      { id: 2, status: 'imported' } as any,
    ]
    expect(store.validatedPackages).toHaveLength(1)
  })

  it('importedPackages getter 过滤 status=imported', () => {
    store.packages = [
      { id: 1, status: 'validated' } as any,
      { id: 2, status: 'imported' } as any,
    ]
    expect(store.importedPackages).toHaveLength(1)
  })

  it('failedPackages getter 过滤 status=failed', () => {
    store.packages = [
      { id: 1, status: 'failed' } as any,
      { id: 2, status: 'imported' } as any,
    ]
    expect(store.failedPackages).toHaveLength(1)
  })

  it('fetchPackages 成功时填充 packages + total', async () => {
    mockGetDataPackages.mockResolvedValueOnce({ items: [{ id: 1 }], total: 1 })
    await store.fetchPackages({ page: 1 })
    expect(mockGetDataPackages).toHaveBeenCalledWith({ page: 1 })
    expect(store.packages).toHaveLength(1)
    expect(store.total).toBe(1)
  })

  it('fetchPackages 失败时设置 error + 抛出', async () => {
    mockGetDataPackages.mockRejectedValueOnce(new Error('boom'))
    await expect(store.fetchPackages()).rejects.toThrow('boom')
    expect(store.error).toBe('boom')
  })

  it('fetchPackage 成功时设置 currentPackage', async () => {
    const pkg = { id: 5, name: 'X' }
    mockGetDataPackage.mockResolvedValueOnce(pkg)
    await store.fetchPackage(5)
    expect(store.currentPackage).toEqual(pkg)
  })

  it('exportPackage 成功时设置 exportResult', async () => {
    const result = { url: 'http://x' }
    mockExportDataPackage.mockResolvedValueOnce(result)
    await store.exportPackage({ org_id: 1, items: [] })
    expect(store.exportResult).toEqual(result)
    expect(store.exporting).toBe(false)
  })

  it('importPackage 成功 + valid 时加入 packages 列表', async () => {
    const result = {
      package_id: 99,
      package_code: 'PKG-001',
      status: 'validated',
      validation: { is_valid: true },
      manifest: { version: '2.0' },
    }
    mockImportDataPackage.mockResolvedValueOnce(result)
    await store.importPackage(new File([], 'pkg.zip'), 1)
    expect(store.importResult).toEqual(result)
    expect(store.packages[0].id).toBe(99)
    expect(store.packages[0].status).toBe('validated')
  })

  it('importPackage 成功 + invalid 时不加入 packages', async () => {
    const result = { validation: { is_valid: false }, package_id: 0 }
    mockImportDataPackage.mockResolvedValueOnce(result)
    await store.importPackage(new File([], 'bad.zip'))
    expect(store.packages).toEqual([])
  })

  it('importPackage valid 且无 orgId 时 org_id 回退 0', async () => {
    const result = {
      package_id: 77,
      package_code: 'PKG-NO-ORG',
      status: 'validated',
      validation: { is_valid: true },
      manifest: { version: '3.0' },
    }
    mockImportDataPackage.mockResolvedValueOnce(result)
    await store.importPackage(new File([], 'no-org.zip'))
    expect(store.packages[0].org_id).toBe(0)
    expect(store.packages[0].id).toBe(77)
  })

  it('importPackage valid 且无 manifest 时 version 回退 1.0', async () => {
    const result = {
      package_id: 88,
      package_code: 'PKG-NO-MANIFEST',
      status: 'validated',
      validation: { is_valid: true },
    }
    mockImportDataPackage.mockResolvedValueOnce(result)
    await store.importPackage(new File([], 'no-manifest.zip'), 2)
    expect(store.packages[0].org_id).toBe(2)
    expect(store.packages[0].version).toBe('1.0')
  })

  it('previewPackage 成功时填充 previewData', async () => {
    const data = [{ id: 1, value: 'x' }]
    mockPreviewDataPackage.mockResolvedValueOnce(data)
    await store.previewPackage(1)
    expect(store.previewData).toEqual(data)
  })

  it('confirmImport 成功时更新 status=imported', async () => {
    store.packages = [{ id: 1, status: 'validated' } as any]
    mockConfirmImport.mockResolvedValueOnce({ success: true })
    await store.confirmImport(1, {})
    expect(store.packages[0].status).toBe('imported')
  })

  it('confirmImport 失败时 packages 状态不变', async () => {
    store.packages = [{ id: 1, status: 'validated' } as any]
    mockConfirmImport.mockResolvedValueOnce({ success: false })
    await store.confirmImport(1, {})
    expect(store.packages[0].status).toBe('validated')
  })

  it('deletePackage 成功时从 packages 移除', async () => {
    store.packages = [{ id: 1 } as any, { id: 2 } as any]
    mockDeleteDataPackage.mockResolvedValueOnce({})
    await store.deletePackage(1, 'reason')
    expect(store.packages).toHaveLength(1)
    expect(store.packages[0].id).toBe(2)
  })

  it('deletePackage 成功时清除 currentPackage (如果 ID 匹配)', async () => {
    store.currentPackage = { id: 1 } as any
    store.packages = [{ id: 1 } as any]
    mockDeleteDataPackage.mockResolvedValueOnce({})
    await store.deletePackage(1)
    expect(store.currentPackage).toBeNull()
  })

  it('setCurrentPackage 设置值', () => {
    const pkg = { id: 5 } as any
    store.setCurrentPackage(pkg)
    expect(store.currentPackage).toEqual(pkg)
    store.setCurrentPackage(null)
    expect(store.currentPackage).toBeNull()
  })

  it('clearImportResult 清空 importResult', () => {
    store.importResult = { x: 1 } as any
    store.clearImportResult()
    expect(store.importResult).toBeNull()
  })

  it('clearExportResult 清空 exportResult', () => {
    store.exportResult = { y: 1 } as any
    store.clearExportResult()
    expect(store.exportResult).toBeNull()
  })

  it('clearPreviewData 清空 previewData', () => {
    store.previewData = [{ x: 1 }] as any
    store.clearPreviewData()
    expect(store.previewData).toEqual([])
  })

  it('clearError 清空 error', () => {
    store.error = 'something'
    store.clearError()
    expect(store.error).toBeNull()
  })

  it('$reset 重置所有 state', () => {
    store.packages = [{ id: 1 }] as any
    store.error = 'x'
    store.total = 5
    store.$reset()
    expect(store.packages).toEqual([])
    expect(store.error).toBeNull()
    expect(store.total).toBe(0)
  })

  it('fetchPackage 失败时设置 error + 抛出', async () => {
    mockGetDataPackage.mockRejectedValueOnce(new Error('pkg boom'))
    await expect(store.fetchPackage(5)).rejects.toThrow('pkg boom')
    expect(store.error).toBe('pkg boom')
    expect(store.loading).toBe(false)
  })

  it('exportPackage 失败时设置 error + 抛出', async () => {
    mockExportDataPackage.mockRejectedValueOnce(new Error('export boom'))
    await expect(store.exportPackage({ org_id: 1 } as any)).rejects.toThrow('export boom')
    expect(store.error).toBe('export boom')
    expect(store.exporting).toBe(false)
  })

  it('importPackage 失败时设置 error + 抛出', async () => {
    mockImportDataPackage.mockRejectedValueOnce(new Error('import boom'))
    await expect(store.importPackage(new File([], 'x.zip'))).rejects.toThrow('import boom')
    expect(store.error).toBe('import boom')
    expect(store.importing).toBe(false)
  })

  it('previewPackage 失败时设置 error + 抛出', async () => {
    mockPreviewDataPackage.mockRejectedValueOnce(new Error('preview boom'))
    await expect(store.previewPackage(1)).rejects.toThrow('preview boom')
    expect(store.error).toBe('preview boom')
    expect(store.loading).toBe(false)
  })

  it('confirmImport 失败时设置 error + 抛出且状态不变', async () => {
    store.packages = [{ id: 1, status: 'validated' } as any]
    mockConfirmImport.mockRejectedValueOnce(new Error('confirm boom'))
    await expect(store.confirmImport(1, {})).rejects.toThrow('confirm boom')
    expect(store.error).toBe('confirm boom')
    expect(store.packages[0].status).toBe('validated')
  })

  it('confirmImport 成功但 pkg 不在列表时仅返回结果', async () => {
    mockConfirmImport.mockResolvedValueOnce({ success: true })
    const result = await store.confirmImport(999, {})
    expect(result).toEqual({ success: true })
    expect(store.packages).toEqual([])
  })

  it('downloadPackage 成功时创建下载链接', async () => {
    const createObjectURL = vi.fn(() => 'blob:mock')
    const revokeObjectURL = vi.fn()
    ;(window.URL as any).createObjectURL = createObjectURL
    ;(window.URL as any).revokeObjectURL = revokeObjectURL
    const link = document.createElement('a')
    link.click = vi.fn()
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: any) =>
      tag === 'a' ? link : realCreate(tag)
    )
    store.packages = [{ id: 1, file_name: 'pkg-1.zip' } as any]
    mockDownloadDataPackage.mockResolvedValueOnce(new Blob(['x']))
    await store.downloadPackage(1)
    expect(createObjectURL).toHaveBeenCalled()
    expect(link.download).toBe('pkg-1.zip')
    expect(link.click).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalled()
    expect(store.loading).toBe(false)
  })

  it('downloadPackage 无 file_name 时使用默认文件名', async () => {
    const createObjectURL = vi.fn(() => 'blob:mock')
    const revokeObjectURL = vi.fn()
    ;(window.URL as any).createObjectURL = createObjectURL
    ;(window.URL as any).revokeObjectURL = revokeObjectURL
    const link = document.createElement('a')
    link.click = vi.fn()
    const realCreate = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: any) =>
      tag === 'a' ? link : realCreate(tag)
    )
    mockDownloadDataPackage.mockResolvedValueOnce(new Blob(['x']))
    await store.downloadPackage(7)
    expect(link.download).toBe('package_7.zip')
  })

  it('downloadPackage 失败时设置 error + 抛出', async () => {
    mockDownloadDataPackage.mockRejectedValueOnce(new Error('dl boom'))
    await expect(store.downloadPackage(1)).rejects.toThrow('dl boom')
    expect(store.error).toBe('dl boom')
    expect(store.loading).toBe(false)
  })

  it('deletePackage 失败时设置 error + 抛出', async () => {
    store.packages = [{ id: 1 } as any]
    mockDeleteDataPackage.mockRejectedValueOnce(new Error('del boom'))
    await expect(store.deletePackage(1)).rejects.toThrow('del boom')
    expect(store.error).toBe('del boom')
    expect(store.packages).toHaveLength(1)
    expect(store.loading).toBe(false)
  })

  it('deletePackage 成功但 currentPackage 非该 id 时不清除', async () => {
    store.currentPackage = { id: 2 } as any
    store.packages = [{ id: 1 } as any]
    mockDeleteDataPackage.mockResolvedValueOnce({})
    await store.deletePackage(1)
    expect(store.currentPackage).toEqual({ id: 2 })
  })
})

describe('zzz-final: common/StatsCard.vue', () => {
  it('renders title, numeric value with prefix/suffix, subtitle and trend up', () => {
    const wrapper = mount(StatsCard, {
      props: { title: '总经费', value: 1234, prefix: '¥', suffix: '元', subtitle: '今年', trend: 5 },
    })
    expect(wrapper.text()).toContain('总经费')
    expect(wrapper.text()).toContain('¥1,234元')
    expect(wrapper.text()).toContain('今年')
    expect(wrapper.find('.stats-card__trend--up').exists()).toBe(true)
    expect(wrapper.find('.stats-card__trend').text()).toBe('+5%')
  })

  it('renders trend down with minus sign', () => {
    const wrapper = mount(StatsCard, { props: { title: 'T', value: 1, trend: -3 } })
    expect(wrapper.find('.stats-card__trend--down').exists()).toBe(true)
    expect(wrapper.find('.stats-card__trend').text()).toBe('-3%')
  })

  it('renders no trend when trend is undefined', () => {
    const wrapper = mount(StatsCard, { props: { title: 'T', value: 1 } })
    expect(wrapper.find('.stats-card__trend').exists()).toBe(false)
  })

  it('renders string value as-is', () => {
    const wrapper = mount(StatsCard, { props: { title: 'T', value: '1,234' } })
    expect(wrapper.find('.stats-card__value').text()).toBe('1,234')
  })

  it('renders icon component and type class', () => {
    const wrapper = mount(StatsCard, {
      props: { title: 'T', value: 1, icon: DummyIcon, type: 'success' },
      global: { stubs },
    })
    expect(wrapper.find('.dummy-icon').exists()).toBe(true)
    expect(wrapper.classes()).toContain('stats-card--success')
  })

  it('renders without subtitle', () => {
    const wrapper = mount(StatsCard, { props: { title: 'T', value: 1 } })
    expect(wrapper.find('.stats-card__subtitle').exists()).toBe(false)
  })
})

describe('zzz-final: sanitize', () => {
  describe('sanitizeHtml', () => {
    it('空字符串返回空字符串', () => {
      expect(sanitizeHtml('')).toBe('')
    })

    it('null/undefined/数字 返回空字符串', () => {
      expect(sanitizeHtml(null as any)).toBe('')
      expect(sanitizeHtml(undefined as any)).toBe('')
      expect(sanitizeHtml(123 as any)).toBe('')
    })

    it('保留允许的标签 (p, b, strong)', () => {
      const html = '<p>hello <b>world</b></p>'
      const result = sanitizeHtml(html)
      expect(result).toContain('<p>')
      expect(result).toContain('<b>')
    })

    it('移除 script 标签', () => {
      const html = '<p>safe</p><script>alert(1)</script>'
      const result = sanitizeHtml(html)
      expect(result).not.toContain('<script>')
      expect(result).not.toContain('alert(1)')
    })

    it('移除 onclick 等事件属性', () => {
      const html = '<p onclick="alert(1)">click me</p>'
      const result = sanitizeHtml(html)
      expect(result).not.toContain('onclick')
    })

    it('移除 javascript: 链接', () => {
      const html = '<a href="javascript:alert(1)">click</a>'
      const result = sanitizeHtml(html)
      expect(result).not.toContain('javascript:')
    })

    it('移除 data: 链接', () => {
      const html = '<a href="data:text/html,<script>alert(1)</script>">x</a>'
      const result = sanitizeHtml(html)
      expect(result).not.toContain('data:text/html')
    })

    it('保留正常 https 链接 + target=_blank + rel=noopener', () => {
      const html = '<a href="https://example.com">link</a>'
      const result = sanitizeHtml(html)
      expect(result).toContain('href="https://example.com"')
      expect(result).toContain('target="_blank"')
      expect(result).toContain('rel="noopener noreferrer"')
    })

    it('内部 # 链接不加 target', () => {
      const html = '<a href="#section">section</a>'
      const result = sanitizeHtml(html)
      expect(result).toContain('href="#section"')
      expect(result).not.toContain('target="_blank"')
    })

    it('内部 / 路径不加 target', () => {
      const html = '<a href="/page">page</a>'
      const result = sanitizeHtml(html)
      expect(result).not.toContain('target="_blank"')
    })
  })

  describe('stripHtml', () => {
    it('空字符串返回空字符串', () => {
      expect(stripHtml('')).toBe('')
    })

    it('null/undefined 返回空字符串', () => {
      expect(stripHtml(null as any)).toBe('')
      expect(stripHtml(undefined as any)).toBe('')
    })

    it('纯文本直接返回', () => {
      expect(stripHtml('hello world')).toBe('hello world')
    })

    it('移除所有 HTML 标签但保留文本', () => {
      expect(stripHtml('<p>hello <b>world</b></p>')).toContain('hello')
      expect(stripHtml('<p>hello <b>world</b></p>')).toContain('world')
    })

    it('完全移除 script 标签', () => {
      expect(stripHtml('<script>alert(1)</script>')).not.toContain('alert(1)')
    })
  })

  describe('escapeHtml', () => {
    it('空字符串返回空字符串', () => {
      expect(escapeHtml('')).toBe('')
    })

    it('null/undefined 返回空字符串', () => {
      expect(escapeHtml(null as any)).toBe('')
      expect(escapeHtml(undefined as any)).toBe('')
    })

    it('转义 < > & " \'', () => {
      expect(escapeHtml('<script>')).toBe('&lt;script&gt;')
      expect(escapeHtml('&')).toBe('&amp;')
      expect(escapeHtml('"hello"')).toBe('&quot;hello&quot;')
      expect(escapeHtml("it's")).toBe('it&#39;s')
    })

    it('混合文本正确转义', () => {
      const text = `<a href="evil">x & y</a>`
      const result = escapeHtml(text)
      expect(result).toContain('&lt;')
      expect(result).toContain('&gt;')
      expect(result).toContain('&quot;')
      expect(result).toContain('&amp;')
    })

    it('无特殊字符时不变', () => {
      expect(escapeHtml('hello world')).toBe('hello world')
    })
  })

  describe('危险协议补充（hook 分支）', () => {
    it('vbscript: / file: 协议被移除', () => {
      expect(sanitizeHtml('<a href="vbscript:msgbox(1)">x</a>')).not.toContain('vbscript:')
      expect(sanitizeHtml('<a href="file:///etc/passwd">x</a>')).not.toContain('file:')
    })

    it('协议大小写混合同样被拦截', () => {
      expect(sanitizeHtml('<a href="JaVaScRiPt:alert(1)">x</a>')).not.toContain('JaVaScRiPt')
      expect(sanitizeHtml('<a href="JaVaScRiPt:alert(1)">x</a>')).not.toContain('href=')
    })

    it('带前导空格的危险协议（DOMPurify 放行，自定义 hook 拦截）', () => {
      const a = sanitizeHtml('<a href=" file:///etc/passwd">x</a>')
      expect(a).not.toContain('href')
      const b = sanitizeHtml('<a href=" javascript:alert(1)">x</a>')
      expect(b).not.toContain('href')
      const c = sanitizeHtml('<img src=" vbscript:msgbox(1)" alt="i">')
      expect(c).not.toContain('src=')
    })

    it('img src data: URI（DOMPurify 默认放行 data URI 标签）被自定义 hook 移除', () => {
      const r = sanitizeHtml('<img src="data:image/png;base64,iVBORw0KGgo=" alt="x">')
      expect(r).not.toContain('src=')
    })

    it('img src 危险协议移除、正常 src 保留', () => {
      const evil = sanitizeHtml('<img src="javascript:alert(1)" alt="x">')
      expect(evil).not.toContain('javascript:')
      const ok = sanitizeHtml('<img src="/static/a.png" alt="y">')
      expect(ok).toContain('/static/a.png')
    })

    it('无 href 的 a 标签只加 rel，不加 target', () => {
      const r = sanitizeHtml('<a>plain</a>')
      expect(r).toContain('rel="noopener noreferrer"')
      expect(r).not.toContain('target="_blank"')
    })

    it('外部链接（非 # 非 /）加 target=_blank', () => {
      expect(sanitizeHtml('<a href="https://example.com/x">x</a>')).toContain(
        'target="_blank"'
      )
    })
  })

  describe('stripHtml 兜底分支', () => {
    it('无可见文本时 textContent 为空 → innerText 兜底，不抛错', () => {
      const r = stripHtml('<div></div>')
      expect(r).toBeFalsy()
    })
  })

  describe('default export', () => {
    it('包含三个函数', () => {
      expect(typeof sanitizeDefault.sanitizeHtml).toBe('function')
      expect(typeof sanitizeDefault.stripHtml).toBe('function')
      expect(typeof sanitizeDefault.escapeHtml).toBe('function')
      expect(sanitizeDefault.sanitizeHtml('<script>x</script>')).not.toContain('<script>')
      expect(sanitizeDefault.stripHtml('<b>t</b>')).toContain('t')
      expect(sanitizeDefault.escapeHtml('<')).toBe('&lt;')
    })
  })
})
