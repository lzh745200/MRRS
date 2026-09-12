/**
 * @/utils/systemMenu 解析器测试
 *
 * 覆盖目标：resolveSystemMenuItems 100% 语句/分支覆盖（src/utils 100% 门禁），
 * 同时验证 DefaultLayoutSafe「系统管理」子菜单动态渲染的核心行为：
 *  - system 组 children 全量解析（cache/zero-trust/update-logs/权限包/后台任务…）
 *  - path 解析三级兜底：有效路由 path → meta.menuKey 路由 → PATH_OVERRIDES 漂移映射
 *  - 死链跳过（child.path 无对应路由且无兜底）
 *  - 去重：backup/messages/machine-code/pass-code（与既有侧边栏入口重复）与同 key/同 path
 *  - 无 path 有 children 的提升一级渲染（不漏功能）
 *  - order 字段排序，缺省保持后端下发顺序（稳定排序）
 */
import { describe, it, expect } from 'vitest'
import { resolveSystemMenuItems } from '@/utils/systemMenu'
import type { MenuItem } from '@/stores/menu'

// ── 路由表：与 src/router/index.ts 中 system 组相关条目一一对应的结构子集 ──
const ROUTES = [
  { path: '/system/audit', meta: { menuKey: 'audit' } },
  { path: '/system/cache' }, // 真实路由无 menuKey
  { path: '/system/config' },
  { path: '/system/users' },
  { path: '/system/monitoring' },
  { path: '/system/backup' },
  { path: '/message' },
  { path: '/admin/machine-code' },
  { path: '/organizations/pass-code' },
  { path: '/system/help' }, // redirect 路由（→ /help），也是合法入口
  { path: '/system/update-logs', meta: { menuKey: 'update-logs' } },
  { path: '/system/zero-trust', meta: { menuKey: 'zero-trust' } },
  { path: '/system/feedback', meta: { menuKey: 'feedback' } },
  { path: '/system/data-tier', meta: { menuKey: 'data-tier' } },
  { path: '' }, // 防御分支：空 path 的路由记录
  { path: '/dup-first', meta: { menuKey: 'dup-menu-key' } },
  { path: '/dup-second', meta: { menuKey: 'dup-menu-key' } }, // 重复 menuKey 取首个
  { path: '/odd-menu-key', meta: { menuKey: 123 } }, // 非字符串 menuKey 忽略
]

// ── 菜单树：镜像后端 MENU_DEFINITIONS system 组（含漂移/死链/分组/重复等形态）──
const SYSTEM_MENUS: MenuItem[] = [
  null as unknown as MenuItem, // 菜单树防御分支（脏数据不抛错；须位于 system 之前才会被遍历到）
  { key: 'dashboard', label: '工作台', path: '/dashboard' },
  {
    key: 'system',
    label: '系统管理',
    children: [
      { key: 'machine-code', label: '机器码管理', path: '/admin/machine-code' }, // 去重跳过
      { key: 'pass-code', label: '通行码管理', path: '/organizations/pass-code' }, // 去重跳过
      { key: 'users-orgs', label: '用户与组织管理', path: '/system/users-orgs' }, // 漂移 → /system/users
      { key: 'audit', label: '安全审计', path: '/system/audit' }, // path 为有效路由
      { key: 'backup', label: '备份管理', path: '/system/backup' }, // 去重跳过（顶级已有入口）
      { key: 'cache', label: '缓存管理', path: '/system/cache' }, // path 为有效路由
      { key: 'monitor', label: '系统监控', path: '/system/monitor' }, // 漂移 → /system/monitoring
      { key: 'help', label: '帮助文档', path: '/system/help' }, // redirect 路由同样有效
      { key: 'update-logs', label: '更新日志', path: '/system/update-logs' },
      { key: 'zero-trust', label: '零信任' }, // 无 path → menuKey 路由兜底
      { key: 'health', label: '系统健壮性', path: '/system/health' }, // 死链 → 跳过
      {
        key: 'group-a',
        label: '分组A',
        children: [
          // 无 path 有 children → 提升一级
          { key: 'data-tier', label: '数据分级', path: '/system/data-tier' },
          { key: 'feedback', label: '反馈管理' }, // 提升 + menuKey 兜底
        ],
      },
      { key: 'cache-mirror', label: '缓存镜像', path: '/system/cache' }, // 同 path 去重
      { key: 'cache', label: '缓存管理2', path: '/system/cache' }, // 同 key 去重
      { key: 'dup-menu-key', label: '重复menuKey' }, // → /dup-first（重复 menuKey 取首个）
      { key: '', label: '空key', path: '/system/cache' }, // 缺 key 跳过
      { key: 'no-label', path: '/system/cache' } as unknown as MenuItem, // 缺 label 跳过
    ],
  },
]

describe('resolveSystemMenuItems', () => {
  it('system 组 children 解析为菜单项，path 指向正确路由', () => {
    const items = resolveSystemMenuItems(SYSTEM_MENUS, ROUTES)
    const byKey = new Map(items.map((i) => [i.key, i]))

    // 后端有、此前侧边栏完全没有入口的功能项全部渲染
    expect(byKey.get('cache')).toMatchObject({ label: '缓存管理', path: '/system/cache' })
    expect(byKey.get('zero-trust')).toMatchObject({ label: '零信任', path: '/system/zero-trust' })
    expect(byKey.get('update-logs')).toMatchObject({
      label: '更新日志',
      path: '/system/update-logs',
    })
    expect(byKey.get('audit')).toMatchObject({ label: '安全审计', path: '/system/audit' })
    expect(byKey.get('help')).toMatchObject({ label: '帮助文档', path: '/system/help' })
    expect(byKey.get('data-tier')).toMatchObject({ label: '数据分级', path: '/system/data-tier' })
    expect(byKey.get('feedback')).toMatchObject({ label: '反馈管理', path: '/system/feedback' })

    // 漂移 path 兜底到真实路由（不渲染死链）
    expect(byKey.get('users-orgs')?.path).toBe('/system/users')
    expect(byKey.get('monitor')?.path).toBe('/system/monitoring')
  })

  it('去重跳过：backup/messages/machine-code/pass-code 不重复出现', () => {
    const items = resolveSystemMenuItems(SYSTEM_MENUS, ROUTES)
    const keys = items.map((i) => i.key)
    expect(keys).not.toContain('machine-code')
    expect(keys).not.toContain('pass-code')
    expect(keys).not.toContain('backup')
    expect(keys).not.toContain('messages')

    // 同 key / 同 path（历史漂移）只保留首个
    expect(keys.filter((k) => k === 'cache')).toHaveLength(1)
    expect(keys).not.toContain('cache-mirror')

    // 重复 menuKey 的路由取首个
    expect(items.find((i) => i.key === 'dup-menu-key')?.path).toBe('/dup-first')
  })

  it('死链与脏数据跳过：无路由可解析的项不渲染', () => {
    const items = resolveSystemMenuItems(SYSTEM_MENUS, ROUTES)
    const keys = items.map((i) => i.key)
    // /system/health 无对应路由、无 menuKey 兜底、无漂移映射 → 跳过
    expect(keys).not.toContain('health')
    // 缺 key / 缺 label 的脏数据 → 跳过
    expect(items.some((i) => i.label === '空key')).toBe(false)
    expect(items.some((i) => i.key === 'no-label')).toBe(false)
  })

  it('顺序保持后端下发顺序（无 order 字段）', () => {
    const items = resolveSystemMenuItems(SYSTEM_MENUS, ROUTES)
    const keys = items.map((i) => i.key)
    // machine-code/pass-code 去重跳过后，首个渲染项为 users-orgs
    expect(keys[0]).toBe('users-orgs')
    expect(keys.indexOf('audit')).toBeGreaterThan(keys.indexOf('users-orgs'))
    expect(keys.indexOf('cache')).toBeGreaterThan(keys.indexOf('audit'))
  })

  it('order 字段存在时按 order 升序，缺省项保持稳定相对顺序', () => {
    const orderedMenus: MenuItem[] = [
      {
        key: 'system',
        label: '系统管理',
        children: [
          { key: 'b', label: 'B', path: '/system/cache', order: 2 },
          { key: 'a', label: 'A', path: '/system/config', order: 1 },
          { key: 'c', label: 'C', path: '/system/users' }, // 无 order（缺省 0）
        ],
      },
    ]
    expect(resolveSystemMenuItems(orderedMenus, ROUTES).map((i) => i.key)).toEqual([
      'c',
      'a',
      'b',
    ])
  })

  it('无 system 节点 / system 无 children / children 为空 → 空列表', () => {
    expect(resolveSystemMenuItems([{ key: 'dashboard', label: '工作台' }], ROUTES)).toEqual([])
    expect(
      resolveSystemMenuItems([{ key: 'system', label: '系统管理' }], ROUTES)
    ).toEqual([])
    expect(
      resolveSystemMenuItems([{ key: 'system', label: '系统管理', children: [] }], ROUTES)
    ).toEqual([])
  })

  it('menus / routes 非数组（store 未初始化等）按空集处理不抛错', () => {
    expect(resolveSystemMenuItems(undefined, ROUTES)).toEqual([])
    expect(resolveSystemMenuItems(null, ROUTES)).toEqual([])
    expect(resolveSystemMenuItems(SYSTEM_MENUS, undefined)).toEqual([])
    expect(resolveSystemMenuItems(SYSTEM_MENUS, null)).toEqual([])
  })

  it('非字符串 menuKey 与空 path 路由记录被忽略', () => {
    const items = resolveSystemMenuItems(
      [{ key: 'system', label: '系统管理', children: [{ key: 'odd-menu-key', label: '异常项' }] }],
      ROUTES
    )
    // menuKey: 123 非字符串 → 不构成兜底；该 child 无 path → 跳过
    expect(items).toEqual([])
  })
})
