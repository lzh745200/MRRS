<template>
  <div class="error-page">
    <div class="error-container">
      <div class="error-code">403</div>
      <div class="error-title">权限不足</div>
      <div class="error-description">
        抱歉，您没有访问该页面的权限。<br />
        请联系系统管理员获取相应权限。
      </div>
      <div class="error-actions">
        <el-button type="primary" @click="goHome">返回首页</el-button>
        <el-button @click="goBack">返回上一页</el-button>
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
</script>

<style lang="scss" scoped>
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
  color: var(--color-accent-gold);
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
  color: var(--color-text-disabled, var(--color-text-secondary));
}

.error-actions {
  display: flex;
  justify-content: center;
  gap: 20px;
}
</style>
