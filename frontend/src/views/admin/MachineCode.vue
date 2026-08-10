<template>
  <div class="machine-code-page">
    <el-card class="header-card">
      <h2>机器码管理</h2>
      <p class="description">用于单机版系统的用户认证和密码管理</p>
    </el-card>

    <!-- 机器码信息 -->
    <el-card class="machine-info-card">
      <h3>当前机器信息</h3>
      <el-button
        type="primary"
        :loading="loading"
        style="margin-bottom: 20px"
        @click="getMachineCode"
      >
        获取机器码
      </el-button>

      <el-descriptions v-if="machineData" :column="2" border>
        <el-descriptions-item label="机器码">
          <el-input v-model="machineData.machine_code" readonly style="width: 100%">
            <template #append>
              <el-button @click="copyToClipboard(machineData.machine_code)"> 复制 </el-button>
            </template>
          </el-input>
        </el-descriptions-item>

        <el-descriptions-item label="校验码">
          <el-tag type="success" size="large" style="font-size: 24px">
            {{ machineData.verification_code }}
          </el-tag>
        </el-descriptions-item>

        <el-descriptions-item label="操作系统">
          {{ machineData.machine_info.system }}
          {{ machineData.machine_info.release }}
        </el-descriptions-item>

        <el-descriptions-item label="计算机名">
          {{ machineData.machine_info.node }}
        </el-descriptions-item>

        <el-descriptions-item label="处理器">
          {{ machineData.machine_info.processor }}
        </el-descriptions-item>

        <el-descriptions-item label="架构">
          {{ machineData.machine_info.machine }}
        </el-descriptions-item>
      </el-descriptions>

      <el-alert v-if="machineData" type="info" :closable="false" style="margin-top: 20px">
        <template #title>
          <strong>使用说明：</strong>
        </template>
        <div>
          1. 将上方的<strong>校验码（{{ machineData.verification_code }}）</strong
          >提供给系统管理员<br />
          2. 管理员使用校验码为您生成初始登录密码<br />
          3. 使用初始密码登录后，请立即修改密码
        </div>
      </el-alert>
    </el-card>

    <!-- 生成初始密码（仅管理员） -->
    <el-card v-if="isAdmin" class="generate-password-card">
      <h3>生成用户初始密码</h3>
      <el-form :model="passwordForm" label-width="120px">
        <el-form-item label="用户名">
          <el-input v-model="passwordForm.username" placeholder="请输入用户名" />
        </el-form-item>

        <el-form-item label="校验码">
          <el-input
            v-model="passwordForm.verification_code"
            placeholder="请输入4位数字校验码"
            maxlength="4"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="generating" @click="generatePassword">
            生成密码
          </el-button>
        </el-form-item>
      </el-form>

      <el-alert v-if="generatedPassword" type="success" :closable="false" style="margin-top: 20px">
        <template #title>
          <strong>初始密码已生成：</strong>
        </template>
        <div style="font-size: 16px; margin-top: 10px">
          用户名：<strong>{{ generatedPassword.username }}</strong
          ><br />
          初始密码：<strong style="font-size: 20px; color: #e6a23c">{{
            generatedPassword.initial_password
          }}</strong>
          <el-button type="text" @click="copyToClipboard(generatedPassword.initial_password)">
            复制密码
          </el-button>
          <br />
          <span style="color: #909399; font-size: 14px">
            请将此密码安全地告知用户，用户首次登录后需要修改密码
          </span>
        </div>
      </el-alert>
    </el-card>

    <!-- 密码重置（忘记密码） -->
    <el-card class="reset-password-card">
      <h3>忘记密码？使用机器码重置</h3>
      <el-form :model="resetForm" label-width="120px">
        <el-form-item label="用户名">
          <el-input v-model="resetForm.username" placeholder="请输入用户名" />
        </el-form-item>

        <el-form-item label="机器码">
          <el-input
            v-model="resetForm.machine_code"
            placeholder="请输入机器码"
            type="textarea"
            :rows="2"
          />
          <el-button
            type="text"
            size="small"
            @click="resetForm.machine_code = machineData?.machine_code || ''"
          >
            使用当前机器码
          </el-button>
        </el-form-item>

        <el-form-item label="校验码">
          <el-input
            v-model="resetForm.verification_code"
            placeholder="请输入4位数字校验码"
            maxlength="4"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="warning" :loading="resetting" @click="resetPassword">
            重置密码
          </el-button>
        </el-form-item>
      </el-form>

      <el-alert v-if="resetResult" type="success" :closable="false" style="margin-top: 20px">
        <template #title>
          <strong>密码已重置：</strong>
        </template>
        <div style="font-size: 16px; margin-top: 10px">
          新密码：<strong style="font-size: 20px; color: #e6a23c">{{
            resetResult.new_password
          }}</strong>
          <el-button type="text" @click="copyToClipboard(resetResult.new_password)">
            复制密码
          </el-button>
          <br />
          <span style="color: #909399; font-size: 14px"> 请使用新密码登录并及时修改 </span>
        </div>
      </el-alert>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import {
  getMachineCode as fetchMachineCode,
  generateInitialPassword,
  resetPasswordWithMachineCode,
} from '@/api/machineCode'
import { copyToClipboard } from '@/utils/clipboard'

const userStore = useUserStore()

const loading = ref(false)
const generating = ref(false)
const resetting = ref(false)

const machineData = ref<any>(null)
const generatedPassword = ref<any>(null)
const resetResult = ref<any>(null)

const passwordForm = ref({
  username: '',
  verification_code: '',
})

const resetForm = ref({
  username: '',
  machine_code: '',
  verification_code: '',
})

const isAdmin = computed(() => {
  const role = userStore.currentUser?.role
  return role === 'super_admin' || role === 'admin'
})

const getMachineCode = async () => {
  loading.value = true
  try {
    const response = await fetchMachineCode()
    machineData.value = response
    ElMessage.success('机器码获取成功')
  } catch (error: any) {
    ElMessage.error(error.message || '获取机器码失败')
  } finally {
    loading.value = false
  }
}

const generatePassword = async () => {
  if (!passwordForm.value.username) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (!passwordForm.value.verification_code) {
    ElMessage.warning('请输入校验码')
    return
  }
  if (passwordForm.value.verification_code.length !== 4) {
    ElMessage.warning('校验码必须是4位数字')
    return
  }

  generating.value = true
  generatedPassword.value = null

  try {
    const response = await generateInitialPassword(passwordForm.value)
    generatedPassword.value = response
    ElMessage.success('初始密码已生成')
  } catch (error: any) {
    ElMessage.error(error.message || '生成密码失败')
  } finally {
    generating.value = false
  }
}

const resetPassword = async () => {
  if (!resetForm.value.username) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (!resetForm.value.machine_code) {
    ElMessage.warning('请输入机器码')
    return
  }
  if (!resetForm.value.verification_code) {
    ElMessage.warning('请输入校验码')
    return
  }

  resetting.value = true
  resetResult.value = null

  try {
    const response = await resetPasswordWithMachineCode(resetForm.value)
    resetResult.value = response
    ElMessage.success('密码已重置')
  } catch (error: any) {
    ElMessage.error(error.message || '重置密码失败')
  } finally {
    resetting.value = false
  }
}

onMounted(() => {
  getMachineCode()
})
</script>

<style scoped lang="scss">
.machine-code-page {
  padding: 20px;
}

.header-card {
  margin-bottom: 20px;

  h2 {
    margin: 0 0 8px 0;
    font-size: 24px;
    color: #303133;
  }

  .description {
    margin: 0;
    color: #909399;
    font-size: 14px;
  }
}

.machine-info-card,
.generate-password-card,
.reset-password-card {
  margin-bottom: 20px;

  h3 {
    margin: 0 0 20px 0;
    font-size: 18px;
    color: #303133;
    border-bottom: 2px solid var(--color-primary);
    padding-bottom: 10px;
  }
}
</style>
