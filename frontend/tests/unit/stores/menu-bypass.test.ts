/**
 * stores/menu.ts — canAccessMenu 超管旁路测试
 *
 * 背景：后端 /menus/accessible 对 is_superuser 做了全量豁免
 * （app/api/v1/menus.py _get_user_accessible_menu_keys），前端 canAccessMenu
 * 需配套旁路，防止后端下发 key 与本地 allKeys 漂移导致超管菜单缺失。
 *
 * 锁定语义（必须与后端 is_superuser 严格一致，仅 superuser，不含普通 admin）：
 *  - is_superuser === true        → 任意 key 可见（含不在 allKeys 内的）
 *  - role === 'super_admin'       → 同上
 *  - 普通用户                      → 仅 allKeys 内的 key 可见（回归保护）
 *  - 普通管理员 role==='admin'     → 不豁免（避免本地可见、后端拒绝）
 *  - 顺序不变：loaded=false 优先于旁路；组织级 hidden 策略优先于旁路
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

import { useMenuStore, type MenuItem } from '@/stores/menu'
import { useAuthStore } from '@/stores/auth'

/** 本地菜单树：system 下的深层 key 不在普通用户 allKeys 内的场景由后端裁剪模拟 */
const LOCAL_MENUS: MenuItem[] = [
  { key: 'dashboard', label: '工作台', path: '/dashboard' },
  {
    key: 'system',
    label: '系统设置',
    children: [{ key: 'machine-code', label: '机器码' }],
  },
]

type AuthUser = {
  id: string
  username: string
  role: string
  is_superuser?: boolean
}

function loginAs(user: AuthUser | null) {
  useAuthStore().user = user
}

describe('stores/menu canAccessMenu 超管旁路', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    sessionStorage.clear()
    localStorage.clear()
  })

  it('is_superuser=true → 任意 key 返回 true（含不在 allKeys 内的深层菜单）', () => {
    loginAs({ id: '1', username: 'admin', role: 'admin', is_superuser: true })
    const menu = useMenuStore()
    menu.setMenus(LOCAL_MENUS)

    // machine-code 在本地 allKeys 内
    expect(menu.canAccessMenu('machine-code')).toBe(true)
    // 本地菜单树里根本没有的 key（后端全量、前端裁剪场景）→ 旁路放行
    expect(menu.canAccessMenu('cache')).toBe(true)
    expect(menu.canAccessMenu('admin-dashboard')).toBe(true)
  })

  it("role='super_admin' 且 is_superuser=false → 同样豁免", () => {
    loginAs({ id: '2', username: 'root', role: 'super_admin', is_superuser: false })
    const menu = useMenuStore()
    menu.setMenus(LOCAL_MENUS)

    expect(menu.canAccessMenu('admin-dashboard')).toBe(true)
  })

  it('普通用户 → 仅 allKeys 内的 key 为 true（回归保护）', () => {
    loginAs({ id: '3', username: 'viewer', role: 'viewer', is_superuser: false })
    const menu = useMenuStore()
    menu.setMenus(LOCAL_MENUS)

    expect(menu.canAccessMenu('dashboard')).toBe(true)
    expect(menu.canAccessMenu('machine-code')).toBe(true)
    // 本地菜单树没有的 key → false（不得被旁路放大）
    expect(menu.canAccessMenu('admin-dashboard')).toBe(false)
  })

  it("普通管理员 role='admin'（is_superuser=false）→ 不豁免", () => {
    // 修复前若误用 isAdmin 语义（含 admin 角色），此断言会失败
    loginAs({ id: '4', username: 'op', role: 'admin', is_superuser: false })
    const menu = useMenuStore()
    menu.setMenus(LOCAL_MENUS)

    expect(menu.canAccessMenu('admin-dashboard')).toBe(false)
  })

  it('loaded=false → 即便是超管也返回 false（顺序：loaded 优先）', () => {
    loginAs({ id: '5', username: 'admin', role: 'admin', is_superuser: true })
    const menu = useMenuStore()
    // 不调用 setMenus → loaded 仍为 false

    expect(menu.canAccessMenu('dashboard')).toBe(false)
  })

  it('组织级 hidden 策略优先于超管旁路', () => {
    loginAs({ id: '6', username: 'admin', role: 'admin', is_superuser: true })
    const menu = useMenuStore()
    menu.setMenus(LOCAL_MENUS)
    menu.setOrgPolicies([
      { module_key: 'dashboard', visibility: 'hidden', edit_mode: 'full_edit' },
    ])

    expect(menu.canAccessMenu('dashboard')).toBe(false)
    // 未被 hidden 的 key 仍走旁路
    expect(menu.canAccessMenu('admin-dashboard')).toBe(true)
  })
})
