/**
 * v-watermark 指令
 * 在容器元素上叠加文字水印（防截图泄密）
 *
 * 用法: <div v-watermark="'张三 2024-01-01'">...</div>
 * 或:   <div v-watermark>...</div>  (自动使用当前用户名+日期)
 */
import type { Directive, DirectiveBinding } from 'vue'
import { AuthStorage } from '@/utils/authStorage'

function createWatermark(el: HTMLElement, text: string) {
  // 移除旧水印
  const old = el.querySelector('.watermark-layer') as HTMLElement | null
  if (old) old.remove()

  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  canvas.width = 300
  canvas.height = 200

  ctx.rotate((-20 * Math.PI) / 180)
  ctx.font = '14px Microsoft YaHei'
  ctx.fillStyle = 'rgba(180, 180, 180, 0.15)'
  ctx.textAlign = 'center'
  ctx.fillText(text, 100, 120)

  const watermarkDiv = document.createElement('div')
  watermarkDiv.className = 'watermark-layer'
  watermarkDiv.style.cssText = `
    position: absolute; top: 0; left: 0; width: 100%; height: 100%;
    pointer-events: none; z-index: 9999;
    background-image: url(${canvas.toDataURL('image/png')});
    background-repeat: repeat;
  `

  // 仅当宿主原本没有 position 时才写入，并记录"position 由本指令写入"，
  // 以便卸载时复原（否则宿主被复用/重挂载时叠加多个水印层或残留定位）。
  if (!el.style.position) {
    el.style.position = 'relative'
    el.dataset.watermarkPosition = '1'
  }
  el.appendChild(watermarkDiv)
}

/** 移除水印层并复原由本指令写入的 position（重挂载/卸载时调用） */
function removeWatermark(el: HTMLElement): void {
  el.querySelector('.watermark-layer')?.remove()
  if (el.dataset.watermarkPosition === '1') {
    el.style.position = ''
    delete el.dataset.watermarkPosition
  }
}

function getDefaultText(): string {
  try {
    const user = AuthStorage.getUser()
    if (user) {
      const name = user.name || user.username || '用户'
      return `${name} ${new Date().toLocaleDateString('zh-CN')}`
    }
  } catch {
    /* ignore */
  }
  return `内部系统 ${new Date().toLocaleDateString('zh-CN')}`
}

export const vWatermark: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    const text = binding.value || getDefaultText()
    createWatermark(el, text)
  },
  updated(el: HTMLElement, binding: DirectiveBinding) {
    const text = binding.value || getDefaultText()
    createWatermark(el, text)
  },
  // 宿主销毁必须清理水印层：水印 DOM 直接 append 在 Vue 管理的元素内，
  // 不清理会在元素复用/重挂载时重复叠加（内存与视觉双重泄漏）。
  unmounted(el: HTMLElement) {
    removeWatermark(el)
  },
}

export default vWatermark
