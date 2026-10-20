---
labels: [done, severity-low]
blocks: []
blocked-by: ["w0-baseline/001-freeze-baseline.md"]
---

# 043: tokens 双维护一致性守卫

**What to build:** scripts 增加 tokens.scss 尾部 $ 映射与 tokens-vars.scss 一致性校验脚本并入 pre-commit（drift 即 fail）。

**Acceptance criteria:**
- [x] 人为制造漂移脚本 FAIL（自测）
- [x] pre-commit 本地运行通过

## Resolution（W19 完成）

守卫已落地并**漂移自测通过**：

- 脚本 `scripts/check_tokens_sync.py`：校验 `tokens-vars.scss` 每个 `$x: var(--y)` 桥接映射的 `--y`
  在 `tokens.scss` 任一主题块中有定义，漂移即非零退出；已接入 pre-commit
  （hook id `check-tokens-sync`，`entry: python scripts/check_tokens_sync.py --staged`，
  `files: ^frontend/src/styles/(tokens|tokens-vars)\.scss$`）。
- 实测三态：
  - 基线 `python scripts/check_tokens_sync.py` → **exit 0**（`[tokens-sync] 一致 ✓`）；
  - 人为注入 `$__w19_drift_probe: var(--__w19_nonexistent_token);` → **exit 1**，输出
    `TOKENS DRIFT —— 桥接引用了 tokens.scss 未定义的变量: $__w19_drift_probe -> --__w19_nonexistent_token (缺失)`；
  - 还原后 → **exit 0**。探针行已删除，工作区无残留。
- 本机**未安装 pre-commit**（PATH 与 backend/.venv 内均无 `pre_commit` 模块），故 hook 未以
  `pre-commit run` 形式执行；已用 hook 本体的同一命令 + 同参数语义完成等价验证（漂移必红）。
