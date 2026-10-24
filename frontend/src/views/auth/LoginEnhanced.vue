<template>
  <div class="login-page">
    <!--
      静态单背景（W27 UI 优化）：
      原来 12 张 JPG 共 3.51MB 全量预加载 + 5s 轮播，是 Electron 冷启动首屏的主要负担，
      且风景轮播对军警/政务系统是气质减分项。现改为 1 张静态图 + 深绿渐变叠加
      （保证任意背景图下表单文字对比度稳定）；图片加载失败时由 .login-bg 的
      background-color（Token）兜底，不出现白屏/黑屏。
    -->
    <div
      class="login-bg"
      aria-hidden="true"
      :style="{ backgroundImage: `url(${LOGIN_BACKGROUND})` }"
    ></div>
    <div class="login-bg-overlay" aria-hidden="true"></div>

    <div class="login-container">
      <!-- 左侧品牌区 -->
      <div class="brand-section">
        <div class="logo-wrapper">
          <img src="/images/badges/badge.png" alt="徽章" class="badge-image" />
        </div>
        <h1 class="brand-title">帮扶管理信息系统</h1>
        <p class="brand-subtitle">地方所需 群众所盼 帮扶所能</p>
      </div>

      <!-- 右侧登录卡片 -->
      <div class="login-card">
        <div class="card-header">
          <h2>{{ twoFactorRequired ? '双因素认证' : '用户登录' }}</h2>
          <p>
            {{
              twoFactorRequired ? '请输入认证器中的 6 位验证码' : '请输入您的账号、密码与机器校验码'
            }}
          </p>
        </div>

        <!--
          结构化提示条（W27）：原实现把所有失败压成一条红字，
          用户被锁定/限流时不知道还要等多久。现按类型分色 + 倒计时 + 可选直达动作。
        -->
        <div
          v-if="alert"
          class="alert"
          :class="`alert--${alert.type}`"
          role="alert"
          aria-live="assertive"
        >
          <span class="alert-text">{{ alert.text }}</span>
          <button
            v-if="alert.action === 'machine-code'"
            type="button"
            class="alert-action"
            @click="goToMachineCode"
          >
            去获取机器码
          </button>
        </div>

        <form class="login-form" novalidate @submit.prevent="handleLogin">
          <!-- 2FA 验证模式 -->
          <template v-if="twoFactorRequired">
            <div class="form-group">
              <label for="login-totp-code">双因素认证验证码</label>
              <div class="input-wrapper">
                <el-icon class="input-icon"><Key /></el-icon>
                <input
                  id="login-totp-code"
                  ref="totpInput"
                  v-model="totpCode"
                  type="text"
                  placeholder="请输入 6 位验证码"
                  class="custom-input"
                  maxlength="6"
                  inputmode="numeric"
                  pattern="[0-9]*"
                  autocomplete="one-time-code"
                  autofocus
                  @input="onTotpInput"
                />
              </div>
              <p class="hint-text">输满 6 位将自动验证，无需再点按钮</p>
            </div>

            <button type="submit" class="login-btn" :disabled="busy">
              <span v-if="!busy">验证并登录</span>
              <span v-else>验证中...</span>
            </button>

            <button type="button" class="back-btn" :disabled="loading" @click="resetTwoFactor">
              返回重新登录
            </button>
          </template>

          <!-- 正常登录模式 -->
          <template v-else>
            <div class="form-group">
              <label for="login-username">账号</label>
              <div class="input-wrapper">
                <el-icon class="input-icon"><User /></el-icon>
                <input
                  id="login-username"
                  ref="usernameInput"
                  v-model="username"
                  type="text"
                  placeholder="请输入用户名"
                  class="custom-input"
                  autocomplete="username"
                  autofocus
                />
              </div>
            </div>

            <div class="form-group">
              <label for="login-password">密码</label>
              <div class="input-wrapper">
                <el-icon class="input-icon"><Lock /></el-icon>
                <input
                  id="login-password"
                  ref="passwordInput"
                  v-model="password"
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="请输入密码"
                  class="custom-input"
                  autocomplete="current-password"
                  @keyup="onPasswordKeyup"
                />
                <!-- 用原生 button 承载密码可见性切换：span+@click 无法键盘聚焦/触发，
                     读屏与纯键盘用户无法操作。type=button 避免触发 form 提交。 -->
                <button
                  type="button"
                  class="toggle-password"
                  :aria-label="showPassword ? '隐藏密码' : '显示密码'"
                  :aria-pressed="showPassword"
                  @click="showPassword = !showPassword"
                >
                  <el-icon v-if="showPassword"><View /></el-icon>
                  <el-icon v-else><Hide /></el-icon>
                </button>
              </div>
              <!-- 大写锁定提示：政务场景密码含大写字母，CapsLock 忘记关是最常见的登录失败原因 -->
              <p v-if="capsLockOn" class="field-hint field-hint--warn" role="status">
                大写锁定已开启，请输入小写字母或先关闭 CapsLock
              </p>
            </div>

            <!-- 机器码验证（可选） -->
            <div v-if="showMachineCodeInput" class="form-group">
              <label for="login-machine-code">机器码验证</label>
              <div class="input-wrapper">
                <el-icon class="input-icon"><Key /></el-icon>
                <input
                  id="login-machine-code"
                  v-model="verificationCode"
                  type="text"
                  placeholder="请输入 4 位校验码"
                  class="custom-input"
                  maxlength="4"
                />
              </div>
              <p class="hint-text">本机尚未授权登录，请向管理员索取 4 位校验码</p>
            </div>

            <button type="submit" class="login-btn" :disabled="busy">
              <span v-if="loading">登录中...</span>
              <span v-else-if="lockRemaining > 0">请稍候 {{ lockLabel }}</span>
              <span v-else>立即登录</span>
            </button>

            <div class="login-extras">
              <label class="remember-me">
                <input v-model="rememberMe" type="checkbox" />
                <span>记住登录</span>
              </label>
              <a href="#" class="text-link" @click.prevent="goToForgotPassword">忘记密码？</a>
            </div>
          </template>
        </form>

        <!-- 首次使用三步引导：把原本散落在角落的机器码/权限包/通行码入口收成一条上手路径 -->
        <section class="first-use">
          <button
            type="button"
            class="first-use-toggle"
            :aria-expanded="firstUseOpen"
            aria-controls="first-use-steps"
            @click="firstUseOpen = !firstUseOpen"
          >
            <span>首次使用？查看开通步骤</span>
            <span class="chev" :class="{ 'is-open': firstUseOpen }" aria-hidden="true">▾</span>
          </button>
          <ol v-show="firstUseOpen" id="first-use-steps" class="first-use-steps">
            <li>
              <span class="step-no" aria-hidden="true">1</span>
              <div class="step-body">
                <p class="step-title">获取本机机器码</p>
                <button type="button" class="step-btn" @click="goToMachineCode">
                  打开机器码页
                </button>
              </div>
            </li>
            <li>
              <span class="step-no" aria-hidden="true">2</span>
              <div class="step-body">
                <p class="step-title">导入管理员导出的权限包（.zip）</p>
                <button type="button" class="step-btn" @click="openPermissionImport">
                  导入权限包
                </button>
              </div>
            </li>
            <li>
              <span class="step-no" aria-hidden="true">3</span>
              <div class="step-body">
                <p class="step-title">用通行码注册账号</p>
                <button v-if="canSelfRegister" type="button" class="step-btn" @click="goToRegister">
                  注册账户
                </button>
                <p v-else class="step-note">本机未开启自助注册，请联系管理员开通账号</p>
              </div>
            </li>
          </ol>
        </section>

        <!-- 权限包导入对话框 -->
        <el-dialog
          v-model="permissionImportVisible"
          append-to-body
          title="导入权限配置包"
          :width="DIALOG_SM"
          :close-on-click-modal="false"
        >
          <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
            选择管理员导出的权限配置包(.zip),导入后即可获得管理员配置的
            页面访问权限。导入仅需本机操作,无需登录。
          </el-alert>
          <div class="permission-import-drop">
            <el-upload
              drag
              :auto-upload="false"
              :limit="1"
              accept=".zip"
              :on-change="onPermissionFileChange"
              :on-remove="onPermissionFileRemove"
              :file-list="permissionFileList"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">将权限包拖到此处，或<em>点击选择</em></div>
              <template #tip>
                <div class="el-upload__tip">仅支持 .zip 格式的权限配置包文件</div>
              </template>
            </el-upload>
          </div>
          <template #footer>
            <el-button @click="permissionImportVisible = false">取消</el-button>
            <el-button
              type="primary"
              :loading="permissionImporting"
              :disabled="!permissionFile"
              @click="handlePermissionImport"
            >
              导入并应用
            </el-button>
          </template>
        </el-dialog>

        <div class="card-footer">
          <p class="copyright">© 2026 V{{ systemVersion }} {{ copyrightOwner }}版权所有</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_SM } from '@/config/dialog'
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { SYSTEM_VERSION, COPYRIGHT_OWNER } from '@/config/constants'
import { User, Lock, Key, View, Hide, UploadFilled } from '@element-plus/icons-vue'
import { AuthStorage } from '@/utils/authStorage'
import { logger } from '@/utils/logger'
import type { UploadFile, UploadUserFile } from 'element-plus'
import { get, post } from '@/api/request'

const router = useRouter()
const { pushSafe } = useRouterSafe()
const authStore = useAuthStore()

/** 登录页背景图（单张静态；换图只改这一处） */
const LOGIN_BACKGROUND = '/images/login-bg/bg1.jpg'

/** 429 限流后的默认冷却秒数（后端未透出具体值，取与后端提示一致的保守值） */
const RATE_LIMIT_COOLDOWN_SECONDS = 60

interface PublicConfig {
  self_register_enabled: boolean
  lockout_minutes: number
  max_failed_attempts: number
}

/**
 * 登录页公开配置（`GET /auth/public-config`，无需登录、不含敏感信息）。
 *
 * **fail-closed 默认值**：全部取"最保守"（不允许自助注册、无倒计时可用）。
 * 若请求失败（后端未就绪/超时），注册入口保持隐藏 —— 宁可不显示，
 * 也不给用户一个点了必然失败的链接（W27 修复「注册账户死链」）。
 */
const DEFAULT_PUBLIC_CONFIG: PublicConfig = {
  self_register_enabled: false,
  lockout_minutes: 0,
  max_failed_attempts: 0,
}

const publicConfig = ref<PublicConfig>({ ...DEFAULT_PUBLIC_CONFIG })
const canSelfRegister = computed(() => publicConfig.value.self_register_enabled === true)

const username = ref('')
const password = ref('')
const verificationCode = ref('')
const rememberMe = ref(false)
const loading = ref(false)
const showPassword = ref(false)
const showMachineCodeInput = ref(false)
const firstUseOpen = ref(false)
const capsLockOn = ref(false)
const systemVersion = SYSTEM_VERSION
const copyrightOwner = COPYRIGHT_OWNER

const usernameInput = ref<HTMLInputElement | null>(null)
const passwordInput = ref<HTMLInputElement | null>(null)
const totpInput = ref<HTMLInputElement | null>(null)

/**
 * 结构化提示（替代原「一条红字」）。
 *
 * `errorMsg` 保留为**文案单一来源**（既有测试直接读 `vm.errorMsg`），
 * `alertType` / `alertAction` 承载语义，模板统一从 `alert` 计算属性渲染。
 * 三者由 `setAlert()` 一并维护，避免出现"有文案无颜色"或反之的中间态。
 */
const errorMsg = ref('')
const alertType = ref<'danger' | 'warn' | 'info'>('danger')
const alertAction = ref<'machine-code' | null>(null)

interface LoginAlert {
  type: 'danger' | 'warn' | 'info'
  text: string
  action?: 'machine-code'
}

const alert = computed<LoginAlert | null>(() => {
  if (!errorMsg.value) return null
  return {
    type: alertType.value,
    text: errorMsg.value,
    ...(alertAction.value ? { action: alertAction.value } : {}),
  }
})

/** 设置/清空提示（传 null 清空） */
function setAlert(next: LoginAlert | null) {
  if (!next) {
    errorMsg.value = ''
    alertAction.value = null
    return
  }
  alertType.value = next.type
  alertAction.value = next.action ?? null
  errorMsg.value = next.text
}

/** 锁定/限流倒计时（秒）。>0 时提交按钮禁用，倒计时结束自动恢复。 */
const lockRemaining = ref(0)
let lockTimer: number | null = null

/** 提交按钮是否不可用（加载中 或 冷却中） */
const busy = computed(() => loading.value || lockRemaining.value > 0)

/**
 * 冷却剩余时间的可读文案。
 *
 * 锁定时长按**分钟**计（默认 30 分钟 = 1800 秒），按钮上直接写 "请稍候 1800s"
 * 既难读也会把按钮文字挤到换行；故 ≥1 分钟用 `X 分 YY 秒`，不足 1 分钟用 `N 秒`。
 */
const lockLabel = computed(() => {
  const total = lockRemaining.value
  if (total <= 0) return ''
  if (total < 60) return `${total} 秒`
  return `${Math.floor(total / 60)} 分 ${String(total % 60).padStart(2, '0')} 秒`
})

/** 清空所有计时器（卸载时调用，避免内存泄漏与卸载后 setState） */
function clearLockTimer() {
  if (lockTimer !== null) {
    window.clearInterval(lockTimer)
    lockTimer = null
  }
}

/**
 * 启动冷却倒计时。
 * @param seconds 倒计时秒数；<=0 视为不启动（保持按钮可用，由后端继续把关）
 */
function startLockCountdown(seconds: number) {
  clearLockTimer()
  if (!Number.isFinite(seconds) || seconds <= 0) {
    lockRemaining.value = 0
    return
  }
  lockRemaining.value = Math.floor(seconds)
  lockTimer = window.setInterval(() => {
    lockRemaining.value -= 1
    if (lockRemaining.value <= 0) {
      lockRemaining.value = 0
      clearLockTimer()
    }
  }, 1000)
}

/** 登录失败类型（决定提示颜色、倒计时与直达动作） */
type LoginFailureKind =
  | 'locked'
  | 'rate-limited'
  | 'inactive'
  | 'machine-unauthorized'
  | 'auth'
  | 'system'

/**
 * 分类登录失败。
 *
 * `authStore.login()` 把 HTTP 状态码吞掉了（只返回 `{status,message}`），
 * 而规格要求**不改认证语义**，故这里优先读可选的 `httpStatus`（若将来 store 透出），
 * 否则回落到后端稳定错误文案匹配。两种依据都有单测锁定。
 */
function classifyLoginFailure(
  result: { message?: string; httpStatus?: number } | undefined
): LoginFailureKind {
  const status = result?.httpStatus
  const message = String(result?.message || '')
  if (status === 423 || message.includes('锁定')) return 'locked'
  if (status === 429 || message.includes('频繁')) return 'rate-limited'
  if (message.includes('未激活')) return 'inactive'
  if (message.includes('未授权')) return 'machine-unauthorized'
  if (status === 401 || message) return 'auth'
  return 'system'
}

/** 各失败类型的兜底文案（接口/store 都没给 message 时使用） */
const FAILURE_DEFAULT_TEXT: Record<LoginFailureKind, string> = {
  locked: '账户已锁定，请稍后再试',
  'rate-limited': '登录尝试过于频繁，请稍后再试',
  inactive: '账户尚未激活，请联系管理员',
  'machine-unauthorized': '本机未授权登录，请先获取机器码并联系管理员',
  auth: '用户名或密码错误',
  system: '登录失败',
}

/** 取失败文案：优先接口/store 的原文，缺失时按类型兜底（纯函数，便于逐类型单测） */
function failureText(kind: LoginFailureKind, message: string): string {
  return message || FAILURE_DEFAULT_TEXT[kind]
}

/** 按失败类型生成结构化提示（并启动需要的倒计时） */
function applyLoginFailure(result: { message?: string; httpStatus?: number } | undefined) {
  const kind = classifyLoginFailure(result)
  // 文案来源顺序与改造前一致：接口返回 message → store.error → 类型兜底。
  // store 的 error 是 authStore.login 内部记录的同一份错误（含网络异常场景），
  // 丢掉它会让"接口没给 message"的情况退化成无信息提示。
  const message = String(result?.message || authStore.error || '')
  const text = failureText(kind, message)
  if (kind === 'locked') {
    // 锁定期间按钮禁用：优先用后端透出的锁定分钟数（public-config），
    // 取不到（=0）时不倒计时，仅提示 —— 前端**不假定**解锁时间
    const minutes = publicConfig.value.lockout_minutes
    startLockCountdown(minutes > 0 ? minutes * 60 : 0)
    setAlert({ type: 'warn', text })
    return
  }
  if (kind === 'rate-limited') {
    startLockCountdown(RATE_LIMIT_COOLDOWN_SECONDS)
    setAlert({ type: 'warn', text })
    return
  }
  if (kind === 'machine-unauthorized') {
    setAlert({ type: 'info', text, action: 'machine-code' })
    return
  }
  setAlert({ type: 'danger', text })
}

/** 拉取登录页公开配置；失败静默降级（fail-closed：注册入口保持隐藏） */
async function loadPublicConfig() {
  try {
    const res: any = await get('/auth/public-config')
    const data: any = res?.data ?? res ?? {}
    publicConfig.value = {
      self_register_enabled: data.self_register_enabled === true,
      lockout_minutes: Number(data.lockout_minutes) || 0,
      max_failed_attempts: Number(data.max_failed_attempts) || 0,
    }
  } catch (err) {
    logger.warn('[Login] 拉取登录页公开配置失败，按最保守策略降级', err)
    publicConfig.value = { ...DEFAULT_PUBLIC_CONFIG }
  }
}

// 权限包导入状态
const permissionImportVisible = ref(false)
const permissionImporting = ref(false)
const permissionFileList = ref<UploadUserFile[]>([])
const permissionFile = ref<File | null>(null)

function openPermissionImport() {
  permissionImportVisible.value = true
}

function onPermissionFileChange(file: UploadFile) {
  const raw = file.raw
  if (!raw) return
  if (!(raw.name || '').toLowerCase().endsWith('.zip')) {
    ElMessage.error('仅支持 .zip 格式的权限配置包')
    permissionFileList.value = []
    permissionFile.value = null
    return
  }
  permissionFile.value = raw
}

function onPermissionFileRemove() {
  permissionFile.value = null
}

async function handlePermissionImport() {
  if (!permissionFile.value) return
  permissionImporting.value = true
  try {
    const formData = new FormData()
    formData.append('file', permissionFile.value)
    // 使用 post() 封装（内部会为 FormData 正确处理 multipart boundary；
    // 直接 apiRequest + 手动 Content-Type 会导致 boundary 缺失）
    const res: any = await post('/permission-packages/import', formData)
    const body: any = res || {}
    // Phase E：加密包重试
    let _body = body
    if (
      (body.success === false || body.code !== 200) &&
      /加密/.test(body.message || body.detail || '')
    ) {
      try {
        const { value } = await ElMessageBox.prompt(
          '该权限包已加密，请输入导出时设置的密码：',
          '解密密码',
          { inputType: 'password', inputValidator: (v: string) => (v ? true : '密码不能为空') }
        )
        const fd2 = new FormData()
        fd2.append('file', permissionFile.value)
        fd2.append('password', value || '')
        const r2: any = await post('/permission-packages/import', fd2)
        _body = r2 || {}
      } catch {
        ElMessage.error('已取消导入')
        return
      }
    }
    const success2 = _body.success === true || _body.code === 200
    const savedFileName =
      _body.saved_file_name || _body.file_name || permissionFile.value?.name || ''
    if (success2 && savedFileName) {
      // 预览验证通过 → 确认导入
      const confirmRes: any = await post(
        `/permission-packages/confirm/${encodeURIComponent(savedFileName)}`,
        { overwrite_existing: true }
      )
      const confirmBody: any = confirmRes || {}
      if (confirmBody.success === true || confirmBody.code === 200) {
        ElMessage.success('权限包已导入,请重新登录查看权限')
        permissionImportVisible.value = false
        permissionFileList.value = []
        permissionFile.value = null
      } else {
        ElMessage.error(confirmBody.message || confirmBody.detail || '权限包应用失败')
      }
    } else {
      // 读 _body（加密包重传后的响应）而非首次 body：重传失败（如密码错误）时
      // 应展示重传返回的真实错误，而不是首次那句「该权限包已加密」误导排查。
      // 非加密路径下 _body === body（初始化），行为完全不变。
      ElMessage.error(_body.message || _body.detail || '权限包验证失败')
    }
  } catch (err: any) {
    logger.error('[Login] 导入权限包失败', err)
    ElMessage.error(err?.response?.data?.detail || err?.message || '导入权限包失败,请检查文件')
  } finally {
    permissionImporting.value = false
  }
}

// 2FA 状态
const twoFactorRequired = ref(false)
const totpCode = ref('')
const tempToken = ref('')

/**
 * 2FA 验证码输入处理：满 6 位自动提交。
 *
 * 防重复：`handleLogin` 内部 `if (busy) return` 已兜住并发的第二次触发；
 * 这里再判 `loading` 避免输入事件连发导致多次请求。
 */
function onTotpInput() {
  const digits = totpCode.value.replace(/\D/g, '').slice(0, 6)
  if (digits !== totpCode.value) totpCode.value = digits
  if (digits.length === 6 && !loading.value) {
    void handleLogin()
  }
}

/** 大写锁定检测：不支持 getModifierState 的环境静默不提示 */
function onPasswordKeyup(event: KeyboardEvent) {
  const supported = typeof event?.getModifierState === 'function'
  capsLockOn.value = supported ? event.getModifierState('CapsLock') === true : false
}

onMounted(() => {
  void loadPublicConfig()
  // 自动聚焦账号（autofocus 属性在部分容器内不生效，这里显式兜底）
  usernameInput.value?.focus?.()
})

onUnmounted(() => {
  clearLockTimer()
})

const handleLogin = async () => {
  if (busy.value) return

  // 2FA 验证模式
  if (twoFactorRequired.value) {
    if (!totpCode.value || totpCode.value.length < 6) {
      setAlert({ type: 'info', text: '请输入 6 位 TOTP 验证码' })
      return
    }

    loading.value = true
    setAlert(null)

    try {
      const success = await authStore.verifyTwoFactorLogin(tempToken.value, totpCode.value)
      if (success) {
        applyRememberLogin()
        navigateAfterLogin()
        return
      }
      setAlert({ type: 'danger', text: authStore.error || '2FA 验证失败，请检查验证码后重试' })
      // 失败即清空并重新聚焦，避免用户反复提交同一错误码
      totpCode.value = ''
      totpInput.value?.focus?.()
    } catch (err: any) {
      setAlert({ type: 'danger', text: '2FA 验证异常: ' + (err.message || '未知错误') })
      totpCode.value = ''
      totpInput.value?.focus?.()
    } finally {
      loading.value = false
    }
    return
  }

  // 正常登录模式
  if (!username.value || !password.value) {
    setAlert({ type: 'info', text: '请输入用户名和密码' })
    if (!username.value) usernameInput.value?.focus?.()
    else passwordInput.value?.focus?.()
    return
  }

  loading.value = true
  setAlert(null)

  try {
    const result = await authStore.login(username.value, password.value)

    if (result.status === 'two_factor_required') {
      // 切换到 2FA 验证模式
      twoFactorRequired.value = true
      tempToken.value = (result as { tempToken?: string }).tempToken || ''
      totpCode.value = ''
      return
    }

    if (result.status === 'success') {
      applyRememberLogin()
      navigateAfterLogin()
      return
    }

    // 失败：分类提示 + 清空密码并聚焦（政务场景多人共用一台机器，
    // 残留密码既不方便也不安全）
    applyLoginFailure(result as { message?: string; httpStatus?: number })
    password.value = ''
    passwordInput.value?.focus?.()
  } catch (err: any) {
    setAlert({ type: 'danger', text: '登录系统异常: ' + (err.message || '未知错误') })
    password.value = ''
    passwordInput.value?.focus?.()
  } finally {
    loading.value = false
  }
}

/**
 * 记住登录：勾选时持久化认证数据（含刷新令牌，供本机自动登录/静默续期），
 * 未勾选时清除历史持久数据。
 */
const applyRememberLogin = () => {
  if (rememberMe.value) {
    const authData = authStore.getAuthData?.()
    if (authData) {
      AuthStorage.persistForAutoLogin(authData)
    }
  } else {
    AuthStorage.clearPersisted()
  }
}

/** 登录成功后的导航逻辑 */
const navigateAfterLogin = () => {
  const redirect = router.currentRoute.value.query.redirect

  // 首次登录 → 跳转修改密码页（保留原始重定向目标）
  if (authStore.mustChangePassword) {
    const target =
      typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')
        ? `/change-password?redirect=${encodeURIComponent(redirect)}`
        : '/change-password'
    pushSafe(target)
    return
  }

  // 安全校验：仅允许站内相对路径跳转
  if (typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')) {
    pushSafe(redirect)
    return
  }

  pushSafe('/dashboard')
}

const resetTwoFactor = () => {
  twoFactorRequired.value = false
  totpCode.value = ''
  tempToken.value = ''
  setAlert(null)
}

const goToForgotPassword = () => {
  pushSafe('/forgot-password')
}

const goToRegister = () => {
  pushSafe('/register')
}

const goToMachineCode = () => {
  pushSafe('/get-machine-code')
}
</script>

<style lang="scss" scoped>
/*
  颜色一律走 Design Token（`src/styles/tokens.scss`）：
  W27 把原先 4 处硬编码色值（#f0e68c / #a8dadc / #0a1a12 / #e0c048）与两处 rgba 收进 Token，
  硬编码色棘轮因此只减不增。
*/
.login-page {
  --military-dark: var(--color-primary-dark-2);
  --military-green: var(--color-primary-dark-1);
  --military-gold: var(--color-accent-gold);
  --military-gold-light: var(--color-badge-gold-lighter);
  --text-white: var(--color-bg-card);
  --text-gray: var(--color-white-60);
}

.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--color-primary-dark-2);
  position: relative;
  overflow-y: auto;
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

/* 静态单背景 */
.login-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  background-size: cover;
  background-position: center;
  /* 图片加载失败/未就绪时的底色（Token，不露白屏） */
  background-color: var(--color-primary-dark-2);
}

.login-bg-overlay {
  position: absolute;
  inset: 0;
  z-index: 0;
  background: linear-gradient(
    135deg,
    var(--color-primary-dark-a50) 0%,
    var(--color-primary-dark-1) 100%
  );
  opacity: 0.92;
}

.login-container {
  display: flex;
  width: 950px;
  max-width: 95vw;
  max-height: 95vh;
  background: var(--color-white-8);
  backdrop-filter: blur(20px);
  border-radius: 16px;
  border: 1px solid var(--color-white-15);
  box-shadow: 0 25px 50px -12px var(--color-black-50);
  z-index: 1;
  overflow: hidden auto;
  /* 入场动效：一次淡入上移，克制不喧宾夺主 */
  animation: login-card-in 260ms ease-out both;
}

@keyframes login-card-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-container {
    animation: none;
  }
}

/* 左侧品牌区 */
.brand-section {
  flex: 1;
  background: linear-gradient(
    135deg,
    var(--color-primary-dark-1) 0%,
    var(--color-primary-dark-2) 100%
  );
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: var(--text-white);
  padding: 50px 40px;
  position: relative;
}

.logo-wrapper {
  width: 120px;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 30px;
  border-radius: 50%;
  overflow: hidden;
}

.badge-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
  filter: drop-shadow(0 4px 8px var(--color-black-30));
}

.brand-title {
  font-size: 34px;
  font-weight: bold;
  text-align: center;
  margin: 0 0 20px 0;
  line-height: 1.4;
  letter-spacing: 3px;
  color: var(--military-gold);
  text-shadow: 0 2px 4px var(--color-black-30);
}

.brand-subtitle {
  color: var(--military-gold-light);
  font-size: 16px;
  letter-spacing: 4px;
  text-align: center;
  margin: 0;
  padding: 12px 20px;
  border: 1px solid var(--color-gold-a30);
  border-radius: var(--radius-card);
  background: var(--color-gold-a10);
}

/* 右侧登录卡片 */
.login-card {
  flex: 1;
  padding: 44px 52px;
  background: var(--color-white-15);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-left: 1px solid var(--color-white-20);
}

.card-header {
  text-align: center;
  margin-bottom: 26px;
}

.card-header h2 {
  font-size: 26px;
  color: var(--color-text-inverse);
  margin: 0 0 10px 0;
  font-weight: 600;
  text-shadow: 0 2px 4px var(--color-black-30);
}

.card-header p {
  color: var(--color-white-80);
  font-size: 14px;
  margin: 0;
}

/* 结构化提示条：按类型分色（危险/警告/信息），不再一律红字 */
.alert {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: var(--radius-card);
  font-size: 14px;
  line-height: 1.5;
  margin-bottom: 16px;
  border: 1px solid transparent;
  border-left-width: 3px;
  background: var(--color-white-10);
  animation: alert-shake 320ms ease-in-out 1;
}

.alert--danger {
  color: var(--color-danger-lighter);
  border-left-color: var(--color-danger);
}

.alert--warn {
  color: var(--color-warning-light-5);
  border-left-color: var(--color-warning);
}

.alert--info {
  color: var(--color-white-90);
  border-left-color: var(--military-gold);
}

.alert-text {
  flex: 1;
}

.alert-action {
  flex: none;
  padding: 6px 12px;
  border-radius: var(--radius-control, 6px);
  border: 1px solid var(--military-gold);
  background: var(--color-gold-a10);
  color: var(--military-gold-light);
  font-size: 13px;
  cursor: pointer;
  transition: background-color 160ms ease;
}

.alert-action:hover {
  background: var(--color-gold-a20);
}

@keyframes alert-shake {
  0%,
  100% {
    transform: translateX(0);
  }
  25% {
    transform: translateX(-3px);
  }
  75% {
    transform: translateX(3px);
  }
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  font-size: 14px;
  color: var(--color-white-90);
  margin-bottom: 8px;
  font-weight: 500;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 14px;
  font-size: 18px;
  color: var(--color-white-60);
  z-index: 1;
  display: flex;
  align-items: center;
}

.custom-input {
  width: 100%;
  height: 44px;
  padding: 0 45px;
  border: 2px solid var(--color-white-30);
  border-radius: var(--radius-card);
  font-size: 15px;
  transition:
    border-color 160ms ease,
    background-color 160ms ease,
    box-shadow 160ms ease;
  background: var(--color-white-10);
  color: var(--color-text-inverse);
  box-sizing: border-box;
}

.custom-input::placeholder {
  color: var(--color-white-50);
}

/* 聚焦态：金色边框 + 左侧 2px 金色竖条（复用侧栏"当前板块"同款视觉语言） */
.custom-input:focus {
  outline: none;
  border-color: var(--military-gold);
  background: var(--color-white-20);
  box-shadow:
    inset 2px 0 0 0 var(--military-gold),
    0 0 0 4px var(--color-gold-a20);
}

.toggle-password {
  position: absolute;
  right: 14px;
  font-size: 18px;
  cursor: pointer;
  user-select: none;
  transition: transform 160ms;
  filter: brightness(1.2);
  display: flex;
  align-items: center;
  /* 语义化为原生 button 后清除浏览器默认外观，保持与原 span 一致的视觉 */
  border: none;
  background: transparent;
  padding: 0;
  color: inherit;
}

.toggle-password:hover {
  transform: scale(1.1);
}

.hint-text {
  font-size: 12px;
  color: var(--color-white-60);
  margin: 6px 0 0 0;
  line-height: 1.4;
}

.field-hint {
  font-size: 12px;
  margin: 6px 0 0 0;
  line-height: 1.4;
  color: var(--color-white-60);
}

.field-hint--warn {
  color: var(--color-warning-light-5);
}

.login-btn {
  width: 100%;
  height: 44px;
  background: linear-gradient(135deg, var(--military-gold), var(--color-accent-gold));
  color: var(--military-dark);
  border: none;
  border-radius: var(--radius-card);
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition:
    transform 160ms ease,
    box-shadow 160ms ease,
    background-color 160ms ease;
  margin-top: 8px;
  box-shadow: 0 4px 15px var(--color-gold-a40);
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px var(--color-gold-a50);
  background: linear-gradient(135deg, var(--color-badge-gold-light), var(--military-gold));
}

.login-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.back-btn {
  width: 100%;
  height: 44px;
  background: transparent;
  color: var(--color-white-80);
  border: 1px solid var(--color-white-30);
  border-radius: var(--radius-card);
  font-size: 14px;
  cursor: pointer;
  transition:
    border-color 160ms ease,
    color 160ms ease;
  margin-top: 12px;
}

.back-btn:hover:not(:disabled) {
  border-color: var(--military-gold);
  color: var(--military-gold-light);
}

.back-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.login-extras {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14px;
  gap: 12px;
}

.remember-me {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--color-white-80);
  cursor: pointer;
  user-select: none;
}

.remember-me input {
  accent-color: var(--military-gold);
  cursor: pointer;
}

.text-link {
  font-size: 13px;
  color: var(--military-gold-light);
  text-decoration: none;
  transition: color 160ms ease;
}

.text-link:hover {
  color: var(--military-gold);
  text-decoration: underline;
}

/* 首次使用三步引导 */
.first-use {
  margin-top: 22px;
  border-top: 1px solid var(--color-white-15);
  padding-top: 14px;
}

.first-use-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 2px;
  background: transparent;
  border: none;
  color: var(--color-white-80);
  font-size: 13px;
  cursor: pointer;
  transition: color 160ms ease;
}

.first-use-toggle:hover {
  color: var(--military-gold-light);
}

.chev {
  transition: transform 160ms ease;
}

.chev.is-open {
  transform: rotate(180deg);
}

.first-use-steps {
  list-style: none;
  margin: 10px 0 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.first-use-steps li {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.step-no {
  flex: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1px solid var(--color-gold-a40);
  background: var(--color-gold-a10);
  color: var(--military-gold-light);
  font-size: 12px;
  line-height: 18px;
  text-align: center;
}

.step-body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.step-title {
  margin: 0;
  font-size: 13px;
  color: var(--color-white-80);
  line-height: 1.5;
}

.step-note {
  margin: 0;
  font-size: 12px;
  color: var(--color-white-60);
  line-height: 1.5;
}

.step-btn {
  flex: none;
  padding: 5px 12px;
  border-radius: var(--radius-control, 6px);
  border: 1px solid var(--color-white-30);
  background: var(--color-white-8);
  color: var(--color-white-90);
  font-size: 12px;
  cursor: pointer;
  transition:
    border-color 160ms ease,
    color 160ms ease;
}

.step-btn:hover {
  border-color: var(--military-gold);
  color: var(--military-gold-light);
}

.card-footer {
  margin-top: 20px;
  text-align: center;
}

.copyright {
  font-size: 12px;
  color: var(--color-white-60);
  margin: 0;
}

/* 响应式 */
@media (max-height: 780px) {
  .login-container {
    width: 880px;
  }

  .brand-section {
    padding: 28px 28px;
  }

  .logo-wrapper {
    width: 76px;
    height: 76px;
    margin-bottom: 14px;
  }

  .brand-title {
    font-size: 26px;
    margin-bottom: 12px;
  }

  .brand-subtitle {
    font-size: 14px;
    padding: 8px 16px;
  }

  .login-card {
    padding: 24px 36px;
  }

  .card-header {
    margin-bottom: 16px;
  }

  .card-header h2 {
    font-size: 22px;
  }

  .form-group {
    margin-bottom: 14px;
  }

  .first-use {
    margin-top: 14px;
    padding-top: 10px;
  }

  .card-footer {
    margin-top: 12px;
  }
}

@media (max-width: 900px) {
  .login-container {
    flex-direction: column;
    width: 95%;
    max-width: 500px;
    max-height: none;
  }

  .brand-section {
    padding: 28px 24px;
  }

  .brand-title {
    font-size: 24px;
  }

  .logo-wrapper {
    width: 76px;
    height: 76px;
  }

  .login-card {
    padding: 28px 24px;
    border-left: none;
    border-top: 1px solid var(--color-white-20);
  }
}

@media (max-width: 600px) {
  .login-extras {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .step-body {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .alert,
  .chev,
  .custom-input,
  .login-btn,
  .toggle-password {
    animation: none;
    transition: none;
  }
}
</style>
