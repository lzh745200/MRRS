/**
 * 危险操作统一二次确认（批次 3）。
 *
 * 背景：删除组织 / 恢复备份 / 轮换密钥 / 重置密码这类操作此前各自实现确认弹窗，
 * 措辞与强度不一致，且"管理员重置他人密码"只有一次按钮点击就能执行。
 * 本 composable 提供统一入口：
 * - 普通危险操作：`ElMessageBox.confirm` + 统一的红色警示文案；
 * - 高危操作：要求**手工输入指定文本**（如目标用户名）才允许继续，避免手滑。
 *
 * 语义约定（与全仓其它确认弹窗一致）：确认返回 `true`，取消/关闭一律返回 `false`，
 * 调用方只在 `true` 时继续执行，**不吞异常、不抛错**。
 */
import { ElMessageBox } from 'element-plus'

export interface DangerConfirmOptions {
  /** 弹窗标题，如「确认重置密码」 */
  title: string
  /** 主体说明（支持 \n 换行） */
  message: string
  /** 确认按钮文字，默认「确定」 */
  confirmButtonText?: string
  /**
   * 高危操作要求手工输入的文本（如目标用户名）。
   * 传入则渲染输入框，输入不完全一致时禁止确认。
   */
  typedConfirmation?: string
}

export function useDangerConfirm() {
  /**
   * 弹出危险操作确认。
   * @returns true=用户确认；false=取消/关闭（调用方必须直接 return）
   */
  async function confirmDanger(options: DangerConfirmOptions): Promise<boolean> {
    const confirmButtonText = options.confirmButtonText ?? '确定'
    try {
      if (options.typedConfirmation !== undefined) {
        const expected = options.typedConfirmation
        await ElMessageBox.prompt(options.message, options.title, {
          type: 'warning',
          confirmButtonText,
          cancelButtonText: '取消',
          inputPlaceholder: `请输入「${expected}」以确认`,
          inputValidator: (value: string) =>
            value === expected || `输入不匹配，请完整输入「${expected}」`,
          distinguishCancelAndClose: true,
        })
      } else {
        await ElMessageBox.confirm(options.message, options.title, {
          type: 'warning',
          confirmButtonText,
          cancelButtonText: '取消',
          distinguishCancelAndClose: true,
        })
      }
      return true
    } catch {
      // 取消 / 关闭 / 输入校验失败统一视为「不执行」：
      // ElMessageBox 以 'cancel'/'close' 字符串或 Error 拒绝，一律不向上抛错打断页面
      return false
    }
  }

  return { confirmDanger }
}
