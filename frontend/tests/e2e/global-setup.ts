/**
 * E2E 全局前置：API 登录一次，写入 storageState（localStorage 持久键），
 * 所有 spec 复用认证态——避免每个用例都走 UI 登录触发后端
 * 登录限流（5 次/分钟/IP）导致的随机失败。
 *
 * 应用侧读取链：AuthStorage.getToken() → sessionStorage → localStorage
 * auth_persist_token（"记住登录"持久键）。Playwright storageState 只支持
 * localStorage（sessionStorage 为标签页级，无法预置），因此写入 persist 键。
 */
import { request } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export const AUTH_FILE = path.join(__dirname, '.auth', 'admin.json')

const API_BASE = process.env.E2E_API_URL || 'http://127.0.0.1:8000/api/v1'
const WEB_ORIGIN = process.env.E2E_BASE_URL || 'http://127.0.0.1:5173'

export default async function globalSetup() {
  const username = process.env.TEST_USERNAME || 'admin'
  const password = process.env.TEST_PASSWORD || 'Admin@202507!'

  const ctx = await request.newContext()
  const resp = await ctx.post(`${API_BASE}/auth/login`, {
    data: { username, password },
  })
  if (!resp.ok()) {
    throw new Error(`E2E 全局登录失败: HTTP ${resp.status()} ${await resp.text()}`)
  }
  const body = await resp.json()
  await ctx.dispose()

  // 统一信封 {code, success, data, message}，后端可能已解包，兼容两种形态
  const payload = body?.data ?? body
  const token = payload?.access_token ?? payload?.accessToken
  const refreshToken = payload?.refresh_token ?? payload?.refreshToken ?? ''
  const user = payload?.user
  if (!token || !user) {
    throw new Error('E2E 全局登录响应缺少 access_token/user，无法构造认证态')
  }

  fs.mkdirSync(path.dirname(AUTH_FILE), { recursive: true })
  const state = {
    cookies: [],
    origins: [
      {
        origin: WEB_ORIGIN,
        localStorage: [
          { name: 'auth_persist_token', value: token },
          { name: 'auth_persist_user', value: JSON.stringify(user) },
          ...(refreshToken ? [{ name: 'auth_persist_refresh', value: refreshToken }] : []),
        ],
      },
    ],
  }
  fs.writeFileSync(AUTH_FILE, JSON.stringify(state, null, 2))
}
