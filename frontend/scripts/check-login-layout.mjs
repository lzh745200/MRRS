/**
 * 登录页排版断言（替代人工看图：当前执行环境不支持图像输入）。
 * 校验：无横向溢出、卡片不出视口、控件 44px、聚焦金色竖条、错误条语义分色。
 */
import { chromium } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'

const BASE = 'http://127.0.0.1:5199'
const OUT = path.resolve('../.scratch/w26-fix/shots')
fs.mkdirSync(OUT, { recursive: true })

const cfg = {
  data: { self_register_enabled: true, lockout_minutes: 30, max_failed_attempts: 5 },
}

const results = []
const check = (name, pass, detail) => {
  results.push({ name, pass, detail })
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? ' — ' + detail : ''}`)
}

const browser = await chromium.launch({ channel: 'msedge' })

async function open(opts = {}) {
  const page = await browser.newPage({ viewport: opts.viewport || { width: 1440, height: 900 } })
  await page.route('**/api/v1/auth/public-config*', (r) =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(opts.config || cfg) })
  )
  if (opts.login) {
    await page.route('**/api/v1/auth/login*', (r) =>
      r.fulfill({
        status: opts.login.status,
        contentType: 'application/json',
        body: JSON.stringify({ detail: opts.login.detail }),
      })
    )
  }
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
  await page.waitForSelector('.login-container')
  await page.waitForTimeout(400)
  return page
}

// ── 桌面端 ─────────────────────────────────────────────
{
  const page = await open()

  const overflow = await page.evaluate(() => ({
    scrollW: document.scrollingElement.scrollWidth,
    clientW: document.documentElement.clientWidth,
  }))
  check('无横向溢出', overflow.scrollW <= overflow.clientW + 1, JSON.stringify(overflow))

  const card = await page.locator('.login-container').boundingBox()
  const vp = page.viewportSize()
  check(
    '卡片完整落在视口内',
    card.x >= 0 && card.y >= 0 && card.x + card.width <= vp.width + 1 && card.y + card.height <= vp.height + 1,
    `card=${Math.round(card.width)}x${Math.round(card.height)} vp=${vp.width}x${vp.height}`
  )

  const inputH = await page.locator('#login-username').evaluate((el) => el.getBoundingClientRect().height)
  const pwdH = await page.locator('#login-password').evaluate((el) => el.getBoundingClientRect().height)
  const btnH = await page.locator('.login-btn').evaluate((el) => el.getBoundingClientRect().height)
  check('输入框高度 44px', Math.abs(inputH - 44) < 0.6 && Math.abs(pwdH - 44) < 0.6, `user=${inputH} pwd=${pwdH}`)
  // 主 CTA 受全站按钮规范约束（实际 48px），只要求不小于输入框且 ≥44px 触控下限
  check(
    '登录按钮 ≥44px 且不矮于输入框',
    btnH >= 44 && btnH >= inputH - 0.6,
    `btn=${btnH} input=${inputH}`
  )

  // 聚焦态：金色左侧竖条（inset box-shadow）
  await page.focus('#login-username')
  await page.waitForTimeout(250)
  const shadow = await page
    .locator('#login-username')
    .evaluate((el) => getComputedStyle(el).boxShadow)
  check('聚焦显示金色竖条(inset)', /inset/i.test(shadow) && /212,\s*175,\s*55/.test(shadow), shadow.slice(0, 80))

  // 背景：只有一张图、无轮播节点
  const bgCount = await page.locator('.login-bg').count()
  const slideCount = await page.locator('.bg-slide').count()
  const bgImage = await page.locator('.login-bg').evaluate((el) => getComputedStyle(el).backgroundImage)
  check('单张静态背景', bgCount === 1 && slideCount === 0, `bg=${bgCount} slide=${slideCount}`)
  check('背景图指向 bg1', bgImage.includes('/images/login-bg/bg1.jpg'), bgImage.slice(0, 90))

  // 品牌字号层级：标题 > 副标题
  const titleSize = await page.locator('.brand-title').evaluate((el) => parseFloat(getComputedStyle(el).fontSize))
  const subSize = await page.locator('.brand-subtitle').evaluate((el) => parseFloat(getComputedStyle(el).fontSize))
  check('品牌标题字号 > 副标题', titleSize > subSize, `title=${titleSize} sub=${subSize}`)

  // 注册入口存在（配置开启）
  await page.click('.first-use-toggle')
  await page.waitForTimeout(250)
  const stepBtns = await page.locator('.step-btn').allTextContents()
  check(
    '首次使用引导三步齐全',
    stepBtns.some((t) => t.includes('机器码')) &&
      stepBtns.some((t) => t.includes('权限包')) &&
      stepBtns.some((t) => t.includes('注册')),
    stepBtns.map((t) => t.trim()).join(' | ')
  )
  const bullets = await page.locator('.first-use-steps li').count()
  check('引导为 3 条编号步骤', bullets === 3, `li=${bullets}`)

  await page.screenshot({ path: path.join(OUT, '01-ready.png') })
  await page.screenshot({ path: path.join(OUT, '02-first-use.png') })
  await page.close()
}

// ── 423 锁定：分色 + 倒计时 + 禁用 ─────────────────────
{
  const page = await open({ login: { status: 423, detail: '账户已锁定，请30分钟后再试' } })
  await page.fill('#login-username', 'admin')
  await page.fill('#login-password', 'wrong')
  await page.click('.login-btn')
  await page.waitForSelector('.alert--warn')
  await page.waitForTimeout(350)

  const borderLeft = await page
    .locator('.alert--warn')
    .evaluate((el) => getComputedStyle(el).borderLeftColor)
  check('锁定提示为琥珀色(warning)', borderLeft.includes('243, 156, 18'), borderLeft)

  const txt = (await page.textContent('.login-btn')) || ''
  const disabled = (await page.getAttribute('.login-btn', 'disabled')) !== null
  check('按钮禁用 + 显示可读倒计时', disabled && /请稍候\s*30\s*分/.test(txt.trim()), txt.trim())

  // 倒计时确实在递减
  const before = txt
  await page.waitForTimeout(1200)
  const after = (await page.textContent('.login-btn')) || ''
  check('倒计时递减', before !== after, `${before.trim()} → ${after.trim()}`)

  await page.screenshot({ path: path.join(OUT, '03-locked.png') })
  await page.close()
}

// ── 403 未授权本机：信息色 + 直达 ──────────────────────
{
  const page = await open({
    login: { status: 403, detail: '您的账户未授权在此机器上登录，请联系管理员' },
  })
  await page.fill('#login-username', 'admin')
  await page.fill('#login-password', 'pw123456')
  await page.click('.login-btn')
  await page.waitForSelector('.alert--info')
  await page.waitForTimeout(300)
  const borderLeft = await page.locator('.alert--info').evaluate((el) => getComputedStyle(el).borderLeftColor)
  check('未授权提示为金色(military gold)', borderLeft.includes('212, 175, 55'), borderLeft)
  check('提供「去获取机器码」直达', (await page.locator('.alert-action').count()) === 1)
  await page.screenshot({ path: path.join(OUT, '04-machine-unauth.png') })
  await page.close()
}

// ── fail-closed ───────────────────────────────────────
{
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await page.route('**/api/v1/auth/public-config*', (r) => r.abort())
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
  await page.waitForSelector('.login-container')
  await page.click('.first-use-toggle')
  await page.waitForTimeout(300)
  const regBtn = await page.locator('.step-btn', { hasText: '注册账户' }).count()
  const note = (await page.locator('.step-note').first().textContent()) || ''
  check('配置失败 → 注册入口隐藏并给说明', regBtn === 0 && note.includes('联系管理员'), note.trim())
  await page.screenshot({ path: path.join(OUT, '05-fail-closed.png') })
  await page.close()
}

// ── 窄屏 420px ────────────────────────────────────────
{
  const page = await open({ viewport: { width: 420, height: 860 } })
  const overflow = await page.evaluate(() => ({
    scrollW: document.scrollingElement.scrollWidth,
    clientW: document.documentElement.clientWidth,
  }))
  check('窄屏无横向溢出', overflow.scrollW <= overflow.clientW + 1, JSON.stringify(overflow))
  await page.screenshot({ path: path.join(OUT, '06-mobile.png'), fullPage: true })
  await page.close()
}

await browser.close()

const failed = results.filter((r) => !r.pass)
console.log(`\n结果：${results.length - failed.length}/${results.length} 通过`)
fs.writeFileSync(path.join(OUT, 'layout-report.json'), JSON.stringify(results, null, 2))
if (failed.length) process.exitCode = 1
