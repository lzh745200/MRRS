<template>
  <!-- UI v2.0 紧凑档 formalize：全局 size=small（与存量 470 处 size="small" 用法对齐，
       表格行高 36px / 控件 32px，1366×768 首屏信息量提升） -->
  <el-config-provider :locale="zhCn" size="small">
    <router-view v-slot="{ Component }">
      <template v-if="appError">
        <div class="app-error-boundary">
          <div class="error-content">
            <h1>页面异常</h1>
            <p>{{ errorMessage }}</p>
            <button class="refresh-btn" @click="handleRetry">重试</button>
          </div>
        </div>
      </template>
      <component :is="Component" v-else />
    </router-view>
  </el-config-provider>
</template>

<script setup lang="ts">
/**
 * 帮扶管理信息系统 - 根组件
 *
 * 职责：
 * 1. 提供 Element Plus 全局配置
 * 2. 路由容器 + 错误边界（组件级，切换路由自动恢复）
 */
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { onErrorCaptured, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { checkVersion } from '@/composables/useVersionCheck'

document.title = '帮扶管理信息系统'

// 启动时检查版本更新
onMounted(() => {
  checkVersion()
})

const router = useRouter()
const appError = ref(false)
const errorMessage = ref('请重试或返回首页')

onErrorCaptured((err, _instance, info) => {
  console.error('[App] 组件错误:', info, err)
  appError.value = true
  const msg = (err as any)?.message || String(err)
  errorMessage.value = msg.length > 80 ? msg.slice(0, 80) + '…' : msg
  return false // 阻止错误继续传播导致白屏
})

// 路由切换时自动清除错误状态
router.afterEach(() => {
  if (appError.value) appError.value = false
})

function handleRetry() {
  appError.value = false
}
</script>

<style>
/* 全局基础样式 */
html,
body,
#app {
  height: 100%;
  margin: 0;
  padding: 0;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* 错误边界回退UI */
.app-error-boundary {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(----color-primary-dark-2);
  color: var(--color-text-inverse);
  text-align: center;
}

.error-content h1 {
  font-size: 28px;
  color: var(----color-accent-gold);
  margin-bottom: 12px;
}

.error-content p {
  font-size: 16px;
  color: #a8dadc;
  margin-bottom: 24px;
}

.refresh-btn {
  padding: 12px 32px;
  background: linear-gradient(135deg, var(----color-accent-gold), #c9a227);
  color: var(----color-primary-dark-2);
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
}
</style>
