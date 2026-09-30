import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

describe('DefaultLayoutSafe 侧边栏回归校验', () => {
  const layoutPath = resolve(process.cwd(), 'src/layouts/DefaultLayoutSafe.vue')
  const routerPath = resolve(process.cwd(), 'src/router/index.ts')
  const layoutSource = readFileSync(layoutPath, 'utf8')
  const routerSource = readFileSync(routerPath, 'utf8')

  it('"经费管理"菜单定义正确且不重复', () => {
    // Layout refactored to use el-menu-item index instead of path prop
    expect(layoutSource).toContain('index="/funds"')
    expect(layoutSource).toContain('经费管理')
    expect(layoutSource).toContain('经费申请')
  })

  it('不再存在管理员无条件放行逻辑（避免重复菜单）', () => {
    expect(layoutSource).not.toContain('if (adminRoles.includes(role)) return true')
    // Layout refactored — permission check moved to roleAccess utility
  })

  it('侧边栏配置的菜单路径均存在于路由定义中', () => {
    // Extract menu paths from layout source. Filter out '/' which is a
    // breadcrumb home link (el-breadcrumb-item :to="{ path: '/' }"), not a
    // sidebar menu item — the regex cannot distinguish menu paths from
    // breadcrumb/router-link destinations by pattern alone.
    const menuPaths = [...layoutSource.matchAll(/path:\s*'([^']+)'/g)]
      .map((m) => m[1])
      .filter((p) => p !== '/')
    const routePaths = [...routerSource.matchAll(/path:\s*"([^"]+)"/g)].map((m) => m[1])
    const fullRoutes = new Set<string>(routePaths.filter((p) => p.startsWith('/')))
    routePaths
      .filter((p) => !p.startsWith('/') && !p.startsWith(':'))
      .forEach((p) => fullRoutes.add(`/${p}`))

    const missing = [...new Set(menuPaths)].filter((p) => !fullRoutes.has(p))
    expect(missing).toEqual([])
  })
})

describe('DefaultLayoutSafe 锁屏摘要与未读轮询定时器', () => {
  const layoutPath = resolve(process.cwd(), 'src/layouts/DefaultLayoutSafe.vue')
  const layoutSource = readFileSync(layoutPath, 'utf8')

  it('自定义 onLock 调用 markLockNow（否则「欢迎回来」摘要永不触发）', () => {
    // 摘要消费侧依赖锁屏打点：consumeLockDigest 只认近 30 分钟内的 markLockNow
    expect(layoutSource).toContain(
      "import { consumeLockDigest, markLockNow } from '@/utils/lockDigest'"
    )
    const start = layoutSource.indexOf('onLock: () => {')
    expect(start).toBeGreaterThan(-1)
    const body = layoutSource.slice(start, layoutSource.indexOf('\n  },', start))
    expect(body).toContain('authStore.lockSession()')
    expect(body).toContain('markLockNow()')
  })

  it('未读数轮询定时器在 setup 作用域声明，并在顶层 onBeforeUnmount 清理', () => {
    // 句柄必须是 setup 顶层变量（原实现是 onMounted 回调内的局部变量 → 无法清理）
    expect(layoutSource).toContain('let unreadTimer: number | null = null')

    const mountedStart = layoutSource.indexOf('onMounted(() => {\n  loadUnreadCount()')
    expect(mountedStart).toBeGreaterThan(-1)
    const mountedBody = layoutSource.slice(mountedStart, layoutSource.indexOf('\n})', mountedStart))
    expect(mountedBody).toContain('unreadTimer = window.setInterval(loadUnreadCount, 60000)')
    // 严禁在 onMounted 回调内注册生命周期钩子（此时无活动实例，钩子不生效）
    expect(mountedBody).not.toContain('onBeforeUnmount(')

    const cleanupStart = layoutSource.indexOf(
      'onBeforeUnmount(() => {\n  if (unreadTimer !== null) {'
    )
    expect(cleanupStart).toBeGreaterThan(-1)
    const cleanupBody = layoutSource.slice(cleanupStart, layoutSource.indexOf('\n})', cleanupStart))
    expect(cleanupBody).toContain('window.clearInterval(unreadTimer)')
    expect(cleanupBody).toContain('unreadTimer = null')
  })
})

describe('DefaultLayoutSafe 系统管理子菜单动态渲染', () => {
  const layoutPath = resolve(process.cwd(), 'src/layouts/DefaultLayoutSafe.vue')
  const routerPath = resolve(process.cwd(), 'src/router/index.ts')
  const systemMenuPath = resolve(process.cwd(), 'src/utils/systemMenu.ts')
  const layoutSource = readFileSync(layoutPath, 'utf8')
  const routerSource = readFileSync(routerPath, 'utf8')
  const systemMenuSource = readFileSync(systemMenuPath, 'utf8')

  it('系统管理子项改为 menuStore.menus 菜单树动态渲染', () => {
    // 动态渲染：v-for 遍历 systemMenuItems（来自 menuStore.menus + router.getRoutes）
    expect(layoutSource).toContain("import { resolveSystemMenuItems } from '@/utils/systemMenu'")
    expect(layoutSource).toContain('resolveSystemMenuItems(menuStore.menus, router.getRoutes())')
    expect(layoutSource).toContain('v-for="item in systemMenuItems"')
    expect(layoutSource).toContain(':index="item.path"')
    expect(layoutSource).toContain('{{ item.label }}')
  })

  it('静态「机器码与通行码」isAdmin 入口保留，machine-code/pass-code 不重复出现', () => {
    // 静态合一入口仍在（authStore.isAdmin 守卫）
    expect(layoutSource).toContain('v-if="authStore.isAdmin"')
    expect(layoutSource).toContain('index="/admin/machine-code/management"')
    expect(layoutSource).toContain('机器码与通行码')
    // 动态列表的去重跳过表覆盖这两个 key
    expect(systemMenuSource).toContain("'machine-code'")
    expect(systemMenuSource).toContain("'pass-code'")
  })

  it('原硬编码子项已移除（用户与角色/审计管理/系统配置/系统监控/帮助文档改由动态渲染承载）', () => {
    // 旧静态 index 不再出现（路由跳转字符串 pushSafe('/system/users') 不受影响）
    expect(layoutSource).not.toContain('index="/system/users"')
    expect(layoutSource).not.toContain('index="/system/audit"')
    expect(layoutSource).not.toContain('index="/system/config"')
    expect(layoutSource).not.toContain('index="/system/monitoring"')
    expect(layoutSource).not.toContain('index="/help"')
  })

  it('顶级静态入口不受影响（组织机构/备份管理/消息中心）', () => {
    expect(layoutSource).toContain('index="/organization"')
    expect(layoutSource).toContain('index="/system/backup"')
    expect(layoutSource).toContain('index="/message"')
    // backup/messages 在动态列表中跳过，避免与顶级入口重复
    expect(systemMenuSource).toContain("'backup'")
    expect(systemMenuSource).toContain("'messages'")
  })

  it('经费子菜单每项都按自己的 menuKey 门控（不再只靠父级放行）', () => {
    // 路径 → 该子项应使用的 menuKey（与 router/index.ts 的 meta.menuKey 对齐；
    // 无独立 menuKey 的历史子页收敛到经费管理主键 funds-admin）
    const expected: Array<[string, string]> = [
      ['/funds', 'funds-admin'],
      ['/funds/budget', 'funds-admin'],
      ['/funds/user', 'funds-user'],
      ['/funds/contract', 'funds-admin'],
      ['/funds/transfer', 'funds-admin'],
      ['/funds/anomaly', 'funds-admin'],
      ['/funds/lifecycle', 'funds-lifecycle'],
      ['/funds/settlement', 'funds-settlement'],
      ['/funds/analysis', 'funds-admin'],
      ['/funds/report', 'funds-admin'],
    ]
    for (const [path, menuKey] of expected) {
      const idx = layoutSource.indexOf(`index="${path}"`)
      expect(idx, `侧边栏缺少 ${path} 入口`).toBeGreaterThan(-1)
      // 同一标签内（index 之前 120 字符窗口）必须带自己的 menuKey 门控
      const before = layoutSource.slice(Math.max(0, idx - 120), idx)
      expect(before, `${path} 缺少 ${menuKey} 门控`).toContain(
        `v-if="menuStore.canAccessMenu('${menuKey}')"`
      )
    }
  })

  it('经费子项使用的 menuKey 与路由 meta.menuKey 一致（有 meta 的路由逐条比对）', () => {
    const routeMenuKeys: Array<[string, string]> = [
      ['/funds', 'funds-admin'],
      ['/funds/user', 'funds-user'],
      ['/funds/lifecycle', 'funds-lifecycle'],
      ['/funds/settlement', 'funds-settlement'],
    ]
    for (const [path, menuKey] of routeMenuKeys) {
      const pattern = new RegExp(
        `path: '${path}',[\\s\\S]{0,160}?meta: \\{[^}]*menuKey: '${menuKey}'`
      )
      expect(routerSource, `路由 ${path} 的 meta.menuKey 应为 ${menuKey}`).toMatch(pattern)
      expect(layoutSource).toContain(`menuStore.canAccessMenu('${menuKey}')`)
    }
  })

  it('PATH_OVERRIDES 漂移映射的目标路径均存在于真实路由表', () => {
    // 从 systemMenu.ts 源码提取 PATH_OVERRIDES 块内的目标路径
    const blockStart = systemMenuSource.indexOf('PATH_OVERRIDES')
    const blockEnd = systemMenuSource.indexOf('export interface', blockStart)
    expect(blockStart).toBeGreaterThan(-1)
    const overrideBlock = systemMenuSource.slice(blockStart, blockEnd)
    const targets = [...overrideBlock.matchAll(/:\s*'([^']+)'/g)].map((m) => m[1])
    // 至少包含两条已知漂移映射
    expect(targets).toContain('/system/users')
    expect(targets).toContain('/system/monitoring')

    // 路由源码 path 一律单引号（path: '/system/users'），双引号正则匹配不到任何值
    const routePaths = [...routerSource.matchAll(/path:\s*'([^']+)'/g)].map((m) => m[1])
    const fullRoutes = new Set<string>(routePaths.filter((p) => p.startsWith('/')))
    routePaths
      .filter((p) => !p.startsWith('/') && !p.startsWith(':'))
      .forEach((p) => fullRoutes.add(`/${p}`))
    const missing = targets.filter((p) => !fullRoutes.has(p))
    expect(missing).toEqual([])
  })
})
