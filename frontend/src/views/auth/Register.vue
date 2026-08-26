<template>
  <div class="register-container">
    <el-card class="register-card">
      <template #header>
        <div class="card-header">
          <h2>用户注册</h2>
          <p class="subtitle">请使用管理员提供的通行码进行注册</p>
        </div>
      </template>

      <el-form
        ref="registerFormRef"
        :model="registerForm"
        :rules="registerRules"
        label-width="100px"
        @submit.prevent="handleRegister"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="registerForm.username"
            placeholder="请输入用户名（3-50个字符）"
            clearable
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="registerForm.password"
            type="password"
            placeholder="至少12位，含大小写字母、数字和特殊字符"
            show-password
            clearable
          />
        </el-form-item>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="registerForm.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            show-password
            clearable
          />
        </el-form-item>

        <el-form-item label="通行码" prop="passCode">
          <el-input
            v-model="registerForm.passCode"
            placeholder="请输入管理员提供的通行码"
            clearable
          >
            <template #append>
              <el-button @click="showPassCodeHelp">
                <el-icon><QuestionFilled /></el-icon>
              </el-button>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="姓名" prop="fullName">
          <el-input
            v-model="registerForm.fullName"
            placeholder="请输入真实姓名（可选）"
            clearable
          />
        </el-form-item>

        <el-form-item label="邮箱" prop="email">
          <el-input v-model="registerForm.email" placeholder="请输入邮箱（可选）" clearable />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="loading" style="width: 100%" @click="handleRegister">
            注册
          </el-button>
        </el-form-item>

        <el-form-item>
          <div class="footer-links">
            <router-link to="/login">已有账号？立即登录</router-link>
            <router-link to="/get-machine-code">获取机器码</router-link>
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 通行码帮助对话框 -->
    <el-dialog v-model="helpDialogVisible" title="如何获取通行码？" :width="DIALOG_SM">
      <div class="help-content">
        <el-steps direction="vertical" :active="3">
          <el-step title="步骤 1：获取机器码">
            <template #description>
              <p>点击"获取机器码"链接，复制您的机器码</p>
            </template>
          </el-step>
          <el-step title="步骤 2：联系管理员">
            <template #description>
              <p>将机器码提供给系统管理员</p>
            </template>
          </el-step>
          <el-step title="步骤 3：获取通行码">
            <template #description>
              <p>管理员会为您生成通行码，使用通行码即可注册</p>
            </template>
          </el-step>
        </el-steps>
      </div>
      <template #footer>
        <el-button type="primary" @click="helpDialogVisible = false"> 我知道了 </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_SM } from '@/config/dialog'
import { ref, reactive } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { logger } from '@/utils/logger'
import { QuestionFilled } from '@element-plus/icons-vue'
import { apiRequest } from '@/api/request'

const { pushSafe } = useRouterSafe()
const registerFormRef = ref<FormInstance>()
const loading = ref(false)
const helpDialogVisible = ref(false)

const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  passCode: '',
  fullName: '',
  email: '',
})

// 验证密码强度（与后端 PasswordPolicy 保持一致：≥12位 + 大写 + 小写 + 数字 + 特殊字符）
const validatePassword = (_rule: any, value: any, callback: any) => {
  if (!value) {
    callback(new Error('请输入密码'))
    return
  }
  const errors: string[] = []
  if (value.length < 12) errors.push('至少12个字符')
  if (!/[A-Z]/.test(value)) errors.push('包含大写字母')
  if (!/[a-z]/.test(value)) errors.push('包含小写字母')
  if (!/\d/.test(value)) errors.push('包含数字')
  if (!/[!@#$%^&*()+\-=[\]{};':"\\|,.<>/?`~]/.test(value)) errors.push('包含特殊字符')
  if (errors.length > 0) {
    callback(new Error(`密码需要：${errors.join('、')}`))
  } else {
    callback()
  }
}

// 验证密码一致性
const validateConfirmPassword = (_rule: any, value: any, callback: any) => {
  if (value === '') {
    callback(new Error('请再次输入密码'))
  } else if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const registerRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    {
      min: 3,
      max: 50,
      message: '用户名长度在 3 到 50 个字符',
      trigger: 'blur',
    },
  ],
  password: [{ required: true, validator: validatePassword, trigger: 'blur' }],
  confirmPassword: [{ required: true, validator: validateConfirmPassword, trigger: 'blur' }],
  passCode: [{ required: true, message: '请输入通行码', trigger: 'blur' }],
  email: [{ type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }],
}

const handleRegister = async () => {
  if (!registerFormRef.value) return

  try {
    await registerFormRef.value.validate()
    loading.value = true

    await apiRequest({
      url: '/auth/register',
      method: 'post',
      data: {
        username: registerForm.username,
        password: registerForm.password,
        pass_code: registerForm.passCode,
        full_name: registerForm.fullName || registerForm.username,
        email: registerForm.email || undefined,
      },
    })

    ElMessage.success('注册成功！正在跳转到登录页面...')
    setTimeout(() => {
      pushSafe('/login')
    }, 1500)
  } catch (error: any) {
    logger.error('注册失败', error)
    const message = error.response?.data?.detail || error.message || '注册失败，请稍后重试'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

const showPassCodeHelp = () => {
  helpDialogVisible.value = true
}
</script>

<style scoped lang="scss">
.register-container {
  --military-dark: var(--color-primary-dark-2);
  --military-green: $military-dark;
  --military-gold: $badge-gold;
  --military-gold-light: $badge-gold-lighter;
  --text-white: var(----color-bg-card);

  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  overflow-y: auto;
  background: linear-gradient(135deg, var(--military-dark) 0%, var(--military-green) 100%);
  padding: 20px;
}

.register-card {
  width: 100%;
  max-width: 500px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.95);

  :deep(.el-card__header) {
    background: linear-gradient(135deg, var(--military-green) 0%, var(--military-dark) 100%);
    color: var(--text-white);
    border-radius: 12px 12px 0 0;
  }
}

.card-header {
  text-align: center;

  h2 {
    margin: 0 0 8px 0;
    font-size: 24px;
    font-weight: 600;
    color: var(--text-white);
  }

  .subtitle {
    margin: 0;
    font-size: 14px;
    opacity: 0.9;
    color: var(--text-white);
  }
}

.footer-links {
  display: flex;
  justify-content: space-between;
  width: 100%;
  font-size: 14px;

  a {
    color: var(--military-green);
    text-decoration: none;

    &:hover {
      text-decoration: underline;
      color: var(--military-gold);
    }
  }
}

.help-content {
  padding: 20px 0;

  :deep(.el-step__description) {
    p {
      margin: 8px 0;
      color: var(--color-text-regular);
      line-height: 1.6;
    }
  }
}
</style>
