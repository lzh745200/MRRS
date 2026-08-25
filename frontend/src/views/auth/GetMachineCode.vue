<template>
  <div class="public-machine-code-page">
    <div class="background-overlay"></div>

    <div class="content-container">
      <!-- 返回登录按钮 -->
      <div class="back-button">
        <el-button :icon="ArrowLeft" @click="pushSafe('/login')"> 返回登录 </el-button>
      </div>

      <!-- 主卡片 -->
      <div class="main-card">
        <div class="card-header">
          <div class="icon-wrapper">
            <el-icon class="icon"><Key /></el-icon>
          </div>
          <h2>获取机器码</h2>
          <p>用于密码重置和系统认证</p>
        </div>

        <div class="card-body">
          <!-- 获取机器码按钮 -->
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            style="width: 100%; margin-bottom: 30px"
            @click="getMachineCode"
          >
            <span v-if="!loading">获取当前机器码</span>
            <span v-else>获取中...</span>
          </el-button>

          <!-- 机器码信息 -->
          <div v-if="machineData" class="machine-info">
            <el-alert type="success" :closable="false" style="margin-bottom: 20px">
              <template #title>
                <strong>机器码获取成功</strong>
              </template>
              <div>请将以下信息提供给系统管理员，或用于密码重置</div>
            </el-alert>

            <!-- 校验码 - 突出显示 -->
            <div class="verification-code-section">
              <h3>校验码</h3>
              <div class="verification-code-display">
                <span class="code-text">{{ machineData.verification_code }}</span>
                <el-button
                  type="primary"
                  style="margin-left: 15px"
                  @click="copyToClipboard(machineData.verification_code, '校验码')"
                >
                  复制
                </el-button>
              </div>
              <p class="hint">这是一个4位数字，用于生成密码或重置密码</p>
            </div>

            <!-- 机器码 -->
            <div class="machine-code-section">
              <h3>机器码</h3>
              <div class="machine-code-display">
                <span class="code-text">{{ machineData.machine_code }}</span>
                <el-button
                  type="primary"
                  style="margin-left: 15px"
                  @click="copyToClipboard(machineData.machine_code, '机器码')"
                >
                  复制
                </el-button>
              </div>
              <p class="hint">这是当前计算机的唯一标识码</p>
            </div>

            <!-- 一键复制全部信息 -->
            <div class="copy-all-section">
              <el-button type="success" size="large" style="width: 100%" @click="copyAllInfo">
                <el-icon><CopyDocument /></el-icon>
                一键复制全部信息（机器码+校验码）
              </el-button>
              <p class="hint">点击后将机器码和校验码一起复制，方便发送给管理员</p>
            </div>

            <!-- 机器信息 -->
            <div class="machine-details">
              <h3>机器信息</h3>
              <el-descriptions :column="2" border>
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
            </div>

            <!-- 使用说明 -->
            <el-alert type="info" :closable="false" style="margin-top: 30px">
              <template #title>
                <strong>使用说明</strong>
              </template>
              <div class="usage-guide">
                <p><strong>方式一：生成初始密码</strong></p>
                <ol>
                  <li>将上方的<strong>校验码</strong>提供给系统管理员</li>
                  <li>管理员使用校验码为您生成初始登录密码</li>
                  <li>使用初始密码登录后，请立即修改密码</li>
                </ol>

                <p style="margin-top: 15px">
                  <strong>方式二：重置密码</strong>
                </p>
                <ol>
                  <li>点击下方"忘记密码"按钮</li>
                  <li>输入您的用户名</li>
                  <li>使用当前机器码和校验码重置密码</li>
                  <li>使用新密码登录后，请立即修改密码</li>
                </ol>
              </div>
            </el-alert>
          </div>
        </div>

        <!-- 底部操作 -->
        <div class="card-footer">
          <el-button
            type="success"
            size="large"
            style="width: 100%"
            @click="pushSafe('/forgot-password')"
          >
            忘记密码？立即重置
          </el-button>
        </div>
      </div>

      <!-- 额外链接 -->
      <div class="extra-links">
        <router-link to="/login" class="link">返回登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { ElMessage } from 'element-plus'
import { logger } from '@/utils/logger'
import { CopyDocument, ArrowLeft, Key } from '@element-plus/icons-vue'
import { get } from '@/api/request'
import { copyToClipboard } from '@/utils/clipboard'

const { pushSafe } = useRouterSafe()

interface MachineInfo {
  system: string
  release: string
  node: string
  processor: string
  machine: string
}

interface MachineData {
  machine_code: string
  verification_code: string
  machine_info: MachineInfo
}

const loading = ref(false)
const machineData = ref<MachineData | null>(null)

const getMachineCode = async () => {
  loading.value = true
  try {
    const response = await get('/machine-code/get-machine-code')
    // 后端返回 {code:200, data:{machine_code, verification_code, machine_info}}
    const resData = response?.data ?? response
    const payload = resData?.data ?? resData
    if (payload?.machine_code) {
      machineData.value = payload as MachineData
      ElMessage.success('机器码获取成功')
    } else {
      ElMessage.error(resData?.message || '获取机器码失败，请重试')
    }
  } catch (error: any) {
    logger.error('[GetMachineCode] 获取机器码失败', error)
    ElMessage.error(
      error?.response?.data?.detail ||
        error?.response?.data?.message ||
        error?.message ||
        '获取机器码失败，请检查系统服务是否正常'
    )
  } finally {
    loading.value = false
  }
}

const copyAllInfo = () => {
  if (!machineData.value) return
  const info = `机器码：${machineData.value.machine_code}\n校验码：${machineData.value.verification_code}`
  copyToClipboard(info, '全部信息')
}
</script>

<style scoped lang="scss">
.public-machine-code-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow-y: auto;
  background: linear-gradient(135deg, #081c15 0%, $military-dark 100%);
  position: relative;
  padding: 20px;
  box-sizing: border-box;
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

.content-container {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 700px;
  max-height: 90vh;
  overflow-y: auto;
}

.back-button {
  margin-bottom: 20px;
}

.main-card {
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
  background: linear-gradient(135deg, $badge-gold, #c9a227);
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

.card-body {
  margin-bottom: 30px;
}

.machine-info {
  animation: fadeIn 0.5s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.verification-code-section {
  margin-bottom: 30px;
  padding: 25px;
  background: linear-gradient(135deg, #fff9e6 0%, #fff5d6 100%);
  border: 2px solid $badge-gold;
  border-radius: 12px;

  h3 {
    font-size: 16px;
    color: $military-dark;
    margin: 0 0 15px 0;
    font-weight: 600;
  }
}

.verification-code-display {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 10px;
}

.code-text {
  font-size: 48px;
  font-weight: bold;
  color: $military-dark;
  letter-spacing: 8px;
  font-family: 'Courier New', monospace;
  text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.1);
}

.machine-code-section {
  margin-bottom: 30px;

  h3 {
    font-size: 16px;
    color: var(--color-text-primary);
    margin: 0 0 10px 0;
    font-weight: 600;
  }
}

.machine-code-display {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 15px;
  background: var(--color-bg-hover);
  border: 1px solid var(--color-border-light);
  border-radius: 8px;
  overflow-wrap: break-word;
  word-break: break-all;
}

.machine-code-display .code-text {
  font-size: 16px;
  color: $military-dark;
  font-family: 'Courier New', monospace;
  letter-spacing: 1px;
  flex: 1;
  text-align: center;
}

.machine-code-input {
  font-family: 'Courier New', monospace;
  font-size: 13px;
}

.copy-all-section {
  margin-bottom: 20px;
  padding: 20px;
  background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
  border: 1px solid #81c784;
  border-radius: 12px;
  text-align: center;
}

.machine-details {
  margin-bottom: 20px;

  h3 {
    font-size: 16px;
    color: var(--color-text-primary);
    margin: 0 0 10px 0;
    font-weight: 600;
  }
}

.hint {
  font-size: 13px;
  color: var(--color-info);
  margin: 8px 0 0 0;
  line-height: 1.5;
}

.usage-guide {
  font-size: 14px;
  line-height: 1.8;

  p {
    margin: 0 0 8px 0;
    color: var(--color-text-regular);
  }

  ol {
    margin: 5px 0 0 0;
    padding-left: 20px;

    li {
      margin-bottom: 5px;
      color: var(--color-text-regular);
    }
  }

  strong {
    color: $military-dark;
  }
}

.card-footer {
  border-top: 1px solid var(--color-border-light);
  padding-top: 20px;
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
    color: $badge-gold;
  }
}

@media (max-width: 768px) {
  .main-card {
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

  .code-text {
    font-size: 36px;
    letter-spacing: 6px;
  }

  .verification-code-section {
    padding: 20px 15px;
  }
}
</style>
