/**
 * W23 通用 UI 组件统一出口（W6）
 *
 * 说明：
 * - 页面接入时**优先按需从具体 .vue 文件 import**（tree-shaking 友好，并遵守
 *   "每个 .vue 只由其唯一测试文件真实执行" 的单执行者规程）；
 * - 本 barrel 仅用于批量注册/工具链遍历，测试中以 mock 方式验证导出面。
 */
export { default as AppPageHeader } from './AppPageHeader.vue'
export { default as AppStatCard } from './AppStatCard.vue'
export { default as AppEmpty } from './AppEmpty.vue'
export { default as AppLoading } from './AppLoading.vue'
export { default as AppError } from './AppError.vue'
export { default as AppTableToolbar } from './AppTableToolbar.vue'
