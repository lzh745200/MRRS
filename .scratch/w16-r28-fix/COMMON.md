# R28 修复批次 · 通用约定（所有成员必读）

## 目标
修复 R27 全系统排查报告（docs/系统全面排查报告-2026-10-14.md，115 条：高13/中56/低46）中属于你范围的条目；逐项验证（测试+门禁）；不得引入回归。
报告条目在 v1.12.16（提交 203659b）之后可能已被部分修复（079ae82/62d6943/6a6bf30 等），**先复核再动手**；已修的记为 already-fixed，不要重复改。

## 硬性纪律
1. 只改你 scope 内文件。禁止 git add / git commit / git checkout / git stash / git clean —— Lead 统一提交。
2. 禁止用删断言/放宽断言/加 skip 来修绿。契约变化时只订正**锁定旧行为**的用例，并在报告里说明旧断言为何是错的。
3. 新代码必须自带测试。后端覆盖率门禁 100%（行+分支），前端同样 100%（含 branches）。
4. 环境：后端用 backend/.venv313/Scripts/python.exe（backend/.venv 已损坏，不要用）。
   定向测试示例：cd backend; .venv313/Scripts/python.exe -m pytest tests/unit/xxx.py -q -p no:randomly
   flake8：.venv313/Scripts/python.exe -m flake8 app/xxx.py --max-line-length=120 --max-complexity=16
   前端：cd frontend; npx vitest run tests/xxx.test.ts ; npx vue-tsc --noEmit ; npx eslint src --max-warnings=0
   不要跑全量后端套件（Lead 最后统一跑）。
5. Windows 编码：禁止 Set-Content / [IO.File]::WriteAllText 写非 ASCII 内容（历史 mojibake 事故），一律用编辑工具。
6. 不要改 backend/app/core/data_permission.py（Lead 负责 H8/M40）；不要动 frontend/dist、resources/frontend、backend/dist。
7. 需要产品决策时：采用安全默认（fail-closed）实现，并在报告里写明决策依据，不要留空。

## 交付报告格式（结束时 send_message 给 lead）
每条一行：编号 → fixed / already-fixed / cannot-fix(原因) | 文件:行 | 证据(命令 + 结果数字)
附：新增/修改测试文件清单、flake8/tsc/eslint 结果、未完成项与原因、你需要的协助。