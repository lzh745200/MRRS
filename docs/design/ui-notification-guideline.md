# UI 提示与通知使用规范（W11-T45 · 第 8 项）

> 适用范围：`frontend/src` 下所有视图、组件、组合式函数。
> 目标：消除「同一件事两种弹法」——轻量反馈用 `ElMessage`，需要被看见/可回溯的通知用 `notify`，
> 并且**异常文案只有一个出口**（`getErrorMessage`）。

## 1. 选型速查

| 场景 | 用法 | 理由 |
|------|------|------|
| 操作成功/失败的即时反馈（保存、删除、复制、提交） | `ElMessage.success/error/warning/info` | 3 秒内自动消失，不打断操作流 |
| 需要用户确认的破坏性操作 | `ElMessageBox.confirm` | 阻塞式确认，带取消路径 |
| 后台任务完成、审批结果、订阅/同步结果、需要点开详情的错误 | `notify.success/error/warning/info` | 右上角卡片、可关闭、5 秒停留，适合异步/跨页面事件 |
| 表单校验失败的字段级提示 | 组件内联错误文案（`el-form-item` 校验） | 就近反馈，不用全局弹层 |
| 开发调试信息 | `console.*` / `logger.*` | 永不出现在用户界面 |

判断口诀：**「用户此刻正在看的操作」→ ElMessage；「用户可能已经切走的事」→ notify。**

## 2. 唯一出口约束

1. 统一从 `@/utils/notify` 导入 `notify`（已内置 `showClose: true` + `duration: 5000` 默认值），
   不要直接 `import { ElNotification } from 'element-plus'` 后再手工传默认值。
2. 错误文案一律经 `@/utils/errorHandler` 的 `getErrorMessage(e)` 提取后再展示，
   禁止 `ElMessage.error(e.message)`（ESLint `no-restricted-syntax` 已拦截）。
3. 同一动作不要「ElMessage + notify」双发；异步任务结束只保留一种。
4. 视图层不得新增自建 toast/notification 组件；确需新形态先扩展 `utils/notify.ts`。

## 3. 代码示例

```ts
import { ElMessage } from 'element-plus'
import { notify } from '@/utils/notify'
import { getErrorMessage } from '@/utils/errorHandler'

// ✅ 同步操作的即时反馈
async function save() {
  try {
    await api.save(payload)
    ElMessage.success('保存成功')
  } catch (e) {
    ElMessage.error(getErrorMessage(e))
  }
}

// ✅ 异步/跨页面事件：审批结果、后台任务完成
function onApprovalFinished(task: { title: string; passed: boolean }) {
  notify[task.passed ? 'success' : 'warning']({
    title: task.passed ? '审批通过' : '审批被驳回',
    message: task.title,
  })
}
```

## 4. 迁移策略（渐进，不搞一次性批改）

- 新增代码一律按本规范执行（ESLint/评审把关）。
- 存量 800+ 处 `ElMessage` 调用**保持不变**：它们绝大多数是同步操作反馈，符合规范。
  仅在「后台任务/跨页面事件却用了 3 秒即逝的 ElMessage」时改为 `notify`。
- 不再新增 `ElNotification` 直接调用点（`git grep "ElNotification" frontend/src` 应只命中
  `utils/notify.ts` 与测试 mock）。

## 5. 关联

- 实现：`frontend/src/utils/notify.ts`（默认值包装）
- 错误文案：`frontend/src/utils/errorHandler.ts` → `getErrorMessage`
- ESLint：`frontend/.eslintrc.cjs` → `no-restricted-syntax`（`*.data.success` 双重解包、
  `ElMessage.error(e.message)` 原始异常文案）
