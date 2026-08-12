/**
 * 消息通知轮询 — 定期检测未读消息，推送桌面通知
 * 兼容 Electron 桌面模式和纯浏览器模式（麒麟 V10 单机版）
 */
import { onMounted, onUnmounted } from 'vue'
import { get } from '@/api/request'
import { getUnreadCount } from '@/api/message'

const POLL_INTERVAL = 60000 // 每 60 秒轮询一次

export function useMessageNotification() {
  let lastUnread = 0
  let timer: number | null = null
  let isRunning = false

  /** 请求浏览器通知权限（仅首次，静默处理拒绝） */
  const requestPermission = async () => {
    if ('Notification' in window && Notification.permission === 'default') {
      try {
        await Notification.requestPermission()
      } catch {
        // 用户拒绝或浏览器不支持，静默处理
      }
    }
  }

  /**
   * 发送通知：优先 Electron 原生通知，回退到 Web Notification API
   * 确保在 Electron 桌面模式和麒麟浏览器模式下均可正常工作
   */
  const showNotification = (title: string, body: string) => {
    // 方式 1: Electron 桌面通知（如果可用）
    const electronAPI = (window as any).electronAPI
    if (electronAPI?.showNotification) {
      try {
        electronAPI.showNotification(title, body)
        return
      } catch {
        // Electron 通知失败，回退到 Web API
      }
    }

    // 方式 2: Web Notification API（浏览器模式 / 麒麟单机版）
    if ('Notification' in window && Notification.permission === 'granted') {
      try {
        new Notification(title, { body, icon: '/favicon.ico' })
      } catch {
        // 某些浏览器环境（如 iframe 受限上下文）不支持 new Notification，静默
      }
    }
  }

  const checkMessages = async () => {
    if (isRunning) return
    isRunning = true
    try {
      const count = await getUnreadCount()
      if (count > lastUnread) {
        const newCount = count - lastUnread
        showNotification('新消息提醒', `您有 ${newCount} 条新消息，请及时查看。`)
      }
      lastUnread = count
      // Electron 托盘未读角标
      const electronAPI = (window as any).electronAPI
      if (electronAPI?.updateTrayUnread) {
        try {
          electronAPI.updateTrayUnread(count)
        } catch {
          /* 静默 */
        }
      }
    } catch {
      // 网络不可用时静默失败
    } finally {
      isRunning = false
    }
  }

  /** 备份到期提醒：距上次备份超过 N 天时提醒一次（每天至多一次，localStorage 去重） */
  const REMINDER_STORAGE_KEY = 'backup-reminder-notified'
  const checkBackupReminder = async () => {
    try {
      const today = new Date().toISOString().slice(0, 10)
      if (localStorage.getItem(REMINDER_STORAGE_KEY) === today) return
      const res = await get<any>('/system/backup/stats')
      // 后端返回 {success, data: {lastBackup, ...}}——兼容内层与顶层两种结构
      const lastBackup = res?.data?.lastBackup ?? res?.lastBackup
      if (!lastBackup) return
      const lastTs = new Date(lastBackup).getTime()
      if (Number.isNaN(lastTs)) return
      const days = Math.floor((Date.now() - lastTs) / 86400000)
      if (days >= 7) {
        showNotification('备份提醒', `距上次备份已 ${days} 天，建议立即备份到 U 盘以防数据丢失。`)
      }
      localStorage.setItem(REMINDER_STORAGE_KEY, today)
    } catch {
      // 网络不可用时静默
    }
  }

  let initTimer: number | null = null
  let backupTimer: number | null = null

  onMounted(() => {
    requestPermission()
    // 延迟首次检查，避免与登录请求竞争
    initTimer = window.setTimeout(checkMessages, 5000)
    timer = window.setInterval(checkMessages, POLL_INTERVAL)
    // 备份提醒：首次挂载时检查一次
    backupTimer = window.setTimeout(checkBackupReminder, 8000)
  })

  onUnmounted(() => {
    if (initTimer) {
      clearTimeout(initTimer)
      initTimer = null
    }
    if (backupTimer) {
      clearTimeout(backupTimer)
      backupTimer = null
    }
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  })
}
