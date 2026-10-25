/**
 * 系统常量配置
 */
// 版本号随 tag 联动：CI 打包前会把 tag 版本写入 frontend/.env.production 的
// VITE_APP_VERSION（vite 构建时注入），本地开发回落 frontend/.env。
// 最后的兜底值由构建工具从 package.json 注入（`__APP_VERSION__`，见
// vite.config.ts / vitest.config.ts 的 define），**源码里不再写版本号字面量** ——
// 此前那串字面量是 sync-version 的同步目标之一，漏提交就会让
// 「版本一致性门禁」与 constants.test.ts 同时变红（v1.18.2~v1.18.5 连续 4 次）。
export const SYSTEM_VERSION = import.meta.env.VITE_APP_VERSION || __APP_VERSION__
export const COPYRIGHT_OWNER = '梁正辉'
export const SYSTEM_NAME = '帮扶管理信息系统'
