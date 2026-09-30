import { useRouter } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'

import { logger } from '@/utils/logger'

function getPathString(path: string | RouteLocationRaw): string | undefined {
  return typeof path === 'string' ? path : path.path
}

/** 原生跳转目标非法时的安全回退路径（应用首页，同源相对路径） */
export const SAFE_LOCATION_FALLBACK = '/'

/**
 * 把原生跳转目标收敛为**同源相对路径**，防止开放重定向与脚本协议执行。
 *
 * `window.location.href = pathString` 会把调用方传入的字符串当**完整 URL** 解析，
 * 而该字符串常来自 `?redirect=` 等用户可控来源：
 *   - `//evil.com/x` / `/\evil.com/x` / `\\evil.com/x` → 协议相对地址，跳出本系统
 *   - `https://evil.com/x` → 带协议的外部地址
 *   - `javascript:...` / `data:text/html,...` → 在当前文档上下文执行脚本
 *   - `java\tscript:...` → 浏览器解析 URL 前会剥离制表/换行，等价于上面的脚本协议
 *
 * @param path - 原始跳转目标
 * @param fallback - 目标非法时的回退路径，默认首页
 */
export function toSafeLocationHref(
  path: string,
  fallback: string = SAFE_LOCATION_FALLBACK
): string {
  // 先按 URL 规范剥离控制字符（含 \t \n \r）与首尾空白，
  // 否则 "java\tscript:" 之类的变形会绕过下面的协议判定
  const cleaned = String(path ?? '')
    // eslint-disable-next-line no-control-regex -- 控制字符白名单即本守卫的目的：必须逐码点剥离
    .replace(/[\u0000-\u001f\u007f]/g, '')
    .trim()
  if (!cleaned) return fallback
  // 以反斜杠开头或前两位均为斜杠类字符：浏览器按 URL 规范解析为"协议相对地址"（外站域名）
  if (cleaned.startsWith('\\') || /^[\\/]{2}/.test(cleaned)) return fallback
  // 带协议前缀（javascript: / data: / http: / https: ...）：一律拒绝，只放行同源相对路径
  if (/^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(cleaned)) return fallback
  return cleaned
}

/**
 * 判定 vue-router 的 NavigationFailure（守卫中止 / 取消 / 重复导航）。
 *
 * 不直接 import isNavigationFailure：仓内大量视图测试用局部 factory mock 掉
 * 'vue-router'（只提供 useRouter），import 绑定会是 undefined，调用即抛。
 * NavigationFailure 由 createRouterError 构造 —— Error + 数字 type + from/to。
 */
export function isNavigationFailureLike(err: unknown): boolean {
  if (!(err instanceof Error)) return false
  const typed = err as { type?: unknown; from?: unknown; to?: unknown }
  return typeof typed.type === 'number' && typed.from !== undefined && typed.to !== undefined
}

/**
 * 安全解析路由参数为数字。
 * 解决 `Number(undefined)` → `NaN` 导致 API 请求 `/api/xxx/NaN` 的问题。
 *
 * @param value - 路由参数值（string | string[] | undefined）
 * @param fallback - 参数无效时的回退值，默认 0
 */
export function safeRouteParam(value: unknown, fallback = 0): number {
  if (value === undefined || value === null) return fallback
  if (Array.isArray(value)) value = value[0]
  if (value === null || value === undefined) return fallback
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

/**
 * 安全的路由导航工具
 * 提供带错误处理和回退机制的路由跳转功能
 */
export function useRouterSafe() {
  const router = useRouter()

  /**
   * 安全地跳转到指定路由
   * 如果 Vue Router 跳转失败，会回退到原生页面跳转
   *
   * @param path - 目标路由路径或路由对象
   * @param debugLabel - 可选的调试标签，仅在开发环境输出日志
   */
  const pushSafe = (path: string | RouteLocationRaw, debugLabel?: string) => {
    const pathString = getPathString(path)

    // 防御性检查：目标路由是否在路由表中注册
    if (pathString) {
      const resolved = router.resolve(pathString)
      if (resolved.name === 'NotFound' || resolved.matched.length === 0) {
        console.error(`[pushSafe] 路由不存在: ${pathString}${debugLabel ? ` (${debugLabel})` : ''}`)
        // 内部未知路由 → 走 SPA 内的 404 页面。
        // 原先的 window.location.href 会整页重载、丢弃全部内存态，
        // 重启后前端路由仍解析回同一个 NotFound 页面（纯浪费 + 状态丢失）。
        try {
          router.push({ name: 'NotFound' })?.catch((err: unknown) => {
            console.error('[pushSafe] NotFound 路由不可达，回退原生跳转:', err)
            window.location.href = toSafeLocationHref(pathString)
          })
        } catch (err) {
          console.error('[pushSafe] NotFound 路由不可达，回退原生跳转:', err)
          window.location.href = toSafeLocationHref(pathString)
        }
        return
      }
    }

    try {
      if (debugLabel) {
        // logger.debug 内部已做生产环境门控，无需手写 import.meta.env.DEV 判断
        logger.debug(`尝试跳转到${debugLabel}页面`)
      }

      router.push(path)?.catch((err: unknown) => {
        // 守卫中止/取消/重复导航属正常控制流：记日志后忽略。
        // 一律整页重载会绕过守卫的决定（如未登录被引导到 /login）并丢内存态。
        if (isNavigationFailureLike(err)) {
          logger.debug('[pushSafe] 导航未完成（守卫中止/取消/重复），已忽略:', err)
          return
        }
        console.error('路由跳转失败:', err)
        if (pathString) {
          window.location.href = toSafeLocationHref(pathString)
        }
      })
    } catch (error) {
      console.error('跳转异常:', error)
      if (pathString) {
        window.location.href = toSafeLocationHref(pathString)
      }
    }
  }

  return { pushSafe }
}
