<template>
  <div class="login-page">
    <!-- 背景轮播（仅渲染当前图，避免12张同时加载） -->
    <div class="background-carousel">
      <div class="bg-slide active" :style="{ backgroundImage: `url(${currentBg})` }"></div>
      <div class="bg-overlay"></div>
    </div>

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
          <h2>用户登录</h2>
          <p>请输入您的账号和密码</p>
        </div>

        <form class="login-form" @submit.prevent="handleLogin">
          <!-- 2FA 验证模式 -->
          <template v-if="twoFactorRequired">
            <div class="form-group">
              <label>双因素认证验证码</label>
              <div class="input-wrapper">
                <el-icon class="input-icon"><Key /></el-icon>
                <input
                  v-model="totpCode"
                  type="text"
                  placeholder="请输入6位TOTP验证码"
                  class="custom-input"
                  maxlength="6"
                  inputmode="numeric"
                  pattern="[0-9]*"
                  autofocus
                />
              </div>
              <p class="hint-text">请打开您的认证器应用（如 Google Authenticator）获取验证码</p>
            </div>

            <button type="submit" class="login-btn" :disabled="loading">
              <span v-if="!loading">验证并登录</span>
              <span v-else>验证中...</span>
            </button>

            <button type="button" class="back-btn" :disabled="loading" @click="resetTwoFactor">
              返回重新登录
            </button>
          </template>

          <!-- 正常登录模式 -->
          <template v-else>
            <div class="form-group">
              <label>账号</label>
              <div class="input-wrapper">
                <el-icon class="input-icon"><User /></el-icon>
                <input
                  v-model="username"
                  type="text"
                  placeholder="请输入用户名"
                  class="custom-input"
                  autocomplete="username"
                />
              </div>
            </div>

            <div class="form-group">
              <label>密码</label>
              <div class="input-wrapper">
                <el-icon class="input-icon"><Lock /></el-icon>
                <input
                  v-model="password"
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="请输入密码"
                  class="custom-input"
                  autocomplete="current-password"
                />
                <span class="toggle-password" @click="showPassword = !showPassword">
                  <el-icon v-if="showPassword"><View /></el-icon>
                  <el-icon v-else><Hide /></el-icon>
                </span>
              </div>
            </div>

            <!-- 机器码验证（可选） -->
            <div v-if="showMachineCodeInput" class="form-group">
              <label>机器码验证</label>
              <div class="input-wrapper">
                <el-icon class="input-icon"><Key /></el-icon>
                <input
                  v-model="verificationCode"
                  type="text"
                  placeholder="请输入4位校验码"
                  class="custom-input"
                  maxlength="4"
                />
              </div>
              <p class="hint-text">首次登录需要验证机器码，请联系管理员获取校验码</p>
            </div>

            <button type="submit" class="login-btn" :disabled="loading">
              <span v-if="!loading">立即登录</span>
              <span v-else>登录中...</span>
            </button>

            <label class="remember-me">
              <input v-model="rememberMe" type="checkbox" />
              <span>记住登录</span>
            </label>
          </template>
        </form>

        <!-- 忘记密码链接 -->
        <div class="extra-actions">
          <a href="#" class="forgot-link" @click.prevent="goToForgotPassword"> 忘记密码？ </a>
          <a href="#" class="register-link" @click.prevent="goToRegister"> 注册账户 </a>
          <a href="/get-machine-code" class="machine-code-link" @click.prevent="goToMachineCode">
            获取机器码
          </a>
          <a href="#" class="forgot-link" @click.prevent="openPermissionImport"> 导入权限包 </a>
        </div>

        <!-- 权限包导入对话框 -->
        <el-dialog
          v-model="permissionImportVisible"
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
          <div v-if="errorMsg" class="error-banner">
            {{ errorMsg }}
          </div>
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
import { post } from '@/api/request'

const router = useRouter()
const { pushSafe } = useRouterSafe()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const verificationCode = ref('')
const rememberMe = ref(false)
const loading = ref(false)
const errorMsg = ref('')
const showPassword = ref(false)
const showMachineCodeInput = ref(false)
const systemVersion = SYSTEM_VERSION
const copyrightOwner = COPYRIGHT_OWNER

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
      ElMessage.error(body.message || body.detail || '权限包验证失败')
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

// 当前背景图（只加载一张，避免12张同时请求）
const currentBg = computed(() => backgroundImages[currentBgIndex.value])

// 背景图片列表
const backgroundImages = [
  '/images/login-bg/bg1.jpg',
  '/images/login-bg/bg2.jpg',
  '/images/login-bg/bg3.jpg',
  '/images/login-bg/bg4.jpg',
  '/images/login-bg/bg5.jpg',
  '/images/login-bg/bg6.jpg',
  '/images/login-bg/bg7.jpg',
  '/images/login-bg/bg8.jpg',
  '/images/login-bg/bg9.jpg',
  '/images/login-bg/bg10.jpg',
  '/images/login-bg/bg11.jpg',
  '/images/login-bg/bg12.jpg',
]

const currentBgIndex = ref(0)
let carouselInterval: number | null = null
const imagesPreloaded = ref(false)

// 预加载所有背景图片，确保轮播流畅无黑屏
const preloadAllImages = async (): Promise<void> => {
  const promises = backgroundImages.map((src) => {
    return new Promise<void>((resolve) => {
      const img = new Image()
      img.onload = () => resolve()
      img.onerror = () => resolve() // 失败也继续，不阻塞轮播
      img.src = src
    })
  })
  await Promise.all(promises)
  imagesPreloaded.value = true
}

const startCarousel = () => {
  if (carouselInterval) clearInterval(carouselInterval)
  carouselInterval = window.setInterval(() => {
    currentBgIndex.value = (currentBgIndex.value + 1) % backgroundImages.length
  }, 5000)
}

onMounted(async () => {
  // 先预加载所有背景图，再启动轮播 — 杜绝黑屏/闪烁
  await preloadAllImages()
  startCarousel()
})

onUnmounted(() => {
  if (carouselInterval) {
    clearInterval(carouselInterval)
  }
})

const handleLogin = async () => {
  // 2FA 验证模式
  if (twoFactorRequired.value) {
    if (!totpCode.value || totpCode.value.length < 6) {
      errorMsg.value = '请输入6位TOTP验证码'
      return
    }

    loading.value = true
    errorMsg.value = ''

    try {
      const success = await authStore.verifyTwoFactorLogin(tempToken.value, totpCode.value)
      if (success) {
        applyRememberLogin()
        navigateAfterLogin()
        return
      }
      errorMsg.value = authStore.error || '2FA验证失败'
    } catch (err: any) {
      errorMsg.value = '2FA验证异常: ' + (err.message || '未知错误')
    } finally {
      loading.value = false
    }
    return
  }

  // 正常登录模式
  if (!username.value || !password.value) {
    errorMsg.value = '请输入用户名和密码'
    return
  }

  loading.value = true
  errorMsg.value = ''

  try {
    const result = await authStore.login(username.value, password.value)

    if (result.status === 'two_factor_required') {
      // 切换到 2FA 验证模式
      twoFactorRequired.value = true
      tempToken.value = result.tempToken
      totpCode.value = ''
      return
    }

    if (result.status === 'success') {
      applyRememberLogin()
      navigateAfterLogin()
      return
    }

    errorMsg.value = result.message || authStore.error || '登录失败'
  } catch (err: any) {
    errorMsg.value = '登录系统异常: ' + (err.message || '未知错误')
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

/** 重置 2FA 状态，返回正常登录 */
const resetTwoFactor = () => {
  twoFactorRequired.value = false
  tempToken.value = ''
  totpCode.value = ''
  errorMsg.value = ''
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
/* 定义变量 */
.login-page {
  --military-dark: var(--color-primary-dark-2);
  --military-green: var(--color-primary-dark-1);
  --military-gold: var(--color-accent-gold);
  --military-gold-light: #f0e68c;
  --text-white: var(----color-bg-card);
  --text-gray: #a8dadc;
}

.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--military-dark);
  position: relative;
  overflow-y: auto;
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

/* 背景轮播 */
.background-carousel {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 0;
}

.bg-slide {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-size: cover;
  background-position: center;
  background-color: #0a1a12; /* 绿色底色 — 图片加载前不露黑 */
  opacity: 0;
  transition: opacity 1.5s ease-in-out;
  will-change: opacity;
}

.bg-slide.active {
  opacity: 1;
}

.bg-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(8, 28, 21, 0.85) 0%, rgba(27, 67, 50, 0.7) 100%);
}

.login-container {
  display: flex;
  width: 950px;
  max-width: 95vw;
  max-height: 95vh;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(20px);
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  z-index: 1;
  overflow: hidden auto;
}

/* 左侧品牌区 */
.brand-section {
  flex: 1;
  background: linear-gradient(135deg, rgba(27, 67, 50, 0.95) 0%, rgba(8, 28, 21, 0.98) 100%);
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
  filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.3));
}

.brand-title {
  font-size: 34px;
  font-weight: bold;
  text-align: center;
  margin: 0 0 20px 0;
  line-height: 1.4;
  letter-spacing: 3px;
  color: var(--military-gold);
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.brand-subtitle {
  color: var(--military-gold-light);
  font-size: 16px;
  letter-spacing: 4px;
  text-align: center;
  margin: 0;
  padding: 12px 20px;
  border: 1px solid rgba(212, 175, 55, 0.3);
  border-radius: 8px;
  background: rgba(212, 175, 55, 0.1);
}

/* 右侧登录卡片 */
.login-card {
  flex: 1;
  padding: 50px 60px;
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-left: 1px solid rgba(255, 255, 255, 0.2);
}

.card-header {
  text-align: center;
  margin-bottom: 32px;
}

.card-header h2 {
  font-size: 28px;
  color: var(--color-text-inverse);
  margin: 0 0 10px 0;
  font-weight: 600;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.card-header p {
  color: rgba(255, 255, 255, 0.8);
  font-size: 15px;
  margin: 0;
}

.form-group {
  margin-bottom: 24px;
}

.form-group label {
  display: block;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
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
  color: rgba(255, 255, 255, 0.6);
  z-index: 1;
  display: flex;
  align-items: center;
}

.custom-input {
  width: 100%;
  padding: 14px 45px 14px 45px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 10px;
  font-size: 15px;
  transition:
    border-color 0.3s ease,
    background-color 0.3s ease,
    box-shadow 0.3s ease;
  background: rgba(255, 255, 255, 0.1);
  color: var(--color-text-inverse);
  box-sizing: border-box;
}

.custom-input::placeholder {
  color: rgba(255, 255, 255, 0.5);
}

.custom-input:focus {
  outline: none;
  border-color: var(--military-gold);
  background: rgba(255, 255, 255, 0.2);
  box-shadow: 0 0 0 4px rgba(212, 175, 55, 0.2);
}

.toggle-password {
  position: absolute;
  right: 14px;
  font-size: 18px;
  cursor: pointer;
  user-select: none;
  transition: transform 0.2s;
  filter: brightness(1.2);
  display: flex;
  align-items: center;
}

.toggle-password:hover {
  transform: scale(1.1);
}

.hint-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin: 6px 0 0 0;
  line-height: 1.4;
}

.login-btn {
  width: 100%;
  padding: 16px;
  background: linear-gradient(135deg, var(--military-gold), var(--color-accent-gold));
  color: var(--military-dark);
  border: none;
  border-radius: 10px;
  font-size: 17px;
  font-weight: 700;
  cursor: pointer;
  transition:
    transform 0.3s ease,
    box-shadow 0.3s ease,
    background 0.3s ease;
  margin-top: 10px;
  box-shadow: 0 4px 15px rgba(212, 175, 55, 0.4);
}

.login-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(212, 175, 55, 0.5);
  background: linear-gradient(135deg, #e0c048, var(--military-gold));
}

.remember-me {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  font-size: 13px;
  color: var(--military-gold-light, #f5d76e);
  cursor: pointer;
  user-select: none;
}
.remember-me input {
  accent-color: var(--military-gold, var(--color-accent-gold));
  cursor: pointer;
}

.login-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.back-btn {
  width: 100%;
  padding: 12px;
  background: transparent;
  color: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 10px;
  font-size: 14px;
  cursor: pointer;
  transition:
    border-color 0.3s ease,
    color 0.3s ease;
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

.extra-actions {
  display: flex;
  justify-content: space-around;
  margin-top: 16px;
  padding: 0 4px;
  gap: 12px;
  flex-wrap: wrap;
}

.forgot-link,
.register-link,
.machine-code-link {
  font-size: 14px;
  color: var(--military-gold-light);
  text-decoration: none;
  transition: color 0.3s ease;
}

.forgot-link:hover,
.register-link:hover,
.machine-code-link:hover {
  color: var(--military-gold);
  text-decoration: underline;
}

.card-footer {
  margin-top: 28px;
  text-align: center;
}

.error-banner {
  background: rgba(254, 215, 215, 0.2);
  color: #fca5a5;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
  margin-bottom: 14px;
  border: 1px solid rgba(254, 215, 215, 0.3);
  backdrop-filter: blur(10px);
}

.copyright {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin: 0;
}

/* 响应式 */
@media (max-height: 750px) {
  .login-container {
    width: 860px;
  }

  .brand-section {
    padding: 30px 30px;
  }

  .logo-wrapper {
    width: 80px;
    height: 80px;
    margin-bottom: 16px;
  }

  .brand-title {
    font-size: 26px;
    margin-bottom: 14px;
  }

  .brand-subtitle {
    font-size: 14px;
    padding: 8px 16px;
  }

  .login-card {
    padding: 30px 40px;
  }

  .card-header {
    margin-bottom: 20px;
  }

  .card-header h2 {
    font-size: 22px;
  }

  .form-group {
    margin-bottom: 16px;
  }

  .custom-input {
    padding: 10px 40px 10px 40px;
  }

  .login-btn {
    padding: 12px;
    font-size: 15px;
  }

  .card-footer {
    margin-top: 16px;
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
    padding: 30px 24px;
  }

  .brand-title {
    font-size: 24px;
  }

  .logo-wrapper {
    width: 80px;
    height: 80px;
  }

  .login-card {
    padding: 30px 24px;
    border-left: none;
    border-top: 1px solid rgba(255, 255, 255, 0.2);
  }
}

@media (max-width: 600px) {
  .extra-actions {
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }
}
</style>
