/**
 * useVersionCheck — 版本指纹校验
 *
 * 应用启动时从服务器获取 /version.json，与本地缓存/当前构建版本比对。
 * 版本不一致 → 提示用户系统已更新 → 破缓存跳转（一次），刷新后的新包
 * 自身版本与服务端一致，此时才写回 localStorage 缓存。
 *
 * 关键语义（2026-09-30 深审修复）：
 * - **不先写缓存再刷新**：先写会让下次比对"相等"，一旦刷新被拦/缓存未破
 *   就永久停留在旧代码且再无检测机会（静默失效）。
 * - 只有"当前运行包版本 === 服务端版本"才落缓存 —— 这是刷新成功的唯一可信判据。
 * - 自动刷新每次会话对同一版本至多一次（sessionStorage 护栏），
 *   避免同一不匹配反复刷新；护栏命中时改为提示人工刷新。
 *
 * Usage (在 App.vue onMounted 中):
 *   import { checkVersion } from '@/composables/useVersionCheck';
 *   onMounted(() => { checkVersion(); });
 */
import { ElMessage } from 'element-plus'
import { SYSTEM_VERSION } from '@/config/constants'

/** localStorage 键名：上次确认一致的服务端版本 */
const VERSION_KEY = 'app_version'

/** sessionStorage 键名：本次会话已为哪个版本自动刷新过（防重复刷新） */
const RELOAD_GUARD_KEY = 'app_version_reload_for'

/** 版本比对后自动刷新的延迟（毫秒） */
const RELOAD_DELAY = 1500

/** 当前运行包的版本（vite 构建期注入，见 config/constants.ts） */
export function getRunningVersion(): string {
  return SYSTEM_VERSION
}

/**
 * 破缓存跳转 URL：reload() 会复用入口 HTML 的 HTTP 缓存，
 * 换一个带版本参数的 URL 才能拿到新的入口与新的资源引用。
 */
function versionedReloadUrl(version: string): string {
  const href = window.location?.href || '/'
  try {
    const url = new URL(href, 'http://localhost')
    url.searchParams.set('_v', version)
    return url.pathname + url.search + url.hash
  } catch {
    // href 畸形（受限环境/测试桩）→ 退回首页带版本参数，仍能破缓存
    return `/?_v=${encodeURIComponent(version)}`
  }
}

/**
 * 检查应用版本是否需要更新。
 * 网络错误时静默跳过，不阻塞应用启动。
 */
export async function checkVersion(): Promise<void> {
  try {
    const response = await fetch(`/version.json?t=${Date.now()}`, {
      cache: 'no-store',
    })

    if (!response.ok) {
      // 404 或其他 HTTP 错误 → 静默跳过（可能 version.json 未部署）
      return
    }

    const data = (await response.json()) as { version?: string }
    const serverVersion = data?.version

    if (!serverVersion) {
      return // version.json 格式不正确
    }

    // 当前运行包就是服务端版本 → 落缓存并清除一次性护栏（本次刷新已生效）
    if (getRunningVersion() === serverVersion) {
      localStorage.setItem(VERSION_KEY, serverVersion)
      sessionStorage.removeItem(RELOAD_GUARD_KEY)
      return
    }

    const cachedVersion = localStorage.getItem(VERSION_KEY)

    if (!cachedVersion) {
      // 首次访问 → 记录版本号，不刷新
      localStorage.setItem(VERSION_KEY, serverVersion)
      return
    }

    if (cachedVersion !== serverVersion) {
      if (sessionStorage.getItem(RELOAD_GUARD_KEY) === serverVersion) {
        // 本会话已为该版本刷新过一次仍不一致（刷新被拦/缓存未破/服务端未换包）
        // → 不再自动刷新，避免死循环，改为提示人工刷新
        ElMessage.warning({
          message: `系统已更新至 v${serverVersion}，自动刷新未生效，请手动刷新页面`,
          duration: 0,
        })
        return
      }
      // 记录一次性护栏（不写 VERSION_KEY：写入后下次比对即相等，将永久停留在旧代码）
      sessionStorage.setItem(RELOAD_GUARD_KEY, serverVersion)
      ElMessage.warning({
        message: `系统已更新至 v${serverVersion}，即将自动刷新...`,
        duration: RELOAD_DELAY,
      })
      setTimeout(() => {
        // 破缓存跳转（绕过入口 HTML 的 HTTP 缓存），而非 location.reload()
        window.location.replace(versionedReloadUrl(serverVersion))
      }, RELOAD_DELAY)
    }
    // 版本一致 → 无需操作
  } catch {
    // 网络错误 → 静默跳过，不阻塞应用
    console.debug('[VersionCheck] /version.json 获取失败，跳过版本检查')
  }
}

export default checkVersion
