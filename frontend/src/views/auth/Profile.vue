<template>
  <div class="profile-container">
    <div class="page-header">
      <h1 class="page-title">个人中心</h1>
      <p class="page-description">查看和编辑您的个人资料信息</p>
    </div>
    <div class="profile-content">
      <div class="profile-card">
        <!-- 用户头像区域 -->
        <div class="avatar-section">
          <div class="avatar-container">
            <el-avatar
              v-if="!uploadingAvatar"
              :size="120"
              :src="userInfo.avatar"
              class="user-avatar"
            >
              {{ userInfo.name ? userInfo.name.charAt(0) : userInfo.username?.charAt(0) }}
            </el-avatar>
            <div v-else class="avatar-loading">
              <el-icon :size="40"><Loading /></el-icon>
            </div>
            <div class="avatar-uploader">
              <el-upload
                class="avatar-upload"
                action="#"
                :auto-upload="false"
                :before-upload="beforeUploadAvatar"
                :show-file-list="false"
                @change="handleAvatarChange"
              >
                <el-button
                  type="primary"
                  :disabled="uploadingAvatar"
                  :size="'small'"
                  class="upload-button"
                >
                  <span v-if="!uploadingAvatar">更换头像</span>
                  <span v-else>上传中...</span>
                </el-button>
              </el-upload>
            </div>
          </div>
          <div class="user-basic-info">
            <h2 class="user-name">{{ userInfo.name || userInfo.username }}</h2>
            <p class="user-role">{{ userInfo.roleName || '普通用户' }}</p>
            <p class="user-id">用户ID: {{ userInfo.id }}</p>
          </div>
        </div>

        <!-- 编辑/保存按钮 -->
        <div class="action-buttons">
          <el-button v-if="!editing" type="primary" :loading="saving" @click="startEditing">
            编辑资料
          </el-button>
          <div v-else class="save-cancel-group">
            <el-button type="primary" :loading="saving" @click="saveProfile"> 保存 </el-button>
            <el-button :loading="saving" :disabled="saving" @click="cancelEditing">
              取消
            </el-button>
          </div>
        </div>
      </div>

      <!-- 详细资料表单 -->
      <div class="detail-section">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>详细资料</span>
            </div>
          </template>

          <el-form
            ref="profileFormRef"
            :model="profileForm"
            :rules="profileRules as any"
            label-position="top"
            label-width="80px"
            size="default"
            class="profile-form"
          >
            <!-- 基本信息 -->
            <div class="form-section">
              <h3 class="section-title">基本信息</h3>

              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="用户名" prop="username">
                    <el-input
                      v-model="profileForm.username"
                      :disabled="true"
                      placeholder="用户名"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="姓名" prop="name">
                    <el-input
                      v-model="profileForm.name"
                      :disabled="!editing"
                      placeholder="请输入姓名"
                    />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="性别" prop="gender">
                    <el-select
                      v-model="profileForm.gender"
                      :disabled="!editing"
                      placeholder="请选择性别"
                      class="select-full-width"
                    >
                      <el-option label="男" value="male" />
                      <el-option label="女" value="female" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="出生日期" prop="birthday">
                    <el-date-picker
                      v-model="profileForm.birthday"
                      type="date"
                      :disabled="!editing"
                      placeholder="选择出生日期"
                      class="date-picker-full-width"
                      value-format="YYYY-MM-DD"
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </div>

            <!-- 联系方式 -->
            <div class="form-section">
              <h3 class="section-title">联系方式</h3>

              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="手机号码" prop="phone">
                    <el-input
                      v-model="profileForm.phone"
                      :disabled="!editing"
                      placeholder="请输入手机号码"
                      type="tel"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="电子邮箱" prop="email">
                    <el-input
                      v-model="profileForm.email"
                      :disabled="!editing"
                      placeholder="请输入电子邮箱"
                      type="email"
                    />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-row>
                <el-col :span="24">
                  <el-form-item label="联系地址" prop="address">
                    <el-input
                      v-model="profileForm.address"
                      :disabled="!editing"
                      placeholder="请输入联系地址"
                      type="textarea"
                      :rows="2"
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </div>

            <!-- 其他信息 -->
            <div class="form-section">
              <h3 class="section-title">其他信息</h3>

              <el-row :gutter="20">
                <el-col :span="12">
                  <el-form-item label="所属部门" prop="department">
                    <el-input
                      v-model="profileForm.department"
                      :disabled="!editing"
                      placeholder="请输入所属部门"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item label="职务" prop="position">
                    <el-input
                      v-model="profileForm.position"
                      :disabled="!editing"
                      placeholder="请输入职务"
                    />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-row>
                <el-col :span="24">
                  <el-form-item label="备注" prop="remark">
                    <el-input
                      v-model="profileForm.remark"
                      :disabled="!editing"
                      placeholder="请输入备注信息"
                      type="textarea"
                      :rows="3"
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </div>
          </el-form>
        </el-card>
      </div>

      <!-- 账户安全信息 -->
      <div class="security-section">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>账户安全</span>
            </div>
          </template>

          <div class="security-info">
            <div class="security-item">
              <div class="security-label">
                <span>上次登录时间</span>
              </div>
              <div class="security-value">
                {{ userInfo.lastLoginTime || '暂无记录' }}
              </div>
            </div>

            <div class="security-item">
              <div class="security-label">
                <span>上次登录IP</span>
              </div>
              <div class="security-value">
                {{ userInfo.lastLoginIp || '暂无记录' }}
              </div>
            </div>

            <div class="security-item">
              <div class="security-label">
                <span>账户状态</span>
              </div>
              <div class="security-value">
                <el-tag :type="userInfo.status === 'active' ? 'success' : 'danger'">
                  {{ userInfo.status === 'active' ? '正常' : '禁用' }}
                </el-tag>
              </div>
            </div>

            <div class="security-item">
              <div class="security-label">
                <span>密码强度</span>
              </div>
              <div class="security-value">
                <password-strength :password-strength="passwordStrength" />
              </div>
            </div>

            <div class="security-actions">
              <el-button type="primary" :disabled="saving" @click="navigateToChangePassword">
                修改密码
              </el-button>
              <el-button type="warning" :disabled="saving" @click="bindMfa"> 绑定MFA </el-button>
            </div>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElForm } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { getErrorMessage } from '@/utils/getErrorMessage'

import { useUserStore } from '@/stores/user'

const { pushSafe } = useRouterSafe()
const userStore = useUserStore()

// 表单引用
const profileFormRef = ref<InstanceType<typeof ElForm> | null>(null)

// 状态变量
const editing = ref(false)
const saving = ref(false)
const uploadingAvatar = ref(false)

// 用户信息接口
interface UserInfo {
  id: string
  username: string
  name: string
  avatar: string
  gender: string
  birthday: string
  phone: string
  email: string
  address: string
  department: string
  position: string
  remark: string
  roleName: string
  status: string
  lastLoginTime: string
  lastLoginIp: string
}

// 用户信息
const userInfo = reactive<UserInfo>({
  id: '',
  username: '',
  name: '',
  avatar: '',
  gender: '',
  birthday: '',
  phone: '',
  email: '',
  address: '',
  department: '',
  position: '',
  remark: '',
  roleName: '',
  status: 'active',
  lastLoginTime: '',
  lastLoginIp: '',
})

// 表单数据接口
interface ProfileForm {
  username?: string
  name?: string
  gender?: string
  birthday?: string
  phone?: string
  email?: string
  address?: string
  department?: string
  position?: string
  remark?: string
}

// 表单数据
const profileForm = reactive<ProfileForm>({
  username: '',
  name: '',
  gender: '',
  birthday: '',
  phone: '',
  email: '',
  address: '',
  department: '',
  position: '',
  remark: '',
})

// 验证规则接口
interface ValidationRule {
  required?: boolean
  message: string
  trigger: string | string[]
  min?: number
  max?: number
  pattern?: RegExp
  validator?: (rule: any, value: any, callback: (error?: string | Error) => void) => void
  whitespace?: boolean
  enum?: Array<string | number | boolean | null | undefined>
  type?: string
  len?: number
  transform?: (value: any) => any
  fields?: Record<string, ValidationRule[]>
  defaultField?: ValidationRule | ValidationRule[]
}

// 表单验证规则
const profileRules = reactive<Record<string, ValidationRule[]>>({
  name: [
    { required: true, message: '请输入姓名', trigger: 'blur' },
    { min: 2, max: 20, message: '姓名长度应在2-20个字符之间', trigger: 'blur' },
  ],
  phone: [
    { required: true, message: '请输入手机号码', trigger: 'blur' },
    {
      pattern: /^1[3-9]\d{9}$/,
      message: '请输入正确的手机号码',
      trigger: 'blur',
    },
  ],
  email: [
    { required: true, message: '请输入电子邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的电子邮箱格式', trigger: 'blur' },
  ],
  gender: [{ required: false, message: '请选择性别', trigger: 'change' }],
  birthday: [{ required: false, message: '请选择出生日期', trigger: 'change' }],
})

// 密码强度
const passwordStrength = computed((): string => {
  // 实际项目中应该从后端获取密码强度信息
  return 'medium' // 模拟中等强度
})

// 获取用户信息
const fetchUserProfile = async () => {
  try {
    const profile = await userStore.getUserProfile()
    if (!profile) return
    Object.assign(userInfo, profile)
    // 初始化表单数据
    Object.assign(profileForm, {
      username: profile.username || '',
      name: profile.name || '',
      gender: profile.gender || '',
      birthday: profile.birthday || '',
      phone: profile.phone || '',
      email: profile.email || '',
      address: profile.address || '',
      department: profile.department || '',
      position: profile.position || '',
      remark: profile.remark || '',
    })
  } catch (error) {
    ElMessage.error('获取用户信息失败')
  }
}

// 开始编辑
const startEditing = () => {
  editing.value = true
}

// 取消编辑
const cancelEditing = () => {
  editing.value = false
  // 重置表单数据
  Object.assign(profileForm, {
    username: userInfo.username || '',
    name: userInfo.name || '',
    gender: userInfo.gender || '',
    birthday: userInfo.birthday || '',
    phone: userInfo.phone || '',
    email: userInfo.email || '',
    address: userInfo.address || '',
    department: userInfo.department || '',
    position: userInfo.position || '',
    remark: userInfo.remark || '',
  })

  // 重置表单验证状态
  if (profileFormRef.value) {
    profileFormRef.value.clearValidate()
  }
}

// 保存个人资料
const saveProfile = async () => {
  if (!profileFormRef.value) return

  try {
    // 使用Promise包装validate方法
    const valid = await new Promise<boolean>((resolve) => {
      profileFormRef.value?.validate((valid: boolean) => {
        resolve(valid)
      })
    })

    if (!valid) {
      ElMessage.warning('请检查输入信息')
      return
    }

    saving.value = true

    // 后端 ProfileUpdate 期望 full_name 字段（前端表单使用 name）
    const updatedData = await userStore.updateUserProfile({
      ...profileForm,
      full_name: profileForm.name,
    })
    Object.assign(userInfo, updatedData)
    editing.value = false
    ElMessage.success('个人资料保存成功')
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : '保存失败，请重试'
    ElMessage.error(errorMessage)
  } finally {
    saving.value = false
  }
}

// 头像上传前检查
const beforeUploadAvatar = (file: File) => {
  const isJPG = file.type === 'image/jpeg' || file.type === 'image/png'
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isJPG) {
    ElMessage.error('只能上传JPG/JPEG/PNG格式的图片')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过2MB')
    return false
  }

  return true
}

// 处理头像上传
const handleAvatarChange = async (file: { raw?: File }) => {
  if (file.raw) {
    uploadingAvatar.value = true
    try {
      const res = await userStore.uploadAvatar(file.raw!)
      if (res?.avatar_url) {
        userInfo.avatar = res.avatar_url
      } else if (res?.url) {
        userInfo.avatar = res.url
      } else {
        // 回退：用本地 ObjectURL 预览
        userInfo.avatar = URL.createObjectURL(file.raw!)
      }

      ElMessage.success('头像上传成功')
    } catch (error) {
      ElMessage.error(getErrorMessage(error, '头像上传失败，请稍后重试'))
    } finally {
      uploadingAvatar.value = false
    }
  }
}

// 跳转到修改密码页面
const navigateToChangePassword = () => {
  pushSafe('/change-password')
}

// 绑定MFA — 跳转到双因素认证设置页
const bindMfa = () => {
  pushSafe('/profile/two-factor')
}

// 初始化
onMounted(() => {
  fetchUserProfile()
})
</script>

<style scoped>
.profile-container {
  padding: 20px;
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

.profile-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.profile-card {
  background: var(--color-bg-card);
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.08);
}

.avatar-section {
  display: flex;
  align-items: center;
  gap: 30px;
  margin-bottom: 24px;
}

.avatar-container {
  position: relative;
}

.user-avatar {
  cursor: pointer;
  border: 3px solid var(--color-bg-hover);
  transition: border-color 0.3s;
}

.user-avatar:hover {
  border-color: var(--color-primary);
}

.avatar-loading {
  width: 120px;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--color-bg-hover);
  border-radius: 50%;
}

.avatar-uploader {
  margin-top: 10px;
  text-align: center;
}

.upload-button {
  padding: 4px 12px;
}

.user-basic-info {
  flex: 1;
}

.user-name {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.user-role {
  font-size: 14px;
  color: var(--color-text-regular);
  margin-bottom: 4px;
}

.user-id {
  font-size: 12px;
  color: var(--color-info);
  margin: 0;
}

.action-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 20px;
  border-top: 1px solid var(--color-border-light);
}

.save-cancel-group {
  display: flex;
  gap: 12px;
}

.detail-section,
.security-section {
  background: var(--color-bg-card);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.08);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border-light);
}

.profile-form {
  padding: 0;
}

.form-section {
  margin-bottom: 30px;
}

.form-section:last-child {
  margin-bottom: 0;
}

.select-full-width,
.date-picker-full-width {
  width: 100%;
}

.security-info {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.security-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border-light);
}

.security-item:last-child {
  border-bottom: none;
}

.security-label {
  font-size: 14px;
  color: var(--color-text-regular);
}

.security-value {
  font-size: 14px;
  color: var(--color-text-primary);
}

.security-actions {
  display: flex;
  gap: 12px;
  padding-top: 20px;
  border-top: 1px solid var(--color-border-light);
  justify-content: flex-end;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .profile-container {
    padding: 10px;
  }

  .avatar-section {
    flex-direction: column;
    text-align: center;
    gap: 20px;
  }

  .el-row {
    margin-left: 0 !important;
    margin-right: 0 !important;
  }

  .el-col {
    padding-left: 0 !important;
    padding-right: 0 !important;
  }

  .security-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}
</style>
