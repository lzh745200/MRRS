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

export const routeGuard = async (to: any, _from: any, next: any) => {
  document.title = (to.meta?.title as string) || '帮扶管理信息系统'

  // 公开路由直接放行
  if (to.meta?.noAuth === true) {
    next()
    return
  }

  const token = AuthStorage.getToken()

  // 已登录（含"记住登录"持久令牌）访问登录/注册页 → 直接进入工作台，实现免登录；
  // 但锁屏标记存在时（自动/手动锁屏）必须重新输入密码，不允许自动跳回。
  if (whiteList.includes(to.path)) {
    let locked = false
    try {
      locked = sessionStorage.getItem('auto_lock_active') === '1'
    } catch {
      /* 静默 */
    }
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
