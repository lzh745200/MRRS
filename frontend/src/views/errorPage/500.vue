<template>
  <div class="error-page">
    <div class="error-container">
      <div class="error-code">500</div>
      <div class="error-title">服务器错误</div>
      <div class="error-description">
        抱歉，服务器出现了问题。<br />
        我们的技术团队已经收到通知，正在紧急处理中。
      </div>
      <div class="error-actions">
        <el-button type="primary" @click="goHome">返回首页</el-button>
        <el-button @click="goBack">返回上一页</el-button>
        <el-button @click="refresh">刷新页面</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useRouterSafe } from '@/composables/useRouterSafe'

const router = useRouter()
const { pushSafe } = useRouterSafe()

const goHome = () => {
  pushSafe('/')
}

const goBack = () => {
  router.go(-1)
}

const refresh = () => {
  window.location.reload()
}
</script>

<style scoped>
.error-page {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, #0a1929 0%, #1b4332 100%);
  color: var(--color-text-inverse);
}

.error-container {
  text-align: center;
  padding: 40px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(10px);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.error-code {
  font-size: 72px;
  font-weight: bold;
  color: #d4af37;
  margin-bottom: 20px;
}

.error-title {
  font-size: 32px;
  font-weight: bold;
  margin-bottom: 20px;
  color: var(--color-text-inverse);
}

.error-description {
  font-size: 16px;
  line-height: 1.6;
  margin-bottom: 30px;
  color: #ccc;
}

.error-actions {
  display: flex;
  justify-content: center;
  gap: 20px;
  flex-wrap: wrap;
}
</style>
