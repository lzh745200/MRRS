/**
 * 权限包管理 E2E 测试（关键路径）
 *
 * 覆盖流程：
 *   1. 管理员通过 API 创建权限包（menu_keys = ['dashboard', 'villages']）
 *   2. 管理员创建普通用户（role=user，is_active=true）
 *   3. 管理员将用户绑定到权限包
 *   4. 用空认证态走 UI 登录表单登录该新用户
 *   5. 断言侧边栏按「权限包」解析菜单：
 *        - 可见：工作台(dashboard)、帮扶村管理(villages)
 *        - 不可见：经费管理(funds-admin/funds-user)、系统管理(system)
 *
 * 菜单解析优先级（后端 menus._get_user_accessible_menu_keys）：
 *   个人 allowed_menus > 绑定包 menu_keys > 角色默认。
 * 本用例用户未设置 allowed_menus，故应命中「绑定包」分支。
 *
 * 清理：afterAll 解绑 + 删除用户 + 删除包，保证共享 e2e_test.db 可重复运行。
 * 用户名/包名带时间戳，避免并发/残留冲突。
 */
import { test, expect, request as playwrightRequest, type APIRequestContext } from '@playwright/test'

const API_BASE = process.env.E2E_API_URL || 'http://127.0.0.1:18000/api/v1'
const ADMIN = { username: 'admin', password: 'Admin@202507!' }

// 满足 PasswordPolicy：≥12 位、含大写+小写+数字+特殊字符（@ 在白名单内）
const PACK_USER_PASSWORD = 'E2EPack@2026'

// 时间戳后缀，保证共享 e2e_test.db 上可重复运行（即使上一次清理失败也不冲突）
const STAMP = Date.now().toString(36)
const PACK_NAME = `E2E权限包${STAMP}`
const USERNAME = `e2epack${STAMP}`

// 本 spec 以空认证态走 UI 登录表单（参考 login.spec.ts），覆盖全局 storageState
test.use({ storageState: { cookies: [], origins: [] } })

let adminCtx: APIRequestContext
let adminToken = ''
let csrfToken = ''
let packId: number | undefined
let userId: number | undefined

/** 管理员请求头：Bearer token + CSRF 双提交（与 Cookie 中的 csrftoken 一致） */
function apiHeaders(): Record<string, string> {
  const headers: Record<string, string> = { Authorization: `Bearer ${adminToken}` }
  if (csrfToken) headers['X-CSRF-Token'] = csrfToken
  return headers
}

/** 管理员 API 请求；非 2xx 抛出带响应体的错误，便于定位 */
async function adminApi(
  method: 'GET' | 'POST' | 'DELETE',
  path: string,
  data?: unknown
): Promise<Awaited<ReturnType<APIRequestContext['get']>>> {
  const resp = await adminCtx.fetch(`${API_BASE}${path}`, {
    method,
    headers: apiHeaders(),
    data: data === undefined ? undefined : (data as Record<string, unknown>),
  })
  if (!resp.ok()) {
    const text = await resp.text().catch(() => '')
    throw new Error(`admin API ${method} ${path} 失败: HTTP ${resp.status()} ${text}`)
  }
  return resp
}

test.beforeAll(async () => {
  adminCtx = await playwrightRequest.newContext()

  // 1. admin 登录（/auth/login 免 CSRF）
  const loginResp = await adminCtx.post(`${API_BASE}/auth/login`, { data: ADMIN })
  if (!loginResp.ok()) {
    throw new Error(`admin 登录失败: HTTP ${loginResp.status()} ${await loginResp.text()}`)
  }
  const loginBody = await loginResp.json()
  const payload = loginBody?.data ?? loginBody
  adminToken = payload?.access_token ?? payload?.accessToken ?? ''
  if (!adminToken) {
    throw new Error(`admin 登录响应缺少 access_token: ${JSON.stringify(loginBody)}`)
  }

  // 2. 获取 CSRF token（响应会同时 set-cookie csrftoken，由同一 request context 保留）
  const csrfResp = await adminCtx.get(`${API_BASE}/auth/csrf-token`)
  if (!csrfResp.ok()) {
    throw new Error(`获取 CSRF token 失败: HTTP ${csrfResp.status()} ${await csrfResp.text()}`)
  }
  const csrfBody = await csrfResp.json()
  csrfToken = csrfBody?.data?.csrf_token ?? csrfBody?.csrf_token ?? ''
  if (!csrfToken) {
    throw new Error(`CSRF 响应缺少 csrf_token: ${JSON.stringify(csrfBody)}`)
  }

  // 3. 创建权限包（menu_keys 取 2 个合法 key：dashboard、villages）
  const packResp = await adminApi('POST', '/permission-packs', {
    name: PACK_NAME,
    description: 'E2E 权限包关键路径',
    menu_keys: ['dashboard', 'villages'],
    is_active: true,
  })
  const packBody = await packResp.json()
  packId = packBody?.data?.id
  if (!packId) {
    throw new Error(`创建权限包响应缺少 id: ${JSON.stringify(packBody)}`)
  }

  // 4. 创建普通用户
  const userResp = await adminApi('POST', '/users', {
    username: USERNAME,
    password: PACK_USER_PASSWORD,
    role: 'user',
    is_active: true,
  })
  const userBody = await userResp.json()
  userId = userBody?.data?.id
  if (!userId) {
    throw new Error(`创建用户响应缺少 id: ${JSON.stringify(userBody)}`)
  }

  // 5. 绑定用户到权限包
  await adminApi('POST', `/permission-packs/${packId}/bind-users`, { user_ids: [userId] })
})

test('权限包绑定用户后，菜单按包解析（包内可见、包外不可见）', async ({ page }) => {
  // 空认证态走 UI 登录表单
  await page.goto('/login')
  await expect(
    page.locator('input[placeholder*="用户名"], input[type="text"]').first()
  ).toBeVisible()

  await page
    .locator('input[placeholder*="用户名"], input[type="text"]')
    .first()
    .fill(USERNAME)
  await page.locator('input[type="password"]').fill(PACK_USER_PASSWORD)
  await page.locator('button[type="submit"]').click()

  // 登录成功落工作台（新用户未设置 must_change_password/2FA/机器码绑定）
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 })

  // 侧边栏渲染（DefaultLayoutSafe 的 el-menu.aside-menu）
  const sidebar = page.locator('.aside-menu')
  await expect(sidebar).toBeVisible({ timeout: 15000 })

  // 包内菜单可见：工作台(dashboard)、帮扶村管理(villages)
  await expect(sidebar.locator('.menu-title-text', { hasText: '工作台' })).toBeVisible({
    timeout: 15000,
  })
  await expect(sidebar.locator('.menu-title-text', { hasText: '帮扶村管理' })).toBeVisible({
    timeout: 15000,
  })

  // 包外菜单不可见：经费管理(funds)、系统管理(system) 均不在 menu_keys 内
  await expect(sidebar.locator('.menu-title-text', { hasText: '经费管理' })).toBeHidden()
  await expect(sidebar.locator('.menu-title-text', { hasText: '系统管理' })).toBeHidden()
})

test.afterAll(async () => {
  try {
    // 解绑（删除包前必须解绑，否则后端拒绝：仍有绑定用户）
    if (packId != null && userId != null) {
      await adminApi('POST', `/permission-packs/${packId}/unbind-users`, { user_ids: [userId] })
    }
  } catch {
    /* 解绑失败不阻断后续清理 */
  }
  try {
    if (userId != null) {
      await adminApi('DELETE', `/users/${userId}`)
    }
  } catch {
    /* 用户可能已不存在 */
  }
  try {
    if (packId != null) {
      await adminApi('DELETE', `/permission-packs/${packId}`)
    }
  } catch {
    /* 包可能已不存在 */
  }
  await adminCtx?.dispose()
})
