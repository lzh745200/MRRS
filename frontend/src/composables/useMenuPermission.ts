import { useMenuStore } from '@/stores/menu'

/**
 * 菜单级权限检查（ADR-0007 / W3-T1 / 工单042）
 *
 * 接入真实菜单权限源（menu store 的 canAccessMenu），
 * 与路由守卫、v-permission="{ menu }" 指令共用同一判定。
 */
export function useMenuPermission() {
  const menuStore = useMenuStore()
  const hasPermission = (menuKey: string) => {
    if (!menuKey) return true
    return menuStore.canAccessMenu(menuKey)
  }
  return { hasPermission }
}
