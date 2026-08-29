/**
 * 应用入口 main.ts
 *
 * Element Plus 组件由 unplugin-vue-components 按需自动导入。
 * 如需使用 ElMessage/ElMessageBox 等命令式 API，从 element-plus 单独导入。
 */

// ── 第零层：DOM 级 CSS 注入，确保所有弹出层绝对居中 ──
//    .el-notification / .el-message 均为 document.body 的直接子元素，
//    使用 position:fixed + translate(-50%,-50%) 逐个居中于视口。
//    外观美化（动画/色条/阴影/响应式）由 styles/components/prompt.scss 提供。
//
//    注意：top:50%!important 会覆盖 Element Plus 的堆叠 inline top:Npx，
//    多个同时出现的通知/消息会重叠在视口同一位置。
//    当前系统 ElNotification 仅有 2 个调用点（errorHandler + BackupManagement），
//    同时触发的概率极低，此限制可接受。
const _style = document.createElement('style')
_style.textContent = `
  .el-message,.el-message--success,.el-message--error,.el-message--warning,.el-message--info{top:50%!important;left:50%!important;right:auto!important;bottom:auto!important;transform:translate(-50%,-50%)!important;position:fixed!important}
  .el-notification{top:50%!important;left:50%!important;right:auto!important;bottom:auto!important;transform:translate(-50%,-50%)!important;position:fixed!important;margin:0!important}
  .el-notification__group{display:flex!important;flex-direction:column!important;align-items:center!important;justify-content:center!important}
  .el-message-box{top:50%!important;left:50%!important;transform:translate(-50%,-50%)!important;position:fixed!important;margin:0!important}
`
document.head.appendChild(_style)

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './router/guards'
import { AuthStorage } from '@/utils/authStorage'
import { setupGlobalErrorHandler } from '@/utils/errorHandler'

// 全局样式（Element Plus 覆盖 + 通知居中 + 组件美化）
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

// ── 全局：ElMessage 默认显示关闭按钮 + 5s 持续时间 ──
//    Element Plus 2.x 通过 messageDefaults 对象配置全局默认值（非 ElMessage.defaults）。
import { messageDefaults } from 'element-plus'
Object.assign(messageDefaults, { showClose: true, duration: 5000 })

app.mount('#app')

export default app
