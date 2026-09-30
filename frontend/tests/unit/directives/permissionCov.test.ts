/**
 * directives/permission.ts 覆盖率攻坚（statements/branches/functions/lines 四指标 100%）
 * 直接调用 mounted / updated 钩子（真实 DOM 元素）：
 * 管理员放行（角色命中 / is_superuser 两侧）、菜单 key / 权限码 / 角色数组 / 模块粒度
 * 四种模式全分支（含 detached el 的 parentNode 短路、空数组、非法值 warn、
 * updated 值不变短路、模块未配置兜底、未知 level 穿透）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// vi.mock 工厂被提升到模块顶部，引用的对象必须先放入 vi.hoisted（TDZ 坑）
const { authState, menuState, loggerMock } = vi.hoisted(() => ({
  authState: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    user: null as any,
    modulePermissions: {} as Record<string, { view: boolean; edit: boolean }>,
  },
  menuState: { canAccessMenu: vi.fn() },
  loggerMock: { warn: vi.fn(), error: vi.fn(), info: vi.fn(), debug: vi.fn() },
}))

vi.mock('@/stores/auth', () => ({ useAuthStore: () => authState }))
vi.mock('@/stores/menu', () => ({ useMenuStore: () => menuState }))
vi.mock('@/utils/logger', () => ({ logger: loggerMock }))

import { permission } from '@/directives/permission'

type MountedFn = (el: HTMLElement, binding: { value: unknown }) => void
type UpdatedFn = (el: HTMLElement, binding: { value: unknown; oldValue: unknown }) => void

const callMounted = (el: HTMLElement, value: unknown) =>
  (permission.mounted as unknown as MountedFn)(el, { value })
const callUpdated = (el: HTMLElement, value: unknown, oldValue: unknown) =>
  (permission.updated as unknown as UpdatedFn)(el, { value, oldValue })

function makeEl(withParent = true) {
  const parent = document.createElement('div')
  const el = document.createElement('button')
  if (withParent) parent.appendChild(el)
  return { parent, el }
}

beforeEach(() => {
  vi.resetAllMocks()
  authState.user = { role: 'viewer', permissions: [], is_superuser: false }
  authState.modulePermissions = {}
  menuState.canAccessMenu.mockReturnValue(false)
})

describe('mounted 钩子', () => {
  it('管理员角色（ADMIN_ROLES 命中）→ 始终放行不移除', () => {
    authState.user = { role: 'admin', permissions: [] }
    const { parent, el } = makeEl()
    callMounted(el, 'project:create')
    expect(parent.contains(el)).toBe(true)
  })

  it('is_superuser（ADMIN_ROLES 未命中右侧）→ 放行', () => {
    authState.user = { role: 'viewer', is_superuser: true, permissions: [] }
    const { parent, el } = makeEl()
    callMounted(el, ['admin'])
    expect(parent.contains(el)).toBe(true)
  })

  // 2026-09-30 深审修复：无权限不再 removeChild（永久摘除、updated 无法复原），
  // 改为与 updated 对称的 display:none（可逆），故断言随之改写。
  it('菜单模式：canAccessMenu=false → 隐藏元素（不再摘除）', () => {
    const { parent, el } = makeEl()
    callMounted(el, { menu: 'system' })
    expect(menuState.canAccessMenu).toHaveBeenCalledWith('system')
    expect(parent.contains(el)).toBe(true)
    expect(el.style.display).toBe('none')
  })

  it('菜单模式：canAccessMenu=true → 保留元素', () => {
    menuState.canAccessMenu.mockReturnValue(true)
    const { parent, el } = makeEl()
    callMounted(el, { menu: 'system' })
    expect(parent.contains(el)).toBe(true)
  })

  it('菜单模式：无权限且 el 无父节点 → 隐藏且不抛错（无需 parentNode）', () => {
    const { el } = makeEl(false)
    callMounted(el, { menu: 'system' })
    expect(el.style.display).toBe('none')
  })

  it('权限码模式：已授权 → 保留', () => {
    authState.user = { role: 'viewer', permissions: ['project:create'] }
    const { parent, el } = makeEl()
    callMounted(el, 'project:create')
    expect(parent.contains(el)).toBe(true)
  })

  it('权限码模式：未授权 → 隐藏（可逆）', () => {
    const { parent, el } = makeEl()
    callMounted(el, 'project:create')
    expect(parent.contains(el)).toBe(true)
    expect(el.style.display).toBe('none')
  })

  it('权限码模式：未授权且 el 无父节点 → 隐藏且不抛错', () => {
    const { el } = makeEl(false)
    callMounted(el, 'project:create')
    expect(el.style.display).toBe('none')
  })

  it('权限码模式：user 为 null → role/permissions 双兜底后隐藏', () => {
    authState.user = null
    const { el } = makeEl()
    callMounted(el, 'project:create')
    expect(el.style.display).toBe('none')
  })

  it('权限码模式：user.permissions 缺失 → 兜底空数组后隐藏', () => {
    authState.user = { role: 'viewer' }
    const { el } = makeEl()
    callMounted(el, 'project:create')
    expect(el.style.display).toBe('none')
  })

  it('角色数组模式：角色命中 → 保留', () => {
    const { parent, el } = makeEl()
    callMounted(el, ['admin', 'viewer'])
    expect(parent.contains(el)).toBe(true)
  })

  it('角色数组模式：角色未命中 → 隐藏', () => {
    const { el } = makeEl()
    callMounted(el, ['admin', 'manager'])
    expect(el.style.display).toBe('none')
  })

  it('角色数组模式：未命中且 el 无父节点 → 隐藏且不抛错', () => {
    const { el } = makeEl(false)
    callMounted(el, ['admin'])
    expect(el.style.display).toBe('none')
  })

  it('角色数组模式：currentRole 为数组 → 任一命中即保留', () => {
    authState.user = { role: ['viewer', 'manager'], permissions: [] }
    const { parent, el } = makeEl()
    callMounted(el, ['manager'])
    expect(parent.contains(el)).toBe(true)
  })

  it('模块粒度 view：有 view 权限 → 显示', () => {
    authState.modulePermissions = { village: { view: true, edit: false } }
    const { el } = makeEl()
    callMounted(el, { module: 'village', level: 'view' })
    expect(el.style.display).toBe('')
  })

  it('模块粒度 view：无 view 有 edit → 显示（|| 右侧）', () => {
    authState.modulePermissions = { village: { view: false, edit: true } }
    const { el } = makeEl()
    callMounted(el, { module: 'village', level: 'view' })
    expect(el.style.display).toBe('')
  })

  it('模块粒度 view：view/edit 均无 → 隐藏', () => {
    authState.modulePermissions = { village: { view: false, edit: false } }
    const { el } = makeEl()
    callMounted(el, { module: 'village', level: 'view' })
    expect(el.style.display).toBe('none')
  })

  it('模块粒度 edit：有 edit → 显示', () => {
    authState.modulePermissions = { village: { view: false, edit: true } }
    const { el } = makeEl()
    callMounted(el, { module: 'village', level: 'edit' })
    expect(el.style.display).toBe('')
  })

  it('模块粒度 edit：无 edit → 隐藏', () => {
    authState.modulePermissions = { village: { view: true, edit: false } }
    const { el } = makeEl()
    callMounted(el, { module: 'village', level: 'edit' })
    expect(el.style.display).toBe('none')
  })

  it('模块粒度：模块未配置 → 兜底 {view:false,edit:false} 隐藏', () => {
    const { el } = makeEl()
    callMounted(el, { module: 'unknown_mod', level: 'view' })
    expect(el.style.display).toBe('none')
  })

  // 2026-09-30 深审修复：未知 level 原先"两个 else-if 都不进"→ 元素保持可见（fail-open）。
  // 现改为 fail-closed 隐藏 + DEV 告警，断言随之改写。
  it('模块粒度：未知 level → fail-closed 隐藏并在 DEV 告警', () => {
    authState.modulePermissions = { village: { view: true, edit: true } }
    const { el } = makeEl()
    callMounted(el, { module: 'village', level: 'delete' })
    expect(el.style.display).toBe('none')
    expect(loggerMock.warn).toHaveBeenCalledWith(expect.stringContaining('未知的模块权限级别'))
  })

  it('模块粒度：未知 level 且非 DEV 环境 → 静默隐藏（不写告警）', () => {
    vi.stubEnv('DEV', false)
    try {
      authState.modulePermissions = { village: { view: true, edit: true } }
      const { el } = makeEl()
      callMounted(el, { module: 'village', level: 'undefined-level' })
      expect(el.style.display).toBe('none')
      expect(loggerMock.warn).not.toHaveBeenCalled()
    } finally {
      vi.unstubAllEnvs()
    }
  })

  it('无权限隐藏后权限恢复 → updated 钩子可复原 display（可逆性）', () => {
    const { el } = makeEl()
    callMounted(el, { menu: 'system' })
    expect(el.style.display).toBe('none')
    menuState.canAccessMenu.mockReturnValue(true)
    callUpdated(el, { menu: 'system' }, { menu: 'other' })
    expect(el.style.display).toBe('')
  })

  it('无效用法：value 为 null → 各检查短路并 warn 提示', () => {
    const { el } = makeEl()
    callMounted(el, null)
    expect(loggerMock.warn).toHaveBeenCalledTimes(1)
    expect(loggerMock.warn.mock.calls[0][0]).toContain('v-permission')
    expect(loggerMock.warn.mock.calls[0][1]).toBeNull()
  })

  it('无效用法：数字（非对象非字符串非数组）→ warn', () => {
    const { el } = makeEl()
    callMounted(el, 123)
    expect(loggerMock.warn).toHaveBeenCalledTimes(1)
  })

  it('无效用法：空数组（length=0 穿透）→ warn', () => {
    const { el } = makeEl()
    callMounted(el, [])
    expect(loggerMock.warn).toHaveBeenCalledTimes(1)
  })

  it('无效用法：对象缺 menu/module → warn', () => {
    const { el } = makeEl()
    callMounted(el, {})
    expect(loggerMock.warn).toHaveBeenCalledTimes(1)
  })

  it('无效用法：{ module } 缺 level → warn', () => {
    const { el } = makeEl()
    callMounted(el, { module: 'village' })
    expect(loggerMock.warn).toHaveBeenCalledTimes(1)
  })

  it('无效用法：{ level } 缺 module → warn', () => {
    const { el } = makeEl()
    callMounted(el, { level: 'edit' })
    expect(loggerMock.warn).toHaveBeenCalledTimes(1)
  })
})

describe('updated 钩子', () => {
  it('值未变化（JSON 相等）→ 直接返回，不查权限不改样式', () => {
    const { el } = makeEl()
    el.style.display = 'none'
    callUpdated(el, { menu: 'system' }, { menu: 'system' })
    expect(menuState.canAccessMenu).not.toHaveBeenCalled()
    expect(el.style.display).toBe('none')
  })

  it('管理员角色 → 复位 display 并移除 disabled', () => {
    authState.user = { role: 'super_admin', permissions: [] }
    const { el } = makeEl()
    el.style.display = 'none'
    el.setAttribute('disabled', '')
    callUpdated(el, 'a', 'b')
    expect(el.style.display).toBe('')
    expect(el.hasAttribute('disabled')).toBe(false)
  })

  it('is_superuser（右侧）→ 复位 display 并移除 disabled', () => {
    authState.user = { role: 'viewer', is_superuser: true, permissions: [] }
    const { el } = makeEl()
    el.style.display = 'none'
    el.setAttribute('disabled', '')
    callUpdated(el, ['admin'], ['viewer'])
    expect(el.style.display).toBe('')
    expect(el.hasAttribute('disabled')).toBe(false)
  })

  it('菜单模式：无权限 → none；有权限 → 复位', () => {
    const { el } = makeEl()
    callUpdated(el, { menu: 'system' }, { menu: 'other' })
    expect(el.style.display).toBe('none')
    menuState.canAccessMenu.mockReturnValue(true)
    callUpdated(el, { menu: 'system' }, { menu: 'sys2' })
    expect(el.style.display).toBe('')
  })

  it('权限码模式：已授权 → 复位；未授权 → none', () => {
    authState.user = { role: 'viewer', permissions: ['p:x'] }
    const { el } = makeEl()
    el.style.display = 'none'
    callUpdated(el, 'p:x', 'p:y')
    expect(el.style.display).toBe('')
    callUpdated(el, 'p:y', 'p:x')
    expect(el.style.display).toBe('none')
  })

  it('权限码模式：user 为 null → 双兜底后 none', () => {
    authState.user = null
    const { el } = makeEl()
    callUpdated(el, 'p:x', 'p:y')
    expect(el.style.display).toBe('none')
  })

  it('权限码模式：permissions 缺失 → 兜底空数组后 none', () => {
    authState.user = { role: 'viewer' }
    const { el } = makeEl()
    callUpdated(el, 'p:x', 'p:y')
    expect(el.style.display).toBe('none')
  })

  it('角色数组模式：命中 → 复位；未命中 → none（三元两侧）', () => {
    const { el } = makeEl()
    el.style.display = 'none'
    callUpdated(el, ['viewer'], ['admin'])
    expect(el.style.display).toBe('')
    callUpdated(el, ['admin'], ['viewer'])
    expect(el.style.display).toBe('none')
  })

  it('角色数组模式：空数组 → 穿透到模块检查后无操作', () => {
    const { el } = makeEl()
    callUpdated(el, [], ['x'])
    expect(el.style.display).toBe('')
  })

  it('模块粒度：view 有权限 → 复位 display', () => {
    authState.modulePermissions = { village: { view: true, edit: false } }
    const { el } = makeEl()
    el.style.display = 'none'
    callUpdated(el, { module: 'village', level: 'view' }, { module: 'village', level: 'edit' })
    expect(el.style.display).toBe('')
  })

  it('模块粒度：{ level } 缺 module / { module } 缺 level → 无操作', () => {
    const { el } = makeEl()
    callUpdated(el, { level: 'edit' }, {})
    expect(el.style.display).toBe('')
    callUpdated(el, { module: 'village' }, { level: 'edit' })
    expect(el.style.display).toBe('')
  })

  it('无效值：null → 各 && 链短路无操作', () => {
    const { el } = makeEl()
    callUpdated(el, null, 'x')
    expect(el.style.display).toBe('')
  })

  it('无效值：数字 → typeof 短路无操作', () => {
    const { el } = makeEl()
    callUpdated(el, 123, 'x')
    expect(el.style.display).toBe('')
  })
})
