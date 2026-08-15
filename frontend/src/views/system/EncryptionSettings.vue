<template>
  <div class="encryption-settings">
    <el-card class="page-header">
      <div class="header-content">
        <h2>数据库加密设置</h2>
        <p class="description">管理数据库加密功能</p>
      </div>
    </el-card>

    <!-- 加密状态 -->
    <el-card class="encryption-status">
      <h3 class="section-title">加密状态</h3>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="加密状态">
          <el-tag :type="encryptionStatus.enabled ? 'success' : 'info'">
            {{ encryptionStatus.enabled ? '已启用' : '未启用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="加密算法">
          {{ encryptionStatus.algorithm || 'N/A' }}
        </el-descriptions-item>
        <el-descriptions-item label="初始化时间">
          {{ formatDate(encryptionStatus.initialized_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="最后更新">
          {{ formatDate(encryptionStatus.updated_at) }}
        </el-descriptions-item>
      </el-descriptions>

      <el-alert
        v-if="!encryptionStatus.enabled"
        title="提示"
        type="warning"
        :closable="false"
        style="margin-top: 20px"
      >
        数据库加密未启用。启用加密可以保护您的数据安全,防止未授权访问。
      </el-alert>

      <el-alert v-else title="注意" type="info" :closable="false" style="margin-top: 20px">
        数据库加密已启用。请妥善保管您的密码,密码丢失将无法恢复数据。
      </el-alert>
    </el-card>

    <!-- 启用加密 -->
    <el-card v-if="!encryptionStatus.enabled" class="enable-encryption">
      <h3 class="section-title">启用数据库加密</h3>
      <el-form ref="initFormRef" :model="initForm" :rules="initRules" label-width="120px">
        <el-form-item label="设置密码" prop="password">
          <el-input
            v-model="initForm.password"
            type="password"
            placeholder="请输入密码(至少8位)"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="initForm.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="initializing" @click="handleInitialize">
            启用加密
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 修改密码 -->
    <el-card v-if="encryptionStatus.enabled" class="change-password">
      <h3 class="section-title">修改加密密码</h3>
      <el-form ref="changeFormRef" :model="changeForm" :rules="changeRules" label-width="120px">
        <el-form-item label="旧密码" prop="oldPassword">
          <el-input
            v-model="changeForm.oldPassword"
            type="password"
            placeholder="请输入旧密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="changeForm.newPassword"
            type="password"
            placeholder="请输入新密码(至少8位)"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="changeForm.confirmPassword"
            type="password"
            placeholder="请再次输入新密码"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="changing" @click="handleChangePassword">
            修改密码
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 禁用加密 -->
    <el-card v-if="encryptionStatus.enabled" class="disable-encryption">
      <h3 class="section-title">禁用数据库加密</h3>
      <el-alert title="警告" type="error" :closable="false" style="margin-bottom: 20px">
        禁用加密后,数据库将不再受到加密保护。此操作不可逆,请谨慎操作!
      </el-alert>
      <el-form :model="disableForm" label-width="120px">
        <el-form-item label="确认密码">
          <el-input
            v-model="disableForm.password"
            type="password"
            placeholder="请输入密码以确认"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button type="danger" :loading="disabling" @click="handleDisable">
            禁用加密
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { get, post } from '@/api/request'

const encryptionStatus = ref({
  enabled: false,
  algorithm: '',
  initialized_at: '',
  updated_at: '',
})

const initForm = ref({
  password: '',
  confirmPassword: '',
})

const changeForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const disableForm = ref({
  password: '',
})

const initFormRef = ref<FormInstance>()
const changeFormRef = ref<FormInstance>()

const initializing = ref(false)
const changing = ref(false)
const disabling = ref(false)

const validatePassword = (_rule: any, value: any, callback: any) => {
  if (value.length < 8) {
    callback(new Error('密码长度至少为8位'))
  } else {
    callback()
  }
}

const validateConfirmPassword = (_rule: any, value: any, callback: any) => {
  if (value !== initForm.value.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const validateNewConfirmPassword = (_rule: any, value: any, callback: any) => {
  if (value !== changeForm.value.newPassword) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const initRules: FormRules = {
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { validator: validatePassword, trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

const changeRules: FormRules = {
  oldPassword: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { validator: validatePassword, trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateNewConfirmPassword, trigger: 'blur' },
  ],
}

const loadStatus = async () => {
  try {
    const response = await get('/encryption/status')
    if (response.success) {
      encryptionStatus.value = response.data
    }
  } catch (error: any) {
    ElMessage.error(error.message || '加载状态失败')
  }
}

const handleInitialize = async () => {
  if (!initFormRef.value) return

  await initFormRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      await ElMessageBox.confirm(
        '启用加密后,每次启动应用都需要输入密码。确定要继续吗?',
        '确认启用',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )

      initializing.value = true

      const response = await post('/encryption/initialize', {
        password: initForm.value.password,
        confirm_password: initForm.value.confirmPassword,
      })

      if (response.success) {
        ElMessage.success(response.message)
        initForm.value = { password: '', confirmPassword: '' }
        await loadStatus()
      }
    } catch (error: any) {
      if (error !== 'cancel') {
        ElMessage.error(error.message || '启用加密失败')
      }
    } finally {
      initializing.value = false
    }
  })
}

const handleChangePassword = async () => {
  if (!changeFormRef.value) return

  await changeFormRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      changing.value = true

      const response = await post('/encryption/change-password', {
        old_password: changeForm.value.oldPassword,
        new_password: changeForm.value.newPassword,
        confirm_password: changeForm.value.confirmPassword,
      })

      if (response.success) {
        ElMessage.success(response.message)
        changeForm.value = {
          oldPassword: '',
          newPassword: '',
          confirmPassword: '',
        }
        await loadStatus()
      }
    } catch (error: any) {
      ElMessage.error(error.message || '修改密码失败')
    } finally {
      changing.value = false
    }
  })
}

const handleDisable = async () => {
  if (!disableForm.value.password) {
    ElMessage.warning('请输入密码')
    return
  }

  try {
    await ElMessageBox.confirm(
      '禁用加密后,数据库将不再受到保护。此操作不可逆,确定要继续吗?',
      '确认禁用',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'error',
      }
    )

    disabling.value = true

    const response = await post('/encryption/disable', {
      password: disableForm.value.password,
    })

    if (response.success) {
      ElMessage.success(response.message)
      disableForm.value.password = ''
      await loadStatus()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '禁用加密失败')
    }
  } finally {
    disabling.value = false
  }
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return 'N/A'
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadStatus()
})
</script>

<style scoped lang="scss">
.encryption-settings {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;

  .header-content {
    h2 {
      margin: 0 0 8px 0;
      font-size: 24px;
      color: #303133;
    }

    .description {
      margin: 0;
      color: var(--color-info);
      font-size: 14px;
    }
  }
}

.encryption-status,
.enable-encryption,
.change-password,
.disable-encryption {
  margin-bottom: 20px;
}

.section-title {
  margin: 0 0 20px 0;
  font-size: 18px;
  color: #303133;
  border-bottom: 2px solid var(--color-primary);
  padding-bottom: 10px;
}
</style>
