#!/usr/bin/env bash
# ci_backend_test_segment.sh — PR Checks 后端测试分段执行器（W24 v1.15.5）
#
# 背景（v1.15.0 ~ v1.15.4 实证）：
#   - 单进程/两段式（integration+security 一段、unit 一段）均在 ubuntu-latest 上
#     约 24 分钟后"进程消失 + exit 1"，日志里没有 FAILED 摘要、没有覆盖率汇总表，
#     进度行停在 integration 段附近（见 v1.15.3/v1.15.4 注释与 PR Checks annotation）。
#   - 该签名与用例断言失败不同：更像进程被 runner 内存限制杀掉（TestClient 与
#     SQLAlchemy 会话叠加 + 覆盖率数据累积）。xdist 未能规避（v1.15.0/1.15.1）。
#
# 本脚本的规避思路：**更细粒度、独立进程、逐段可定位**
#   - 把 integration/security 与 unit（再按目录/文件名首字母拆成多个均衡段）拆成
#     6 个独立 pytest 进程顺序执行：每个进程退出即释放全部内存与覆盖率对象，
#     单段峰值显著低于"一次跑全量"；
#   - 每段单独日志（$RUNNER_TEMP/pytest-seg-<name>.log），失败时把该段真实
#     FAILED/ERROR（或"疑似被杀"的日志尾部）打成 ::error:: 注解，避免旧版把
#     pytest 进度行（tests/xxx.py ..... [ 8%]）误报成"覆盖率缺口"，淹没真因；
#   - 覆盖率用 --cov-append 跨进程合并：前 N-1 段加 --cov-fail-under=0（部分数据
#     不判阈值），最后一段（--mode final）不加该参数 → 仍由 backend/.coveragerc
#     的 fail_under=100 单一来源判定最终覆盖率。
#
# 用法（在 backend/ 目录下执行）：
#   bash ../scripts/ci_backend_test_segment.sh --name seg1-integration --mode first tests/integration tests/security
#   bash ../scripts/ci_backend_test_segment.sh --name seg2-unit-api --mode partial tests/unit/api
#   bash ../scripts/ci_backend_test_segment.sh --name seg6-unit-root-c --mode final tests/unit/test_c*.py
#
# --mode first  : 删除旧 .coverage（覆盖数据起点）
# --mode partial: 追加覆盖率，不判阈值
# --mode final  : 追加覆盖率并输出报表，按 .coveragerc fail_under 判定最终阈值
#
# 退出码 = pytest 退出码（脚本自身失败也是非 0）。仅用于 Linux CI（bash）。

set -uo pipefail

NAME="segment"
MODE="partial"
while [ $# -gt 0 ]; do
  case "$1" in
    --name) NAME="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --) shift; break ;;
    *) break ;;
  esac
done

if [ $# -eq 0 ]; then
  echo "::error::ci_backend_test_segment.sh: no pytest targets given"
  exit 2
fi

SLUG=$(printf '%s' "$NAME" | tr -c 'A-Za-z0-9._-' '_')
LOG_DIR="${RUNNER_TEMP:-/tmp}"
LOG="$LOG_DIR/pytest-seg-$SLUG.log"

COV_ARGS=(--cov=app --cov-branch --cov-append)
case "$MODE" in
  first)
    rm -f .coverage
    COV_ARGS+=(--cov-report= --cov-fail-under=0)
    ;;
  partial)
    COV_ARGS+=(--cov-report= --cov-fail-under=0)
    ;;
  final)
    COV_ARGS+=(--cov-report=term-missing --cov-report=json:coverage-branch.json --cov-report=xml)
    ;;
  *)
    echo "::error::ci_backend_test_segment.sh: unknown --mode '$MODE' (first|partial|final)"
    exit 2
    ;;
esac

echo "===== [$NAME] mode=$MODE targets=$* ====="
echo "===== [$NAME] log=$LOG ====="
free -m 2>/dev/null || true
date -u +"started_at=%Y-%m-%dT%H:%M:%SZ"

set -o pipefail
python -m pytest "$@" -q --tb=short -rR --reruns 2 --reruns-delay 1 \
  "${COV_ARGS[@]}" 2>&1 | tee "$LOG"
STATUS=${PIPESTATUS[0]}

echo "===== [$NAME] pytest exit=$STATUS ====="
free -m 2>/dev/null || true
date -u +"finished_at=%Y-%m-%dT%H:%M:%SZ"

if [ "$STATUS" -ne 0 ]; then
  echo "===== [$NAME] failure signals ====="
  SIGNALS=$(grep -aE "^(FAILED|ERROR) |INTERNALERROR|MemoryError|worker crashed|Killed|Out of memory|Coverage failure|Required test coverage" "$LOG" 2>/dev/null | head -8 | cut -c1-500)
  if [ -n "$SIGNALS" ]; then
    printf '%s\n' "$SIGNALS" | sed 's/^/::error::/'
  else
    # 无 FAILED 摘要 = 典型的进程被杀/OOM 签名：把日志尾部（去掉进度行）打出来
    TAIL=$(grep -avE "^tests/.*\[[ 0-9]+%\]$" "$LOG" 2>/dev/null | tail -6 | tr '\n' '|' | cut -c1-1200)
    echo "::error::[$NAME] pytest exited $STATUS with no FAILED summary (pytest usage/collection error, or process killed/OOM?) last lines: $TAIL"
  fi
  dmesg 2>/dev/null | tail -20 || true
  grep -aE "Out of memory|oom-kill|Killed process" /var/log/syslog 2>/dev/null | tail -5 || true
  exit 1
fi

exit 0
