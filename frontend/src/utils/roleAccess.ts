/**
 * 统一角色访问控制工具
 * 用于菜单可见性与权限门槛判断，避免各组件重复实现。
 */

import { AuthStorage } from './authStorage'

/** 管理员角色列表（唯一来源） */
export const ADMIN_ROLES: readonly string[] = ['admin', 'super_admin']

/** 旧角色 → 新角色归一化映射（与后端 constants.normalize_role 一致） */
const ROLE_NORMALIZE_MAP: Record<string, string> = {
  approval_leader: 'admin',
  manager: 'admin',
  operator: 'user',
}

/** 角色优先级（数字越小权限越高） */
export const ROLE_PRIORITY: Record<string, number> = {
  super_admin: 0,
  admin: 1,
  user: 2,
  viewer: 3,
  // 旧角色兼容（归一化后查表）
  approval_leader: 1,
  manager: 1,
  operator: 2,
}

/**
 * 标准化角色：旧角色映射到精简后的角色
 * 与后端 app/core/constants.py normalize_role() 保持一致。
 */
export function normalizeRole(role?: string | null): string {
  if (!role) return 'user'
  const r = role.toLowerCase()
  return ROLE_NORMALIZE_MAP[r] || r
}

/**
 * 兼容角色映射
 * - super_admin 兼容 admin 配置
 */
export function getEffectiveRoles(role?: string | null): string[] {
  const normalized = normalizeRole(role)
  if (normalized === 'super_admin') return ['super_admin', 'admin']
  return [normalized]
}

/**
 * 检查是否为管理员（支持 role 和 is_superuser 标志）。
 *
 * 角色必须先 normalizeRole：后端旧值 manager/approval_leader 归一化后就是 admin，
 * 直接用原始 role 比对 ADMIN_ROLES 会把这类存量管理员误判为非管理员
 * （菜单/入口按管理员隐藏），与后端 normalize_role 的语义不一致。
 */
export function isAdminUser(): boolean {
  try {
    const user = AuthStorage.getUser()
    if (!user) return false
    // 检查角色（归一化后比对）
    if (ADMIN_ROLES.includes(normalizeRole(user.role))) return true
    // 检查 is_superuser 标志
    if (user.is_superuser === true) return true
    return false
  } catch {
    return false
  }
}

/**
 * 检查当前用户是否可查看软删记录（回收站入口可见性）。
 *
 * 采用严格路线：仅 super_admin/admin 可见。
 * 参考 AGENTS.md "软删除模式" 章节 — `include_deleted=true 显示全部（管理员）`。
 *
 * 后端依赖 `enforce_admin_include_deleted`（app/api/v1/deps.py）会对非管理员
 * 静默降级 `include_deleted=true` → `False`，此处仅控制 UI 入口可见性。
 */
export function canViewDeleted(): boolean {
  return isAdminUser()
}

/**
 * 基于角色白名单判断是否可访问
 * @param role 当前角色
 * @param allowedRoles 白名单角色；为空表示不限制
 */
export function hasAllowedRole(role: string, allowedRoles?: string[]): boolean {
  if (!allowedRoles || allowedRoles.length === 0) return true
  // 管理员自动拥有所有权限
  if (isAdminUser()) return true
  const effectiveRoles = getEffectiveRoles(role)
  // 白名单同样归一化后比对：否则 {roles:['manager']} 这类存量配置与
  // 归一化后的 'admin' 永不相等（菜单被错误隐藏）
  return allowedRoles.some((r) => effectiveRoles.includes(normalizeRole(r)))
}

/**
 * 基于最小角色门槛判断是否可访问
 * @param role 当前角色
 * @param minRole 最小角色（含自身及更高权限）
 */
export function hasMinRole(role: string, minRole?: string): boolean {
  if (!minRole) return true
  // 管理员自动满足所有最小角色要求
  if (isAdminUser()) return true
  const currentPriority = ROLE_PRIORITY[normalizeRole(role)] ?? ROLE_PRIORITY.viewer
  // minRole 归一化后再查表；未知角色的回退保持 super_admin（最严门槛，fail-closed）
  const requiredPriority = ROLE_PRIORITY[normalizeRole(minRole)] ?? ROLE_PRIORITY.super_admin
  return currentPriority <= requiredPriority
}

/**
 * 统一菜单访问判断（可同时支持 roles + minRole）
 */
export function canAccessMenu(
  role: string,
  options: { roles?: string[]; minRole?: string } = {}
): boolean {
  return hasAllowedRole(role, options.roles) && hasMinRole(role, options.minRole)
}

/**
 * 从 localStorage 安全获取角色。
 *
 * 返回值统一为归一化角色（与 normalizeRole 的默认值 'user' 对齐；
 * 原实现返回原始 role 且默认 'viewer'，与 normalizeRole 的默认值互相矛盾，
 * 调用方拿到的"同一个用户"在不同入口可能是 user / viewer / operator 三种值）。
 * is_superuser 为 true 但角色不是管理员时，仍返回 super_admin。
 */
export function getRoleFromLocalStorage(defaultRole = 'user'): string {
  try {
    const user = AuthStorage.getUser()
    if (!user) return normalizeRole(defaultRole)

    const role = user.role || defaultRole

    if (user.is_superuser === true && !ADMIN_ROLES.includes(normalizeRole(role))) {
      return 'super_admin'
    }

    return normalizeRole(role)
  } catch {
    return normalizeRole(defaultRole)
  }
}
