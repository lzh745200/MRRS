# 协作约定（多代理/多人并发开发规范）

> 2026-08-24 制定。背景：v1.10 发布周期内出现两个 AI 会话在同一分支无协调并发提交，
> `git add -A` 相互吸收半成品文件，导致一次 YAML 损坏进入远端、多次测试断言互相踩踏。
> 为避免复发，所有写入者（人类或代理）必须遵守以下约定。

## 1. 单写者原则（按目录分权）

| 目录归属 | 当前负责方 | 说明 |
|----------|-----------|------|
| `.github/workflows/*` | 安全会话（W1 系列） | CI/CD 触发器、门禁、Runner 运维 |
| `backend/app/api/**`、`backend/app/services/**`、`backend/app/models/**` | 业务会话 | 业务功能与修复 |
| `backend/tests/**` | 与所测代码同归属方 | 测试跟随被测代码 |
| `frontend/src/**`、`frontend/tests/**` | 业务会话（安全相关页面除外） | |
| `docs/**`、`CHANGELOG.md`、`README.md` | 双方可写，但**只追加自己的条目**，禁止重写他人段落 | |

跨目录改动前必须 `git fetch` + `git log --oneline -5` 确认对方无在途提交。

## 2. 提交纪律

- **禁止 `git add -A` / `git commit -a`**。只 add 自己明确修改的文件路径。
- 提交前 `git status --short` 自查：任何不属于自己任务范围的文件**不得**带入暂存区。
- 遇到工作区内他人的未提交修改：**不要动它**。需要干净基线时用
  `git stash push -u -m "snapshot-<日期>-<原因> -- <路径列表>"`（带路径），
  并在本文件 §4 登记。

## 3. PowerShell 编码禁令（Windows 环境）

- **禁止**用 `[System.IO.File]::WriteAllText` / `Set-Content` 写含非 ASCII 的文件
  （历史事故：GBK 控制页把 UTF-8 中文断言与注释写成 mojibake、甚至 t→o 字符替换）。
- 含中文的编辑一律使用代理内置 Edit 工具，或 `python -c` 脚本内显式
  `open(..., encoding='utf-8')` 读写。
- 正则批量替换后必须跑语法检查（py_compile / esbuild）确认未破坏结构。

## 3.5 前端测试约定

- **新增 `.vue` 组件或页面必须配套 `.test.ts`**，且覆盖率阈值已设为 100%——
  无测试的新代码会直接导致 CI 失败。
- 修改已有组件的 props/emit/事件名时，必须同步更新对应 `.test.ts`。
- 新增 API 端点时必须在对应 `tests/unit/api/` 或 `tests/unit/views/` 下补用例。
- 后端新增路由/服务方法同理：先写失败测试（TDD），再实现功能。

## 4. 快照登记簿

| stash/分支 | 日期 | 内容 | 状态 |
|------------|------|------|------|
| 分支 `stash/wip-20260823`（= stash@{0}） | 2026-08-23 | 安全会话 W1 中途产物 + 业务文档更新，共 47 文件；其中大部分已被后续正式提交覆盖 | 已固化分支，保留备查；确认无遗留价值后可 `git branch -D` |

## 5. 构建触发

- 安装包构建（windows/arm64）：仅 tag `v*` 或手动 dispatch（见各 workflow 触发器）。
- 派发前先 `gh api` / API 查询是否已有同 ref 在途运行，避免 concurrency 组互踩取消。
