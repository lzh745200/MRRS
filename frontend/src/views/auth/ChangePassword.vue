<template>
  <div class="change-password-container">
    <div class="page-header">
      <h1 class="page-title">修改密码</h1>
      <p class="page-description">请设置新的账户密码，确保密码安全且易于记忆</p>
    </div>

    <div class="password-card">
      <el-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-position="top"
        label-width="100px"
        size="default"
        class="password-form"
      >
        <!-- 原密码 -->
        <el-form-item label="当前密码" prop="oldPassword">
          <el-input
            v-model="passwordForm.oldPassword"
            type="password"
            placeholder="请输入当前密码"
            :prefix-icon="Lock"
            show-password
            :disabled="loading"
          />
        </el-form-item>

        <!-- 新密码 -->
        <el-form-item label="新密码" prop="newPassword" :error="newPasswordError">
          <el-input
            v-model="passwordForm.newPassword"
            type="password"
            placeholder="请输入新密码"
            :prefix-icon="Lock"
            show-password
            :disabled="loading"
            @input="validatePassword"
          />
          <div v-if="showPasswordHint" class="password-hint" :class="{ active: showPasswordHint }">
            <!-- 密码规则提示 -->
            <ul class="hint-list">
              <li :class="{ valid: passwordStrengthData.length >= 12 }">
                <el-icon v-if="passwordStrengthData.length >= 12" class="hint-check"
                  ><Check
                /></el-icon>
                密码长度至少12个字符
              </li>
              <li :class="{ valid: passwordStrengthData.hasUppercase }">
                <el-icon v-if="passwordStrengthData.hasUppercase" class="hint-check"
                  ><Check
                /></el-icon>
                包含至少一个大写字母
              </li>
              <li :class="{ valid: passwordStrengthData.hasLowercase }">
                <el-icon v-if="passwordStrengthData.hasLowercase" class="hint-check"
                  ><Check
                /></el-icon>
                包含至少一个小写字母
              </li>
              <li :class="{ valid: passwordStrengthData.hasNumber }">
                <el-icon v-if="passwordStrengthData.hasNumber" class="hint-check"
                  ><Check
                /></el-icon>
                包含至少一个数字
              </li>
              <li :class="{ valid: passwordStrengthData.hasSpecial }">
                <el-icon v-if="passwordStrengthData.hasSpecial" class="hint-check"
                  ><Check
                /></el-icon>
                包含至少一个特殊字符(!@#$%^&*)
              </li>
            </ul>
            <!-- 密码强度指示器 -->
            <div class="strength-indicator">
              <span class="strength-label">密码强度:</span>
              <div class="strength-bar">
                <div
                  class="strength-level"
                  :class="[
                    'level-' + passwordStrengthData.level,
                    'level-count-' + passwordStrengthData.validCount,
                  ]"
                ></div>
              </div>
              <span class="strength-text" :class="['text-' + passwordStrengthData.level]">{{
                passwordStrengthData.text
              }}</span>
            </div>
          </div>
        </el-form-item>

        <!-- 确认新密码 -->
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="passwordForm.confirmPassword"
            type="password"
            placeholder="请再次输入新密码"
            :prefix-icon="Lock"
            show-password
            :disabled="loading"
          />
        </el-form-item>

        <!-- 操作按钮 -->
        <el-form-item class="form-actions">
          <el-button
            type="primary"
            :loading="loading"
            :disabled="loading"
            size="large"
            class="submit-button"
            @click="handleChangePassword"
          >
            <span v-if="!loading">确认修改</span>
            <span v-else>修改中...</span>
          </el-button>
          <el-button
            v-if="!isForceChange"
            :loading="loading"
            :disabled="loading"
            size="large"
            @click="handleCancel"
          >
            取消
          </el-button>
          <span v-if="isForceChange" class="force-change-hint">
            <el-icon><Warning /></el-icon> 首次登录或密码已过期，必须修改密码后才能使用系统
          </span>
        </el-form-item>
      </el-form>
    </div>

    <!-- 安全提示卡片 -->
    <div class="security-tips-card">
      <el-card shadow="hover" :body-style="{ padding: '20px' }">
        <template #header>
          <div class="tips-header">
            <el-icon :size="20"><WarningFilled /></el-icon>
            <span class="tips-title">安全提示</span>
          </div>
        </template>
        <ul class="security-tips">
          <li>请定期更换密码，建议每90天更新一次</li>
          <li>请勿使用与其他网站相同的密码</li>
          <li>避免使用生日、手机号等容易被猜测的信息作为密码</li>
          <li>密码修改成功后，您需要重新登录系统</li>
        </ul>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox, ElForm } from 'element-plus'
import { useRouter } from 'vue-router'
import { WarningFilled, Lock, Check, Warning } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useAuthStore } from '@/stores/auth'
import { cancelAllRequests, freezeRequests } from '@/api/request'

const router = useRouter()
const userStore = useUserStore()
const authStore = useAuthStore()

// 是否为强制改密模式
const isForceChange = computed(() => authStore.mustChangePassword === true)

// 表单引用
const passwordFormRef = ref<InstanceType<typeof ElForm> | null>(null)

// 表单数据
const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

// 状态变量
const loading = ref(false)

// 改密成功后的跳转定时器句柄（卸载时清理，避免定时器泄漏/测试环境拆除后触发）
let redirectTimer: ReturnType<typeof setTimeout> | null = null

onBeforeUnmount(() => {
  if (redirectTimer !== null) {
    clearTimeout(redirectTimer)
    redirectTimer = null
  }
})
const newPasswordError = ref('')
const showPasswordHint = ref(false)

// 密码强度检查结果
const passwordStrengthData = reactive({
  length: 0,
  hasUppercase: false,
  hasLowercase: false,
  hasNumber: false,
  hasSpecial: false,
  validCount: 0,
  level: 0 as 0 | 1 | 2 | 3,
  text: '未设置',
})

// 表单验证规则
const passwordRules: Record<string, any[]> = reactive({
  oldPassword: [
    { required: true, message: '请输入当前密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6个字符', trigger: 'blur' },
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: (error?: Error) => void) => {
        if (!value) {
          callback(new Error('请输入新密码'))
        } else if (value === passwordForm.oldPassword) {
          callback(new Error('新密码不能与当前密码相同'))
        } else if (passwordStrengthData.validCount < 5 || passwordStrengthData.length < 12) {
          callback(new Error('密码强度不足，需满足全部5项规则且长度≥12位'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: (error?: Error) => void) => {
        if (!value) {
          callback(new Error('请再次输入新密码'))
        } else if (value !== passwordForm.newPassword) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
})

// 验证密码强度（与后端 PasswordPolicy.SPECIAL_WHITELIST 一致）
const validatePassword = (value: string) => {
  showPasswordHint.value = !!value

  // 重置验证结果
  passwordStrengthData.length = value.length
  passwordStrengthData.hasUppercase = /[A-Z]/.test(value)
  passwordStrengthData.hasLowercase = /[a-z]/.test(value)
  passwordStrengthData.hasNumber = /\d/.test(value)
  // 与后端白名单一致：!@#$%^&*()-_=+[]{}|;:,.<>?
  passwordStrengthData.hasSpecial = /[!@#$%^&*()\-_=+[\]{}|;:,.<>?]/.test(value)

  // 计算符合规则的数量（与后端 PasswordPolicy 一致：长度≥12）
  const validCount = [
    passwordStrengthData.length >= 12,
    passwordStrengthData.hasUppercase,
    passwordStrengthData.hasLowercase,
    passwordStrengthData.hasNumber,
    passwordStrengthData.hasSpecial,
  ].filter(Boolean).length

  passwordStrengthData.validCount = validCount

  // 设置强度等级
  if (validCount === 0) {
    passwordStrengthData.level = 0
    passwordStrengthData.text = '未设置'
  } else if (validCount <= 2) {
    passwordStrengthData.level = 1
    passwordStrengthData.text = '弱'
  } else if (validCount <= 4) {
    passwordStrengthData.level = 2
    passwordStrengthData.text = '中'
  } else {
    passwordStrengthData.level = 3
    passwordStrengthData.text = '强'
  }

  // 清除错误提示
  if (validCount >= 3) {
    newPasswordError.value = ''
  }
}

// 处理密码修改
const handleChangePassword = async () => {
  if (!passwordFormRef.value) return

  try {
    const valid = await new Promise<boolean>((resolve) => {
      passwordFormRef.value!.validate((valid: boolean) => {
        resolve(valid)
      })
    })

    if (!valid) {
      ElMessage.warning('请检查输入信息')
      return
    }

    // 二次确认
    await ElMessageBox.confirm('确定要修改密码吗？修改成功后需要重新登录。', '确认修改', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    loading.value = true
    await userStore.changePassword(passwordForm.oldPassword, passwordForm.newPassword)

    // 密码修改成功 — 后端已 revoke 所有 token（token_version+1），必须立即清理
    // 1. 立即冻结所有后续请求 + 取消 pending 请求
    //    （防止 setTimeout 跳转期间 Vue 组件发请求触发 401 竞态，覆盖成功消息）
    freezeRequests()
    cancelAllRequests()

    // 2. 同步清 token（阻止任何残留请求带失效 token）
    try {
      if (authStore && typeof authStore.logout === 'function') {
        authStore.logout()
      }
      if (userStore && typeof userStore.logout === 'function') {
        userStore.logout()
      }
    } catch (_) {
      // 即使退出失败也要清 token 跳转
    }

    // 3. 提示用户
    ElMessage.success('密码修改成功，请使用新密码重新登录')

    // 4. 硬跳转登录页（用极短延迟让 ElMessage 渲染一帧，冻结机制保证期间无 401）
    redirectTimer = setTimeout(() => {
      window.location.href = '/login'
    }, 100)
  } catch (error: any) {
    if (error?.name === 'Cancel') return
    // 后端返回 envelope: {code, message, field}
    const field = error?.response?.data?.field
    const serverMsg = error?.response?.data?.message
    const rawDetail = error?.response?.data?.detail
    const detailMsg = rawDetail || serverMsg || error?.message

    if (!detailMsg) {
      ElMessage.error('密码修改失败，请检查网络连接或联系管理员')
    } else if (field === 'old_password') {
      // 当前密码错误：高亮 oldPassword，清除新密码错误
      newPasswordError.value = ''
      if (passwordFormRef.value) {
        passwordFormRef.value.clearValidate(['newPassword', 'confirmPassword'])
      }
      ElMessage.error({ message: '当前密码错误，请重新输入', duration: 5000 })
    } else if (field === 'new_password') {
      // 新密码策略错误：高亮 newPassword 并显示后端具体消息
      newPasswordError.value = String(detailMsg)
      ElMessage.error({ message: String(detailMsg), duration: 5000 })
    } else {
      // 其它错误（如 403/500）
      ElMessage.error(typeof detailMsg === 'string' ? detailMsg : '密码修改失败')
    }
  } finally {
    loading.value = false
  }
}

// 处理取消
const handleCancel = async () => {
  if (passwordForm.oldPassword || passwordForm.newPassword || passwordForm.confirmPassword) {
    try {
      await ElMessageBox.confirm('确定要取消修改吗？当前输入将不会保存。', '确认取消', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info',
      })
      router.back()
    } catch {
      // 继续留在当前页面
    }
  } else {
    router.back()
  }
}

// 监听新密码变化，自动验证确认密码
watch(
  () => passwordForm.newPassword,
  () => {
    if (passwordForm.confirmPassword && passwordForm.confirmPassword !== passwordForm.newPassword) {
      if (passwordFormRef.value) {
        passwordFormRef.value.validateField('confirmPassword')
      }
    }
  }
)
</script>

<style lang="scss" scoped>
.change-password-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 30px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.page-description {
  font-size: 14px;
  color: var(--color-text-regular);
  margin: 0;
}

.force-change-hint {
  display: inline-block;
  margin-left: 12px;
  font-size: 13px;
  color: var(--color-warning);
  line-height: 40px;
}

.force-change-hint .el-icon {
  vertical-align: middle;
  margin-right: 4px;
}

.password-card,
.security-tips-card {
  background: var(--color-bg-card);
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.08);
  margin-bottom: 24px;
}

.password-form {
  max-width: 600px;
  margin: 0 auto;
}

.password-hint {
  margin-top: 8px;
  padding: 12px;
  background-color: #f8f9fa;
  border-radius: 6px;
  border-left: 3px solid #e6f7ff;
  opacity: 0;
  transform: translateY(-10px);
  transition: all 0.3s ease;
}

.password-hint.active {
  opacity: 1;
  transform: translateY(0);
}

.hint-list {
  list-style: none;
  padding: 0;
  margin: 0 0 12px 0;
}

.hint-list li {
  font-size: 12px;
  color: var(--color-text-regular);
  margin-bottom: 6px;
  transition: color 0.3s;
  line-height: 1.5;
}

.hint-list li:last-child {
  margin-bottom: 0;
}

.hint-list li.valid {
  color: var(--color-success);
}

.hint-list li.valid .hint-check {
  color: var(--color-success);
  font-weight: bold;
}

.hint-list .hint-check {
  margin-right: 4px;
  vertical-align: middle;
}

.strength-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--color-border-light);
}

.strength-label {
  font-size: 12px;
  color: var(--color-text-regular);
  flex-shrink: 0;
}

.strength-bar {
  flex: 1;
  height: 6px;
  background-color: var(--color-border-light);
  border-radius: 3px;
  overflow: hidden;
  min-width: 120px;
}

.strength-level {
  height: 100%;
  border-radius: 3px;
  transition: all 0.3s ease;
  width: 0;
}

.level-0 {
  width: 0;
  background-color: var(--color-border-light);
}

.level-1 {
  background-color: var(--color-danger);
}

.level-2 {
  background-color: var(--color-warning);
}

.level-3 {
  background-color: var(--color-success);
}

.level-count-0 {
  width: 0;
}

.level-count-1 {
  width: 20%;
}

.level-count-2 {
  width: 40%;
}

.level-count-3 {
  width: 60%;
}

.level-count-4 {
  width: 80%;
}

.level-count-5 {
  width: 100%;
}

.strength-text {
  font-size: 12px;
  font-weight: 500;
  flex-shrink: 0;
  min-width: 30px;
}

.text-0 {
  color: var(--color-info);
}

.text-1 {
  color: var(--color-danger);
}

.text-2 {
  color: var(--color-warning);
}

.text-3 {
  color: var(--color-success);
}

.form-actions {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-top: 30px;
}

.submit-button {
  min-width: 120px;
}

.tips-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tips-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-inverse);
}

.security-tips {
  list-style: none;
  padding: 0;
  margin: 12px 0 0 0;
}

.security-tips li {
  position: relative;
  padding-left: 20px;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--color-text-regular);
  line-height: 1.6;
}

.security-tips li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: var(--color-danger);
  font-size: 16px;
}

.security-tips li:last-child {
  margin-bottom: 0;
}

@media (max-width: 768px) {
  .change-password-container {
    padding: 10px;
  }

  .password-card,
  .security-tips-card {
    padding: 16px;
  }

  .strength-indicator {
    flex-wrap: wrap;
  }

  .strength-bar {
    min-width: 100px;
  }

  .form-actions {
    flex-direction: column;
  }

  .submit-button {
    width: 100%;
  }
}
</style>
