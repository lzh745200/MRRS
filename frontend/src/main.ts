/**
 * 应用入口 main.ts
 *
 * Element Plus 组件由 unplugin-vue-components 按需自动导入。
 * 如需使用 ElMessage/ElMessageBox 等命令式 API，从 element-plus 单独导入。
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './router/guards'
import { AuthStorage } from '@/utils/authStorage'
import { setupGlobalErrorHandler } from '@/utils/errorHandler'

// ── 命令式组件（ElMessage/ElMessageBox/ElNotification）官方样式显式注入 ──
//    ElementPlusResolver 按需注入只对模板中的组件生效；命令式 API 直接
//    import 不会触发样式副作用。历史上这三个弹层的官方 CSS 从未进过
//    构建包（无底色/无排版 = "提示看不清"根因之一），此处显式补齐。
import 'element-plus/theme-chalk/el-message.css'
import 'element-plus/theme-chalk/el-message-box.css'
import 'element-plus/theme-chalk/el-notification.css'

// 全局样式（Element Plus 覆盖 + 组件美化）
import '@/styles/index.scss'
// Dashboard 深度视觉主题（注：tokens.scss 通过 vite additionalData 自动注入组件 SCSS 块）
import '@/styles/dashboard-theme.scss'
// 列表页统一规范化 (Phase 2)
import '@/styles/components/list-page.scss'
// 表单/详情页统一升级 (Phase 3)
import '@/styles/components/form-page.scss'
// 全站精美增强层 (UI v2.0 · U1)：柔和阴影/微交互/focus 光环，置于规范化层之后
import '@/styles/theme-elevated.scss'
// 打印样式（A4适配，隐藏非内容区域）
import '@/styles/print.scss'
// 无障碍增强（焦点环/skip-link/reduced-motion/high-contrast 主题补全）
import '@/styles/accessibility.css'

// 挂载前应用已记忆的主题，避免首屏主题闪烁（FOUC）
import { applyThemeToDom, THEME_STORAGE_KEY, DEFAULT_THEME } from '@/stores/config'
applyThemeToDom(localStorage.getItem(THEME_STORAGE_KEY) || DEFAULT_THEME)

// 一次性将旧版 localStorage token 迁移到 sessionStorage
AuthStorage.migrateFromLocalStorage()

const app = createApp(App)

// ADR-0007（W3-T1/工单042）：启用权限指令与防泄密水印
import { permission as vPermissionDirective } from './directives/permission'
import vWatermark from './directives/watermark'
app.directive('permission', vPermissionDirective)
app.directive('watermark', vWatermark)

app.use(createPinia())
app.use(router)

// 安装全局错误处理（window.onerror + unhandledrejection）
setupGlobalErrorHandler()

// ── 全局：ElMessage 默认关闭按钮 + 5s 时长 + grouping 去重 ──
//    grouping 使相同文案的多条消息合并为一条角标计数（401 并发重试场景
//    不再重复弹同文案）。Element Plus 2.x 通过 messageDefaults 配置全局默认。
import { messageDefaults } from 'element-plus'
Object.assign(messageDefaults, { showClose: true, duration: 5000, grouping: true })

app.mount('#app')

export default app
