<template>
  <div class="two-factor-settings">
    <el-card class="page-header">
      <div class="header-content">
        <h2>双因素认证设置</h2>
        <p class="description">管理您的账户双因素认证（2FA），增强账户安全性</p>
      </div>
    </el-card>

    <el-skeleton v-if="loading" :rows="4" animated />

    <template v-else>
      <!-- 状态卡片 -->
      <el-card class="status-card">
        <h3 class="section-title">认证状态</h3>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="双因素认证">
            <el-tag :type="isEnabled ? 'success' : 'info'">
              {{ isEnabled ? '已启用' : '未启用' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="认证方式">
            {{ isEnabled ? 'TOTP（基于时间的一次性密码）' : '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <el-alert
          v-if="!isEnabled"
          title="建议启用"
          type="warning"
          :closable="false"
          style="margin-top: 16px"
        >
          双因素认证为您的账户提供额外一层安全保护。启用后，登录时需要输入手机验证器生成的动态验证码。
        </el-alert>
        <el-alert v-else title="已保护" type="success" :closable="false" style="margin-top: 16px">
          您的账户已启用双因素认证保护。请妥善保管备用恢复码。
        </el-alert>
      </el-card>

      <!-- 启用 2FA（未启用时） -->
      <el-card v-if="!isEnabled && setupStep === 0" class="enable-card">
        <h3 class="section-title">启用双因素认证</h3>
        <p class="step-desc">
          请使用手机验证器应用（如 Google Authenticator、Microsoft
          Authenticator）扫描下方二维码，然后输入生成的验证码完成设置。
        </p>
        <el-button type="primary" :loading="enabling" @click="startEnable"> 开始设置 </el-button>
      </el-card>

      <!-- 设置步骤: 显示二维码 -->
      <el-card v-if="setupStep === 1" class="setup-card">
        <h3 class="section-title">第 1 步：扫描二维码</h3>
        <div class="qr-section">
          <!-- 后端返回 data:image/png;base64,... 的 dataURL，用 <img> 渲染而非 v-html -->
          <img class="qr-container" :src="qrCodeSvg" alt="TOTP 二维码" />
          <div class="secret-info">
            <p class="secret-label">或手动输入密钥：</p>
            <div class="secret-display">
              <code>{{ secretKey }}</code>
              <el-button size="small" text @click="copySecret">复制</el-button>
            </div>
          </div>
        </div>

        <h3 class="section-title" style="margin-top: 24px">第 2 步：验证令牌</h3>
        <p class="step-desc">请输入手机验证器生成的 6 位验证码</p>
        <el-form :model="verifyForm" inline @submit.prevent="verifyToken">
          <el-form-item>
            <el-input
              v-model="verifyForm.token"
              placeholder="6位验证码"
              maxlength="6"
              style="width: 200px"
              @input="verifyForm.token = verifyForm.token.replace(/\D/g, '').slice(0, 6)"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="verifying" @click="verifyToken">
              验证并启用
            </el-button>
          </el-form-item>
        </el-form>

        <!-- 备用恢复码 -->
        <div v-if="backupCodes.length" class="backup-codes">
          <h4 class="subsection-title">备用恢复码（请妥善保存）</h4>
          <el-alert title="重要" type="warning" :closable="false" style="margin-bottom: 12px">
            每个恢复码只能使用一次。请将这些恢复码保存在安全的地方。
          </el-alert>
          <div class="codes-grid">
            <el-tag v-for="(code, idx) in backupCodes" :key="idx" class="code-tag" type="info">
              {{ code }}
            </el-tag>
          </div>
          <el-button size="small" style="margin-top: 12px" @click="copyBackupCodes">
            复制全部恢复码
          </el-button>
        </div>

        <div style="margin-top: 16px">
          <el-button text @click="cancelSetup">取消设置</el-button>
        </div>
      </el-card>

      <!-- 禁用 2FA（已启用时） -->
      <el-card v-if="isEnabled" class="disable-card">
        <h3 class="section-title">禁用双因素认证</h3>
        <el-alert title="警告" type="error" :closable="false" style="margin-bottom: 16px">
          禁用双因素认证将降低账户安全性。此操作不可逆，确认要继续吗？
        </el-alert>
        <el-button type="danger" :loading="disabling" @click="handleDisable">
          禁用双因素认证
        </el-button>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { twoFactorApi } from '@/api/twoFactor'

const loading = ref(true)
const isEnabled = ref(false)
const enabling = ref(false)
const verifying = ref(false)
const disabling = ref(false)

const setupStep = ref(0) // 0=未开始, 1=显示二维码和验证
const qrCodeSvg = ref('')
const secretKey = ref('')
const backupCodes = ref<string[]>([])
const verifyForm = ref({ token: '' })

async function loadStatus() {
  loading.value = true
  try {
    const status = await twoFactorApi.getStatus()
    isEnabled.value = status.enabled
  } catch {
    ElMessage.warning('获取双因素认证状态失败')
  } finally {
    loading.value = false
  }
}

async function startEnable() {
  enabling.value = true
  try {
    const result = await twoFactorApi.enable()
    qrCodeSvg.value = result.qr_code
    secretKey.value = result.secret
    backupCodes.value = result.backup_codes || []
    setupStep.value = 1
  } catch (e: any) {
    ElMessage.error(e?.message || '启用双因素认证失败')
  } finally {
    enabling.value = false
  }
}

async function verifyToken() {
  if (!verifyForm.value.token || verifyForm.value.token.length !== 6) {
    ElMessage.warning('请输入6位验证码')
    return
  }
  verifying.value = true
  try {
    await twoFactorApi.verifyAndEnable(verifyForm.value.token)
    ElMessage.success('双因素认证已启用')
    isEnabled.value = true
    setupStep.value = 0
    verifyForm.value.token = ''
  } catch (e: any) {
    ElMessage.error(e?.message || '验证码错误，请重试')
  } finally {
    verifying.value = false
  }
}

function cancelSetup() {
  setupStep.value = 0
  verifyForm.value.token = ''
  qrCodeSvg.value = ''
  secretKey.value = ''
  backupCodes.value = []
}

async function handleDisable() {
  try {
    await ElMessageBox.confirm(
      '禁用双因素认证后，登录时将不再需要验证码。确定要继续吗？',
      '确认禁用',
      {
        confirmButtonText: '确定禁用',
        cancelButtonText: '取消',
        type: 'error',
      }
    )
    disabling.value = true
    await twoFactorApi.disable()
    ElMessage.success('双因素认证已禁用')
    isEnabled.value = false
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.message || '禁用失败')
    }
  } finally {
    disabling.value = false
  }
}

async function copySecret() {
  try {
    await navigator.clipboard.writeText(secretKey.value)
    ElMessage.success('密钥已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

async function copyBackupCodes() {
  try {
    await navigator.clipboard.writeText(backupCodes.value.join('\n'))
    ElMessage.success('恢复码已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

onMounted(() => {
  loadStatus()
})
</script>

<style scoped lang="scss">
.two-factor-settings {
  padding: 20px;
  max-width: 700px;
}

.page-header {
  margin-bottom: 20px;

  .header-content {
    h2 {
      margin: 0 0 8px;
      font-size: 22px;
      color: #303133;
    }
    .description {
      margin: 0;
      color: var(--color-info);
      font-size: 14px;
    }
  }
}

.status-card,
.enable-card,
.setup-card,
.disable-card {
  margin-bottom: 20px;
}

.section-title {
  margin: 0 0 16px;
  font-size: 17px;
  color: #303133;
  border-bottom: 2px solid var(--color-primary);
  padding-bottom: 8px;
}

.subsection-title {
  margin: 16px 0 8px;
  font-size: 15px;
  color: #303133;
}

.step-desc {
  margin: 0 0 16px;
  color: #606266;
  font-size: 14px;
  line-height: 1.6;
}

.qr-section {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  flex-wrap: wrap;
}

.qr-container {
  :deep(svg) {
    width: 200px;
    height: 200px;
  }
}

.secret-info {
  .secret-label {
    margin: 0 0 8px;
    color: #606266;
    font-size: 13px;
  }
  .secret-display {
    display: flex;
    align-items: center;
    gap: 8px;
    code {
      background: #f5f7fa;
      padding: 6px 10px;
      border-radius: 4px;
      font-size: 14px;
      word-break: break-all;
    }
  }
}

.backup-codes {
  margin-top: 24px;
}

.codes-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  .code-tag {
    font-family: monospace;
    font-size: 13px;
  }
}
</style>
