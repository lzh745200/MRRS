/**
 * E2E 全局前置：API 登录一次，写入 storageState（localStorage 持久键），
 * 所有 spec 复用认证态——避免每个用例都走 UI 登录触发后端
 * 登录限流（5 次/分钟/IP）导致的随机失败。
 *
 * 应用侧读取链：AuthStorage.getToken() → sessionStorage → localStorage
 * auth_persist_token（"记住登录"持久键）。Playwright storageState 只支持
 * localStorage（sessionStorage 为标签页级，无法预置），因此写入 persist 键。
 *
 * 首登强制改密自适应（2026-09-06）：全新 e2e_test.db 由后端种子逻辑创建
 * 管理员（出厂密码 Admin@2026，must_change_password=True），首次登录会被
 * 强制跳转修改密码页。此处自动完成一次改密（改为 E2E 专用密码），并把
 * E2E 专用密码通过 process.env.TEST_PASSWORD 传给各 spec——持久库第二次
 * 运行时直接用该密码登录。
 */
import { request } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export const AUTH_FILE = path.join(__dirname, '.auth', 'admin.json')

const API_BASE = process.env.E2E_API_URL || 'http://127.0.0.1:18000/api/v1'
const WEB_ORIGIN = process.env.E2E_BASE_URL || 'http://127.0.0.1:15173'

const FACTORY_PASSWORD = 'Admin@2026'
const E2E_PASSWORD = process.env.TEST_PASSWORD || 'E2e#Probe2026!x'

async function login(ctx: ReturnType<typeof request.newContext>, password: string) {
  const resp = await ctx.post(`${API_BASE}/auth/login`, {
    data: { username: 'admin', password },
  })
  if (!resp.ok()) {
    throw new Error(`E2E 全局登录失败: HTTP ${resp.status()} ${await resp.text()}`)
  }
  const body = await resp.json()
  // 统一信封 {code, success, data, message, refresh_token...}，兼容已解包形态
  const payload = body?.data ?? body
  const token = payload?.access_token ?? payload?.accessToken
  const refreshToken = payload?.refresh_token ?? payload?.refreshToken ?? ''
  const user = payload?.user
  const mustChange = body?.must_change_password === true
  if (!token || !user) {
    throw new Error('E2E 全局登录响应缺少 access_token/user，无法构造认证态')
  }
  return { token, refreshToken, user, mustChange }
}

async function fetchMe(ctx: ReturnType<typeof request.newContext>, token: string) {
  const resp = await ctx.get(`${API_BASE}/users/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!resp.ok()) {
    throw new Error(`E2E 获取当前用户失败: HTTP ${resp.status()}`)
  }
  const body = await resp.json()
  return (body?.data ?? body) as { id?: number }
}

async function changePassword(
  ctx: ReturnType<typeof request.newContext>,
  token: string,
  userId: number,
  oldPassword: string,
) {
  // 改密为状态变更请求：需先取 CSRF token（响应会同时写入 csrf_token cookie，
  // APIRequestContext 自动携带，形成 cookie+header 配对）
  const csrfResp = await ctx.get(`${API_BASE}/auth/csrf-token`)
  if (!csrfResp.ok()) {
    throw new Error(`E2E 获取 CSRF token 失败: HTTP ${csrfResp.status()}`)
  }
  const csrfBody = await csrfResp.json()
  const csrf = (csrfBody?.data ?? csrfBody)?.csrf_token
  const resp = await ctx.put(`${API_BASE}/users/${userId}/password`, {
    headers: { Authorization: `Bearer ${token}`, 'X-CSRF-Token': csrf },
    data: { old_password: oldPassword, new_password: E2E_PASSWORD },
  })
  if (!resp.ok()) {
    throw new Error(
      `E2E 首登改密失败: HTTP ${resp.status()} ${await resp.text()}`,
    )
  }
}

export default async function globalSetup() {
  const ctx = await request.newContext()

  // 1) 优先尝试 E2E 专用密码（持久库：上次运行已改过）
  let session: Awaited<ReturnType<typeof login>>
  let usedFactory = false
  try {
    session = await login(ctx, E2E_PASSWORD)
  } catch {
    // 2) 全新库：出厂密码（登录成功但 must_change_password=True）
    usedFactory = true
    session = await login(ctx, FACTORY_PASSWORD)
  }

  if (session.mustChange || usedFactory) {
    // 完成首登强制改密：出厂密码 → E2E 专用密码
    const me = await fetchMe(ctx, session.token)
    if (!me?.id) {
      throw new Error('E2E 首登改密失败：无法获取管理员用户 id')
    }
    await changePassword(ctx, session.token, me.id, FACTORY_PASSWORD)
    // 用新密码重新登录构造认证态
    session = await login(ctx, E2E_PASSWORD)
  }
  await ctx.dispose()

  // 把生效密码传给各 spec（login.spec / permission-packs / rural-works 读取）
  process.env.TEST_PASSWORD = E2E_PASSWORD

  fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true })
  const state = {
    cookies: [],
    origins: [
      {
        origin: WEB_ORIGIN,
        localStorage: [
          { name: 'auth_persist_token', value: session.token },
          { name: 'auth_persist_user', value: JSON.stringify(session.user) },
          ...(session.refreshToken
            ? [{ name: 'auth_persist_refresh', value: session.refreshToken }]
            : []),
        ],
      },
    ],
  }
  fs.writeFileSync(AUTH_FILE, JSON.stringify(state, null, 2))
}
