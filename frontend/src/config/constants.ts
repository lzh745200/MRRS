/**
 * 系统常量配置
 */
// 版本号随 tag 联动：CI 打包前 scripts/sync_version.py 会把 tag 版本写入
// frontend/.env.production 的 VITE_APP_VERSION（vite 构建时注入），本地开发
// 回落 .env；字符串兜底仅为环境文件缺失时的最后防线。
export const SYSTEM_VERSION = import.meta.env.VITE_APP_VERSION || '1.11.0'
export const COPYRIGHT_OWNER = '梁正辉'
export const SYSTEM_NAME = '帮扶管理信息系统'
