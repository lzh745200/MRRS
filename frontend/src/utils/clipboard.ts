/**
 * 剪贴板操作工具
 */

import { ElMessage } from 'element-plus'

/**
 * 复制文本到剪贴板
 * @param text 要复制的文本
 * @param label 成功提示中的标签（如"机器码"、"校验码"）
 * @returns 是否复制成功
 */
export async function copyToClipboard(text: string, label = '内容'): Promise<boolean> {
  if (!text) return false

  // 优先使用现代 Clipboard API
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text)
      ElMessage.success(`${label}已复制到剪贴板`)
      return true
    } catch (error) {
      console.error('剪贴板写入失败:', error)
    }
  }

  // 降级方案：使用旧版 execCommand
  try {
    const textArea = document.createElement('textarea')
    textArea.value = text
    textArea.style.position = 'fixed'
    textArea.style.left = '-999999px'
    textArea.style.top = '-999999px'
    document.body.appendChild(textArea)
    let copied = false
    try {
      textArea.focus()
      textArea.select()
      // 原实现丢弃 execCommand 的布尔结果并直接提示"已复制"——
      // 复制实际失败时用户被误导。这里以返回值判定成败。
      copied =
        typeof document.execCommand === 'function' ? document.execCommand('copy') === true : false
    } finally {
      // 无论 focus/select/execCommand 是否抛错，临时节点都必须移除（原实现不在 finally，
      // 异常时 textarea 永久残留在 DOM 中）
      textArea.remove()
    }
    if (!copied) {
      ElMessage.error('复制失败，请手动复制')
      return false
    }
    ElMessage.success(`${label}已复制到剪贴板`)
    return true
  } catch (error) {
    console.error('复制失败:', error)
    ElMessage.error('复制失败，请手动复制')
    return false
  }
}

/**
 * 生成随机密码
 * @param length 密码长度，默认12位
 * @returns 随机密码
 */
export function generateRandomPassword(length = 12): string {
  // 排除易混淆字符：I, l, O, 0
  const upper = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
  const lower = 'abcdefghjkmnpqrstuvwxyz'
  const digits = '23456789'
  const special = '!@#$%&*'

  const all = upper + lower + digits + special
  const randomValues = new Uint32Array(length)
  crypto.getRandomValues(randomValues)

  // 先生成随机密码
  let password = ''
  for (let i = 0; i < length; i++) {
    password += all[randomValues[i] % all.length]
  }

  // 确保至少包含每种类型（替换前4位）
  const chars = password.split('')
  const pos = [0, 1, 2, 3].sort(() => (randomValues[0] % 2) - 0.5) // 随机位置
  chars[pos[0] % length] = upper[randomValues[0] % upper.length]
  chars[pos[1] % length] = lower[randomValues[1] % lower.length]
  chars[pos[2] % length] = digits[randomValues[2] % digits.length]
  chars[pos[3] % length] = special[randomValues[3] % special.length]

  return chars.join('')
}

/**
 * 将树形结构扁平化为列表
 * @param tree 树形数据
 * @param childrenKey 子节点字段名，默认 "children"
 * @returns 扁平化后的列表
 */
export function flattenTree<T extends Record<string, any>>(
  tree: T[],
  childrenKey = 'children'
): T[] {
  const result: T[] = []

  function traverse(node: T) {
    result.push(node)
    const children = node[childrenKey]
    if (Array.isArray(children) && children.length > 0) {
      for (const child of children) {
        traverse(child)
      }
    }
  }

  for (const node of tree) {
    traverse(node)
  }

  return result
}
