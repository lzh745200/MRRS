/**
 * 路由守卫 — 认证 + 菜单权限双重校验
 */
import router from './index'
import { AuthStorage } from '@/utils/authStorage'
import { ADMIN_ROLES, normalizeRole } from '@/utils/roleAccess'
import { useMenuStore } from '@/stores/menu'

const whiteList = ['/login', '/register', '/forgot-password']
// 强制改密期间允许访问的路由
const changePasswordWhitelist = ['/change-password', '/logout']

/**
 * 读取锁屏标记（自动/手动锁屏置 '1'，登录成功后由 authStore.unlockSession 清除）。
 *
 * fail-closed：读取失败（隐私模式/配额/SecurityError）时按"已锁定"处理——
 * 这是一处安全判定，异常时宁可要求重新输密码，也不能静默放行。
 */
function readLockFlag(): boolean {
  try {
    return sessionStorage.getItem('auto_lock_active') === '1'
  } catch {
    return true
  }
}

export const routeGuard = async (to: any, _from: any, next: any) => {
  document.title = (to.meta?.title as string) || '帮扶管理信息系统'

  // 公开路由直接放行
  if (to.meta?.noAuth === true) {
    next()
    return
  }

  const token = AuthStorage.getToken()
  const locked = readLockFlag()

  // 已登录（含"记住登录"持久令牌）访问登录/注册页 → 直接进入工作台，实现免登录；
  // 但锁屏标记存在时（自动/手动锁屏）必须重新输入密码，不允许自动跳回。
  if (whiteList.includes(to.path)) {
    if (token && !locked) {
      next('/dashboard')
      return
    }
    next()
    return
  }

  // 未登录 → 登录页
  if (!token) {
    next(`/login?redirect=${to.path}`)
    return
  }

  // ── 锁屏收口（安全修复）──
  // token 可能来自"记住登录"的持久令牌回退链（AuthStorage.getToken 的
  // session → PERSIST_TOKEN → legacy 三级回退），原实现只在白名单分支读锁屏标记，
  // 于是锁屏后直接在地址栏输入 /dashboard、点书签或按后退，都能带着旧 token
  // 进入受保护页面，锁屏形同虚设。此处对所有非白名单路由统一校验。
  if (locked) {
    next(`/login?redirect=${to.path}`)
    return
  }

  // 强制改密检查：must_change_password=true 时只能访问改密页
  const user = AuthStorage.getUser() as Record<string, any> | null
  if (user?.must_change_password === true && !changePasswordWhitelist.includes(to.path)) {
    next('/change-password')
    return
  }

  // 角色权限检查：meta.roles 非空时校验用户角色（存量旧角色名先归一化）
  const requiredRoles = to.meta?.roles as string[] | undefined
  if (requiredRoles && requiredRoles.length > 0) {
    const userRole = normalizeRole(user?.role)
    const hasAccess = ADMIN_ROLES.includes(userRole) || requiredRoles.includes(userRole)
    if (!hasAccess) {
      next('/403')
      return
    }
  }

  // 菜单权限检查：确保菜单已加载，然后根据路由 meta.menuKey 检查可见性
  const menuKey = to.meta?.menuKey as string | undefined
  if (menuKey) {
    const menuStore = useMenuStore()
    // 首次访问时加载菜单
    if (!menuStore.loaded) {
      await menuStore.fetchMenus()
    }
    // 仅在菜单已加载且明确不含该键时才 403。
    // 菜单加载失败（打包版后端冷启动期/接口异常）时不阻断导航：
    // 菜单只是可见性层，真实权限由后端接口兜底，否则启动窗口期全站被弹到 /403。
    if (menuStore.loaded && !menuStore.canAccessMenu(menuKey)) {
      next('/403')
      return
    }
  }

  next()
}

router.beforeEach(routeGuard)

export default router
