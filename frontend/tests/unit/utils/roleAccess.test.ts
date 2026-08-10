import { describe, it, expect, vi } from 'vitest'
import { AuthStorage } from '@/utils/authStorage'
import {
  ADMIN_ROLES,
  ROLE_PRIORITY,
  normalizeRole,
  getEffectiveRoles,
  isAdminUser,
  canViewDeleted,
  hasAllowedRole,
  hasMinRole,
  canAccessMenu,
  getRoleFromLocalStorage,
} from '@/utils/roleAccess'

function setAuthUser(user: Record<string, unknown>) {
  sessionStorage.clear()
  sessionStorage.setItem('auth_user', JSON.stringify(user))
}

describe('roleAccess utility', () => {
  it('ROLE_PRIORITY includes expected roles', () => {
    expect(ROLE_PRIORITY.super_admin).toBe(0)
    expect(ROLE_PRIORITY.admin).toBe(1)
    // 历史角色归一化到精简角色（approval_leader/manager → admin, operator → user）
    expect(ROLE_PRIORITY.approval_leader).toBe(1)
    expect(ROLE_PRIORITY.manager).toBe(1)
    expect(ROLE_PRIORITY.user).toBe(2)
    expect(ROLE_PRIORITY.operator).toBe(2)
    expect(ROLE_PRIORITY.viewer).toBe(3)
  })

  it('normalizeRole returns user when role is empty', () => {
    expect(normalizeRole(undefined)).toBe('user')
    expect(normalizeRole(null)).toBe('user')
    expect(normalizeRole('')).toBe('user')
  })

  it('normalizeRole keeps valid role', () => {
    expect(normalizeRole('admin')).toBe('admin')
  })

  it('normalizeRole maps legacy roles to simplified roles', () => {
    expect(normalizeRole('manager')).toBe('admin')
    expect(normalizeRole('approval_leader')).toBe('admin')
    expect(normalizeRole('operator')).toBe('user')
    expect(normalizeRole('editor')).toBe('editor')
  })

  it('getEffectiveRoles maps super_admin to include admin', () => {
    expect(getEffectiveRoles('super_admin')).toEqual(['super_admin', 'admin'])
  })

  it('getEffectiveRoles normalizes legacy roles', () => {
    expect(getEffectiveRoles('manager')).toEqual(['admin'])
    expect(getEffectiveRoles('operator')).toEqual(['user'])
  })

  it('hasAllowedRole passes when no allowedRoles', () => {
    expect(hasAllowedRole('viewer')).toBe(true)
    expect(hasAllowedRole('viewer', [])).toBe(true)
  })

  it('hasAllowedRole supports super_admin compatible admin config', () => {
    expect(hasAllowedRole('super_admin', ['admin'])).toBe(true)
  })

  it('hasAllowedRole rejects role not in allowed list', () => {
    expect(hasAllowedRole('viewer', ['admin', 'manager'])).toBe(false)
  })

  it('hasMinRole works with same or higher privilege', () => {
    expect(hasMinRole('admin', 'admin')).toBe(true)
    expect(hasMinRole('super_admin', 'admin')).toBe(true)
    expect(hasMinRole('manager', 'operator')).toBe(true)
  })

  it('hasMinRole rejects lower privilege', () => {
    expect(hasMinRole('viewer', 'operator')).toBe(false)
    expect(hasMinRole('operator', 'manager')).toBe(false)
  })

  it('hasMinRole passes when minRole is undefined', () => {
    expect(hasMinRole('viewer', undefined)).toBe(true)
  })

  it('canAccessMenu supports combined roles + minRole', () => {
    expect(canAccessMenu('admin', { roles: ['admin'], minRole: 'manager' })).toBe(true)
    expect(canAccessMenu('viewer', { roles: ['viewer'], minRole: 'operator' })).toBe(false)
    expect(canAccessMenu('operator', { roles: ['manager', 'admin'], minRole: 'viewer' })).toBe(false)
  })

  it('getRoleFromLocalStorage returns default when no user', () => {
    sessionStorage.clear()
    expect(getRoleFromLocalStorage()).toBe('viewer')
    expect(getRoleFromLocalStorage('operator')).toBe('operator')
  })

  it('getRoleFromLocalStorage reads sessionStorage auth_user', () => {
    sessionStorage.clear()
    sessionStorage.setItem('auth_user', JSON.stringify({ role: 'manager' }))
    expect(getRoleFromLocalStorage()).toBe('manager')
  })

  it('getRoleFromLocalStorage handles invalid json', () => {
    sessionStorage.clear()
    sessionStorage.setItem('auth_user', '{invalid')
    expect(getRoleFromLocalStorage()).toBe('viewer')
  })
})

describe('ADMIN_ROLES / normalizeRole / getEffectiveRoles 补充', () => {
  it('ADMIN_ROLES 包含 admin 与 super_admin', () => {
    expect(ADMIN_ROLES).toContain('admin')
    expect(ADMIN_ROLES).toContain('super_admin')
  })

  it('normalizeRole 大写角色转小写', () => {
    expect(normalizeRole('ADMIN')).toBe('admin')
    expect(normalizeRole('Super_Admin')).toBe('super_admin')
  })

  it('normalizeRole 未知名角色原样返回', () => {
    expect(normalizeRole('ghost')).toBe('ghost')
  })

  it('getEffectiveRoles(admin) → [admin]', () => {
    expect(getEffectiveRoles('admin')).toEqual(['admin'])
  })
})

describe('isAdminUser / canViewDeleted', () => {
  it('无用户 → false', () => {
    sessionStorage.clear()
    expect(isAdminUser()).toBe(false)
    expect(canViewDeleted()).toBe(false)
  })

  it('admin/super_admin 角色 → true', () => {
    setAuthUser({ role: 'admin' })
    expect(isAdminUser()).toBe(true)
    expect(canViewDeleted()).toBe(true)
    setAuthUser({ role: 'super_admin' })
    expect(isAdminUser()).toBe(true)
  })

  it('is_superuser 标志（role 非管理员）→ true', () => {
    setAuthUser({ role: 'user', is_superuser: true })
    expect(isAdminUser()).toBe(true)
  })

  it('普通角色 → false', () => {
    setAuthUser({ role: 'user' })
    expect(isAdminUser()).toBe(false)
  })

  it('用户无 role 字段 → user.role || \'\' 兜底为 false', () => {
    setAuthUser({})
    expect(isAdminUser()).toBe(false)
  })

  it('AuthStorage.getUser 抛错 → false（catch 分支）', () => {
    const spy = vi.spyOn(AuthStorage, 'getUser').mockImplementation(() => {
      throw new Error('boom')
    })
    expect(isAdminUser()).toBe(false)
    expect(canViewDeleted()).toBe(false)
    spy.mockRestore()
  })
})

describe('管理员快捷权限分支', () => {
  it('hasAllowedRole 当前用户是管理员 → 自动 true', () => {
    setAuthUser({ role: 'admin' })
    expect(hasAllowedRole('viewer', ['admin'])).toBe(true)
  })

  it('hasMinRole 当前用户是管理员 → 自动 true', () => {
    setAuthUser({ role: 'admin' })
    expect(hasMinRole('viewer', 'super_admin')).toBe(true)
  })

  it('未知角色按 viewer 优先级判定', () => {
    sessionStorage.clear()
    expect(hasMinRole('ghost', 'admin')).toBe(false)
    expect(hasMinRole('ghost', 'viewer')).toBe(true)
  })

  it('未知 minRole 按 super_admin 优先级判定', () => {
    sessionStorage.clear()
    expect(hasMinRole('admin', 'ghost')).toBe(false)
  })

  it('canAccessMenu 空选项默认放行', () => {
    sessionStorage.clear()
    expect(canAccessMenu('viewer')).toBe(true)
  })
})

describe('getRoleFromLocalStorage 补充', () => {
  it('is_superuser 且 role 非管理员 → super_admin', () => {
    setAuthUser({ role: 'user', is_superuser: true })
    expect(getRoleFromLocalStorage()).toBe('super_admin')
  })

  it('is_superuser 且 role=admin → 保持 admin', () => {
    setAuthUser({ role: 'admin', is_superuser: true })
    expect(getRoleFromLocalStorage()).toBe('admin')
  })

  it('用户无 role 字段 → 回退 defaultRole', () => {
    setAuthUser({})
    expect(getRoleFromLocalStorage()).toBe('viewer')
    expect(getRoleFromLocalStorage('user')).toBe('user')
  })

  it('getUser 抛错 → default（catch 分支）', () => {
    const spy = vi.spyOn(AuthStorage, 'getUser').mockImplementation(() => {
      throw new Error('boom')
    })
    expect(getRoleFromLocalStorage()).toBe('viewer')
    spy.mockRestore()
  })
})
