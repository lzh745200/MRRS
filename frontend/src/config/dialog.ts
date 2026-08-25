/**
 * 弹窗宽度三档常量（UI 精细化设计方案 v2.0 · P1 底座）
 *
 * 全站 el-dialog 宽度只允许使用这三个档位，禁止魔法数：
 * - sm 480：表单单列 / 二次确认
 * - md 720：双列表单 / 详情查看
 * - lg 960：复杂表单 + 内嵌表格（白名单豁免需注释说明）
 *
 * 用法：
 *   <el-dialog :width="DIALOG_SM" ...>
 */
export const DIALOG_SM = '480px'
export const DIALOG_MD = '720px'
export const DIALOG_LG = '960px'

/** 兼容别名：与 tokens.scss --dialog-{sm,md,lg} 一一对应 */
export const DIALOG_WIDTH = {
  sm: DIALOG_SM,
  md: DIALOG_MD,
  lg: DIALOG_LG,
} as const

/** 表单标签宽两档（对齐 --form-label-width，长标签表单用第二档） */
export const FORM_LABEL_WIDTH = {
  normal: 100,
  wide: 120,
} as const
