<template>
  <div class="forgot-password-page">
    <div class="background-overlay"></div>

    <div class="forgot-container">
      <div class="forgot-card">
        <div class="card-header">
          <div class="icon-wrapper">
            <el-icon class="icon"><Key /></el-icon>
          </div>
          <h2>忘记密码</h2>
          <p>使用机器码重置您的密码</p>
        </div>

        <el-steps :active="currentStep" align-center finish-status="success">
          <el-step title="输入信息" />
          <el-step title="验证机器码" />
          <el-step title="重置成功" />
        </el-steps>

        <!-- 步骤1: 输入用户信息 -->
        <div v-if="currentStep === 0" class="step-content">
          <el-form :model="resetForm" label-width="100px">
            <el-form-item label="用户名">
              <el-input v-model="resetForm.username" placeholder="请输入您的用户名" clearable />
            </el-form-item>

            <el-form-item label="机器码">
              <el-input
                v-model="resetForm.machine_code"
                placeholder="请输入机器码"
                type="textarea"
                :rows="3"
                clearable
              />
              <div class="form-hint">
                <el-button
                  link
                  type="primary"
                  :loading="loadingMachineCode"
                  @click="useCurrentMachineCode"
                >
                  使用当前机器码
                </el-button>
              </div>
            </el-form-item>

            <el-form-item label="校验码">
              <el-input
                v-model="resetForm.verification_code"
                placeholder="请输入4位数字校验码"
                maxlength="4"
                clearable
              />
              <div class="form-hint">校验码可在"获取机器码"页面查看</div>
            </el-form-item>
          </el-form>

          <div class="action-buttons">
            <el-button @click="goBack">返回登录</el-button>
            <el-button
              type="primary"
              :loading="resetting"
              :disabled="!canSubmit"
              @click="handleResetPassword"
            >
              重置密码
            </el-button>
          </div>
        </div>

        <!-- 步骤2: 重置成功 -->
        <div v-if="currentStep === 1" class="step-content success-content">
          <div class="reset-result">
            <el-icon class="result-icon-success"><CircleCheckFilled /></el-icon>
            <h3>密码重置成功</h3>
            <p class="result-subtitle">您的新密码是：</p>
            <div class="password-box">
              <span class="password-text">{{ newPassword }}</span>
              <el-button type="primary" size="small" @click="copyPassword"> 复制密码 </el-button>
            </div>
            <el-alert type="warning" :closable="false" class="password-tip">
              <template #title>
                <strong>重要提示：此密码仅显示一次，请立即复制保存</strong>
              </template>
              <div>登录后请尽快修改密码</div>
            </el-alert>
            <el-button type="primary" size="large" class="goto-login" @click="goToLogin">
              前往登录
            </el-button>
          </div>
        </div>
      </div>

      <div class="extra-links">
        <router-link to="/get-machine-code" class="link"> 获取机器码 </router-link>
        <span class="separator">|</span>
        <router-link to="/login" class="link">返回登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { CircleCheckFilled, Key } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { logger } from '@/utils/logger'
import { get, post } from '@/api/request'

const { pushSafe } = useRouterSafe()

const currentStep = ref(0)
const resetting = ref(false)
const loadingMachineCode = ref(false)
const newPassword = ref('')

const resetForm = ref({
  username: '',
  machine_code: '',
  verification_code: '',
})

const canSubmit = computed(() => {
  return (
    !!resetForm.value.username &&
    !!resetForm.value.machine_code &&
    !!resetForm.value.verification_code &&
    resetForm.value.verification_code.length === 4
  )
})

const useCurrentMachineCode = async () => {
  loadingMachineCode.value = true
  try {
    // get() 已自动解包，返回值即为 {code, data, message} 信封体
    const response = await get('/machine-code/get-machine-code')
    const payload = response?.data ?? response
    if (payload?.machine_code) {
      resetForm.value.machine_code = payload.machine_code
      resetForm.value.verification_code = payload.verification_code ?? ''
      ElMessage.success('已自动填入当前机器码和校验码')
    } else {
      ElMessage.error(response?.message || '获取机器码失败，请重试')
    }
  } catch (error: any) {
    logger.error('[ForgotPassword] 获取机器码失败', error)
    const msg =
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      error?.message ||
      '获取机器码失败，请检查系统服务是否正常'
    ElMessage.error(msg)
  } finally {
    loadingMachineCode.value = false
  }
}

const handleResetPassword = async () => {
  if (!canSubmit.value) {
    ElMessage.warning('请填写完整信息')
    return
  }

  resetting.value = true

  try {
    // post() 已自动解包，返回值即为 {code, data, message} 信封体
    const response = await post('/machine-code/reset-password-with-machine-code', undefined, {
      params: resetForm.value,
    })

    const payload = response?.data ?? response
    if (response?.code === 200 && payload?.new_password) {
      newPassword.value = payload.new_password
      currentStep.value = 1
      ElMessage.success('密码重置成功')
    } else if (response?.code === 200) {
      // 后端返回成功但未携带密码（兼容旧版）
      currentStep.value = 1
      newPassword.value = '(请查看系统临时文件)'
      ElMessage.success(response?.message || '密码重置成功')
    } else {
      const errMsg = response?.message || response?.detail || '重置密码失败，请检查填写信息'
      ElMessage.error(errMsg)
    }
  } catch (error: any) {
    logger.error('[ForgotPassword] 重置密码失败', error)
    const msg =
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      error?.message ||
      '重置密码失败，请检查网络连接'
    ElMessage.error(msg)
  } finally {
    resetting.value = false
  }
}

const copyPassword = () => {
  navigator.clipboard.writeText(newPassword.value).then(
    () => {
      ElMessage.success('密码已复制到剪贴板')
    },
    () => {
      ElMessage.error('复制失败，请手动复制')
    }
  )
}

const goBack = () => {
  pushSafe('/login')
}

const goToLogin = () => {
  pushSafe('/login')
}
</script>

<style scoped lang="scss">
.forgot-password-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #081c15 0%, $military-dark 100%);
  position: relative;
  padding: 20px;
  overflow-y: auto;
}

.background-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-image: url('/images/login-bg/bg1.jpg');
  background-size: cover;
  background-position: center;
  opacity: 0.15;
  z-index: 0;
}

.forgot-container {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 600px;
}

.forgot-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-radius: 16px;
  padding: 40px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.card-header {
  text-align: center;
  margin-bottom: 30px;
}

.icon-wrapper {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 80px;
  height: 80px;
  background: linear-gradient(135deg, #d4af37, #c9a227);
  border-radius: 50%;
  margin-bottom: 20px;
  box-shadow: 0 4px 15px rgba(212, 175, 55, 0.4);
}

.icon {
  font-size: 40px;
}

.card-header h2 {
  font-size: 28px;
  color: $military-dark;
  margin: 0 0 10px 0;
  font-weight: 600;
}

.card-header p {
  color: var(--color-text-secondary);
  font-size: 15px;
  margin: 0;
}

.step-content {
  margin-top: 30px;
}

.form-hint {
  font-size: 13px;
  color: var(--color-info);
  margin-top: 5px;
}

.action-buttons {
  display: flex;
  justify-content: space-between;
  margin-top: 30px;
}

.success-content {
  padding: 20px 0;
}

.new-password-display {
  text-align: center;

  p {
    font-size: 16px;
    color: var(--color-text-regular);
    margin-bottom: 15px;
  }
}

.password-box {
  display: inline-flex;
  align-items: center;
  padding: 15px 25px;
  background: var(--color-bg-hover);
  border: 2px solid #d4af37;
  border-radius: 8px;
  margin-bottom: 10px;
}

.password-text {
  font-size: 24px;
  font-weight: bold;
  color: $military-dark;
  letter-spacing: 2px;
  font-family: 'Courier New', monospace;
}

.extra-links {
  text-align: center;
  margin-top: 20px;
  font-size: 14px;
}

.link {
  color: rgba(255, 255, 255, 0.9);
  text-decoration: none;
  transition: color 0.3s;

  &:hover {
    color: #d4af37;
  }
}

.separator {
  color: rgba(255, 255, 255, 0.5);
  margin: 0 15px;
}

/* ── 密码重置成功 ── */
.reset-result {
  text-align: center;
  padding: 10px 0;
}
.result-icon-success {
  font-size: 56px;
  color: var(--color-success);
  margin-bottom: 12px;
}
.result-subtitle {
  margin: 10px 0 16px;
  font-size: 15px;
}
.password-box {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin: 16px 0;
  padding: 16px 20px;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 8px;
  border: 1px dashed #dcdfe6;
}
.password-text {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 3px;
  font-family: 'Courier New', monospace;
  color: var(--color-warning);
  user-select: all;
}
.password-tip {
  margin: 16px 0;
  text-align: left;
}
.goto-login {
  margin-top: 16px;
  min-width: 160px;
}

@media (max-width: 768px) {
  .forgot-card {
    padding: 30px 20px;
  }

  .card-header h2 {
    font-size: 24px;
  }

  .icon-wrapper {
    width: 60px;
    height: 60px;
  }

  .icon {
    font-size: 30px;
  }
}
</style>
