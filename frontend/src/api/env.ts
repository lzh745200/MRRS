/**
 * 运行环境检查 API
 * 提供系统运行环境的诊断与检查
 */

import { get } from '@/api/request'

// ==================== 类型定义 ====================

/** 系统信息 */
export interface SystemInfo {
  python_version: string
  platform: string
  env_mode: string
  /** true=PyInstaller 冻结运行时（自包含安装包，无 pip 可装） */
  frozen?: boolean
}

/** 单条依赖明细（分发名 / import 名 / 用途 / 是否安装 / 版本） */
export interface DependencyItem {
  distribution: string
  module: string
  purpose: string
  requirements: string
  installed: boolean
  version: string | null
}

/** 环境检查结果（R15：依赖分三级，只有 missing_packages 才算故障） */
export interface EnvCheckResult {
  system: SystemInfo
  /** 登记的依赖 → 版本（未安装为空串） */
  packages: Record<string, string>
  /** 逐条明细 */
  dependencies?: DependencyItem[]
  /** 运行时必需但缺失（红色告警） */
  missing_packages: string[]
  /** 运行时可选但缺失（功能降级提示） */
  optional_missing?: string[]
  /** 仅开发期依赖缺失（开发环境诊断） */
  dev_missing?: string[]
  /** 运行时依赖是否齐备 */
  runtime_ok?: boolean
  fix_command?: string
}

// ==================== API 函数 ====================

/** 检查系统运行环境 */
export async function checkEnv(): Promise<EnvCheckResult> {
  return get<EnvCheckResult>('/env/check')
}

// ==================== 分组导出 ====================

export const envApi = {
  check: checkEnv,
}
