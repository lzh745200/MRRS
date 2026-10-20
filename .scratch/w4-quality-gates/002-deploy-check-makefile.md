---
labels: [done, severity-high]
blocks: []
blocked-by: []
---

# W4-T2 deploy-check 后端门禁修复

**来源**: 检测（`Makefile:46-48` 反斜杠续行使 `|| true` 吞掉 pytest+bandit 全部失败）

## 验收标准
- [x] 拆分为独立行：pytest 与 bandit 各自阻断；bandit 低级别告警单独容忍
- [x] 补 flake8 到 deploy-check
- [x] 本地验证：人为制造后端测试失败 → make deploy-check 必须非零退出
- [x] bandit JSON 输出落盘供审计

## 涉及文件
- `Makefile`

## Resolution（W19 完成）

`make deploy-check`（Makefile L82-95）已是「逐行独立、任一失败即中断」的阻塞链：

- L85 `cd backend && $(PYTHON) -m pytest tests/ --cov=app -q` —— 覆盖率阈值由
  `backend/.coveragerc` 的 `fail_under=100` 单一承载（不再内联 `--cov-fail-under`，避免屏蔽配置口径）。
- L86 补入了 flake8（`--max-line-length=120 --count --max-complexity=16`）。
- L87 bandit `-ll`（低危放行、中高危阻断）+ `-f json -o bandit-report.json` 落盘供审计。
- L90-93 前端三段仍为 `lint:check && type-check && test:coverage` 串联。

本机验证（本机**未安装 make**，按等价命令逐项实测）：

- **后端测试失败即非零退出且后续命令不执行**：在 `backend/tests/unit/` 写入刻意失败用例
  （临时探针文件，已删除）→ `pytest` 输出 `1 failed`、exit=1；随后用 `&&` 串联复跑，
  输出 `CHAIN_ABORTED`（后续命令未执行）。Makefile 的四条 recipe 行各自独立 shell，
  make 对任一非零退出即中止整个 target —— 与所验证语义一致。
- **bandit JSON 落盘**：`bandit -r app/ -ll -f json -o bandit-report.json` 实测 exit=0，
  产出合法 JSON（含 `metrics._totals`）。
- 顺带修复：`.gitignore` 增加 `backend/bandit-report.json`（此前只有 `backend/bandit_tmp.json`，
  deploy-check 落盘会让工作区出现未跟踪文件）。

未验证项：`make deploy-check` 的字面执行（本机无 make）；GNU make 的 recipe 中止语义为标准行为。
