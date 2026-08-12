import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { useMessageNotification } from '@/composables/useMessageNotification'

vi.mock('@/api/message', () => ({
  getUnreadCount: vi.fn(),
}))

vi.mock('@/api/request', () => ({
  get: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

import { getUnreadCount } from '@/api/message'
import { get } from '@/api/request'

;(globalThis as any).window.electronAPI = undefined

/** 挂载组件触发 onMounted（内部闭包仅能通过计时器驱动） */
function mountNotifier() {
  const Comp = defineComponent({
    setup() {
      useMessageNotification()
      return () => h('div')
    },
  })
  return mount(Comp, { attachTo: document.body })
}

/** 安装 Notification 桩，返回 ctor spy */
function stubNotification(opts: {
  permission?: string
  requestPermission?: () => Promise<void>
  ctorImpl?: () => void
} = {}) {
  class FakeNotification {
    static permission: string = opts.permission ?? 'granted'
    static requestPermission: () => Promise<void> =
      opts.requestPermission ?? vi.fn().mockResolvedValue(undefined)
    title: string
    options: any
    constructor(title: string, options: any) {
      this.title = title
      this.options = options
      if (opts.ctorImpl) opts.ctorImpl()
    }
  }
  ;(globalThis as any).Notification = FakeNotification
  return FakeNotification
}

describe('composables/useMessageNotification', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    stubNotification()
    localStorage.clear()
    delete (window as any).electronAPI
  })
  afterEach(() => {
    vi.useRealTimers()
    delete (globalThis as any).Notification
    delete (window as any).electronAPI
  })

  it('exposes function (Vue composable, requires app context)', () => {
    expect(typeof useMessageNotification).toBe('function')
  })

  it('getUnreadCount 可调用 (mock)', async () => {
    ;(getUnreadCount as any).mockResolvedValue(5)
    const r = await getUnreadCount()
    expect(r).toBe(5)
  })

  it('getUnreadCount 失败被 catch', async () => {
    ;(getUnreadCount as any).mockRejectedValue(new Error('net'))
    await expect(getUnreadCount()).rejects.toThrow('net')
  })

  describe('requestPermission（挂载时）', () => {
    it('permission=default 时请求权限', async () => {
      const requestSpy = vi.fn().mockResolvedValue(undefined)
      stubNotification({ permission: 'default', requestPermission: requestSpy })
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(0)
      expect(requestSpy).toHaveBeenCalledTimes(1)
      w.unmount()
    })

    it('requestPermission 被拒绝时静默（catch 分支）', async () => {
      const requestSpy = vi.fn().mockRejectedValue(new Error('denied'))
      stubNotification({ permission: 'default', requestPermission: requestSpy })
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(0)
      expect(requestSpy).toHaveBeenCalledTimes(1)
      w.unmount()
    })

    it('permission=granted 时不请求', async () => {
      const requestSpy = vi.fn().mockResolvedValue(undefined)
      stubNotification({ permission: 'granted', requestPermission: requestSpy })
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(0)
      expect(requestSpy).not.toHaveBeenCalled()
      w.unmount()
    })

    it('无 Notification API 时静默跳过', async () => {
      delete (globalThis as any).Notification
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(0)
      w.unmount()
    })
  })

  describe('checkMessages（5s 首查 + 60s 轮询）', () => {
    it('count > lastUnread → Electron 通知 + 托盘角标', async () => {
      const showNotification = vi.fn()
      const updateTrayUnread = vi.fn()
      ;(window as any).electronAPI = { showNotification, updateTrayUnread }
      ;(getUnreadCount as any).mockResolvedValue(3)
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(5000)
      expect(showNotification).toHaveBeenCalledWith(
        '新消息提醒',
        '您有 3 条新消息，请及时查看。'
      )
      expect(updateTrayUnread).toHaveBeenCalledWith(3)
      w.unmount()
    })

    it('Electron 通知抛错 → 回退 Web Notification', async () => {
      const updateTrayUnread = vi.fn()
      ;(window as any).electronAPI = {
        showNotification: vi.fn(() => {
          throw new Error('electron fail')
        }),
        updateTrayUnread,
      }
      const ctorSpy = vi.fn()
      stubNotification({ ctorImpl: ctorSpy })
      ;(getUnreadCount as any).mockResolvedValue(2)
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(5000)
      expect(ctorSpy).toHaveBeenCalledTimes(1)
      expect(updateTrayUnread).toHaveBeenCalledWith(2)
      w.unmount()
    })

    it('无 electronAPI → Web Notification 发送', async () => {
      const ctorSpy = vi.fn()
      stubNotification({ ctorImpl: ctorSpy })
      ;(getUnreadCount as any).mockResolvedValue(1)
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(5000)
      expect(ctorSpy).toHaveBeenCalledTimes(1)
      w.unmount()
    })

    it('Web Notification 构造抛错 → 静默', async () => {
      const ctorSpy = vi.fn(() => {
        throw new Error('ctor fail')
      })
      stubNotification({ ctorImpl: ctorSpy })
      ;(getUnreadCount as any).mockResolvedValue(1)
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(5000)
      expect(ctorSpy).toHaveBeenCalledTimes(1)
      w.unmount()
    })

    it('updateTrayUnread 抛错 → 静默', async () => {
      const showNotification = vi.fn()
      ;(window as any).electronAPI = {
        showNotification,
        updateTrayUnread: vi.fn(() => {
          throw new Error('tray fail')
        }),
      }
      ;(getUnreadCount as any).mockResolvedValue(3)
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(5000)
      expect(showNotification).toHaveBeenCalledTimes(1)
      w.unmount()
    })

    it('count <= lastUnread → 不再通知', async () => {
      const ctorSpy = vi.fn()
      stubNotification({ ctorImpl: ctorSpy })
      ;(getUnreadCount as any).mockResolvedValue(3)
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(5000)
      expect(ctorSpy).toHaveBeenCalledTimes(1)
      await vi.advanceTimersByTimeAsync(60000)
      expect(ctorSpy).toHaveBeenCalledTimes(1)
      w.unmount()
    })

    it('getUnreadCount 失败 → 静默且无通知', async () => {
      const ctorSpy = vi.fn()
      stubNotification({ ctorImpl: ctorSpy })
      ;(getUnreadCount as any).mockRejectedValue(new Error('net'))
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(5000)
      expect(ctorSpy).not.toHaveBeenCalled()
      w.unmount()
    })

    it('isRunning 重入保护：轮询期间跳过重复执行', async () => {
      const ctorSpy = vi.fn()
      stubNotification({ ctorImpl: ctorSpy })
      let resolveUnread!: (v: number) => void
      ;(getUnreadCount as any).mockImplementation(
        () => new Promise((resolve) => (resolveUnread = resolve))
      )
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(5000) // 首查挂起，isRunning = true
      await vi.advanceTimersByTimeAsync(60000) // 轮询触发 → isRunning 直接返回
      expect(getUnreadCount).toHaveBeenCalledTimes(1)
      resolveUnread(5)
      await vi.advanceTimersByTimeAsync(0)
      expect(ctorSpy).toHaveBeenCalledTimes(1)
      await vi.advanceTimersByTimeAsync(60000) // 下一轮 count=5 → 不再通知
      expect(ctorSpy).toHaveBeenCalledTimes(1)
      w.unmount()
    })
  })

  describe('checkBackupReminder（8s 备份提醒）', () => {
    it('距上次备份 >= 7 天 → 提醒并写入 localStorage', async () => {
      const ctorSpy = vi.fn()
      stubNotification({ ctorImpl: ctorSpy })
      ;(getUnreadCount as any).mockResolvedValue(0)
      ;(get as any).mockResolvedValue({
        lastBackup: new Date(Date.now() - 10 * 86400000).toISOString(),
      })
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(8000)
      expect(get).toHaveBeenCalledWith('/system/backup/stats')
      expect(ctorSpy).toHaveBeenCalledTimes(1)
      expect(localStorage.getItem('backup-reminder-notified')).toBe(
        new Date().toISOString().slice(0, 10)
      )
      w.unmount()
    })

    it('已提醒过（localStorage 去重）→ 不再请求', async () => {
      ;(get as any).mockResolvedValue({
        lastBackup: new Date(Date.now() - 10 * 86400000).toISOString(),
      })
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(8000)
      expect(get).toHaveBeenCalledTimes(1)
      const ctorSpy = vi.fn()
      stubNotification({ ctorImpl: ctorSpy })
      ;(getUnreadCount as any).mockResolvedValue(0)
      const w2 = mountNotifier()
      await vi.advanceTimersByTimeAsync(8000)
      expect(get).toHaveBeenCalledTimes(1)
      expect(ctorSpy).not.toHaveBeenCalled()
      w.unmount()
      w2.unmount()
    })

    it('距上次备份 < 7 天 → 不提醒但标记', async () => {
      const ctorSpy = vi.fn()
      stubNotification({ ctorImpl: ctorSpy })
      ;(getUnreadCount as any).mockResolvedValue(0)
      ;(get as any).mockResolvedValue({
        lastBackup: new Date(Date.now() - 2 * 86400000).toISOString(),
      })
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(8000)
      expect(ctorSpy).not.toHaveBeenCalled()
      expect(localStorage.getItem('backup-reminder-notified')).toBeTruthy()
      w.unmount()
    })

    it('lastBackup 缺失 → 静默返回', async () => {
      ;(get as any).mockResolvedValue({})
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(8000)
      expect(localStorage.getItem('backup-reminder-notified')).toBeNull()
      w.unmount()
    })

    it('lastBackup 非法日期 → 静默返回', async () => {
      ;(get as any).mockResolvedValue({ lastBackup: 'not-a-date' })
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(8000)
      expect(localStorage.getItem('backup-reminder-notified')).toBeNull()
      w.unmount()
    })

    it('get 失败 → 静默且不标记', async () => {
      ;(get as any).mockRejectedValue(new Error('net'))
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(8000)
      expect(localStorage.getItem('backup-reminder-notified')).toBeNull()
      w.unmount()
    })

    it('后端返回 {success, data:{lastBackup}} 内层结构 → 正常提醒', async () => {
      const ctorSpy = vi.fn()
      stubNotification({ ctorImpl: ctorSpy })
      ;(getUnreadCount as any).mockResolvedValue(0)
      ;(get as any).mockResolvedValue({
        success: true,
        data: { lastBackup: new Date(Date.now() - 8 * 86400000).toISOString() },
      })
      const w = mountNotifier()
      await vi.advanceTimersByTimeAsync(8000)
      expect(ctorSpy).toHaveBeenCalledTimes(1)
      w.unmount()
    })
  })

  describe('卸载清理', () => {
    it('onUnmounted 清理 initTimer 与 interval', async () => {
      ;(getUnreadCount as any).mockResolvedValue(0)
      const w = mountNotifier()
      w.unmount()
      await vi.advanceTimersByTimeAsync(200000)
      expect(getUnreadCount).not.toHaveBeenCalled()
    })
  })
})
